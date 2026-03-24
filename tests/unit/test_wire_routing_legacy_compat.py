"""Phase 4: WireRouting legacy compatibility tests.

Ensures WireRouting.to_legacy_segments() produces the correct format
expected by the SVG renderer and bridge pipeline.
"""

from __future__ import annotations

import pytest

from psim_mcp.routing.models import (
    JunctionPoint,
    RoutedSegment,
    WireRouting,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_segments() -> list[RoutedSegment]:
    return [
        RoutedSegment(id="seg_1", net_id="net_gnd", x1=120, y1=150, x2=350, y2=150, role="trunk"),
        RoutedSegment(id="seg_2", net_id="net_gnd", x1=220, y1=150, x2=220, y2=100, role="branch"),
        RoutedSegment(id="seg_3", net_id="net_out", x1=300, y1=100, x2=350, y2=100, role="direct"),
    ]


@pytest.fixture
def sample_routing(sample_segments) -> WireRouting:
    return WireRouting(
        topology="buck",
        segments=sample_segments,
        junctions=[JunctionPoint(x=220, y=150, net_id="net_gnd")],
        metadata={"strategy": "generic_trunk_branch"},
    )


# ---------------------------------------------------------------------------
# to_legacy_segments() format tests
# ---------------------------------------------------------------------------

class TestToLegacySegments:
    def test_returns_list(self, sample_routing):
        legacy = sample_routing.to_legacy_segments()
        assert isinstance(legacy, list)

    def test_correct_count(self, sample_routing, sample_segments):
        legacy = sample_routing.to_legacy_segments()
        assert len(legacy) == len(sample_segments)

    def test_each_segment_has_id(self, sample_routing):
        for seg in sample_routing.to_legacy_segments():
            assert "id" in seg
            assert isinstance(seg["id"], str)

    def test_each_segment_has_net(self, sample_routing):
        for seg in sample_routing.to_legacy_segments():
            assert "net" in seg

    def test_each_segment_has_coordinates(self, sample_routing):
        for seg in sample_routing.to_legacy_segments():
            assert "x1" in seg
            assert "y1" in seg
            assert "x2" in seg
            assert "y2" in seg
            assert isinstance(seg["x1"], int)
            assert isinstance(seg["y1"], int)
            assert isinstance(seg["x2"], int)
            assert isinstance(seg["y2"], int)

    def test_net_id_mapped_to_net_key(self, sample_routing):
        """RoutedSegment.net_id should map to legacy 'net' key."""
        legacy = sample_routing.to_legacy_segments()
        assert legacy[0]["net"] == "net_gnd"
        assert legacy[2]["net"] == "net_out"

    def test_coordinate_values_preserved(self, sample_routing):
        legacy = sample_routing.to_legacy_segments()
        assert legacy[0]["x1"] == 120
        assert legacy[0]["y1"] == 150
        assert legacy[0]["x2"] == 350
        assert legacy[0]["y2"] == 150

    def test_empty_routing_produces_empty_list(self):
        routing = WireRouting(topology="buck", segments=[])
        assert routing.to_legacy_segments() == []


# ---------------------------------------------------------------------------
# Round-trip: to_dict -> from_dict -> to_legacy_segments
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_to_dict_from_dict_round_trip(self, sample_routing):
        d = sample_routing.to_dict()
        restored = WireRouting.from_dict(d)
        assert restored.topology == sample_routing.topology
        assert len(restored.segments) == len(sample_routing.segments)
        assert len(restored.junctions) == len(sample_routing.junctions)

    def test_round_trip_legacy_segments_match(self, sample_routing):
        d = sample_routing.to_dict()
        restored = WireRouting.from_dict(d)
        original_legacy = sample_routing.to_legacy_segments()
        restored_legacy = restored.to_legacy_segments()
        assert original_legacy == restored_legacy

    def test_round_trip_metadata_preserved(self, sample_routing):
        d = sample_routing.to_dict()
        restored = WireRouting.from_dict(d)
        assert restored.metadata == sample_routing.metadata

    def test_round_trip_segment_roles_preserved(self, sample_routing):
        d = sample_routing.to_dict()
        restored = WireRouting.from_dict(d)
        for orig, rest in zip(sample_routing.segments, restored.segments):
            assert orig.role == rest.role

    def test_from_dict_with_empty_segments(self):
        d = {"topology": "test", "segments": [], "junctions": [], "metadata": {}}
        restored = WireRouting.from_dict(d)
        assert restored.to_legacy_segments() == []
