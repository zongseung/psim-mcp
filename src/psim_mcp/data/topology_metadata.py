"""Per-topology metadata: required fields, slot questions, and category info.

This replaces hardcoded fallbacks in the intent parser with topology-aware
metadata that can be used regardless of whether a generator exists.
"""

TOPOLOGY_METADATA: dict[str, dict] = {
    # DC-DC non-isolated
    "buck": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "switching_frequency"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요? (예: 48V)",
            "vout_target": "목표 출력 전압은 몇 V인가요? (예: 12V)",
            "iout": "출력 전류는 몇 A인가요? (예: 5A)",
        },
    },
    "boost": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "switching_frequency"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요? (예: 12V)",
            "vout_target": "목표 출력 전압은 몇 V인가요? (예: 48V)",
        },
    },
    "buck_boost": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "switching_frequency"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "목표 출력 전압은 몇 V인가요?",
        },
    },
    # DC-DC isolated
    "flyback": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "switching_frequency", "isolation"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요? (예: 310V, 정류 후 DC)",
            "vout_target": "출력 전압은 몇 V인가요? (예: 5V, 12V)",
            "iout": "출력 전류는 몇 A인가요?",
        },
    },
    "forward": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "switching_frequency"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
        },
    },
    "llc": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "slot_questions": {
            "vin": "입력 DC 전압은 몇 V인가요? (예: 400V)",
            "vout_target": "출력 전압은 몇 V인가요? (예: 48V)",
            "power_rating": "정격 전력은 얼마인가요? (예: 1kW)",
        },
    },
    "dab": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "slot_questions": {
            "vin": "1차측 전압은 몇 V인가요?",
            "vout_target": "2차측 전압은 몇 V인가요?",
        },
    },
    "push_pull": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
        },
    },
    "phase_shifted_full_bridge": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "slot_questions": {
            "vin": "입력 DC 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
            "power_rating": "정격 전력은 얼마인가요?",
        },
    },
    # DC-AC inverters
    "half_bridge": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance", "switching_frequency"],
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 400V)",
            "load_resistance": "부하 저항은 몇 Ω인가요?",
        },
    },
    "full_bridge": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance", "switching_frequency"],
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 400V)",
        },
    },
    "three_phase_inverter": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance", "switching_frequency", "output_frequency"],
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 600V)",
            "output_frequency": "출력 주파수는? (기본: 60Hz)",
        },
    },
    "three_level_npc": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance", "switching_frequency"],
        "slot_questions": {
            "vin": "DC bus 전압(총)은 몇 V인가요? (예: 800V, 분할 사용)",
        },
    },
    # AC-DC
    "diode_bridge_rectifier": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance"],
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요? (예: 220V)",
        },
    },
    "thyristor_rectifier": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["firing_angle", "load_resistance"],
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요?",
        },
    },
    # PFC
    "boost_pfc": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "power_rating"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요? (예: 220V)",
            "power_rating": "정격 전력은 얼마인가요?",
        },
    },
    "totem_pole_pfc": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "power_rating"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요?",
        },
    },
    # Renewable
    "pv_mppt_boost": {
        "required_fields": [],
        "design_ready_fields": [],
        "optional_fields": ["voc", "isc", "vmp", "imp"],
        "slot_questions": {
            "voc": "태양광 패널 개방전압(Voc)은? (예: 40V)",
            "isc": "단락전류(Isc)는? (예: 10A)",
        },
    },
    "pv_grid_tied": {
        "required_fields": [],
        "design_ready_fields": [],
        "optional_fields": ["voc", "grid_voltage"],
        "slot_questions": {},
    },
    # Motor drives
    "bldc_drive": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin"],
        "optional_fields": ["motor_poles", "rated_speed"],
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 48V)",
        },
    },
    "pmsm_foc_drive": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin"],
        "optional_fields": ["motor_poles", "rated_speed", "rated_torque"],
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 300V)",
        },
    },
    "induction_motor_vf": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin"],
        "optional_fields": ["motor_poles", "rated_speed"],
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 540V)",
        },
    },
    # Battery
    "cc_cv_charger": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "battery_capacity"],
        "slot_questions": {
            "vin": "충전기 입력 전압은 몇 V인가요?",
            "vout_target": "배터리 전압은 몇 V인가요? (예: 12V, 48V)",
            "iout": "충전 전류는 몇 A인가요?",
        },
    },
    "ev_obc": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin"],
        "optional_fields": ["vout_target", "power_rating"],
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요? (예: 220V)",
            "vout_target": "배터리 전압은 몇 V인가요? (예: 400V)",
            "power_rating": "충전 전력은 얼마인가요? (예: 6.6kW)",
        },
    },
    # Filters
    "lc_filter": {
        "required_fields": [],
        "design_ready_fields": [],
        "optional_fields": ["cutoff_frequency"],
        "slot_questions": {},
    },
    "lcl_filter": {
        "required_fields": [],
        "design_ready_fields": [],
        "optional_fields": ["cutoff_frequency", "grid_frequency"],
        "slot_questions": {},
    },
    # Bidirectional
    "bidirectional_buck_boost": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["power_rating"],
        "slot_questions": {
            "vin": "고압측 전압은 몇 V인가요?",
            "vout_target": "저압측(배터리) 전압은 몇 V인가요?",
        },
    },
    # Misc
    "cuk": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
        },
    },
    "sepic": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout"],
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
        },
    },
}


def get_topology_metadata(topology: str) -> dict | None:
    """Return metadata for a topology, or None if unknown."""
    return TOPOLOGY_METADATA.get(topology.lower())


def get_required_fields(topology: str) -> list[str]:
    """Return required fields for a topology. Falls back to empty list."""
    meta = get_topology_metadata(topology)
    if meta:
        return meta["required_fields"]
    return []


def get_design_ready_fields(topology: str) -> list[str]:
    """Return fields needed for a meaningful design (stricter than required_fields)."""
    meta = get_topology_metadata(topology)
    if meta:
        return meta.get("design_ready_fields", meta.get("required_fields", []))
    return []


def get_slot_questions(topology: str) -> dict[str, str]:
    """Return topology-specific slot questions."""
    meta = get_topology_metadata(topology)
    if meta:
        return meta.get("slot_questions", {})
    return {}
