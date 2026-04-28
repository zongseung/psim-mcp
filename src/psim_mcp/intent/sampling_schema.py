"""Pydantic models for the LLM intent extraction sampling response.

The client's LLM is instructed (via INTENT_EXTRACTION_SYSTEM_PROMPT in
sampling_resolver.py) to emit STRICT JSON matching ExtractedIntent. These
models then validate and normalize that response before it is fed into the
deterministic ranker / spec_builder pipeline.

Pydantic v2 syntax.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedValues(BaseModel):
    """Numeric values extracted from the user description.

    All fields default to None so the LLM can omit unknown values; the
    deterministic pipeline (ranker, spec_builder) handles missing fields.
    """

    vin: float | None = None
    vout_target: float | None = None
    iout: float | None = None
    fsw: float | None = None
    power: float | None = None


class ExtractedIntent(BaseModel):
    """Top-level extracted intent payload returned by the client LLM.

    Mirrors the JSON schema embedded in INTENT_EXTRACTION_SYSTEM_PROMPT.
    Restrictive Literal types reject malformed enum values up front so the
    deterministic safety net (rank_topologies + topology_metadata check) is
    only ever exposed to well-typed input.
    """

    input_domain: Literal["ac", "dc"] | None = None
    output_domain: Literal["ac", "dc"] | None = None
    isolation: bool | None = None
    conversion_goal: Literal["step_down", "step_up", "rectification", "inversion"] | None = None
    use_case: str | None = None
    bidirectional: bool | None = None
    values: ExtractedValues = Field(default_factory=ExtractedValues)
    topology_hint: str | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
