"""토폴로지별 기본 시뮬레이션 파라미터 테스트."""

from __future__ import annotations

import pytest

from psim_mcp.data.simulation_defaults import (
    GLOBAL_DEFAULT,
    SIMULATION_DEFAULTS,
    get_simulation_defaults,
)


class TestSimulationDefaults:
    """SIMULATION_DEFAULTS 딕셔너리 구조 검증."""

    def test_all_entries_have_required_keys(self):
        """모든 토폴로지에 time_step과 total_time이 있어야 한다."""
        for topology, defaults in SIMULATION_DEFAULTS.items():
            assert "time_step" in defaults, f"{topology}: time_step 누락"
            assert "total_time" in defaults, f"{topology}: total_time 누락"

    def test_global_default_has_required_keys(self):
        """글로벌 기본값에도 time_step과 total_time이 있어야 한다."""
        assert "time_step" in GLOBAL_DEFAULT
        assert "total_time" in GLOBAL_DEFAULT

    def test_all_values_are_strings(self):
        """모든 값은 문자열이어야 한다 (PSIM API가 문자열을 요구)."""
        for topology, defaults in SIMULATION_DEFAULTS.items():
            assert isinstance(defaults["time_step"], str), f"{topology}: time_step이 문자열이 아님"
            assert isinstance(defaults["total_time"], str), f"{topology}: total_time이 문자열이 아님"

    @pytest.mark.parametrize(
        "topology",
        [
            "buck", "boost", "buck_boost", "flyback", "llc", "dab",
            "half_bridge", "full_bridge", "three_phase_inverter",
            "diode_bridge_rectifier",
            "boost_pfc", "totem_pole_pfc",
            "bldc_drive", "pmsm_foc_drive",
            "cc_cv_charger",
            "pv_mppt_boost", "pv_grid_tied",
            "lc_filter", "lcl_filter",
        ],
    )
    def test_required_topologies_exist(self, topology: str):
        """PRD에서 요구한 모든 토폴로지가 정의되어 있어야 한다."""
        assert topology in SIMULATION_DEFAULTS


class TestGetSimulationDefaults:
    """get_simulation_defaults() 함수 테스트."""

    def test_known_topology_returns_specific_defaults(self):
        """알려진 토폴로지는 해당 기본값을 반환한다."""
        result = get_simulation_defaults("buck")
        assert result == SIMULATION_DEFAULTS["buck"]

    def test_unknown_topology_returns_global_default(self):
        """알 수 없는 토폴로지는 글로벌 기본값을 반환한다."""
        result = get_simulation_defaults("unknown_topology")
        assert result == GLOBAL_DEFAULT

    def test_case_insensitive_lookup(self):
        """토폴로지 이름은 대소문자를 구분하지 않는다."""
        assert get_simulation_defaults("BUCK") == SIMULATION_DEFAULTS["buck"]
        assert get_simulation_defaults("Buck") == SIMULATION_DEFAULTS["buck"]
        assert get_simulation_defaults("LLC") == SIMULATION_DEFAULTS["llc"]

    def test_empty_string_returns_global_default(self):
        """빈 문자열은 글로벌 기본값을 반환한다."""
        result = get_simulation_defaults("")
        assert result == GLOBAL_DEFAULT

    def test_llc_has_smaller_timestep_than_buck(self):
        """LLC는 buck보다 작은 time_step을 가져야 한다 (더 높은 주파수)."""
        llc_ts = float(get_simulation_defaults("llc")["time_step"])
        buck_ts = float(get_simulation_defaults("buck")["time_step"])
        assert llc_ts < buck_ts

    def test_motor_drive_has_longer_total_time(self):
        """모터 드라이브는 정상 상태 도달에 더 긴 total_time이 필요하다."""
        bldc_tt = float(get_simulation_defaults("bldc_drive")["total_time"])
        buck_tt = float(get_simulation_defaults("buck")["total_time"])
        assert bldc_tt > buck_tt
