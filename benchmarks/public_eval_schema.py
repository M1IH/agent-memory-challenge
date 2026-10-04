"""Normalized, source-grounded cases for public end-to-end memory evaluation.

Adapters may translate public datasets into this shape, but must not repair or
rewrite reference answers.  The normalized file keeps provenance so every
reported score can be traced back to a licensed source record.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ALLOWED_SPLITS = {"development", "frozen_holdout"}
ALLOWED_SCORERS = {"multiple_choice", "exact_match", "token_f1", "official"}
ALLOWED_ROLES = {"user", "assistant", "system", "tool"}


class CaseValidationError(ValueError):
    """Raised when an adapter emits an unsafe or ambiguous evaluation case."""


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseValidationError(f"{field} must be a nonempty string")
    return value


def validate_case(case: dict[str, Any]) -> None:
    """Validate one normalized case without mutating it."""

    if not isinstance(case, dict):
        raise CaseValidationError("case must be an object")
    required_strings = (
        "case_id",
        "dataset",
        "dataset_version",
        "source_record_id",
        "license",
        "split",
        "language",
        "question",
        "scorer",
    )
    for field in required_strings:
        _nonempty_string(case.get(field), field)
    if case["split"] not in ALLOWED_SPLITS:
        raise CaseValidationError(f"split must be one of {sorted(ALLOWED_SPLITS)}")
    if case["scorer"] not in ALLOWED_SCORERS:
        raise CaseValidationError(f"scorer must be one of {sorted(ALLOWED_SCORERS)}")

    capabilities = case.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(not isinstance(item, str) or not item.strip() for item in capabilities)
        or len(set(capabilities)) != len(capabilities)
    ):
        raise CaseValidationError("capabilities must contain unique nonempty strings")

    memories = case.get("memories")
    if not isinstance(memories, list) or not memories:
        raise CaseValidationError("memories must be a nonempty list")
    memory_ids: list[str] = []
    for index, memory in enumerate(memories):
        if not isinstance(memory, dict):
            raise CaseValidationError(f"memories[{index}] must be an object")
        memory_ids.append(_nonempty_string(memory.get("memory_id"), f"memories[{index}].memory_id"))
        _nonempty_string(memory.get("content"), f"memories[{index}].content")
        role = memory.get("role", "user")
        if role not in ALLOWED_ROLES:
            raise CaseValidationError(f"memories[{index}].role is unsupported")
        timestamp = memory.get("timestamp")
        if timestamp is not None and (not isinstance(timestamp, int) or isinstance(timestamp, bool)):
            raise CaseValidationError(f"memories[{index}].timestamp must be an integer or null")
    if len(memory_ids) != len(set(memory_ids)):
        raise CaseValidationError("memory_id values must be unique within a case")

    evidence_ids = case.get("evidence_memory_ids")
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or any(not isinstance(item, str) or not item for item in evidence_ids)
        or len(evidence_ids) != len(set(evidence_ids))
        or not set(evidence_ids) <= set(memory_ids)
    ):
        raise CaseValidationError("evidence_memory_ids must be unique known memory IDs")

    answers = case.get("reference_answers")
    if (
        not isinstance(answers, list)
        or not answers
        or any(not isinstance(item, str) or not item.strip() for item in answers)
    ):
        raise CaseValidationError("reference_answers must be a nonempty list of strings")

    choices = case.get("choices")
    if case["scorer"] == "multiple_choice":
        if (
            not isinstance(choices, list)
            or len(choices) < 2
            or any(not isinstance(item, str) or not item.strip() for item in choices)
        ):
            raise CaseValidationError("multiple_choice cases require at least two choices")
        if not any(answer in choices for answer in answers):
            raise CaseValidationError("a multiple-choice reference answer must match a choice")
    elif choices is not None:
        raise CaseValidationError("choices are only valid for multiple_choice cases")

    query_time = case.get("query_time")
    if query_time is not None and (not isinstance(query_time, int) or isinstance(query_time, bool)):
        raise CaseValidationError("query_time must be an integer or null")
    scorer_ref = case.get("official_scorer")
    if case["scorer"] == "official":
        _nonempty_string(scorer_ref, "official_scorer")
    elif scorer_ref is not None:
        raise CaseValidationError("official_scorer is only valid with the official scorer")


def validate_suite(document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise CaseValidationError("suite must be an object")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise CaseValidationError(f"schema_version must equal {SCHEMA_VERSION}")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CaseValidationError("suite cases must be a nonempty list")
    seen: set[str] = set()
    for case in cases:
        validate_case(case)
        if case["case_id"] in seen:
            raise CaseValidationError("case_id values must be unique within a suite")
        seen.add(case["case_id"])


def load_suite(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    document = json.loads(raw)
    validate_suite(document)
    document["file_sha256"] = hashlib.sha256(raw).hexdigest()
    return document

