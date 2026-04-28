"""Acceptance scenarios backed by a real PSIM simulation run."""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = [pytest.mark.real_psim, pytest.mark.acceptance]


def _unwrap_service_data(result: dict, action: str) -> dict:
    assert result["success"] is True, f"{action} failed: {result}"
    payload = result.get("data", {})
    if isinstance(payload, dict) and "success" in payload and "data" in payload:
        assert payload["success"] is True, f"{action} bridge payload failed: {payload}"
        return payload["data"]
    return payload


def _require_numeric_metric(analysis_result: dict, metric_name: str) -> float:
    metrics = analysis_result.get("metrics", {})
    available_signals = analysis_result.get("available_signals", [])
    value = metrics.get(metric_name)
    if isinstance(value, dict):
        pytest.fail(
            f"Metric '{metric_name}' could not be computed: {value}. "
            f"Available signals: {available_signals}"
        )
    if value is None:
        pytest.fail(
            f"Metric '{metric_name}' is missing from analysis output. "
            f"Available signals: {available_signals}"
        )
    return float(value)


@pytest.mark.asyncio
async def test_buck_given_48v_12v_5a_when_simulated_then_output_meets_spec(
    circuit_design_service,
    simulation_service,
    analysis_service,
    real_test_workspace: dict[str, Path],
):
    # Given
    specs = {
        "vin": 48.0,
        "vout_target": 12.0,
        "iout": 5.0,
        "fsw": 100_000.0,
    }
    simulation_options = {
        "simview": 0,
        "time_step": 5e-8,
        "total_time": 0.02,
    }

    preview_result = await circuit_design_service.preview_circuit(
        circuit_type="buck",
        specs=specs,
        simulation_settings=simulation_options,
    )
    assert preview_result["success"] is True, preview_result
    preview_token = preview_result["data"]["preview_token"]

    save_path = real_test_workspace["project_dir"] / "buck_48v_12v_5a_100khz.psimsch"
    confirm_result = await circuit_design_service.confirm_circuit(
        save_path=str(save_path),
        preview_token=preview_token,
    )
    confirm_data = _unwrap_service_data(confirm_result, "confirm_circuit")
    assert Path(confirm_data["file_path"]).is_file()

    # When
    run_result = await simulation_service.run_simulation(simulation_options)
    run_data = _unwrap_service_data(run_result, "run_simulation")
    graph_file = Path(run_data["output_path"])
    assert graph_file.is_file(), f"Simulation output file was not created: {graph_file}"

    # Then
    analysis_result = await analysis_service.analyze(
        topology="buck",
        targets={"output_voltage_mean": 12.0},
        graph_file=str(graph_file),
        show_waveform=False,
    )

    output_voltage_mean = _require_numeric_metric(analysis_result, "output_voltage_mean")
    output_voltage_ripple_pct = _require_numeric_metric(analysis_result, "output_voltage_ripple_pct")
    inductor_current_mean = _require_numeric_metric(analysis_result, "inductor_current_mean")

    assert output_voltage_mean == pytest.approx(12.0, rel=0.05)
    assert analysis_result["comparison"]["output_voltage_mean"]["pass"] is True
    assert output_voltage_ripple_pct < 2.0
    assert inductor_current_mean > 0.0
