from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Self, assert_never

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


@dataclass(frozen=True, slots=True)
class OptimizationValidationError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


class _FrozenModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        populate_by_name=True,
    )


class ComponentKind(StrEnum):
    INDUCTOR = "L"
    CAPACITOR = "C"
    RESISTOR = "R"


class ResistorRole(StrEnum):
    DESIGN = "design"
    LOAD = "load"


class MetricFunction(StrEnum):
    MEAN = "mean"
    RIPPLE_PP = "ripple_pp"
    RIPPLE_PERCENT = "ripple_percent"
    PEAK = "peak"
    RMS = "rms"


class ConstraintOperator(StrEnum):
    UPPER = "<="
    LOWER = ">="


class AnalysisWindow(_FrozenModel):
    start_fraction: float = Field(ge=0.0, lt=1.0)
    end_fraction: float = Field(gt=0.0, le=1.0)
    min_samples: int = Field(default=2, ge=2)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.start_fraction >= self.end_fraction:
            raise OptimizationValidationError(
                "window start_fraction must be smaller than end_fraction"
            )
        return self


class ParameterBinding(_FrozenModel):
    component_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    component_kind: ComponentKind
    parameter_name: str
    role: ResistorRole | None = None

    @model_validator(mode="after")
    def validate_parameter(self) -> Self:
        match self.component_kind:
            case ComponentKind.INDUCTOR:
                expected = "Inductance"
            case ComponentKind.CAPACITOR:
                expected = "Capacitance"
            case ComponentKind.RESISTOR:
                expected = "Resistance"
                if self.role is not ResistorRole.DESIGN:
                    raise OptimizationValidationError(
                        "R bindings require role='design'; load resistors are not tunable"
                    )
            case unreachable:
                assert_never(unreachable)

        if self.parameter_name != expected:
            raise OptimizationValidationError(
                f"{self.component_kind.value} bindings require parameter_name='{expected}'"
            )
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.component_id, self.parameter_name)


class DecisionVariable(_FrozenModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    minimum: float = Field(alias="min", gt=0.0)
    maximum: float = Field(alias="max", gt=0.0)
    bindings: tuple[ParameterBinding, ...] = Field(min_length=1)
    log_scale: bool = True

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.minimum >= self.maximum:
            raise OptimizationValidationError("variable min must be smaller than max")
        return self


class Measurement(_FrozenModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    signal: str = Field(min_length=1, max_length=128)
    function: MetricFunction
    window: AnalysisWindow

    def to_metric_spec(self) -> dict[str, str | dict[str, float | int]]:
        return {
            "name": self.name,
            "signal": self.signal,
            "function": self.function.value,
            "window": self.window.model_dump(),
        }


class ObjectiveTerm(_FrozenModel):
    measurement: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    target: float
    weight: float = Field(default=1.0, gt=0.0)
    scale: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def validate_scale(self) -> Self:
        if self.target == 0.0 and self.scale is None:
            raise OptimizationValidationError("zero objective target requires an explicit scale")
        return self

    @property
    def normalization_scale(self) -> float:
        if self.scale is not None:
            return self.scale
        return abs(self.target)


class HardConstraint(_FrozenModel):
    measurement: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    operator: ConstraintOperator
    limit: float
    scale: float = Field(gt=0.0)


class OptimizationRequest(_FrozenModel):
    source_project_path: str
    variables: tuple[DecisionVariable, ...] = Field(min_length=1, max_length=3)
    measurements: tuple[Measurement, ...] = Field(min_length=1)
    objective: tuple[ObjectiveTerm, ...] = Field(min_length=1)
    constraints: tuple[HardConstraint, ...] = Field(min_length=1)
    n_trials: int = Field(default=50, ge=1, le=50)
    time_budget_seconds: int = Field(default=300, ge=1, le=300)
    seed: int = Field(default=0, ge=0, le=2**32 - 1)

    @field_validator("source_project_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        path = value.strip()
        if not path:
            raise OptimizationValidationError("source_project_path must not be empty")
        return path

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        variable_names = [variable.name for variable in self.variables]
        if len(variable_names) != len(set(variable_names)):
            raise OptimizationValidationError("variable names must be unique")

        binding_keys = [binding.key for variable in self.variables for binding in variable.bindings]
        if len(binding_keys) != len(set(binding_keys)):
            raise OptimizationValidationError("each component parameter binding must be unique")

        measurement_names = [measurement.name for measurement in self.measurements]
        if len(measurement_names) != len(set(measurement_names)):
            raise OptimizationValidationError("measurement names must be unique")

        declared = set(measurement_names)
        referenced = {term.measurement for term in self.objective} | {
            constraint.measurement for constraint in self.constraints
        }
        missing = sorted(referenced - declared)
        if missing:
            raise OptimizationValidationError(
                f"objective or constraint references unknown measurement: {', '.join(missing)}"
            )
        return self
