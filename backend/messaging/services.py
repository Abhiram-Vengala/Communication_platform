r"""Business logic: creating messages, sending them, retrying, and applying provider updates.

Status model
------------
    scheduled -> queued -> sending -> sent -> delivered -> read
                              \-> failed          (can be retried if `retryable`)
                              \-> queued (auto-retry with backoff for temporary errors)

Provider callbacks may repeat or arrive out of order, so progress only moves forward by
rank (sent < delivered < read). `failed` from the provider is honoured until the message
is delivered, and a stale `sent` can never resurrect a failed message.
"""
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from . import templating
from .models import Message, MessageBatch, StatusEvent
from .providers import PERMANENT_CODES, ProviderError, friendly_message, get_provider, recipient_for

logger = logging.getLogger(__name__)
S = Message.Status
RANK = {S.SENT: 1, S.DELIVERED: 2, S.READ: 3}
PROVIDER_EVENT_STATUSES = {"sent", "delivered", "read", "failed"}


class NotRetryable(Exception):
    pass


class UnknownMessage(Exception):
    pass


class InvalidEvent(Exception):
    pass


# --- Creating ----------------------------------------------------------------
def create_messages(candidates, body, provider, scheduled_for=None, batch_body=None):
    """Create one independent Message per candidate (plus a batch if there are several)."""
    now = timezone.now()
    with transaction.atomic():
        batch = None
        if batch_body is not None:
            batch = MessageBatch.objects.create(body=batch_body, provider=provider)
        status = S.SCHEDULED if scheduled_for and scheduled_for > now else S.QUEUED
        messages = Message.objects.bulk_create(
            [
                Message(
                    candidate=c,
                    batch=batch,
                    body=templating.render(body, c),
                    provider=provider,
                    status=status,
                    scheduled_for=scheduled_for,
                    next_attempt_at=scheduled_for or now,
                )
                for c in candidates
            ]
        )
    return batch, messages


def enqueue(message_ids):
    """In eager mode send right away; otherwise the worker picks them up."""
    if settings.MESSAGING_EAGER_DISPATCH:
        for message_id in message_ids:
            dispatch_message(message_id)


# --- Sending -----------------------------------------------------------------
def _claim(message_id):
    """Atomically move a due message to `sending`. Returns False if someone else got it."""
    now = timezone.now()
    updated = Message.objects.filter(
        pk=message_id, status__in=[S.QUEUED, S.SCHEDULED], next_attempt_at__lte=now
    ).update(status=S.SENDING, attempts=F("attempts") + 1, updated_at=now)
    return updated == 1


def dispatch_message(message_id):
    """Send one message. Never raises: a failure here must not affect other messages."""
    if not _claim(message_id):
        return None
    message = Message.objects.select_related("candidate").filter(pk=message_id).first()
    if message is None:  # candidate deleted between claim and send
        return None
    try:
        provider = get_provider(message.provider)
        result = provider.send(
            to=recipient_for(message.provider, message.candidate),
            body=message.body,
            idempotency_key=str(message.idempotency_key),
        )
    except ProviderError as exc:
        _record_failure(message, exc)
    except Exception as exc:  # defensive: unknown bug must still leave a visible, retryable failure
        logger.exception("Unexpected error sending message %s", message_id)
        _record_failure(message, ProviderError("internal_error", repr(exc), retryable=True))
    else:
        now = timezone.now()
        Message.objects.filter(pk=message_id, status=S.SENDING).update(
            status=S.SENT,
            provider_message_id=result.provider_message_id,
            sent_at=now,
            next_attempt_at=None,
            failure_code="",
            failure_message="",
            failure_detail="",
            retryable=False,
            updated_at=now,
        )
    return Message.objects.filter(pk=message_id).first()


def _record_failure(message, exc):
    now = timezone.now()
    fields = dict(
        failure_code=exc.code,
        failure_message=exc.friendly,
        failure_detail=exc.detail[:1000],
        retryable=exc.retryable,
        updated_at=now,
    )
    if exc.retryable and message.attempts < settings.MESSAGE_MAX_ATTEMPTS:
        backoff = settings.MESSAGE_RETRY_BACKOFF
        delay = exc.retry_after or backoff[min(message.attempts - 1, len(backoff) - 1)]
        Message.objects.filter(pk=message.pk).update(
            status=S.QUEUED, next_attempt_at=now + timedelta(seconds=delay), **fields
        )
    else:
        Message.objects.filter(pk=message.pk).update(status=S.FAILED, next_attempt_at=None, **fields)


def recover_stuck():
    cutoff = timezone.now() - timedelta(seconds=settings.MESSAGE_STUCK_AFTER_SECONDS)
    return Message.objects.filter(status=S.SENDING, updated_at__lt=cutoff).update(
        status=S.QUEUED, next_attempt_at=timezone.now()
    )


def process_due(limit=50):
    """One worker tick. Each message is isolated; returns how many were attempted."""
    recover_stuck()
    ids = list(
        Message.objects.filter(status__in=[S.QUEUED, S.SCHEDULED], next_attempt_at__lte=timezone.now())
        .order_by("next_attempt_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    for message_id in ids:
        dispatch_message(message_id)
    return len(ids)


# --- Manual retry --------------------------------------------------------------
def retry_message(message):
    if message.status != S.FAILED:
        raise NotRetryable("Only failed messages can be retried.")
    if not message.retryable:
        raise NotRetryable(
            "This message can't be retried because the problem is permanent. "
            "Fix the candidate's contact details and send a new message."
        )
    now = timezone.now()
    updated = Message.objects.filter(pk=message.pk, status=S.FAILED, retryable=True).update(
        status=S.QUEUED,
        attempts=0,
        next_attempt_at=now,
        idempotency_key=uuid.uuid4(),  # a deliberate resend, so a fresh key
        provider_message_id=None,  # late callbacks for the old attempt are ignored
        sent_at=None,
        failure_code="",
        failure_message="",
        failure_detail="",
        updated_at=now,
    )
    if not updated:
        raise NotRetryable("This message was already retried.")


# --- Provider callbacks --------------------------------------------------------
def apply_provider_event(payload):
    """Apply a webhook. Returns "applied", "stale" or "duplicate". Safe to call repeatedly."""
    try:
        event_id = str(payload["event_id"])
        provider_message_id = str(payload["message_id"])
        status = str(payload["status"]).lower()
        occurred_at = _parse_time(payload.get("occurred_at"))
    except (KeyError, TypeError, ValueError):
        raise InvalidEvent("Payload must include event_id, message_id, status and occurred_at.")
    if status not in PROVIDER_EVENT_STATUSES:
        raise InvalidEvent(f"Unsupported status '{status}'.")

    with transaction.atomic():
        message = Message.objects.select_for_update().filter(provider_message_id=provider_message_id).first()
        if message is None:
            raise UnknownMessage(provider_message_id)
        try:
            with transaction.atomic():
                event = StatusEvent.objects.create(
                    message=message, event_id=event_id, status=status, occurred_at=occurred_at, payload=payload
                )
        except IntegrityError:
            return "duplicate"

        applied = _advance(message, status, occurred_at, payload)
        if applied:
            event.applied = True
            event.save(update_fields=["applied"])
    return "applied" if applied else "stale"


def _parse_time(raw):
    from django.utils.dateparse import parse_datetime

    parsed = parse_datetime(str(raw)) if raw else None
    if parsed is None:
        raise ValueError("bad timestamp")
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


def _advance(message, status, occurred_at, payload):
    current = message.status
    updates = {"updated_at": timezone.now()}

    if status == "failed":
        if current in (S.DELIVERED, S.READ):
            return False  # a later state already won
        code = payload.get("error_code") or "delivery_failed"
        updates.update(
            status=S.FAILED,
            failure_code=code,
            failure_message=friendly_message(code),
            failure_detail=str(payload.get("error_message", ""))[:1000],
            retryable=code not in PERMANENT_CODES,
            next_attempt_at=None,
        )
    else:
        new = S(status)
        if current == S.FAILED and new == S.SENT:
            return False  # stale "sent" must not undo a failure
        if RANK[new] <= RANK.get(S(current), 0):
            _stamp(message, new, occurred_at)  # still record the timestamp if we missed it
            return False
        updates.update(status=new, failure_code="", failure_message="", failure_detail="", retryable=False)

    Message.objects.filter(pk=message.pk).update(**updates)
    if status != "failed":
        _stamp(message, S(status), occurred_at)
    return True


def _stamp(message, status, when):
    column = {S.SENT: "sent_at", S.DELIVERED: "delivered_at", S.READ: "read_at"}.get(status)
    if column and getattr(message, column) is None:
        Message.objects.filter(pk=message.pk, **{f"{column}__isnull": True}).update(**{column: when})


# --- Stats -----------------------------------------------------------------------
def delivery_stats():
    qs = Message.objects
    return {
        "sent": qs.filter(status__in=Message.ACCEPTED).count(),
        "delivered": qs.filter(status__in=[S.DELIVERED, S.READ]).count(),
        "read": qs.filter(status=S.READ).count(),
        "failed": qs.filter(status=S.FAILED).count(),
        "pending": qs.filter(status__in=Message.PENDING).count(),
    }
