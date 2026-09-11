from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .store import MemoryStore, PayloadTooLargeError, RequestConflictError


logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=100_000)
    timestamp: int | None = None

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
    expected = os.getenv("AML_API_KEY") or os.getenv("API_KEY")
    if not expected:
        return
    candidates = [x_api_key or ""]
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() in {"bearer", "token"}:
            candidates.append(credential)
    if not any(secrets.compare_digest(candidate, expected) for candidate in candidates):
        raise HTTPException(status_code=401, detail="Invalid API key")


app = FastAPI(title="AML Memory Entry", version="0.1.0")
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
