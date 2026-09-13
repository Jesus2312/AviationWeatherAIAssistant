"""HTTP routes for the chat API (non-streaming and streaming)."""

import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent import build_agent, get_langfuse_callbacks
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a chat message",
    description=(
        "Send a message to the METAR/TAF weather assistant and get a "
        "complete response. Pass `session_id` to keep conversation history "
        "across calls; omit it to start a new conversation and receive a "
        "generated `session_id` to reuse."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    agent = build_agent()
    config = {
        "configurable": {"thread_id": session_id},
        "callbacks": get_langfuse_callbacks(),
        "metadata": {"langfuse_session_id": session_id},
    }
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": request.message}]},
        config=config,
    )
    answer = result["messages"][-1].content
    return ChatResponse(answer=answer, session_id=session_id)


@router.post(
    "/chat/stream",
    summary="Send a chat message (streamed)",
    description=(
        "Same as `/chat`, but streams the answer as it's generated via "
        "Server-Sent Events. The first event is a JSON object "
        "`{\"session_id\": ...}` (generated if you didn't pass one); "
        "subsequent events are `{\"token\": ...}` chunks, and the stream "
        "ends with a `[DONE]` event."
    ),
    responses={
        200: {
            "description": "text/event-stream: a `{\"session_id\": str}` "
            "event, then `{\"token\": str}` chunks, terminated by `[DONE]`.",
            "content": {"text/event-stream": {}},
        }
    },
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or str(uuid.uuid4())
    agent = build_agent()
    config = {
        "configurable": {"thread_id": session_id},
        "callbacks": get_langfuse_callbacks(),
        "metadata": {"langfuse_session_id": session_id},
    }

    async def event_generator():
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"
        async for message_chunk, _metadata in agent.astream(
            {"messages": [{"role": "user", "content": request.message}]},
            config=config,
            stream_mode="messages",
        ):
            # Tool-call argument deltas have empty content; only forward
            # actual answer text tokens from the model.
            if getattr(message_chunk, "content", None):
                yield f"data: {json.dumps({'token': message_chunk.content})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
