"""A minimal async circuit breaker for guarding calls to flaky external
services (aviationweather.gov, the LLM provider).

Without this, when a dependency goes down every request still waits out the
full connect/read timeout before failing -- under load that piles up
concurrent hung requests and makes the whole app feel stalled. Once a
service has failed `failure_threshold` times in a row, the breaker opens and
further calls fail immediately (no network wait) until `reset_timeout`
seconds have passed, at which point a single trial call is let through
(half-open) to test recovery.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Awaitable, Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerOpenError(Exception):
    """Raised in place of calling through when the breaker is open."""

    def __init__(self, name: str):
        super().__init__(f"{name!r} is currently unavailable (circuit breaker open)")
        self.name = name


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = _State.CLOSED
        self._failure_count = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state.value

    async def guard(self) -> None:
        """Raise CircuitBreakerOpenError if calls should be rejected right now."""
        async with self._lock:
            if self._state == _State.OPEN:
                if time.monotonic() - self._opened_at >= self.reset_timeout:
                    self._state = _State.HALF_OPEN
                    logger.info("Circuit breaker %r half-open: testing recovery.", self.name)
                else:
                    raise CircuitBreakerOpenError(self.name)

    async def record_success(self) -> None:
        async with self._lock:
            if self._state != _State.CLOSED:
                logger.info("Circuit breaker %r closed: recovered.", self.name)
            self._state = _State.CLOSED
            self._failure_count = 0

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._state == _State.HALF_OPEN or self._failure_count >= self.failure_threshold:
                if self._state != _State.OPEN:
                    logger.warning(
                        "Circuit breaker %r open after %d failure(s); failing fast for %.0fs.",
                        self.name,
                        self._failure_count,
                        self.reset_timeout,
                    )
                self._state = _State.OPEN
                self._opened_at = time.monotonic()

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Run `func` through the breaker: reject fast if open, otherwise
        call through and record the outcome."""
        await self.guard()
        try:
            result = await func(*args, **kwargs)
        except Exception:
            await self.record_failure()
            raise
        else:
            await self.record_success()
            return result


class CircuitBreakerTransport(httpx.AsyncBaseTransport):
    """An httpx transport that routes requests through a CircuitBreaker.

    Connection errors/timeouts and 5xx responses count as failures; 4xx
    responses (bad request, bad auth, etc.) do not -- those indicate a
    problem with the request, not an outage, so they shouldn't trip the
    breaker or block other requests.
    """

    def __init__(self, breaker: CircuitBreaker, wrapped: httpx.AsyncBaseTransport | None = None):
        self._breaker = breaker
        self._wrapped = wrapped or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await self._breaker.guard()
        try:
            response = await self._wrapped.handle_async_request(request)
        except Exception:
            await self._breaker.record_failure()
            raise
        if response.status_code >= 500:
            await self._breaker.record_failure()
        else:
            await self._breaker.record_success()
        return response

    async def aclose(self) -> None:
        await self._wrapped.aclose()
