"""Tests for layout data models."""

from psim_mcp.layout.models import (
    LayoutComponent,
    LayoutConstraint,
    LayoutRegion,
    SchematicLayout,
)


# -- LayoutComponent tests --

def test_layout_component_creation():
    lc = LayoutComponent(id="V1", x=100, y=200, direction=0)
    assert lc.id == "V1"
    assert lc.x == 100
    assert lc.y == 200
    assert lc.direction == 0


def test_layout_component_defaults():
    lc = LayoutComponent(id="R1", x=0, y=0, direction=90)
    assert lc.symbol_variant is None
    assert lc.region_id is None
    assert lc.anchor_policy is None
    assert lc.metadata == {}


def test_layout_component_with_all_fields():
    lc = LayoutComponent(
        id="SW1", x=150, y=100, direction=270,
        symbol_variant="mosfet_horizontal",
        region_id="switch_region",
        anchor_policy="pin_aligned",
        metadata={"custom": True},
    )
    assert lc.symbol_variant == "mosfet_horizontal"
    assert lc.region_id == "switch_region"
    assert lc.anchor_policy == "pin_aligned"
    assert lc.metadata["custom"] is True


# -- LayoutRegion tests --

def test_layout_region_creation():
    lr = LayoutRegion(id="input_region", role="input", x=100, y=80, width=80, height=100)
    assert lr.id == "input_region"
    assert lr.role == "input"
    assert lr.width == 80
    assert lr.height == 100


def test_layout_region_defaults():
    lr = LayoutRegion(id="r1", role="test", x=0, y=0, width=50, height=50)
    assert lr.metadata == {}


# -- LayoutConstraint tests --

def test_layout_constraint_creation():
    lc = LayoutConstraint(kind="left_of", subject_ids=["a", "b"])
    assert lc.kind == "left_of"
    assert lc.subject_ids == ["a", "b"]
    assert lc.value is None
    assert lc.priority == "normal"


def test_layout_constraint_with_value():
    lc = LayoutConstraint(
        kind="align_to_rail",
        subject_ids=["net_gnd"],
        value={"y": 150},
        priority="high",
    )
    assert lc.value == {"y": 150}
    assert lc.priority == "high"


# -- SchematicLayout tests --

def test_schematic_layout_creation():
    sl = SchematicLayout(
        topology="buck",
        components=[LayoutComponent(id="V1", x=100, y=100, direction=0)],
    )
    assert sl.topology == "buck"
    assert len(sl.components) == 1


def test_schematic_layout_defaults():
    sl = SchematicLayout(topology="test", components=[])
    assert sl.regions == []
    assert sl.constraints == []
    assert sl.metadata == {}


def test_schematic_layout_to_dict_roundtrip():
    original = SchematicLayout(
        topology="buck",
        components=[
            LayoutComponent(id="V1", x=120, y=100, direction=0, symbol_variant="dc_source"),
            LayoutComponent(id="R1", x=350, y=100, direction=90),
        ],
        regions=[
            LayoutRegion(id="input_region", role="input", x=100, y=80, width=80, height=100),
        ],
        constraints=[
            LayoutConstraint(kind="left_of", subject_ids=["a", "b"]),
        ],
        metadata={"flow_direction": "left_to_right"},
    )
    d = original.to_dict()
    restored = SchematicLayout.from_dict(d)

    assert restored.topology == original.topology
    assert len(restored.components) == len(original.components)
    assert restored.components[0].id == "V1"
    assert restored.components[0].x == 120
    assert restored.components[0].symbol_variant == "dc_source"
    assert restored.components[1].id == "R1"
    assert len(restored.regions) == 1
    assert restored.regions[0].id == "input_region"
    assert len(restored.constraints) == 1
    assert restored.constraints[0].kind == "left_of"
    assert restored.metadata["flow_direction"] == "left_to_right"


def test_get_component_found():
    sl = SchematicLayout(
        topology="test",
        components=[
            LayoutComponent(id="A", x=0, y=0, direction=0),
            LayoutComponent(id="B", x=10, y=10, direction=90),
        ],
    )
    result = sl.get_component("B")
    assert result is not None
    assert result.id == "B"
    assert result.x == 10


def test_get_component_not_found():
    sl = SchematicLayout(topology="test", components=[])
    assert sl.get_component("missing") is None


def test_get_region_found():
    sl = SchematicLayout(
        topology="test",
        components=[],
        regions=[
            LayoutRegion(id="r1", role="input", x=0, y=0, width=50, height=50),
            LayoutRegion(id="r2", role="output", x=100, y=0, width=50, height=50),
        ],
    )
    result = sl.get_region("r2")
    assert result is not None
    assert result.role == "output"


def test_get_region_not_found():
    sl = SchematicLayout(topology="test", components=[])
    assert sl.get_region("nonexistent") is None
