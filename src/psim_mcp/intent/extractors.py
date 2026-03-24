"""Intent extraction -- extracts domain constraints and values from natural language.

This module is responsible for:
- Constraint extraction (input/output domain, isolation, conversion goal, use case)
- Value extraction (voltages, currents, frequencies, etc.)
- Voltage role hinting (context-aware vin/vout detection)

It does NOT:
- Decide the final topology
- Rank candidates
- Build canonical specs
"""

from __future__ import annotations

import re

from .models import IntentModel

# ---------------------------------------------------------------------------
# Constraint keyword patterns -- domain concepts, NOT topology names.
# ---------------------------------------------------------------------------

_CONSTRAINT_PATTERNS: dict[str, dict] = {
    "input_domain": {
        "ac": re.compile(r"(ac|교류|mains|벽전원|상용전원|220v|110v)", re.I),
        "dc": re.compile(r"(dc|직류|dc\s*bus|배터리|battery|pv|태양광|solar)", re.I),
    },
    "output_domain": {
        "ac": re.compile(r"(ac\s*출력|교류\s*출력|인버|inverter|모터|motor)", re.I),
        "dc": re.compile(r"(dc\s*출력|직류\s*출력|충전|charg|어댑터|adapter|전원)", re.I),
    },
    "isolation": {
        False: re.compile(r"(비절연|non.isolated)", re.I),
        True: re.compile(r"(절연|isolated|갈바닉|galvanic)", re.I),
    },
    "conversion_goal": {
        "step_down": re.compile(r"(강압|step.down|낮추|줄이|감소|저전압)", re.I),
        "step_up": re.compile(r"(승압|step.up|높이|올리|부스트|boost|증가|고전압)", re.I),
        "rectification": re.compile(r"(정류|rectif|교류를\s*직류|ac\s*(to|를)\s*dc)", re.I),
        "inversion": re.compile(r"(인버|inver|직류를\s*교류|dc\s*(to|를)\s*ac|모터\s*구동)", re.I),
    },
    "use_case": {
        "charger": re.compile(r"(충전|charg|배터리)", re.I),
        "adapter": re.compile(r"(어댑터|adapter|노트북|laptop)", re.I),
        "auxiliary_supply": re.compile(r"(보조전원|auxiliary|aux)", re.I),
        "power_supply": re.compile(r"(전원|power\s*supply)", re.I),
        "motor_drive": re.compile(r"(모터|motor|드라이브|drive|서보|servo)", re.I),
        "pv_frontend": re.compile(r"(태양광|solar|pv|mppt)", re.I),
        "led_driver": re.compile(r"(led|조명)", re.I),
        "telecom": re.compile(r"(텔레콤|telecom|통신)", re.I),
        "pfc": re.compile(r"(역률|pfc|power\s*factor)", re.I),
        "filter": re.compile(r"(필터|filter|emi)", re.I),
    },
    "bidirectional": {
        True: re.compile(r"(양방향|bidirectional|v2g|v2h|충방전)", re.I),
    },
}

# ---------------------------------------------------------------------------
# Context keywords for voltage role detection
# ---------------------------------------------------------------------------

_VIN_CONTEXT = re.compile(
    r"(입력|input|source|bus|소스|1차|primary|dc\s*bus|공급)",
    re.IGNORECASE,
)
_VOUT_CONTEXT = re.compile(
    r"(출력|output|target|목표|2차|secondary|배터리|battery|부하측)",
    re.IGNORECASE,
)

_CONTEXT_WINDOW = 20  # characters to look around a voltage match


def extract_intent(text: str) -> IntentModel:
    """Extract structured intent from natural language text.

    Returns IntentModel with constraints, values, and voltage candidates.
    Does NOT select a topology.
    """
    from psim_mcp.parsers.unit_parser import extract_values

    # 1. Extract domain constraints
    constraints = _extract_constraints(text)

    # 2. Extract numeric values
    values_raw = extract_values(text)

    # 3. Map values to specs with voltage role detection
    specs, voltage_candidates, mapping_confidence = _map_values_with_context(values_raw, text)

    return IntentModel(
        input_domain=constraints.get("input_domain"),
        output_domain=constraints.get("output_domain"),
        conversion_goal=constraints.get("conversion_goal"),
        use_case=constraints.get("use_case"),
        isolation=constraints.get("isolation"),
        bidirectional=constraints.get("bidirectional"),
        values=specs,
        voltage_candidates=voltage_candidates,
        constraints=constraints,
        raw_text=text,
        mapping_confidence=mapping_confidence,
    )


def _extract_constraints(text: str) -> dict:
    """Extract design constraints from natural language text.

    Scans *text* for domain-level keywords (AC/DC, step-up/down, use-case,
    isolation, bidirectional) and returns a dict of matched constraints.
    """
    constraints: dict = {}

    for category, patterns in _CONSTRAINT_PATTERNS.items():
        for value, pattern in patterns.items():
            if pattern.search(text):
                if category == "bidirectional":
                    constraints["bidirectional"] = True
                else:
                    constraints[category] = value
                break  # first match per category

    return constraints


def _find_voltage_contexts(text: str) -> list[tuple[float, str | None]]:
    """Find voltages in *text* along with contextual role hints.

    Returns list of (value, role) where role is 'vin', 'vout_target', or None.
    """
    from psim_mcp.parsers.unit_parser import _FULL_PATTERN, _resolve_category, _resolve_prefix

    results: list[tuple[float, str | None]] = []

    for m in _FULL_PATTERN.finditer(text):
        unit_str = m.group("unit")
        category = _resolve_category(unit_str)
        if category != "voltage":
            continue

        number = float(m.group("number"))
        prefix = m.group("prefix")
        multiplier = _resolve_prefix(prefix)
        value = number * multiplier

        # Look at surrounding text for context clues
        start = max(0, m.start() - _CONTEXT_WINDOW)
        end = min(len(text), m.end() + _CONTEXT_WINDOW)
        window = text[start:end]

        role: str | None = None
        if _VIN_CONTEXT.search(window):
            role = "vin"
        elif _VOUT_CONTEXT.search(window):
            role = "vout_target"

        results.append((value, role))

    return results


def _map_values_with_context(
    values: dict[str, list[float]],
    text: str = "",
) -> tuple[dict[str, float], list[dict], str]:
    """Map extracted values to circuit spec fields with context awareness.

    Returns (specs, voltage_candidates, mapping_confidence).

    voltage_candidates is a list of dicts with 'value' and 'role_hint' keys,
    useful for downstream disambiguation.
    """
    specs: dict[str, float] = {}
    voltage_candidates: list[dict] = []
    mapping_confidence = "high"

    # --- Voltage mapping (context-aware) ---
    voltages = values.get("voltage", [])

    if voltages and text:
        voltage_contexts = _find_voltage_contexts(text)

        # Build voltage_candidates from contexts
        for v, role in voltage_contexts:
            voltage_candidates.append({"value": v, "role_hint": role})

        vin_assigned = False
        vout_assigned = False
        no_context: list[float] = []

        for v, role in voltage_contexts:
            if role == "vin" and not vin_assigned:
                specs["vin"] = v
                vin_assigned = True
            elif role == "vout_target" and not vout_assigned:
                specs["vout_target"] = v
                vout_assigned = True
            else:
                no_context.append(v)

        # Fall back to size-based heuristic for remaining unassigned voltages
        if no_context:
            if len(no_context) >= 3 and not vin_assigned and not vout_assigned:
                # Too many ambiguous voltages -- don't force assignment
                mapping_confidence = "low"
            else:
                no_context_sorted = sorted(no_context, reverse=True)
                for v in no_context_sorted:
                    if not vin_assigned:
                        specs["vin"] = v
                        vin_assigned = True
                        mapping_confidence = "medium"
                    elif not vout_assigned:
                        specs["vout_target"] = v
                        vout_assigned = True
                        mapping_confidence = "medium"

    elif voltages:
        # No text provided -- pure size-based fallback
        for v in voltages:
            voltage_candidates.append({"value": v, "role_hint": None})

        if len(voltages) >= 2:
            v_sorted = sorted(voltages, reverse=True)
            specs["vin"] = v_sorted[0]
            specs["vout_target"] = v_sorted[1]
            if len(voltages) > 2:
                mapping_confidence = "medium"
        elif len(voltages) == 1:
            specs["vin"] = voltages[0]

    # --- Non-voltage mappings ---
    currents = values.get("current", [])
    if currents:
        specs["iout"] = currents[0]

    # --- Frequency mapping (context-aware) ---
    frequencies = values.get("frequency", [])
    if frequencies and text:
        if len(frequencies) == 1:
            specs["fsw"] = frequencies[0]
        elif len(frequencies) >= 2:
            sorted_freq = sorted(frequencies, reverse=True)
            specs["fsw"] = sorted_freq[0]
            specs["output_frequency"] = sorted_freq[-1]
    elif frequencies:
        specs["fsw"] = frequencies[0]

    resistances = values.get("resistance", [])
    if resistances:
        specs["r_load"] = resistances[0]

    inductances = values.get("inductance", [])
    if inductances:
        specs["inductance"] = inductances[0]

    capacitances = values.get("capacitance", [])
    if capacitances:
        specs["capacitance"] = capacitances[0]

    powers = values.get("power", [])
    if powers:
        specs["power_rating"] = powers[0]

    # --- Topology-specific value detection ---
    if text:
        voc_match = re.search(r"[Vv]oc\s*[=:]?\s*(\d+\.?\d*)", text)
        if voc_match:
            specs["voc"] = float(voc_match.group(1))

        isc_match = re.search(r"[Ii]sc\s*[=:]?\s*(\d+\.?\d*)", text)
        if isc_match:
            specs["isc"] = float(isc_match.group(1))

        vmp_match = re.search(r"[Vv]mp\s*[=:]?\s*(\d+\.?\d*)", text)
        if vmp_match:
            specs["vmp"] = float(vmp_match.group(1))

        imp_match = re.search(r"[Ii]mp\s*[=:]?\s*(\d+\.?\d*)", text)
        if imp_match:
            specs["imp"] = float(imp_match.group(1))

        grid_match = re.search(r"(계통|grid)\s*(\d+\.?\d*)\s*V", text, re.IGNORECASE)
        if grid_match:
            specs["grid_voltage"] = float(grid_match.group(2))

    return specs, voltage_candidates, mapping_confidence
