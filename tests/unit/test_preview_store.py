"""Tests for preview token store."""
from psim_mcp.services.preview_store import PreviewStore


def test_save_and_get():
    store = PreviewStore()
    token = store.save({"circuit_type": "buck", "components": []})
    assert isinstance(token, str)
    assert len(token) == 12
    data = store.get(token)
    assert data is not None
    assert data["circuit_type"] == "buck"


def test_delete():
    store = PreviewStore()
    token = store.save({"test": True})
    assert store.delete(token) is True
    assert store.get(token) is None
    assert store.delete(token) is False


def test_expired():
    from unittest.mock import patch

    fake_time = 1000.0
    with patch("psim_mcp.shared.state_store.time") as mock_time:
        mock_time.monotonic = lambda: fake_time
        store = PreviewStore(ttl=1)
        token = store.save({"test": True})

        # Advance time past the TTL
        fake_time = 1001.1
        mock_time.monotonic = lambda: fake_time

        assert store.get(token) is None


def test_multiple_tokens():
    store = PreviewStore()
    t1 = store.save({"type": "buck"})
    t2 = store.save({"type": "boost"})
    assert t1 != t2
    assert store.get(t1)["type"] == "buck"
    assert store.get(t2)["type"] == "boost"
