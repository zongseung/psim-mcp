"""Tests for the IntentResolver strategy interface (Phase 0).

These tests pin the public contract Phase 1 will rely on:
- ``IntentResolver`` is an abstract base class.
- ``RegexResolver`` produces the legacy ``_resolve_intent_v2`` dict shape.
- ``get_resolver(mode)`` returns concrete resolvers keyed on the mode string.

Behavior beyond the dict contract (specific regex matches, ranker scoring,
etc.) is exercised by the dedicated extractor / ranker test suites.
"""

from __future__ import annotations

import inspect

import pytest

from psim_mcp.intent import IntentResolver, RegexResolver, get_resolver
from psim_mcp.intent.resolver import RESOLVER_RESULT_KEYS


# ---------------------------------------------------------------------------
# 1. IntentResolver is abstract
# ---------------------------------------------------------------------------


def test_intent_resolver_is_abstract():
    """The base ABC must not be directly instantiable."""
    with pytest.raises(TypeError):
        IntentResolver()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 2. RegexResolver resolves a clear buck request
# ---------------------------------------------------------------------------


async def test_regex_resolver_extracts_buck():
    """A canonical buck description must round-trip to topology=='buck'."""
    resolver = RegexResolver()
    result = await resolver.resolve("12V to 5V step-down")
    assert result["topology"] == "buck"
    # Step-down conversion is the controlling constraint here; preserve it.
    assert result.get("constraints", {}).get("conversion_goal") == "step_down"


# ---------------------------------------------------------------------------
# 3. Result dict carries the full legacy key set
# ---------------------------------------------------------------------------


async def test_regex_resolver_dict_shape_has_all_keys():
    """Every documented key must be present, even on a minimal input."""
    resolver = RegexResolver()
    result = await resolver.resolve("buck converter 48V to 12V 5A")

    assert isinstance(result, dict)
    for key in RESOLVER_RESULT_KEYS:
        assert key in result, f"missing key {key!r} in resolver result"

    # Spot-check the strict shape: 12 keys total, no extras.
    assert set(result.keys()) == set(RESOLVER_RESULT_KEYS)
    assert result["resolution_version"] == "v2"
    assert isinstance(result["topology_candidates"], list)
    assert isinstance(result["candidate_scores"], list)
    assert isinstance(result["decision_trace"], list)


# ---------------------------------------------------------------------------
# 4. get_resolver factory returns RegexResolver for any mode in Phase 0
# ---------------------------------------------------------------------------


def test_get_resolver_regex_mode_returns_regex_resolver():
    resolver = get_resolver("regex")
    assert isinstance(resolver, RegexResolver)
    # And RegexResolver implements the IntentResolver contract.
    assert isinstance(resolver, IntentResolver)


def test_get_resolver_unknown_mode_falls_back_to_regex():
    """Phase 0 only ships RegexResolver; unknown modes must not blow up."""
    resolver = get_resolver("does-not-exist-yet")
    assert isinstance(resolver, RegexResolver)


# ---------------------------------------------------------------------------
# 5. Resolution is genuinely async (returns a coroutine)
# ---------------------------------------------------------------------------


async def test_resolve_is_async_and_awaitable():
    resolver = RegexResolver()
    coro = resolver.resolve("buck 48V to 12V")
    # The unawaited call returns a coroutine — the marker that the contract is
    # async-native (Phase 1 SamplingResolver will await network I/O here).
    assert inspect.iscoroutine(coro)
    result = await coro
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 6. Empty input returns a valid dict with topology=None / low confidence
# ---------------------------------------------------------------------------


async def test_resolve_empty_string_returns_valid_dict_no_crash():
    """Empty descriptions must not raise; they yield no topology."""
    resolver = RegexResolver()
    result = await resolver.resolve("")

    assert isinstance(result, dict)
    assert set(result.keys()) == set(RESOLVER_RESULT_KEYS)
    # No signal -> ranker yields nothing -> topology=None, confidence=low.
    assert result["topology"] is None
    assert result["confidence"] == "low"
    assert result["topology_candidates"] == []
    assert result["candidate_scores"] == []
    assert result["resolution_version"] == "v2"


# ---------------------------------------------------------------------------
# 7. ctx parameter is accepted (interface forward-compat with Phase 1)
# ---------------------------------------------------------------------------


async def test_resolve_accepts_ctx_kwarg_without_using_it():
    """RegexResolver must tolerate a non-None ctx argument for parity."""
    resolver = RegexResolver()
    sentinel = object()  # any opaque value; RegexResolver ignores it
    result = await resolver.resolve("buck 48V to 12V", ctx=sentinel)
    assert result["topology"] == "buck"
