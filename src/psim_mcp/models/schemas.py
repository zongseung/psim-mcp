"""Pydantic v2 request / response schemas for PSIM-MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class OpenProjectRequest(BaseModel):
    """Open a PSIM project file (.psimsch)."""

    path: str = Field(..., min_length=1, max_length=4096, description="Absolute path to the PSIM project file.")


class SetParameterRequest(BaseModel):
    """Set a single component parameter."""

    component_id: str = Field(..., min_length=1, max_length=64, description="Target component identifier.")
    parameter_name: str = Field(..., min_length=1, max_length=64, description="Parameter name to set.")
    value: int | float | str = Field(..., description="New parameter value.")


class RunSimulationRequest(BaseModel):
    """Run a transient simulation."""

    time_step: float | None = Field(default=None, gt=0, le=3600, description="Simulation time step (seconds).")
    total_time: float | None = Field(default=None, gt=0, le=3600, description="Total simulation duration (seconds).")
    timeout: int | None = Field(default=None, gt=0, le=3600, description="Max wait time in seconds (overrides config).")


class ExportResultsRequest(BaseModel):
    """Export simulation results to a file."""

    output_dir: str | None = Field(None, description="Directory for exported files.")
    format: Literal["json", "csv"] = Field("json", description="Output format.")
    signals: list[str] | None = Field(None, max_length=100, description="Signal names to export; None = all.")


class SweepParameterRequest(BaseModel):
    """Run a parameter sweep across a range of values."""

    component_id: str = Field(..., min_length=1, max_length=64, description="Target component identifier.")
    parameter_name: str = Field(..., min_length=1, max_length=64, description="Parameter to sweep.")
    start: float = Field(..., description="Sweep range start value.")
    end: float = Field(..., description="Sweep range end value.")
    step: float = Field(..., gt=0, description="Sweep step size (must be > 0).")
    metrics: list[str] | None = Field(None, description="Metric names to collect per step.")

    @model_validator(mode="after")
    def _start_less_than_end(self) -> SweepParameterRequest:
        if self.start >= self.end:
            raise ValueError(
                f"'start' ({self.start}) must be less than 'end' ({self.end})."
            )
        return self


class CompareResultsRequest(BaseModel):
    """Compare two simulation result sets."""

    result_a: str = Field(..., description="Identifier or path for the first result.")
    result_b: str = Field(..., description="Identifier or path for the second result.")
    signals: list[str] | None = Field(None, description="Signals to compare; None = all.")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Structured error information returned to the client."""

    code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable error description.")
    suggestion: str | None = Field(None, description="Optional remediation hint.")


class ToolResponse(BaseModel):
    """Unified response envelope for every tool call."""

    success: bool
    data: dict | None = None
    message: str | None = None
    error: ErrorDetail | None = None
