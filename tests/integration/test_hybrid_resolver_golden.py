"""Golden-set integration coverage for HybridResolver.

This uses deterministic mocked sampling payloads. Real LLM accuracy tests can
live in a separate opt-in layer, but this pins the resolver contract and the
golden-set scoring harness in default CI.
"""

from __future__ import annotations

import pytest

from psim_mcp.intent.hybrid_resolver import HybridResolver
from psim_mcp.intent.resolver import IntentResolver, RegexResolver, build_legacy_resolution_dict
from psim_mcp.intent.sampling_resolver import _payload_to_intent_model, _rank_with_topology_hint


pytestmark = pytest.mark.integration


GOLDEN_SET = [
    (
        "12V input to 5V output step-down converter",
        {
            "input_domain": "dc",
            "output_domain": "dc",
            "conversion_goal": "step_down",
            "isolation": False,
            "values": {"vin": 12, "vout_target": 5},
            "topology_hint": "buck",
            "confidence": "high",
        },
        "buck",
        {"vin": 12.0, "vout_target": 5.0},
    ),
    (
        "5V to 12V boost supply",
        {
            "input_domain": "dc",
            "output_domain": "dc",
            "conversion_goal": "step_up",
            "isolation": False,
            "values": {"vin": 5, "vout_target": 12},
            "topology_hint": "boost",
            "confidence": "high",
        },
        "boost",
        {"vin": 5.0, "vout_target": 12.0},
    ),
    (
        "isolated 400V DC bus to 48V telecom supply",
        {
            "input_domain": "dc",
            "output_domain": "dc",
            "conversion_goal": "step_down",
            "isolation": True,
            "use_case": "telecom",
            "values": {"vin": 400, "vout_target": 48},
            "topology_hint": "forward",
            "confidence": "medium",
        },
        "forward",
        {"vin": 400.0, "vout_target": 48.0},
    ),
    (
        "LLC resonant converter 400V to 48V 1kW",
        {
            "input_domain": "dc",
            "output_domain": "dc",
            "conversion_goal": "step_down",
            "isolation": True,
            "values": {"vin": 400, "vout_target": 48, "power": 1000},
            "topology_hint": "llc",
            "confidence": "high",
        },
        "llc",
        {"vin": 400.0, "vout_target": 48.0, "power_rating": 1000.0},
    ),
    (
        "220V AC rectifier front end",
        {
            "input_domain": "ac",
            "output_domain": "dc",
            "conversion_goal": "rectification",
            "values": {"vin": 220},
            "topology_hint": "diode_bridge_rectifier",
            "confidence": "high",
        },
        "diode_bridge_rectifier",
        {"vin": 220.0},
    ),
    (
        "three phase inverter from 600V DC bus",
        {
            "input_domain": "dc",
            "output_domain": "ac",
            "conversion_goal": "inversion",
            "use_case": "motor_drive",
            "values": {"vin": 600},
            "topology_hint": "three_phase_inverter",
            "confidence": "high",
        },
        "three_phase_inverter",
        {"vin": 600.0},
    ),
    (
        "bidirectional 400V to 48V battery interface",
        {
            "input_domain": "dc",
            "output_domain": "dc",
            "bidirectional": True,
            "values": {"vin": 400, "vout_target": 48},
            "topology_hint": "bidirectional_buck_boost",
            "confidence": "high",
        },
        "bidirectional_buck_boost",
        {"vin": 400.0, "vout_target": 48.0},
    ),
    (
        "PV MPPT boost with Voc 40V Isc 10A",
        {
            "input_domain": "dc",
            "output_domain": "dc",
            "conversion_goal": "step_up",
            "use_case": "pv_frontend",
            "values": {"vin": 40, "iout": 10},
            "topology_hint": "pv_mppt_boost",
            "confidence": "high",
        },
        "pv_mppt_boost",
        {"vin": 40.0, "iout": 10.0},
    ),
]


class GoldenSamplingResolver(IntentResolver):
    def __init__(self, payloads: dict[str, dict]) -> None:
        self._payloads = payloads

    async def resolve(self, text: str, ctx=None):
        intent = _payload_to_intent_model(self._payloads[text], raw_text=text)
        candidates = _rank_with_topology_hint(intent)
        return build_legacy_resolution_dict(intent, candidates, "v2_sampling")


async def test_hybrid_resolver_golden_set_hits_80_percent():
    payloads = {text: payload for text, payload, _, _ in GOLDEN_SET}
    resolver = HybridResolver(
        sampling_resolver=GoldenSamplingResolver(payloads),
        fallback_resolver=RegexResolver(),
    )

    passes = 0
    for text, _, expected_topology, expected_values in GOLDEN_SET:
        result = await resolver.resolve(text)
        specs = result["normalized_specs"]
        topology_ok = result["topology"] == expected_topology
        values_ok = all(specs.get(field) == value for field, value in expected_values.items())
        passes += int(topology_ok and values_ok)

    assert passes / len(GOLDEN_SET) >= 0.8
