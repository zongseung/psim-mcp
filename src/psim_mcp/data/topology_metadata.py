"""Per-topology metadata: required fields, slot questions, and category info.

This replaces hardcoded fallbacks in the intent parser with topology-aware
metadata that can be used regardless of whether a generator exists.

Each topology entry may include:
- required_fields: minimum to identify user intent
- design_ready_fields: minimum for meaningful auto-design
- optional_fields: nice-to-have parameters
- slot_questions: topology-specific prompts for missing fields
- isolated: True if the topology uses galvanic isolation (transformer)
- single_voltage_role: when only 1 voltage is given, assign to "vin" or "vout_target"
- conversion_type: "dc_dc", "ac_dc", "dc_ac", "ac_ac", "filter", "drive", "pfc"

This module also owns parser-side metadata that should not live inline in
``intent_parser.py``, such as priority keyword overrides for descriptive
requests like "노트북 어댑터" or "충전기".
"""

PRIORITY_OVERRIDES: dict[str, list[str]] = {
    "어댑터": ["flyback", "llc"],
    "adapter": ["flyback", "llc"],
    "노트북": ["flyback", "llc"],
    "laptop": ["flyback", "llc"],
    "충전기": ["cc_cv_charger", "flyback"],
    "charger": ["cc_cv_charger", "flyback"],
}

TOPOLOGY_METADATA: dict[str, dict] = {
    # DC-DC non-isolated
    "buck": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "switching_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["voltage_regulator", "power_supply", "led_driver"],
        "power_range": "any",
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
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": False,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["pv_frontend", "power_supply"],
        "power_range": "any",
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요? (예: 12V)",
            "vout_target": "목표 출력 전압은 몇 V인가요? (예: 48V)",
        },
    },
    "buck_boost": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "switching_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["battery_system", "power_supply"],
        "power_range": "any",
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
        "isolated": True,
        "single_voltage_role": "vout_target",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["adapter", "auxiliary_supply", "charger", "power_supply"],
        "power_range": "low",
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
        "isolated": True,
        "single_voltage_role": "vout_target",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["telecom", "industrial_supply"],
        "power_range": "medium",
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
        },
    },
    "llc": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "isolated": True,
        "single_voltage_role": "vout_target",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["server_psu", "ev_charger", "adapter", "high_efficiency"],
        "power_range": "high",
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
        "isolated": True,
        "single_voltage_role": "vin",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": True,
        "supports_bidirectional": True,
        "typical_use_cases": ["ev_charger", "energy_storage", "v2g", "microgrid"],
        "power_range": "high",
        "slot_questions": {
            "vin": "1차측 전압은 몇 V인가요?",
            "vout_target": "2차측 전압은 몇 V인가요?",
        },
    },
    "push_pull": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout"],
        "isolated": True,
        "single_voltage_role": "vout_target",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["low_voltage_bus", "power_supply"],
        "power_range": "medium",
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
        },
    },
    "phase_shifted_full_bridge": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "isolated": True,
        "single_voltage_role": "vout_target",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["server_psu", "telecom", "high_power"],
        "power_range": "high",
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
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_ac",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["ups", "inverter"],
        "power_range": "medium",
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 400V)",
            "load_resistance": "부하 저항은 몇 Ω인가요?",
        },
    },
    "full_bridge": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance", "switching_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_ac",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["ups", "inverter", "welding"],
        "power_range": "medium",
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 400V)",
        },
    },
    "three_phase_inverter": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance", "switching_frequency", "output_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_ac",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["motor_drive", "grid_inverter"],
        "power_range": "high",
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 600V)",
            "output_frequency": "출력 주파수는? (기본: 60Hz)",
        },
    },
    "three_level_npc": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance", "switching_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_ac",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["motor_drive", "grid_inverter", "medium_voltage"],
        "power_range": "high",
        "slot_questions": {
            "vin": "DC bus 전압(총)은 몇 V인가요? (예: 800V, 분할 사용)",
        },
    },
    # AC-DC
    "diode_bridge_rectifier": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["load_resistance"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "ac_dc",
        "input_domain": "ac",
        "output_domain": "dc",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["rectification", "power_supply_frontend"],
        "power_range": "any",
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요? (예: 220V)",
        },
    },
    "thyristor_rectifier": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "load_resistance"],
        "optional_fields": ["firing_angle", "load_resistance"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "ac_dc",
        "input_domain": "ac",
        "output_domain": "dc",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["dc_motor_drive", "industrial"],
        "power_range": "high",
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요?",
        },
    },
    # PFC
    "boost_pfc": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "power_rating"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "pfc",
        "input_domain": "ac",
        "output_domain": "dc",
        "supports_step_down": False,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["pfc", "power_supply_frontend"],
        "power_range": "any",
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요? (예: 220V)",
            "power_rating": "정격 전력은 얼마인가요?",
        },
    },
    "totem_pole_pfc": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin", "power_rating"],
        "optional_fields": ["power_rating", "switching_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "pfc",
        "input_domain": "ac",
        "output_domain": "dc",
        "supports_step_down": False,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["pfc", "high_efficiency"],
        "power_range": "medium",
        "slot_questions": {
            "vin": "AC 입력 전압은 몇 V인가요?",
        },
    },
    # Renewable
    "pv_mppt_boost": {
        "required_fields": [],
        "design_ready_fields": ["voc", "isc"],
        "optional_fields": ["vmp", "imp"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "renewable",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": False,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["solar", "mppt", "renewable"],
        "power_range": "any",
        "slot_questions": {
            "voc": "태양광 패널 개방전압(Voc)은? (예: 40V)",
            "isc": "단락전류(Isc)는? (예: 10A)",
        },
    },
    "pv_grid_tied": {
        "required_fields": [],
        "design_ready_fields": [],
        "optional_fields": ["voc", "grid_voltage"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "renewable",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["solar", "grid_tied", "renewable"],
        "power_range": "any",
        "slot_questions": {},
    },
    # Motor drives
    "bldc_drive": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin"],
        "optional_fields": ["motor_poles", "rated_speed"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "drive",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["motor_drive", "drone", "ebike"],
        "power_range": "medium",
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 48V)",
        },
    },
    "pmsm_foc_drive": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin"],
        "optional_fields": ["motor_poles", "rated_speed", "rated_torque"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "drive",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["motor_drive", "servo", "ev_traction"],
        "power_range": "high",
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 300V)",
        },
    },
    "induction_motor_vf": {
        "required_fields": ["vin"],
        "design_ready_fields": ["vin"],
        "optional_fields": ["motor_poles", "rated_speed"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "drive",
        "input_domain": "dc",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["motor_drive", "fan", "pump", "vfd"],
        "power_range": "high",
        "slot_questions": {
            "vin": "DC bus 전압은 몇 V인가요? (예: 540V)",
        },
    },
    # Battery
    "cc_cv_charger": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout", "battery_capacity"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "battery",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["battery_charger", "charger"],
        "power_range": "medium",
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
        "isolated": True,
        "single_voltage_role": "vin",
        "conversion_type": "battery",
        "input_domain": "ac",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["ev_charger", "charger"],
        "power_range": "high",
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
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "filter",
        "input_domain": "ac",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["filter", "output_filter"],
        "power_range": "any",
        "slot_questions": {},
    },
    "lcl_filter": {
        "required_fields": [],
        "design_ready_fields": [],
        "optional_fields": ["cutoff_frequency", "grid_frequency"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "filter",
        "input_domain": "ac",
        "output_domain": "ac",
        "supports_step_down": False,
        "supports_step_up": False,
        "supports_bidirectional": False,
        "typical_use_cases": ["filter", "grid_filter"],
        "power_range": "any",
        "slot_questions": {},
    },
    # Bidirectional
    "bidirectional_buck_boost": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["power_rating"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": True,
        "supports_bidirectional": True,
        "typical_use_cases": ["battery_interface", "energy_storage", "v2g"],
        "power_range": "medium",
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
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["low_ripple", "power_supply"],
        "power_range": "low",
        "slot_questions": {
            "vin": "입력 전압은 몇 V인가요?",
            "vout_target": "출력 전압은 몇 V인가요?",
        },
    },
    "sepic": {
        "required_fields": ["vin", "vout_target"],
        "design_ready_fields": ["vin", "vout_target"],
        "optional_fields": ["iout"],
        "isolated": False,
        "single_voltage_role": "vin",
        "conversion_type": "dc_dc",
        "input_domain": "dc",
        "output_domain": "dc",
        "supports_step_down": True,
        "supports_step_up": True,
        "supports_bidirectional": False,
        "typical_use_cases": ["automotive", "led_driver", "battery_charger"],
        "power_range": "low",
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


def is_isolated(topology: str) -> bool:
    """Return True if the topology uses galvanic isolation."""
    meta = get_topology_metadata(topology)
    return meta.get("isolated", False) if meta else False


def get_single_voltage_role(topology: str) -> str:
    """Return the default role for a single voltage: 'vin' or 'vout_target'."""
    meta = get_topology_metadata(topology)
    return meta.get("single_voltage_role", "vin") if meta else "vin"


def get_isolated_topologies() -> set[str]:
    """Return set of all isolated topology names (derived from metadata)."""
    return {name for name, meta in TOPOLOGY_METADATA.items() if meta.get("isolated")}


def get_non_isolated_topologies() -> set[str]:
    """Return set of all non-isolated topology names (derived from metadata)."""
    return {name for name, meta in TOPOLOGY_METADATA.items() if not meta.get("isolated")}


def get_priority_overrides() -> dict[str, list[str]]:
    """Return descriptive-request priority overrides for the parser."""
    return PRIORITY_OVERRIDES
