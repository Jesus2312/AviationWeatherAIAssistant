"""HTTP routes for the chat API (non-streaming and streaming)."""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent import build_agent, trace_request
from app.circuit_breaker import CircuitBreakerOpenError
from app.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

_UNAVAILABLE_DETAIL = "The assistant is temporarily unavailable. Please try again shortly."


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
    responses={
        503: {"description": "The LLM provider is unavailable."},
    },
)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    agent = build_agent()

    with trace_request(
        "POST /api/chat", session_id, {"message": request.message}
    ) as trace:
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": trace.callbacks,
            "metadata": {
                "langfuse_session_id": session_id,
                "langfuse_trace_name": "POST /api/chat",
            },
        }
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": request.message}]},
                config=config,
            )
        except CircuitBreakerOpenError as e:
            if trace.span:
                trace.span.update(level="ERROR", status_message=str(e))
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception:
            logger.exception("Chat request failed (session_id=%s)", session_id)
            if trace.span:
                trace.span.update(level="ERROR", status_message="unhandled exception")
            raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None

        answer = result["messages"][-1].content
        if trace.span:
            trace.span.update(output={"answer": answer})

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        trace_id=trace.trace_id,
        trace_url=trace.trace_url,
    )


@router.post(
    "/chat/stream",
    summary="Send a chat message (streamed)",
    description=(
        "Same as `/chat`, but streams the answer as it's generated via "
        "Server-Sent Events. The first event is a JSON object "
        "`{\"session_id\": ..., \"trace_id\": ..., \"trace_url\": ...}` "
        "(session_id generated if you didn't pass one); subsequent events "
        "are `{\"token\": ...}` chunks. If the LLM provider is unavailable, "
        "an `{\"error\": ...}` event is sent instead. The stream always "
        "ends with a `[DONE]` event."
    ),
    responses={
        200: {
            "description": "text/event-stream: a `{\"session_id\": str, "
            "\"trace_id\": str, \"trace_url\": str | null}` event, then "
            "`{\"token\": str}` chunks (or a `{\"error\": str}` event on "
            "failure), terminated by `[DONE]`.",
            "content": {"text/event-stream": {}},
        }
    },
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or str(uuid.uuid4())
    agent = build_agent()

    async def event_generator():
        # The trace span must stay open for the generator's whole lifetime
        # (it's iterated by Starlette after this function returns), so it's
        # opened here rather than in the route body -- ending it early would
        # close it before the streamed tool/LLM calls it should contain.
        with trace_request(
            "POST /api/chat/stream", session_id, {"message": request.message}
        ) as trace:
            yield (
                "data: "
                f"{json.dumps({'session_id': session_id, 'trace_id': trace.trace_id, 'trace_url': trace.trace_url})}"
                "\n\n"
            )
            config = {
                "configurable": {"thread_id": session_id},
                "callbacks": trace.callbacks,
                "metadata": {
                    "langfuse_session_id": session_id,
                    "langfuse_trace_name": "POST /api/chat/stream",
                },
            }
            answer_parts = []
            try:
                async for message_chunk, _metadata in agent.astream(
                    {"messages": [{"role": "user", "content": request.message}]},
                    config=config,
                    stream_mode="messages",
                ):
                    # Tool-call argument deltas have empty content; only
                    # forward actual answer text tokens from the model.
                    if getattr(message_chunk, "content", None):
                        answer_parts.append(message_chunk.content)
                        yield f"data: {json.dumps({'token': message_chunk.content})}\n\n"
            except CircuitBreakerOpenError as e:
                if trace.span:
                    trace.span.update(level="ERROR", status_message=str(e))
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            except Exception:
                logger.exception("Chat stream failed (session_id=%s)", session_id)
                if trace.span:
                    trace.span.update(level="ERROR", status_message="unhandled exception")
                yield f"data: {json.dumps({'error': _UNAVAILABLE_DETAIL})}\n\n"
            else:
                if trace.span:
                    trace.span.update(output={"answer": "".join(answer_parts)})
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
