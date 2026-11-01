"""Vault MCP tools wired into create_app (mock adapter)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.server import create_app
from psim_mcp.tools.vault import _compare, _verify


@pytest.fixture
def env(tmp_path: Path):
    drive = tmp_path / "drive"
    drive.mkdir()
    local = tmp_path / "local"
    cfg = AppConfig(
        psim_mode="mock",
        psim_output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        allowed_project_dirs=[str(tmp_path)],
        vault_drive_root=drive,
        vault_local_root=local,
    )
    app = create_app(cfg)
    src = tmp_path / "buck.psimsch"
    src.write_bytes(b"<psim/>")
    return app, drive, local, src


async def _call(app, name: str, **kwargs) -> dict:
    result = await app.call_tool(name, kwargs)
    blocks = result[0] if isinstance(result, tuple) else result
    return json.loads(blocks[0].text)


async def test_status_and_register(env):
    app, drive, local, src = env
    st = await _call(app, "vault_status")
    assert st["success"] and st["data"]["drive_root_exists"]
    reg = await _call(app, "vault_register", source_path=str(src), project="buck")
    assert reg["success"] and reg["data"]["version"] == "v001"
    dup = await _call(app, "vault_register", source_path=str(src), project="buck")
    assert dup["success"] is False and dup["error"]["code"] == "PROJECT_EXISTS"


async def test_checkout_opens_work_file(env):
    app, drive, local, src = env
    await _call(app, "vault_register", source_path=str(src), project="buck")
    co = await _call(app, "vault_checkout", project="buck")
    assert co["success"] and co["data"]["opened"] is True
    assert co["data"]["work_file"].endswith(str(Path("buck") / "work" / "buck.psimsch"))


async def test_edit_and_run_commits_new_version_and_results(env):
    app, drive, local, src = env
    await _call(app, "vault_register", source_path=str(src), project="buck")

    # The mock adapter keeps parameters in memory; emulate PSIM's PsimFileSave
    # by touching the opened work file so the commit sees a real change.
    adapter = app._adapter
    original = adapter.set_parameter

    async def set_and_save(component_id, parameter_name, value):
        out = await original(component_id, parameter_name, value)
        work = local / "buck" / "work" / "buck.psimsch"
        work.write_bytes(work.read_bytes() + f"<{component_id}={value}/>".encode())
        return out

    adapter.set_parameter = set_and_save

    res = await _call(
        app,
        "vault_edit_and_run",
        project="buck",
        changes=[{"component_id": "L1", "parameter_name": "inductance", "value": 2.2e-5}],
    )
    assert res["success"], res
    data = res["data"]
    assert data["commit"]["committed"] is True and data["commit"]["version"] == "v002"
    assert data["changes"][0]["check"]["status"] in {"verified", "unverified"}
    assert (drive / "buck" / "history" / "buck_v002.psimsch").exists()
    assert (local / "buck" / "buck_v002.psimsch").exists()
    assert (drive / "buck" / "results" / "v002" / "simulation.json").exists()

    hist = await _call(app, "vault_history", project="buck")
    assert [v["version"] for v in hist["data"]["versions"]] == [1, 2]


async def test_edit_and_run_rejects_bad_change_and_keeps_original(env):
    app, drive, local, src = env
    await _call(app, "vault_register", source_path=str(src), project="buck")
    before = (drive / "buck" / "buck.psimsch").read_bytes()
    res = await _call(app, "vault_edit_and_run", project="buck", changes=[{"component_id": "L1"}])
    assert res["success"] is False and res["error"]["code"] == "INVALID_CHANGE"
    assert (drive / "buck" / "buck.psimsch").read_bytes() == before


async def test_edit_and_run_blocks_silent_noop(env):
    app, drive, local, src = env
    await _call(app, "vault_register", source_path=str(src), project="buck")
    before = (drive / "buck" / "buck.psimsch").read_bytes()

    adapter = app._adapter

    async def ok_set(component_id, parameter_name, value):  # PSIM ignores unknown names
        return {"component_id": component_id}

    async def info():
        return {"components": [{"name": "L1", "parameters": {"Inductance": "4.7e-5"}}]}

    adapter.set_parameter = ok_set
    adapter.get_project_info = info

    res = await _call(
        app,
        "vault_edit_and_run",
        project="buck",
        changes=[{"component_id": "L1", "parameter_name": "Inductnce", "value": 1e-5}],
    )
    assert res["success"] is False and res["error"]["code"] == "PARAM_NOT_APPLIED"
    assert "Inductance" in (res["error"]["suggestion"] or "")
    assert (drive / "buck" / "buck.psimsch").read_bytes() == before


@pytest.mark.parametrize(
    ("actual", "requested", "expected"),
    [
        ("22u", 2.2e-5, "same"),
        ("4.7e-5", 4.7e-5, "same"),
        ("100k", 1e5, "same"),
        ("1meg", 1e6, "same"),
        ("10", 11, "different"),
        ("Lval", 1e-5, "unknown"),
        ("2.2m", "2.2m", "same"),
    ],
)
def test_compare_handles_si_suffixes(actual, requested, expected):
    assert _compare(actual, requested) == expected


async def test_verify_statuses():
    class P:
        def __init__(self, info):
            self.info = info

        async def get_project_info(self):
            return self.info

    info = {"data": {"components": [{"name": "L1", "parameters": {"Inductance": "4.7e-5"}}]}}
    assert (await _verify(P(info), "L1", "Inductance", 4.7e-5))["status"] == "verified"
    assert (await _verify(P(info), "L1", "Inductance", 1e-5))["status"] == "not_applied"
    assert (await _verify(P(info), "L1", "Inductnce", 1e-5))["status"] == "not_applied"
    assert (await _verify(P(info), "L9", "Inductance", 1e-5))["status"] == "unverified"
