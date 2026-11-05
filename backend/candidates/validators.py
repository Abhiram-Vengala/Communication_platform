import re

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(raw: str) -> str:
    """Return E.164 (+919876543210) or raise ValueError with a recruiter-friendly message."""
    cleaned = re.sub(r"[\s\-().]", "", raw or "")
    if not cleaned.startswith("+"):
        raise ValueError("Include the country code, for example +91 98765 43210.")
    if not PHONE_RE.match(cleaned):
        raise ValueError("Enter a valid phone number with country code, for example +91 98765 43210.")
    return cleaned
