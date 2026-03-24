"""Design rule registry -- topology-specific sizing and feasibility rules.

Source of truth for:
- Sizing formula references per topology
- Default design values
- Feasibility rules (e.g., vout < vin for buck)
- Forbidden parameter combinations

The actual formulas live in ``synthesis/sizing.py``; this module only records
*what* exists so that tooling, validation, and introspection layers can query
capabilities without importing the math.
"""

from __future__ import annotations

DESIGN_RULES: dict[str, dict] = {
    # ---- DC-DC non-isolated ------------------------------------------------
    "buck": {
        "sizing_function": "psim_mcp.synthesis.sizing.size_buck",
        "sizing_rules": ["buck_duty", "buck_inductor", "buck_capacitor", "buck_load"],
        "feasibility_rules": [
            {"rule": "vout_less_than_vin", "check": "vout_target < vin", "message": "Buck: vout must be less than vin"},
        ],
        "default_design_values": {
            "fsw": 50_000,
            "ripple_ratio": 0.3,
            "voltage_ripple_ratio": 0.01,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [
            {"condition": "isolated == True", "message": "Buck topology cannot be isolated"},
        ],
    },
    "boost": {
        "sizing_function": "psim_mcp.synthesis.sizing.size_boost",
        "sizing_rules": ["boost_duty", "boost_inductor", "boost_capacitor", "boost_load"],
        "feasibility_rules": [
            {"rule": "vout_greater_than_vin", "check": "vout_target > vin", "message": "Boost: vout must be greater than vin"},
        ],
        "default_design_values": {
            "fsw": 50_000,
            "ripple_ratio": 0.3,
            "voltage_ripple_ratio": 0.01,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [
            {"condition": "isolated == True", "message": "Boost topology cannot be isolated"},
        ],
    },
    "buck_boost": {
        "sizing_function": "psim_mcp.synthesis.sizing.size_buck_boost",
        "sizing_rules": ["buck_boost_duty", "buck_boost_inductor", "buck_boost_capacitor", "buck_boost_load"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 50_000,
            "ripple_ratio": 0.3,
            "voltage_ripple_ratio": 0.01,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [
            {"condition": "isolated == True", "message": "Buck-boost topology cannot be isolated"},
        ],
    },
    # ---- DC-DC isolated ----------------------------------------------------
    "flyback": {
        "sizing_function": "psim_mcp.synthesis.sizing.size_flyback",
        "sizing_rules": ["flyback_turns_ratio", "flyback_duty", "flyback_magnetizing_inductance", "flyback_capacitor", "flyback_load"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 100_000,
            "ripple_ratio": 0.3,
            "voltage_ripple_ratio": 0.01,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    "forward": {
        "sizing_function": None,
        "sizing_rules": ["forward_turns_ratio", "forward_duty", "forward_inductor", "forward_capacitor"],
        "feasibility_rules": [
            {"rule": "vout_less_than_vin_times_n", "check": "vout_target < vin * n", "message": "Forward: vout must be less than vin * turns_ratio"},
        ],
        "default_design_values": {
            "fsw": 100_000,
            "ripple_ratio": 0.3,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    "llc": {
        "sizing_function": "psim_mcp.synthesis.sizing.size_llc",
        "sizing_rules": ["llc_turns_ratio", "llc_resonant_inductor", "llc_resonant_capacitor", "llc_magnetizing_inductance", "llc_output_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 100_000,
            "quality_factor": 6.0,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    "dab": {
        "sizing_function": None,
        "sizing_rules": ["dab_turns_ratio", "dab_inductor", "dab_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 100_000,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    "push_pull": {
        "sizing_function": None,
        "sizing_rules": ["push_pull_turns_ratio", "push_pull_inductor", "push_pull_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 50_000,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    "phase_shifted_full_bridge": {
        "sizing_function": None,
        "sizing_rules": ["psfb_turns_ratio", "psfb_inductor", "psfb_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 100_000,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    # ---- DC-AC inverters ---------------------------------------------------
    "half_bridge": {
        "sizing_function": None,
        "sizing_rules": ["half_bridge_output_voltage"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 20_000,
            "load_resistance": 10.0,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    "full_bridge": {
        "sizing_function": None,
        "sizing_rules": ["full_bridge_output_voltage"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 20_000,
            "load_resistance": 10.0,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    "three_phase_inverter": {
        "sizing_function": None,
        "sizing_rules": ["three_phase_modulation"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 10_000,
            "output_frequency": 60,
            "load_resistance": 10.0,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    "three_level_npc": {
        "sizing_function": None,
        "sizing_rules": ["npc_modulation"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 10_000,
            "load_resistance": 10.0,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    # ---- AC-DC -------------------------------------------------------------
    "diode_bridge_rectifier": {
        "sizing_function": None,
        "sizing_rules": ["rectifier_output_voltage"],
        "feasibility_rules": [],
        "default_design_values": {
            "load_resistance": 100.0,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    "thyristor_rectifier": {
        "sizing_function": None,
        "sizing_rules": ["thyristor_output_voltage"],
        "feasibility_rules": [],
        "default_design_values": {
            "firing_angle": 30,
            "load_resistance": 100.0,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    # ---- PFC ---------------------------------------------------------------
    "boost_pfc": {
        "sizing_function": None,
        "sizing_rules": ["pfc_inductor", "pfc_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 65_000,
            "power_rating": 500,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    "totem_pole_pfc": {
        "sizing_function": None,
        "sizing_rules": ["totem_pole_inductor", "totem_pole_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 65_000,
            "power_rating": 500,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    # ---- Renewable ---------------------------------------------------------
    "pv_mppt_boost": {
        "sizing_function": None,
        "sizing_rules": ["mppt_inductor", "mppt_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 50_000,
        },
        "required_constraints": [],
        "forbidden_combinations": [],
    },
    "pv_grid_tied": {
        "sizing_function": None,
        "sizing_rules": [],
        "feasibility_rules": [],
        "default_design_values": {},
        "required_constraints": [],
        "forbidden_combinations": [],
    },
    # ---- Motor drives ------------------------------------------------------
    "bldc_drive": {
        "sizing_function": None,
        "sizing_rules": ["bldc_gate_timing"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 20_000,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    "pmsm_foc_drive": {
        "sizing_function": None,
        "sizing_rules": ["foc_current_loop", "foc_speed_loop"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 10_000,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    "induction_motor_vf": {
        "sizing_function": None,
        "sizing_rules": ["vf_curve"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 10_000,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    # ---- Battery -----------------------------------------------------------
    "cc_cv_charger": {
        "sizing_function": None,
        "sizing_rules": ["charger_inductor", "charger_capacitor", "charger_load"],
        "feasibility_rules": [
            {"rule": "vout_less_than_vin", "check": "vout_target < vin", "message": "Charger: battery voltage must be less than input"},
        ],
        "default_design_values": {
            "fsw": 50_000,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    "ev_obc": {
        "sizing_function": None,
        "sizing_rules": ["obc_pfc_stage", "obc_dcdc_stage"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 65_000,
            "power_rating": 6600,
        },
        "required_constraints": ["vin"],
        "forbidden_combinations": [],
    },
    # ---- Filters -----------------------------------------------------------
    "lc_filter": {
        "sizing_function": None,
        "sizing_rules": ["lc_cutoff"],
        "feasibility_rules": [],
        "default_design_values": {},
        "required_constraints": [],
        "forbidden_combinations": [],
    },
    "lcl_filter": {
        "sizing_function": None,
        "sizing_rules": ["lcl_cutoff"],
        "feasibility_rules": [],
        "default_design_values": {},
        "required_constraints": [],
        "forbidden_combinations": [],
    },
    # ---- Bidirectional -----------------------------------------------------
    "bidirectional_buck_boost": {
        "sizing_function": None,
        "sizing_rules": ["bidir_inductor", "bidir_capacitor"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 50_000,
            "power_rating": 500,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    # ---- Misc --------------------------------------------------------------
    "cuk": {
        "sizing_function": None,
        "sizing_rules": ["cuk_inductors", "cuk_capacitors"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 50_000,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
    "sepic": {
        "sizing_function": None,
        "sizing_rules": ["sepic_inductors", "sepic_capacitors"],
        "feasibility_rules": [],
        "default_design_values": {
            "fsw": 50_000,
            "iout": 1.0,
        },
        "required_constraints": ["vin", "vout_target"],
        "forbidden_combinations": [],
    },
}


def get_design_rules(topology: str) -> dict:
    """Return design rules for *topology*, or empty dict if unknown."""
    return DESIGN_RULES.get(topology.lower(), {})


def get_default_values(topology: str) -> dict:
    """Return default design values for *topology*."""
    rules = get_design_rules(topology)
    return dict(rules.get("default_design_values", {}))


def get_feasibility_rules(topology: str) -> list:
    """Return feasibility rules for *topology*."""
    rules = get_design_rules(topology)
    return list(rules.get("feasibility_rules", []))
