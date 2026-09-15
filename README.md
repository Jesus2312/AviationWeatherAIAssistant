# Aviation METAR/TAF Chat API

A FastAPI service exposing an LLM chat interface (via LangChain, using
OpenAI tool-calling) that answers questions about current METAR
observations and TAF forecasts for airports, by calling the
[aviationweather.gov](https://aviationweather.gov/api/data) data API and
decoding the raw report for the user.

## Features

- `POST /api/chat` — single request/response chat.
- `POST /api/chat/stream` — Server-Sent Events streaming chat.
- LangChain tool-calling agent with `get_metar` / `get_taf` tools.
- Per-session conversation history (`session_id`), persisted in Redis.
- A React frontend (`frontend/`) — a chatgpt.com-style chat UI for this API.
  See [`frontend/README.md`](frontend/README.md).

## Local setup (Python virtual environment)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
# edit .env and set OPENAI_API_KEY
```

You also need a Redis 8+ (or Redis Stack) instance for conversation memory
— plain old Redis without the RediSearch/RedisJSON modules will not work.
`REDIS_URL` in `.env` defaults to `redis://localhost:6379`; the quickest way
to get one locally is `docker compose up -d redis`.

Run the dev server:

```powershell
uvicorn app.main:app --reload
```

Run tests:

```powershell
pytest
```

## Example requests

`session_id` is optional — omit it to start a new conversation; the API
generates a GUID and returns it (as `session_id` in the JSON response for
`/api/chat`, or as the first `{"session_id": ...}` SSE event for
`/api/chat/stream`). Pass it back on later requests to continue that
conversation.

Non-streaming:

```powershell
curl http://localhost:8000/api/chat -Method Post -ContentType "application/json" -Body '{"message": "please give me the metar information for el paso international airport", "session_id": "demo"}'
```

Streaming (SSE):

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "what is the current metar for KJFK?", "session_id": "demo"}'
```

## Docker

```bash
docker compose up --build
```

This starts a `redis:8` container the API depends on for conversation
memory, and a `web` container serving the React frontend (built with nginx)
on `http://localhost:3000`, proxying its own `/api/*` calls to the `api`
service. The API itself is available at `http://localhost:8000`.
Environment variables are read from `.env` (see `.env.example`); when run
via compose, `REDIS_URL` is overridden to point at the `redis` service.

## Notes / limitations

- Airport-name-to-ICAO resolution relies on the LLM's own knowledge (set in
  the system prompt in `app/agent.py`); it is not backed by a lookup table.
- Conversation history is persisted in Redis (via
  `langgraph-checkpoint-redis`) and survives process restarts, keyed by
  `session_id`.
