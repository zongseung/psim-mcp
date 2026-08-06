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
    from psim_mcp.data.bridge_mapping_registry import (
        get_parameter_mapping as _registry_get_parameter_mapping,
    )
except Exception:  # pragma: no cover - bridge must still run in PSIM's isolated Python
    _registry_get_parameter_mapping = None


# Fallback parameter-name mapping for PSIM's isolated Python environment.
# Used when the registry import above is unavailable.
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
    "firing_angle": "Firing_Angle",
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

    # Fallback path runs inside PSIM's Python 3.8 where the registry
    # import fails. ``_PARAM_NAME_MAP`` is a FLAT parameter→PSIM-name
    # translation that's effectively universal (parameter names rarely
    # overlap across components), so we hand it back wholesale instead
    # of treating it as a per-component lookup (the original bug —
    # ``_PARAM_NAME_MAP.get("DC_Source")`` is always None, so every
    # parameter passed through untranslated and PSIM silently kept its
    # defaults).
    return _PARAM_NAME_MAP


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

        # ``TotalTime`` / ``TimeStep`` kwargs on PsimSimulate are silently
        # ignored — PSIM reads those values from the schematic's
        # "Simulation Control" element instead.  Patch the element directly
        # (same call the chassis ``simulation_overrides`` flow uses).
        for opt_key, sch_key in (("total_time", "TOTALTIME"),
                                  ("time_step", "TIMESTEP")):
            if opt_key in options:
                try:
                    with _suppress_stdout():
                        p.PsimSetElmValue(sim_target, None, sch_key,
                                          str(options[opt_key]))
                except Exception:
                    pass  # best-effort; sim may still run with schematic default

        sim_kwargs = {"Simview": options.get("simview", 1)}

        # Remaining (caller-supplied) overrides are forwarded as kwargs.
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


def handle_convert_to_python(params):
    """스키매틱(.psimsch)을 PsimConvertToPython으로 Python 스크립트로 변환한다.

    PsimGetElementList는 와이어·좌표·노드 정보를 반환하지 않으므로,
    기존 회로의 완전한 구조(소자 PORTS + WIRE 좌표 + LABEL)를 얻는
    유일한 API 경로가 이 변환이다. 생성된 스크립트 텍스트를 그대로
    반환하며, 파싱은 MCP 서버 측(psim_mcp.importer)에서 수행한다.
    """
    path = params.get("path")
    if not path:
        return _error("INVALID_INPUT", "path가 지정되지 않았습니다.")
    if not os.path.isfile(path):
        return _error("FILE_NOT_FOUND", "파일을 찾을 수 없습니다: %s" % path)

    output_path = params.get("output_path")
    if not output_path:
        import tempfile
        base = os.path.splitext(os.path.basename(path))[0]
        output_path = os.path.join(
            tempfile.gettempdir(), "%s_converted.py" % base
        )

    try:
        p = _get_psim()
        ret = p.PsimConvertToPython(path, output_path)
        if not os.path.isfile(output_path):
            return _error(
                "CONVERT_FAILED",
                "PsimConvertToPython이 출력 파일을 생성하지 못했습니다 (ret=%s)." % ret,
            )
        with open(output_path, "r", encoding="utf-8", errors="replace") as f:
            script_text = f.read()
        return _success({
            "source_path": path,
            "script_path": output_path,
            "script_text": script_text,
            "size": len(script_text),
        })
    except Exception as e:
        return _error("PSIM_ERROR", "스키매틱 변환 실패: %s" % str(e))


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

    # Capture every curve name up-front (cheap — just metadata, no Values[]
    # traversal). ``available_signals`` is the caller's only diagnostic when
    # metric specs don't match — e.g. the buck closed-loop chassis exports
    # ``Vo`` / ``IL_sensed`` rather than the canonical ``V(Vout)`` / ``I(L1)``.
    # Without this list a name mismatch makes analyze_existing look like a
    # silent parse failure.
    all_signal_names = [curve.Name for curve in res.Graph]

    # ONLY materialise Values[] for signals actually referenced by the metric
    # specs. For buck-cblock chassis (~20 signals × 1M points) loading every
    # curve into a Python list took 4+ minutes and tripped the MCP tool-call
    # timeout; filtering to the 1-3 referenced signals keeps analyze_existing
    # in single-digit seconds.
    needed_signal_names = {
        spec.get("signal", "") for spec in metrics_spec if spec.get("signal")
    }
    signal_data = {}
    for curve in res.Graph:
        if needed_signal_names and curve.Name not in needed_signal_names:
            continue
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
        "available_signals": all_signal_names,
        "loaded_signals": list(signal_data.keys()),
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
    "convert_to_python": handle_convert_to_python,
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
