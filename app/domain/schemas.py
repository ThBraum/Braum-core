from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatMode(str, Enum):
    GENERAL = "general"
    RAG = "rag"
    SQL = "sql"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: ChatMode = ChatMode.GENERAL
    session_id: str | None = None
    access_token: str | None = None
    sql_query: str | None = None


class ChatResponse(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    mode: ChatMode
    answer: str
    requires_login: bool = False
    next_action: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
