import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.db import connection

from .models import Message, ServiceState
from .scenarios import lifecycle_for

logger = logging.getLogger(__name__)


def sign(body: bytes) -> str:
    return hmac.new(settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def deliver(event: dict) -> bool:
    """POST one signed event. Retries a few times, like real providers do."""
    body = json.dumps(event).encode()
    headers = {"Content-Type": "application/json", "X-Signature": sign(body)}
    for attempt in range(settings.WEBHOOK_MAX_ATTEMPTS):
        try:
            resp = requests.post(settings.WEBHOOK_URL, data=body, headers=headers, timeout=5)
            if resp.status_code < 300:
                return True
            logger.warning("Webhook %s got HTTP %s", event["event_id"], resp.status_code)
        except requests.RequestException as exc:
            logger.warning("Webhook %s failed: %s", event["event_id"], exc)
        if attempt < settings.WEBHOOK_MAX_ATTEMPTS - 1:
            time.sleep(settings.WEBHOOK_RETRY_DELAY)
    return False


def run_lifecycle(message_id: str) -> None:
    state = ServiceState.load()
    msg = Message.objects.get(pk=message_id)
    events = lifecycle_for(msg.scenario, out_of_order=state.out_of_order)
    for status, error_code in events:
        time.sleep(settings.EVENT_DELAY_SECONDS)
        Message.objects.filter(pk=message_id).update(status=status, error_code=error_code)
        event = {
            "event_id": "evt_" + uuid.uuid4().hex[:20],
            "message_id": message_id,
            "status": status,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        if error_code:
            event["error_code"] = error_code
            event["error_message"] = "The recipient's device could not be reached."
        deliver(event)
        if state.duplicate_webhooks:
            deliver(event)  # same event_id: the receiver must be idempotent


def _thread_main(message_id: str) -> None:
    try:
        run_lifecycle(message_id)
    except Exception:  # pragma: no cover - background thread must never crash the server
        logger.exception("Lifecycle failed for %s", message_id)
    finally:
        connection.close()


def start_lifecycle(message_id: str) -> None:
    if settings.WEBHOOK_THREADED:
        threading.Thread(target=_thread_main, args=(message_id,), daemon=True).start()
    else:
        run_lifecycle(message_id)
