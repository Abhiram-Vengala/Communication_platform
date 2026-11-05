from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from messaging import services
from messaging.models import Message
from messaging.providers import ProviderError

from .helpers import FakeProvider, make_candidate, patched_provider

S = Message.Status


def queue(candidates, body="Hi", provider="whatsapp", scheduled_for=None):
    _, messages = services.create_messages(candidates, body, provider, scheduled_for)
    return messages


class SendingTests(TestCase):
    def test_successful_send_records_provider_id_and_sent_status(self):
        (msg,) = queue([make_candidate(1)])
        with patched_provider(FakeProvider()) as fake:
            services.process_due()
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.SENT)
        self.assertTrue(msg.provider_message_id)
        self.assertIsNotNone(msg.sent_at)
        self.assertEqual(msg.attempts, 1)
        self.assertEqual(fake.calls[0]["key"], str(msg.idempotency_key))

    def test_email_provider_sends_to_email_address(self):
        queue([make_candidate(1)], provider="email")
        with patched_provider(FakeProvider()) as fake:
            services.process_due()
        self.assertEqual(fake.calls[0]["to"], "c1@example.com")

    def test_body_is_personalised_per_candidate(self):
        a, b = make_candidate(1, name="Rahul Sharma"), make_candidate(2, name="Priya Shah")
        queue([a, b], body="Hello {{first_name}}, welcome {{ name }}!")
        bodies = set(Message.objects.values_list("body", flat=True))
        self.assertEqual(bodies, {"Hello Rahul, welcome Rahul Sharma!", "Hello Priya, welcome Priya Shah!"})

    def test_permanent_failure_is_final_and_not_retryable(self):
        (msg,) = queue([make_candidate(1)])
        fake = FakeProvider({"+919876500001": ProviderError("invalid_recipient", "HTTP 400")})
        with patched_provider(fake):
            services.process_due()
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.FAILED)
        self.assertFalse(msg.retryable)
        self.assertIn("invalid", msg.failure_message)
        self.assertEqual(msg.attempts, 1)

    def test_temporary_failure_requeues_with_backoff(self):
        (msg,) = queue([make_candidate(1)])
        fake = FakeProvider({"+919876500001": ProviderError("provider_unavailable", "HTTP 503")})
        with patched_provider(fake):
            services.process_due()
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.QUEUED)
        self.assertGreater(msg.next_attempt_at, timezone.now() + timedelta(seconds=3))
        self.assertTrue(msg.retryable)
        self.assertEqual(msg.failure_code, "provider_unavailable")

    def test_not_due_message_is_not_picked_up_until_backoff_passes(self):
        (msg,) = queue([make_candidate(1)])
        fake = FakeProvider({"+919876500001": [ProviderError("provider_unavailable"), None]})
        with patched_provider(fake):
            services.process_due()
            self.assertEqual(services.process_due(), 0)  # still backing off
            Message.objects.filter(pk=msg.pk).update(next_attempt_at=timezone.now())
            self.assertEqual(services.process_due(), 1)
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.SENT)
        self.assertEqual(msg.attempts, 2)
        self.assertEqual(msg.failure_message, "")  # cleared after recovery

    def test_rate_limit_honours_retry_after(self):
        (msg,) = queue([make_candidate(1)])
        fake = FakeProvider({"+919876500001": ProviderError("rate_limited", retry_after=60)})
        with patched_provider(fake):
            services.process_due()
        msg.refresh_from_db()
        delta = (msg.next_attempt_at - timezone.now()).total_seconds()
        self.assertTrue(55 < delta <= 60)

    @override_settings(MESSAGE_MAX_ATTEMPTS=2)
    def test_exhausted_retries_end_failed_but_manually_retryable(self):
        (msg,) = queue([make_candidate(1)])
        fake = FakeProvider({"+919876500001": ProviderError("provider_unavailable")})
        with patched_provider(fake):
            services.process_due()
            Message.objects.filter(pk=msg.pk).update(next_attempt_at=timezone.now())
            services.process_due()
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.FAILED)
        self.assertTrue(msg.retryable)
        self.assertEqual(msg.attempts, 2)

    def test_unexpected_exception_does_not_crash_and_is_recorded(self):
        (msg,) = queue([make_candidate(1)])
        with mock.patch("messaging.services.get_provider", side_effect=RuntimeError("boom")):
            services.process_due()
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.QUEUED)
        self.assertEqual(msg.failure_code, "internal_error")
        self.assertNotIn("boom", msg.failure_message)

    def test_scheduled_message_waits_until_due(self):
        future = timezone.now() + timedelta(hours=1)
        (msg,) = queue([make_candidate(1)], scheduled_for=future)
        self.assertEqual(msg.status, S.SCHEDULED)
        with patched_provider(FakeProvider()) as fake:
            self.assertEqual(services.process_due(), 0)
            Message.objects.filter(pk=msg.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(services.process_due(), 1)
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.SENT)
        self.assertEqual(len(fake.calls), 1)

    def test_message_is_claimed_only_once(self):
        (msg,) = queue([make_candidate(1)])
        with patched_provider(FakeProvider()) as fake:
            services.dispatch_message(msg.pk)
            services.dispatch_message(msg.pk)  # second worker racing: no-op
        self.assertEqual(len(fake.calls), 1)

    def test_stuck_sending_messages_are_recovered(self):
        (msg,) = queue([make_candidate(1)])
        Message.objects.filter(pk=msg.pk).update(
            status=S.SENDING, updated_at=timezone.now() - timedelta(minutes=10)
        )
        with patched_provider(FakeProvider()):
            services.process_due()
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.SENT)


class BulkIsolationTests(TestCase):
    def test_one_failure_does_not_block_the_others(self):
        candidates = [make_candidate(i) for i in range(1, 6)]
        fake = FakeProvider(
            {
                "+919876500002": ProviderError("invalid_recipient"),
                "+919876500004": ProviderError("provider_unavailable"),
            }
        )
        queue(candidates)
        with patched_provider(fake):
            services.process_due()
        by_candidate = {m.candidate.name: m for m in Message.objects.select_related("candidate")}
        self.assertEqual(by_candidate["Candidate 1"].status, S.SENT)
        self.assertEqual(by_candidate["Candidate 2"].status, S.FAILED)
        self.assertEqual(by_candidate["Candidate 3"].status, S.SENT)
        self.assertEqual(by_candidate["Candidate 4"].status, S.QUEUED)  # will retry
        self.assertEqual(by_candidate["Candidate 5"].status, S.SENT)
        self.assertEqual(len(fake.calls), 5)


class ManualRetryTests(TestCase):
    def failed(self, error):
        (msg,) = queue([make_candidate(1)])
        with patched_provider(FakeProvider({"+919876500001": error})):
            services.process_due()
        msg.refresh_from_db()
        return msg

    @override_settings(MESSAGE_MAX_ATTEMPTS=1)
    def test_retry_resets_and_uses_a_new_idempotency_key(self):
        msg = self.failed(ProviderError("provider_unavailable"))
        old_key = msg.idempotency_key
        self.assertEqual(msg.status, S.FAILED)
        services.retry_message(msg)
        msg.refresh_from_db()
        self.assertEqual((msg.status, msg.attempts, msg.failure_message), (S.QUEUED, 0, ""))
        self.assertNotEqual(msg.idempotency_key, old_key)
        with patched_provider(FakeProvider()):
            services.process_due()
        msg.refresh_from_db()
        self.assertEqual(msg.status, S.SENT)

    def test_permanent_failure_cannot_be_retried(self):
        msg = self.failed(ProviderError("invalid_recipient"))
        with self.assertRaisesMessage(services.NotRetryable, "permanent"):
            services.retry_message(msg)

    def test_only_failed_messages_can_be_retried(self):
        (msg,) = queue([make_candidate(1)])
        with self.assertRaises(services.NotRetryable):
            services.retry_message(msg)
