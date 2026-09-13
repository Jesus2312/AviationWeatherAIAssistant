"""Application settings, loaded from environment variables / .env file."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# The langfuse SDK reads LANGFUSE_* directly from the process environment,
# not through this Settings class, so make sure .env actually lands there
# too (docker compose's `env_file:` already does this for containers).
load_dotenv()


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_api_base: str = ""
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.2

    aviationweather_base_url: str = "https://aviationweather.gov/api/data"

    redis_url: str = "redis://localhost:6379"

    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # Circuit breaker for calls to aviationweather.gov and the LLM provider:
    # trip open after this many consecutive failures, then fail fast for
    # this many seconds before testing recovery with a single trial call.
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_reset_timeout: float = 30.0

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_secret_key and self.langfuse_public_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
