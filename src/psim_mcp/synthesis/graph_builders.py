"""Factory helpers for building CircuitGraph elements."""

from __future__ import annotations

from .graph import (
    DesignDecisionTrace,
    FunctionalBlock,
    GraphComponent,
    GraphNet,
)


def make_component(
    id: str,
    type: str,
    *,
    role: str | None = None,
    parameters: dict[str, object] | None = None,
    tags: list[str] | None = None,
    block_ids: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> GraphComponent:
    """Create a GraphComponent with sensible defaults."""
    return GraphComponent(
        id=id,
        type=type,
        role=role,
        parameters=parameters or {},
        tags=tags or [],
        block_ids=block_ids or [],
        metadata=metadata or {},
    )


def make_net(
    id: str,
    pins: list[str],
    *,
    role: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> GraphNet:
    """Create a GraphNet with sensible defaults."""
    return GraphNet(
        id=id,
        pins=pins,
        role=role,
        tags=tags or [],
        metadata=metadata or {},
    )


def make_block(
    id: str,
    type: str,
    *,
    role: str | None = None,
    component_ids: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> FunctionalBlock:
    """Create a FunctionalBlock with sensible defaults."""
    return FunctionalBlock(
        id=id,
        type=type,
        role=role,
        component_ids=component_ids or [],
        metadata=metadata or {},
    )


def make_trace(
    source: str,
    key: str,
    value: object,
    *,
    confidence: float | None = None,
    rationale: str | None = None,
) -> DesignDecisionTrace:
    """Create a DesignDecisionTrace."""
    return DesignDecisionTrace(
        source=source,
        key=key,
        value=value,
        confidence=confidence,
        rationale=rationale,
    )
