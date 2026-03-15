"""Tests for psim_mcp.models.schemas (Pydantic v2 models)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from psim_mcp.models.schemas import (
    ErrorDetail,
    ExportResultsRequest,
    OpenProjectRequest,
    RunSimulationRequest,
    SetParameterRequest,
    SweepParameterRequest,
    ToolResponse,
)


# ---------------------------------------------------------------------------
# OpenProjectRequest
# ---------------------------------------------------------------------------


class TestOpenProjectRequest:
    def test_valid(self) -> None:
        req = OpenProjectRequest(path="/tmp/project.psimsch")
        assert req.path == "/tmp/project.psimsch"

    def test_empty_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OpenProjectRequest(path="")

    def test_missing_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OpenProjectRequest()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# SetParameterRequest
# ---------------------------------------------------------------------------


class TestSetParameterRequest:
    def test_valid(self) -> None:
        req = SetParameterRequest(component_id="V1", parameter_name="Voltage", value=12.0)
        assert req.component_id == "V1"
        assert req.parameter_name == "Voltage"
        assert req.value == 12.0

    def test_missing_component_id(self) -> None:
        with pytest.raises(ValidationError):
            SetParameterRequest(parameter_name="Voltage", value=12.0)  # type: ignore[call-arg]

    def test_missing_parameter_name(self) -> None:
        with pytest.raises(ValidationError):
            SetParameterRequest(component_id="V1", value=12.0)  # type: ignore[call-arg]

    def test_missing_value(self) -> None:
        with pytest.raises(ValidationError):
            SetParameterRequest(component_id="V1", parameter_name="Voltage")  # type: ignore[call-arg]

    def test_string_value_accepted(self) -> None:
        req = SetParameterRequest(component_id="V1", parameter_name="Mode", value="PWM")
        assert req.value == "PWM"

    def test_int_value_accepted(self) -> None:
        req = SetParameterRequest(component_id="V1", parameter_name="Count", value=5)
        assert req.value == 5


# ---------------------------------------------------------------------------
# RunSimulationRequest
# ---------------------------------------------------------------------------


class TestRunSimulationRequest:
    def test_defaults(self) -> None:
        req = RunSimulationRequest()
        assert req.time_step is None
        assert req.total_time is None
        assert req.timeout is None

    def test_custom_values(self) -> None:
        req = RunSimulationRequest(time_step=1e-6, total_time=0.01, timeout=60)
        assert req.time_step == 1e-6
        assert req.total_time == 0.01
        assert req.timeout == 60


# ---------------------------------------------------------------------------
# SweepParameterRequest
# ---------------------------------------------------------------------------


class TestSweepParameterRequest:
    def test_valid(self) -> None:
        req = SweepParameterRequest(
            component_id="R1",
            parameter_name="Resistance",
            start=1.0,
            end=10.0,
            step=1.0,
        )
        assert req.start == 1.0
        assert req.end == 10.0
        assert req.step == 1.0

    def test_start_greater_than_end_rejected(self) -> None:
        with pytest.raises(ValidationError, match="start"):
            SweepParameterRequest(
                component_id="R1",
                parameter_name="Resistance",
                start=10.0,
                end=1.0,
                step=1.0,
            )

    def test_start_equal_to_end_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SweepParameterRequest(
                component_id="R1",
                parameter_name="Resistance",
                start=5.0,
                end=5.0,
                step=1.0,
            )

    def test_step_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SweepParameterRequest(
                component_id="R1",
                parameter_name="Resistance",
                start=1.0,
                end=10.0,
                step=0,
            )

    def test_negative_step_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SweepParameterRequest(
                component_id="R1",
                parameter_name="Resistance",
                start=1.0,
                end=10.0,
                step=-1.0,
            )

    def test_with_metrics(self) -> None:
        req = SweepParameterRequest(
            component_id="R1",
            parameter_name="Resistance",
            start=1.0,
            end=10.0,
            step=0.5,
            metrics=["efficiency", "ripple"],
        )
        assert req.metrics == ["efficiency", "ripple"]


# ---------------------------------------------------------------------------
# ExportResultsRequest
# ---------------------------------------------------------------------------


class TestExportResultsRequest:
    def test_defaults(self) -> None:
        req = ExportResultsRequest()
        assert req.output_dir is None
        assert req.format == "json"
        assert req.signals is None

    def test_csv_format(self) -> None:
        req = ExportResultsRequest(format="csv")
        assert req.format == "csv"

    def test_invalid_format_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExportResultsRequest(format="xml")  # type: ignore[arg-type]

    def test_with_signals(self) -> None:
        req = ExportResultsRequest(signals=["Vout", "Iout"])
        assert req.signals == ["Vout", "Iout"]


# ---------------------------------------------------------------------------
# ToolResponse + ErrorDetail
# ---------------------------------------------------------------------------


class TestToolResponse:
    def test_success(self) -> None:
        resp = ToolResponse(success=True, data={"key": "value"}, message="OK")
        assert resp.success is True
        assert resp.data == {"key": "value"}
        assert resp.error is None

    def test_error(self) -> None:
        err = ErrorDetail(code="SIM_FAIL", message="Simulation crashed.")
        resp = ToolResponse(success=False, error=err)
        assert resp.success is False
        assert resp.error is not None
        assert resp.error.code == "SIM_FAIL"

    def test_error_with_suggestion(self) -> None:
        err = ErrorDetail(
            code="TIMEOUT",
            message="Timed out.",
            suggestion="Increase simulation_timeout.",
        )
        assert err.suggestion == "Increase simulation_timeout."

    def test_defaults(self) -> None:
        resp = ToolResponse(success=True)
        assert resp.data is None
        assert resp.message is None
        assert resp.error is None
