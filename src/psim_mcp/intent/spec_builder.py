"""Canonical spec builder -- merges intent, topology decision, and defaults."""

from __future__ import annotations

from .models import CanonicalIntentSpec, IntentModel, TopologyCandidate


def build_canonical_spec(
    intent: IntentModel,
    selected: TopologyCandidate,
    additional_specs: dict[str, object] | None = None,
) -> CanonicalIntentSpec:
    """Build a canonical spec ready for the synthesis pipeline.

    Merges:
    - User-provided values (from intent.values)
    - Additional specs (from continue_design / clarification answers)
    - Topology defaults

    Records decision trace for each value source.
    """
    from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA

    requirements: dict[str, object] = {}
    trace: list[dict[str, object]] = []

    # 1. User-provided values
    for key, value in intent.values.items():
        requirements[key] = value
        trace.append({"source": "user", "field": key, "value": value})

    # 2. Additional specs (from follow-up)
    if additional_specs:
        for key, value in additional_specs.items():
            requirements[key] = value
            trace.append({"source": "user_followup", "field": key, "value": value})

    # 3. Topology selection trace
    trace.append(
        {
            "source": "ranker",
            "field": "topology",
            "value": selected.topology,
            "confidence": selected.score,
            "reasons": selected.reasons,
        }
    )

    # 4. Inferred values from constraints
    inferred: dict[str, object] = {}
    if intent.isolation is not None:
        inferred["isolation"] = intent.isolation
        trace.append({"source": "extractor", "field": "isolation", "value": intent.isolation})

    if intent.input_domain is not None:
        inferred["input_domain"] = intent.input_domain

    if intent.output_domain is not None:
        inferred["output_domain"] = intent.output_domain

    if intent.conversion_goal is not None:
        inferred["conversion_goal"] = intent.conversion_goal

    # 5. Missing fields
    meta = TOPOLOGY_METADATA.get(selected.topology, {})
    required = meta.get("required_fields", [])
    missing = [f for f in required if f not in requirements]

    return CanonicalIntentSpec(
        topology=selected.topology,
        requirements=requirements,
        inferred_values=inferred,
        missing_fields=missing,
        decision_trace=trace,
    )
