import hashlib
import hmac
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

from django.conf import settings

from candidates.models import Candidate
from messaging.providers import ProviderError, ProviderResult


def make_candidate(i=1, **kwargs):
    data = dict(name=f"Candidate {i}", phone=f"+9198765{i:05d}", email=f"c{i}@example.com")
    data.update(kwargs)
    return Candidate.objects.create(**data)


class FakeProvider:
    """Stands in for the HTTP provider. `outcomes` maps recipient -> ProviderError | list of outcomes."""

    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.calls = []
        self._counter = 0

    def send(self, *, to, body, idempotency_key):
        self.calls.append({"to": to, "body": body, "key": idempotency_key})
        outcome = self.outcomes.get(to)
        if isinstance(outcome, list):
            outcome = outcome.pop(0) if len(outcome) > 1 else outcome[0]
        if isinstance(outcome, ProviderError):
            raise outcome
        self._counter += 1
        return ProviderResult(provider_message_id=f"pm_{self._counter}_{to[-5:]}")


@contextmanager
def patched_provider(fake):
    with mock.patch("messaging.services.get_provider", return_value=SimpleNamespace(send=fake.send)):
        yield fake


def signed_post(client, payload, secret=None, raw=None):
    body = raw if raw is not None else json.dumps(payload)
    secret = secret or settings.PROVIDER_WEBHOOK_SECRET
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return client.post("/api/webhooks/provider/", data=body, content_type="application/json", HTTP_X_SIGNATURE=sig)


def event(message, status, event_id, at="2026-11-04T10:00:00+00:00", **extra):
    return {"event_id": event_id, "message_id": message.provider_message_id, "status": status, "occurred_at": at, **extra}
