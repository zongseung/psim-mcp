"""Topology keyword mapping and slot questions for intent parsing."""

from __future__ import annotations

TOPOLOGY_KEYWORDS: dict[str, list[str]] = {
    "buck": ["buck", "\ubc85", "\uac15\uc555", "step-down", "step down", "\uc2a4\ud15d\ub2e4\uc6b4"],
    "boost": ["boost", "\ubd80\uc2a4\ud2b8", "\uc2b9\uc555", "step-up", "step up", "\uc2a4\ud15d\uc5c5"],
    "buck_boost": ["buck-boost", "\ubc85\ubd80\uc2a4\ud2b8", "\ubc85-\ubd80\uc2a4\ud2b8", "buck boost"],
    "cuk": ["cuk", "\ucfe1"],
    "sepic": ["sepic"],
    "flyback": ["flyback", "\ud50c\ub77c\uc774\ubc31"],
    "forward": ["forward", "\ud3ec\uc6cc\ub4dc"],
    "push_pull": ["push-pull", "push pull", "\ud478\uc2dc\ud480"],
    "llc": ["llc", "\uacf5\uc9c4"],
    "dab": ["dab", "\ub4c0\uc5bc \uc561\ud2f0\ube0c \ube0c\ub9ac\uc9c0", "dual active bridge"],
    "phase_shifted_full_bridge": ["psfb", "\uc704\uc0c1 \ucc9c\uc774", "phase shift"],
    "half_bridge": ["half bridge", "\ud558\ud504 \ube0c\ub9ac\uc9c0", "\ud558\ud504\ube0c\ub9ac\uc9c0", "\ubc18\ube0c\ub9ac\uc9c0"],
    "full_bridge": ["full bridge", "\ud480 \ube0c\ub9ac\uc9c0", "\ud480\ube0c\ub9ac\uc9c0", "h-bridge", "h\ube0c\ub9ac\uc9c0"],
    "three_phase_inverter": ["3\uc0c1 \uc778\ubc84\ud130", "three phase inverter", "3-phase inverter", "\uc0bc\uc0c1 \uc778\ubc84\ud130"],
    "three_level_npc": ["3\ub808\ubca8", "npc", "three level", "3-level"],
    "diode_bridge_rectifier": ["\ub2e4\uc774\uc624\ub4dc \uc815\ub958", "diode bridge", "\ube0c\ub9ac\uc9c0 \uc815\ub958", "diode rectifier"],
    "thyristor_rectifier": ["\uc0ac\uc774\ub9ac\uc2a4\ud130 \uc815\ub958", "thyristor rectifier", "scr \uc815\ub958"],
    "boost_pfc": ["pfc", "\uc5ed\ub960\ubcf4\uc815", "\uc5ed\ub960 \ubcf4\uc815", "power factor"],
    "totem_pole_pfc": ["\ud1a0\ud15c\ud3f4", "totem pole", "totem-pole"],
    "pv_mppt_boost": ["mppt", "\ud0dc\uc591\uad11", "solar", "pv"],
    "pv_grid_tied": ["\uacc4\ud1b5\uc5f0\uacc4", "grid-tied", "grid tied", "\uacc4\ud1b5 \uc5f0\uacc4"],
    "bldc_drive": ["bldc", "brushless"],
    "pmsm_foc_drive": ["pmsm", "foc", "\ubca1\ud130 \uc81c\uc5b4", "vector control"],
    "induction_motor_vf": ["\uc720\ub3c4 \uc804\ub3d9\uae30", "induction motor", "v/f", "\uc720\ub3c4\uc804\ub3d9\uae30", "im \ub4dc\ub77c\uc774\ube0c"],
    "cc_cv_charger": ["\ucda9\uc804\uae30", "charger", "cc-cv", "cc cv", "\ubc30\ud130\ub9ac \ucda9\uc804"],
    "ev_obc": ["obc", "\uc628\ubcf4\ub4dc \ucda9\uc804", "ev \ucda9\uc804", "\uc804\uae30\ucc28 \ucda9\uc804"],
    "lc_filter": ["lc \ud544\ud130", "lc filter"],
    "lcl_filter": ["lcl \ud544\ud130", "lcl filter"],
    "bidirectional_buck_boost": ["\uc591\ubc29\ud5a5", "bidirectional", "v2g"],
}

USE_CASE_MAP: dict[str, list[str]] = {
    "\ucda9\uc804": ["cc_cv_charger", "ev_obc"],
    "\uc778\ubc84\ud130": ["half_bridge", "full_bridge", "three_phase_inverter"],
    "\ud0dc\uc591\uad11": ["pv_mppt_boost", "pv_grid_tied"],
    "\ubaa8\ud130": ["bldc_drive", "pmsm_foc_drive", "induction_motor_vf"],
    "\uc5ed\ub960": ["boost_pfc", "totem_pole_pfc"],
    "LED": ["buck", "flyback"],
    "\uc804\uc6d0": ["buck", "boost", "flyback"],
    "\uc815\ub958": ["diode_bridge_rectifier", "thyristor_rectifier"],
    "\ubc30\ud130\ub9ac": ["cc_cv_charger", "bidirectional_buck_boost"],
    "EV": ["ev_obc", "pmsm_foc_drive", "bidirectional_buck_boost"],
}

SLOT_QUESTIONS: dict[str, str] = {
    "vin": "\uc785\ub825 \uc804\uc555\uc740 \uba87 V\uc778\uac00\uc694? (\uc608: 48V)",
    "vout_target": "\ubaa9\ud45c \ucd9c\ub825 \uc804\uc555\uc740 \uba87 V\uc778\uac00\uc694? (\uc608: 12V)",
    "iout_target": "\ucd9c\ub825 \uc804\ub958(\ubd80\ud558)\ub294 \uba87 A\uc778\uac00\uc694? (\uc608: 5A)",
    "switching_frequency": "\uc2a4\uc704\uce6d \uc8fc\ud30c\uc218\ub97c \uc9c0\uc815\ud558\uc2dc\uaca0\uc5b4\uc694? (\uae30\ubcf8: 50kHz)",
    "power_rating": "\uc815\uaca9 \uc804\ub825\uc740 \uc5bc\ub9c8\uc778\uac00\uc694? (\uc608: 1kW)",
}
