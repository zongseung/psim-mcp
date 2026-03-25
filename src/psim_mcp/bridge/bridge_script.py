#!/usr/bin/env python
"""PSIM Bridge Script — psimapipy 기반 PSIM 2026 API 브릿지.

이 스크립트는 MCP 서버(Python 3.12+)와 PSIM Python API 사이의
브릿지 역할을 한다. stdin으로 JSON 명령을 받고, psimapipy를 호출한 뒤,
stdout으로 JSON 결과를 반환한다.

프로토콜:
    입력 (stdin):  {"action": "open_project", "params": {"path": "..."}}
    출력 (stdout): {"success": true, "data": {...}}
                   {"success": false, "error": {"code": "...", "message": "..."}}

PSIM API 참조 (psimapipy 2026.0):
    - PSIM(psim_folder_path) → 인스턴스 생성
    - p.IsValid() → bool
    - p.get_psim_version() → (ver, sub, subsub, subsubsub)
    - p.get_psim_version_name() → str
    - p.PsimFileNew() → sch
    - p.PsimFileOpen(path) → sch
    - p.PsimFileSave(sch, path)
    - p.PsimCreateNewElement(sch, type, name, PORTS=..., DIRECTION=0, **params)
    - p.PsimCreateNewElement(sch, "WIRE", "", X1=..., Y1=..., X2=..., Y2=...)
    - p.PsimSetElmValue(sch, elem, param_name, value)
    - p.PsimSetElmValue2(sch, type, name, param_name, value)
    - p.PsimGetElementList(sch, 0) → [element, ...]
    - p.PsimSimulate(sch_or_path, output_path, Simview=0, **params)
    - p.PsimReadGraphFile(path) → result with .Graph
"""

import json
import os
import sys
import time
import traceback

try:
    from psim_mcp.data.component_library import build_port_pin_map as _shared_build_port_pin_map
except Exception:  # pragma: no cover - bridge must still run in PSIM's isolated Python
    _shared_build_port_pin_map = None

try:
    from psim_mcp.data.bridge_mapping_registry import (
        get_parameter_mapping as _registry_get_parameter_mapping,
        get_port_pin_groups as _registry_get_port_pin_groups,
        get_psim_element_type as _registry_get_psim_element_type,
    )
except Exception:  # pragma: no cover - bridge must still run in PSIM's isolated Python
    _registry_get_parameter_mapping = None
    _registry_get_port_pin_groups = None
    _registry_get_psim_element_type = None


# ---------------------------------------------------------------------------
# 토폴로지별 기본 시뮬레이션 파라미터
# (이 스크립트는 PSIM Python 3.8에서 실행되므로 psim_mcp 모듈을 import할 수 없다.
#  simulation_defaults.py와 동일한 매핑을 인라인으로 유지한다.)
# ---------------------------------------------------------------------------

_SIMULATION_DEFAULTS = {
    # DC-DC 컨버터
    "buck": {"time_step": "1E-006", "total_time": "0.02"},
    "boost": {"time_step": "1E-006", "total_time": "0.02"},
    "buck_boost": {"time_step": "1E-006", "total_time": "0.02"},
    "flyback": {"time_step": "5E-007", "total_time": "0.01"},
    "forward": {"time_step": "5E-007", "total_time": "0.01"},
    "llc": {"time_step": "1E-007", "total_time": "0.005"},
    "dab": {"time_step": "1E-007", "total_time": "0.005"},
    # 인버터
    "half_bridge": {"time_step": "1E-006", "total_time": "0.04"},
    "full_bridge": {"time_step": "1E-006", "total_time": "0.04"},
    "three_phase_inverter": {"time_step": "1E-006", "total_time": "0.06"},
    # 정류기
    "diode_bridge_rectifier": {"time_step": "1E-005", "total_time": "0.06"},
    # PFC
    "boost_pfc": {"time_step": "1E-006", "total_time": "0.06"},
    "totem_pole_pfc": {"time_step": "5E-007", "total_time": "0.06"},
    # 모터 드라이브
    "bldc_drive": {"time_step": "1E-006", "total_time": "0.5"},
    "pmsm_foc_drive": {"time_step": "1E-006", "total_time": "0.5"},
    # 배터리 충전
    "cc_cv_charger": {"time_step": "1E-005", "total_time": "1.0"},
    # 태양광
    "pv_mppt_boost": {"time_step": "1E-006", "total_time": "0.1"},
    "pv_grid_tied": {"time_step": "1E-006", "total_time": "0.1"},
    # 필터
    "lc_filter": {"time_step": "1E-006", "total_time": "0.01"},
    "lcl_filter": {"time_step": "1E-006", "total_time": "0.01"},
}

_GLOBAL_DEFAULT = {"time_step": "1E-006", "total_time": "0.05"}


_FALLBACK_PORT_PIN_GROUPS = {
    "MOSFET": (("drain", "collector"), ("source", "emitter"), ("gate",)),
    "IGBT": (("collector", "drain"), ("emitter", "source"), ("gate",)),
    "Diode": (("anode",), ("cathode",)),
    "DIODE": (("anode",), ("cathode",)),
    "Schottky_Diode": (("anode",), ("cathode",)),
    "Zener_Diode": (("anode",), ("cathode",)),
    "DC_Source": (("positive", "pin1"), ("negative", "pin2")),
    "AC_Source": (("positive", "pin1"), ("negative", "pin2")),
    "Battery": (("positive", "pin1"), ("negative", "pin2")),
    "DC_Current_Source": (("positive", "pin1"), ("negative", "pin2")),
    "AC_Current_Source": (("positive", "pin1"), ("negative", "pin2")),
    "Inductor": (("pin1", "input"), ("pin2", "output")),
    "Resistor": (("pin1", "input"), ("pin2", "output")),
    "Capacitor": (("positive", "pin1"), ("negative", "pin2")),
    "Ground": (("pin1",),),
    "PWM_Generator": (("output",),),
    "Voltage_Probe": (("positive",),),
    "Current_Probe": (("input",), ("output",)),
    "DiodeBridge": (("ac_pos",), ("ac_neg",), ("dc_pos",), ("dc_neg",)),
    "Transformer": (
        ("primary1", "primary_in"),
        ("primary2", "primary_out"),
        ("secondary1", "secondary_out"),
        ("secondary2", "secondary_in"),
    ),
    "IdealTransformer": (
        ("primary1", "primary_in"),
        ("primary2", "primary_out"),
        ("secondary1", "secondary_out"),
        ("secondary2", "secondary_in"),
    ),
    "Center_Tap_Transformer": (
        ("primary_top",),
        ("primary_center",),
        ("primary_bottom",),
        ("secondary_top",),
        ("secondary_center",),
        ("secondary_bottom",),
    ),
}


def _build_port_pin_map(component):
    if _shared_build_port_pin_map is not None:
        return _shared_build_port_pin_map(component)

    comp_id = component.get("id", "")
    comp_type = component.get("type", "")
    ports = component.get("ports", [])
    groups = (
        _registry_get_port_pin_groups(comp_type)
        if _registry_get_port_pin_groups is not None
        else _FALLBACK_PORT_PIN_GROUPS.get(comp_type, ())
    )
    if not comp_id or not ports or not groups:
        return {}

    pin_map = {}
    for idx, aliases in enumerate(groups):
        base = idx * 2
        if len(ports) < base + 2:
            break
        coord = (ports[base], ports[base + 1])
        for alias in aliases:
            pin_map["%s.%s" % (comp_id, alias)] = coord
    return pin_map


# ---------------------------------------------------------------------------
# PSIM element type mapping
# ---------------------------------------------------------------------------
# Internal/generic type names → PSIM MULTI_* element types.
# PSIM's PsimConvertToPython output reveals that power components use
# MULTI_* prefixed types (e.g. MULTI_MOSFET, MULTI_DIODE, etc.).

_PSIM_TYPE_MAP = {
    "MOSFET": "MULTI_MOSFET",
    "IGBT": "MULTI_IGBT",
    "DIODE": "MULTI_DIODE",
    "Diode": "MULTI_DIODE",
    "L": "MULTI_INDUCTOR",
    "Inductor": "MULTI_INDUCTOR",
    "C": "MULTI_CAPACITOR",
    "Capacitor": "MULTI_CAPACITOR",
    "R": "MULTI_RESISTOR",
    "Resistor": "MULTI_RESISTOR",
    # These stay the same — no MULTI_ prefix
    "VDC": "VDC",
    "VAC": "VAC",
    "IDC": "IDC",
    "Ground": "Ground",
    "GATING": "GATING",
    "VP": "VP",
    "IP": "IP",
    "SIMCONTROL": "SIMCONTROL",
    "ONCTRL": "ONCTRL",
    "TF_1F_1": "TF_1F_1",
    "TF_IDEAL": "TF_IDEAL",
    "Transformer": "TF_1F_1",
    "IdealTransformer": "TF_IDEAL",
    "DiodeBridge": "BDIODE1",
    "AC_Source": "VAC",
    "DC_Source": "VDC",
    "BATTERY": "BATTERY",
    "GTO": "MULTI_GTO",
    "TRIAC": "MULTI_TRIAC",
}

# Internal parameter name → PSIM API parameter name mapping.
# None means the parameter should be skipped (not a PSIM creation parameter).
_PARAM_NAME_MAP = {
    # Sources
    "voltage": "Amplitude",
    "frequency": "Frequency",
    "current": "Amplitude",
    # Passives
    "resistance": "Resistance",
    "inductance": "Inductance",
    "capacitance": "Capacitance",
    # Switches — PSIM MULTI_* elements accept these directly
    "switching_frequency": None,  # skip — not a PSIM element param
    "on_resistance": "On_Resistance",
    "forward_voltage": "Diode_Voltage_Drop",
    # Flags
    "VoltageFlag": "Voltage_Flag",
    "CurrentFlag": "Current_Flag",
    # GATING params
    "Frequency": "Frequency",
    "NoOfPoints": "No__of_Points",
    "Switching_Points": "Switching_Points",
    # Transformer — PSIM uses Np/Ns (not Ratio)
    "turns_ratio": None,             # skip — use np_turns/ns_turns instead
    "np_turns": "Np__primary_",      # primary turns count
    "ns_turns": "Ns__secondary_",    # secondary turns count
    "magnetizing_inductance": "Lm__magnetizing_",
    "primary_inductance": "Inductance",
    # Series impedance (sources)
    "Lseries": "Lseries",
    "Rseries": "Rseries",
}

_PARAMETER_COMPONENT_ALIASES = {
    "VDC": "DC_Source",
    "VAC": "AC_Source",
    "IDC": "DC_Current_Source",
    "IAC": "AC_Current_Source",
    "BATTERY": "Battery",
    "GATING": "PWM_Generator",
    "SIMCONTROL": "SimControl",
    "MULTI_RESISTOR": "Resistor",
    "MULTI_INDUCTOR": "Inductor",
    "MULTI_CAPACITOR": "Capacitor",
    "MULTI_DIODE": "Diode",
    "MULTI_MOSFET": "MOSFET",
    "MULTI_IGBT": "IGBT",
    "TF_1F_1": "Transformer",
    "TF_IDEAL": "IdealTransformer",
}


def _get_parameter_name_mapping(component_type):
    """Resolve parameter-name mapping for a schematic element type."""
    candidates = []
    if component_type:
        candidates.append(component_type)
    alias = _PARAMETER_COMPONENT_ALIASES.get(component_type)
    if alias and alias not in candidates:
        candidates.append(alias)

    if _registry_get_parameter_mapping is not None:
        for candidate in candidates:
            mapping = _registry_get_parameter_mapping(candidate)
            if mapping:
                return mapping

    for candidate in candidates:
        mapping = _PARAM_NAME_MAP.get(candidate)
        if mapping:
            return mapping

    return {}


def _get_simulation_defaults(topology):
    """토폴로지에 맞는 기본 시뮬레이션 파라미터를 반환한다."""
    if not topology:
        return _GLOBAL_DEFAULT
    return _SIMULATION_DEFAULTS.get(topology.lower(), _GLOBAL_DEFAULT)


def _calculate_simcontrol_position(components):
    """컴포넌트 bounding box 바깥에 SIMCONTROL 위치를 계산한다."""
    if not components:
        return "{130, 40}"  # 컴포넌트 없으면 기본값

    max_x = max(c.get("position", {}).get("x", 0) for c in components)
    min_y = min(c.get("position", {}).get("y", 0) for c in components)

    # bounding box 우측 상단에서 100px 오프셋
    sim_x = max_x + 100
    sim_y = min_y - 50

    return "{%d, %d}" % (sim_x, sim_y)


# ---------------------------------------------------------------------------
# PSIM Instance Management
# ---------------------------------------------------------------------------

_psim_instance = None
_current_sch = None
_current_path = None
_element_cache = {}  # name → type 매핑 (set_parameter에서 component_type 자동 조회용)


def _build_element_cache():
    """열린 schematic의 모든 소자를 캐시한다 (name → type 매핑)."""
    global _element_cache
    _element_cache = {}
    if _current_sch is None:
        return
    try:
        p = _get_psim()
        elm_list = p.PsimGetElementList(_current_sch, 0)
        if elm_list:
            _element_cache = {elem.Name: elem.Type for elem in elm_list}
    except Exception:
        pass  # 캐시 빌드 실패해도 치명적이지 않음


class _suppress_stdout(object):
    """PSIM API가 stdout으로 에러/상태 메시지를 print하는 것을 차단한다.

    stdout은 JSON IPC 채널이므로 PSIM API의 print가 섞이면
    MCP 서버 측 JSON 파싱이 깨진다. 모든 PSIM API 호출을 이 컨텍스트
    매니저로 감싸야 한다.

    사용법::

        with _suppress_stdout():
            p.PsimFileSave(sch, path)
    """

    def __enter__(self):
        self._real = sys.stdout
        sys.stdout = open(os.devnull, "w")
        return self

    def __exit__(self, *_):
        sys.stdout.close()
        sys.stdout = self._real


def _get_psim():
    """PSIM 인스턴스를 반환한다. 없으면 생성."""
    global _psim_instance
    if _psim_instance is not None:
        return _psim_instance

    try:
        from psimapipy import PSIM
    except ImportError:
        raise ImportError(
            "psimapipy를 불러올 수 없습니다. "
            "PSIM이 설치되어 있고 psimapipy가 Python 환경에 설치되어 있는지 확인하세요."
        )

    psim_path = os.environ.get("PSIM_PATH", "")
    p = PSIM(psim_path)

    if not p or not p.IsValid():
        raise RuntimeError(
            "PSIM 인스턴스 생성 실패. PSIM_PATH=%s 경로에 psim2.dll이 있는지 확인하세요." % psim_path
        )

    _psim_instance = p
    return p


# ---------------------------------------------------------------------------
# Action Handlers
# ---------------------------------------------------------------------------

def handle_open_project(params):
    """PSIM 프로젝트 파일(.psimsch)을 연다."""
    global _current_sch, _current_path

    path = params.get("path")
    if not path:
        return _error("INVALID_INPUT", "path가 지정되지 않았습니다.")

    if not os.path.isfile(path):
        return _error("FILE_NOT_FOUND", "파일을 찾을 수 없습니다: %s" % path)

    try:
        p = _get_psim()
        sch = p.PsimFileOpen(path)
        if not sch:
            return _error("PSIM_API_ERROR", "스키매틱 파일을 열 수 없습니다: %s" % path)

        _current_sch = sch
        _current_path = path

        # element cache 빌드 (set_parameter에서 component_type 자동 조회용)
        _build_element_cache()

        # 소자 목록 조회
        components = []
        try:
            elm_list = p.PsimGetElementList(sch, 0)
            if elm_list:
                for elem in elm_list:
                    comp = {
                        "type": elem.Type,
                        "name": elem.Name,
                        "index": elem.Index,
                    }
                    if hasattr(elem, "Params") and elem.Params:
                        comp["parameters"] = {
                            param.Name: param.Value for param in elem.Params
                        }
                    components.append(comp)
        except Exception:
            pass  # 소자 목록 조회 실패해도 파일 열기는 성공

        return _success({
            "path": path,
            "status": "opened",
            "component_count": len(components),
            "components": components[:50],  # 최대 50개만 반환
        })

    except Exception as e:
        return _error("PSIM_ERROR", "프로젝트 열기 실패: %s" % str(e))


def handle_set_parameter(params):
    """Update a component parameter in the currently open schematic."""
    global _current_sch

    component_id = params.get("component_id")
    parameter_name = params.get("parameter_name")
    value = params.get("value")
    component_type = params.get("component_type")

    if not component_id or not parameter_name:
        return _error("INVALID_INPUT", "component_id and parameter_name are required.")

    if _current_sch is None:
        return _error("NO_PROJECT", "No project is open. Call open_project first.")

    if not component_type and not _element_cache:
        _build_element_cache()
    if not component_type:
        component_type = _element_cache.get(component_id, "")
    if not component_type:
        return _error("COMPONENT_NOT_FOUND", "Unknown component '%s'" % component_id)

    try:
        p = _get_psim()
        parameter_map = _get_parameter_name_mapping(component_type)
        psim_parameter_name = parameter_map.get(parameter_name, parameter_name)
        if psim_parameter_name is None:
            return _error(
                "UNSUPPORTED_PARAMETER",
                "Parameter '%s' is not directly writable for component type '%s'"
                % (parameter_name, component_type),
            )

        with _suppress_stdout():
            result = p.PsimSetElmValue2(
                _current_sch,
                component_type,
                component_id,
                psim_parameter_name,
                str(value),
            )
            if _current_path:
                p.PsimFileSave(_current_sch, _current_path)

        return _success({
            "component_id": component_id,
            "parameter_name": parameter_name,
            "psim_parameter_name": psim_parameter_name,
            "new_value": str(value),
            "persisted": bool(_current_path),
            "raw_result": result,
        })

    except Exception as e:
        return _error("PSIM_ERROR", "Parameter update failed: %s" % str(e))


def handle_run_simulation(params):
    """시뮬레이션을 실행한다."""
    global _current_sch, _current_path

    options = params.get("options", {})

    # 시뮬레이션 대상: 열린 sch 또는 직접 지정된 파일
    sch_path = params.get("schematic_path") or _current_path
    output_path = params.get("output_path", "")

    if _current_sch is None and not sch_path:
        return _error("NO_PROJECT", "열린 프로젝트가 없거나 schematic_path가 지정되지 않았습니다.")

    try:
        p = _get_psim()

        # 시뮬레이션 대상 결정
        sim_target = _current_sch if _current_sch else sch_path

        # 출력 경로가 없으면 기본값 생성
        if not output_path and sch_path:
            base = os.path.splitext(sch_path)[0]
            output_path = base + "_result.smv"

        # 시뮬레이션 옵션을 kwargs로 전달
        sim_kwargs = {"Simview": options.get("simview", 1)}
        if "total_time" in options:
            sim_kwargs["TotalTime"] = options["total_time"]
        if "time_step" in options:
            sim_kwargs["TimeStep"] = options["time_step"]

        # 추가 파라미터 오버라이드
        for key, val in options.items():
            if key not in ("simview", "total_time", "time_step"):
                sim_kwargs[key] = val

        start_time = time.time()
        result = p.PsimSimulate(sim_target, output_path, **sim_kwargs)
        duration = time.time() - start_time

        if result.Result == 0:
            return _error("SIMULATION_FAILED", "시뮬레이션 실패: %s" % result.ErrorMessage)

        # 그래프 데이터 요약
        graph_summary = []
        if hasattr(result, "Graph") and result.Graph:
            for curve in result.Graph:
                summary = {
                    "name": curve.Name,
                    "rows": curve.Rows,
                }
                if curve.Rows > 0:
                    summary["last_value"] = curve.Values[curve.Rows - 1]
                graph_summary.append(summary)

        return _success({
            "status": "completed",
            "duration_seconds": round(duration, 3),
            "output_path": output_path,
            "signal_count": len(graph_summary),
            "signals": graph_summary,
        })

    except Exception as e:
        return _error("SIMULATION_FAILED", "시뮬레이션 실행 실패: %s" % str(e))


def handle_export_results(params):
    """시뮬레이션 결과를 CSV로 내보낸다."""
    output_dir = params.get("output_dir", ".")
    signals = params.get("signals")
    graph_file = params.get("graph_file", "")

    if not graph_file:
        return _error("INVALID_INPUT", "graph_file 경로가 필요합니다.")

    try:
        p = _get_psim()

        res = p.PsimReadGraphFile(graph_file)
        if res.Result == 0:
            return _error("EXPORT_FAILED", "그래프 파일 읽기 실패: %s" % res.ErrorMessage)

        graph = res.Graph
        if not graph:
            return _error("EXPORT_FAILED", "그래프 데이터가 비어 있습니다.")

        # 시그널 필터링
        if signals:
            signal_set = set(signals)
            graph = [c for c in graph if c.Name in signal_set]

        # CSV 출력
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(graph_file))[0]
        out_file = os.path.join(output_dir, base + ".csv")

        with open(out_file, "w") as f:
            # 헤더
            names = [curve.Name for curve in graph]
            f.write(",".join(names) + "\n")

            # 데이터
            max_rows = max(curve.Rows for curve in graph)
            for i in range(max_rows):
                values = []
                for curve in graph:
                    if i < curve.Rows:
                        values.append(str(curve.Values[i]))
                    else:
                        values.append("")
                f.write(",".join(values) + "\n")

        return _success({
            "output_file": out_file,
            "format": "csv",
            "signal_count": len(graph),
            "signal_names": [c.Name for c in graph],
            "row_count": max_rows,
        })

    except Exception as e:
        return _error("EXPORT_FAILED", "결과 추출 실패: %s" % str(e))


def handle_get_status(params):
    """PSIM 연결 상태를 반환한다."""
    try:
        p = _get_psim()
        ver, sub, subsub, subsubsub = p.get_psim_version()
        version_name = p.get_psim_version_name()

        return _success({
            "psim_available": True,
            "psim_version": "%d.%d.%d.%d" % (ver, sub, subsub, subsubsub),
            "psim_version_name": version_name,
            "psim_path": os.environ.get("PSIM_PATH", ""),
            "project_open": _current_sch is not None,
            "current_project": _current_path,
        })
    except ImportError:
        return _success({
            "psim_available": False,
            "psim_version": None,
            "psim_version_name": None,
        })
    except Exception as e:
        return _success({
            "psim_available": False,
            "psim_version": None,
            "error": str(e),
        })


def handle_get_project_info(params):
    """열린 프로젝트의 상세 정보를 반환한다."""
    global _current_sch, _current_path

    if _current_sch is None:
        return _error("NO_PROJECT", "열린 프로젝트가 없습니다.")

    try:
        p = _get_psim()
        is_sub = p.PsimIsSubcircuit(_current_sch)

        # 소자 목록
        components = []
        elm_list = p.PsimGetElementList(_current_sch, 0)
        if elm_list:
            for elem in elm_list:
                comp = {
                    "type": elem.Type,
                    "name": elem.Name,
                    "index": elem.Index,
                }
                if hasattr(elem, "Params") and elem.Params:
                    comp["parameters"] = {
                        param.Name: param.Value for param in elem.Params
                    }
                components.append(comp)

        return _success({
            "path": _current_path,
            "is_subcircuit": is_sub,
            "component_count": len(components),
            "components": components,
        })

    except Exception as e:
        return _error("PSIM_ERROR", "프로젝트 정보 조회 실패: %s" % str(e))


def _resolve_pin_positions(components):
    """Build a dict: 'ComponentID.pin_name' -> (x, y) for all placed components.

    Pin positions are read from the ``ports`` field (a flat list of coordinates)
    which mirrors the PSIM PORTS format.  If ``ports`` is not present, falls
    back to ``position`` / ``position2`` fields for backward compatibility.
    """
    pin_map = {}

    for comp in components:
        comp_id = comp.get("id", "")
        comp_type = comp.get("type", "")
        ports = comp.get("ports", [])

        # ------------------------------------------------------------------
        # Fallback: build a ports list from position / position2 when the
        # new ``ports`` field is not yet provided by the generator.
        # ------------------------------------------------------------------
        if not ports:
            pos = comp.get("position", {})
            pos2 = comp.get("position2")
            x = pos.get("x", 0)
            y = pos.get("y", 0)
            if pos2:
                ports = [x, y, pos2.get("x", x + 50), pos2.get("y", y)]
            else:
                ports = [x, y]

        mapped = _build_port_pin_map({"id": comp_id, "type": comp_type, "ports": ports})
        if mapped:
            pin_map.update(mapped)
            continue

        if comp_type in ("Transformer", "IdealTransformer"):
            if len(ports) >= 4:
                pin_map["%s.pin1" % comp_id] = (ports[0], ports[1])
                pin_map["%s.pin2" % comp_id] = (ports[2], ports[3])
            else:
                x = comp.get("position", {}).get("x", 0)
                y = comp.get("position", {}).get("y", 0)
                pin_map["%s.primary_in" % comp_id] = (x, y + 8)
                pin_map["%s.primary_out" % comp_id] = (x, y + 22)
                pin_map["%s.secondary_out" % comp_id] = (x + 80, y + 8)
                pin_map["%s.secondary_in" % comp_id] = (x + 80, y + 22)
        elif comp_type == "Center_Tap_Transformer":
            x = comp.get("position", {}).get("x", 0)
            y = comp.get("position", {}).get("y", 0)
            pin_map["%s.primary_top" % comp_id] = (x, y + 6)
            pin_map["%s.primary_center" % comp_id] = (x, y + 15)
            pin_map["%s.primary_bottom" % comp_id] = (x, y + 24)
            pin_map["%s.secondary_top" % comp_id] = (x + 80, y + 6)
            pin_map["%s.secondary_center" % comp_id] = (x + 80, y + 15)
            pin_map["%s.secondary_bottom" % comp_id] = (x + 80, y + 24)
        else:
            # Generic fallback: first pair = pin1/positive, second = pin2/negative
            if len(ports) >= 2:
                pin_map["%s.pin1" % comp_id] = (ports[0], ports[1])
                pin_map["%s.positive" % comp_id] = (ports[0], ports[1])
            if len(ports) >= 4:
                pin_map["%s.pin2" % comp_id] = (ports[2], ports[3])
                pin_map["%s.negative" % comp_id] = (ports[2], ports[3])

    return pin_map


def _route_wire(p, sch, x1, y1, x2, y2):
    """Route a wire between two points, using L-shaped routing if needed."""
    # Skip zero-length wires (pins at same location are already connected)
    if x1 == x2 and y1 == y2:
        return
    with _suppress_stdout():
        if x1 == x2 or y1 == y2:
            # Straight line
            p.PsimCreateNewElement(
                sch, "WIRE", "",
                X1=str(x1), Y1=str(y1), X2=str(x2), Y2=str(y2),
            )
        else:
            # L-shaped: go horizontal first, then vertical
            p.PsimCreateNewElement(
                sch, "WIRE", "",
                X1=str(x1), Y1=str(y1), X2=str(x2), Y2=str(y1),
            )
            p.PsimCreateNewElement(
                sch, "WIRE", "",
                X1=str(x2), Y1=str(y1), X2=str(x2), Y2=str(y2),
            )


def _handle_template_circuit(psim_template, save_path):
    """PSIM 예제 파일을 복사하고 파라미터만 변경하여 회로를 생성한다."""
    import shutil
    global _current_sch, _current_path

    psim_path = os.environ.get("PSIM_PATH", "")
    source_rel = psim_template.get("source", "")
    source_path = os.path.join(psim_path, source_rel)

    if not os.path.isfile(source_path):
        return _error("TEMPLATE_NOT_FOUND",
                       "PSIM template not found: %s" % source_path)
    try:
        save_dir = os.path.dirname(save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
        shutil.copy2(source_path, save_path)

        p = _get_psim()
        sch = p.PsimFileOpen(save_path)
        if not sch:
            return _error("PSIM_API_ERROR", "Failed to open template file.")

        applied = 0
        for ov in psim_template.get("parameter_overrides", []):
            try:
                p.PsimSetElmValue2(sch, ov["type"], ov["name"],
                                   ov["param"], str(ov["value"]))
                applied += 1
            except Exception:
                pass

        for key, val in psim_template.get("simulation_overrides", {}).items():
            try:
                p.PsimSetElmValue(sch, None, key, str(val))
            except Exception:
                pass

        p.PsimFileSave(sch, save_path)
        _current_sch = sch
        _current_path = save_path
        _build_element_cache()

        return _success({
            "file_path": save_path,
            "mode": "template",
            "template_source": source_rel,
            "parameters_applied": applied,
            "status": "created",
        })
    except Exception as e:
        return _error("TEMPLATE_ERROR",
                       "Template circuit creation failed: %s" % str(e))


def handle_create_circuit(params):
    """psimapipy를 사용하여 새 PSIM 회로를 생성한다.

    PSIM 2026 API 기준 (PsimConvertToPython 출력 기반):
    - 소자: PsimCreateNewElement(sch, "MULTI_MOSFET", name, PORTS=[x1,y1,...], DIRECTION=0, SubType="Ideal", ...)
    - 와이어: PsimCreateNewElement(sch, "WIRE", "", X1=str, Y1=str, X2=str, Y2=str)
    - 시뮬레이션 설정: PsimCreateNewElement(sch, "SIMCONTROL", "", POINT="{x,y}", TIMESTEP=..., TOTALTIME=...)

    PORTS는 Python list (문자열 아님)이며, MULTI_* 타입에는 SubType="Ideal"이 필요하다.
    """
    global _current_sch, _current_path

    components = params.get("components", [])
    wire_segments = params.get("wire_segments", [])
    save_path = params.get("save_path")
    simulation_settings = params.get("simulation_settings") or {}

    if not save_path:
        return _error("INVALID_INPUT", "save_path가 지정되지 않았습니다.")

    # --- Template mode: copy PSIM example and modify parameters ---
    psim_template = params.get("psim_template")
    if psim_template:
        return _handle_template_circuit(psim_template, save_path)

    try:
        p = _get_psim()

        with _suppress_stdout():
            sch = p.PsimFileNew()

        if not sch:
            return _error("PSIM_API_ERROR", "새 스키매틱을 생성할 수 없습니다.")

        # 토폴로지별 기본 시뮬레이션 파라미터 적용
        circuit_type = params.get("circuit_type", "")
        defaults = _get_simulation_defaults(circuit_type)
        ts = simulation_settings.get("time_step", defaults["time_step"])
        tt = simulation_settings.get("total_time", defaults["total_time"])

        # SIMCONTROL 위치를 컴포넌트 bounding box 바깥에 배치
        simcontrol_point = _calculate_simcontrol_position(components)
        with _suppress_stdout():
            p.PsimCreateNewElement(
                sch, "SIMCONTROL", "",
                POINT=simcontrol_point,
                TIMESTEP=str(ts),
                TOTALTIME=str(tt),
            )

        # 컴포넌트 배치
        element_map = {}
        failed_components = []
        for comp in components:
            comp_id = comp.get("id", "")
            comp_type = comp.get("type", "")
            comp_name = comp.get("name", comp_id)
            comp_params = comp.get("parameters", {})
            position = comp.get("position", {"x": 0, "y": 0})
            direction = comp.get("direction", 0)

            # Resolve the actual PSIM element type via the mapping table.
            # Priority: explicit psim_element_type > _PSIM_TYPE_MAP > raw type
            raw_psim_type = comp.get("psim_element_type") or comp_type
            psim_type = (
                _registry_get_psim_element_type(raw_psim_type)
                if _registry_get_psim_element_type is not None
                else _PSIM_TYPE_MAP.get(raw_psim_type, raw_psim_type)
            )

            try:
                # ----------------------------------------------------------
                # Build PORTS as a Python list (PSIM 2026 native format).
                # The ``ports`` field is a flat list of coordinates produced
                # by the circuit generators, e.g. [150, 100, 200, 100, 180, 120].
                # ----------------------------------------------------------
                ports_list = comp.get("ports")

                if not ports_list:
                    # Fallback: build from position / position2
                    x = position.get("x", 0)
                    y = position.get("y", 0)
                    position2 = comp.get("position2")
                    if position2:
                        ports_list = [x, y, position2.get("x", x + 50), position2.get("y", y)]
                    else:
                        ports_list = [x, y]

                # Build kwargs for PsimCreateNewElement
                kwargs = {
                    "PORTS": ports_list,
                    "DIRECTION": direction,
                    "PAGE": 0,
                    "XFLIP": 0,
                    "_OPTIONS_": 16,
                }

                # MULTI_* elements require SubType="Ideal"
                if psim_type.startswith("MULTI_"):
                    kwargs["SubType"] = "Ideal"

                # Map and add parameters (내부 이름 → PSIM API 이름)
                parameter_map = _get_parameter_name_mapping(comp_type)
                for param_name, param_value in comp_params.items():
                    psim_name = parameter_map.get(param_name, param_name)
                    if psim_name is not None:
                        kwargs[psim_name] = str(param_value)

                with _suppress_stdout():
                    elem = p.PsimCreateNewElement(
                        sch, psim_type, comp_name, **kwargs
                    )

                element_map[comp_id] = {
                    "elem": elem,
                    "position": position,
                    "type": psim_type,
                }

            except Exception as e:
                failed_components.append({
                    "id": comp_id,
                    "type": comp_type,
                    "psim_element_type": psim_type,
                    "reason": str(e),
                })

        # 와이어(연결선) 생성
        connected = 0
        failed_connections = []

        # Phase 4: wire_segments have explicit coordinates from routing engine.
        # When available, use them directly as straight segments (no L-shape re-routing).
        if wire_segments:
            for seg in wire_segments:
                try:
                    if all(k in seg for k in ("x1", "y1", "x2", "y2")):
                        with _suppress_stdout():
                            p.PsimCreateNewElement(
                                sch, "WIRE", "",
                                X1=str(int(seg["x1"])), Y1=str(int(seg["y1"])),
                                X2=str(int(seg["x2"])), Y2=str(int(seg["y2"])),
                            )
                        connected += 1
                    else:
                        failed_connections.append({
                            "segment": seg,
                            "reason": "missing x1/y1/x2/y2 keys",
                        })
                except Exception as e:
                    failed_connections.append({
                        "segment": seg,
                        "reason": str(e),
                    })
        else:
            # Fallback: resolve pin positions and route via from/to or coordinate pairs.
            # PHASE 4 NOTE: This branch is fallback for when wire_segments are not
            # provided. When wire_segments are available (from routing engine), the
            # above branch handles wiring directly without _resolve_pin_positions.
            connections = params.get("connections", [])
            pin_map = _resolve_pin_positions(components)
            for conn in connections:
                try:
                    # 연결 방식 1: 좌표 기반 (직접 좌표 지정)
                    if "x1" in conn and "y1" in conn:
                        _route_wire(
                            p, sch,
                            int(conn["x1"]), int(conn["y1"]),
                            int(conn["x2"]), int(conn["y2"]),
                        )
                        connected += 1
                        continue

                    # 연결 방식 2: from/to 핀 이름 기반 -> pin_map에서 좌표 조회
                    from_pin = conn.get("from", "")
                    to_pin = conn.get("to", "")

                    from_pos = pin_map.get(from_pin)
                    to_pos = pin_map.get(to_pin)

                    if from_pos and to_pos:
                        _route_wire(p, sch, from_pos[0], from_pos[1], to_pos[0], to_pos[1])
                        connected += 1
                    else:
                        missing_pins = []
                        if not from_pos:
                            missing_pins.append("from='%s'" % from_pin)
                        if not to_pos:
                            missing_pins.append("to='%s'" % to_pin)
                        failed_connections.append({
                            "from": from_pin,
                            "to": to_pin,
                            "reason": "pin position not found: %s" % ", ".join(missing_pins),
                        })

                except Exception as e:
                    failed_connections.append({
                        "connection": conn,
                        "reason": str(e),
                    })

        # 파일 저장
        # 저장 디렉토리가 없으면 생성
        save_dir = os.path.dirname(save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

        with _suppress_stdout():
            p.PsimFileSave(sch, save_path)

        # 저장 결과 검증
        if not os.path.isfile(save_path):
            return _error("SAVE_FAILED",
                          "PSIM 파일 저장에 실패했습니다: %s" % save_path)

        _current_sch = sch
        _current_path = save_path
        _build_element_cache()

        total_requested_conns = len(wire_segments) if wire_segments else len(params.get("connections", []))
        result = {
            "file_path": save_path,
            "component_count": len(element_map),
            "total_requested": len(components),
            "connection_count": connected,
            "total_connections_requested": total_requested_conns,
            "status": "created",
        }

        if failed_components:
            result["failed_components"] = failed_components
        if failed_connections:
            result["failed_connections"] = failed_connections

        return _success(result)

    except ImportError:
        return _error(
            "PSIM_NOT_AVAILABLE",
            "psimapipy를 불러올 수 없습니다. "
            "PSIM이 설치되어 있고 psimapipy가 Python 환경에 설치되어 있는지 확인하세요."
        )
    except Exception as e:
        return _error("CREATE_CIRCUIT_FAILED", "회로 생성 실패: %s" % str(e))


# ---------------------------------------------------------------------------
# Simulation metric extraction functions
# ---------------------------------------------------------------------------

def _steady_state_slice(values, skip_ratio=0.5):
    """Skip transient startup, return steady-state portion."""
    start = int(len(values) * skip_ratio)
    return values[start:] if start < len(values) else values


def _metric_mean(values, skip_ratio=0.5):
    ss = _steady_state_slice(values, skip_ratio)
    return sum(ss) / len(ss) if ss else 0.0


def _metric_ripple_pp(values, skip_ratio=0.5):
    ss = _steady_state_slice(values, skip_ratio)
    return (max(ss) - min(ss)) if ss else 0.0


def _metric_ripple_percent(values, skip_ratio=0.5):
    ss = _steady_state_slice(values, skip_ratio)
    if not ss:
        return 0.0
    avg = sum(ss) / len(ss)
    return ((max(ss) - min(ss)) / abs(avg) * 100.0) if avg != 0 else 0.0


def _metric_rms(values, skip_ratio=0.5):
    ss = _steady_state_slice(values, skip_ratio)
    return (sum(v * v for v in ss) / len(ss)) ** 0.5 if ss else 0.0


def _metric_max_value(values, skip_ratio=0.5):
    ss = _steady_state_slice(values, skip_ratio)
    return max(ss) if ss else 0.0


def _metric_min_value(values, skip_ratio=0.5):
    ss = _steady_state_slice(values, skip_ratio)
    return min(ss) if ss else 0.0


def _metric_overshoot_percent(values, target, skip_ratio=0.0):
    if not values or target == 0:
        return 0.0
    peak = max(values)
    return max(0.0, (peak - target) / abs(target) * 100.0)


def _metric_settling_time(values, time_step, target, band=0.02, skip_ratio=0.0):
    if not values or target == 0:
        return 0.0
    threshold = abs(target * band)
    for i in range(len(values) - 1, -1, -1):
        if abs(values[i] - target) > threshold:
            return (i + 1) * time_step
    return 0.0


_METRIC_FUNCTIONS = {
    "mean": _metric_mean,
    "ripple_pp": _metric_ripple_pp,
    "ripple_percent": _metric_ripple_percent,
    "rms": _metric_rms,
    "max": _metric_max_value,
    "min": _metric_min_value,
    "overshoot_percent": _metric_overshoot_percent,
    "settling_time": _metric_settling_time,
}


# ---------------------------------------------------------------------------
# Signal extraction and metric computation handlers
# ---------------------------------------------------------------------------

def handle_extract_signals(params):
    """Extract raw signal data from the last simulation or a graph file."""
    graph_file = params.get("graph_file", "")
    signal_names = params.get("signals")  # None = all
    skip_ratio = float(params.get("skip_ratio", 0.0))
    max_points = int(params.get("max_points", 2000))

    p = _get_psim()

    if not graph_file and _current_path:
        base = os.path.splitext(_current_path)[0]
        graph_file = base + "_result.smv"

    if not graph_file or not os.path.isfile(graph_file):
        return _error("NO_GRAPH_FILE", "결과 파일을 찾을 수 없습니다: %s" % graph_file)

    with _suppress_stdout():
        res = p.PsimReadGraphFile(graph_file)

    if res.Result == 0:
        return _error("READ_FAILED", "그래프 파일 읽기 실패")

    output = {}
    for curve in res.Graph:
        if signal_names and curve.Name not in signal_names:
            continue
        values = list(curve.Values[:curve.Rows])
        start = int(len(values) * skip_ratio)
        values = values[start:]
        if len(values) > max_points:
            step = max(1, len(values) // max_points)
            values = values[::step]
        output[curve.Name] = [round(v, 9) for v in values]

    return _success({
        "signals": output,
        "signal_names": list(output.keys()),
        "point_count": len(next(iter(output.values()), [])),
        "graph_file": graph_file,
    })


def handle_compute_metrics(params):
    """Compute metrics from simulation results."""
    graph_file = params.get("graph_file", "")
    metrics_spec = params.get("metrics", [])
    skip_ratio = float(params.get("skip_ratio", 0.5))
    time_step = float(params.get("time_step", 1e-6))

    p = _get_psim()

    if not graph_file and _current_path:
        base = os.path.splitext(_current_path)[0]
        graph_file = base + "_result.smv"

    if not graph_file or not os.path.isfile(graph_file):
        return _error("NO_GRAPH_FILE", "결과 파일이 없습니다: %s" % graph_file)

    with _suppress_stdout():
        res = p.PsimReadGraphFile(graph_file)

    if res.Result == 0:
        return _error("READ_FAILED", "그래프 파일 읽기 실패")

    signal_data = {}
    for curve in res.Graph:
        signal_data[curve.Name] = list(curve.Values[:curve.Rows])

    results = {}
    for spec in metrics_spec:
        name = spec.get("name", "")
        sig_name = spec.get("signal", "")
        fn_name = spec.get("function", "")
        kwargs = spec.get("kwargs", {})

        if sig_name not in signal_data:
            results[name] = {"error": "signal '%s' not found" % sig_name}
            continue

        fn = _METRIC_FUNCTIONS.get(fn_name)
        if fn is None:
            results[name] = {"error": "unknown function '%s'" % fn_name}
            continue

        values = signal_data[sig_name]
        try:
            if fn_name in ("overshoot_percent",):
                target = float(kwargs.get("target", 0))
                result = fn(values, target, skip_ratio)
            elif fn_name in ("settling_time",):
                target = float(kwargs.get("target", 0))
                band = float(kwargs.get("band", 0.02))
                result = fn(values, time_step, target, band, skip_ratio)
            else:
                result = fn(values, skip_ratio)
            results[name] = round(result, 6)
        except Exception as e:
            results[name] = {"error": str(e)}

    return _success({
        "metrics": results,
        "available_signals": list(signal_data.keys()),
        "graph_file": graph_file,
    })


# ---------------------------------------------------------------------------
# Response Helpers
# ---------------------------------------------------------------------------

def _success(data):
    """표준 성공 응답을 생성한다."""
    return {"success": True, "data": data}


def _error(code, message):
    """표준 에러 응답을 생성한다."""
    return {"success": False, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Action Dispatch
# ---------------------------------------------------------------------------

_ACTION_HANDLERS = {
    "open_project": handle_open_project,
    "set_parameter": handle_set_parameter,
    "run_simulation": handle_run_simulation,
    "export_results": handle_export_results,
    "get_status": handle_get_status,
    "get_project_info": handle_get_project_info,
    "create_circuit": handle_create_circuit,
    "extract_signals": handle_extract_signals,
    "compute_metrics": handle_compute_metrics,
}


def main():
    """stdin에서 JSON 명령을 줄 단위로 읽고, 처리 후, stdout으로 JSON 응답을 한 줄씩 출력한다.

    장기 실행(long-running) 프로세스로 동작하여, 호출 간 _psim_instance,
    _current_sch, _current_path 등 전역 상태를 유지한다.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            command = json.loads(line)
            action = command.get("action")
            params = command.get("params", {})

            handler = _ACTION_HANDLERS.get(action)
            if handler is None:
                output = _error(
                    "UNKNOWN_ACTION",
                    "알 수 없는 action: %s. 지원: %s" % (action, ", ".join(_ACTION_HANDLERS.keys())),
                )
            else:
                output = handler(params)

        except json.JSONDecodeError as e:
            output = _error("INVALID_JSON", "JSON 파싱 실패: %s" % str(e))
        except ImportError as e:
            output = _error("PSIM_NOT_AVAILABLE", str(e))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            output = _error("INTERNAL_ERROR", "브릿지 내부 오류: %s" % str(e))

        # 한 줄로 출력 (줄바꿈으로 구분), flush로 즉시 전송
        print(json.dumps(output, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
