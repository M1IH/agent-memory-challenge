from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


BASE_URL = "http://127.0.0.1:8765"
API_KEY = "local-smoke-secret"


def wait_until_ready(client: httpx.Client, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited early with code {process.returncode}")
        try:
            response = client.get(f"{BASE_URL}/health")
            if response.status_code == 200 and response.json() == {"status": "ok"}:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.25)
    raise TimeoutError("server did not become healthy within 60 seconds")


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        environment = os.environ.copy()
        environment.update(
            {
                "API_KEY": API_KEY,
                "AML_DB_PATH": str(Path(temp_dir) / "smoke.db"),
            }
        )
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        try:
            with httpx.Client(timeout=30) as client:
                wait_until_ready(client, process)
                denied = client.post(
                    f"{BASE_URL}/search",
                    json={"query": "contact", "user_id": "alice", "top_k": 100},
                )
                assert denied.status_code == 401, denied.text

                add_response = client.post(
                    f"{BASE_URL}/add",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={
                        "request_id": "smoke-request-1",
                        "messages": [
                            {
                                "role": "user",
                                "timestamp": 1704067200000,
                                "content": "My emergency contact is Jordan Lee.",
                            }
                        ],
                        "user_id": "alice",
                        "session_id": "smoke-session-1",
                    },
                )
                add_response.raise_for_status()
                assert add_response.json()["request_id"] == "smoke-request-1"

                for headers in (
                    {"Authorization": f"Bearer {API_KEY}"},
                    {"Authorization": f"Token {API_KEY}"},
                    {"X-Api-Key": API_KEY},
                ):
                    search_response = client.post(
                        f"{BASE_URL}/search",
                        headers=headers,
                        json={
                            "query": "Who is my emergency contact?",
                            "user_id": "alice",
                            "top_k": 100,
                        },
                    )
                    search_response.raise_for_status()
                    assert "Jordan Lee" in search_response.json()["data"][0]["content"]
            print("PASS: health, auth, synchronous add, and search")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
