"""Free-tier overflow: immutable volume seed plus an S3 write-ahead journal.

The volume database is only read. Every new Add is journaled before its local
SQLite transaction commits, so a fresh container can rebuild the ephemeral DB.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import zlib
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.exceptions import ClientError


class OverflowJournal:
    def __init__(self, *, endpoint: str, bucket: str, access_key: str, secret_key: str):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

    @classmethod
    def from_environment(cls) -> "OverflowJournal | None":
        if os.getenv("AML_OVERFLOW_ENABLED", "false").lower() != "true":
            return None
        names = (
            "AML_OVERFLOW_ENDPOINT",
            "AML_OVERFLOW_BUCKET",
            "AML_OVERFLOW_ACCESS_KEY",
            "AML_OVERFLOW_SECRET_KEY",
        )
        values = [os.environ[name] for name in names]
        return cls(
            endpoint=values[0], bucket=values[1],
            access_key=values[2], secret_key=values[3],
        )

    @staticmethod
    def _key(user_id: str, request_id: str) -> str:
        digest = hashlib.sha256(
            json.dumps([user_id, request_id], ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return f"add/{digest}.json.z"

    def record(self, *, request_id: str, user_id: str, session_id: str,
               messages: list[dict], created_at: str, payload_hash: str) -> str:
        key = self._key(user_id, request_id)
        record = {
            "request_id": request_id, "user_id": user_id,
            "session_id": session_id, "messages": messages,
            "created_at": created_at, "payload_hash": payload_hash,
        }
        payload = zlib.compress(
            json.dumps(record, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        )
        try:
            existing = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {"NoSuchKey", "404"}:
                raise
        else:
            previous = json.loads(zlib.decompress(existing))
            if previous["payload_hash"] != payload_hash or previous["user_id"] != user_id or previous["request_id"] != request_id:
                raise ValueError("conflicting durable Add journal entry")
            return previous["created_at"]
        self.client.put_object(Bucket=self.bucket, Key=key, Body=payload)
        return created_at

    def _keys(self) -> list[str]:
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix="add/"):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return sorted(keys)

    def prepare(self, *, seed_path: str | Path, runtime_path: str | Path) -> list[str]:
        # Check S3 before touching any ephemeral copy. The seed is never changed.
        keys = self._keys()
        seed = Path(seed_path)
        if not seed.is_file():
            raise FileNotFoundError(f"overflow seed database missing: {seed}")
        runtime = Path(runtime_path)
        runtime.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            (runtime.parent / (runtime.name + suffix)).unlink(missing_ok=True)
        source = sqlite3.connect(f"file:{seed.as_posix()}?mode=ro", uri=True)
        try:
            destination = sqlite3.connect(runtime)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
        return keys

    def replay(self, store, keys: list[str]) -> int:
        def fetch_record(key: str) -> dict:
            payload = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            return json.loads(zlib.decompress(payload))

        count = 0
        # Fetch in bounded parallel batches; apply in stable key order so a
        # restart rebuilds the same SQLite state without holding every record
        # in memory. The S3 client supports concurrent requests.
        with ThreadPoolExecutor(max_workers=16) as pool:
            for offset in range(0, len(keys), 128):
                for record in pool.map(fetch_record, keys[offset:offset + 128]):
                    store.add(
                        request_id=record["request_id"], user_id=record["user_id"],
                        session_id=record["session_id"], messages=record["messages"],
                        _created_at=record["created_at"], _skip_journal=True,
                    )
                    count += 1
        return count
