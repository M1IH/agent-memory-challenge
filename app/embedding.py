from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterable, Iterator

import numpy as np


def positive_concurrency(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("AML_EMBED_CONCURRENCY must be a positive integer") from exc
    if parsed < 1:
        raise ValueError("AML_EMBED_CONCURRENCY must be a positive integer")
    return parsed


class _PriorityCapacity:
    """Bound inference concurrency while allowing latency-sensitive queries first."""

    def __init__(self, limit: int, max_query_burst: int = 8) -> None:
        if limit < 1 or max_query_burst < 1:
            raise ValueError("capacity limits must be positive")
        self._limit = limit
        self._max_query_burst = max_query_burst
        self._active = 0
        self._waiting_queries = 0
        self._waiting_adds = 0
        self._query_burst = 0
        self._condition = threading.Condition()

    @contextmanager
    def slot(self, query: bool = False) -> Iterator[None]:
        with self._condition:
            if query:
                self._waiting_queries += 1
            else:
                self._waiting_adds += 1
            try:
                self._condition.wait_for(
                    lambda: self._active < self._limit
                    and (
                        (
                            query
                            and (
                                self._waiting_adds == 0
                                or self._query_burst < self._max_query_burst
                            )
                        )
                        or (
                            not query
                            and (
                                self._waiting_queries == 0
                                or self._query_burst >= self._max_query_burst
                            )
                        )
                    )
                )
                self._active += 1
                if query:
                    if self._waiting_adds:
                        self._query_burst += 1
                    else:
                        self._query_burst = 0
                else:
                    self._query_burst = 0
            finally:
                if query:
                    self._waiting_queries -= 1
                else:
                    self._waiting_adds -= 1
                self._condition.notify_all()
        try:
            yield
        finally:
            with self._condition:
                self._active -= 1
                self._condition.notify_all()


class EmbeddingBackend:
    """Thread-safe local embedding backend with no runtime API dependency."""

    supports_query_priority = True

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        model_name = os.getenv("AML_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
        cache_dir = os.getenv("AML_MODEL_CACHE") or None
        concurrency = positive_concurrency(os.getenv("AML_EMBED_CONCURRENCY", "2"))
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
        self._capacity = _PriorityCapacity(concurrency)
        self.concurrency = concurrency
        self.index_identity = f"fastembed:{model_name}:float32:l2-v1"

    def encode(self, texts: Iterable[str]) -> list[np.ndarray]:
        return self._encode(texts, query=False)

    def encode_query(self, texts: Iterable[str]) -> list[np.ndarray]:
        return self._encode(texts, query=True)

    def _encode(self, texts: Iterable[str], query: bool) -> list[np.ndarray]:
        values = list(texts)
        if not values:
            return []
        with self._capacity.slot(query=query):
            vectors = list(self._model.embed(values))
        return [self._normalize(np.asarray(vector, dtype=np.float32)) for vector in vectors]

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        return vector if norm == 0 else vector / norm
