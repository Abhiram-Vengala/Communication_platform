from django.test import TestCase

from messaging import services
from messaging.models import Message, StatusEvent

from .helpers import event, make_candidate, signed_post

S = Message.Status


class WebhookTests(TestCase):
    def setUp(self):
        _, (self.msg,) = services.create_messages([make_candidate(1)], "Hi", "whatsapp")
        Message.objects.filter(pk=self.msg.pk).update(status=S.SENT, provider_message_id="pm_abc")
        self.msg.refresh_from_db()

    def status(self):
        self.msg.refresh_from_db()
        return self.msg.status

    def test_rejects_bad_signature(self):
        resp = signed_post(self.client, event(self.msg, "delivered", "e1"), secret="wrong")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(StatusEvent.objects.count(), 0)

    def test_rejects_malformed_payloads(self):
        self.assertEqual(signed_post(self.client, None, raw="not json").status_code, 400)
        self.assertEqual(signed_post(self.client, {"event_id": "x"}).status_code, 400)
        bad = event(self.msg, "exploded", "e2")
        self.assertEqual(signed_post(self.client, bad).status_code, 400)
        bad = event(self.msg, "read", "e3", at="yesterday-ish")
        self.assertEqual(signed_post(self.client, bad).status_code, 400)

    def test_unknown_message_returns_404_so_provider_retries(self):
        payload = event(self.msg, "delivered", "e4")
        payload["message_id"] = "pm_nope"
        self.assertEqual(signed_post(self.client, payload).status_code, 404)

    def test_status_moves_forward(self):
        for i, status in enumerate(["delivered", "read"]):
            resp = signed_post(self.client, event(self.msg, status, f"e{i}"))
            self.assertEqual(resp.json(), {"result": "applied"})
        self.assertEqual(self.status(), S.READ)
        self.msg.refresh_from_db()
        self.assertIsNotNone(self.msg.delivered_at)
        self.assertIsNotNone(self.msg.read_at)

    def test_duplicate_event_is_idempotent(self):
        payload = event(self.msg, "delivered", "dup-1")
        first = signed_post(self.client, payload)
        second = signed_post(self.client, payload)
        self.assertEqual((first.status_code, first.json()["result"]), (200, "applied"))
        self.assertEqual((second.status_code, second.json()["result"]), (200, "duplicate"))
        self.assertEqual(StatusEvent.objects.filter(event_id="dup-1").count(), 1)
        self.assertEqual(self.status(), S.DELIVERED)

    def test_late_delivered_never_downgrades_read(self):
        signed_post(self.client, event(self.msg, "read", "e1"))
        resp = signed_post(self.client, event(self.msg, "delivered", "e2"))
        self.assertEqual(resp.json()["result"], "stale")
        self.assertEqual(self.status(), S.READ)
        self.assertFalse(StatusEvent.objects.get(event_id="e2").applied)
        self.msg.refresh_from_db()
        self.assertIsNotNone(self.msg.delivered_at)  # timestamp still back-filled

    def test_out_of_order_sent_after_delivered_is_stale(self):
        signed_post(self.client, event(self.msg, "delivered", "e1"))
        resp = signed_post(self.client, event(self.msg, "sent", "e2"))
        self.assertEqual(resp.json()["result"], "stale")
        self.assertEqual(self.status(), S.DELIVERED)

    def test_delivery_failure_marks_failed_with_friendly_reason(self):
        payload = event(self.msg, "failed", "e1", error_code="delivery_failed", error_message="device off")
        signed_post(self.client, payload)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, S.FAILED)
        self.assertTrue(self.msg.retryable)
        self.assertIn("couldn't be delivered", self.msg.failure_message)
        self.assertNotIn("device off", self.msg.failure_message)

    def test_permanent_failure_code_is_not_retryable(self):
        signed_post(self.client, event(self.msg, "failed", "e1", error_code="invalid_recipient"))
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.retryable)

    def test_failed_after_read_is_ignored(self):
        signed_post(self.client, event(self.msg, "read", "e1"))
        resp = signed_post(self.client, event(self.msg, "failed", "e2", error_code="delivery_failed"))
        self.assertEqual(resp.json()["result"], "stale")
        self.assertEqual(self.status(), S.READ)

    def test_stale_sent_cannot_resurrect_a_failed_message(self):
        signed_post(self.client, event(self.msg, "failed", "e1", error_code="delivery_failed"))
        signed_post(self.client, event(self.msg, "sent", "e2"))
        self.assertEqual(self.status(), S.FAILED)

    def test_delivered_after_failed_recovers_and_clears_error(self):
        signed_post(self.client, event(self.msg, "failed", "e1", error_code="delivery_failed"))
        signed_post(self.client, event(self.msg, "delivered", "e2"))
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, S.DELIVERED)
        self.assertEqual(self.msg.failure_message, "")
