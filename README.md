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
- Per-session in-memory conversation history (`session_id`).

## Local setup (Python virtual environment)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
# edit .env and set OPENAI_API_KEY
```

Run the dev server:

```powershell
uvicorn app.main:app --reload
```

Run tests:

```powershell
pytest
```

## Example requests

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

The API will be available at `http://localhost:8000`. Environment variables
are read from `.env` (see `.env.example`).

## Notes / limitations

- Airport-name-to-ICAO resolution relies on the LLM's own knowledge (set in
  the system prompt in `app/agent.py`); it is not backed by a lookup table.
- Conversation history is kept in-memory per process and is lost on
  restart — fine for a demo/student project, not for production.
