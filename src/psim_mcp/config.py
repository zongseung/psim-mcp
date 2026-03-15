"""Application configuration via environment variables and .env file."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """PSIM-MCP server configuration.

    All values can be overridden via environment variables or a `.env` file.
    """

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # --- PSIM integration ---
    psim_mode: Literal["mock", "real"] = "mock"
    psim_path: Path | None = None
    psim_python_exe: Path | None = None
    psim_project_dir: Path | None = None
    psim_output_dir: Path | None = None

    # --- Logging ---
    log_dir: Path = Path("./logs")
    log_level: str = "INFO"

    # --- Server ---
    server_transport: str = "stdio"
    server_host: str = "127.0.0.1"
    server_port: int = 8000

    # --- Simulation ---
    simulation_timeout: int = 300
    max_sweep_steps: int = 100

    # --- Preview ---
    preview_ttl: int = 3600  # seconds

    # --- Security ---
    allowed_project_dirs: list[str] = []

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        v = v.upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid:
            raise ValueError(f"log_level must be one of {valid}, got '{v}'")
        return v

    @field_validator("allowed_project_dirs", mode="before")
    @classmethod
    def _parse_allowed_dirs(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [d.strip() for d in v.split(",") if d.strip()]
        return v

    def validate_real_mode(self) -> None:
        """Validate that all required fields are set for real mode.

        Should be called at server startup. Raises ValueError with a clear
        message listing all missing fields so the operator can fix them at once.
        """
        if self.psim_mode != "real":
            return

        missing: list[str] = []
        if self.psim_path is None:
            missing.append("PSIM_PATH")
        if self.psim_python_exe is None:
            missing.append("PSIM_PYTHON_EXE")
        if self.psim_project_dir is None:
            missing.append("PSIM_PROJECT_DIR")
        if self.psim_output_dir is None:
            missing.append("PSIM_OUTPUT_DIR")

        if missing:
            raise ValueError(
                f"PSIM_MODE=real requires the following environment variables: "
                f"{', '.join(missing)}. "
                f"Set them in .env or as environment variables."
            )
