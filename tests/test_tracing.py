import pytest

from app.agent import trace_request
from app.config import get_settings


@pytest.fixture
def no_langfuse(monkeypatch):
    """Force settings.langfuse_enabled False regardless of the real .env,
    so this test is hermetic and never touches the network."""
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_trace_request_noops_without_langfuse_configured(no_langfuse):
    with trace_request("test-op", "session-1", {"message": "hi"}) as trace:
        assert trace.span is None
        assert trace.callbacks == []
        assert trace.trace_url is None
        assert trace.trace_id  # still a unique id the caller can return


def test_trace_request_ids_are_unique(no_langfuse):
    with trace_request("test-op", "session-1", {"message": "hi"}) as trace_a:
        pass
    with trace_request("test-op", "session-1", {"message": "hi"}) as trace_b:
        pass
    assert trace_a.trace_id != trace_b.trace_id
