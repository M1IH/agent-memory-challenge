from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Protocol

import numpy as np

from .embedding import EmbeddingBackend


logger = logging.getLogger(__name__)


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
        "避免", "不吃", "讨厌", "不喜欢",
        "avoid", "cannot stand", "dislike", "hate",
    ),
    ("过敏", "allergic", "allergy"),
    ("工作", "职业", "职位", "任职", "job", "career", "work"),
    (
        "预订", "预约", "订了", "订房",
        "book", "booked", "booking", "reserve", "reserved", "reservation",
        "confirm", "confirmed",
    ),
    (
        "住宿", "旅馆", "酒店", "民宿",
        "accommodation", "hotel", "hostel", "guesthouse", "inn", "lodging",
    ),
)
_CURRENT_MARKERS = ("现在", "目前", "最近", "如今", "当前", "latest", "current", "now")
_UPDATE_MARKERS = ("后来", "改成", "改为", "变了", "不再", "首选", "updated", "changed")
_TOPIC_STOP = set("a an the my your our their his her its i we you it is are was were be been to of for in on at from with and or do does did what which where who when how now current latest later changed updated user assistant system favorite prefer currently".split()) | set(_CURRENT_MARKERS) | set(_UPDATE_MARKERS) | {"什么", "哪个", "哪里", "喜欢", "最喜", "我的", "你的", "我们", "他们", "这个", "那个"}
_ENTITY_STOP = {"My", "The", "A", "An", "I", "He", "She", "It", "We", "They", "Project", "Room", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
_CJK_ENTITY_PATTERNS = (
    re.compile(r"叫([\u3400-\u9fff]{2,4})(?=[，。！？,.!?]|$)"),
    re.compile(r"(?:^|[，。！？,.!?]|:\s)([\u3400-\u9fff]{2,4})(?=寄|负责|管理|保管|持有)"),
    re.compile(r"(?:使用(?:了)?|通过)([\u3400-\u9fff]{2,6}快递)"),
    re.compile(r"(?:^|:\s)([\u3400-\u9fff]{2,6}快递)"),
)
_PACKING_QUERY = re.compile(r"\bpack(?:ed|ing)?\b|打包|装了什么|带了什么", re.I)
_PACKING_SUPPORT = re.compile(
    r"\bpack(?:ed)?\b|\bput\b.{0,40}\b(?:bag|backpack|suitcase)\b|"
    r"\bwent into\b.{0,30}\b(?:bag|backpack|suitcase)\b|"
    r"(?:装进|放进|收进).{0,20}(?:包|背包|行李箱)",
    re.I,
)
_CONFIRM_QUERY = re.compile(r"\bconfirm(?:ed)?\b|已确认|确认参加", re.I)
_CONFIRM_SUPPORT = re.compile(
    r"\bconfirm(?:ed)?\b|\baccepted\b|\bsaid yes\b|已确认|接受了?邀请|答应参加",
    re.I,
)
_EVENT_NEGATION = re.compile(
    r"\b(?:did not|didn't|never|forgot|unpacked|removed|cancelled|declined)\b|"
    r"\bno reply\b|\bleft\b.{0,30}\bhome\b|\bstayed home\b|"
    r"\b(?:considered|planned|wanted)\b|,\s*not\b|"
    r"(?:没有|没带|忘了|取消|拒绝|留在家|并未)",
    re.I,
)
_QUERY_NEGATION = re.compile(r"\b(?:not|never|didn't|did not)\b|(?:没有|没|未)", re.I)
_IDENTIFIER_TOKEN = re.compile(r"(?=.*\d)[a-z0-9]+(?:[-_][a-z0-9]+)+", re.I)
_OTHER_FIRST_PERSON = re.compile(
    r"\bmy (?:colleague|coworker|friend|brother|sister|roommate|manager)\b|"
    r"(?:我的|我)(?:同事|朋友|哥哥|弟弟|姐姐|妹妹|室友|经理)",
    re.I,
)
_DENSE_BATCH_SIZE = 2048


def topic_terms(text: str) -> set[str]:
    # Keep Chinese bigrams, discard grammatical single characters and numeric
    # dates. Split Room-101 so explicit room updates can share a topic anchor.
    text = re.sub(r"\[\d{4}-\d{2}-\d{2}T[^\]]+\]", " ", text)
    for marker in (*_CURRENT_MARKERS, *_UPDATE_MARKERS):
        if not marker.isascii():
            text = text.replace(marker, " ")
    return {
        part for token in tokenize(text) for part in re.split(r"[-_]", token)
        if len(part) > 1 and not part.isdigit() and part not in _TOPIC_STOP
    }


def entity_terms(text: str) -> set[str]:
    """Extract conservative proper-name tokens for bounded linkage."""
    entities = {
        token.lower()
        for token in re.findall(r"(?<![\w-])[A-Z][a-z]+(?:-[A-Z]?[a-z]+)?", text)
        if token not in _ENTITY_STOP
    }
    for pattern in _CJK_ENTITY_PATTERNS:
        entities.update(pattern.findall(text))
    return entities


def has_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(
        re.search(r"\b" + re.escape(marker) + r"\b", lowered) is not None
        if marker.isascii() else marker in lowered
        for marker in markers
    )


def event_consistency_score(query: str, content: str) -> float:
    """Score explicit completion evidence for narrow event-list intents."""
    support_pattern = None
    if _PACKING_QUERY.search(query):
        support_pattern = _PACKING_SUPPORT
    elif _CONFIRM_QUERY.search(query):
        support_pattern = _CONFIRM_SUPPORT
    if support_pattern is None or _QUERY_NEGATION.search(query):
        return 0.0
    asks_about_self = (
        re.search(r"\b(?:I|me|my)\b", query, re.I) is not None
        and _OTHER_FIRST_PERSON.search(query) is None
    )
    if _EVENT_NEGATION.search(content) or (
        asks_about_self and _OTHER_FIRST_PERSON.search(content)
    ):
        return -8.0
    return 8.0 if support_pattern.search(content) else 0.0


@dataclass(frozen=True)
class RetrievalConfig:
    lexical_enabled: bool = True
    expansion_enabled: bool = True
    temporal_enabled: bool = True
    linkage_enabled: bool = True
    lexical_weight: float = 1.5
    dense_weight: float = 0.5

    def __post_init__(self) -> None:
        for weight in (self.lexical_weight, self.dense_weight):
            if not math.isfinite(weight) or weight <= 0:
                raise ValueError("RRF weights must be finite and positive; use channel switches to disable retrieval")


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
    expansions: list[str] = []
    for group in _CONCEPT_GROUPS:
        if has_marker(text, group):
            # Only add actual alternatives. Re-adding the query's own wording
            # would amplify lexical distractors instead of bridging paraphrases.
            alternatives = [
                phrase for phrase in group if not has_marker(text, (phrase,))
            ]
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


class RequestConflictError(ValueError):
    """An existing request ID was reused with different input."""


class MemoryStore:
    def __init__(
        self,
        path: str | Path,
        embedder: Encoder | bool | None = None,
        retrieval_config: RetrievalConfig | None = None,
    ):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._retrieval = retrieval_config or RetrievalConfig()
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
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            connection.close()
            raise
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
                """
                CREATE TABLE IF NOT EXISTS store_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS add_requests (
                    user_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    PRIMARY KEY (user_id, request_id)
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "embedding" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN embedding BLOB")
            self._verify_embedding_identity(connection)

    def _verify_embedding_identity(self, connection: sqlite3.Connection) -> None:
        if self._embedder is None:
            return
        identity = getattr(self._embedder, "index_identity", None)
        if not isinstance(identity, str) or not identity.strip():
            encoder_type = type(self._embedder)
            identity = f"python:{encoder_type.__module__}.{encoder_type.__qualname__}:implicit-v1"
        existing = connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'embedding_identity'"
        ).fetchone()
        has_vectors = connection.execute(
            "SELECT 1 FROM memories WHERE embedding IS NOT NULL LIMIT 1"
        ).fetchone() is not None
        if existing is None:
            if has_vectors:
                raise RuntimeError(
                    "stored embeddings have no verifiable embedding identity; rebuild the index"
                )
            connection.execute(
                "INSERT INTO store_metadata (key, value) VALUES ('embedding_identity', ?)",
                (identity,),
            )
        elif existing["value"] != identity:
            if has_vectors:
                raise RuntimeError(
                    "embedding identity does not match the persisted index; rebuild the index"
                )
            connection.execute(
                "UPDATE store_metadata SET value = ? WHERE key = 'embedding_identity'",
                (identity,),
            )

    def add(
        self,
        request_id: str,
        user_id: str,
        session_id: str,
        messages: Iterable[dict],
    ) -> None:
        message_values = list(messages)
        payload_hash = hashlib.sha256(
            json.dumps(
                {"session_id": session_id, "messages": message_values},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        # Fast path only: the transactional claim below still arbitrates races
        # between concurrent writers, including separate worker processes.
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT payload_hash FROM add_requests WHERE user_id = ? AND request_id = ?",
                (user_id, request_id),
            ).fetchone()
        if existing is not None:
            if existing["payload_hash"] != payload_hash:
                raise RequestConflictError("request_id was already used with a different payload")
            return
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
        if len(embeddings) != len(message_values):
            raise RuntimeError(
                "embedding backend returned a different number of vectors than messages"
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
                json.dumps(
                    [request_id, user_id, session_id, index, role, timestamp_ms, content],
                    ensure_ascii=False, separators=(",", ":"),
                ).encode("utf-8")
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
            # Legacy databases may contain memories without a payload ledger.
            # Their raw messages cannot be recovered from contextual display
            # text, so never guess equivalence or append a duplicate batch.
            legacy = connection.execute(
                "SELECT 1 FROM memories WHERE user_id = ? AND request_id = ? LIMIT 1",
                (user_id, request_id),
            ).fetchone()
            claim = connection.execute(
                """
                INSERT OR IGNORE INTO add_requests (user_id, request_id, payload_hash)
                VALUES (?, ?, ?)
                """,
                (user_id, request_id, payload_hash),
            )
            if claim.rowcount == 0:
                existing = connection.execute(
                    "SELECT payload_hash FROM add_requests WHERE user_id = ? AND request_id = ?",
                    (user_id, request_id),
                ).fetchone()
                if existing["payload_hash"] != payload_hash:
                    raise RequestConflictError(
                        "request_id was already used with a different payload"
                    )
                return
            if legacy is not None:
                raise RequestConflictError(
                    "legacy request_id exists without a verifiable payload; use a new request_id"
                )
            connection.executemany(
                """
                INSERT INTO memories
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
        config = self._retrieval
        expansion_terms = semantic_expansion_terms(query) if config.expansion_enabled else []
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

        memories = []
        for row in db_rows:
            embedding = None
            if row["embedding"] is not None:
                try:
                    embedding = np.frombuffer(row["embedding"], dtype=np.float32)
                except ValueError:
                    embedding = None
                if embedding is not None and not np.all(np.isfinite(embedding)):
                    # Embeddings are a rebuildable index. A partially corrupted
                    # vector must not poison ranking or JSON serialization; keep
                    # the durable text available through lexical retrieval.
                    embedding = None
            memories.append(Memory(
                id=row["id"], content=row["content"],
                timestamp_ms=row["timestamp_ms"], created_at=row["created_at"],
                terms=row["terms"].split(),
                embedding=embedding,
            ))
        document_frequency: dict[str, int] = {}
        for memory in memories:
            for term in set(memory.terms):
                document_frequency[term] = document_frequency.get(term, 0) + 1
        rare_query_identifiers = (
            {
                term
                for term in query_terms
                if _IDENTIFIER_TOKEN.fullmatch(term)
                and document_frequency.get(term, 0) <= 4
            }
            if config.lexical_enabled
            else set()
        )

        average_length = sum(len(memory.terms) for memory in memories) / len(memories)
        lexical_scores = []
        lexical_candidates = []
        newest_timestamp = max((memory.timestamp_ms or 0) for memory in memories)
        oldest_timestamp = min((memory.timestamp_ms or 0) for memory in memories)
        rank_timestamp = (
            (lambda memory: memory.timestamp_ms or 0)
            if config.temporal_enabled else (lambda memory: 0)
        )
        asks_for_current = has_marker(query, _CURRENT_MARKERS)
        temporal_ids: set[str] = set()
        if config.temporal_enabled and asks_for_current:
            query_topics = topic_terms(query)
            memory_topics = {memory.id: topic_terms(memory.content) for memory in memories}
            anchors = [memory for memory in memories if query_topics & memory_topics[memory.id]]
            temporal_ids = {memory.id for memory in anchors}
            earliest_anchor: dict[str, int] = {}
            for anchor in anchors:
                if anchor.timestamp_ms is not None:
                    for term in memory_topics[anchor.id]:
                        earliest_anchor[term] = min(
                            earliest_anchor.get(term, anchor.timestamp_ms), anchor.timestamp_ms
                        )
            # One-hop linkage only. An omitted topic needs an explicit shared
            # term and a known later timestamp; generic pronouns alone do not
            # establish that an update belongs to the queried subject.
            for memory in memories:
                if memory.timestamp_ms is None or not has_marker(memory.content, _UPDATE_MARKERS):
                    continue
                if any(
                    term in earliest_anchor and memory.timestamp_ms > earliest_anchor[term]
                    for term in memory_topics[memory.id]
                ):
                    temporal_ids.add(memory.id)
        # A total order makes ties independent of SQLite insertion order and
        # Python's randomized set iteration across worker processes.
        def rank_key(item):
            return (-item[0], -rank_timestamp(item[1]), item[1].id)

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
            score += event_consistency_score(query, memory.content)
            if memory.id in temporal_ids:
                if newest_timestamp > oldest_timestamp and memory.timestamp_ms is not None:
                    score += 0.4 * (
                        (memory.timestamp_ms - oldest_timestamp)
                        / (newest_timestamp - oldest_timestamp)
                    )
                if has_marker(memory.content, _UPDATE_MARKERS):
                    score += 10.0
            if config.lexical_enabled:
                lexical_candidates.append((score, memory))
                if score > 0:
                    lexical_scores.append((score, memory))

        lexical_scores.sort(key=rank_key)
        if config.lexical_enabled and config.linkage_enabled and lexical_scores:
            seeds = [lexical_scores[0][1]]
            seeds.extend(
                memory for _, memory in lexical_scores[1:5]
                if re.search(r"\b(?:is|are|was|were)\b", memory.content, re.I)
            )
            query_entities = entity_terms(query)
            seed_entities = {
                entity
                for seed in seeds
                for entity in entity_terms(seed.content) - query_entities
            }
            # If the seeds expose no proper-name bridge, linkage cannot change
            # any score. Avoid running several regexes over the entire user's
            # corpus on this common direct-retrieval path.
            if not seed_entities and not _CJK_RUN.search(query):
                return self._finish_search(
                    query, memories, lexical_scores, rank_key, config, top_k,
                    rare_query_identifiers,
                )
            entity_frequency: dict[str, int] = {}
            entities_by_id = {memory.id: entity_terms(memory.content) for memory in memories}
            for entities in entities_by_id.values():
                for entity in entities:
                    entity_frequency[entity] = entity_frequency.get(entity, 0) + 1

            def linked_ranking(
                candidates: list[tuple[float, Memory]], active_seeds: list[Memory]
            ) -> list[tuple[float, Memory]]:
                active_seed_ids = {seed.id for seed in active_seeds}
                bridge_terms = {
                    entity
                    for seed in active_seeds
                    for entity in entities_by_id[seed.id] - query_entities
                    if 1 < entity_frequency.get(entity, 0) <= 4
                }
                linked_scores = []
                for score, memory in candidates:
                    shared = bridge_terms & entities_by_id[memory.id]
                    if memory.id in active_seed_ids:
                        bridge_score = 4.0 if shared else 0.0
                    else:
                        bridge_score = min(
                            10.0,
                            sum(16.0 / entity_frequency[term] for term in shared),
                        )
                    if score + bridge_score > 0:
                        linked_scores.append((score + bridge_score, memory))
                return sorted(linked_scores, key=rank_key)

            lexical_scores = linked_ranking(lexical_candidates, seeds)
            # CJK text has no capitalization signal. A first linked result can
            # therefore reveal one additional named organization or courier.
            # Limit the second hop to ten seeds and CJK queries only. The wider
            # seed window is needed because a bridge statement can rank below
            # surface-form distractors before linkage is applied.
            if _CJK_RUN.search(query):
                lexical_scores = linked_ranking(
                    lexical_scores, [memory for _, memory in lexical_scores[:10]]
                )
        return self._finish_search(
            query, memories, lexical_scores, rank_key, config, top_k,
            rare_query_identifiers,
        )

    def _finish_search(
        self,
        query: str,
        memories: list[Memory],
        lexical_scores: list[tuple[float, Memory]],
        rank_key: Callable[[tuple[float, Memory]], tuple[float, int, str]],
        config: RetrievalConfig,
        top_k: int,
        rare_query_identifiers: set[str],
    ) -> list[dict]:
        if self._embedder is None or not any(memory.embedding is not None for memory in memories):
            scores = lexical_scores
        else:
            try:
                query_encoder = (
                    self._embedder.encode_query
                    if getattr(
                        self._embedder, "supports_query_priority", False
                    ) is True
                    else self._embedder.encode
                )
                encoded_query = query_encoder([query])
                query_vector = encoded_query[0]
                if not np.all(np.isfinite(query_vector)):
                    raise ValueError("embedding backend returned a non-finite query vector")
            except Exception:
                # Search remains useful when the rebuildable semantic channel is
                # temporarily unavailable. The durable lexical index is already
                # loaded and provides a deterministic degraded response.
                logger.warning(
                    "query embedding failed; falling back to lexical retrieval",
                    exc_info=True,
                )
                return self._results(lexical_scores, top_k)
            compatible_memories = [
                memory for memory in memories
                if memory.embedding is not None
                and memory.embedding.shape == query_vector.shape
            ]
            if not compatible_memories:
                return self._results(lexical_scores, top_k)
            dense_pairs: list[tuple[float, Memory]] = []
            for offset in range(0, len(compatible_memories), _DENSE_BATCH_SIZE):
                batch = compatible_memories[offset : offset + _DENSE_BATCH_SIZE]
                embedding_matrix = np.vstack([memory.embedding for memory in batch])
                dense_values = embedding_matrix @ query_vector
                dense_pairs.extend(
                    (float(value), memory)
                    for value, memory in zip(dense_values, batch)
                )
            dense_scores = sorted(
                dense_pairs,
                key=rank_key,
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
                    score += config.lexical_weight / (60 + lexical_ranks[memory_id])
                if memory_id in dense_ranks:
                    score += config.dense_weight / (60 + dense_ranks[memory_id])
                # Preserve strong temporal/update preferences established in the
                # lexical channel without letting raw BM25 scale dominate fusion.
                if config.lexical_weight > 0 and lexical_raw.get(memory_id, 0.0) >= 8.0:
                    score += 0.002
                # Dense models are intentionally weak at opaque identifiers.
                # Preserve an exact, low-frequency code match without boosting
                # ordinary words or broad CJK fragments across the whole rank.
                if (
                    rare_query_identifiers
                    and memory_id in lexical_ranks
                    and rare_query_identifiers.intersection(
                        memory_by_id[memory_id].terms
                    )
                ):
                    score += 0.01
                fused.append((score, memory_by_id[memory_id]))
            fused.sort(key=rank_key)
            scores = fused
        return self._results(scores, top_k)

    @staticmethod
    def _results(scores: list[tuple[float, Memory]], top_k: int) -> list[dict]:
        return [
            {
                "id": memory.id,
                "content": memory.content,
                "score": round(score, 6),
                "created_at": MemoryStore._source_time(memory),
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
        for term in sorted(set(query_terms)):
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
