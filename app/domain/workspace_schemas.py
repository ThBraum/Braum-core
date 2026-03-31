from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.schemas import ChatMode


class ConversationCreateRequest(BaseModel):
    mode: ChatMode = ChatMode.GENERAL
    title: str | None = None
    client_id: str | None = None
    access_token: str | None = None


class ChatSendRequest(BaseModel):
    content: str = Field(min_length=1)
    client_id: str | None = None
    access_token: str | None = None
    web_search_enabled: bool = False


class ConversationMessageDTO(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ConversationDTO(BaseModel):
    id: str
    title: str
    mode: ChatMode
    created_at: datetime
    updated_at: datetime


class FileDTO(BaseModel):
    id: str
    original_name: str
    category: str
    media_type: str
    created_at: datetime
    thumbnail: str


class ChatSendResponse(BaseModel):
    conversation_id: str
    answer: str
    mode: ChatMode
    requires_login: bool = False
    next_action: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    uploaded_files: list[FileDTO] = Field(default_factory=list)
