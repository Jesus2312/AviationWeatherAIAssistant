# CLAUDE.md

Guidance for Claude Code (or any future assistant) working in this repository.

## Project purpose

A FastAPI backend that provides an LLM chat interface for aviation METAR and
TAF weather information. A typical user (e.g. a student pilot) asks something
like "please give me the metar information for el paso international
airport"; the LLM resolves the airport to its ICAO code, calls a LangChain
tool that hits the aviationweather.gov data API, and then decodes the raw
METAR/TAF text (the `rawOb` / `rawTAF` field) into a plain-English
explanation alongside the raw code.

## Stack

- **FastAPI** for the HTTP API.
- **LangChain** (`langchain`, `langchain-openai`, `langchain-community`) for
  the tool-calling agent and conversation memory.
- **httpx** for the outbound calls to aviationweather.gov.
- **pydantic-settings** for config via environment variables / `.env`.
- **pytest** + **respx** for tests (HTTP calls are mocked, never live).
- **Docker** / **docker compose** for containerized runs.
- **Redis** (via `langgraph-checkpoint-redis`) for persistent, cross-process
  conversation memory.

## Architecture

```
app/
  main.py            FastAPI app, CORS, /health, mounts api router
  config.py           Settings (env vars, .env) via pydantic-settings
  schemas.py           ChatRequest / ChatResponse pydantic models
  agent.py             Builds the LangChain 1.x create_agent graph;
                       per-session memory via a LangGraph AsyncRedisSaver
                       checkpointer (thread_id == session_id), initialized
                       in main.py's lifespan handler
  api/routes.py         POST /api/chat (non-streaming)
                       POST /api/chat/stream (SSE streaming)
  tools/aviation_weather.py   get_metar / get_taf LangChain @tool functions
tests/                 pytest tests; aviationweather.gov calls mocked with respx
```

## Key design decisions

- **ICAO resolution is the LLM's job, not code's.** The tools (`get_metar`,
  `get_taf`) take a 4-letter ICAO code as their only argument. The system
  prompt in `app/agent.py` instructs the model to convert an airport
  name/city into its ICAO code using its own knowledge before calling a
  tool. There is no local airport-name lookup table by design — keep it that
  way unless the user asks for deterministic/offline resolution, since a
  lookup table adds a dataset to maintain for a case the LLM already
  handles well for major airports.
- **METAR/TAF decoding is done by the LLM**, not by a hand-written parser.
  The tools return the raw JSON from aviationweather.gov as-is; the system
  prompt tells the model to decode the raw report field by field. Don't add
  a manual METAR-parsing library unless asked — that would duplicate what
  the system prompt already asks the LLM to do.
- **Conversation memory is persisted in Redis** via a LangGraph
  `AsyncRedisSaver` checkpointer (`app/agent.py`), keyed by `thread_id` ==
  `session_id`. It survives process restarts and is shared across
  workers/instances that point at the same Redis. The checkpointer is
  opened once in `app/main.py`'s lifespan handler (`init_checkpointer` /
  `close_checkpointer`) rather than per-request; `build_agent()` raises if
  called before startup has run. Requires Redis 8+ (or Redis Stack) because
  `langgraph-checkpoint-redis` indexes checkpoints with RediSearch/RedisJSON
  — plain old Redis without those modules will not work. Configured via
  `REDIS_URL` (`app/config.py`); `docker-compose.yml` runs a `redis:8`
  service as a dependency of `api`.
- **Streaming** is implemented with `agent.astream_events(..., version="v2")`
  in `app/api/routes.py`, filtering for `on_chat_model_stream` events and
  forwarding non-empty `chunk.content` as SSE `data:` lines. Tool-call
  argument deltas are excluded automatically since those chunks have empty
  `content`.
- **LLM provider**: only OpenAI via `langchain-openai` `ChatOpenAI` is wired
  up (`OPENAI_API_KEY`, `OPENAI_MODEL` in `.env`). If another provider is
  ever needed, swap the `ChatOpenAI` construction in
  `app/agent.py:build_agent_executor`.

## Running things

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env   # then set OPENAI_API_KEY
uvicorn app.main:app --reload
pytest
```

Docker: `docker compose up --build` (reads `.env`).

## Conventions

- All I/O (HTTP calls, agent invocation) is async; keep new tools/routes
  async too.
- Tests must not hit the real aviationweather.gov API — mock with `respx`
  as in `tests/test_aviation_weather.py`.
- New LangChain tools go in `app/tools/`, one module per external API, and
  get added to the `_TOOLS` list in `app/agent.py`.
