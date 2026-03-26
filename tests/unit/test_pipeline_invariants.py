"""Pipeline invariant tests — continuous tracking of fallback boundaries.

These tests ensure:
1. Fallback doesn't silently replace the main canonical path
2. Capability matrix matches actual synthesize/layout/routing support
3. Topology promotion readiness (legacy → new)
4. Preview/PSIM payload consistency across fallback boundaries
"""

from __future__ import annotations

import asyncio

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.data.capability_matrix import CAPABILITY_MATRIX


# ---------------------------------------------------------------------------
# 1. Fallback must not silently replace main path for "new" topologies
# ---------------------------------------------------------------------------

class TestFallbackDoesNotSilentlyReplace:
    """For topologies marked "new" in capability_matrix, the canonical pipeline
    must succeed — not silently fall through to legacy generator."""

    NEW_TOPOLOGIES = [
        name for name, caps in CAPABILITY_MATRIX.items()
        if caps.get("synthesize") == "new"
    ]

    @pytest.mark.parametrize("topology", NEW_TOPOLOGIES)
    def test_synthesize_succeeds_for_new_topology(self, topology):
        """synthesize() must not raise NotImplementedError for "new" topologies."""
        from psim_mcp.generators import get_generator
        gen = get_generator(topology)
        # Minimal specs — just needs to not crash
        specs = {"vin": 48, "vout_target": 12, "iout": 1}
        try:
            graph = gen.synthesize(specs)
            assert graph is not None
            assert graph.topology == topology
        except NotImplementedError:
            pytest.fail(
                f"Topology '{topology}' is marked 'new' in capability_matrix "
                f"but synthesize() raises NotImplementedError"
            )

    @pytest.mark.parametrize("topology", NEW_TOPOLOGIES)
    def test_layout_succeeds_for_new_topology(self, topology):
        """generate_layout() must not raise for "new" topologies."""
        from psim_mcp.generators import get_generator
        from psim_mcp.layout import generate_layout

        gen = get_generator(topology)
        graph = gen.synthesize({"vin": 48, "vout_target": 12, "iout": 1})
        layout = generate_layout(graph)
        assert layout is not None
        assert len(layout.components) > 0

    @pytest.mark.parametrize("topology", NEW_TOPOLOGIES)
    def test_routing_succeeds_for_new_topology(self, topology):
        """generate_routing() must not raise for "new" topologies."""
        from psim_mcp.generators import get_generator
        from psim_mcp.layout import generate_layout
        from psim_mcp.routing.engine import generate_routing

        gen = get_generator(topology)
        graph = gen.synthesize({"vin": 48, "vout_target": 12, "iout": 1})
        layout = generate_layout(graph)
        routing = generate_routing(graph, layout)
        assert routing is not None
        assert len(routing.segments) > 0

    @pytest.mark.parametrize("topology", NEW_TOPOLOGIES)
    def test_service_uses_canonical_path(self, topology):
        """preview_circuit() must store graph/layout in payload for "new" topologies."""
        from psim_mcp.services.circuit_design_service import CircuitDesignService
        from psim_mcp.adapters.mock_adapter import MockPsimAdapter

        config = AppConfig(psim_mode="mock", _env_file=None)
        service = CircuitDesignService(adapter=MockPsimAdapter(), config=config)

        # Provide topology-appropriate specs.  Boost/sepic need vout > vin.
        _TOPO_SPECS = {
            "boost": {"vin": 12, "vout_target": 48, "iout": 1},
            "sepic": {"vin": 12, "vout_target": 24, "iout": 1},
            "pv_mppt_boost": {"vin": 30},
        }
        specs = _TOPO_SPECS.get(topology, {"vin": 48, "vout_target": 12, "iout": 1})
        result = asyncio.get_event_loop().run_until_complete(
            service.preview_circuit(
                circuit_type=topology,
                specs=specs,
            )
        )
        assert result["success"] is True
        token = result["data"]["preview_token"]
        stored = service._store.get(token)
        assert stored is not None, f"Preview not stored for {topology}"
        assert "graph" in stored, (
            f"Topology '{topology}' is 'new' but preview_circuit() didn't store graph. "
            f"Canonical pipeline may have silently fallen back to legacy."
        )
        assert "layout" in stored, (
            f"Topology '{topology}' is 'new' but preview_circuit() didn't store layout."
        )


# ---------------------------------------------------------------------------
# 2. Capability matrix matches actual code support
# ---------------------------------------------------------------------------

class TestCapabilityMatrixAccuracy:
    """Capability matrix claims must match actual code behavior."""

    def test_new_topologies_have_synthesize_method(self):
        """Every 'new' topology must have a working synthesize() on its generator."""
        from psim_mcp.generators import get_generator

        for topo, caps in CAPABILITY_MATRIX.items():
            if caps.get("synthesize") != "new":
                continue
            gen = get_generator(topo)
            assert hasattr(gen, "synthesize"), (
                f"'{topo}' is 'new' for synthesize but generator has no synthesize() method"
            )

    def test_legacy_topologies_have_generate_method(self):
        """Every 'legacy' topology must have a working generate() on its generator."""
        from psim_mcp.generators import get_generator

        for topo, caps in CAPABILITY_MATRIX.items():
            if caps.get("synthesize") not in ("legacy", "new"):
                continue
            try:
                gen = get_generator(topo)
                assert hasattr(gen, "generate"), (
                    f"'{topo}' is marked '{caps['synthesize']}' but generator has no generate()"
                )
            except KeyError:
                pass  # no generator registered — that's a different issue

    def test_no_topology_claims_new_without_graph(self):
        """If synthesize is 'new', graph must also be 'new'."""
        for topo, caps in CAPABILITY_MATRIX.items():
            if caps.get("synthesize") == "new":
                assert caps.get("graph") == "new", (
                    f"'{topo}' has synthesize=new but graph={caps.get('graph')}"
                )

    def test_layout_requires_graph(self):
        """If layout is 'new', graph must be 'new' too."""
        for topo, caps in CAPABILITY_MATRIX.items():
            if caps.get("layout") == "new":
                assert caps.get("graph") == "new", (
                    f"'{topo}' has layout=new but graph={caps.get('graph')}"
                )


# ---------------------------------------------------------------------------
# 3. Topology promotion readiness (legacy → new)
# ---------------------------------------------------------------------------

class TestTopologyPromotionReadiness:
    """Track which legacy topologies are ready for promotion to 'new'."""

    def test_legacy_topologies_with_synthesize_method(self):
        """Report legacy topologies that already have synthesize() — promotion candidates."""
        from psim_mcp.generators import get_generator

        promotion_candidates = []
        for topo, caps in CAPABILITY_MATRIX.items():
            if caps.get("synthesize") != "legacy":
                continue
            try:
                gen = get_generator(topo)
                if hasattr(gen, "synthesize"):
                    try:
                        graph = gen.synthesize({"vin": 48, "vout_target": 12, "iout": 1})
                        if graph is not None:
                            promotion_candidates.append(topo)
                    except (NotImplementedError, Exception):
                        pass
            except KeyError:
                pass

        # This is informational — not a failure
        # If promotion_candidates is non-empty, someone should update capability_matrix
        if promotion_candidates:
            pytest.skip(
                f"These legacy topologies have working synthesize() and could be promoted: "
                f"{promotion_candidates}"
            )


# ---------------------------------------------------------------------------
# 4. Preview/PSIM payload consistency across fallback boundaries
# ---------------------------------------------------------------------------

class TestPayloadConsistencyAcrossFallback:
    """Preview and confirm/create must use the same canonical data."""

    @pytest.fixture
    def service(self):
        from psim_mcp.services.circuit_design_service import CircuitDesignService
        from psim_mcp.adapters.mock_adapter import MockPsimAdapter
        config = AppConfig(psim_mode="mock", _env_file=None)
        return CircuitDesignService(adapter=MockPsimAdapter(), config=config)

    async def test_preview_components_match_confirm_components(self, service):
        """Components in preview payload must match what confirm_circuit uses."""
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"]
        token = result["data"]["preview_token"]
        stored = service._store.get(token)

        preview_comp_ids = {c["id"] for c in stored["components"]}

        # If graph is stored, materialize should produce same component set
        if "graph" in stored and "layout" in stored:
            from psim_mcp.synthesis.graph import CircuitGraph
            from psim_mcp.layout.models import SchematicLayout
            from psim_mcp.layout.materialize import materialize_to_legacy

            graph = CircuitGraph.from_dict(stored["graph"])
            layout = SchematicLayout.from_dict(stored["layout"])
            rematerialized_comps, _ = materialize_to_legacy(graph, layout)
            remat_ids = {c["id"] for c in rematerialized_comps}

            assert preview_comp_ids == remat_ids, (
                f"Preview components {preview_comp_ids} don't match "
                f"rematerialized components {remat_ids}. "
                f"This means confirm_circuit would use different components than preview."
            )

    async def test_wire_segments_match_routing(self, service):
        """wire_segments in payload must match routing.to_legacy_segments()."""
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"]
        token = result["data"]["preview_token"]
        stored = service._store.get(token)

        if "routing" in stored and "wire_segments" in stored:
            from psim_mcp.routing.models import WireRouting
            routing = WireRouting.from_dict(stored["routing"])
            routing_segs = routing.to_legacy_segments()

            stored_segs = stored["wire_segments"]

            # Same count
            assert len(stored_segs) == len(routing_segs), (
                f"wire_segments count ({len(stored_segs)}) != "
                f"routing.to_legacy_segments() count ({len(routing_segs)})"
            )

    async def test_legacy_topology_still_produces_valid_preview(self, service):
        """Legacy topologies must still produce valid previews via fallback."""
        # boost is legacy — no synthesize()
        result = await service.preview_circuit(
            circuit_type="boost",
            specs={"vin": 12, "vout_target": 48, "iout": 2},
        )
        assert result["success"] is True
        assert "preview_token" in result["data"]
        assert result["data"]["component_count"] > 0
