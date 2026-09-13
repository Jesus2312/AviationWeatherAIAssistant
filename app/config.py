"""Application settings, loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_api_base: str = ""
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.2

    aviationweather_base_url: str = "https://aviationweather.gov/api/data"

    redis_url: str = "redis://localhost:6379"

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
