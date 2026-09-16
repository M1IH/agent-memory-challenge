from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from smoke_remote import run_smoke


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
                run_smoke(
                    client,
                    base_url=BASE_URL,
                    api_key=API_KEY,
                    probe_id="local-smoke",
                )
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
