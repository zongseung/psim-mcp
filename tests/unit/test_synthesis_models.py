"""Unit tests for synthesis data models."""

from psim_mcp.synthesis.models import (
    DesignSessionV1,
    LegacyRenderableCircuit,
    NetSpec,
    PreviewPayloadV1,
    SizedComponentSpec,
    TopologySynthesisResult,
)


def test_sized_component_spec_defaults():
    s = SizedComponentSpec(id="V1", type="DC_Source")
    assert s.id == "V1"
    assert s.type == "DC_Source"
    assert s.role is None
    assert s.parameters == {}
    assert s.metadata == {}


def test_sized_component_spec_with_params():
    s = SizedComponentSpec(
        id="L1", type="Inductor", role="output_inductor",
        parameters={"inductance": 1e-3},
    )
    assert s.role == "output_inductor"
    assert s.parameters["inductance"] == 1e-3


def test_net_spec_creation():
    n = NetSpec(name="net_gnd", pins=["V1.negative", "GND1.pin1"])
    assert n.name == "net_gnd"
    assert len(n.pins) == 2
    assert n.role is None


def test_net_spec_with_role():
    n = NetSpec(name="net_gnd", pins=["V1.negative"], role="ground")
    assert n.role == "ground"


def test_topology_synthesis_result():
    comps = [SizedComponentSpec(id="V1", type="DC_Source")]
    nets = [NetSpec(name="net1", pins=["V1.positive"])]
    r = TopologySynthesisResult(
        topology="buck", components=comps, nets=nets,
        design={"duty": 0.25},
    )
    assert r.topology == "buck"
    assert len(r.components) == 1
    assert r.design["duty"] == 0.25


def test_legacy_renderable_circuit():
    lrc = LegacyRenderableCircuit(
        topology="buck",
        components=[{"id": "V1"}],
        nets=[{"name": "net1"}],
    )
    assert lrc.topology == "buck"
    assert len(lrc.components) == 1


def test_preview_payload_v1_defaults():
    p = PreviewPayloadV1()
    assert p.payload_kind == "preview_payload"
    assert p.payload_version == "v1"
    assert p.circuit_type is None


def test_preview_payload_v1_roundtrip():
    p = PreviewPayloadV1(circuit_type="buck", components=[{"id": "V1"}])
    d = p.to_dict()
    p2 = PreviewPayloadV1.from_dict(d)
    assert p2.circuit_type == "buck"
    assert p2.components == [{"id": "V1"}]


def test_design_session_v1_roundtrip():
    s = DesignSessionV1(topology="buck", specs={"vin": 48}, missing_fields=["vout_target"])
    d = s.to_dict()
    s2 = DesignSessionV1.from_dict(d)
    assert s2.topology == "buck"
    assert s2.specs["vin"] == 48
    assert s2.missing_fields == ["vout_target"]


def test_design_session_v1_defaults():
    s = DesignSessionV1()
    assert s.payload_kind == "design_session"
    assert s.payload_version == "v1"
    assert s.topology is None
