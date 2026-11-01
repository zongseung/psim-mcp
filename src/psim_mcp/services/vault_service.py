"""Vault service: Google Drive original + local copy storage routine.

Layout
------
Drive (source of truth, e.g. ``G:\\내 드라이브\\PSIM``)::

    <project>/<project>.psimsch            latest original
    <project>/history/<project>_v001.psimsch  every committed version
    <project>/results/v002/simulation.json    simulation summary per version
    <project>/manifest.json                   version log (sha256, time, message)

Local (copies + working area, e.g. ``C:\\Users\\me\\psim-projects``)::

    <project>/<project>_v001.psimsch       local copy of each version
    <project>/work/<project>.psimsch       checked-out working file (PSIM runs here)
    <project>/work/.checkout.json          base version / hash of the checkout

Rules
-----
* Drive always wins.  A commit is refused when the Drive original changed after
  the checkout (another device committed in the meantime) unless ``force``.
* PSIM never writes onto the Drive folder directly; it runs on the local work
  file and the finished file is copied up (avoids sync/lock conflicts).
* Writes to Drive go to a temp name first and are then atomically renamed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")
DEFAULT_DRIVE_ROOT = r"G:\내 드라이브\PSIM"
DEFAULT_LOCAL_ROOT = str(Path.home() / "psim-projects")


class VaultError(Exception):
    """Expected, user-facing vault failure."""

    def __init__(self, code: str, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion


@dataclass(frozen=True)
class VaultPaths:
    project: str
    drive_dir: Path
    drive_file: Path
    history_dir: Path
    results_dir: Path
    manifest: Path
    local_dir: Path
    work_dir: Path
    work_file: Path
    checkout_info: Path


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp-vault")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def _atomic_write_json(data: dict, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp-vault")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, dst)


def vfmt(version: int) -> str:
    return f"v{version:03d}"


class VaultService:
    """File-level operations of the Drive-original / local-copy routine."""

    def __init__(self, drive_root: str | Path | None = None, local_root: str | Path | None = None):
        self.drive_root = Path(
            drive_root or os.environ.get("VAULT_DRIVE_ROOT") or DEFAULT_DRIVE_ROOT
        )
        self.local_root = Path(
            local_root or os.environ.get("VAULT_LOCAL_ROOT") or DEFAULT_LOCAL_ROOT
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def paths(self, project: str) -> VaultPaths:
        if not project or not _PROJECT_RE.match(project):
            raise VaultError(
                "INVALID_PROJECT_NAME",
                f"프로젝트 이름이 올바르지 않습니다: {project!r}",
                "영문/숫자로 시작하고 영문·숫자·_·- 만 사용하세요(최대 64자). 예: buck_48v",
            )
        d = self.drive_root / project
        loc = self.local_root / project
        w = loc / "work"
        return VaultPaths(
            project=project,
            drive_dir=d,
            drive_file=d / f"{project}.psimsch",
            history_dir=d / "history",
            results_dir=d / "results",
            manifest=d / "manifest.json",
            local_dir=loc,
            work_dir=w,
            work_file=w / f"{project}.psimsch",
            checkout_info=w / ".checkout.json",
        )

    def _require_roots(self) -> None:
        if not self.drive_root.exists():
            raise VaultError(
                "DRIVE_ROOT_MISSING",
                f"드라이브 원본 폴더를 찾을 수 없습니다: {self.drive_root}",
                "Google Drive for Desktop이 실행 중인지, VAULT_DRIVE_ROOT 경로가 맞는지 확인하세요.",
            )
        self.local_root.mkdir(parents=True, exist_ok=True)

    def _read_manifest(self, p: VaultPaths) -> dict:
        if not p.manifest.exists():
            raise VaultError(
                "PROJECT_NOT_FOUND",
                f"드라이브에 '{p.project}' 프로젝트가 없습니다.",
                "vault_register로 먼저 원본을 등록하세요.",
            )
        return json.loads(p.manifest.read_text(encoding="utf-8"))

    def _store_version(self, p: VaultPaths, src: Path, version: int) -> dict:
        """Copy *src* as version N: Drive history + Drive latest + local copy."""
        name = f"{p.project}_{vfmt(version)}.psimsch"
        _atomic_copy(src, p.history_dir / name)  # Drive: history
        _atomic_copy(src, p.drive_file)  # Drive: latest original
        local_copy = p.local_dir / name
        _atomic_copy(src, local_copy)  # Local: copy
        return {
            "drive_original": str(p.drive_file),
            "drive_history": str(p.history_dir / name),
            "local_copy": str(local_copy),
        }

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def status(self) -> dict:
        projects = []
        if self.drive_root.exists():
            for d in sorted(self.drive_root.iterdir()):
                m = d / "manifest.json"
                if d.is_dir() and m.exists():
                    try:
                        man = json.loads(m.read_text(encoding="utf-8"))
                        last = man["versions"][-1]
                        projects.append(
                            {
                                "project": d.name,
                                "current_version": vfmt(man["current_version"]),
                                "updated_at": last.get("saved_at"),
                                "last_message": last.get("message", ""),
                            }
                        )
                    except Exception:  # noqa: BLE001 - report but don't fail
                        projects.append({"project": d.name, "error": "manifest 읽기 실패"})
        return {
            "drive_root": str(self.drive_root),
            "drive_root_exists": self.drive_root.exists(),
            "local_root": str(self.local_root),
            "local_root_exists": self.local_root.exists(),
            "projects": projects,
        }

    def register(self, source_path: str, project: str, message: str = "") -> dict:
        """Register a .psimsch as v001 original of a new project."""
        self._require_roots()
        src = Path(source_path)
        if src.suffix.lower() != ".psimsch" or not src.is_file():
            raise VaultError("INVALID_SOURCE", f".psimsch 파일을 찾을 수 없습니다: {source_path}")
        p = self.paths(project)
        if p.manifest.exists():
            raise VaultError(
                "PROJECT_EXISTS",
                f"'{project}' 프로젝트가 이미 드라이브에 있습니다.",
                "수정은 vault_checkout → 작업 → vault_commit 또는 vault_edit_and_run을 사용하세요.",
            )
        files = self._store_version(p, src, 1)
        digest = sha256_of(p.drive_file)
        manifest = {
            "project": project,
            "current_version": 1,
            "versions": [
                {
                    "version": 1,
                    "sha256": digest,
                    "saved_at": _now(),
                    "message": message or "최초 등록",
                    "source": str(src),
                    "host": os.environ.get("COMPUTERNAME", ""),
                }
            ],
        }
        _atomic_write_json(manifest, p.manifest)
        return {"project": project, "version": vfmt(1), "sha256": digest, **files}

    def checkout(self, project: str, force: bool = False) -> dict:
        """Copy the Drive original into the local work folder."""
        self._require_roots()
        p = self.paths(project)
        man = self._read_manifest(p)
        if not p.drive_file.exists():
            raise VaultError("DRIVE_FILE_MISSING", f"드라이브 원본 파일이 없습니다: {p.drive_file}")

        if p.work_file.exists() and p.checkout_info.exists() and not force:
            info = json.loads(p.checkout_info.read_text(encoding="utf-8"))
            if sha256_of(p.work_file) != info.get("work_sha256"):
                raise VaultError(
                    "UNCOMMITTED_WORK",
                    "작업 폴더에 아직 커밋하지 않은 변경이 있습니다.",
                    "vault_commit으로 저장하거나, 버리려면 force=true로 다시 체크아웃하세요.",
                )

        p.work_dir.mkdir(parents=True, exist_ok=True)
        _atomic_copy(p.drive_file, p.work_file)
        digest = sha256_of(p.work_file)
        expected = man["versions"][-1]["sha256"]
        info = {
            "project": project,
            "base_version": man["current_version"],
            "base_sha256": digest,
            "work_sha256": digest,
            "checked_out_at": _now(),
            "drive_matches_manifest": digest == expected,
        }
        _atomic_write_json(info, p.checkout_info)
        return {
            "project": project,
            "base_version": vfmt(man["current_version"]),
            "work_file": str(p.work_file),
            "drive_matches_manifest": info["drive_matches_manifest"],
        }

    def commit(self, project: str, message: str = "", force: bool = False) -> dict:
        """Save the work file as the next version (Drive original + local copy)."""
        self._require_roots()
        p = self.paths(project)
        man = self._read_manifest(p)
        if not p.work_file.exists() or not p.checkout_info.exists():
            raise VaultError(
                "NOT_CHECKED_OUT",
                "체크아웃된 작업 파일이 없습니다.",
                "vault_checkout을 먼저 실행하세요.",
            )
        info = json.loads(p.checkout_info.read_text(encoding="utf-8"))

        drive_now = sha256_of(p.drive_file) if p.drive_file.exists() else None
        if drive_now != info["base_sha256"] and not force:
            raise VaultError(
                "CONFLICT",
                "체크아웃 이후 드라이브 원본이 다른 곳에서 변경되었습니다.",
                "vault_checkout(force=true)로 최신 원본을 다시 받아 작업하거나, 덮어쓰려면 force=true로 커밋하세요.",
            )

        work_digest = sha256_of(p.work_file)
        if work_digest == info["base_sha256"] and not force:
            return {
                "project": project,
                "committed": False,
                "version": vfmt(man["current_version"]),
                "reason": "변경 사항이 없어 새 버전을 만들지 않았습니다.",
            }

        version = man["current_version"] + 1
        files = self._store_version(p, p.work_file, version)
        man["current_version"] = version
        man["versions"].append(
            {
                "version": version,
                "sha256": work_digest,
                "saved_at": _now(),
                "message": message,
                "parent": info["base_version"],
                "host": os.environ.get("COMPUTERNAME", ""),
            }
        )
        _atomic_write_json(man, p.manifest)
        info.update(
            {
                "base_version": version,
                "base_sha256": work_digest,
                "work_sha256": work_digest,
                "committed_at": _now(),
            }
        )
        _atomic_write_json(info, p.checkout_info)
        return {
            "project": project,
            "committed": True,
            "version": vfmt(version),
            "sha256": work_digest,
            **files,
        }

    def save_results(
        self, project: str, version: int, summary: dict, smv_path: str | None = None
    ) -> dict:
        """Store a simulation summary (and optionally the .smv) under Drive results/vNNN."""
        p = self.paths(project)
        out = p.results_dir / vfmt(version)
        _atomic_write_json(summary, out / "simulation.json")
        saved = {"summary": str(out / "simulation.json")}
        if smv_path and Path(smv_path).is_file():
            dst = out / Path(smv_path).name
            _atomic_copy(Path(smv_path), dst)
            saved["smv"] = str(dst)
        return saved
