"""LangChain tool-calling agent for the aviation weather chat assistant.

Built with LangChain 1.x's `create_agent` (a thin wrapper around a LangGraph
agent graph). Per-session conversation memory is provided by a LangGraph
Redis checkpointer, keyed by `thread_id` (== our `session_id`), so history
survives process restarts and is shared across workers/instances.
"""

import logging
import uuid
from contextlib import AsyncExitStack, contextmanager
from typing import Any, Iterator, NamedTuple

import httpx
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from app.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerTransport,
    SyncCircuitBreaker,
    SyncCircuitBreakerTransport,
)
from app.config import get_settings
from app.tools.aviation_weather import get_metar, get_taf

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an aviation weather assistant for pilots and \
aviation students. You answer questions about current METAR observations and \
TAF forecasts.

When a user names an airport (by name, city, or code), first determine its \
4-letter ICAO identifier using your own aviation knowledge (e.g. "El Paso \
International Airport" -> "KELP", "JFK" -> "KJFK").

If no ICAO code found on user request, please ask user to provide it and confirm it. \
Do not Invent ICAO codes. \

Use the get_metar tool for current conditions and the get_taf tool for \
forecasts. Never guess weather data yourself -- always call the appropriate \
tool.

The tool result is raw JSON from aviationweather.gov. Its 'rawOb' (METAR) or \
'rawTAF' (TAF) field holds the raw coded report. In your answer:
1. Show the raw code as-is.
2. Decode it in plain English, field by field (report time, wind, \
visibility, weather phenomena, sky condition/ceiling, temperature and \
dewpoint, altimeter setting, and any remarks).
Keep the explanation clear and approachable for a student pilot.
"""

_TOOLS = [get_metar, get_taf]

# Set up in the FastAPI lifespan (see app.main) and shared across requests
# for the lifetime of the process: LangGraph's Redis-backed checkpointer,
# partitioned by thread_id (== session_id).
_checkpointer: AsyncRedisSaver | None = None
_checkpointer_stack: AsyncExitStack | None = None

# Circuit breaker for the LLM provider, wired in via a shared httpx client
# so every call the OpenAI SDK makes -- ainvoke, astream, tool-calling
# round trips -- goes through it regardless of which LangGraph code path
# triggers it. Module-level/shared so the connection pool is reused across
# requests and the breaker's failure count is process-wide, not per-call.
_settings = get_settings()
_llm_breaker = CircuitBreaker(
    "llm-provider",
    failure_threshold=_settings.circuit_breaker_failure_threshold,
    reset_timeout=_settings.circuit_breaker_reset_timeout,
)
_llm_http_client = httpx.AsyncClient(
    transport=CircuitBreakerTransport(_llm_breaker),
    timeout=30.0,
)


async def close_llm_http_client() -> None:
    """Close the shared LLM HTTP client. Call once at shutdown."""
    await _llm_http_client.aclose()


def get_llm_breaker_state() -> str:
    """Current state of the LLM provider circuit breaker (for /health)."""
    return _llm_breaker.state


# Circuit breaker for Langfuse. Langfuse's SDK makes its own HTTP calls
# (prompt/dataset/score APIs, span export) through an internal *sync*
# httpx.Client, so this uses the sync breaker variant rather than the async
# one used for the LLM provider above. Guarding matters here because,
# without it, an unreachable/misconfigured Langfuse host can hang or raise
# out of trace_request() below -- and since that call wraps the whole
# request in app/api/routes.py, a Langfuse outage would otherwise take
# down /chat and /chat/stream too, not just tracing.
_langfuse_breaker = SyncCircuitBreaker(
    "langfuse",
    failure_threshold=_settings.circuit_breaker_failure_threshold,
    reset_timeout=_settings.circuit_breaker_reset_timeout,
)
_langfuse_client: Langfuse | None = None


def get_langfuse_breaker_state() -> str:
    """Current state of the Langfuse circuit breaker (for /health)."""
    return _langfuse_breaker.state


def _get_langfuse_client() -> Langfuse:
    """Build (once) our own Langfuse client with its internal httpx.Client
    routed through the circuit breaker above, instead of `langfuse.get_client()`,
    which builds an unguarded one from the environment."""
    global _langfuse_client
    if _langfuse_client is None:
        settings = get_settings()
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            httpx_client=httpx.Client(
                transport=SyncCircuitBreakerTransport(_langfuse_breaker),
                timeout=5.0,
            ),
        )
    return _langfuse_client


async def init_checkpointer() -> None:
    """Open the Redis connection and create indices. Call once at startup."""
    global _checkpointer, _checkpointer_stack
    settings = get_settings()
    stack = AsyncExitStack()
    _checkpointer = await stack.enter_async_context(
        AsyncRedisSaver.from_conn_string(settings.redis_url)
    )
    await _checkpointer.asetup()
    _checkpointer_stack = stack


async def close_checkpointer() -> None:
    """Close the Redis connection. Call once at shutdown."""
    global _checkpointer, _checkpointer_stack
    if _checkpointer_stack is not None:
        await _checkpointer_stack.aclose()
    _checkpointer = None
    _checkpointer_stack = None


class RequestTrace(NamedTuple):
    """What a route needs to tie one HTTP request to one Langfuse trace."""

    trace_id: str
    trace_url: str | None
    callbacks: list
    span: Any | None  # langfuse._client.span.LangfuseSpan, or None if disabled


@contextmanager
def trace_request(
    name: str, session_id: str, request_input: dict
) -> Iterator[RequestTrace]:
    """Open one root Langfuse span covering a single HTTP request end to
    end -- from arrival at the route handler to the response being built.

    Every LLM generation and tool call the request triggers (via
    `config["callbacks"] = trace.callbacks` on the agent invocation) nests
    under this span as a child, so the whole call tree -- including how
    long the aviationweather.gov call and the LLM call each took -- shows
    up under one `trace_id` in the Langfuse UI.

    No-ops (yields a random id, no callbacks, no span) if Langfuse isn't
    configured, or if the Langfuse circuit breaker is open or trips during
    setup -- a Langfuse outage should never take the chat request down with
    it, it should just mean this one request goes untraced.
    """
    settings = get_settings()
    if not settings.langfuse_enabled:
        yield RequestTrace(trace_id=str(uuid.uuid4()), trace_url=None, callbacks=[], span=None)
        return

    try:
        _langfuse_breaker.guard()
        client = _get_langfuse_client()
        trace_id = client.create_trace_id()
        span_cm = client.start_as_current_observation(
            trace_context={"trace_id": trace_id},
            name=name,
            as_type="span",
            input=request_input,
            metadata={"langfuse_session_id": session_id},
        )
        span = span_cm.__enter__()
    except Exception:
        # SyncCircuitBreakerTransport already recorded the underlying HTTP
        # failure (if any) against _langfuse_breaker; a CircuitBreakerOpenError
        # from guard() above needs no further recording.
        logger.warning("Langfuse trace setup failed; continuing without tracing.", exc_info=True)
        yield RequestTrace(trace_id=str(uuid.uuid4()), trace_url=None, callbacks=[], span=None)
        return

    try:
        # Explicit trace_context (trace_id + parent_span_id) is required here:
        # LangGraph's async execution doesn't reliably propagate the ambient
        # OTel context set up by start_as_current_observation above (a known
        # langfuse/langgraph limitation), so without this the model/tool
        # spans below would land as a *separate* top-level trace instead of
        # nesting under `span`.
        handler = CallbackHandler(
            trace_context={"trace_id": trace_id, "parent_span_id": span.id}
        )
        try:
            # get_trace_url() calls Langfuse's /projects API on its first
            # invocation (to resolve the project id, then caches it) --
            # a real network round trip, not just local string formatting.
            # Best-effort: a request should never fail just because the
            # trace URL couldn't be resolved.
            trace_url = client.get_trace_url(trace_id=trace_id)
        except Exception:
            logger.warning("Langfuse get_trace_url failed; omitting trace_url.", exc_info=True)
            trace_url = None
        yield RequestTrace(
            trace_id=trace_id,
            trace_url=trace_url,
            callbacks=[handler],
            span=span,
        )
    finally:
        span_cm.__exit__(None, None, None)


def flush_langfuse() -> None:
    """Flush any pending Langfuse trace exports and close its HTTP client.
    Call on app shutdown."""
    settings = get_settings()
    if settings.langfuse_enabled and _langfuse_client is not None:
        _langfuse_client.flush()
        _langfuse_client.shutdown()


def build_agent():
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialized; call init_checkpointer() at "
            "app startup before building the agent."
        )
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.temperature,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base or None,
        streaming=True,
        http_async_client=_llm_http_client,
    )
    return create_agent(
        model=llm,
        tools=_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=_checkpointer,
    )
