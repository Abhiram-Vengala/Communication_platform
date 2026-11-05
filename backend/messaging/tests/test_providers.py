from unittest import mock

import requests
from django.test import SimpleTestCase

from messaging.providers import DummyProvider, ProviderError


def response(status, body=None, headers=None, text=""):
    resp = mock.Mock(status_code=status, headers=headers or {}, text=text)
    if body is None:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = body
    return resp


class DummyProviderTests(SimpleTestCase):
    def send(self, resp=None, exc=None):
        provider = DummyProvider("whatsapp", "whatsapp", "http://provider")
        with mock.patch("messaging.providers.requests.post", return_value=resp, side_effect=exc) as post:
            try:
                return provider.send(to="+919876512345", body="hi", idempotency_key="k"), post
            except ProviderError as err:
                return err, post

    def test_success(self):
        result, post = self.send(response(202, {"id": "pm_1", "status": "accepted"}))
        self.assertEqual(result.provider_message_id, "pm_1")
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["Idempotency-Key"], "k")
        self.assertTrue(headers["Authorization"].startswith("Bearer "))

    def test_invalid_recipient_is_permanent(self):
        err, _ = self.send(response(400, {"error": {"code": "invalid_recipient", "message": "bad"}}))
        self.assertEqual((err.code, err.retryable), ("invalid_recipient", False))

    def test_rate_limit_is_retryable_with_retry_after(self):
        err, _ = self.send(response(429, {"error": {"code": "rate_limited"}}, {"Retry-After": "3"}))
        self.assertEqual((err.code, err.retryable, err.retry_after), ("rate_limited", True, 3))

    def test_server_error_is_retryable(self):
        err, _ = self.send(response(503, {"error": {"code": "service_unavailable"}}))
        self.assertEqual((err.code, err.retryable), ("provider_unavailable", True))

    def test_html_error_page_is_handled(self):
        err, _ = self.send(response(502, None, text="<html>Bad gateway</html>"))
        self.assertEqual((err.code, err.retryable), ("provider_unavailable", True))

    def test_timeout_and_connection_errors_are_retryable(self):
        for exc in (requests.Timeout("slow"), requests.ConnectionError("refused")):
            err, _ = self.send(exc=exc)
            self.assertEqual((err.code, err.retryable), ("provider_unavailable", True))

    def test_bad_credentials_are_permanent_and_friendly(self):
        err, _ = self.send(response(401, {"error": {"code": "unauthorized"}}))
        self.assertEqual((err.code, err.retryable), ("provider_auth", False))
        self.assertIn("administrator", err.friendly)

    def test_unknown_client_error_is_permanent(self):
        err, _ = self.send(response(422, {"error": {"code": "weird"}}))
        self.assertEqual((err.code, err.retryable), ("rejected", False))

    def test_garbage_success_body_is_retryable(self):
        err, _ = self.send(response(200, {"nope": 1}))
        self.assertEqual((err.code, err.retryable), ("provider_error", True))

    def test_health_reports_down_when_unreachable(self):
        provider = DummyProvider("whatsapp", "whatsapp", "http://provider")
        with mock.patch("messaging.providers.requests.get", side_effect=requests.ConnectionError()):
            self.assertEqual(provider.health()["status"], "down")
