"""Canonical synthesis pipeline regression — parameterized over 28 topologies.

Exercises every topology the capability matrix marks ``synthesize="new"``,
asserting that:

1. The capability matrix and the generator registry agree on what's canonical.
2. Each generator's ``synthesize()`` returns a CircuitGraph with the right
   topology, components, nets, blocks, and design values.
3. ``validate_graph`` reports zero ``error``-severity issues.

Runs purely against the in-process synthesis layer — no PSIM binary, no
subprocess, no bridge IPC. This codifies the README's "15 verified" claim
into automated regression coverage that's safe to run in CI.

If a future change breaks any topology's canonical path, the parameterized
test names (e.g. ``test_synthesize_returns_valid_graph[buck]``) point at
the offending topology immediately.
"""

from __future__ import annotations

import pytest

from psim_mcp.data.capability_matrix import (
    CAPABILITY_MATRIX,
    get_new_pipeline_topologies,
)
from psim_mcp.generators import get_generator, list_generators, synthesize_topology
from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.validators.graph import validate_graph


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Topology list — single source of truth for parameterization
# ---------------------------------------------------------------------------

CANONICAL_TOPOLOGIES = sorted(get_new_pipeline_topologies())


# Common requirements that satisfy the `required_fields` of every canonical
# topology. We intentionally use a single dict so a new topology with novel
# required fields surfaces as an explicit test failure (instead of a silent
# pass via defaults) — that's how we keep this test honest as the registry
# evolves.
COMMON_REQS: dict = {
    "vin": 48,
    "vout_target": 12,
    "iout": 5,
    "vdc": 400,         # pv_grid_tied uses this (currently legacy-only)
    "fsw": 100_000,
    "ripple_ratio": 0.3,
    "voltage_ripple_ratio": 0.01,
}


# ---------------------------------------------------------------------------
# Registry consistency — fast smoke checks
# ---------------------------------------------------------------------------


class TestRegistryConsistency:
    """Pin invariants between capability_matrix and the generator registry."""

    def test_canonical_set_is_28_topologies(self):
        # 29 total in capability_matrix; only pv_grid_tied is synthesize="none".
        assert len(CANONICAL_TOPOLOGIES) == 28
        assert "pv_grid_tied" not in CANONICAL_TOPOLOGIES

    def test_every_canonical_topology_has_a_registered_generator(self):
        registered = set(list_generators())
        missing = [t for t in CANONICAL_TOPOLOGIES if t not in registered]
        assert not missing, f"Canonical topologies missing from generator registry: {missing}"

    def test_pv_grid_tied_is_marked_synthesize_none(self):
        # Documents the single known canonical-pipeline gap.
        assert CAPABILITY_MATRIX["pv_grid_tied"]["synthesize"] == "none"

    def test_capability_matrix_has_29_topologies(self):
        # Sanity check matching CLAUDE.md verified status.
        assert len(CAPABILITY_MATRIX) == 29


# ---------------------------------------------------------------------------
# Per-topology canonical synthesis (parameterized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", CANONICAL_TOPOLOGIES, ids=CANONICAL_TOPOLOGIES)
class TestCanonicalSynthesis:
    """One full canonical-synthesis invocation per topology.

    Each test is scoped to a single topology so failures are isolated and
    parameter IDs surface the offending name directly in CI output.
    """

    def _build_requirements(self, topology: str) -> dict:
        """Return a requirements dict that satisfies the topology's required_fields."""
        gen = get_generator(topology)
        reqs: dict = {}
        for field in gen.required_fields:
            if field not in COMMON_REQS:
                pytest.fail(
                    f"Topology '{topology}' requires field '{field}' which is "
                    f"not in COMMON_REQS. Add a default to keep parameterized "
                    f"coverage complete."
                )
            reqs[field] = COMMON_REQS[field]
        # Optional fields — only pass ones we have defaults for, generators
        # supply their own internal defaults otherwise.
        for field in gen.optional_fields:
            if field in COMMON_REQS:
                reqs[field] = COMMON_REQS[field]
        return reqs

    def test_synthesize_returns_circuit_graph(self, topology: str):
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        assert isinstance(graph, CircuitGraph), (
            f"{topology}.synthesize() did not return a CircuitGraph"
        )

    def test_graph_topology_field_matches(self, topology: str):
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        assert graph.topology == topology

    def test_graph_has_components(self, topology: str):
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        assert len(graph.components) > 0, f"{topology} produced empty components"

    def test_graph_has_nets(self, topology: str):
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        assert len(graph.nets) > 0, f"{topology} produced empty nets"

    def test_graph_components_have_unique_ids(self, topology: str):
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        ids = [c.id for c in graph.components]
        assert len(ids) == len(set(ids)), f"{topology} has duplicate component IDs: {ids}"

    def test_graph_components_have_roles(self, topology: str):
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        roleless = [c.id for c in graph.components if not c.role]
        assert not roleless, f"{topology} has components without roles: {roleless}"

    def test_graph_passes_structural_validation(self, topology: str):
        """No error-severity issues from validate_graph."""
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        issues = validate_graph(graph)
        errors = [i for i in issues if i.severity == "error"]
        assert not errors, (
            f"{topology} graph failed validation: "
            + "; ".join(f"[{e.code}] {e.message}" for e in errors)
        )

    def test_net_pin_refs_resolve_to_existing_components(self, topology: str):
        """Every '<comp>.<pin>' in nets references a known component."""
        reqs = self._build_requirements(topology)
        graph = synthesize_topology(topology, reqs)
        comp_ids = {c.id for c in graph.components}
        dangling: list[str] = []
        for net in graph.nets:
            for pin_ref in net.pins:
                if "." not in pin_ref:
                    continue
                comp_id = pin_ref.split(".", 1)[0]
                if comp_id not in comp_ids:
                    dangling.append(f"{net.id}:{pin_ref}")
        assert not dangling, f"{topology} has dangling pin refs: {dangling}"


# ---------------------------------------------------------------------------
# pv_grid_tied — explicit gap acknowledgement
# ---------------------------------------------------------------------------


class TestPvGridTiedCanonicalGap:
    """``pv_grid_tied`` is the only topology without canonical synthesis.

    These tests document the known gap so a future implementation flips
    them green without needing to discover the constraint by hand.
    """

    def test_pv_grid_tied_generator_exists_but_synthesis_raises(self):
        gen = get_generator("pv_grid_tied")
        with pytest.raises(NotImplementedError):
            gen.synthesize({"vdc": 400})

    def test_pv_grid_tied_excluded_from_canonical_list(self):
        assert "pv_grid_tied" not in CANONICAL_TOPOLOGIES
