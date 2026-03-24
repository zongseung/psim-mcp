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

    model_config = {
        "env_file": [
            ".env",  # current working directory
            str(Path(__file__).resolve().parent.parent.parent / ".env"),  # project root
        ],
        "env_file_encoding": "utf-8",
    }

    # --- PSIM integration ---
    psim_mode: Literal["mock", "real"] = "mock"
    psim_path: Path | None = None
    psim_python_exe: Path | None = None
    psim_project_dir: Path | None = None
    psim_output_dir: Path | None = None

    # --- Logging ---
    log_dir: Path = Path(__file__).resolve().parent.parent.parent / "logs"
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

    # --- Feature flags ---
    psim_intent_pipeline_v2: bool = True
    psim_synthesis_enabled_topologies: list[str] = []

    # --- Security ---
    allowed_project_dirs: list[str] = []

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("log_dir", mode="before")
    @classmethod
    def _resolve_log_dir(cls, v: str | Path) -> Path:
        """상대 경로를 프로젝트 루트 기준 절대 경로로 변환."""
        p = Path(v)
        if not p.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            return project_root / p
        return p

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        v = v.upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid:
            raise ValueError(f"log_level must be one of {valid}, got '{v}'")
        return v

    @field_validator("allowed_project_dirs", "psim_synthesis_enabled_topologies", mode="before")
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

        # 각 필드별 예시값을 포함한 안내 메시지
        field_examples = {
            "PSIM_PATH": r"C:\Powersim\PSIM",
            "PSIM_PYTHON_EXE": r"C:\Powersim\PSIM\python38\python.exe",
            "PSIM_PROJECT_DIR": r"C:\Users\user\psim-projects",
            "PSIM_OUTPUT_DIR": r"C:\Users\user\psim-output",
        }

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
            details = "\n".join(
                f"  - {field} (예: {field_examples[field]})"
                for field in missing
            )
            raise ValueError(
                f"PSIM_MODE=real requires the following environment variables:\n"
                f"{details}\n"
                f"claude_desktop_config.json의 env 또는 .env 파일에 설정하세요."
            )

        # 경로 존재 여부 검증
        if self.psim_path and not self.psim_path.is_dir():
            raise ValueError(
                f"PSIM_PATH 디렉터리가 존재하지 않습니다: {self.psim_path}\n"
                f"PSIM이 올바르게 설치되어 있는지 확인하세요."
            )
        if self.psim_python_exe and not self.psim_python_exe.is_file():
            raise ValueError(
                f"PSIM_PYTHON_EXE 파일이 존재하지 않습니다: {self.psim_python_exe}\n"
                f"PSIM Python 번들이 올바르게 설치되어 있는지 확인하세요."
            )
