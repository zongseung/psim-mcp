"""LLM-driven intent resolver using MCP sampling.

Delegates natural-language -> structured intent extraction to the client's
LLM via ``ctx.session.create_message`` (MCP 2025-06-18 sampling spec). The
deterministic ranker is kept as a safety net: even when the LLM emits a
``topology_hint``, that hint must (a) be in the topology registry, and (b)
appear in the ranker's top-3 candidates -- otherwise we fall back to the
ranker's top-1.

Phase 1 of the LLM-native intent migration. See
``claudedocs/design-llm-native-intent-2026-04-28.md`` sections 3 and 5.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

from mcp.types import SamplingMessage, TextContent
from pydantic import ValidationError

from .models import IntentModel
from .ranker import rank_topologies
from .resolver import IntentResolver
from .sampling_schema import ExtractedIntent
from .spec_builder import build_canonical_spec

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SamplingExtractionError(RuntimeError):
    """Raised when the LLM sampling response cannot be parsed/validated.

    Hybrid resolver (Phase 2) catches this to fall back to the regex pipeline.
    """


class UnknownTopologyError(ValueError):
    """Raised when the LLM emits a topology_hint not in TOPOLOGY_METADATA.

    Hard correctness gate -- never trust LLM-emitted topology names.
    """


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


INTENT_EXTRACTION_SYSTEM_PROMPT = """\
You are a power electronics intent extractor. Given a Korean or English
natural language description of a desired circuit, return STRICT JSON with
the following fields. Use null for unknown values.

{
  "input_domain": "ac" | "dc" | null,
  "output_domain": "ac" | "dc" | null,
  "isolation": true | false | null,
  "conversion_goal": "step_down" | "step_up" | "rectification" | "inversion" | null,
  "use_case": "charger" | "adapter" | "motor_drive" | "pv_frontend" | "led_driver"
              | "telecom" | "pfc" | "filter" | "auxiliary_supply" | "power_supply" | null,
  "bidirectional": true | false | null,
  "values": {
    "vin": <number> | null,
    "vout_target": <number> | null,
    "iout": <number> | null,
    "fsw": <number> | null,
    "power": <number> | null
  },
  "topology_hint": <string from KNOWN_TOPOLOGIES> | null,
  "confidence": "high" | "medium" | "low",
  "rationale": <one-sentence explanation>
}

KNOWN_TOPOLOGIES: buck, boost, buck_boost, cuk, sepic, flyback, forward,
  half_bridge, full_bridge, push_pull, llc, dab, phase_shifted_full_bridge,
  bidirectional_buck_boost, lcl_filter, lc_filter, three_phase_inverter,
  three_level_npc, diode_bridge_rectifier, thyristor_rectifier, boost_pfc,
  totem_pole_pfc, cc_cv_charger, ev_obc, pv_mppt_boost, induction_motor_vf,
  pmsm_foc_drive, bldc_drive

Output JSON only. No prose, no markdown fences.
"""


# ---------------------------------------------------------------------------
# SamplingResolver
# ---------------------------------------------------------------------------


class SamplingResolver(IntentResolver):
    """IntentResolver implementation that delegates to the client LLM via MCP sampling."""

    def __init__(self, max_tokens: int = 512, temperature: float = 0.1) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def resolve(
        self,
        description: str,
        ctx: Optional["Context"] = None,
    ) -> dict:
        """Resolve a natural-language description into a legacy-compatible intent dict.

        Pipeline:
          1. Sampling round-trip -> JSON payload
          2. JSON parse + Pydantic validation -> ExtractedIntent
          3. topology_hint validation against TOPOLOGY_METADATA
          4. Build IntentModel, run deterministic ranker
          5. Decide final topology (LLM hint if in top-3, else ranker top-1)
          6. build_canonical_spec for normalized_specs/missing_fields
          7. Assemble 12-key legacy dict
        """
        if ctx is None:
            raise RuntimeError("SamplingResolver requires Context")

        # 1-2. Sampling + JSON parse + Pydantic validation.
        extracted = await self._sample_and_parse(description, ctx)

        # 3. Validate topology hint against the canonical registry.
        from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA

        hint = extracted.topology_hint
        if hint is not None and hint not in TOPOLOGY_METADATA:
            raise UnknownTopologyError(f"Unknown topology hint: {hint}")

        # 4. Convert to IntentModel for the deterministic ranker.
        intent_model = self._build_intent_model(extracted, raw_text=description)

        # 5. Run ranker + decide final topology.
        candidates = rank_topologies(intent_model)
        selected_topology, selected_candidate = self._select_topology(hint, candidates)

        # 6-7. Assemble legacy dict.
        return self._build_legacy_dict(
            extracted=extracted,
            intent_model=intent_model,
            candidates=candidates,
            selected_topology=selected_topology,
            selected_candidate=selected_candidate,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _sample_and_parse(
        self,
        description: str,
        ctx: "Context",
    ) -> ExtractedIntent:
        """Round-trip the description through the client LLM and validate the response."""
        result = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=description),
                )
            ],
            system_prompt=INTENT_EXTRACTION_SYSTEM_PROMPT,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        text = self._extract_text_from_result(result)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SamplingExtractionError(f"LLM response was not valid JSON: {exc}") from exc

        try:
            return ExtractedIntent.model_validate(payload)
        except ValidationError as exc:
            raise SamplingExtractionError(f"LLM response failed schema validation: {exc}") from exc

    @staticmethod
    def _extract_text_from_result(result: Any) -> str:
        """Pull the text string out of a CreateMessageResult.

        The MCP CreateMessageResult shape is ``result.content`` -> TextContent
        with a ``.text`` attribute. We tolerate plain attribute access on mocks
        as well so unit tests can use simple MagicMock structures.
        """
        content = getattr(result, "content", None)
        if content is None:
            raise SamplingExtractionError("LLM response missing 'content'")
        text = getattr(content, "text", None)
        if not isinstance(text, str):
            raise SamplingExtractionError("LLM response content has no text")
        return text

    @staticmethod
    def _build_intent_model(extracted: ExtractedIntent, raw_text: str) -> IntentModel:
        """Convert the validated LLM payload into a deterministic IntentModel."""
        values: dict[str, float] = {}
        v = extracted.values
        if v.vin is not None:
            values["vin"] = float(v.vin)
        if v.vout_target is not None:
            values["vout_target"] = float(v.vout_target)
        if v.iout is not None:
            values["iout"] = float(v.iout)
        if v.fsw is not None:
            values["fsw"] = float(v.fsw)
        if v.power is not None:
            values["power_rating"] = float(v.power)

        constraints: dict[str, object] = {}
        if extracted.input_domain is not None:
            constraints["input_domain"] = extracted.input_domain
        if extracted.output_domain is not None:
            constraints["output_domain"] = extracted.output_domain
        if extracted.isolation is not None:
            constraints["isolation"] = extracted.isolation
        if extracted.conversion_goal is not None:
            constraints["conversion_goal"] = extracted.conversion_goal
        if extracted.use_case is not None:
            constraints["use_case"] = extracted.use_case
        if extracted.bidirectional is not None:
            constraints["bidirectional"] = extracted.bidirectional

        # Map LLM confidence to IntentModel.mapping_confidence (same vocabulary).
        return IntentModel(
            input_domain=extracted.input_domain,
            output_domain=extracted.output_domain,
            conversion_goal=extracted.conversion_goal,
            use_case=extracted.use_case,
            isolation=extracted.isolation,
            bidirectional=extracted.bidirectional,
            values=values,
            voltage_candidates=[],
            constraints=constraints,
            raw_text=raw_text,
            mapping_confidence=extracted.confidence,
        )

    @staticmethod
    def _select_topology(
        hint: str | None,
        candidates: list,
    ) -> tuple[str | None, object | None]:
        """Decide the final topology.

        - If hint is in the ranker's top-3 candidates -> trust the LLM.
        - Otherwise -> fall back to ranker top-1.
        - If ranker returns no candidates -> (hint, None) (hint is already
          validated against TOPOLOGY_METADATA, so it is at least a real name).
        """
        if not candidates:
            return hint, None

        top3 = [c.topology for c in candidates[:3]]
        if hint is not None and hint in top3:
            chosen = next(c for c in candidates[:3] if c.topology == hint)
            return hint, chosen

        top1 = candidates[0]
        return top1.topology, top1

    def _build_legacy_dict(
        self,
        extracted: ExtractedIntent,
        intent_model: IntentModel,
        candidates: list,
        selected_topology: str | None,
        selected_candidate: object | None,
    ) -> dict:
        """Assemble the 12-key legacy dict expected by CircuitDesignService."""
        if selected_candidate is not None:
            spec = build_canonical_spec(intent_model, selected_candidate)  # type: ignore[arg-type]
            normalized_specs: dict[str, Any] = dict(spec.requirements)
            missing_fields = list(spec.missing_fields)
            decision_trace = list(spec.decision_trace)
        else:
            normalized_specs = dict(intent_model.values)
            missing_fields = []
            decision_trace = []

        topology_candidates = [c.topology for c in candidates[:5]]
        candidate_scores = [
            {"topology": c.topology, "score": c.score, "reasons": list(c.reasons)}
            for c in candidates[:5]
        ]

        return {
            "topology": selected_topology,
            "topology_candidates": topology_candidates,
            "specs": dict(intent_model.values),
            "normalized_specs": normalized_specs,
            "missing_fields": missing_fields,
            "questions": [],
            "confidence": extracted.confidence,
            "use_case": extracted.use_case,
            "constraints": dict(intent_model.constraints),
            "candidate_scores": candidate_scores,
            "decision_trace": decision_trace,
            "resolution_version": "v3-sampling",
        }
