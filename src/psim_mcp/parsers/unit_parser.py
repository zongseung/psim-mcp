"""Extract numeric values with SI units from natural language text."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# SI prefix multipliers
# ---------------------------------------------------------------------------

_SI_PREFIX: dict[str, float] = {
    "p": 1e-12,
    "n": 1e-9,
    "\u03bc": 1e-6,  # Greek mu
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
}

# ---------------------------------------------------------------------------
# Unit definitions: (category, base_unit_aliases, korean_aliases)
# ---------------------------------------------------------------------------

# Each entry: pattern_suffix -> (category, multiplier_override or None)
# We build a combined regex from these.

_UNIT_DEFS: list[tuple[str, list[str]]] = [
    ("voltage",     ["V", "\ubcfc\ud2b8", "volt", "volts"]),
    ("current",     ["A", "\uc554\ud398\uc5b4", "amp", "amps", "ampere"]),
    ("frequency",   ["Hz", "\ud5e4\ub974\uce20"]),
    ("resistance",  ["\u03a9", "\uc634", "ohm", "ohms"]),
    ("inductance",  ["H", "\ud5e8\ub9ac", "henry"]),
    ("capacitance", ["F", "\ud328\ub7ff", "farad"]),
    ("power",       ["W", "\uc640\ud2b8", "watt", "watts"]),
]

# Build a lookup: unit_string (lower) -> category
_UNIT_LOOKUP: dict[str, str] = {}
_UNIT_STRINGS: list[str] = []

for _cat, _aliases in _UNIT_DEFS:
    for _alias in _aliases:
        _UNIT_LOOKUP[_alias.lower()] = _cat
        _UNIT_STRINGS.append(re.escape(_alias))

# Sort by length descending so longer units match first (e.g. "Hz" before "H")
_UNIT_STRINGS.sort(key=len, reverse=True)

# SI prefix pattern (single char)
_PREFIX_PAT = r"[pPnN\u03bcuUmMkK]"

# Number pattern: integer or decimal, optional leading minus
_NUMBER_PAT = r"(?:\d+\.?\d*|\.\d+)"

# Full pattern: number + optional whitespace + optional SI prefix + unit
_FULL_PATTERN = re.compile(
    r"(?P<number>" + _NUMBER_PAT + r")"
    r"\s*"
    r"(?P<prefix>" + _PREFIX_PAT + r")?"
    r"(?P<unit>" + "|".join(_UNIT_STRINGS) + r")",
    re.IGNORECASE,
)


def _resolve_prefix(prefix_char: str | None) -> float:
    """Return the multiplier for a given SI prefix character."""
    if not prefix_char:
        return 1.0
    return _SI_PREFIX.get(prefix_char, 1.0)


def _resolve_category(unit_str: str) -> str | None:
    """Map a unit string to its category."""
    return _UNIT_LOOKUP.get(unit_str.lower())


def extract_values(text: str) -> dict[str, list[float]]:
    """Extract all recognizable numeric values with units from *text*.

    Returns a dict keyed by category (voltage, current, frequency,
    resistance, inductance, capacitance, power) with lists of float values.

    Examples::

        >>> extract_values("48V input 12V output 5A load")
        {'voltage': [48.0, 12.0], 'current': [5.0]}

        >>> extract_values("100kHz switching, 47uH inductor")
        {'frequency': [100000.0], 'inductance': [4.7e-05]}
    """
    results: dict[str, list[float]] = {}

    for m in _FULL_PATTERN.finditer(text):
        number = float(m.group("number"))
        prefix = m.group("prefix")
        unit_str = m.group("unit")

        # Disambiguate 'm' prefix vs. 'M' prefix:
        # - 'mH', 'mF', 'mA' -> milli
        # - 'MHz' -> mega
        # The prefix group captures the raw character.
        # For units starting with a capital (like Hz, H), lowercase 'm' is milli.
        # For 'M' followed by Hz -> mega.
        multiplier = _resolve_prefix(prefix)
        category = _resolve_category(unit_str)

        if category is None:
            continue

        value = number * multiplier
        results.setdefault(category, []).append(value)

    return results
