"""VaultService: Drive original / local copy storage routine (file-level)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psim_mcp.services.vault_service import VaultError, VaultService, sha256_of


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    drive = tmp_path / "drive"
    drive.mkdir()
    return drive, tmp_path / "local"


@pytest.fixture
def vault(roots) -> VaultService:
    drive, local = roots
    return VaultService(drive_root=drive, local_root=local)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    src = tmp_path / "buck.psimsch"
    src.write_bytes(b"<psim>v1</psim>")
    return src


def _edit_work(vault: VaultService, project: str, payload: bytes) -> Path:
    work = vault.paths(project).work_file
    work.write_bytes(work.read_bytes() + payload)
    return work


def test_status_reports_missing_drive(tmp_path: Path):
    v = VaultService(drive_root=tmp_path / "nope", local_root=tmp_path / "local")
    st = v.status()
    assert st["drive_root_exists"] is False
    assert st["projects"] == []


def test_register_creates_original_history_and_local_copy(vault, roots, source):
    drive, local = roots
    out = vault.register(str(source), "buck", "first")
    assert out["version"] == "v001"
    assert (drive / "buck" / "buck.psimsch").read_bytes() == source.read_bytes()
    assert (drive / "buck" / "history" / "buck_v001.psimsch").exists()
    assert (local / "buck" / "buck_v001.psimsch").exists()
    man = json.loads((drive / "buck" / "manifest.json").read_text(encoding="utf-8"))
    assert man["current_version"] == 1
    assert man["versions"][0]["sha256"] == sha256_of(source)


def test_register_rejects_duplicate_and_bad_input(vault, source, tmp_path):
    vault.register(str(source), "buck")
    with pytest.raises(VaultError) as e:
        vault.register(str(source), "buck")
    assert e.value.code == "PROJECT_EXISTS"
    with pytest.raises(VaultError) as e:
        vault.register(str(source), "bad name!")
    assert e.value.code == "INVALID_PROJECT_NAME"
    with pytest.raises(VaultError) as e:
        vault.register(str(tmp_path / "missing.psimsch"), "other")
    assert e.value.code == "INVALID_SOURCE"


def test_register_requires_drive_root(tmp_path, source):
    v = VaultService(drive_root=tmp_path / "nope", local_root=tmp_path / "local")
    with pytest.raises(VaultError) as e:
        v.register(str(source), "buck")
    assert e.value.code == "DRIVE_ROOT_MISSING"


def test_commit_without_changes_creates_no_version(vault, source):
    vault.register(str(source), "buck")
    vault.checkout("buck")
    out = vault.commit("buck")
    assert out["committed"] is False
    assert out["version"] == "v001"


def test_checkout_edit_commit_creates_next_version(vault, roots, source):
    drive, local = roots
    vault.register(str(source), "buck")
    vault.checkout("buck")
    work = _edit_work(vault, "buck", b"<edit/>")
    out = vault.commit("buck", "L1 change")
    assert out["committed"] is True and out["version"] == "v002"
    assert (drive / "buck" / "buck.psimsch").read_bytes() == work.read_bytes()
    assert (drive / "buck" / "history" / "buck_v001.psimsch").read_bytes() == source.read_bytes()
    assert (local / "buck" / "buck_v002.psimsch").exists()
    man = json.loads((drive / "buck" / "manifest.json").read_text(encoding="utf-8"))
    assert [v["version"] for v in man["versions"]] == [1, 2]
    assert man["versions"][1]["parent"] == 1


def test_checkout_refuses_uncommitted_work_unless_forced(vault, source):
    vault.register(str(source), "buck")
    vault.checkout("buck")
    _edit_work(vault, "buck", b"<dirty/>")
    with pytest.raises(VaultError) as e:
        vault.checkout("buck")
    assert e.value.code == "UNCOMMITTED_WORK"
    out = vault.checkout("buck", force=True)
    assert Path(out["work_file"]).read_bytes() == source.read_bytes()


def test_commit_detects_conflict_when_drive_changed(vault, roots, source):
    drive, _ = roots
    vault.register(str(source), "buck")
    vault.checkout("buck")
    (drive / "buck" / "buck.psimsch").write_bytes(b"changed on another device")
    _edit_work(vault, "buck", b"<mine/>")
    with pytest.raises(VaultError) as e:
        vault.commit("buck")
    assert e.value.code == "CONFLICT"
    assert vault.commit("buck", force=True)["committed"] is True


def test_commit_requires_checkout(vault, source):
    vault.register(str(source), "buck")
    with pytest.raises(VaultError) as e:
        vault.commit("buck")
    assert e.value.code == "NOT_CHECKED_OUT"


def test_unknown_project(vault):
    with pytest.raises(VaultError) as e:
        vault.checkout("ghost")
    assert e.value.code == "PROJECT_NOT_FOUND"


def test_save_results_writes_summary_and_optional_smv(vault, roots, source, tmp_path):
    drive, _ = roots
    vault.register(str(source), "buck")
    smv = tmp_path / "buck_result.smv"
    smv.write_bytes(b"wave")
    saved = vault.save_results("buck", 1, {"ok": True}, str(smv))
    assert json.loads(Path(saved["summary"]).read_text(encoding="utf-8")) == {"ok": True}
    assert (drive / "buck" / "results" / "v001" / "buck_result.smv").exists()


def test_status_lists_projects(vault, source):
    vault.register(str(source), "buck", "first")
    st = vault.status()
    assert st["projects"][0]["project"] == "buck"
    assert st["projects"][0]["current_version"] == "v001"
