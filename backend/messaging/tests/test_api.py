from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from candidates.models import Candidate
from messaging import services
from messaging.models import Message, MessageTemplate
from messaging.providers import ProviderError

from .helpers import FakeProvider, make_candidate, patched_provider

S = Message.Status


class CandidateApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def create(self, **kw):
        data = {"name": "Rahul Sharma", "phone": "+91 98765 43210", "email": "Rahul@Example.com"}
        data.update(kw)
        return self.api.post("/api/candidates/", data, format="json")

    def test_create_normalises_phone_and_email(self):
        resp = self.create()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["phone"], "+919876543210")
        self.assertEqual(resp.json()["email"], "rahul@example.com")

    def test_validation_errors_use_the_error_envelope(self):
        resp = self.create(name="", phone="9876543210", email="nope")
        self.assertEqual(resp.status_code, 400)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "validation_error")
        self.assertEqual(set(err["fields"]), {"name", "phone", "email"})
        self.assertIn("country code", err["fields"]["phone"])

    def test_duplicate_phone_and_email_rejected(self):
        self.create()
        resp = self.create(name="Someone Else", phone="+919876543210", email="RAHUL@example.com")
        fields = resp.json()["error"]["fields"]
        self.assertIn("phone", fields)
        self.assertIn("email", fields)

    def test_editing_a_candidate_can_keep_own_phone(self):
        cid = self.create().json()["id"]
        resp = self.api.patch(f"/api/candidates/{cid}/", {"name": "Rahul S"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Rahul S")

    def test_search_by_name_email_and_phone_digits(self):
        make_candidate(1, name="Rahul Sharma", phone="+919876543210", email="rahul@acme.com")
        make_candidate(2, name="Priya Shah", phone="+919000000002", email="priya@corp.io")
        find = lambda q: [c["name"] for c in self.api.get("/api/candidates/", {"search": q}).json()["results"]]
        self.assertEqual(find("rahul"), ["Rahul Sharma"])
        self.assertEqual(find("corp.io"), ["Priya Shah"])
        self.assertEqual(find("+91 98765"), ["Rahul Sharma"])
        self.assertEqual(find("zzz"), [])
        self.assertEqual(len(find("")), 2)

    def test_empty_list_and_missing_detail(self):
        self.assertEqual(self.api.get("/api/candidates/").json()["count"], 0)
        resp = self.api.get("/api/candidates/999/")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("message", resp.json()["error"])


class SendApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.rahul = make_candidate(1, name="Rahul Sharma")

    def test_send_creates_queued_message(self):
        resp = self.api.post("/api/messages/", {"candidate_id": self.rahul.id, "body": "Hello {{first_name}}"}, format="json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual((data["status"], data["body"]), ("queued", "Hello Rahul"))
        self.assertNotIn("failure_detail", data)

    def test_send_validation(self):
        post = lambda payload: self.api.post("/api/messages/", payload, format="json")
        self.assertIn("candidate_id", post({"body": "x"}).json()["error"]["fields"])
        self.assertIn("candidate_id", post({"candidate_id": 999, "body": "x"}).json()["error"]["fields"])
        self.assertIn("body", post({"candidate_id": self.rahul.id}).json()["error"]["fields"])
        self.assertIn("body", post({"candidate_id": self.rahul.id, "body": "   "}).json()["error"]["fields"])
        self.assertIn("body", post({"candidate_id": self.rahul.id, "body": "Hi {{salary}}"}).json()["error"]["fields"])
        self.assertIn("provider", post({"candidate_id": self.rahul.id, "body": "x", "provider": "fax"}).json()["error"]["fields"])

    def test_scheduled_send_requires_future_time(self):
        past = (timezone.now() - timedelta(minutes=5)).isoformat()
        resp = self.api.post("/api/messages/", {"candidate_id": self.rahul.id, "body": "x", "scheduled_for": past}, format="json")
        self.assertEqual(resp.status_code, 400)
        future = (timezone.now() + timedelta(days=1)).isoformat()
        resp = self.api.post("/api/messages/", {"candidate_id": self.rahul.id, "body": "x", "scheduled_for": future}, format="json")
        self.assertEqual((resp.status_code, resp.json()["status"]), (201, "scheduled"))

    def test_send_using_a_template(self):
        tpl = MessageTemplate.objects.create(name="Interview", body="Hi {{name}}, interview tomorrow.")
        resp = self.api.post("/api/messages/", {"candidate_id": self.rahul.id, "template_id": tpl.id}, format="json")
        self.assertEqual(resp.json()["body"], "Hi Rahul Sharma, interview tomorrow.")

    @override_settings(MESSAGING_EAGER_DISPATCH=True)
    def test_eager_dispatch_sends_inline(self):
        with patched_provider(FakeProvider()):
            resp = self.api.post("/api/messages/", {"candidate_id": self.rahul.id, "body": "x"}, format="json")
        self.assertEqual(resp.json()["status"], "sent")


class BulkApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.people = [make_candidate(i) for i in range(1, 4)]

    def bulk(self, **kw):
        payload = {"candidate_ids": [c.id for c in self.people], "body": "Interview tomorrow"}
        payload.update(kw)
        return self.api.post("/api/messages/bulk/", payload, format="json")

    def test_bulk_creates_independent_messages(self):
        resp = self.bulk()
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["summary"]["total"], 3)
        self.assertEqual(data["summary"]["pending"], 3)
        self.assertEqual(len(data["messages"]), 3)
        self.assertEqual(Message.objects.filter(batch_id=data["id"]).count(), 3)

    def test_duplicate_ids_are_collapsed(self):
        resp = self.bulk(candidate_ids=[self.people[0].id] * 3)
        self.assertEqual(resp.json()["summary"]["total"], 1)

    def test_bulk_validation(self):
        self.assertIn("candidate_ids", self.bulk(candidate_ids=[]).json()["error"]["fields"])
        self.assertIn("candidate_ids", self.bulk(candidate_ids=[999]).json()["error"]["fields"])
        self.assertIn("body", self.bulk(body="").json()["error"]["fields"])

    @override_settings(MAX_BULK_RECIPIENTS=2)
    def test_bulk_limit(self):
        self.assertEqual(self.bulk().status_code, 400)

    def test_partial_failure_is_visible_per_candidate(self):
        batch_id = self.bulk().json()["id"]
        fake = FakeProvider({"+919876500002": ProviderError("invalid_recipient")})
        with patched_provider(fake):
            services.process_due()
        data = self.api.get(f"/api/batches/{batch_id}/").json()
        self.assertEqual(data["summary"]["succeeded"], 2)
        self.assertEqual(data["summary"]["failed"], 1)
        failed = [m for m in data["messages"] if m["status"] == "failed"][0]
        self.assertEqual(failed["candidate"]["name"], "Candidate 2")
        self.assertFalse(failed["retryable"])
        self.assertTrue(failed["failure_message"])


class HistoryAndRetryApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.rahul = make_candidate(1)

    def test_history_newest_first_and_empty_state(self):
        self.assertEqual(self.api.get(f"/api/candidates/{self.rahul.id}/messages/").json()["count"], 0)
        services.create_messages([self.rahul], "first", "whatsapp")
        services.create_messages([self.rahul], "second", "whatsapp")
        results = self.api.get(f"/api/candidates/{self.rahul.id}/messages/").json()["results"]
        self.assertEqual([m["body"] for m in results], ["second", "first"])

    def test_history_for_unknown_candidate_is_404(self):
        self.assertEqual(self.api.get("/api/candidates/999/messages/").status_code, 404)

    def test_history_only_includes_that_candidates_messages(self):
        other = make_candidate(2)
        services.create_messages([other], "not yours", "whatsapp")
        self.assertEqual(self.api.get(f"/api/candidates/{self.rahul.id}/messages/").json()["count"], 0)

    def test_message_detail_includes_event_timeline(self):
        _, (msg,) = services.create_messages([self.rahul], "x", "whatsapp")
        data = self.api.get(f"/api/messages/{msg.id}/").json()
        self.assertEqual(data["events"], [])

    def test_retry_endpoint_for_retryable_failure(self):
        _, (msg,) = services.create_messages([self.rahul], "x", "whatsapp")
        Message.objects.filter(pk=msg.pk).update(status=S.FAILED, retryable=True, failure_message="down")
        resp = self.api.post(f"/api/messages/{msg.id}/retry/")
        self.assertEqual((resp.status_code, resp.json()["status"]), (200, "queued"))

    def test_retry_endpoint_conflicts_for_permanent_failure(self):
        _, (msg,) = services.create_messages([self.rahul], "x", "whatsapp")
        Message.objects.filter(pk=msg.pk).update(status=S.FAILED, retryable=False)
        resp = self.api.post(f"/api/messages/{msg.id}/retry/")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("permanent", resp.json()["error"]["message"])

    def test_retry_endpoint_conflicts_for_non_failed(self):
        _, (msg,) = services.create_messages([self.rahul], "x", "whatsapp")
        self.assertEqual(self.api.post(f"/api/messages/{msg.id}/retry/").status_code, 409)

    def test_message_list_filters_by_status(self):
        services.create_messages([self.rahul], "a", "whatsapp")
        _, (b,) = services.create_messages([self.rahul], "b", "whatsapp")
        Message.objects.filter(pk=b.pk).update(status=S.FAILED)
        data = self.api.get("/api/messages/", {"status": "failed"}).json()
        self.assertEqual([m["body"] for m in data["results"]], ["b"])


class TemplateAndHealthApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_template_crud_and_placeholder_validation(self):
        ok = self.api.post("/api/templates/", {"name": "Reminder", "body": "Hi {{first_name}}"}, format="json")
        self.assertEqual(ok.status_code, 201)
        bad = self.api.post("/api/templates/", {"name": "Bad", "body": "Hi {{nickname}}"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("nickname", bad.json()["error"]["fields"]["body"])
        dup = self.api.post("/api/templates/", {"name": "Reminder", "body": "x"}, format="json")
        self.assertEqual(dup.status_code, 400)
        self.assertEqual(len(self.api.get("/api/templates/").json()["results"]), 1)

    def test_health_combines_provider_status_and_our_stats(self):
        c = make_candidate(1)
        for status in (S.SENT, S.DELIVERED, S.READ, S.FAILED, S.QUEUED):
            services.create_messages([c], "x", "whatsapp")
        for msg, status in zip(Message.objects.order_by("id"), (S.SENT, S.DELIVERED, S.READ, S.FAILED, S.QUEUED)):
            Message.objects.filter(pk=msg.pk).update(status=status)
        health = {"status": "operational", "mode": "normal"}
        with mock.patch("messaging.providers.DummyProvider.health", return_value=health):
            data = self.api.get("/api/provider-health/").json()
        self.assertEqual(data["status"], "operational")
        self.assertEqual(data["stats"], {"sent": 3, "delivered": 2, "read": 1, "failed": 1, "pending": 1})

    def test_health_down_when_provider_unreachable(self):
        with mock.patch("messaging.providers.DummyProvider.health", return_value={"status": "down", "mode": None}):
            self.assertEqual(self.api.get("/api/provider-health/").json()["status"], "down")

    def test_health_degraded_on_mixed_states(self):
        states = iter([{"status": "operational"}, {"status": "degraded"}])
        with mock.patch("messaging.providers.DummyProvider.health", side_effect=lambda: next(states)):
            self.assertEqual(self.api.get("/api/provider-health/").json()["status"], "degraded")
