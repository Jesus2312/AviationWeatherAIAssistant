"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.agent import (
    close_checkpointer,
    close_llm_http_client,
    flush_langfuse,
    get_langfuse_breaker_state,
    get_llm_breaker_state,
    init_checkpointer,
)
from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.tools.aviation_weather import get_breaker_state as get_weather_breaker_state

tags_metadata = [
    {
        "name": "chat",
        "description": "LLM chat endpoints for asking about METAR/TAF weather reports.",
    },
    {
        "name": "auth",
        "description": "Login endpoint issuing JWTs for the demo user.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_checkpointer()
    yield
    flush_langfuse()
    await close_checkpointer()
    await close_llm_http_client()


app = FastAPI(
    title="Aviation METAR/TAF Chat API",
    description=(
        "LLM-powered chat API that answers questions about current METAR "
        "and TAF aviation weather reports, using LangChain tool calling "
        "against aviationweather.gov."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["health"], summary="Health check")
async def health() -> dict:
    return {
        "status": "ok",
        "circuit_breakers": {
            "aviationweather.gov": get_weather_breaker_state(),
            "llm_provider": get_llm_breaker_state(),
            "langfuse": get_langfuse_breaker_state(),
        },
    }
