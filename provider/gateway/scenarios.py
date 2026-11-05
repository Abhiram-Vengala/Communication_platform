"""Magic recipients: lets a reviewer trigger each behaviour on demand.

Phone numbers: last four digits. Emails: the +tag in the local part
(e.g. rahul+invalid@example.com).

    0001 / +invalid      -> 400 invalid recipient (permanent)
    0002 / +ratelimit    -> 429 rate limited (retryable)
    0003 / +flaky        -> 503 for the first two attempts, then succeeds
    0004 / +undelivered  -> accepted, then a 'failed' delivery event
    0005 / +unread       -> accepted, sent, delivered, never read
    anything else        -> sent, delivered, read
"""
import re

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SUFFIX = {"0001": "invalid", "0002": "ratelimit", "0003": "flaky", "0004": "undelivered", "0005": "unread"}
TAGS = {"invalid", "ratelimit", "flaky", "undelivered", "unread"}

FLAKY_FAILURES = 2


def is_valid_recipient(channel, to):
    if channel == "email":
        return bool(EMAIL_RE.match(to))
    return bool(PHONE_RE.match(to))


def scenario_for(to):
    if "@" in to:
        tag = to.split("@")[0].partition("+")[2].lower()
        return tag if tag in TAGS else "ok"
    digits = re.sub(r"\D", "", to)
    return SUFFIX.get(digits[-4:], "ok")


def lifecycle_for(scenario, out_of_order=False):
    """Ordered (status, error_code) events the provider will report via webhook."""
    if scenario == "undelivered":
        return [("sent", ""), ("failed", "delivery_failed")]
    events = [("sent", ""), ("delivered", "")]
    if scenario != "unread":
        events.append(("read", ""))
    if out_of_order:
        events[0], events[1] = events[1], events[0]
    return events
