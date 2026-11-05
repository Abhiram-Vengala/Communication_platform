from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from candidates.models import Candidate
from messaging.models import Message
from messaging.providers import friendly_message

S = Message.Status


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


# Created oldest first, so the newest-first table reads top to bottom in this order reversed.
PEOPLE = [
    ("Amarjeet Kumar", "+919012345678", "S1T2U3", []),
    ("Ira Akbar", "+919456789012", "P7Q8R9", []),
    ("Aniket Sawant", "+919876512345", "M4N5O6", [("2026-10-24 10:15", S.SENT, "Hi Aniket, thanks for applying. Could we schedule a quick intro call this week?")]),
    ("Ajit Srivastava", "+919234567890", "J1K2L3", [("2026-10-21 09:30", S.READ, "Hi Ajit, your technical round is confirmed for Friday at 11:00 AM.")]),
    ("Aditya Kumar", "+919988766554", "G7H8I9", [("2026-10-18 16:05", S.READ, "Hi Aditya, please share your updated resume before our call.")]),
    ("Urvashi Soni", "+919123456789", "D4E5F6", [("2026-10-15 11:20", S.FAILED, "Hi Urvashi, we'd like to move you to the final interview round.")]),
    (
        "Krishna Khandelwal", "+919876543210", "A1B2C3",
        [
            ("2026-10-12 10:47", S.READ, "Hello Krishna, your interview is scheduled for tomorrow at 11:00 AM."),
            ("2026-09-19 22:00", S.READ, "Thanks for your time today. We will share feedback within two days."),
            ("2026-09-12 22:00", S.READ, "Welcome to our hiring process. Please confirm your availability this week."),
        ],
    ),
]  # fmt: skip


class Command(BaseCommand):
    help = "Create demo candidates and message history (matches the Figma data)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete all candidates first.")

    def handle(self, *args, **options):
        if options["reset"]:
            Candidate.objects.all().delete()
        elif Candidate.objects.exists():
            self.stdout.write("Candidates already exist. Use --reset to replace them.")
            return
        n = 0
        for name, phone, code, messages in PEOPLE:
            email = name.lower().replace(" ", ".") + "@gmail.com"
            candidate = Candidate.objects.create(name=name, phone=phone, email=email, code=code)
            for when, status, body in messages:
                n += 1
                msg = Message.objects.create(
                    candidate=candidate, body=body, provider="whatsapp", status=status,
                    provider_message_id=f"seed_{n}", sent_at=at(when),
                    delivered_at=at(when) if status in (S.DELIVERED, S.READ) else None,
                    read_at=at(when) if status == S.READ else None,
                )  # fmt: skip
                fields = {"created_at": at(when), "updated_at": at(when)}
                if status == S.FAILED:
                    fields.update(
                        failure_code="invalid_recipient",
                        failure_message=friendly_message("invalid_recipient"),
                        retryable=False, provider_message_id=None, sent_at=None,
                    )  # fmt: skip
                Message.objects.filter(pk=msg.pk).update(**fields)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(PEOPLE)} candidates and {n} messages."))
