"""HTTP routes for the chat API (non-streaming and streaming)."""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent import build_agent
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a chat message",
    description=(
        "Send a message to the METAR/TAF weather assistant and get a "
        "complete response. Use `session_id` to keep conversation history "
        "across calls."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    agent = build_agent()
    config = {"configurable": {"thread_id": request.session_id}}
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": request.message}]},
        config=config,
    )
    answer = result["messages"][-1].content
    return ChatResponse(answer=answer, session_id=request.session_id)


@router.post(
    "/chat/stream",
    summary="Send a chat message (streamed)",
    description=(
        "Same as `/chat`, but streams the answer as it's generated via "
        "Server-Sent Events. Each event is a JSON object `{\"token\": ...}`; "
        "the stream ends with a `[DONE]` event."
    ),
    responses={
        200: {
            "description": "text/event-stream of `{\"token\": str}` chunks, "
            "terminated by `[DONE]`.",
            "content": {"text/event-stream": {}},
        }
    },
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    agent = build_agent()
    config = {"configurable": {"thread_id": request.session_id}}

    async def event_generator():
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
