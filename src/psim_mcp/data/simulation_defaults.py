"""토폴로지별 기본 시뮬레이션 파라미터.

스위칭 주파수와 정상 상태 도달 시간을 고려하여
각 토폴로지에 적합한 time_step과 total_time 기본값을 정의한다.
"""

from __future__ import annotations

SIMULATION_DEFAULTS: dict[str, dict[str, str]] = {
    # DC-DC 컨버터 (스위칭 주파수 기반, 정상 상태 도달까지 충분한 시간)
    "buck": {"time_step": "1E-006", "total_time": "0.05"},
    "boost": {"time_step": "1E-006", "total_time": "0.05"},
    "buck_boost": {"time_step": "1E-006", "total_time": "0.05"},
    "flyback": {"time_step": "5E-007", "total_time": "0.05"},
    "forward": {"time_step": "5E-007", "total_time": "0.05"},
    "llc": {"time_step": "1E-007", "total_time": "0.01"},
    "dab": {"time_step": "1E-007", "total_time": "0.01"},
    "sepic": {"time_step": "1E-006", "total_time": "0.05"},
    "cuk": {"time_step": "1E-006", "total_time": "0.05"},
    "push_pull": {"time_step": "5E-007", "total_time": "0.05"},
    "bidirectional_buck_boost": {"time_step": "1E-006", "total_time": "0.05"},
    "phase_shifted_full_bridge": {"time_step": "1E-007", "total_time": "0.01"},

    # 인버터 (출력 주파수 기반)
    "half_bridge": {"time_step": "1E-006", "total_time": "0.1"},
    "full_bridge": {"time_step": "1E-006", "total_time": "0.1"},
    "three_phase_inverter": {"time_step": "1E-006", "total_time": "0.1"},
    "three_level_npc": {"time_step": "1E-006", "total_time": "0.1"},

    # 정류기
    "diode_bridge_rectifier": {"time_step": "1E-005", "total_time": "0.1"},
    "thyristor_rectifier": {"time_step": "1E-005", "total_time": "0.1"},

    # PFC
    "boost_pfc": {"time_step": "1E-006", "total_time": "0.1"},
    "totem_pole_pfc": {"time_step": "5E-007", "total_time": "0.1"},

    # 모터 드라이브
    "bldc_drive": {"time_step": "1E-006", "total_time": "0.5"},
    "pmsm_foc_drive": {"time_step": "1E-006", "total_time": "0.5"},
    "induction_motor_vf": {"time_step": "1E-006", "total_time": "0.5"},

    # 배터리 충전 / OBC
    "cc_cv_charger": {"time_step": "1E-005", "total_time": "1.0"},
    "ev_obc": {"time_step": "1E-006", "total_time": "0.1"},

    # 태양광
    "pv_mppt_boost": {"time_step": "1E-006", "total_time": "0.1"},
    "pv_grid_tied": {"time_step": "1E-006", "total_time": "0.1"},

    # 필터
    "lc_filter": {"time_step": "1E-006", "total_time": "0.01"},
    "lcl_filter": {"time_step": "1E-006", "total_time": "0.01"},
}

# 토폴로지를 찾지 못한 경우 글로벌 기본값
GLOBAL_DEFAULT: dict[str, str] = {"time_step": "1E-006", "total_time": "0.05"}


def get_simulation_defaults(topology: str) -> dict[str, str]:
    """토폴로지에 맞는 기본 시뮬레이션 파라미터를 반환한다.

    Args:
        topology: 토폴로지 이름 (예: "buck", "llc", "three_phase_inverter")

    Returns:
        {"time_step": "...", "total_time": "..."} 형태의 딕셔너리
    """
    return SIMULATION_DEFAULTS.get(topology.lower(), GLOBAL_DEFAULT)
