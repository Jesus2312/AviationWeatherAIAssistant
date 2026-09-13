"""LangChain tool-calling agent for the aviation weather chat assistant.

Built with LangChain 1.x's `create_agent` (a thin wrapper around a LangGraph
agent graph). Per-session conversation memory is provided by a LangGraph
Redis checkpointer, keyed by `thread_id` (== our `session_id`), so history
survives process restarts and is shared across workers/instances.
"""

from contextlib import AsyncExitStack

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from app.config import get_settings
from app.tools.aviation_weather import get_metar, get_taf

SYSTEM_PROMPT = """You are an aviation weather assistant for pilots and \
aviation students. You answer questions about current METAR observations and \
TAF forecasts.

When a user names an airport (by name, city, or code), first determine its \
4-letter ICAO identifier using your own aviation knowledge (e.g. "El Paso \
International Airport" -> "KELP", "JFK" -> "KJFK"). If you are not confident \
of the ICAO code, ask the user to confirm or provide it.

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
    )
    return create_agent(
        model=llm,
        tools=_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=_checkpointer,
    )
