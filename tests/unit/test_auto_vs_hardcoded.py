"""Comparison tests: auto_place vs hardcoded layout strategies.

Verifies that the algorithmic auto-layout produces results that are
structurally comparable to the existing hardcoded strategies.
"""

from __future__ import annotations

import pytest

from psim_mcp.layout.auto_placer import auto_place
from psim_mcp.layout.strategies._reference.buck import BuckLayoutStrategy
from psim_mcp.layout.strategies._reference.flyback import FlybackLayoutStrategy
from psim_mcp.layout.strategies._reference.llc import LlcLayoutStrategy
from psim_mcp.synthesis.topologies.buck import synthesize_buck
from psim_mcp.synthesis.topologies.flyback import synthesize_flyback
from psim_mcp.synthesis.topologies.llc import synthesize_llc


@pytest.fixture
def buck_graph():
    return synthesize_buck({"vin": 48, "vout_target": 12, "iout": 5, "fsw": 50000})


@pytest.fixture
def flyback_graph():
    return synthesize_flyback({"vin": 400, "vout_target": 12, "iout": 2, "fsw": 100000})


@pytest.fixture
def llc_graph():
    return synthesize_llc({"vin": 400, "vout_target": 48, "iout": 5, "fsw": 100000})


def test_buck_auto_vs_hardcoded_same_component_count(buck_graph):
    auto_layout = auto_place(buck_graph)
    hc_layout = BuckLayoutStrategy().build_layout(buck_graph)
    assert len(auto_layout.components) == len(hc_layout.components)


def test_buck_auto_vs_hardcoded_all_nonzero(buck_graph):
    auto_layout = auto_place(buck_graph)
    for comp in auto_layout.components:
        assert comp.x > 0 or comp.y > 0, f"{comp.id} has zero position"


def test_buck_auto_vs_hardcoded_power_flow_matches(buck_graph):
    """Both auto and hardcoded should have input x < output x."""
    auto_layout = auto_place(buck_graph)
    hc_layout = BuckLayoutStrategy().build_layout(buck_graph)

    auto_map = {c.id: c for c in auto_layout.components}
    hc_map = {c.id: c for c in hc_layout.components}

    # Auto: V1 left of R1
    assert auto_map["V1"].x < auto_map["R1"].x
    # Hardcoded: V1 left of R1
    assert hc_map["V1"].x < hc_map["R1"].x


def test_flyback_auto_vs_hardcoded_same_count(flyback_graph):
    auto_layout = auto_place(flyback_graph)
    hc_layout = FlybackLayoutStrategy().build_layout(flyback_graph)
    assert len(auto_layout.components) == len(hc_layout.components)


def test_flyback_auto_vs_hardcoded_power_flow(flyback_graph):
    auto_layout = auto_place(flyback_graph)
    auto_map = {c.id: c for c in auto_layout.components}
    # Input left of secondary output
    assert auto_map["V1"].x < auto_map["R1"].x


def test_llc_auto_vs_hardcoded_same_count(llc_graph):
    auto_layout = auto_place(llc_graph)
    hc_layout = LlcLayoutStrategy().build_layout(llc_graph)
    assert len(auto_layout.components) == len(hc_layout.components)


def test_llc_auto_vs_hardcoded_power_flow(llc_graph):
    auto_layout = auto_place(llc_graph)
    auto_map = {c.id: c for c in auto_layout.components}
    assert auto_map["V1"].x < auto_map["R1"].x
