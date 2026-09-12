"""Pydantic request/response models for the chat API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's chat message.")
    session_id: str = Field(
        default="default",
        description="Conversation identifier used to keep per-session chat history.",
    )


class ChatResponse(BaseModel):
    answer: str
    session_id: str
