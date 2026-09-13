import asyncio

import httpx
import pytest

from app.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerTransport,
)


class _Boom(Exception):
    pass


async def _fail():
    raise _Boom("nope")


async def _ok():
    return "ok"


@pytest.mark.asyncio
async def test_closed_by_default():
    breaker = CircuitBreaker("svc", failure_threshold=3, reset_timeout=30)
    assert breaker.state == "closed"
    assert await breaker.call(_ok) == "ok"
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_opens_after_threshold_failures():
    breaker = CircuitBreaker("svc", failure_threshold=3, reset_timeout=30)
    for _ in range(3):
        with pytest.raises(_Boom):
            await breaker.call(_fail)
    assert breaker.state == "open"


@pytest.mark.asyncio
async def test_open_breaker_fails_fast_without_calling_through():
    breaker = CircuitBreaker("svc", failure_threshold=1, reset_timeout=30)
    with pytest.raises(_Boom):
        await breaker.call(_fail)
    assert breaker.state == "open"

    calls = 0

    async def _would_succeed():
        nonlocal calls
        calls += 1
        return "ok"

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(_would_succeed)
    assert calls == 0


@pytest.mark.asyncio
async def test_half_open_recovers_on_success_after_reset_timeout():
    breaker = CircuitBreaker("svc", failure_threshold=1, reset_timeout=0.05)
    with pytest.raises(_Boom):
        await breaker.call(_fail)
    assert breaker.state == "open"

    await asyncio.sleep(0.1)

    assert await breaker.call(_ok) == "ok"
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_half_open_reopens_on_failure():
    breaker = CircuitBreaker("svc", failure_threshold=1, reset_timeout=0.05)
    with pytest.raises(_Boom):
        await breaker.call(_fail)

    await asyncio.sleep(0.1)

    with pytest.raises(_Boom):
        await breaker.call(_fail)
    assert breaker.state == "open"


@pytest.mark.asyncio
async def test_transport_trips_on_connection_error():
    class _RaisingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.ConnectError("connection refused", request=request)

    breaker = CircuitBreaker("svc", failure_threshold=1, reset_timeout=30)
    transport = CircuitBreakerTransport(breaker, _RaisingTransport())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("/x")
        assert breaker.state == "open"

        with pytest.raises(CircuitBreakerOpenError):
            await client.get("/x")


@pytest.mark.asyncio
async def test_transport_trips_on_5xx_but_not_4xx():
    class _StatusTransport(httpx.AsyncBaseTransport):
        def __init__(self, status: int):
            self.status = status

        async def handle_async_request(self, request):
            return httpx.Response(self.status, request=request)

    breaker = CircuitBreaker("svc", failure_threshold=1, reset_timeout=30)

    # 4xx should not trip the breaker.
    transport_4xx = CircuitBreakerTransport(breaker, _StatusTransport(404))
    async with httpx.AsyncClient(transport=transport_4xx, base_url="http://test") as client:
        response = await client.get("/x")
        assert response.status_code == 404
    assert breaker.state == "closed"

    # 5xx should.
    transport_5xx = CircuitBreakerTransport(breaker, _StatusTransport(500))
    async with httpx.AsyncClient(transport=transport_5xx, base_url="http://test") as client:
        response = await client.get("/x")
        assert response.status_code == 500
    assert breaker.state == "open"
