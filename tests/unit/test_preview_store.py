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
    store = PreviewStore(ttl=0)  # immediate expiry
    import time
    token = store.save({"test": True})
    time.sleep(0.01)
    assert store.get(token) is None


def test_multiple_tokens():
    store = PreviewStore()
    t1 = store.save({"type": "buck"})
    t2 = store.save({"type": "boost"})
    assert t1 != t2
    assert store.get(t1)["type"] == "buck"
    assert store.get(t2)["type"] == "boost"
