import uuid

from django.db import models

from candidates.models import Candidate


class MessageTemplate(models.Model):
    name = models.CharField(max_length=80, unique=True)
    body = models.TextField(max_length=1600)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class MessageBatch(models.Model):
    """One bulk send. Every recipient still gets its own independent Message."""

    body = models.TextField()
    provider = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled"
        QUEUED = "queued"
        SENDING = "sending"
        SENT = "sent"
        DELIVERED = "delivered"
        READ = "read"
        FAILED = "failed"

    PENDING = (Status.SCHEDULED, Status.QUEUED, Status.SENDING)
    ACCEPTED = (Status.SENT, Status.DELIVERED, Status.READ)

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="messages")
    batch = models.ForeignKey(MessageBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages")
    body = models.TextField()  # already rendered for this candidate
    provider = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)

    # Sent to the provider as Idempotency-Key so a retry after a timeout can't double-send.
    # Regenerated only on a deliberate manual retry.
    idempotency_key = models.UUIDField(default=uuid.uuid4)
    provider_message_id = models.CharField(max_length=64, null=True, blank=True, unique=True)

    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)

    failure_code = models.CharField(max_length=50, blank=True)
    failure_message = models.CharField(max_length=300, blank=True)  # shown to recruiters
    failure_detail = models.TextField(blank=True)  # technical, never exposed by the API
    retryable = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]


class StatusEvent(models.Model):
    """Append-only log of every provider callback. `event_id` makes redelivery harmless."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="events")
    event_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    applied = models.BooleanField(default=False)  # False if stale / out of order
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ["occurred_at", "id"]
