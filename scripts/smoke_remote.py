from __future__ import annotations

import argparse
import os
import uuid
from urllib.parse import urlsplit

import httpx


def validated_base_url(value: str, *, allow_http: bool) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlsplit(base_url)
    allowed_schemes = {"https"} if not allow_http else {"http", "https"}
    if parsed.scheme.lower() not in allowed_schemes:
        requirement = "http or https" if allow_http else "https"
        raise ValueError(f"base URL must use {requirement}")
    if not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("base URL must contain a host and no embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a query string or fragment")
    return base_url


def configured_api_key() -> str:
    api_key = os.getenv("AML_API_KEY") or os.getenv("API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("set AML_API_KEY or API_KEY before running remote smoke")
    return api_key


def run_smoke(
    client: httpx.Client,
    *,
    base_url: str,
    api_key: str,
    probe_id: str | None = None,
) -> dict[str, str]:
    probe_id = probe_id or uuid.uuid4().hex
    marker = f"aml-remote-smoke-{probe_id}"
    user_id = f"smoke-user-{probe_id}"
    session_id = f"smoke-session-{probe_id}"
    request_id = f"smoke-request-{probe_id}"

    health = client.get(f"{base_url}/health")
    health.raise_for_status()
    if health.json() != {"status": "ok"}:
        raise RuntimeError("health response did not match the expected contract")

    denied = client.post(
        f"{base_url}/search",
        json={"query": marker, "user_id": user_id, "top_k": 100},
    )
    if denied.status_code != 401:
        raise RuntimeError(
            f"unauthenticated Search returned {denied.status_code}, expected 401"
        )

    add = client.post(
        f"{base_url}/add",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "request_id": request_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"Synthetic deployment probe marker: {marker}",
                }
            ],
            "user_id": user_id,
            "session_id": session_id,
        },
    )
    add.raise_for_status()
    add_payload = add.json()
    expected_echo = {
        "success": True,
        "request_id": request_id,
        "user_id": user_id,
        "session_id": session_id,
    }
    if add_payload != expected_echo:
        raise RuntimeError("Add response did not exactly echo the request identifiers")

    auth_headers = (
        {"Authorization": f"Bearer {api_key}"},
        {"Authorization": f"Token {api_key}"},
        {"X-Api-Key": api_key},
    )
    for headers in auth_headers:
        search = client.post(
            f"{base_url}/search",
            headers=headers,
            json={"query": marker, "user_id": user_id, "top_k": 100},
        )
        search.raise_for_status()
        search_payload = search.json()
        if not isinstance(search_payload, dict):
            raise RuntimeError("Search response was not a JSON object")
        data = search_payload.get("data")
        if not isinstance(data, list) or not data:
            raise RuntimeError("Search response did not contain any memory evidence")
        first = data[0]
        content = first.get("content") if isinstance(first, dict) else None
        if not isinstance(content, str) or marker not in content:
            raise RuntimeError("the newly added probe was not the first Search result")

    return {
        "request_id": request_id,
        "user_id": user_id,
        "session_id": session_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a deployed AML memory API without exposing its key on the command line."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("AML_BASE_URL"),
        help="deployment origin or prefix; defaults to AML_BASE_URL",
    )
    parser.add_argument(
        "--allow-http",
        action="store_true",
        help="allow plain HTTP for an explicitly local or isolated rehearsal",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    if not args.base_url:
        parser.error("provide --base-url or set AML_BASE_URL")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        base_url = validated_base_url(args.base_url, allow_http=args.allow_http)
        api_key = configured_api_key()
        with httpx.Client(timeout=args.timeout, follow_redirects=False) as client:
            identifiers = run_smoke(client, base_url=base_url, api_key=api_key)
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        parser.exit(1, f"REMOTE SMOKE FAILED: {exc}\n")

    print(
        "REMOTE SMOKE PASS: HTTPS/auth/Add/Search contract verified; "
        f"request_id={identifiers['request_id']}"
    )


if __name__ == "__main__":
    main()
