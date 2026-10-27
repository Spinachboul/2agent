from datetime import datetime, timezone
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
    referenced_ids: list[str] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    document_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    chat_history: list[ChatMessage] = Field(default_factory=list)
    last_referenced_requirement_id: str | None = None