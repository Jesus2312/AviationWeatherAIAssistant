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
    trace_id: str = Field(
        description="Unique identifier for this request/response, usable to "
        "look up its full trace (LLM calls, tool calls, timing) in Langfuse.",
    )
    trace_url: str | None = Field(
        default=None,
        description="Direct link to this request's trace in Langfuse, or "
        "null if Langfuse isn't configured.",
    )
