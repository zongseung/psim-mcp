"""Backward-compatible preview store.

The canonical state management implementation lives in
``psim_mcp.shared.state_store``.  This module re-exports a thin wrapper
so that existing code using ``get_preview_store()`` continues to work
without changes.
"""

from __future__ import annotations

from psim_mcp.shared.state_store import StateStore, get_state_store


# Type alias for code that references ``PreviewStore`` directly.
PreviewStore = StateStore


def get_preview_store() -> StateStore:
    """Return the default :class:`StateStore` singleton.

    Backward-compatible alias for ``get_state_store()``.
    """
    return get_state_store()
