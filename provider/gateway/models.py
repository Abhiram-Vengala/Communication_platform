import uuid

from django.db import models


def new_message_id():
    return "pm_" + uuid.uuid4().hex[:20]


class Message(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=new_message_id, editable=False)
    channel = models.CharField(max_length=20)
    to = models.CharField(max_length=254)
    body = models.TextField()
    status = models.CharField(max_length=20, default="accepted")
    error_code = models.CharField(max_length=50, blank=True)
    scenario = models.CharField(max_length=20, default="ok")
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AttemptCounter(models.Model):
    """Counts attempts per key so the 'flaky' scenario can fail N times then succeed."""

    key = models.CharField(max_length=200, primary_key=True)
    count = models.PositiveIntegerField(default=0)

    @classmethod
    def bump(cls, key):
        obj, _ = cls.objects.get_or_create(key=key)
        obj.count += 1
        obj.save(update_fields=["count"])
        return obj.count


class ServiceState(models.Model):
    """Singleton row controlling the simulated health of the provider."""

    MODES = [("normal", "normal"), ("rate_limit", "rate_limit"), ("outage", "outage")]

    mode = models.CharField(max_length=20, choices=MODES, default="normal")
    duplicate_webhooks = models.BooleanField(default=False)
    out_of_order = models.BooleanField(default=False)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
