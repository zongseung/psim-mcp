"""Unit tests for MockPsimAdapter."""

from __future__ import annotations

import pytest

from psim_mcp.adapters.mock_adapter import MockPsimAdapter


@pytest.fixture
def mock_adapter() -> MockPsimAdapter:
    return MockPsimAdapter()


class TestOpenProject:
    async def test_returns_project_metadata(self, mock_adapter: MockPsimAdapter):
        result = await mock_adapter.open_project("/tmp/demo.psimsch")

        assert result["name"] == "demo"
        assert isinstance(result["components"], list)
        assert result["component_count"] == len(result["components"])
        assert result["component_count"] > 0
        assert "parameter_count" in result

    async def test_path_is_preserved(self, mock_adapter: MockPsimAdapter):
        path = "/some/path/project.psimsch"
        result = await mock_adapter.open_project(path)
        assert result["path"] == path

    async def test_windows_path(self, mock_adapter: MockPsimAdapter):
        result = await mock_adapter.open_project(r"C:\Users\test\project.psimsch")
        assert result["name"] == "project"


class TestSetParameter:
    async def test_success_after_open(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.set_parameter("V1", "voltage", 24.0)

        assert result["component_id"] == "V1"
        assert result["parameter_name"] == "voltage"
        assert result["previous_value"] == 48.0
        assert result["new_value"] == 24.0
        assert "unit" in result

    async def test_raises_without_open_project(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No project"):
            await mock_adapter.set_parameter("V1", "voltage", 24.0)

    async def test_raises_for_unknown_component(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        with pytest.raises(ValueError, match="not found"):
            await mock_adapter.set_parameter("NONEXISTENT", "voltage", 1.0)

    async def test_raises_for_unknown_parameter(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        with pytest.raises(ValueError, match="not found"):
            await mock_adapter.set_parameter("V1", "nonexistent_param", 1.0)


class TestRunSimulation:
    async def test_returns_completed_status(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.run_simulation()

        assert result["status"] == "completed"
        assert "duration_seconds" in result
        assert "summary" in result
        assert isinstance(result["summary"], dict)

    async def test_raises_without_open_project(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No project"):
            await mock_adapter.run_simulation()

    async def test_explicit_output_path_is_created(
        self,
        mock_adapter: MockPsimAdapter,
        tmp_path,
    ) -> None:
        # Given
        project = tmp_path / "demo.psimsch"
        project.write_text("mock")
        output = tmp_path / "trial-0001.smv"
        await mock_adapter.open_project(str(project))

        # When
        async with mock_adapter.session_lease(str(tmp_path)) as token:
            result = await mock_adapter.run_simulation(
                output_path=str(output),
                lease_token=token,
            )

        # Then
        assert result["output_path"] == str(output)
        assert output.is_file()


class TestExportResults:
    async def test_returns_exported_files(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        await mock_adapter.run_simulation()
        result = await mock_adapter.export_results("/tmp/output", "json")

        assert "exported_files" in result
        assert isinstance(result["exported_files"], list)
        assert len(result["exported_files"]) > 0

    async def test_raises_without_simulation(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No simulation"):
            await mock_adapter.export_results("/tmp/output")


class TestAnalysisHelpers:
    async def test_extract_signals_returns_waveforms(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        await mock_adapter.run_simulation()

        result = await mock_adapter.extract_signals(signals=["V(Vout)", "I(L1)"], max_points=200)

        assert set(result["signal_names"]) == {"V(Vout)", "I(L1)"}
        assert result["point_count"] > 0
        assert "V(Vout)" in result["signals"]
        assert len(result["signals"]["V(Vout)"]) <= 200

    async def test_compute_metrics_returns_requested_metrics(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        await mock_adapter.run_simulation()

        result = await mock_adapter.compute_metrics(
            metrics_spec=[
                {"name": "vout_mean", "signal": "V(Vout)", "function": "mean"},
                {"name": "vout_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
                {"name": "il1_rms", "signal": "I(L1)", "function": "rms"},
            ],
        )

        assert "vout_mean" in result["metrics"]
        assert "vout_ripple_pct" in result["metrics"]
        assert "il1_rms" in result["metrics"]
        assert result["metrics"]["vout_mean"] > 0
        assert "V(Vout)" in result["available_signals"]

    async def test_compute_metrics_applies_exact_fractional_window(
        self,
        mock_adapter: MockPsimAdapter,
    ) -> None:
        # Given
        await mock_adapter.open_project("/tmp/demo.psimsch")
        await mock_adapter.run_simulation()
        metric = {
            "name": "vout_mean",
            "signal": "V(Vout)",
            "function": "mean",
            "window": {
                "start_fraction": 0.25,
                "end_fraction": 0.75,
                "min_samples": 20,
            },
        }

        # When
        result = await mock_adapter.compute_metrics([metric])

        # Then
        assert result["windows"]["vout_mean"] == {
            "start_index": 200,
            "end_index": 600,
            "point_count": 400,
        }


class TestGetStatus:
    async def test_returns_status_dict(self, mock_adapter: MockPsimAdapter):
        result = await mock_adapter.get_status()

        assert result["mode"] == "mock"
        assert result["psim_connected"] is False
        assert result["current_project"] is None
        assert result["last_simulation"] is None
        assert "server" in result

    async def test_status_reflects_open_project(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.get_status()

        assert result["current_project"] is not None
        assert result["current_project"]["name"] == "demo"


class TestGetProjectInfo:
    async def test_returns_project_info_after_open(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.get_project_info()

        assert result["name"] == "demo"
        assert "components" in result
        assert result["component_count"] == len(result["components"])
        assert "parameter_count" in result

    async def test_raises_without_open_project(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No project"):
            await mock_adapter.get_project_info()


async def test_session_lease_blocks_all_ordinary_mock_operations(
    mock_adapter: MockPsimAdapter,
) -> None:
    # Given
    operations = (
        lambda: mock_adapter.export_results("/tmp/output"),
        mock_adapter.extract_signals,
        mock_adapter.get_status,
        mock_adapter.get_project_info,
        lambda: mock_adapter.convert_to_python("/tmp/demo.psimsch"),
    )

    # When
    async with mock_adapter.session_lease("/tmp/study"):
        # Then
        for operation in operations:
            with pytest.raises(RuntimeError, match="SESSION_BUSY"):
                await operation()
