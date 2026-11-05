import re
from datetime import datetime, timezone

from django.test import TestCase
from rest_framework.test import APIClient

from candidates.models import Candidate
from messaging import services
from messaging.models import Message

from .helpers import FakeProvider, make_candidate, patched_provider

S = Message.Status


def message_at(candidate, status, when, body="x"):
    msg = Message.objects.create(candidate=candidate, body=body, provider="whatsapp", status=status)
    Message.objects.filter(pk=msg.pk).update(created_at=datetime.fromisoformat(when).replace(tzinfo=timezone.utc))
    return msg


class CandidateCodeTests(TestCase):
    def test_code_is_generated_and_looks_like_a_short_id(self):
        c = make_candidate(1)
        self.assertRegex(c.code, r"^([A-Z]\d){3}$")

    def test_codes_are_unique_and_not_editable_via_api(self):
        api = APIClient()
        a = api.post("/api/candidates/", {"name": "Aa Bb", "phone": "+919000000001", "email": "a@x.com"}, format="json").json()
        b = api.post("/api/candidates/", {"name": "Cc Dd", "phone": "+919000000002", "email": "b@x.com"}, format="json").json()
        self.assertNotEqual(a["code"], b["code"])
        resp = api.patch(f"/api/candidates/{a['id']}/", {"code": "ZZZZZZ"}, format="json")
        self.assertEqual(resp.json()["code"], a["code"])


class CandidateListTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.a = make_candidate(1, name="Alpha One")
        self.b = make_candidate(2, name="Bravo Two")
        self.c = make_candidate(3, name="Charlie Three")
        message_at(self.a, S.READ, "2026-10-10T10:00:00")
        message_at(self.a, S.SENT, "2026-10-25T09:00:00")  # latest for Alpha
        message_at(self.b, S.FAILED, "2026-10-15T12:00:00")

    def names(self, **params):
        return [c["name"] for c in self.api.get("/api/candidates/", params).json()["results"]]

    def test_default_order_is_newest_first(self):
        self.assertEqual(self.names(), ["Charlie Three", "Bravo Two", "Alpha One"])

    def test_exposes_latest_message_date_and_status(self):
        rows = {c["name"]: c for c in self.api.get("/api/candidates/").json()["results"]}
        self.assertEqual(rows["Alpha One"]["last_message_status"], "sent")
        self.assertEqual(rows["Alpha One"]["last_message_at"], "2026-10-25T09:00:00Z")
        self.assertIsNone(rows["Charlie Three"]["last_message_status"])
        self.assertIsNone(rows["Charlie Three"]["last_message_at"])

    def test_filter_by_status_including_never_messaged(self):
        self.assertEqual(self.names(status="failed"), ["Bravo Two"])
        self.assertEqual(self.names(status="none"), ["Charlie Three"])
        self.assertEqual(sorted(self.names(status="sent,none")), ["Alpha One", "Charlie Three"])
        self.assertEqual(self.api.get("/api/candidates/", {"status": "bogus"}).status_code, 400)

    def test_column_filters(self):
        self.assertEqual(self.names(name="brav"), ["Bravo Two"])
        self.assertEqual(self.names(phone="+91 98765 00003"), ["Charlie Three"])
        self.assertEqual(self.names(code=self.a.code.lower()), ["Alpha One"])

    def test_last_message_date_range(self):
        self.assertEqual(self.names(last_message_from="2026-10-20"), ["Alpha One"])
        self.assertEqual(self.names(last_message_to="2026-10-16"), ["Bravo Two"])
        self.assertEqual(self.api.get("/api/candidates/", {"last_message_from": "yesterday"}).status_code, 400)

    def test_ordering_and_pagination(self):
        self.assertEqual(self.names(ordering="name"), ["Alpha One", "Bravo Two", "Charlie Three"])
        data = self.api.get("/api/candidates/", {"page_size": 2}).json()
        self.assertEqual((data["count"], len(data["results"])), (3, 2))

    def test_search_matches_code(self):
        self.assertEqual(self.names(search=self.b.code), ["Bravo Two"])


class DeleteTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.people = [make_candidate(i) for i in range(1, 4)]

    def test_delete_one_removes_history_too(self):
        _, (msg,) = services.create_messages([self.people[0]], "hi", "whatsapp")
        resp = self.api.delete(f"/api/candidates/{self.people[0].id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Message.objects.filter(pk=msg.pk).exists())
        self.assertEqual(Candidate.objects.count(), 2)

    def test_bulk_delete(self):
        resp = self.api.post("/api/candidates/bulk-delete/", {"ids": [self.people[0].id, self.people[1].id]}, format="json")
        self.assertEqual(resp.json(), {"deleted": 2})
        self.assertEqual(Candidate.objects.count(), 1)

    def test_bulk_delete_ignores_unknown_ids_and_validates_input(self):
        self.assertEqual(self.api.post("/api/candidates/bulk-delete/", {"ids": [9999]}, format="json").json(), {"deleted": 0})
        for bad in ({}, {"ids": []}, {"ids": "1"}, {"ids": ["a"]}):
            resp = self.api.post("/api/candidates/bulk-delete/", bad, format="json")
            self.assertEqual(resp.status_code, 400, bad)
            self.assertIn("ids", resp.json()["error"]["fields"])

    def test_deleting_a_candidate_mid_send_does_not_break_the_worker(self):
        _, (msg,) = services.create_messages([self.people[0]], "hi", "whatsapp")
        survivor = services.create_messages([self.people[1]], "hi", "whatsapp")[1][0]
        original = services._claim

        def claim_then_delete(message_id):
            claimed = original(message_id)
            if message_id == msg.pk:
                Candidate.objects.filter(pk=self.people[0].pk).delete()
            return claimed

        from unittest import mock

        with mock.patch("messaging.services._claim", side_effect=claim_then_delete), patched_provider(FakeProvider()):
            services.process_due()
        survivor.refresh_from_db()
        self.assertEqual(survivor.status, S.SENT)


class SeedTests(TestCase):
    def test_seed_demo_creates_figma_data_once(self):
        from django.core.management import call_command

        call_command("seed_demo", stdout=open("/dev/null", "w"))
        self.assertEqual(Candidate.objects.count(), 7)
        krishna = Candidate.objects.get(code="A1B2C3")
        self.assertEqual(krishna.messages.count(), 3)
        urvashi = Candidate.objects.get(code="D4E5F6")
        self.assertEqual(urvashi.messages.get().status, S.FAILED)
        call_command("seed_demo", stdout=open("/dev/null", "w"))  # second run is a no-op
        self.assertEqual(Candidate.objects.count(), 7)
