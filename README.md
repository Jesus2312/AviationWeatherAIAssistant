# Aviation Weather Assistant

A FastAPI service exposing an LLM chat interface (via LangChain, using
OpenAI tool-calling) that answers questions about current METAR
observations and TAF forecasts for airports, by calling the
[aviationweather.gov](https://aviationweather.gov/api/data) data API and
decoding the raw report for the user.

## Features

- `POST /api/chat` — single request/response chat.
- `POST /api/chat/stream` — Server-Sent Events streaming chat.
- `POST /api/auth/login` — JWT login (demo single-user auth).
- LangChain tool-calling agent with `get_metar` / `get_taf` tools.
- Per-session conversation history (`session_id`), persisted in Redis.
- Circuit breakers around both external dependencies (aviationweather.gov
  and the LLM provider) so an outage fails fast instead of hanging.
- Optional request tracing via Langfuse.
- A React frontend (`frontend/`) — a chatgpt.com-style chat UI for this API.
  See [`frontend/README.md`](frontend/README.md).

## Prerequisites

- **Python 3.11+**
- **Redis 8+** (or Redis Stack) — plain Redis without the RediSearch/
  RedisJSON modules will **not** work; `langgraph-checkpoint-redis` needs
  them to index conversation checkpoints.
- An **OpenAI API key** (or an OpenAI-compatible endpoint, e.g. OpenRouter).
- **Node.js 18+** if you also want to build/run the frontend.
- **Docker** / **docker compose**, only if you're using the container path.

## 1. Configure environment variables

```powershell
copy .env.example .env
```

Then edit `.env`. The important ones:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | **Required.** Your OpenAI (or compatible provider) key. |
| `OPENAI_MODEL` | Model name, defaults to `gpt-4o-mini`. |
| `OPENAI_API_BASE` | Leave blank for api.openai.com, or point at another OpenAI-compatible base URL. |
| `REDIS_URL` | `redis://localhost:6379` for a local Redis; `redis://redis:6379` when run via docker compose. |
| `DEMO_USERNAME` / `DEMO_PASSWORD` | Credentials for the demo login (see [Authentication](#authentication) below). |
| `JWT_SECRET_KEY` | Change to a random value for anything beyond a local demo. |
| `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY` | Optional; leave both blank to disable tracing entirely (no-op). |

The full list with defaults is in `.env.example` / `app/config.py`.

## 2. Run it — pick one path

### Option A: Python virtual environment (fastest for local dev)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Start a local Redis 8 (the quickest way, if you don't already have one, is
via Docker even in this path):

```powershell
docker run -d --name redis -p 6379:6379 redis:8
```

Run the dev server:

```powershell
uvicorn app.main:app --reload
```

The API is now on `http://localhost:8000` (interactive docs at
`http://localhost:8000/docs`).

### Option B: Docker Compose (full stack: API + Redis + frontend)

```bash
docker compose up --build
```

This builds and starts:
- `api` — the FastAPI backend on `http://localhost:8000`.
- `redis` — a `redis:8` container with a named volume for persistence.
- `web` — the React frontend (built and served by nginx) on
  `http://localhost:3000`, proxying its own `/api/*` calls to `api`.

Environment variables are read from `.env` (`env_file:` in
`docker-compose.yml`); `REDIS_URL` is overridden inside compose to point at
the `redis` service. All three services have health checks, and `web`
waits for `api` to report healthy before starting.

To run only the backend + Redis (e.g. while iterating on the frontend with
`npm run dev` instead):

```bash
docker compose up --build api redis
```

### Option C: Kubernetes

See [`k8s/README.md`](k8s/README.md) for full manifests (Deployments,
Services, a Redis `StatefulSet`, Secret/ConfigMap templates, and an
optional Ingress) and step-by-step instructions for both:
- a cluster that can pull from a registry, and
- a fully local cluster (e.g. Kubernetes on a local VM) using images built
  on your machine, with no registry involved (`docker save` /
  `ctr images import` or `docker load`).

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`, proxying `/api/*` to `http://localhost:8000`
— start the backend first. See [`frontend/README.md`](frontend/README.md)
for build/preview commands and project structure.

## Authentication

The API issues JWTs for a single hardcoded demo user (`app/auth.py`,
credentials from `DEMO_USERNAME`/`DEMO_PASSWORD` in `.env`). Not designed to
scale past one user.

Log in to get a token:

```powershell
curl http://localhost:8000/api/auth/login -Method Post -ContentType "application/json" -Body '{"username": "admin", "password": "admin"}'
```

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

Response: `{"access_token": "<jwt>", "token_type": "bearer"}`. Pass it on
subsequent chat requests:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"message": "metar for KJFK", "session_id": "demo"}'
```

## Example requests

`session_id` is optional — omit it to start a new conversation; the API
generates a GUID and returns it (as `session_id` in the JSON response for
`/api/chat`, or as the first `{"session_id": ...}` SSE event for
`/api/chat/stream`). Pass it back on later requests to continue that
conversation.

Non-streaming:

```powershell
curl http://localhost:8000/api/chat -Method Post -ContentType "application/json" -Headers @{Authorization="Bearer <jwt>"} -Body '{"message": "please give me the metar information for el paso international airport", "session_id": "demo"}'
```

Streaming (SSE):

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"message": "what is the current metar for KJFK?", "session_id": "demo"}'
```

## Tests

```powershell
pytest
```

Tests never hit the real aviationweather.gov API — outbound HTTP is mocked
with `respx`. `tests/test_metar_deepeval.py` uses `deepeval` to grade the
LLM's actual decoded output quality; that one does call the real OpenAI
model configured in `.env`, so it needs a valid `OPENAI_API_KEY` and will
incur API usage.

## Health & observability

- `GET /health` — reports circuit breaker state for both external
  dependencies (aviationweather.gov and the LLM provider); returns 503 if
  either is tripped.
- If `LANGFUSE_SECRET_KEY`/`LANGFUSE_PUBLIC_KEY` are set, every request gets
  a Langfuse trace (`trace_id`/`trace_url` returned in the response) linking
  the LLM generations and the tool call under one span.

## Notes / limitations

- Airport-name-to-ICAO resolution relies on the LLM's own knowledge (set in
  the system prompt in `app/agent.py`); it is not backed by a lookup table.
- METAR/TAF decoding is also done by the LLM, not a hand-written parser.
- Conversation history is persisted in Redis (via
  `langgraph-checkpoint-redis`) and survives process restarts, keyed by
  `session_id`.
- Auth is a single hardcoded demo user — swap `app/auth.py` for a real user
  store before using this beyond a demo.

## Project layout

See [`CLAUDE.md`](CLAUDE.md) for the full architecture write-up (module
responsibilities, design decisions, and the reasoning behind them).
