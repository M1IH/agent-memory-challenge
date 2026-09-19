from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .store import MemoryStore, PayloadTooLargeError, RequestConflictError


logger = logging.getLogger(__name__)


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Reject oversized API payloads before JSON parsing allocates more memory."""

    def __init__(self, app: Any, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError("AML_MAX_REQUEST_BYTES must be a positive integer")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in {"/add", "/search"}
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", ()))
        raw_content_length = headers.get(b"content-length")
        if raw_content_length is not None:
            try:
                content_length = int(raw_content_length)
            except ValueError:
                content_length = None
            if content_length is not None and content_length > self.max_bytes:
                await self._send_too_large(scope, send)
                return

        received_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await self._send_too_large(scope, send)

    @staticmethod
    async def _send_too_large(
        scope: dict[str, Any],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body exceeds the configured byte limit"},
        )

        async def disconnected() -> dict[str, str]:
            return {"type": "http.disconnect"}

        await response(scope, disconnected, send)


def configured_max_request_bytes() -> int:
    raw_value = os.getenv("AML_MAX_REQUEST_BYTES", "2000000")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("AML_MAX_REQUEST_BYTES must be a positive integer") from exc
    if value <= 0:
        raise ValueError("AML_MAX_REQUEST_BYTES must be a positive integer")
    return value


def configured_api_key() -> str | None:
    for variable in ("AML_API_KEY", "API_KEY"):
        value = os.getenv(variable)
        if value is not None and value.strip():
            return value
    return None


def validate_api_key_configuration() -> None:
    raw_required = os.getenv("AML_LOCKDOWN", "false").strip().lower()
    if raw_required not in {"true", "false"}:
        raise ValueError("AML_LOCKDOWN must be true or false")
    if raw_required == "true" and configured_api_key() is None:
        raise ValueError(
            "AML_API_KEY or API_KEY must be set when AML_LOCKDOWN=true"
        )


class Message(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=100_000)
    timestamp: int | None = None

    @field_validator("role")
    @classmethod
    def role_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("role must not be blank")
        return value

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_representable(cls, value: int | None) -> int | None:
        if value is not None:
            try:
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            except (OverflowError, OSError, ValueError) as exc:
                raise ValueError("timestamp is outside the supported range") from exc
        return value


class AddRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=512)
    messages: list[Message] = Field(min_length=1, max_length=1000)
    user_id: str = Field(min_length=1, max_length=512)
    session_id: str = Field(min_length=1, max_length=512)

    @field_validator("request_id", "user_id", "session_id")
    @classmethod
    def identifiers_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier must not be blank")
        return value


class AddResponse(BaseModel):
    success: bool
    request_id: str
    user_id: str
    session_id: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=100_000)
    options: list[str] | None = Field(default=None, max_length=1000)
    user_id: str = Field(min_length=1, max_length=512)
    top_k: int = Field(ge=1, le=1000)

    @field_validator("query", "user_id")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("options")
    @classmethod
    def options_must_not_contain_blank_values(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is not None and any(not option.strip() for option in value):
            raise ValueError("options must not contain blank values")
        return value


class SearchResult(BaseModel):
    id: str
    content: str
    score: float | None = None
    created_at: str | None = None


class SearchResponse(BaseModel):
    data: list[SearchResult]


def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
) -> None:
    expected = configured_api_key()
    if not expected:
        return
    candidates = [x_api_key or ""]
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() in {"bearer", "token"}:
            candidates.append(credential)
    if not any(secrets.compare_digest(candidate, expected) for candidate in candidates):
        raise HTTPException(status_code=401, detail="Invalid API key")


validate_api_key_configuration()
app = FastAPI(title="AML Memory Entry", version="0.1.0")
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_bytes=configured_max_request_bytes(),
)
store = MemoryStore(os.getenv("AML_DB_PATH", "data/memory.db"))


@app.exception_handler(sqlite3.Error)
async def storage_error_response(_request: Request, exc: sqlite3.Error) -> JSONResponse:
    logger.error("storage operation failed (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "Storage temporarily unavailable"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    store.check_health()
    return {"status": "ok"}


@app.post("/add", response_model=AddResponse, dependencies=[Depends(require_api_key)])
def add_memory(request: AddRequest) -> AddResponse:
    try:
        store.add(
            request_id=request.request_id,
            user_id=request.user_id,
            session_id=request.session_id,
            messages=[message.model_dump() for message in request.messages],
        )
    except RequestConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PayloadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return AddResponse(
        success=True,
        request_id=request.request_id,
        user_id=request.user_id,
        session_id=request.session_id,
    )


@app.post("/search", response_model=SearchResponse, dependencies=[Depends(require_api_key)])
def search_memory(request: SearchRequest) -> SearchResponse:
    try:
        return SearchResponse(
            data=store.search(
                user_id=request.user_id,
                query=request.query,
                options=request.options,
                top_k=request.top_k,
            )
        )
    except PayloadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
