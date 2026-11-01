"""Synthetic end-to-end probe for the optional Railway bucket overflow path."""

import os
import tempfile
import time
from pathlib import Path

from app.overflow import OverflowJournal
from app.store import MemoryStore


def main():
    journal = OverflowJournal(
        endpoint=os.environ["AML_PROBE_ENDPOINT"],
        bucket=os.environ["AML_PROBE_BUCKET"],
        access_key=os.environ["AML_PROBE_ACCESS"],
        secret_key=os.environ["AML_PROBE_SECRET"],
    )
    count = int(os.getenv("AML_PROBE_COUNT", "1"))
    request_ids = [f"synthetic-overflow-probe-20261101-{index}" for index in range(count)]
    user_id = "synthetic-probe-user"
    keys_to_delete = [journal._key(user_id, request_id) for request_id in request_ids]
    try:
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / "seed.db"
            runtime = Path(directory) / "runtime.db"
            MemoryStore(seed, embedder=False, compress_text=True)
            journal.prepare(seed_path=seed, runtime_path=runtime)
            store = MemoryStore(runtime, embedder=False, compress_text=True, journal=journal)
            started = time.monotonic()
            for request_id in request_ids:
                store.add(request_id, user_id, "synthetic-session",
                          [{"role": "user", "content": "synthetic test memory"}])
            add_seconds = time.monotonic() - started
            keys = journal.prepare(seed_path=seed, runtime_path=runtime)
            rebuilt = MemoryStore(runtime, embedder=False, compress_text=True)
            assert journal.replay(rebuilt, keys) == count
            with rebuilt._connection() as connection:
                assert connection.execute("SELECT count(*) FROM memories").fetchone()[0] == count
        print("bucket_overflow_roundtrip_ok", "adds", count,
              "mean_add_seconds", round(add_seconds / count, 3))
    finally:
        for key in keys_to_delete:
            journal.client.delete_object(Bucket=journal.bucket, Key=key)


if __name__ == "__main__":
    main()
