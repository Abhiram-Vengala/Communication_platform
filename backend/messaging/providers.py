"""Provider abstraction.

`get_provider(name)` is the only thing the rest of the app knows about. Adding a real
provider (Twilio, Resend...) means writing another class with `send()` and `health()`
and registering it in `get_provider`.

Everything a provider can do wrong is translated into one `ProviderError` carrying a
stable `code`, whether it is retryable, and a recruiter-friendly message.
"""
from dataclasses import dataclass

import requests
from django.conf import settings

FRIENDLY_MESSAGES = {
    "invalid_recipient": "The phone number or email looks invalid, so the message couldn't be delivered. "
    "Please check the candidate's contact details.",
    "rate_limited": "The messaging service is receiving too many requests right now.",
    "provider_unavailable": "The messaging service is temporarily unavailable.",
    "provider_error": "The messaging service returned an unexpected response.",
    "provider_auth": "The messaging service isn't set up correctly. Please contact an administrator.",
    "rejected": "The messaging service rejected this message.",
    "delivery_failed": "The message was sent, but it couldn't be delivered to the candidate.",
    "internal_error": "Something went wrong while sending this message.",
}
# Retrying these can never help.
PERMANENT_CODES = {"invalid_recipient", "provider_auth", "rejected"}


def friendly_message(code: str) -> str:
    return FRIENDLY_MESSAGES.get(code, "The message couldn't be sent.")


class ProviderError(Exception):
    def __init__(self, code, detail="", retryable=None, retry_after=None):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail
        self.retryable = (code not in PERMANENT_CODES) if retryable is None else retryable
        self.retry_after = retry_after

    @property
    def friendly(self):
        return friendly_message(self.code)


@dataclass
class ProviderResult:
    provider_message_id: str
    status: str = "accepted"


class DummyProvider:
    """HTTP client for the standalone dummy provider service (see /provider)."""

    def __init__(self, name, channel, base_url):
        self.name = name
        self.channel = channel
        self.base_url = base_url.rstrip("/")

    def _headers(self, **extra):
        return {"Authorization": f"Bearer {settings.PROVIDER_API_KEY}", **extra}

    def send(self, *, to, body, idempotency_key):
        try:
            resp = requests.post(
                f"{self.base_url}/v1/messages",
                json={"to": to, "body": body, "channel": self.channel},
                headers=self._headers(**{"Idempotency-Key": idempotency_key}),
                timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise ProviderError("provider_unavailable", f"timeout: {exc}", retryable=True)
        except requests.RequestException as exc:
            raise ProviderError("provider_unavailable", f"connection error: {exc}", retryable=True)
        return self._parse(resp)

    @staticmethod
    def _error_body(resp):
        try:
            return (resp.json() or {}).get("error") or {}
        except ValueError:
            return {}

    def _parse(self, resp):
        status = resp.status_code
        if 200 <= status < 300:
            try:
                return ProviderResult(resp.json()["id"], resp.json().get("status", "accepted"))
            except (ValueError, KeyError, TypeError):
                raise ProviderError("provider_error", f"bad success body: {resp.text[:200]}", retryable=True)

        err = self._error_body(resp)
        detail = f"HTTP {status}: {err.get('message') or resp.text[:200]}"
        if status == 429:
            retry_after = None
            raw = resp.headers.get("Retry-After", "")
            if raw.isdigit():
                retry_after = min(int(raw), settings.MESSAGE_RETRY_AFTER_CAP)
            raise ProviderError("rate_limited", detail, retryable=True, retry_after=retry_after)
        if status in (401, 403):
            raise ProviderError("provider_auth", detail, retryable=False)
        if status >= 500:
            raise ProviderError("provider_unavailable", detail, retryable=True)
        code = err.get("code")
        raise ProviderError(code if code in FRIENDLY_MESSAGES else "rejected", detail)

    def health(self):
        try:
            resp = requests.get(f"{self.base_url}/v1/health", timeout=2)
            data = resp.json()
            return {"status": data.get("status", "down"), "mode": data.get("mode")}
        except (requests.RequestException, ValueError):
            return {"status": "down", "mode": None}


def get_provider(name):
    config = settings.PROVIDERS.get(name)
    if not config:
        raise ProviderError("provider_error", f"unknown provider '{name}'", retryable=False)
    return DummyProvider(name, config["channel"], config["base_url"])


def recipient_for(provider_name, candidate):
    channel = settings.PROVIDERS[provider_name]["channel"]
    return candidate.email if channel == "email" else candidate.phone
