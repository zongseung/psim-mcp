#!/usr/bin/env python
"""PSIM Bridge Script — PSIM 번들 Python 3.8로 실행됨.

이 스크립트는 MCP 서버(Python 3.12+)와 PSIM Python API(Python 3.8) 사이의
브릿지 역할을 한다. stdin으로 JSON 명령을 받고, PSIM API를 호출한 뒤,
stdout으로 JSON 결과를 반환한다.

프로토콜:
    입력 (stdin):  {"action": "open_project", "params": {"path": "..."}}
    출력 (stdout): {"success": true, "data": {...}}
                   {"success": false, "error": {"code": "...", "message": "..."}}

주의:
    - 이 파일은 PSIM 번들 Python 3.8에서 실행되므로 3.8 호환 문법만 사용
    - f-string, dataclass 등은 사용 가능하나 walrus operator(:=), match 등은 불가
    - MCP 서버의 의존성(pydantic, mcp 등)을 import하면 안 됨
"""

import json
import os
import sys
import time
import traceback


# ---------------------------------------------------------------------------
# PSIM API Wrapper
# ---------------------------------------------------------------------------
# PSIM Python API의 실제 함수명은 Windows에서 "Save as Python Code" 기능으로
# 확인 후 아래 함수들을 업데이트해야 한다.
# 현재는 import 시도 + 실패 시 명확한 에러를 반환하는 구조로 작성되어 있다.

_psim = None
_psim_available = False


def _ensure_psim():
    """PSIM 모듈을 로드한다. 실패 시 ImportError를 raise."""
    global _psim, _psim_available
    if _psim_available:
        return _psim
    try:
        import psim
        _psim = psim
        _psim_available = True
        return _psim
    except ImportError:
        raise ImportError(
            "PSIM Python API를 불러올 수 없습니다. "
            "PSIM이 설치되어 있고, PSIM 번들 Python으로 이 스크립트를 "
            "실행하고 있는지 확인하세요."
        )


# ---------------------------------------------------------------------------
# Function discovery candidates — ordered by likelihood.
# The actual function names must be confirmed via "Save as Python Code"
# analysis on Windows. See docs/ver1.1.1/06-windows-smoke-test.md.
# ---------------------------------------------------------------------------

_OPEN_FUNCTION_CANDIDATES = ("open_schematic", "load", "open", "load_schematic")
_SET_PARAM_CANDIDATES = ("set_param", "set_parameter", "set_element_param")
_RUN_SIM_CANDIDATES = ("run", "simulate", "run_simulation", "run_sim")
_EXPORT_CANDIDATES = ("export", "export_results", "get_results", "get_simulation_data")
_INFO_CANDIDATES = ("get_all_elements", "get_elements", "get_components", "get_schematic_info")
# Wire creation function candidates — ordered by likelihood.
# The actual function name must be confirmed via "Save as Python Code"
# analysis on Windows. See docs/ver1.1.1/06-windows-smoke-test.md.
_WIRE_FUNCTION_CANDIDATES = ("PsimCreateWire", "PsimConnect", "PsimCreateNewWire")


def _get_override_name(env_name):
    """Return a stripped override value from the environment, if present."""
    value = os.environ.get(env_name, "").strip()
    return value or None


def _resolve_wire_function(psim_instance):
    """Resolve the wire creation function with explicit override support."""
    override = _get_override_name("PSIM_WIRE_FUNCTION")
    if override:
        if hasattr(psim_instance, override):
            return getattr(psim_instance, override), override, None
        return None, override, "override_not_found"

    for fn_name in _WIRE_FUNCTION_CANDIDATES:
        if hasattr(psim_instance, fn_name):
            return getattr(psim_instance, fn_name), fn_name, None
    return None, None, "no_candidate_found"

# ---------------------------------------------------------------------------
# Action Handlers
# ---------------------------------------------------------------------------
# 각 핸들러는 params dict를 받고 결과 dict를 반환한다.
# PSIM API의 실제 함수명/시그니처가 확인되면 아래 TODO 부분을 교체한다.

def handle_open_project(params):
    """PSIM 프로젝트 파일을 연다."""
    path = params.get("path")
    if not path:
        return _error("INVALID_INPUT", "path가 지정되지 않았습니다.")

    psim = _ensure_psim()

    # TODO: PSIM API 확인 후 실제 호출로 교체
    # 예상 패턴 (Save as Python Code 기반):
    #   psim.open_schematic(path)
    #   components = psim.get_all_elements()
    #
    # 현재는 PSIM API 시그니처 미확인 상태이므로 아래 패턴을 시도한다.
    # 실패 시 에러 메시지에 사용 가능한 함수 목록을 포함하여 디버깅을 돕는다.
    try:
        # 시도 1: psim.load / psim.open_schematic / psim.open 등
        open_fn = None
        for fn_name in _OPEN_FUNCTION_CANDIDATES:
            if hasattr(psim, fn_name):
                open_fn = getattr(psim, fn_name)
                break

        if open_fn is None:
            available = [a for a in dir(psim) if not a.startswith("_")]
            return _error(
                "PSIM_API_ERROR",
                "프로젝트 열기 함수를 찾을 수 없습니다. "
                "사용 가능한 PSIM API 함수: %s" % ", ".join(available[:20]),
            )

        result = open_fn(path)
        return _success(_serialize(result) if result else {"path": path, "status": "opened"})

    except Exception as e:
        return _error("PSIM_ERROR", "프로젝트 열기 실패: %s" % str(e))


def handle_set_parameter(params):
    """컴포넌트 파라미터를 변경한다."""
    component_id = params.get("component_id")
    parameter_name = params.get("parameter_name")
    value = params.get("value")

    if not component_id or not parameter_name:
        return _error("INVALID_INPUT", "component_id와 parameter_name이 필요합니다.")

    psim = _ensure_psim()

    try:
        # TODO: PSIM API 확인 후 실제 호출로 교체
        set_fn = None
        for fn_name in _SET_PARAM_CANDIDATES:
            if hasattr(psim, fn_name):
                set_fn = getattr(psim, fn_name)
                break

        if set_fn is None:
            available = [a for a in dir(psim) if not a.startswith("_")]
            return _error(
                "PSIM_API_ERROR",
                "파라미터 설정 함수를 찾을 수 없습니다. "
                "사용 가능한 PSIM API 함수: %s" % ", ".join(available[:20]),
            )

        result = set_fn(component_id, parameter_name, value)
        return _success({
            "component_id": component_id,
            "parameter_name": parameter_name,
            "new_value": value,
            "raw_result": _serialize(result) if result else None,
        })

    except Exception as e:
        return _error("PSIM_ERROR", "파라미터 설정 실패: %s" % str(e))


def handle_run_simulation(params):
    """시뮬레이션을 실행한다."""
    options = params.get("options", {})

    psim = _ensure_psim()

    try:
        # TODO: PSIM API 확인 후 실제 호출로 교체
        run_fn = None
        for fn_name in _RUN_SIM_CANDIDATES:
            if hasattr(psim, fn_name):
                run_fn = getattr(psim, fn_name)
                break

        if run_fn is None:
            available = [a for a in dir(psim) if not a.startswith("_")]
            return _error(
                "PSIM_API_ERROR",
                "시뮬레이션 실행 함수를 찾을 수 없습니다. "
                "사용 가능한 PSIM API 함수: %s" % ", ".join(available[:20]),
            )

        start_time = time.time()
        result = run_fn()
        duration = time.time() - start_time

        return _success({
            "status": "completed",
            "duration_seconds": round(duration, 3),
            "raw_result": _serialize(result) if result else None,
        })

    except Exception as e:
        return _error("SIMULATION_FAILED", "시뮬레이션 실행 실패: %s" % str(e))


def handle_export_results(params):
    """시뮬레이션 결과를 내보낸다."""
    output_dir = params.get("output_dir", ".")
    fmt = params.get("format", "json")
    signals = params.get("signals")

    psim = _ensure_psim()

    try:
        # TODO: PSIM API 확인 후 실제 결과 추출 로직으로 교체
        # 예상 패턴:
        #   data = psim.get_simulation_data()
        #   또는 .smv 파일을 읽어 파싱
        export_fn = None
        for fn_name in _EXPORT_CANDIDATES:
            if hasattr(psim, fn_name):
                export_fn = getattr(psim, fn_name)
                break

        if export_fn is None:
            available = [a for a in dir(psim) if not a.startswith("_")]
            return _error(
                "PSIM_API_ERROR",
                "결과 추출 함수를 찾을 수 없습니다. "
                "사용 가능한 PSIM API 함수: %s" % ", ".join(available[:20]),
            )

        result = export_fn()
        return _success({
            "output_dir": output_dir,
            "format": fmt,
            "raw_result": _serialize(result) if result else None,
        })

    except Exception as e:
        return _error("EXPORT_FAILED", "결과 추출 실패: %s" % str(e))


def handle_get_status(params):
    """PSIM 연결 상태를 반환한다."""
    try:
        psim = _ensure_psim()
        version = getattr(psim, "__version__", getattr(psim, "version", "unknown"))
        return _success({
            "psim_available": True,
            "psim_version": str(version),
        })
    except ImportError:
        return _success({
            "psim_available": False,
            "psim_version": None,
        })


def handle_create_circuit(params):
    """psimapipy를 사용하여 새 PSIM 회로를 생성한다."""
    components = params.get("components", [])
    connections = params.get("connections", [])
    save_path = params.get("save_path")
    simulation_settings = params.get("simulation_settings", {})

    if not save_path:
        return _error("INVALID_INPUT", "save_path가 지정되지 않았습니다.")

    try:
        from psimapipy import PSIM

        p = PSIM("")
        if not p or not p.IsValid():
            return _error("PSIM_API_ERROR", "PSIM 인스턴스를 생성할 수 없습니다.")

        sch = p.PsimFileNew()
        if not sch:
            return _error("PSIM_API_ERROR", "새 스키매틱을 생성할 수 없습니다.")

        # 시뮬레이션 설정 적용
        ts = simulation_settings.get("time_step", 1e-5)
        tt = simulation_settings.get("total_time", 0.1)
        p.PsimSetElmValue(sch, None, "TIMESTEP", str(ts))
        p.PsimSetElmValue(sch, None, "TOTALTIME", str(tt))

        # 컴포넌트 배치
        element_map = {}
        failed_components = []
        for comp in components:
            comp_id = comp.get("id", "")
            comp_type = comp.get("type", "")
            comp_params = comp.get("parameters", {})
            position = comp.get("position", {"x": 0, "y": 0})

            try:
                element_type = comp.get("psim_element_type") or comp_type
                elem = p.PsimCreateNewElement(
                    sch, element_type,
                    position.get("x", 0),
                    position.get("y", 0),
                )
                if elem:
                    element_map[comp_id] = elem
                    for param_name, param_value in comp_params.items():
                        p.PsimSetElmValue(sch, elem, param_name, str(param_value))
                else:
                    failed_components.append({
                        "id": comp_id,
                        "type": comp_type,
                        "psim_element_type": element_type,
                        "reason": "PsimCreateNewElement returned None",
                    })
            except Exception as e:
                failed_components.append({
                    "id": comp_id,
                    "type": comp_type,
                    "psim_element_type": comp.get("psim_element_type") or comp_type,
                    "reason": str(e),
                })

        # 연결선 생성
        connected = 0
        failed_connections = []
        for conn in connections:
            from_pin = conn.get("from", "")
            to_pin = conn.get("to", "")
            try:
                wire_fn, wire_fn_name, wire_error = _resolve_wire_function(p)

                if wire_fn is not None:
                    # from/to에서 component_id와 pin 분리
                    from_parts = from_pin.split(".")
                    to_parts = to_pin.split(".")
                    from_elem = element_map.get(from_parts[0])
                    to_elem = element_map.get(to_parts[0])

                    if from_elem and to_elem:
                        wire_fn(sch, from_elem, to_elem)
                        connected += 1
                    else:
                        failed_connections.append({
                            "from": from_pin,
                            "to": to_pin,
                            "reason": "element not found in element_map",
                        })
                else:
                    # wire 함수가 없으면 전체 건너뜀 (한 번만 기록)
                    if not failed_connections or failed_connections[-1].get("reason") not in (
                        "no wire function found in psimapipy",
                        "configured wire function not found in psimapipy",
                    ):
                        reason = "no wire function found in psimapipy"
                        if wire_error == "override_not_found":
                            reason = "configured wire function not found in psimapipy"
                        failed_connections.append({
                            "from": from_pin,
                            "to": to_pin,
                            "reason": reason,
                            "wire_function": wire_fn_name,
                        })
            except Exception as e:
                failed_connections.append({
                    "from": from_pin,
                    "to": to_pin,
                    "reason": str(e),
                })

        # 파일 저장
        p.PsimFileSave(sch, save_path)

        result = {
            "file_path": save_path,
            "component_count": len(element_map),
            "total_requested": len(components),
            "connection_count": connected,
            "total_connections_requested": len(connections),
            "status": "created",
        }
        _, resolved_wire_function, _ = _resolve_wire_function(p)
        if resolved_wire_function:
            result["wire_function"] = resolved_wire_function

        if failed_components:
            result["failed_components"] = failed_components
        if failed_connections:
            result["failed_connections"] = failed_connections

        return _success(result)

    except ImportError:
        return _error(
            "PSIM_NOT_AVAILABLE",
            "psimapipy를 불러올 수 없습니다. "
            "PSIM이 설치되어 있고, PSIM 번들 Python으로 이 스크립트를 "
            "실행하고 있는지 확인하세요."
        )
    except Exception as e:
        return _error("CREATE_CIRCUIT_FAILED", "회로 생성 실패: %s" % str(e))


def handle_get_project_info(params):
    """열린 프로젝트의 상세 정보를 반환한다."""
    psim = _ensure_psim()

    try:
        # TODO: PSIM API 확인 후 실제 호출로 교체
        info_fn = None
        for fn_name in _INFO_CANDIDATES:
            if hasattr(psim, fn_name):
                info_fn = getattr(psim, fn_name)
                break

        if info_fn is None:
            available = [a for a in dir(psim) if not a.startswith("_")]
            return _error(
                "PSIM_API_ERROR",
                "프로젝트 정보 조회 함수를 찾을 수 없습니다. "
                "사용 가능한 PSIM API 함수: %s" % ", ".join(available[:20]),
            )

        result = info_fn()
        return _success(_serialize(result) if result else {})

    except Exception as e:
        return _error("PSIM_ERROR", "프로젝트 정보 조회 실패: %s" % str(e))


# ---------------------------------------------------------------------------
# Response Helpers
# ---------------------------------------------------------------------------

def _success(data):
    """표준 성공 응답을 생성한다."""
    return {"success": True, "data": data}


def _error(code, message):
    """표준 에러 응답을 생성한다."""
    return {"success": False, "error": {"code": code, "message": message}}


def _serialize(obj):
    """PSIM 객체를 JSON 직렬화 가능한 형태로 변환한다."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    # PSIM 객체 → 속성을 dict로 변환 시도
    try:
        return {k: _serialize(v) for k, v in vars(obj).items() if not k.startswith("_")}
    except TypeError:
        return str(obj)


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
}


def main():
    """stdin에서 JSON 명령을 읽고, 처리 후, stdout으로 JSON 응답을 출력한다."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            output = _error("INVALID_INPUT", "빈 입력입니다.")
            print(json.dumps(output))
            return

        command = json.loads(raw_input)
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
        # 예상하지 못한 에러 — stderr에 스택 트레이스, stdout에 에러 응답
        traceback.print_exc(file=sys.stderr)
        output = _error("INTERNAL_ERROR", "브릿지 내부 오류: %s" % str(e))

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
