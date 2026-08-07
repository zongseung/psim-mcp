from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from psim_mcp.models.optimization import OptimizationRequest


def _valid_request() -> dict:
    return {
        "source_project_path": "C:/circuits/converter.psimsch",
        "variables": [
            {
                "name": "phase_inductance",
                "min": 80e-6,
                "max": 180e-6,
                "bindings": [
                    {
                        "component_id": "L1",
                        "component_kind": "L",
                        "parameter_name": "Inductance",
                    },
                    {
                        "component_id": "L2",
                        "component_kind": "L",
                        "parameter_name": "Inductance",
                    },
                ],
            }
        ],
        "measurements": [
            {
                "name": "vout_mean",
                "signal": "V(Vout)",
                "function": "mean",
                "window": {
                    "start_fraction": 0.5,
                    "end_fraction": 1.0,
                    "min_samples": 20,
                },
            },
            {
                "name": "inductor_peak",
                "signal": "I(L1)",
                "function": "peak",
                "window": {
                    "start_fraction": 0.5,
                    "end_fraction": 1.0,
                    "min_samples": 20,
                },
            },
        ],
        "objective": [{"measurement": "vout_mean", "target": 12.0, "weight": 1.0}],
        "constraints": [
            {
                "measurement": "inductor_peak",
                "operator": "<=",
                "limit": 5.0,
                "scale": 5.0,
            }
        ],
        "n_trials": 2,
        "time_budget_seconds": 30,
        "seed": 0,
    }


def test_parses_tied_bindings_and_target_scale_when_request_is_valid() -> None:
    # Given
    raw = _valid_request()

    # When
    request = OptimizationRequest.model_validate(raw)

    # Then
    assert len(request.variables[0].bindings) == 2
    assert request.objective[0].normalization_scale == 12.0


def test_rejects_overlapping_binding_when_component_parameter_is_reused() -> None:
    # Given
    raw = _valid_request()
    raw["variables"].append(
        {
            "name": "duplicate",
            "min": 1e-6,
            "max": 2e-6,
            "bindings": [raw["variables"][0]["bindings"][0]],
        }
    )

    # When / Then
    with pytest.raises(ValidationError, match="binding"):
        OptimizationRequest.model_validate(raw)


def test_rejects_load_resistor_when_role_is_not_design() -> None:
    # Given
    raw = _valid_request()
    raw["variables"][0] = {
        "name": "load",
        "min": 5.0,
        "max": 20.0,
        "bindings": [
            {
                "component_id": "R1",
                "component_kind": "R",
                "parameter_name": "Resistance",
                "role": "load",
            }
        ],
    }

    # When / Then
    with pytest.raises(ValidationError, match="design"):
        OptimizationRequest.model_validate(raw)


def test_rejects_unknown_measurement_reference() -> None:
    # Given
    raw = _valid_request()
    raw["objective"][0]["measurement"] = "missing"

    # When / Then
    with pytest.raises(ValidationError, match="measurement"):
        OptimizationRequest.model_validate(raw)


@pytest.mark.parametrize(
    ("field_path", "invalid_value"),
    [
        (("objective", 0, "target"), math.nan),
        (("constraints", 0, "limit"), math.inf),
        (("measurements", 0, "window", "start_fraction"), math.nan),
    ],
)
def test_rejects_non_finite_numeric_boundary(
    field_path: tuple[str | int, ...],
    invalid_value: float,
) -> None:
    # Given
    raw = _valid_request()
    target = raw
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = invalid_value

    # When / Then
    with pytest.raises(ValidationError):
        OptimizationRequest.model_validate(raw)
