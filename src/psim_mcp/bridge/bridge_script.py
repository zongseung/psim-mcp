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
        for fn_name in ("open_schematic", "load", "open", "load_schematic"):
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
        for fn_name in ("set_param", "set_parameter", "set_element_param"):
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
        for fn_name in ("run", "simulate", "run_simulation", "run_sim"):
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
        for fn_name in ("export", "export_results", "get_results", "get_simulation_data"):
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
        for comp in components:
            comp_id = comp.get("id", "")
            comp_type = comp.get("type", "")
            comp_params = comp.get("parameters", {})
            position = comp.get("position", {"x": 0, "y": 0})

            try:
                elem = p.PsimCreateNewElement(
                    sch, comp_type,
                    position.get("x", 0),
                    position.get("y", 0),
                )
                if elem:
                    element_map[comp_id] = elem
                    for param_name, param_value in comp_params.items():
                        p.PsimSetElmValue(sch, elem, param_name, str(param_value))
            except Exception as e:
                # 개별 컴포넌트 실패 시 계속 진행
                pass

        # 파일 저장
        p.PsimFileSave(sch, save_path)

        return _success({
            "file_path": save_path,
            "component_count": len(element_map),
            "total_requested": len(components),
            "connection_count": len(connections),
            "status": "created",
        })

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
        for fn_name in ("get_all_elements", "get_elements", "get_components", "get_schematic_info"):
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
