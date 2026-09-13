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
- **Langfuse** (`langfuse`) for per-request LLM/tool call tracing, optional
  (no-ops if unconfigured).

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
  circuit_breaker.py    CircuitBreaker + CircuitBreakerTransport (httpx),
                       shared by the aviationweather.gov tools and the LLM
                       provider client
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
- **Streaming** is implemented with `agent.astream(..., stream_mode="messages")`
  in `app/api/routes.py`, forwarding non-empty `chunk.content` as SSE
  `data:` lines. Tool-call argument deltas are excluded automatically since
  those chunks have empty `content`.
- **LLM provider**: only OpenAI-compatible via `langchain-openai`
  `ChatOpenAI` is wired up (`OPENAI_API_KEY`, `OPENAI_MODEL`,
  `OPENAI_API_BASE` in `.env`). If another provider is ever needed, swap the
  `ChatOpenAI` construction in `app/agent.py:build_agent`.
- **Circuit breakers** (`app/circuit_breaker.py`) guard both external
  dependencies so an outage fails fast instead of piling up hung requests:
  one wraps the aviationweather.gov tool calls (`app/tools/aviation_weather.py`),
  the other wraps every LLM provider call via a shared `httpx.AsyncClient`
  passed as `ChatOpenAI(http_async_client=...)` in `app/agent.py` — this
  covers `ainvoke`/`astream`/tool-calling round trips regardless of which
  LangGraph code path triggers them, since they all funnel through that one
  HTTP transport. Tripped state is surfaced at `GET /health` and via
  `CircuitBreakerOpenError` → HTTP 503 (or an `{"error": ...}` SSE event for
  `/chat/stream`) in `app/api/routes.py`. Tunable via
  `CIRCUIT_BREAKER_FAILURE_THRESHOLD` / `CIRCUIT_BREAKER_RESET_TIMEOUT`.
- **Request tracing** (`app/agent.py:trace_request`) opens one root Langfuse
  span per HTTP request — covering arrival at the route handler through to
  the response — via `Langfuse.start_as_current_observation` with an
  explicitly generated `trace_id`. Both `/chat` and `/chat/stream`
  (`app/api/routes.py`) wrap their whole body in `with trace_request(...) as
  trace:` and pass `trace.callbacks` into the agent's `config["callbacks"]`;
  every LLM generation and tool call the request triggers nests under that
  span, so e.g. the aviationweather.gov call's latency and each LLM call's
  latency show up as separate child observations under one `trace_id` in
  Langfuse. The `trace_id`/`trace_url` are returned to the caller (JSON body
  for `/chat`, first SSE event for `/chat/stream`) as the request's
  correlation id. **Important**: the LangChain `CallbackHandler` is
  constructed with an explicit `trace_context={"trace_id":...,
  "parent_span_id": span.id}` rather than relying on ambient OTel context —
  LangGraph's async execution doesn't reliably propagate that context, a
  known langfuse/langgraph limitation (verified live before landing this;
  don't "simplify" it back to ambient-context propagation). No-ops entirely
  (empty callbacks, `trace.span is None`) when Langfuse isn't configured.
  The streaming endpoint opens the span *inside* `event_generator()`, not in
  the route body — the generator outlives the route function's return, so
  opening it outside would close the span before streaming even starts.

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
- Any new outbound call to an external service that the app depends on at
  request time should go through a `CircuitBreaker` (see
  `app/circuit_breaker.py`), the same way the aviationweather.gov tools and
  the LLM client do — don't let a new dependency reintroduce the
  hung-request problem the breakers exist to prevent.
