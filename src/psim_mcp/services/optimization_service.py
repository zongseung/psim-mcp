"""Safe sequential Optuna optimization for user-selected circuit values."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import time
from asyncio import CancelledError  # noqa: F401  # noqa: ANYIO_OK
from pathlib import Path
from typing import TYPE_CHECKING

from psim_mcp.models.optimization import OptimizationRequest
from psim_mcp.services.optimization_study import (
    OptimizationStudy,
    StudyFiles,
    append_ledger,
)
from psim_mcp.services.validators import validate_project_path

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter, SessionToken
    from psim_mcp.config import AppConfig


class OptimizationService:
    def __init__(self, adapter: BasePsimAdapter, config: AppConfig) -> None:
        self._adapter = adapter
        self._config = config

    async def optimize(  # noqa: ANN401  # noqa: DICT_OK
        self,
        request: OptimizationRequest,
    ) -> dict:
        started = time.monotonic()
        result = self._empty_result()
        validation = validate_project_path(
            request.source_project_path,
            self._config.allowed_project_dirs or None,
        )
        if not validation.is_valid:
            result["error"] = validation.error_message
            return result
        if self._config.psim_output_dir is None:
            result["error"] = "PSIM_OUTPUT_DIR is required for optimization artifacts"
            return result

        source = Path(request.source_project_path).resolve()
        ledger: Path | None = None
        try:
            output_root = self._config.psim_output_dir.resolve()
            output_root.mkdir(parents=True, exist_ok=True)
            study_dir = Path(tempfile.mkdtemp(prefix="optuna-", dir=output_root))
            ledger = study_dir / "study.jsonl"
            result.update(study_dir=str(study_dir), ledger_path=str(ledger))
            source_copy = study_dir / "source-copy.psimsch"
            working = study_dir / "working.psimsch"
            source_hash = self._hash(source)
            result["source_hash_before"] = source_hash
        except Exception as exc:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
            result.update(
                state="failed",
                stop_reason="setup_failed",
                error=str(exc),
                elapsed_seconds=round(time.monotonic() - started, 6),
            )
            if ledger is not None:
                append_ledger(ledger, {"type": "terminal", **result})
            return result

        try:
            async with self._adapter.session_lease(str(study_dir)) as token:
                previous = self._adapter.current_project_path
                try:
                    shutil.copy2(source, source_copy)
                    if self._hash(source_copy) != source_hash:
                        raise OSError("source copy hash mismatch")
                    shutil.copy2(source_copy, working)
                    result.update(
                        await OptimizationStudy(self._adapter, request).run(
                            token,
                            StudyFiles(source_copy, working, study_dir, ledger),
                            started,
                        )
                    )
                except CancelledError:
                    result.update(
                        success=False,
                        state="cancelled",
                        stop_reason="cancelled",
                        error="optimization cancelled",
                    )
                    raise
                except Exception as exc:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
                    result.update(
                        success=False,
                        state="failed",
                        stop_reason="optimization_failed",
                        error=str(exc),
                    )
                finally:
                    result["restoration_status"] = await self._restore(token, previous)
                    result["source_hash_after"] = self._hash_if_present(source)
                    if result["source_hash_after"] != source_hash:
                        result["source_changed_during_study"] = True
                        result.update(success=False, state="failed", stop_reason="source_changed")
                    if str(result["restoration_status"]).startswith("failed"):
                        result.update(
                            success=False, state="failed", stop_reason="restoration_failed"
                        )
                    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
                    result["result_paths"] = [
                        path for path in result["result_paths"] if Path(path).is_file()
                    ]
                    append_ledger(ledger, {"type": "terminal", **result})
        except Exception as exc:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
            result.update(
                success=False,
                state="failed",
                stop_reason="session_lease_failed",
                error=str(exc),
                elapsed_seconds=round(time.monotonic() - started, 6),
            )
            append_ledger(ledger, {"type": "terminal", **result})
        return result

    async def _restore(self, token: SessionToken, previous: str | None) -> str:
        try:
            await self._adapter.reset_session(token)
            if previous is not None:
                await self._adapter.open_project(previous, lease_token=token)
                return "restored"
            return "no_previous_project"
        except Exception as exc:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
            return f"failed: {exc}"

    @staticmethod
    def _hash(path: Path) -> str:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    @classmethod
    def _hash_if_present(cls, path: Path) -> str | None:
        try:
            return cls._hash(path)
        except OSError:
            return None

    @staticmethod
    def _empty_result() -> dict:  # noqa: ANN401  # noqa: DICT_OK
        return {
            "success": False,
            "state": "failed",
            "stop_reason": "validation_failed",
            "trials_complete": 0,
            "trials_failed": 0,
            "best_params": None,
            "best_cost": None,
            "best_metrics": None,
            "constraint_residuals": None,
            "best_project_path": None,
            "source_hash_before": None,
            "source_hash_after": None,
            "source_changed_during_study": False,
            "restoration_status": "not_started",
            "study_dir": None,
            "ledger_path": None,
            "result_paths": [],
            "elapsed_seconds": 0.0,
            "error": None,
        }
