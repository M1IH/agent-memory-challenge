"""Offline Add segmentation for testing one directional context boundary."""

from __future__ import annotations

from app.store import MemoryStore


def add_memory(
    store: MemoryStore, *, request_id: str, user_id: str, session_id: str,
    messages: list[dict], mode: str = "native",
) -> None:
    if mode == "native":
        store.add(
            request_id=request_id, user_id=user_id,
            session_id=session_id, messages=messages,
        )
        return
    if mode != "no_assistant_to_user":
        raise ValueError(f"unknown context mode: {mode}")
    parts: list[list[dict]] = []
    current: list[dict] = []
    for message in messages:
        if current and current[-1]["role"] == "assistant" and message["role"] == "user":
            parts.append(current)
            current = []
        current.append(message)
    if current:
        parts.append(current)
    for index, part in enumerate(parts):
        store.add(
            request_id=f"{request_id}:part:{index}", user_id=user_id,
            session_id=session_id, messages=part,
        )
