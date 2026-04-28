"""Fixtures for opt-in real-PSIM acceptance tests."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

import pytest

import psim_mcp.services.circuit_design_service as circuit_design_service_module
from psim_mcp.config import AppConfig
from psim_mcp.server import create_app
from psim_mcp.services.analysis_service import AnalysisService

_OPT_IN_ENV = "RUN_REAL_PSIM_TESTS"
_REQUIRED_ENV_VARS = ("PSIM_PATH", "PSIM_PROJECT_DIR", "PSIM_OUTPUT_DIR")
_TRUTHY = {"1", "true", "yes", "on"}


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUTHY


def _real_psim_skip_reason() -> str | None:
    if os.name != "nt":
        return "Real PSIM acceptance tests require Windows."

    if not _is_truthy(os.getenv(_OPT_IN_ENV)):
        return f"Set {_OPT_IN_ENV}=1 to enable opt-in real PSIM acceptance tests."

    if os.getenv("PSIM_MODE", "").strip().lower() != "real":
        return "Set PSIM_MODE=real to run real PSIM acceptance tests."

    missing = [name for name in _REQUIRED_ENV_VARS if not os.getenv(name)]

    psim_path = Path(os.environ["PSIM_PATH"]) if os.getenv("PSIM_PATH") else None
    inferred_python = psim_path / "python38" / "python.exe" if psim_path else None
    if not os.getenv("PSIM_PYTHON_EXE") and (inferred_python is None or not inferred_python.is_file()):
        missing.append("PSIM_PYTHON_EXE")

    if missing:
        return "Missing required environment variables for real PSIM tests: " + ", ".join(sorted(missing))

    return None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    reason = _real_psim_skip_reason()
    if reason is None:
        return

    # Only skip tests that live under tests/real/, not the entire suite
    real_dir = str(Path(__file__).resolve().parent)
    skip_marker = pytest.mark.skip(reason=reason)
    for item in items:
        if str(Path(item.fspath).resolve()).startswith(real_dir):
            item.add_marker(skip_marker)


@pytest.fixture(autouse=True)
def _disable_preview_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent preview generation from opening a GUI browser during tests."""
    monkeypatch.setattr(circuit_design_service_module, "open_svg_in_browser", lambda _path: None)


@pytest.fixture(scope="session")
def real_config() -> AppConfig:
    """Build AppConfig from the real PSIM environment."""
    project_root = Path(os.environ["PSIM_PROJECT_DIR"]).resolve()
    output_root = Path(os.environ["PSIM_OUTPUT_DIR"]).resolve()
    scenario_project_dir = project_root / "pytest_real"
    scenario_output_dir = output_root / "pytest_real"
    scenario_project_dir.mkdir(parents=True, exist_ok=True)
    scenario_output_dir.mkdir(parents=True, exist_ok=True)

    python_exe = os.getenv("PSIM_PYTHON_EXE")
    config = AppConfig(
        psim_mode="real",
        psim_path=Path(os.environ["PSIM_PATH"]).resolve(),
        psim_python_exe=Path(python_exe).resolve() if python_exe else None,
        psim_project_dir=scenario_project_dir,
        psim_output_dir=scenario_output_dir,
        log_dir=Path(__file__).resolve().parents[2] / "logs" / "tests-real",
        simulation_timeout=max(int(os.getenv("PSIM_SIM_TIMEOUT", "300")), 300),
        allowed_project_dirs=[str(project_root), str(scenario_project_dir)],
    )
    config.validate_real_mode()
    return config


@pytest.fixture(scope="session")
def real_app(real_config: AppConfig):
    """Create a production-wired app bound to the real adapter."""
    app = create_app(real_config)
    yield app

    adapter = app._services["_adapter"]  # type: ignore[attr-defined]
    try:
        asyncio.run(adapter.shutdown())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(adapter.shutdown())
        finally:
            loop.close()


@pytest.fixture(scope="session")
def circuit_design_service(real_app):
    return real_app._services["circuit_design"]  # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def simulation_service(real_app):
    return real_app._services["simulation"]  # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def analysis_service(real_app) -> AnalysisService:
    adapter = real_app._services["_adapter"]  # type: ignore[attr-defined]
    return AnalysisService(adapter)


@pytest.fixture
def real_test_workspace(real_config: AppConfig, request: pytest.FixtureRequest) -> dict[str, Path]:
    """Create per-test directories inside the configured real-PSIM workspace."""
    scenario_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name).strip("_") or "scenario"
    project_dir = Path(real_config.psim_project_dir) / scenario_name
    output_dir = Path(real_config.psim_output_dir) / scenario_name
    project_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "project_dir": project_dir,
        "output_dir": output_dir,
    }
