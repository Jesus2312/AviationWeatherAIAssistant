"""LangChain tools that call the aviationweather.gov Data API.

Both tools take a 4-letter ICAO airport identifier (e.g. "KELP" for El Paso
International Airport). Resolving a human airport name/city to its ICAO code
is left to the LLM's own knowledge and is described in the agent's system
prompt -- these tools only handle the HTTP call and raw JSON pass-through.
"""

import json

import httpx
from langchain_core.tools import tool

from app.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.config import get_settings

_settings = get_settings()
_breaker = CircuitBreaker(
    "aviationweather.gov",
    failure_threshold=_settings.circuit_breaker_failure_threshold,
    reset_timeout=_settings.circuit_breaker_reset_timeout,
)

def get_breaker_state() -> str:
    """Current state of the aviationweather.gov circuit breaker (for /health)."""
    return _breaker.state


_UNAVAILABLE_MESSAGE = (
    "The aviationweather.gov service appears to be down right now (too many "
    "recent failures), so this tool is temporarily disabled to avoid hanging. "
    "Tell the user the weather service is unavailable and to try again in a "
    "little while."
)


async def _fetch(report_type: str, icao: str) -> list:
    settings = get_settings()
    url = f"{settings.aviationweather_base_url}/{report_type}"
    params = {"ids": icao.strip().upper(), "format": "json"}

    async def _get() -> list:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    return await _breaker.call(_get)


@tool
async def get_metar(icao: str) -> str:
    """Fetch the current METAR observation for an airport.

    Args:
        icao: The airport's 4-letter ICAO code (e.g. "KELP" for El Paso
            International Airport, "KJFK" for John F. Kennedy International).

    Returns the raw JSON from aviationweather.gov. The 'rawOb' field contains
    the raw METAR text that must be decoded for the user.
    """
    try:
        data = await _fetch("metar", icao)
    except CircuitBreakerOpenError:
        return _UNAVAILABLE_MESSAGE
    except Exception as e:
        return f"Error fetching METAR data: {e}"

    if not data:
        return (
            f"No METAR data found for ICAO code '{icao.strip().upper()}'. "
            "Double-check the airport identifier."
        )
    return json.dumps(data, indent=2)


@tool
async def get_taf(icao: str) -> str:
    """Fetch the current TAF (terminal aerodrome forecast) for an airport.

    Args:
        icao: The airport's 4-letter ICAO code (e.g. "KELP" for El Paso
            International Airport, "KJFK" for John F. Kennedy International).

    Returns the raw JSON from aviationweather.gov. The 'rawTAF' field contains
    the raw TAF text that must be decoded for the user.
    """
    try:
        data = await _fetch("taf", icao)
    except CircuitBreakerOpenError:
        return _UNAVAILABLE_MESSAGE
    except Exception as e:
        return f"Error fetching TAF data: {e}"

    if not data:
        return (
            f"No TAF data found for ICAO code '{icao.strip().upper()}'. "
            "Double-check the airport identifier."
        )
    return json.dumps(data, indent=2)
