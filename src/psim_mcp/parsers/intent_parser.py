"""Main intent parser: extract topology and specifications from natural language."""

from __future__ import annotations

import re

from psim_mcp.data.topology_metadata import get_design_ready_fields, get_required_fields, get_slot_questions
from psim_mcp.parsers.keyword_map import (
    SLOT_QUESTIONS,
    TOPOLOGY_KEYWORDS,
    USE_CASE_MAP,
)
from psim_mcp.parsers.unit_parser import extract_values

# ---------------------------------------------------------------------------
# Canonical field name aliases — parser outputs short names,
# but generators/metadata may use longer names.
# When checking missing_fields, we match against all aliases.
# ---------------------------------------------------------------------------

FIELD_ALIASES: dict[str, list[str]] = {
    "vin": ["vin"],
    "vout_target": ["vout_target", "vout"],
    "iout": ["iout", "iout_target"],
    "fsw": ["fsw", "switching_frequency"],
    "r_load": ["r_load", "load_resistance"],
    "inductance": ["inductance"],
    "capacitance": ["capacitance"],
    "power_rating": ["power_rating"],
}

# Reverse: canonical name → parser field name
_CANONICAL_TO_PARSER: dict[str, str] = {}
for _parser_name, _aliases in FIELD_ALIASES.items():
    for _alias in _aliases:
        _CANONICAL_TO_PARSER[_alias] = _parser_name


def _match_topology(text: str) -> tuple[str | None, list[str]]:
    """Match topology keywords against *text* (case-insensitive).

    Returns (best_match, all_candidates).  Longest keyword match wins.
    """
    text_lower = text.lower()
    matches: list[tuple[str, str]] = []  # (topology_name, matched_keyword)

    for topo, keywords in TOPOLOGY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                matches.append((topo, kw))

    if not matches:
        return None, []

    # Sort by keyword length descending (longest match first)
    matches.sort(key=lambda x: len(x[1]), reverse=True)

    # Deduplicate topology names while preserving order
    seen: set[str] = set()
    candidates: list[str] = []
    for topo, _kw in matches:
        if topo not in seen:
            seen.add(topo)
            candidates.append(topo)

    best = candidates[0]
    return best, candidates


def _match_use_case(text: str) -> tuple[str | None, list[str]]:
    """Try to match a use-case keyword and return suggested topologies."""
    text_lower = text.lower()
    for use_case, topologies in USE_CASE_MAP.items():
        if use_case.lower() in text_lower:
            return use_case, topologies
    return None, []


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


def _find_voltage_contexts(text: str) -> list[tuple[float, str | None]]:
    """Find voltages in *text* along with contextual role hints.

    Returns list of (value, role) where role is 'vin', 'vout_target', or None.
    """
    from psim_mcp.parsers.unit_parser import _FULL_PATTERN, _resolve_prefix, _resolve_category

    results: list[tuple[float, str | None]] = []

    for m in _FULL_PATTERN.finditer(text):
        unit_str = m.group("unit")
        category = _resolve_category(unit_str)
        if category != "voltage":
            continue

        number = float(m.group("number"))
        prefix = m.group("prefix")
        from psim_mcp.parsers.unit_parser import _resolve_prefix as _rp
        multiplier = _rp(prefix)
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


def _map_values_to_specs(
    values: dict[str, list[float]],
    text: str = "",
) -> tuple[dict[str, float], list[float], str]:
    """Map extracted values to circuit spec fields with context awareness.

    Returns (specs, unassigned_voltages, mapping_confidence).

    Context-aware voltage mapping:
    - Words like "입력", "input", "source", "bus" near a voltage -> vin
    - Words like "출력", "output", "target", "목표" -> vout_target
    - If context is ambiguous, fall back to size-based heuristic with
      confidence "medium"
    - If 3+ voltages with no context, return them as unassigned_voltages
      with confidence "low"
    """
    specs: dict[str, float] = {}
    unassigned_voltages: list[float] = []
    mapping_confidence = "high"

    # --- Voltage mapping (context-aware) ---
    voltages = values.get("voltage", [])

    if voltages and text:
        voltage_contexts = _find_voltage_contexts(text)

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
                unassigned_voltages = no_context
                mapping_confidence = "low"
            else:
                # Sort descending; assign largest remaining to vin, next to vout
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
                    else:
                        unassigned_voltages.append(v)
        elif not vin_assigned and not vout_assigned and not no_context:
            # All voltages were assigned via context -- confidence stays high
            pass

    elif voltages:
        # No text provided -- pure size-based fallback (backward compat)
        if len(voltages) >= 2:
            v_sorted = sorted(voltages, reverse=True)
            specs["vin"] = v_sorted[0]
            specs["vout_target"] = v_sorted[1]
            if len(voltages) > 2:
                unassigned_voltages = v_sorted[2:]
                mapping_confidence = "medium"
        elif len(voltages) == 1:
            specs["vin"] = voltages[0]

    # --- Non-voltage mappings (unchanged) ---
    currents = values.get("current", [])
    if currents:
        specs["iout"] = currents[0]

    # --- Frequency mapping (context-aware) ---
    frequencies = values.get("frequency", [])
    if frequencies and text:
        # If only 1 frequency, assign to fsw
        if len(frequencies) == 1:
            specs["fsw"] = frequencies[0]
        elif len(frequencies) >= 2:
            # Sort: higher likely switching, lower likely output
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
        # PV parameters: "Voc 40V" "Isc 10A" "Vmp 32V" "Imp 9A"
        voc_match = re.search(r'[Vv]oc\s*[=:]?\s*(\d+\.?\d*)', text)
        if voc_match:
            specs["voc"] = float(voc_match.group(1))

        isc_match = re.search(r'[Ii]sc\s*[=:]?\s*(\d+\.?\d*)', text)
        if isc_match:
            specs["isc"] = float(isc_match.group(1))

        vmp_match = re.search(r'[Vv]mp\s*[=:]?\s*(\d+\.?\d*)', text)
        if vmp_match:
            specs["vmp"] = float(vmp_match.group(1))

        imp_match = re.search(r'[Ii]mp\s*[=:]?\s*(\d+\.?\d*)', text)
        if imp_match:
            specs["imp"] = float(imp_match.group(1))

        # Grid voltage: "계통 220V", "grid 220V"
        grid_match = re.search(r'(계통|grid)\s*(\d+\.?\d*)\s*V', text, re.IGNORECASE)
        if grid_match:
            specs["grid_voltage"] = float(grid_match.group(2))

    return specs, unassigned_voltages, mapping_confidence


def _get_required_fields_for(topology: str) -> list[str]:
    """Get required fields from generator or topology metadata."""
    # Try generator first
    try:
        from psim_mcp.generators import get_generator

        gen = get_generator(topology)
        return gen.required_fields
    except (KeyError, Exception):
        pass
    # Fall back to topology metadata
    return get_required_fields(topology)


def _get_questions_for(topology: str, missing_fields: list[str]) -> list[str]:
    """Generate topology-aware questions for missing fields."""
    topo_questions = get_slot_questions(topology)

    questions = []
    for field in missing_fields:
        # Prefer topology-specific question
        q = topo_questions.get(field)
        if not q:
            # Fall back to generic
            q = SLOT_QUESTIONS.get(field, f"{field}을(를) 지정해주세요.")
        questions.append(q)
    return questions


def _apply_topology_specific_postprocess(
    topology: str | None,
    use_case: str | None,
    specs: dict[str, float],
    values: dict[str, list[float]],
    description: str,
) -> dict[str, float]:
    """Adjust generic parser output for topology/use-case specific semantics."""
    fixed = dict(specs)

    adapter_like_use_cases = {"어댑터", "adapter", "노트북", "laptop", "보조전원", "auxiliary"}
    if (
        use_case in adapter_like_use_cases
        and "vin" in fixed
        and "vout_target" not in fixed
        and len(values.get("voltage", [])) == 1
        and not _VIN_CONTEXT.search(description)
        and not _VOUT_CONTEXT.search(description)
    ):
        fixed["vout_target"] = fixed.pop("vin")

    if topology in {"pv_mppt_boost", "pv_grid_tied"}:
        if "voc" in fixed and fixed.get("vin") == fixed["voc"]:
            fixed.pop("vin", None)
        if "isc" in fixed and fixed.get("iout") == fixed["isc"]:
            fixed.pop("iout", None)
        if "imp" in fixed and fixed.get("iout") == fixed["imp"]:
            fixed.pop("iout", None)

    return fixed


# Keep old functions as thin wrappers for backward compatibility
def _get_required_fields(topology: str) -> list[str]:
    """Return required fields for a topology.

    .. deprecated:: Use :func:`_get_required_fields_for` instead.
    """
    return _get_required_fields_for(topology)


def parse_circuit_intent(description: str) -> dict:
    """Parse a natural language circuit description.

    Parameters
    ----------
    description:
        Free-form text describing a circuit, e.g.
        ``"Buck converter 48V input 12V output 5A load"``

    Returns
    -------
    dict with keys:
        topology, topology_candidates, specs, missing_fields,
        questions, confidence, use_case
        Optionally includes ``unassigned_voltages`` when voltage mapping
        is ambiguous.
    """
    # 1. Extract numeric values with units
    values = extract_values(description)

    # 2. Match topology keywords
    topology, candidates = _match_topology(description)

    # 3. If no topology match, try use-case matching
    use_case = None
    if not topology:
        use_case, use_case_candidates = _match_use_case(description)
        if use_case_candidates:
            candidates = use_case_candidates
            topology = use_case_candidates[0]

    # 4. Map extracted values to specs (context-aware)
    specs, unassigned_voltages, mapping_confidence = _map_values_to_specs(
        values, description,
    )
    specs = _apply_topology_specific_postprocess(topology, use_case, specs, values, description)

    # 5. Determine missing fields
    missing_fields: list[str] = []
    if topology:
        required = _get_required_fields_for(topology)
        missing_fields = []
        for f in required:
            # Check if any alias of this field is in specs
            parser_name = _CANONICAL_TO_PARSER.get(f, f)
            if parser_name not in specs and f not in specs:
                missing_fields.append(f)

    # 6. Generate topology-aware questions for missing fields
    questions: list[str] = []
    if topology and missing_fields:
        questions = _get_questions_for(topology, missing_fields)
    else:
        questions = [
            SLOT_QUESTIONS.get(f, f"{f}을(를) 지정해주세요.")
            for f in missing_fields
        ]

    # 7. Check design readiness (stricter than required_fields)
    design_fields = get_design_ready_fields(topology) if topology else []
    design_missing = [
        f for f in design_fields
        if _CANONICAL_TO_PARSER.get(f, f) not in specs and f not in specs
    ]

    # Determine confidence
    if topology and not missing_fields and not design_missing:
        confidence = "high"
    elif topology and not missing_fields:
        confidence = "medium"  # intent clear but not design-ready
    elif topology and len(missing_fields) <= 1:
        confidence = "medium"
    else:
        confidence = "low"

    # Lower confidence if voltage mapping was uncertain
    if mapping_confidence == "low":
        confidence = "low"
    elif mapping_confidence == "medium" and confidence == "high":
        confidence = "medium"

    # Normalize specs to canonical field names for downstream consumers
    normalized_specs = {}
    _NORMALIZE_MAP = {
        "iout": "iout",          # keep as-is (generators use this)
        "fsw": "switching_frequency",  # normalize to long form
        "r_load": "load_resistance",   # normalize to long form
    }
    for k, v in specs.items():
        canonical = _NORMALIZE_MAP.get(k, k)
        normalized_specs[canonical] = v
        if canonical != k:
            normalized_specs[k] = v  # keep short name too for backward compat

    result: dict = {
        "topology": topology,
        "topology_candidates": candidates,
        "specs": specs,
        "normalized_specs": normalized_specs,
        "missing_fields": missing_fields,
        "questions": questions,
        "confidence": confidence,
        "use_case": use_case,
    }

    if unassigned_voltages:
        result["unassigned_voltages"] = unassigned_voltages

    return result
