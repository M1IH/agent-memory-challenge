from __future__ import annotations

import os
import secrets
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .store import MemoryStore


class Message(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1)
    timestamp: int | None = None


class AddRequest(BaseModel):
    request_id: str = Field(min_length=1)
    messages: list[Message] = Field(min_length=1)
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class AddResponse(BaseModel):
    success: bool
    request_id: str
    user_id: str
    session_id: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    options: list[str] | None = None
    user_id: str = Field(min_length=1)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/add", response_model=AddResponse, dependencies=[Depends(require_api_key)])
def add_memory(request: AddRequest) -> AddResponse:
    store.add(
        request_id=request.request_id,
        user_id=request.user_id,
        session_id=request.session_id,
        messages=[message.model_dump() for message in request.messages],
    )
    return AddResponse(
        success=True,
        request_id=request.request_id,
        user_id=request.user_id,
        session_id=request.session_id,
    )


@app.post("/search", response_model=SearchResponse, dependencies=[Depends(require_api_key)])
def search_memory(request: SearchRequest) -> SearchResponse:
    return SearchResponse(
        data=store.search(
            user_id=request.user_id,
            query=request.query,
            options=request.options,
            top_k=request.top_k,
        )
    )
