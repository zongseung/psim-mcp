"""Main intent parser: extract topology and specifications from natural language."""

from __future__ import annotations

from psim_mcp.parsers.keyword_map import (
    SLOT_QUESTIONS,
    TOPOLOGY_KEYWORDS,
    USE_CASE_MAP,
)
from psim_mcp.parsers.unit_parser import extract_values


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


def _map_values_to_specs(values: dict[str, list[float]]) -> dict[str, float]:
    """Map extracted values to circuit spec fields.

    Heuristics:
    - Voltages sorted descending: largest -> vin, second -> vout_target
    - First current -> iout
    - First frequency -> fsw
    - First resistance -> r_load
    - First inductance -> inductance
    - First capacitance -> capacitance
    - First power -> power_rating
    """
    specs: dict[str, float] = {}

    voltages = values.get("voltage", [])
    if len(voltages) >= 2:
        v_sorted = sorted(voltages, reverse=True)
        specs["vin"] = v_sorted[0]
        specs["vout_target"] = v_sorted[1]
    elif len(voltages) == 1:
        specs["vin"] = voltages[0]

    currents = values.get("current", [])
    if currents:
        specs["iout"] = currents[0]

    frequencies = values.get("frequency", [])
    if frequencies:
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

    return specs


def _get_required_fields(topology: str) -> list[str]:
    """Return required fields for a topology if a generator exists."""
    try:
        from psim_mcp.generators import get_generator

        gen = get_generator(topology)
        return gen.required_fields
    except KeyError:
        # No generator for this topology; use sensible defaults
        return ["vin", "vout_target", "iout"]


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

    # 4. Map extracted values to specs
    specs = _map_values_to_specs(values)

    # 5. Determine missing fields
    missing_fields: list[str] = []
    if topology:
        required = _get_required_fields(topology)
        missing_fields = [f for f in required if f not in specs]

    # 6. Generate questions for missing fields
    questions = [
        SLOT_QUESTIONS.get(f, f"{f}\uc744(\ub97c) \uc9c0\uc815\ud574\uc8fc\uc138\uc694.")
        for f in missing_fields
    ]

    # 7. Determine confidence
    if topology and not missing_fields:
        confidence = "high"
    elif topology and len(missing_fields) <= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "topology": topology,
        "topology_candidates": candidates,
        "specs": specs,
        "missing_fields": missing_fields,
        "questions": questions,
        "confidence": confidence,
        "use_case": use_case,
    }
