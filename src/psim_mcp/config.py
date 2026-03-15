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
