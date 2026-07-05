"""Project lifecycle management service.

Handles project open/close, information retrieval, and status checks.
Extracted from the original monolithic ``SimulationService``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psim_mcp.shared.audit import AuditMiddleware
from psim_mcp.shared.response import ResponseBuilder
from psim_mcp.utils.logging import hash_input
from psim_mcp.utils.sanitize import sanitize_for_llm_context, sanitize_path_for_display
from psim_mcp.services.validators import validate_project_path

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter
    from psim_mcp.config import AppConfig


class ProjectService:
    """Project lifecycle management.

    Responsibilities:
    - Project path validation and security checks
    - Delegating project operations to the adapter
    - Project state tracking
    """

    def __init__(self, adapter: BasePsimAdapter, config: AppConfig) -> None:
        self._adapter = adapter
        self._config = config
        self._logger = logging.getLogger(__name__)
        self._audit = AuditMiddleware()

    async def open_project(self, path: str) -> dict:
        """Validate and open a PSIM project file."""

        async def _handler():
            vr = validate_project_path(path, self._config.allowed_project_dirs or None)
            if not vr.is_valid:
                self._audit.log_path_blocked(path, vr.error_code or "VALIDATION_ERROR")
                return ResponseBuilder.error(
                    code=vr.error_code or "VALIDATION_ERROR",
                    message=vr.error_message or "Invalid project path.",
                    suggestion="Provide an absolute path to a .psimsch file.",
                )

            try:
                data = await self._adapter.open_project(path)
                display_name = sanitize_for_llm_context(
                    data.get("name", sanitize_path_for_display(path))
                )
                return ResponseBuilder.success(
                    data, f"Project '{display_name}' opened successfully."
                )
            except Exception:
                self._logger.exception("Failed to open project: %s", path)
                return ResponseBuilder.error(
                    code="OPEN_PROJECT_FAILED",
                    message="프로젝트를 여는 중 오류가 발생했습니다.",
                )

        return await self._audit.execute_with_audit(
            "open_project",
            {"path_hash": hash_input(path)},
            _handler,
        )

    async def get_project_info(self) -> dict:
        """Return detailed structural information about the currently open project."""

        async def _handler():
            if not self.is_project_open:
                return ResponseBuilder.error(
                    code="NO_PROJECT",
                    message="No project is currently open.",
                    suggestion="Use open_project to load a .psimsch file first.",
                )

            try:
                data = await self._adapter.get_project_info()
                return ResponseBuilder.success(data, "프로젝트 정보를 조회했습니다.")
            except Exception:
                self._logger.exception("Failed to get project info")
                return ResponseBuilder.error(
                    code="PROJECT_INFO_FAILED",
                    message="프로젝트 정보 조회 중 오류가 발생했습니다.",
                )

        return await self._audit.execute_with_audit("get_project_info", {}, _handler)

    async def import_circuit(self, path: str, include_graph: bool = False) -> dict:
        """Reconstruct the full structure (components + nets) of an existing schematic.

        Pipeline: adapter.convert_to_python (PSIM's own schematic→Python
        converter — the only API path that exposes wires/labels/pin
        coordinates) → importer.parse_converted_script → importer.reconstruct
        (union-find net reconstruction) → structured summary.
        """

        async def _handler():
            vr = validate_project_path(path, self._config.allowed_project_dirs or None)
            if not vr.is_valid:
                self._audit.log_path_blocked(path, vr.error_code or "VALIDATION_ERROR")
                return ResponseBuilder.error(
                    code=vr.error_code or "VALIDATION_ERROR",
                    message=vr.error_message or "Invalid project path.",
                    suggestion="Provide an absolute path to a .psimsch file.",
                )

            try:
                raw = await self._adapter.convert_to_python(path)
            except NotImplementedError:
                return ResponseBuilder.error(
                    code="NOT_SUPPORTED",
                    message="현재 어댑터는 회로 가져오기(convert_to_python)를 지원하지 않습니다.",
                    suggestion="PSIM_MODE=real 환경에서 실행하세요.",
                )
            except Exception:
                self._logger.exception("convert_to_python failed: %s", path)
                return ResponseBuilder.error(
                    code="CONVERT_FAILED",
                    message="스키매틱을 Python 스크립트로 변환하는 중 오류가 발생했습니다.",
                )

            if not raw.get("success", False):
                err = raw.get("error", {}) if isinstance(raw, dict) else {}
                return ResponseBuilder.error(
                    code=err.get("code", "CONVERT_FAILED"),
                    message=err.get("message", "스키매틱 변환에 실패했습니다."),
                )

            data = raw.get("data", {})
            script_text = data.get("script_text", "")
            if not script_text:
                return ResponseBuilder.error(
                    code="EMPTY_SCRIPT",
                    message="변환된 스크립트가 비어 있습니다.",
                )

            from pathlib import Path

            from psim_mcp.importer import parse_converted_script, reconstruct

            try:
                parsed = parse_converted_script(script_text)
                result = reconstruct(parsed, topology=Path(path).stem)
            except SyntaxError:
                self._logger.exception("Converted script parse failed: %s", path)
                return ResponseBuilder.error(
                    code="IMPORT_PARSE_FAILED",
                    message="변환된 스크립트를 파싱하지 못했습니다.",
                )

            def _short(value: object, limit: int = 300) -> object:
                if isinstance(value, str) and len(value) > limit:
                    return value[:limit] + f"... ({len(value)} chars)"
                return value

            graph = result.graph
            payload = {
                "path": sanitize_path_for_display(path),
                "script_path": data.get("script_path", ""),
                "stats": result.stats,
                "simulation": graph.simulation,
                "components": [
                    {
                        "id": c.id,
                        "type": c.type,
                        "parameters": {k: _short(v) for k, v in c.parameters.items()},
                        "enabled": c.metadata.get("enabled", True),
                    }
                    for c in graph.components
                ],
                "nets": [
                    {
                        "id": n.id,
                        "pins": n.pins,
                        "labels": n.metadata.get("labels", []),
                        "role": n.role,
                    }
                    for n in graph.nets
                ],
                "dangling_pins": result.dangling_pins,
            }
            if include_graph:
                payload["graph"] = graph.to_dict()

            stats = result.stats
            message = (
                f"회로 구조 복원 완료: 소자 {stats['components']}개, "
                f"넷 {stats['nets']}개, 미연결 핀 {stats['dangling_pins']}개."
            )
            return ResponseBuilder.success(payload, message)

        return await self._audit.execute_with_audit(
            "import_circuit",
            {"path_hash": hash_input(path)},
            _handler,
        )

    async def get_status(self) -> dict:
        """Return current adapter and server status."""

        async def _handler():
            try:
                data = await self._adapter.get_status()
                return ResponseBuilder.success(data, "Status retrieved.")
            except Exception:
                self._logger.exception("Status check failed")
                return ResponseBuilder.error(
                    code="STATUS_FAILED",
                    message="상태 확인 중 오류가 발생했습니다.",
                )

        return await self._audit.execute_with_audit("get_status", {}, _handler)

    @property
    def is_project_open(self) -> bool:
        """Check if a project is currently open via the adapter."""
        return self._adapter.is_project_open
