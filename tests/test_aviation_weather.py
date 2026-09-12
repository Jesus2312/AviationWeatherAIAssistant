import json

import httpx
import pytest
import respx

from app.tools.aviation_weather import get_metar, get_taf


@pytest.mark.asyncio
@respx.mock
async def test_get_metar_success():
    sample = [
        {
            "icaoId": "KELP",
            "rawOb": "KELP 121953Z 00000KT 10SM CLR 28/09 A3005",
        }
    ]
    respx.get("https://aviationweather.gov/api/data/metar").mock(
        return_value=httpx.Response(200, json=sample)
    )

    result = await get_metar.ainvoke({"icao": "kelp"})

    data = json.loads(result)
    assert data[0]["icaoId"] == "KELP"
    assert "rawOb" in data[0]


@pytest.mark.asyncio
@respx.mock
async def test_get_metar_no_data():
    respx.get("https://aviationweather.gov/api/data/metar").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await get_metar.ainvoke({"icao": "zzzz"})

    assert "No METAR data found" in result


@pytest.mark.asyncio
@respx.mock
async def test_get_taf_success():
    sample = [{"icaoId": "KELP", "rawTAF": "TAF KELP 121740Z 1218/1324 00000KT P6SM SKC"}]
    respx.get("https://aviationweather.gov/api/data/taf").mock(
        return_value=httpx.Response(200, json=sample)
    )

    result = await get_taf.ainvoke({"icao": "kelp"})

    data = json.loads(result)
    assert data[0]["icaoId"] == "KELP"
    assert "rawTAF" in data[0]
