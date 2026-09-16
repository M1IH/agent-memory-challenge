import json
import os
import unittest
from unittest.mock import patch

import httpx

from scripts.smoke_remote import (
    configured_api_key,
    run_smoke,
    success_summary,
    validated_base_url,
)


class RemoteSmokeTests(unittest.TestCase):
    def test_success_summary_reports_the_actual_transport(self):
        self.assertIn(
            "HTTPS/auth",
            success_summary("https://memory.example", "request-1"),
        )
        self.assertIn(
            "HTTP/auth",
            success_summary("http://127.0.0.1:8000", "request-1"),
        )

    def test_https_is_required_unless_http_is_explicitly_allowed(self):
        self.assertEqual(
            "https://memory.example/api",
            validated_base_url("https://memory.example/api/", allow_http=False),
        )
        self.assertEqual(
            "http://127.0.0.1:8000",
            validated_base_url("http://127.0.0.1:8000", allow_http=True),
        )
        with self.assertRaisesRegex(ValueError, "must use https"):
            validated_base_url("http://memory.example", allow_http=False)
        with self.assertRaisesRegex(ValueError, "no embedded credentials"):
            validated_base_url("https://secret@memory.example", allow_http=False)
        with self.assertRaisesRegex(ValueError, "query string or fragment"):
            validated_base_url("https://memory.example?key=secret", allow_http=False)

    def test_api_key_is_loaded_from_environment_and_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "set AML_API_KEY"):
                configured_api_key()
        with patch.dict(os.environ, {"AML_API_KEY": "   "}, clear=True):
            with self.assertRaisesRegex(ValueError, "set AML_API_KEY"):
                configured_api_key()
        with patch.dict(
            os.environ,
            {"AML_API_KEY": "   ", "API_KEY": "fallback-secret"},
            clear=True,
        ):
            self.assertEqual("fallback-secret", configured_api_key())
        with patch.dict(os.environ, {"AML_API_KEY": "secret"}, clear=True):
            self.assertEqual("secret", configured_api_key())

    def test_remote_smoke_verifies_auth_add_echo_and_immediate_search(self):
        marker = "aml-remote-smoke-fixed-probe"
        seen_auth_headers = []
        add_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/api/add":
                self.assertEqual("Bearer secret", request.headers["Authorization"])
                payload = json.loads(request.content)
                add_requests.append(payload)
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "request_id": payload["request_id"],
                        "user_id": payload["user_id"],
                        "session_id": payload["session_id"],
                    },
                )
            if request.url.path == "/api/search":
                payload = json.loads(request.content)
                authorization = request.headers.get("Authorization")
                api_key = request.headers.get("X-Api-Key")
                if authorization is None and api_key is None:
                    return httpx.Response(401, json={"detail": "Invalid API key"})
                if payload["user_id"].startswith("foreign-"):
                    return httpx.Response(200, json={"data": []})
                seen_auth_headers.append(authorization or f"X-Api-Key {api_key}")
                return httpx.Response(
                    200,
                    json={"data": [{"id": "1", "content": marker}]},
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            identifiers = run_smoke(
                client,
                base_url="https://memory.example/api",
                api_key="secret",
                probe_id="fixed-probe",
            )

        self.assertEqual("smoke-request-fixed-probe", identifiers["request_id"])
        self.assertEqual(2, len(add_requests))
        self.assertEqual(add_requests[0], add_requests[1])
        self.assertEqual(
            ["Bearer secret", "Token secret", "X-Api-Key secret"],
            seen_auth_headers,
        )

    def test_remote_smoke_rejects_cross_user_probe_leakage(self):
        marker = "aml-remote-smoke-leak-probe"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/add":
                payload = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "request_id": payload["request_id"],
                        "user_id": payload["user_id"],
                        "session_id": payload["session_id"],
                    },
                )
            if request.url.path == "/search":
                if (
                    request.headers.get("Authorization") is None
                    and request.headers.get("X-Api-Key") is None
                ):
                    return httpx.Response(401, json={"detail": "Invalid API key"})
                return httpx.Response(200, json={"data": [{"content": marker}]})
            return httpx.Response(404)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(RuntimeError, "leaked probe evidence"):
                run_smoke(
                    client,
                    base_url="https://memory.example",
                    api_key="secret",
                    probe_id="leak-probe",
                )

    def test_remote_smoke_rejects_duplicate_probe_after_replay(self):
        marker = "aml-remote-smoke-duplicate-probe"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/add":
                payload = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "request_id": payload["request_id"],
                        "user_id": payload["user_id"],
                        "session_id": payload["session_id"],
                    },
                )
            if request.url.path == "/search":
                if (
                    request.headers.get("Authorization") is None
                    and request.headers.get("X-Api-Key") is None
                ):
                    return httpx.Response(401, json={"detail": "Invalid API key"})
                return httpx.Response(
                    200,
                    json={"data": [{"content": marker}, {"content": marker}]},
                )
            return httpx.Response(404)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(RuntimeError, "exactly one searchable probe"):
                run_smoke(
                    client,
                    base_url="https://memory.example",
                    api_key="secret",
                    probe_id="duplicate-probe",
                )

    def test_remote_smoke_rejects_an_open_unauthenticated_search(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(200, json={"data": []})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(RuntimeError, "expected 401"):
                run_smoke(
                    client,
                    base_url="https://memory.example",
                    api_key="secret",
                    probe_id="open-api",
                )


if __name__ == "__main__":
    unittest.main()
