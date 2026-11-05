import re

PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
ALLOWED_PLACEHOLDERS = ("name", "first_name", "email", "phone")


def unknown_placeholders(body: str):
    return sorted({p for p in PLACEHOLDER_RE.findall(body) if p not in ALLOWED_PLACEHOLDERS})


def check_placeholders(body: str) -> None:
    unknown = unknown_placeholders(body)
    if unknown:
        listed = ", ".join("{{%s}}" % p for p in unknown)
        allowed = ", ".join("{{%s}}" % p for p in ALLOWED_PLACEHOLDERS)
        raise ValueError(f"Unknown placeholder(s): {listed}. You can use {allowed}.")


def render(body: str, candidate) -> str:
    values = {
        "name": candidate.name,
        "first_name": candidate.name.split()[0],
        "email": candidate.email,
        "phone": candidate.phone,
    }
    return PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), body)
