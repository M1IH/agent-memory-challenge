from __future__ import annotations

import os
import threading
from typing import Iterable

import numpy as np


def positive_concurrency(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("AML_EMBED_CONCURRENCY must be a positive integer") from exc
    if parsed < 1:
        raise ValueError("AML_EMBED_CONCURRENCY must be a positive integer")
    return parsed


class EmbeddingBackend:
    """Thread-safe local embedding backend with no runtime API dependency."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        model_name = os.getenv("AML_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
        cache_dir = os.getenv("AML_MODEL_CACHE") or None
        concurrency = positive_concurrency(os.getenv("AML_EMBED_CONCURRENCY", "2"))
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
        self._lock = threading.BoundedSemaphore(concurrency)
        self.concurrency = concurrency
        self.index_identity = f"fastembed:{model_name}:float32:l2-v1"

    def encode(self, texts: Iterable[str]) -> list[np.ndarray]:
        values = list(texts)
        if not values:
            return []
        with self._lock:
            vectors = list(self._model.embed(values))
        return [self._normalize(np.asarray(vector, dtype=np.float32)) for vector in vectors]

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        return vector if norm == 0 else vector / norm
