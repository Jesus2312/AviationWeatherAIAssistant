"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.agent import close_checkpointer, flush_langfuse, init_checkpointer
from app.api.routes import router

tags_metadata = [
    {
        "name": "chat",
        "description": "LLM chat endpoints for asking about METAR/TAF weather reports.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_checkpointer()
    yield
    flush_langfuse()
    await close_checkpointer()


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

app.include_router(router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["health"], summary="Health check")
async def health() -> dict:
    return {"status": "ok"}
