import hashlib
import hmac
import json
from unittest import mock

from django.test import TestCase, override_settings

from .models import ServiceState
from .scenarios import scenario_for

AUTH = {"HTTP_AUTHORIZATION": "Bearer dev-provider-key"}
OK_PHONE = "+919876512345"


def post(client, payload, key=None, **extra):
    headers = dict(AUTH, **extra)
    if key:
        headers["HTTP_IDEMPOTENCY_KEY"] = key
    return client.post("/v1/messages", data=json.dumps(payload), content_type="application/json", **headers)


@override_settings(WEBHOOK_THREADED=False, EVENT_DELAY_SECONDS=0, WEBHOOK_RETRY_DELAY=0)
class SendTests(TestCase):
    def setUp(self):
        patcher = mock.patch("gateway.webhooks.requests.post")
        self.webhook = patcher.start()
        self.webhook.return_value.status_code = 200
        self.addCleanup(patcher.stop)

    def events(self):
        return [json.loads(c.kwargs["data"]) for c in self.webhook.call_args_list]

    def test_requires_api_key(self):
        resp = self.client.post("/v1/messages", data="{}", content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_accepts_message_and_emits_full_lifecycle(self):
        resp = post(self.client, {"to": OK_PHONE, "body": "hi"})
        self.assertEqual(resp.status_code, 202)
        msg_id = resp.json()["id"]
        self.assertEqual([e["status"] for e in self.events()], ["sent", "delivered", "read"])
        self.assertTrue(all(e["message_id"] == msg_id for e in self.events()))
        self.assertEqual(self.client.get(f"/v1/messages/{msg_id}", **AUTH).json()["status"], "read")

    def test_webhooks_are_signed(self):
        post(self.client, {"to": OK_PHONE, "body": "hi"})
        call = self.webhook.call_args_list[0].kwargs
        expected = hmac.new(b"dev-webhook-secret", call["data"], hashlib.sha256).hexdigest()
        self.assertEqual(call["headers"]["X-Signature"], expected)

    def test_invalid_recipient_format(self):
        resp = post(self.client, {"to": "12345", "body": "hi"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "invalid_recipient")

    def test_invalid_scenario_number(self):
        resp = post(self.client, {"to": "+919876500001", "body": "hi"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.webhook.call_count, 0)

    def test_rate_limited_scenario_sets_retry_after(self):
        resp = post(self.client, {"to": "+919876500002", "body": "hi"})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp["Retry-After"], "3")

    def test_flaky_fails_twice_then_succeeds_with_same_key(self):
        payload = {"to": "+919876500003", "body": "hi"}
        codes = [post(self.client, payload, key="k1").status_code for _ in range(3)]
        self.assertEqual(codes, [503, 503, 202])

    def test_undelivered_reports_failure_event(self):
        post(self.client, {"to": "+919876500004", "body": "hi"})
        last = self.events()[-1]
        self.assertEqual(last["status"], "failed")
        self.assertEqual(last["error_code"], "delivery_failed")

    def test_unread_stops_at_delivered(self):
        post(self.client, {"to": "+919876500005", "body": "hi"})
        self.assertEqual([e["status"] for e in self.events()], ["sent", "delivered"])

    def test_idempotency_key_replays_same_message(self):
        first = post(self.client, {"to": OK_PHONE, "body": "hi"}, key="abc")
        calls = self.webhook.call_count
        second = post(self.client, {"to": OK_PHONE, "body": "hi"}, key="abc")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["id"], first.json()["id"])
        self.assertEqual(second["Idempotent-Replay"], "true")
        self.assertEqual(self.webhook.call_count, calls)

    def test_email_channel_uses_tags(self):
        self.assertEqual(scenario_for("rahul+invalid@example.com"), "invalid")
        self.assertEqual(scenario_for("rahul@example.com"), "ok")
        resp = post(self.client, {"to": "rahul+invalid@example.com", "body": "hi", "channel": "email"})
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_and_out_of_order_modes(self):
        self.client.post(
            "/v1/admin/state",
            data=json.dumps({"duplicate_webhooks": True, "out_of_order": True}),
            content_type="application/json",
            **AUTH,
        )
        post(self.client, {"to": OK_PHONE, "body": "hi"})
        events = self.events()
        self.assertEqual(len(events), 6)
        self.assertEqual(events[0]["event_id"], events[1]["event_id"])
        self.assertEqual([e["status"] for e in events[::2]], ["delivered", "sent", "read"])

    def test_webhook_delivery_is_retried_on_failure(self):
        self.webhook.return_value.status_code = 500
        post(self.client, {"to": "+919876500005", "body": "hi"})
        # 2 events x 3 attempts each
        self.assertEqual(self.webhook.call_count, 6)


class ServiceStateTests(TestCase):
    def set_mode(self, mode):
        return self.client.post(
            "/v1/admin/state", data=json.dumps({"mode": mode}), content_type="application/json", **AUTH
        )

    def test_outage_returns_503(self):
        self.set_mode("outage")
        self.assertEqual(post(self.client, {"to": OK_PHONE, "body": "hi"}).status_code, 503)
        self.assertEqual(self.client.get("/v1/health").json()["status"], "down")

    def test_rate_limit_mode_returns_429_and_degraded(self):
        self.set_mode("rate_limit")
        self.assertEqual(post(self.client, {"to": OK_PHONE, "body": "hi"}).status_code, 429)
        self.assertEqual(self.client.get("/v1/health").json()["status"], "degraded")

    def test_invalid_mode_rejected(self):
        self.assertEqual(self.set_mode("chaos").status_code, 400)
        self.assertEqual(ServiceState.load().mode, "normal")

    def test_health_operational_by_default(self):
        self.assertEqual(self.client.get("/v1/health").json()["status"], "operational")
