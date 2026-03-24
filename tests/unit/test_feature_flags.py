"""Unit tests for feature flag behavior in config and circuit design service."""

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.services.circuit_design_service import (
    CircuitDesignService,
    _SYNTHESIS_PIPELINE_AVAILABLE,
)


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


# --- Config parsing ---

def test_empty_enabled_list_means_all_allowed(mock_adapter):
    """Empty psim_synthesis_enabled_topologies means all topologies are allowed."""
    config = AppConfig(psim_mode="mock", psim_synthesis_enabled_topologies=[])
    service = CircuitDesignService(adapter=mock_adapter, config=config)
    assert service._is_synthesis_enabled_for_topology("buck") is _SYNTHESIS_PIPELINE_AVAILABLE
    assert service._is_synthesis_enabled_for_topology("flyback") is _SYNTHESIS_PIPELINE_AVAILABLE


def test_specific_topology_in_list_allowed(mock_adapter):
    """Only topologies in the list should be allowed."""
    config = AppConfig(
        psim_mode="mock",
        psim_synthesis_enabled_topologies=["buck", "boost"],
    )
    service = CircuitDesignService(adapter=mock_adapter, config=config)
    if _SYNTHESIS_PIPELINE_AVAILABLE:
        assert service._is_synthesis_enabled_for_topology("buck") is True
        assert service._is_synthesis_enabled_for_topology("boost") is True


def test_topology_not_in_list_rejected(mock_adapter):
    """Topology not in the enabled list should be rejected."""
    config = AppConfig(
        psim_mode="mock",
        psim_synthesis_enabled_topologies=["buck"],
    )
    service = CircuitDesignService(adapter=mock_adapter, config=config)
    assert service._is_synthesis_enabled_for_topology("flyback") is False


def test_intent_v2_flag_off_uses_legacy(mock_adapter):
    """When psim_intent_pipeline_v2 is False, V2 intent should not be used."""
    config = AppConfig(psim_mode="mock", psim_intent_pipeline_v2=False)
    service = CircuitDesignService(adapter=mock_adapter, config=config)
    assert service._is_intent_v2_enabled() is False


def test_intent_v2_flag_on_default(mock_adapter):
    """Default config has psim_intent_pipeline_v2=True."""
    config = AppConfig(psim_mode="mock")
    service = CircuitDesignService(adapter=mock_adapter, config=config)
    # V2 is enabled only if the v2 module is importable AND flag is True
    from psim_mcp.services.circuit_design_service import _INTENT_V2_AVAILABLE
    assert service._is_intent_v2_enabled() == _INTENT_V2_AVAILABLE


def test_new_flag_fields_parse_from_csv():
    """New list flags should parse from comma-separated strings."""
    config = AppConfig(
        psim_mode="mock",
        psim_graph_enabled_topologies="buck,boost",
        psim_layout_engine_enabled_topologies="buck",
        psim_routing_enabled_topologies="",
    )
    assert config.psim_graph_enabled_topologies == ["buck", "boost"]
    assert config.psim_layout_engine_enabled_topologies == ["buck"]
    assert config.psim_routing_enabled_topologies == []


def test_new_flag_fields_default_empty():
    """New list flags default to empty list."""
    config = AppConfig(psim_mode="mock")
    assert config.psim_graph_enabled_topologies == []
    assert config.psim_layout_engine_enabled_topologies == []
    assert config.psim_routing_enabled_topologies == []
