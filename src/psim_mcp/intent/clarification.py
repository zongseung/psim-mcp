"""Clarification policy -- determines when to ask questions vs default."""

from __future__ import annotations

from .models import ClarificationNeed, IntentModel, TopologyCandidate


def analyze_clarification_needs(
    intent: IntentModel,
    candidates: list[TopologyCandidate],
) -> list[ClarificationNeed]:
    """Determine what clarifications are needed before synthesis.

    Returns empty list if no clarification needed (can proceed directly).
    """
    needs: list[ClarificationNeed] = []

    # 1. No candidates at all
    if not candidates:
        needs.append(
            ClarificationNeed(
                kind="no_match",
                message="어떤 종류의 회로를 만들고 싶으신가요?",
                priority="high",
            )
        )
        return needs

    # 2. Top candidates too close in score (ambiguous topology)
    if len(candidates) >= 2:
        top_score = candidates[0].score
        second_score = candidates[1].score
        if top_score > 0 and (top_score - second_score) / max(top_score, 1) < 0.2:
            options = [c.topology for c in candidates[:3]]
            needs.append(
                ClarificationNeed(
                    kind="ambiguous_topology",
                    message=f"다음 토폴로지 중 어떤 것이 적합할까요?: {', '.join(options)}",
                    options=options,
                    priority="high",
                )
            )

    # 3. Missing required fields on top candidate
    if candidates:
        top = candidates[0]
        for fld in top.missing_fields:
            from psim_mcp.parsers.keyword_map import SLOT_QUESTIONS

            question = SLOT_QUESTIONS.get(fld, f"{fld}을(를) 지정해주세요.")
            needs.append(
                ClarificationNeed(
                    kind="missing_field",
                    field=fld,
                    message=question,
                    priority="normal",
                )
            )

    # 4. Ambiguous voltage roles
    if intent.mapping_confidence == "low" and intent.voltage_candidates:
        needs.append(
            ClarificationNeed(
                kind="ambiguous_voltage",
                message="전압 역할이 불분명합니다. 입력 전압(vin)과 출력 전압(vout)을 명확히 지정해주세요.",
                priority="high",
            )
        )

    # 5. Isolation ambiguity
    if intent.isolation is None and candidates:
        isolated_set = _get_isolated_set()
        has_isolated = any(c.topology in isolated_set for c in candidates[:3])
        has_non_isolated = any(c.topology not in isolated_set for c in candidates[:3])
        if has_isolated and has_non_isolated:
            needs.append(
                ClarificationNeed(
                    kind="ambiguous_isolation",
                    message="절연이 필요한가요?",
                    options=["절연", "비절연"],
                    priority="normal",
                )
            )

    return needs


def _get_isolated_set() -> set[str]:
    from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA

    return {name for name, meta in TOPOLOGY_METADATA.items() if meta.get("isolated")}
