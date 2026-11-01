"""set_parameter 파라미터 이름 해석 테스트.

실측(PSIM 2026.1): PsimSetElmValue2는 PsimGetElementList의 실제 Type('MOSFET')과
표시 이름('On Resistance')만 받는다. 'On_Resistance'나 Type 'MULTI_MOSFET'은
False를 반환하고 stdout에 'Unable to update element...'를 출력한다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import psim_mcp.bridge.bridge_script as bridge_script
from psim_mcp.adapters.base import ParameterError
from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.adapters.real_adapter import RealPsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.services.project_service import ProjectService
from psim_mcp.services.simulation_service import SimulationService
from psim_mcp.services.validators import normalize_parameter_name, validate_parameter_name

# ---------------------------------------------------------------------------
# PSIM을 흉내 내는 가짜 객체
# ---------------------------------------------------------------------------

_ELEMENTS = {
    "MOS1": (
        "MOSFET",
        [
            "Name",
            "On Resistance",
            "Diode Voltage Drop",
            "Rd",
            "Initial Position",
            "Current Flag",
            "Voltage Flag",
        ],
    ),
    "C2": ("C", ["Name", "Capacitance", "Init. Cap. Voltage", "Current Flag", "Voltage Flag"]),
    "G0": ("GATING", ["Name", "Frequency", "No. of Points", "Switching Points"]),
    # 정규화 키가 겹치는 인위적 소자(모호성 검사용)
    "X1": ("CUSTOM", ["Name", "Gain 1", "Gain_1"]),
}


def _elem(name: str) -> SimpleNamespace:
    etype, params = _ELEMENTS[name]
    return SimpleNamespace(
        Name=name,
        Type=etype,
        Index=0,
        Params=[SimpleNamespace(Name=p, Value="0") for p in params],
    )


class FakePsim:
    """실측한 PsimSetElmValue2 동작을 재현한다."""

    def __init__(self, reject_values: tuple[str, ...] = ()):
        self.set_calls: list[tuple] = []
        self.save_calls: list[tuple] = []
        self.reject_values = reject_values

    def PsimGetElementList(self, sch, flag):
        return [_elem(n) for n in _ELEMENTS]

    def PsimSetElmValue2(self, sch, comp_type, comp_name, param_name, value):
        self.set_calls.append((comp_type, comp_name, param_name, value))
        etype, params = _ELEMENTS.get(comp_name, (None, []))
        if comp_type != etype or param_name not in params or value in self.reject_values:
            print(
                "Unable to update element. Type:%s  Name:%s  VarName:%s  varValue:%s\n"
                % (comp_type, comp_name, param_name, value)
            )
            return False
        return True

    def PsimFileSave(self, sch, path):
        self.save_calls.append((sch, path))


@pytest.fixture
def fake_psim(monkeypatch) -> FakePsim:
    fake = FakePsim(reject_values=("bad",))
    monkeypatch.setattr(bridge_script, "_get_psim", lambda: fake)
    monkeypatch.setattr(bridge_script, "_current_sch", object())
    monkeypatch.setattr(bridge_script, "_current_path", "C:/tmp/buck.psimsch")
    monkeypatch.setattr(bridge_script, "_element_cache", {})
    monkeypatch.setattr(bridge_script, "_element_params", {})
    return fake


def _set(component_id, parameter_name, value="0.01", **extra):
    params = {"component_id": component_id, "parameter_name": parameter_name, "value": value}
    params.update(extra)
    return bridge_script.handle_set_parameter(params)


# ---------------------------------------------------------------------------
# 브리지: 이름·Type 해석
# ---------------------------------------------------------------------------


class TestBridgeNameResolution:
    @pytest.mark.parametrize("name", ["On Resistance", "On_Resistance", "on_resistance"])
    def test_space_underscore_and_alias_resolve_to_display_name(self, fake_psim, name):
        result = _set("MOS1", name)

        assert result["success"] is True, result
        assert result["data"]["psim_parameter_name"] == "On Resistance"
        assert fake_psim.set_calls[-1] == ("MOSFET", "MOS1", "On Resistance", "0.01")
        assert len(fake_psim.save_calls) == 1

    def test_dotted_display_name_from_script_name(self, fake_psim):
        result = _set("C2", "Init__Cap__Voltage", "5")

        assert result["success"] is True, result
        assert fake_psim.set_calls[-1] == ("C", "C2", "Init. Cap. Voltage", "5")

    def test_legacy_alias_mapping_still_works(self, fake_psim):
        # _COMPONENT_PARAM_MAP의 NoOfPoints → No__of_Points → 실제 'No. of Points'
        result = _set("G0", "NoOfPoints", "2")

        assert result["success"] is True, result
        assert result["data"]["psim_parameter_name"] == "No. of Points"

    def test_actual_type_overrides_caller_type(self, fake_psim):
        result = _set("MOS1", "On Resistance", component_type="MULTI_MOSFET")

        assert result["success"] is True, result
        assert result["data"]["component_type"] == "MOSFET"
        assert fake_psim.set_calls[-1][0] == "MOSFET"

    def test_unknown_name_returns_available_parameters(self, fake_psim):
        result = _set("MOS1", "Ron")

        assert result["success"] is False
        err = result["error"]
        assert err["code"] == "PARAMETER_NOT_FOUND"
        assert "On Resistance" in err["details"]["available_parameters"]
        assert "On Resistance" in err["message"]
        assert fake_psim.set_calls == []
        assert fake_psim.save_calls == []

    def test_ambiguous_name_is_rejected_without_guessing(self, fake_psim):
        result = _set("X1", "gain.1")

        assert result["success"] is False
        err = result["error"]
        assert err["code"] == "AMBIGUOUS_PARAMETER"
        assert sorted(err["details"]["candidates"]) == ["Gain 1", "Gain_1"]
        assert fake_psim.set_calls == []

    def test_exact_name_wins_over_ambiguous_normalized_match(self, fake_psim):
        result = _set("X1", "Gain_1")

        assert result["success"] is True, result
        assert fake_psim.set_calls[-1][2] == "Gain_1"

    def test_unknown_component(self, fake_psim):
        result = _set("NOPE", "Resistance")

        assert result["success"] is False
        assert result["error"]["code"] == "COMPONENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# 브리지: PSIM 거부(False 반환)와 stdout 경고
# ---------------------------------------------------------------------------


class TestBridgeRejection:
    def test_false_return_becomes_error_with_psim_output(self, fake_psim):
        stdout_before = sys.stdout

        result = _set("MOS1", "On Resistance", "bad")

        assert result["success"] is False
        err = result["error"]
        assert err["code"] == "PARAMETER_REJECTED"
        assert "Unable to update element" in err["message"]
        assert "Unable to update element" in err["details"]["psim_output"]
        assert err["details"]["psim_parameter_name"] == "On Resistance"
        # 거부되면 파일을 저장하지 않는다.
        assert fake_psim.save_calls == []
        # stdout(IPC 채널)은 원래대로 복원되어야 한다.
        assert sys.stdout is stdout_before

    def test_psim_output_not_leaked_to_stdout(self, fake_psim, capsys):
        _set("MOS1", "On Resistance", "bad")

        assert "Unable to update element" not in capsys.readouterr().out

    def test_falls_back_to_mapped_name_without_element_list(self, monkeypatch):
        """PsimGetElementList를 못 쓰면 기존 동작(매핑 이름 그대로)을 유지한다."""

        class NoListPsim:
            def __init__(self):
                self.set_calls = []

            def PsimSetElmValue2(self, sch, comp_type, comp_name, param_name, value):
                self.set_calls.append((comp_type, comp_name, param_name, value))
                return True

            def PsimFileSave(self, sch, path):
                pass

        fake = NoListPsim()
        monkeypatch.setattr(bridge_script, "_get_psim", lambda: fake)
        monkeypatch.setattr(bridge_script, "_current_sch", object())
        monkeypatch.setattr(bridge_script, "_current_path", "")
        monkeypatch.setattr(bridge_script, "_element_cache", {"R1": "R"})
        monkeypatch.setattr(bridge_script, "_element_params", {})

        result = _set("R1", "resistance", "10")

        assert result["success"] is True
        assert fake.set_calls == [("R", "R1", "Resistance", "10")]


# ---------------------------------------------------------------------------
# 정규화 규칙과 입력 검증
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "On Resistance",
        "On_Resistance",
        "Init. Cap. Voltage",
        "No__of_Points",
        "Np (primary)",
        "Ω x",
    ],
)
def test_bridge_and_server_normalization_agree(name):
    assert bridge_script._normalize_param_key(name) == normalize_parameter_name(name)


def test_script_names_equal_normalized_display_names():
    assert normalize_parameter_name("Init. Cap. Voltage") == "Init__Cap__Voltage".lower()
    assert normalize_parameter_name("No. of Points") == "No__of_Points".lower()
    assert normalize_parameter_name("On Resistance") == "on_resistance"


@pytest.mark.parametrize(
    "name",
    [
        "On Resistance",
        "On_Resistance",
        "Init. Cap. Voltage",
        "Np (primary)",
        "Lm__magnetizing_",
        "R",
        "A" * 64,
    ],
)
def test_validate_parameter_name_accepts(name):
    assert validate_parameter_name(name)


@pytest.mark.parametrize(
    "name",
    ["", " On", "On ", "1abc", "_x", "a;b", "a/b", "On\tR", "저항", "A" * 65],
)
def test_validate_parameter_name_rejects(name):
    assert not validate_parameter_name(name)


# ---------------------------------------------------------------------------
# 서비스·어댑터: 에러 코드와 후보 목록이 사용자에게 전달되는지
# ---------------------------------------------------------------------------


@pytest.fixture
def service(test_config: AppConfig) -> SimulationService:
    adapter = MockPsimAdapter()
    return SimulationService(
        adapter=adapter,
        config=test_config,
        project_service=ProjectService(adapter=adapter, config=test_config),
    )


class TestServiceErrors:
    async def test_space_name_passes_validation(self, service, sample_project_path: Path):
        await service.open_project(str(sample_project_path))

        result = await service.set_parameter("V1", "On Resistance", 0.01)

        # mock V1에는 없는 이름 → 검증은 통과하고 PARAMETER_NOT_FOUND + 목록
        assert result["success"] is False
        assert result["error"]["code"] == "PARAMETER_NOT_FOUND"
        assert result["error"]["details"]["available_parameters"]
        assert result["error"]["suggestion"].startswith("사용 가능한 파라미터:")

    async def test_invalid_characters_rejected(self, service, sample_project_path: Path):
        await service.open_project(str(sample_project_path))

        result = await service.set_parameter("V1", "On;Resistance", 0.01)

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"

    async def test_bridge_parameter_errors_reach_user(self, service, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        service._adapter.set_parameter = AsyncMock(
            side_effect=ParameterError(
                "AMBIGUOUS_PARAMETER",
                "Parameter 'gain.1' matches several parameters of 'X1': Gain 1, Gain_1",
                {"candidates": ["Gain 1", "Gain_1"]},
            )
        )

        result = await service.set_parameter("X1", "gain.1", 1)

        assert result["error"]["code"] == "AMBIGUOUS_PARAMETER"
        assert "Gain 1, Gain_1" in result["error"]["suggestion"]
        assert result["error"]["details"]["candidates"] == ["Gain 1", "Gain_1"]


@pytest.fixture
def real_adapter(tmp_path) -> RealPsimAdapter:
    fake_bridge = tmp_path / "bridge_script.py"
    fake_bridge.write_text("# dummy")
    config = AppConfig(
        psim_mode="real",
        psim_python_exe="python",
        psim_path=str(tmp_path),
        psim_output_dir=tmp_path / "output",
    )
    with patch("psim_mcp.adapters.real_adapter._BRIDGE_SCRIPT", str(fake_bridge)):
        return RealPsimAdapter(config)


class TestRealAdapterErrors:
    @pytest.mark.parametrize(
        "code",
        ["PARAMETER_NOT_FOUND", "AMBIGUOUS_PARAMETER", "PARAMETER_REJECTED", "COMPONENT_NOT_FOUND"],
    )
    async def test_bridge_error_raises_parameter_error(self, real_adapter, code):
        real_adapter._call_bridge = AsyncMock(
            return_value={
                "success": False,
                "error": {
                    "code": code,
                    "message": "msg",
                    "details": {"available_parameters": ["On Resistance"]},
                },
            }
        )

        with pytest.raises(ParameterError) as info:
            await real_adapter.set_parameter("MOS1", "Ron", 0.01)

        assert info.value.code == code
        assert info.value.details["available_parameters"] == ["On Resistance"]

    async def test_other_bridge_errors_stay_runtime_errors(self, real_adapter):
        real_adapter._call_bridge = AsyncMock(
            return_value={"success": False, "error": {"code": "PSIM_ERROR", "message": "boom"}}
        )

        with pytest.raises(RuntimeError, match="boom"):
            await real_adapter.set_parameter("MOS1", "On Resistance", 0.01)
