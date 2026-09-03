from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol

import numpy as np

from .embedding import EmbeddingBackend


_LATIN_WORD = re.compile(r"[a-z0-9]+(?:['_-][a-z0-9]+)*", re.I)
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
_OPTION_LABEL = re.compile(r"^\s*(?:[A-Z]|\d+)[.、:)）]\s*", re.I)
_CONCEPT_GROUPS = (
    (
        "住", "居住", "生活", "定居", "落脚", "搬到", "迁居",
        "live", "reside", "relocate", "relocated", "move", "moved",
    ),
    ("买", "购买", "入手", "添置", "购置", "bought", "buy", "purchase"),
    ("喜欢", "偏爱", "最爱", "首选", "favorite", "prefer"),
    (
        "避免", "不吃", "讨厌", "不喜欢", "过敏",
        "avoid", "cannot stand", "dislike", "hate", "allergic", "allergy",
    ),
    ("工作", "职业", "职位", "任职", "job", "career", "work"),
)
_CURRENT_MARKERS = ("现在", "目前", "最近", "如今", "当前", "latest", "current", "now")
_UPDATE_MARKERS = ("后来", "改成", "改为", "变了", "不再", "首选", "updated", "changed")


def tokenize(text: str) -> list[str]:
    """Tokenize English words and overlapping Chinese characters/bigrams."""
    lowered = text.lower()
    tokens = _LATIN_WORD.findall(lowered)
    for run in _CJK_RUN.findall(lowered):
        tokens.extend(run)
        tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def semantic_expansion_terms(text: str) -> list[str]:
    """Return small, auditable synonym expansions without a paid model."""
    lowered = text.lower()
    expansions: list[str] = []
    for group in _CONCEPT_GROUPS:
        if any(phrase in lowered for phrase in group):
            # Only add actual alternatives. Re-adding the query's own wording
            # would amplify lexical distractors instead of bridging paraphrases.
            alternatives = [phrase for phrase in group if phrase not in lowered]
            expansions.extend(tokenize(" ".join(alternatives)))
    return expansions


@dataclass(frozen=True)
class Memory:
    id: str
    content: str
    created_at: str
    timestamp_ms: int | None
    terms: list[str]
    embedding: np.ndarray | None


class Encoder(Protocol):
    def encode(self, texts: Iterable[str]) -> list[np.ndarray]: ...


class MemoryStore:
    def __init__(
        self,
        path: str | Path,
        embedder: Encoder | bool | None = None,
    ):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if embedder is False:
            self._embedder = None
        elif embedder is not None:
            self._embedder = embedder
        elif os.getenv("AML_EMBED_ENABLED", "true").lower() in {
            "0", "false", "no", "off"
        }:
            self._embedder = None
        else:
            self._embedder = EmbeddingBackend()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp_ms INTEGER,
                    created_at TEXT NOT NULL,
                    terms TEXT NOT NULL,
                    embedding BLOB
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)"
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "embedding" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN embedding BLOB")

    def add(
        self,
        request_id: str,
        user_id: str,
        session_id: str,
        messages: Iterable[dict],
    ) -> None:
        message_values = list(messages)
        raw_contents = [message["content"].strip() for message in message_values]
        max_context_chars = int(os.getenv("AML_MAX_CONTEXT_CHARS", "1200"))
        index_contents: list[str] = []
        display_contents: list[str] = []
        for index, (message, content) in enumerate(zip(message_values, raw_contents)):
            current_display = self._format_content(
                message["role"], content, message.get("timestamp")
            )
            current_index = f"{message['role']}: {content}"
            if index > 0:
                previous = message_values[index - 1]
                previous_content = raw_contents[index - 1]
                previous_display = self._format_content(
                    previous["role"], previous_content, previous.get("timestamp")
                )
                contextual_display = f"{previous_display}\n{current_display}"
                contextual_index = (
                    f"{previous['role']}: {previous_content}\n{current_index}"
                )
                if len(contextual_display) <= max_context_chars:
                    current_display = contextual_display
                    current_index = contextual_index
            display_contents.append(current_display)
            index_contents.append(current_index)
        embeddings = (
            self._embedder.encode(index_contents)
            if self._embedder is not None
            else [None] * len(raw_contents)
        )
        rows = []
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for index, (message, content, display_content, index_content, embedding) in enumerate(
            zip(
                message_values,
                raw_contents,
                display_contents,
                index_contents,
                embeddings,
            )
        ):
            role = message["role"]
            timestamp_ms = message.get("timestamp")
            digest = hashlib.sha256(
                f"{request_id}\0{user_id}\0{session_id}\0{index}\0{role}\0"
                f"{timestamp_ms}\0{content}".encode()
            ).hexdigest()[:24]
            rows.append(
                (
                    f"mem_{digest}", request_id, user_id, session_id,
                    role, display_content, timestamp_ms, now,
                    " ".join(tokenize(index_content)),
                    None if embedding is None else embedding.tobytes(),
                )
            )
        with self._lock, self._connection() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO memories
                (id, request_id, user_id, session_id, role, content,
                 timestamp_ms, created_at, terms, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int,
        options: list[str] | None = None,
    ) -> list[dict]:
        query_terms = tokenize(query)
        expansion_terms = semantic_expansion_terms(query)
        option_texts = [
            _OPTION_LABEL.sub("", option).strip()
            for option in (options or [])
            if option.strip()
        ]
        option_terms = [tokenize(option) for option in option_texts]
        if not query_terms:
            return []

        with self._connection() as connection:
            db_rows = connection.execute(
                """
                SELECT id, content, timestamp_ms, created_at, terms, embedding
                FROM memories WHERE user_id = ?
                """,
                (user_id,),
            ).fetchall()
        if not db_rows:
            return []

        memories = [
            Memory(
                id=row["id"], content=row["content"],
                timestamp_ms=row["timestamp_ms"], created_at=row["created_at"],
                terms=row["terms"].split(),
                embedding=(
                    np.frombuffer(row["embedding"], dtype=np.float32)
                    if row["embedding"] is not None else None
                ),
            )
            for row in db_rows
        ]
        document_frequency: dict[str, int] = {}
        for memory in memories:
            for term in set(memory.terms):
                document_frequency[term] = document_frequency.get(term, 0) + 1

        average_length = sum(len(memory.terms) for memory in memories) / len(memories)
        lexical_scores = []
        newest_timestamp = max((memory.timestamp_ms or 0) for memory in memories)
        oldest_timestamp = min((memory.timestamp_ms or 0) for memory in memories)
        asks_for_current = any(marker in query.lower() for marker in _CURRENT_MARKERS)
        for memory in memories:
            score = self._bm25(
                query_terms, memory.terms, document_frequency,
                len(memories), average_length,
            )
            # Options are supporting evidence, not extra query text. Scoring each
            # option separately prevents a long option list from overwhelming the
            # user's actual question.
            option_score = max(
                (
                    self._bm25(
                        terms, memory.terms, document_frequency,
                        len(memories), average_length,
                    )
                    for terms in option_terms if terms
                ),
                default=0.0,
            )
            score += 0.35 * option_score
            if expansion_terms:
                score += 6.5 * self._bm25(
                    expansion_terms, memory.terms, document_frequency,
                    len(memories), average_length,
                )

            unique_query_terms = set(query_terms)
            matched_query_terms = unique_query_terms.intersection(memory.terms)
            score += 0.75 * len(matched_query_terms) / max(len(unique_query_terms), 1)
            if query.lower() in memory.content.lower():
                score += 2.0
            if any(option.lower() in memory.content.lower() for option in option_texts):
                score += 0.5
            if asks_for_current:
                if newest_timestamp > oldest_timestamp and memory.timestamp_ms is not None:
                    score += 0.4 * (
                        (memory.timestamp_ms - oldest_timestamp)
                        / (newest_timestamp - oldest_timestamp)
                    )
                if any(marker in memory.content.lower() for marker in _UPDATE_MARKERS):
                    score += 10.0
            if score > 0:
                lexical_scores.append((score, memory))

        lexical_scores.sort(
            key=lambda item: (item[0], item[1].timestamp_ms or 0), reverse=True
        )
        if self._embedder is None or not any(memory.embedding is not None for memory in memories):
            scores = lexical_scores
        else:
            query_vector = self._embedder.encode([query])[0]
            dense_scores = sorted(
                (
                    (float(np.dot(query_vector, memory.embedding)), memory)
                    for memory in memories if memory.embedding is not None
                ),
                key=lambda item: (item[0], item[1].timestamp_ms or 0),
                reverse=True,
            )
            lexical_ranks = {
                memory.id: rank
                for rank, (_, memory) in enumerate(lexical_scores, start=1)
            }
            dense_ranks = {
                memory.id: rank
                for rank, (_, memory) in enumerate(dense_scores, start=1)
            }
            lexical_raw = {memory.id: score for score, memory in lexical_scores}
            memory_by_id = {memory.id: memory for memory in memories}
            fused = []
            for memory_id in set(lexical_ranks) | set(dense_ranks):
                score = 0.0
                if memory_id in lexical_ranks:
                    score += 1.0 / (60 + lexical_ranks[memory_id])
                if memory_id in dense_ranks:
                    score += 0.85 / (60 + dense_ranks[memory_id])
                # Preserve strong temporal/update preferences established in the
                # lexical channel without letting raw BM25 scale dominate fusion.
                if lexical_raw.get(memory_id, 0.0) >= 8.0:
                    score += 0.002
                fused.append((score, memory_by_id[memory_id]))
            fused.sort(
                key=lambda item: (item[0], item[1].timestamp_ms or 0), reverse=True
            )
            scores = fused
        return [
            {
                "id": memory.id,
                "content": memory.content,
                "score": round(score, 6),
                "created_at": self._source_time(memory),
            }
            for score, memory in scores[:top_k]
        ]

    @staticmethod
    def _bm25(
        query_terms: list[str], document_terms: list[str],
        document_frequency: dict[str, int], document_count: int,
        average_length: float,
    ) -> float:
        frequencies: dict[str, int] = {}
        for term in document_terms:
            frequencies[term] = frequencies.get(term, 0) + 1
        k1, b = 1.5, 0.75
        score = 0.0
        for term in set(query_terms):
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            df = document_frequency.get(term, 0)
            inverse_document_frequency = math.log(1 + (document_count - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (
                1 - b + b * len(document_terms) / max(average_length, 1)
            )
            score += inverse_document_frequency * frequency * (k1 + 1) / denominator
        return score

    @staticmethod
    def _source_time(memory: Memory) -> str:
        if memory.timestamp_ms is None:
            return memory.created_at
        return datetime.fromtimestamp(
            memory.timestamp_ms / 1000, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _format_content(role: str, content: str, timestamp_ms: int | None) -> str:
        if timestamp_ms is None:
            return f"{role}: {content}"
        timestamp = datetime.fromtimestamp(
            timestamp_ms / 1000, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")
        return f"[{timestamp}] {role}: {content}"
