"""LangChain tools that call the aviationweather.gov Data API.

Both tools take a 4-letter ICAO airport identifier (e.g. "KELP" for El Paso
International Airport). Resolving a human airport name/city to its ICAO code
is left to the LLM's own knowledge and is described in the agent's system
prompt -- these tools only handle the HTTP call and raw JSON pass-through.
"""

import json

import httpx
from langchain_core.tools import tool

from app.config import get_settings


@tool
async def get_metar(icao: str) -> str:
    """Fetch the current METAR observation for an airport.

    Args:
        icao: The airport's 4-letter ICAO code (e.g. "KELP" for El Paso
            International Airport, "KJFK" for John F. Kennedy International).

    Returns the raw JSON from aviationweather.gov. The 'rawOb' field contains
    the raw METAR text that must be decoded for the user.
    """
    settings = get_settings()
    url = f"{settings.aviationweather_base_url}/metar"
    params = {"ids": icao.strip().upper(), "format": "json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        
        if not data:
                return (
                    f"No METAR data found for ICAO code '{icao.strip().upper()}'. "
                    "Double-check the airport identifier."
                )

        return json.dumps(data, indent=2)        
    except Exception as e:
        return f"Error fetching METAR data: {e}"    


@tool
async def get_taf(icao: str) -> str:
    """Fetch the current TAF (terminal aerodrome forecast) for an airport.

    Args:
        icao: The airport's 4-letter ICAO code (e.g. "KELP" for El Paso
            International Airport, "KJFK" for John F. Kennedy International).

    Returns the raw JSON from aviationweather.gov. The 'rawTAF' field contains
    the raw TAF text that must be decoded for the user.
    """
    settings = get_settings()
    url = f"{settings.aviationweather_base_url}/taf"
    params = {"ids": icao.strip().upper(), "format": "json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    if not data:
        return (
            f"No TAF data found for ICAO code '{icao.strip().upper()}'. "
            "Double-check the airport identifier."
        )
    return json.dumps(data, indent=2)
