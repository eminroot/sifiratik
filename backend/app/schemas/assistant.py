from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """One turn of the conversation, with everything before it for context."""

    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    period: str | None = None
    company_id: int | None = None


class ChatReply(BaseModel):
    reply: str
    model: str
    period: str


class AssistantStatus(BaseModel):
    enabled: bool
    model: str
    detail: str
