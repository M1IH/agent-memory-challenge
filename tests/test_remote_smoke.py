import json
import os
import unittest
from unittest.mock import patch

import httpx

from scripts.smoke_remote import (
    configured_api_key,
    run_smoke,
    validated_base_url,
)


class RemoteSmokeTests(unittest.TestCase):
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
        with patch.dict(os.environ, {"AML_API_KEY": "secret"}, clear=True):
            self.assertEqual("secret", configured_api_key())

    def test_remote_smoke_verifies_auth_add_echo_and_immediate_search(self):
        marker = "aml-remote-smoke-fixed-probe"
        seen_auth_headers = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/api/add":
                self.assertEqual("Bearer secret", request.headers["Authorization"])
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
            if request.url.path == "/api/search":
                authorization = request.headers.get("Authorization")
                api_key = request.headers.get("X-Api-Key")
                if authorization is None and api_key is None:
                    return httpx.Response(401, json={"detail": "Invalid API key"})
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
        self.assertEqual(
            ["Bearer secret", "Token secret", "X-Api-Key secret"],
            seen_auth_headers,
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
