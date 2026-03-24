"""Capability matrix -- tracks which pipeline stages each topology supports.

Each topology maps to a dict of pipeline stage names and their status:
- ``"new"``: fully supported by the new graph/layout/routing pipeline
- ``"legacy"``: supported by legacy template-based pipeline
- ``"none"``: not yet implemented

This allows tooling and service layers to make informed decisions about
which code path to use for each topology.
"""

from __future__ import annotations

CAPABILITY_MATRIX: dict[str, dict[str, str]] = {
    # ---- DC-DC non-isolated ------------------------------------------------
    "buck": {
        "synthesize": "new",
        "graph": "new",
        "layout": "new",
        "routing": "new",
        "design_circuit": "new",
        "preview_generator": "new",
        "preview_template": "legacy",
        "confirm": "new",
        "create_direct": "new",
        "simulation_service": "legacy",
    },
    "boost": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "buck_boost": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- DC-DC isolated ----------------------------------------------------
    "flyback": {
        "synthesize": "new",
        "graph": "new",
        "layout": "new",
        "routing": "new",
        "design_circuit": "new",
        "preview_generator": "new",
        "preview_template": "legacy",
        "confirm": "new",
        "create_direct": "new",
        "simulation_service": "legacy",
    },
    "forward": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "llc": {
        "synthesize": "new",
        "graph": "new",
        "layout": "new",
        "routing": "new",
        "design_circuit": "new",
        "preview_generator": "new",
        "preview_template": "legacy",
        "confirm": "new",
        "create_direct": "new",
        "simulation_service": "legacy",
    },
    "dab": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "push_pull": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "phase_shifted_full_bridge": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- DC-AC inverters ---------------------------------------------------
    "half_bridge": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "full_bridge": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "three_phase_inverter": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "three_level_npc": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- AC-DC -------------------------------------------------------------
    "diode_bridge_rectifier": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "thyristor_rectifier": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- PFC ---------------------------------------------------------------
    "boost_pfc": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "totem_pole_pfc": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- Renewable ---------------------------------------------------------
    "pv_mppt_boost": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "pv_grid_tied": {
        "synthesize": "none",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- Motor drives ------------------------------------------------------
    "bldc_drive": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "pmsm_foc_drive": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "induction_motor_vf": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- Battery -----------------------------------------------------------
    "cc_cv_charger": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "ev_obc": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- Filters -----------------------------------------------------------
    "lc_filter": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "lcl_filter": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- Bidirectional -----------------------------------------------------
    "bidirectional_buck_boost": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    # ---- Misc --------------------------------------------------------------
    "cuk": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
    "sepic": {
        "synthesize": "legacy",
        "graph": "none",
        "layout": "none",
        "routing": "none",
        "design_circuit": "legacy",
        "preview_generator": "legacy",
        "preview_template": "legacy",
        "confirm": "legacy",
        "create_direct": "legacy",
        "simulation_service": "legacy",
    },
}


def get_capability(topology: str, stage: str) -> str:
    """Return the capability status for a topology's pipeline stage.

    Returns ``"none"`` if the topology or stage is not registered.
    """
    topo = CAPABILITY_MATRIX.get(topology.lower(), {})
    return topo.get(stage, "none")


def supports_new_pipeline(topology: str) -> bool:
    """Return True if the topology supports the full new pipeline.

    A topology supports the new pipeline if synthesize, graph, layout,
    and routing are all ``"new"``.
    """
    topo = CAPABILITY_MATRIX.get(topology.lower(), {})
    return all(
        topo.get(stage) == "new"
        for stage in ("synthesize", "graph", "layout", "routing")
    )


def get_new_pipeline_topologies() -> list[str]:
    """Return list of topology names that support the full new pipeline."""
    return [
        name for name in CAPABILITY_MATRIX
        if supports_new_pipeline(name)
    ]


def get_supported_topologies(feature: str) -> list[str]:
    """Return list of topologies that have 'new' status for *feature*."""
    return [
        topo for topo, caps in CAPABILITY_MATRIX.items()
        if caps.get(feature) == "new"
    ]


def is_supported(topology: str, feature: str) -> bool:
    """Return True if *topology* has 'new' status for *feature*."""
    return get_capability(topology, feature) == "new"
