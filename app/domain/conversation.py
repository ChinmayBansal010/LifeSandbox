from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Conversation(BaseModel):
    id: str
    user_id: str
    title: str
    messages: list[Message] = Field(default_factory=list)
    pending_question: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
