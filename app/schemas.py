"""Pydantic request/response models for the chat API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's chat message.")
    session_id: str | None = Field(
        default=None,
        description=(
            "Conversation identifier used to keep per-session chat history. "
            "Omit it to start a new conversation; the API generates a GUID "
            "and returns it, which you should pass on subsequent requests "
            "to continue that conversation."
        ),
    )


class ChatResponse(BaseModel):
    answer: str
    session_id: str
