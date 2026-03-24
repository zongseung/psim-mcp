"""Phase 3: Materialize layout integration tests.

Tests that materialize_to_legacy produces output matching generators/buck.py format.
"""

import pytest

from psim_mcp.synthesis.topologies.buck import synthesize_buck
from psim_mcp.layout.engine import generate_layout
from psim_mcp.layout.materialize import materialize_to_legacy


@pytest.fixture
def buck_requirements():
    return {"vin": 48, "vout_target": 12, "iout": 5}


@pytest.fixture
def buck_graph(buck_requirements):
    return synthesize_buck(buck_requirements)


@pytest.fixture
def buck_layout(buck_graph):
    return generate_layout(buck_graph)


@pytest.fixture
def materialized(buck_graph, buck_layout):
    return materialize_to_legacy(buck_graph, buck_layout)


class TestMaterializeComponents:

    def test_components_have_position(self, materialized):
        components, _ = materialized
        for comp in components:
            assert "position" in comp, f"{comp['id']} missing position"
            assert "x" in comp["position"]
            assert "y" in comp["position"]

    def test_components_have_direction(self, materialized):
        components, _ = materialized
        for comp in components:
            assert "direction" in comp, f"{comp['id']} missing direction"
            assert isinstance(comp["direction"], int)

    def test_components_have_ports(self, materialized):
        components, _ = materialized
        for comp in components:
            assert "ports" in comp, f"{comp['id']} missing ports"
            assert isinstance(comp["ports"], list)
            assert len(comp["ports"]) >= 2, f"{comp['id']} needs at least 2 port coords"

    def test_component_count_matches_graph(self, buck_graph, materialized):
        components, _ = materialized
        assert len(components) == len(buck_graph.components)

    def test_all_component_ids_present(self, buck_graph, materialized):
        components, _ = materialized
        comp_ids = {c["id"] for c in components}
        expected_ids = {c.id for c in buck_graph.components}
        assert comp_ids == expected_ids

    def test_components_have_parameters(self, materialized):
        components, _ = materialized
        for comp in components:
            assert "parameters" in comp
            assert isinstance(comp["parameters"], dict)

    def test_inductor_has_position2(self, materialized):
        components, _ = materialized
        l1 = next(c for c in components if c["id"] == "L1")
        assert "position2" in l1

    def test_capacitor_has_position2(self, materialized):
        components, _ = materialized
        c1 = next(c for c in components if c["id"] == "C1")
        assert "position2" in c1

    def test_resistor_has_position2(self, materialized):
        components, _ = materialized
        r1 = next(c for c in components if c["id"] == "R1")
        assert "position2" in r1

    def test_mosfet_has_3_port_pairs(self, materialized):
        components, _ = materialized
        sw1 = next(c for c in components if c["id"] == "SW1")
        # drain, source, gate = 6 coordinates
        assert len(sw1["ports"]) == 6

    def test_dc_source_has_2_port_pairs(self, materialized):
        components, _ = materialized
        v1 = next(c for c in components if c["id"] == "V1")
        # positive, negative = 4 coordinates
        assert len(v1["ports"]) == 4


class TestMaterializeNets:

    def test_net_count_matches_graph(self, buck_graph, materialized):
        _, nets = materialized
        assert len(nets) == len(buck_graph.nets)

    def test_nets_have_name_and_pins(self, materialized):
        _, nets = materialized
        for net in nets:
            assert "name" in net
            assert "pins" in net
            assert isinstance(net["pins"], list)
            assert len(net["pins"]) >= 2

    def test_net_names_match_graph(self, buck_graph, materialized):
        _, nets = materialized
        net_names = {n["name"] for n in nets}
        expected_names = {n.id for n in buck_graph.nets}
        assert net_names == expected_names


class TestMaterializeMatchesGenerator:
    """Verify output format is compatible with existing pipeline."""

    def test_format_matches_buck_generator_output(self, buck_requirements, materialized):
        from psim_mcp.generators.buck import BuckGenerator
        gen = BuckGenerator()
        gen_result = gen.generate(buck_requirements)

        components, nets = materialized

        # Same component IDs
        mat_ids = sorted(c["id"] for c in components)
        gen_ids = sorted(c["id"] for c in gen_result["components"])
        assert mat_ids == gen_ids

        # Same net names
        mat_net_names = sorted(n["name"] for n in nets)
        gen_net_names = sorted(n["name"] for n in gen_result["nets"])
        assert mat_net_names == gen_net_names

        # All components have required keys
        required_keys = {"id", "type", "parameters", "position", "direction", "ports"}
        for comp in components:
            assert required_keys.issubset(comp.keys()), (
                f"Component {comp['id']} missing keys: {required_keys - comp.keys()}"
            )
