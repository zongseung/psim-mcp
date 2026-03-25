"""bridge_script.py 헬퍼 함수 테스트.

bridge_script.py는 PSIM Python 3.8에서 실행되지만,
순수 함수인 헬퍼들은 테스트 환경에서도 import하여 검증할 수 있다.
"""

from __future__ import annotations

from psim_mcp.bridge.bridge_script import (
    _PSIM_TYPE_MAP,
    _calculate_simcontrol_position,
    _GLOBAL_DEFAULT,
    _get_simulation_defaults,
    _resolve_pin_positions,
    _SIMULATION_DEFAULTS,
)
from psim_mcp.generators.layout import make_transformer


class TestCalculateSimcontrolPosition:
    """_calculate_simcontrol_position() 테스트."""

    def test_no_components_returns_default(self):
        """컴포넌트가 없으면 기본 위치를 반환한다."""
        assert _calculate_simcontrol_position([]) == "{130, 40}"

    def test_single_component(self):
        """단일 컴포넌트가 있으면 그 위치 기준으로 오프셋을 적용한다."""
        components = [{"position": {"x": 200, "y": 100}}]
        result = _calculate_simcontrol_position(components)
        assert result == "{300, 50}"  # 200+100, 100-50

    def test_multiple_components_uses_bounding_box(self):
        """여러 컴포넌트의 bounding box 우측 상단에 배치한다."""
        components = [
            {"position": {"x": 100, "y": 200}},
            {"position": {"x": 400, "y": 50}},
            {"position": {"x": 250, "y": 300}},
        ]
        result = _calculate_simcontrol_position(components)
        # max_x=400, min_y=50 → {500, 0}
        assert result == "{500, 0}"

    def test_components_without_position_treated_as_origin(self):
        """position이 없는 컴포넌트는 (0, 0)으로 처리된다."""
        components = [{"id": "R1"}, {"position": {"x": 100, "y": 100}}]
        result = _calculate_simcontrol_position(components)
        assert result == "{200, -50}"  # max_x=100, min_y=0

    def test_negative_coordinates(self):
        """음수 좌표도 올바르게 처리한다."""
        components = [
            {"position": {"x": -100, "y": -200}},
            {"position": {"x": 50, "y": -50}},
        ]
        result = _calculate_simcontrol_position(components)
        # max_x=50, min_y=-200 → {150, -250}
        assert result == "{150, -250}"


class TestGetSimulationDefaults:
    """_get_simulation_defaults() 테스트 (bridge_script 인라인 버전)."""

    def test_known_topology(self):
        result = _get_simulation_defaults("buck")
        assert result == _SIMULATION_DEFAULTS["buck"]

    def test_unknown_topology_returns_global(self):
        result = _get_simulation_defaults("nonexistent")
        assert result == _GLOBAL_DEFAULT

    def test_empty_string_returns_global(self):
        result = _get_simulation_defaults("")
        assert result == _GLOBAL_DEFAULT

    def test_none_returns_global(self):
        result = _get_simulation_defaults(None)
        assert result == _GLOBAL_DEFAULT

    def test_case_insensitive(self):
        result = _get_simulation_defaults("BUCK")
        assert result == _SIMULATION_DEFAULTS["buck"]


class TestResolvePinPositions:
    def test_uses_shared_transformer_alias_contract(self):
        components = [
            make_transformer("T1", 100, 80, 100, 130, 150, 130, 150, 80, turns_ratio=0.25)
        ]

        pin_map = _resolve_pin_positions(components)

        assert pin_map["T1.primary1"] == (100, 80)
        assert pin_map["T1.primary_in"] == (100, 80)
        assert pin_map["T1.secondary1"] == (150, 130)
        assert pin_map["T1.secondary_out"] == (150, 130)


class TestPsimTypeMap:
    def test_vac_mapping_uses_native_vac_element(self):
        assert _PSIM_TYPE_MAP["VAC"] == "VAC"
        assert _PSIM_TYPE_MAP["AC_Source"] == "VAC"
