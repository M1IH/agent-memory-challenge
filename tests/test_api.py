import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.store import MemoryStore


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_patch = patch(
            "app.main.store",
            MemoryStore(
                Path(self.temp_dir.name) / "api-test.db",
                embedder=False,
            ),
        )
        self.store_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_add_echoes_identifiers_and_search_finds_written_memory(self):
        payload = {
            "request_id": "req-1",
            "messages": [
                {
                    "role": "user",
                    "timestamp": 1704067200000,
                    "content": "我喜欢喝乌龙茶",
                }
            ],
            "user_id": "alice",
            "session_id": "session-1",
        }
        add_response = self.client.post("/add", json=payload)
        self.assertEqual(200, add_response.status_code)
        self.assertEqual(
            {
                "success": True,
                "request_id": "req-1",
                "user_id": "alice",
                "session_id": "session-1",
            },
            add_response.json(),
        )

        search_response = self.client.post(
            "/search",
            json={
                "query": "我喜欢喝什么",
                "options": ["A. 咖啡", "B. 乌龙茶"],
                "user_id": "alice",
                "top_k": 10,
            },
        )
        self.assertEqual(200, search_response.status_code)
        self.assertIn("乌龙茶", search_response.json()["data"][0]["content"])

    def test_api_key_is_enforced_when_configured(self):
        with patch.dict(os.environ, {"AML_API_KEY": "secret"}):
            denied = self.client.post(
                "/search",
                json={"query": "茶", "user_id": "alice", "top_k": 10},
            )
            allowed = self.client.post(
                "/search",
                headers={"Authorization": "Bearer secret"},
                json={"query": "茶", "user_id": "alice", "top_k": 10},
            )
        self.assertEqual(401, denied.status_code)
        self.assertEqual(200, allowed.status_code)

    def test_all_supported_api_key_schemes_are_accepted(self):
        payload = {"query": "茶", "user_id": "alice", "top_k": 10}
        with patch.dict(os.environ, {"AML_API_KEY": "secret"}):
            token = self.client.post(
                "/search", headers={"Authorization": "Token secret"}, json=payload
            )
            x_api_key = self.client.post(
                "/search", headers={"X-Api-Key": "secret"}, json=payload
            )
        self.assertEqual(200, token.status_code)
        self.assertEqual(200, x_api_key.status_code)

    def test_invalid_top_k_is_rejected(self):
        response = self.client.post(
            "/search",
            json={"query": "茶", "user_id": "alice", "top_k": 0},
        )
        self.assertEqual(422, response.status_code)

    def test_aggregate_add_and_search_limits_return_413(self):
        self.store_patch.stop()
        limited_store = MemoryStore(
            Path(self.temp_dir.name) / "limited-api.db", embedder=False
        )
        limited_store.max_add_chars = 5
        limited_store.max_search_chars = 5
        self.store_patch = patch("app.main.store", limited_store)
        self.store_patch.start()

        add_response = self.client.post(
            "/add",
            json={
                "request_id": "too-large",
                "user_id": "alice",
                "session_id": "session",
                "messages": [
                    {"role": "user", "content": "abc"},
                    {"role": "assistant", "content": "def"},
                ],
            },
        )
        search_response = self.client.post(
            "/search",
            json={
                "query": "abc",
                "options": ["def"],
                "user_id": "alice",
                "top_k": 100,
            },
        )

        self.assertEqual(413, add_response.status_code)
        self.assertEqual(413, search_response.status_code)
        self.assertIn("character limit", add_response.json()["detail"])
        self.assertIn("character limit", search_response.json()["detail"])

    def test_blank_content_and_unrepresentable_timestamp_are_rejected(self):
        base = {
            "request_id": "req-invalid",
            "user_id": "alice",
            "session_id": "session-1",
        }
        blank = self.client.post(
            "/add", json={**base, "messages": [{"role": "user", "content": "   "}]}
        )
        bad_time = self.client.post(
            "/add",
            json={**base, "messages": [{"role": "user", "content": "ok", "timestamp": 10**30}]},
        )
        self.assertEqual(422, blank.status_code)
        self.assertEqual(422, bad_time.status_code)

    def test_request_id_reuse_with_different_payload_is_rejected(self):
        base = {
            "request_id": "req-reused",
            "user_id": "alice",
            "session_id": "session-1",
        }
        first = self.client.post(
            "/add", json={**base, "messages": [{"role": "user", "content": "first"}]}
        )
        conflict = self.client.post(
            "/add", json={**base, "messages": [{"role": "user", "content": "second"}]}
        )
        self.assertEqual(200, first.status_code)
        self.assertEqual(409, conflict.status_code)

    def test_system_messages_are_accepted_and_searchable(self):
        add_response = self.client.post(
            "/add",
            json={
                "request_id": "req-system",
                "messages": [
                    {
                        "role": "system",
                        "content": "Never include customer email addresses in reports.",
                    }
                ],
                "user_id": "alice",
                "session_id": "session-system",
            },
        )
        self.assertEqual(200, add_response.status_code)
        search_response = self.client.post(
            "/search",
            json={
                "query": "What must reports never include?",
                "user_id": "alice",
                "top_k": 100,
            },
        )
        self.assertEqual(200, search_response.status_code)
        self.assertIn("system:", search_response.json()["data"][0]["content"])

    def test_backend_value_error_is_not_reported_as_request_conflict(self):
        with patch("app.main.store.add", side_effect=ValueError("backend failure")):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post("/add", json={
                    "request_id": "req-error", "user_id": "alice", "session_id": "s",
                    "messages": [{"role": "user", "content": "tea"}],
                })
        self.assertEqual(500, response.status_code)
        self.assertNotIn("backend failure", response.text)


if __name__ == "__main__":
    unittest.main()
