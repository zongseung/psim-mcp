"""Intent resolution data models."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field


@dataclass
class IntentModel:
    """Extracted user intent -- domain constraints and values, NO topology decision."""

    input_domain: str | None = None  # "ac" | "dc"
    output_domain: str | None = None  # "ac" | "dc"
    conversion_goal: str | None = None  # "step_down" | "step_up" | "rectification" | "inversion"
    use_case: str | None = None  # "charger" | "adapter" | "motor_drive" | ...
    isolation: bool | None = None
    bidirectional: bool | None = None
    values: dict[str, float] = dataclass_field(default_factory=dict)  # vin, vout_target, iout, fsw, ...
    voltage_candidates: list[dict] = dataclass_field(default_factory=list)  # [{"value": 400, "role_hint": "input_bus"}, ...]
    constraints: dict[str, object] = dataclass_field(default_factory=dict)  # raw constraint map
    raw_text: str = ""
    mapping_confidence: str = "high"  # "high" | "medium" | "low"


@dataclass
class TopologyCandidate:
    """A ranked topology candidate with scoring breakdown."""

    topology: str
    score: float
    reasons: list[str] = dataclass_field(default_factory=list)
    missing_fields: list[str] = dataclass_field(default_factory=list)
    conflicts: list[str] = dataclass_field(default_factory=list)


@dataclass
class ClarificationNeed:
    """A question or clarification the system needs from the user."""

    kind: str  # "missing_field" | "ambiguous_topology" | "ambiguous_voltage" | "ambiguous_isolation"
    field: str | None = None
    message: str | None = None
    options: list[str] = dataclass_field(default_factory=list)
    priority: str = "normal"  # "high" | "normal" | "low"


@dataclass
class CanonicalIntentSpec:
    """Fully resolved spec ready for synthesis pipeline."""

    topology: str
    requirements: dict[str, object]
    inferred_values: dict[str, object] = dataclass_field(default_factory=dict)
    missing_fields: list[str] = dataclass_field(default_factory=list)
    decision_trace: list[dict[str, object]] = dataclass_field(default_factory=list)


@dataclass
class DesignResolutionResult:
    """Complete resolution result for service consumption."""

    action: str  # "confirm_intent" | "need_specs" | "suggest_candidates"
    selected_topology: str | None = None
    candidates: list[TopologyCandidate] = dataclass_field(default_factory=list)
    canonical_spec: CanonicalIntentSpec | None = None
    missing_fields: list[str] = dataclass_field(default_factory=list)
    questions: list[str] = dataclass_field(default_factory=list)
    confidence: str = "low"
    design_session_payload: dict[str, object] | None = None
