# 기존 PSIM 회로 안전 편집 및 멀티 클라이언트 구현 계획

> **에이전트 작업자용:** 필수 하위 스킬은 `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans`이다. 각 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** Codex, ChatGPT Desktop, Claude Desktop에서 기존 `.psimsch`를 원본 훼손 없이 분석하고, 작업 사본의 소자값 또는 C-block 코드를 수정한 뒤 재가져오기로 저장 결과를 검증한다.

**아키텍처:** 실제 호출 경로를 `MCP 도구 -> 전용 도메인 서비스 -> 어댑터 -> 기존 PSIM 브리지`로 고정한다. `ProjectService`가 읽기와 작업 사본 생성을, `ParameterService`가 입력 검증을, 기존 브리지의 `PsimSetElmValue2`와 `PsimFileSave`가 실제 저장을 담당한다. 레거시 `SimulationService` 파사드는 이번 구현에서 삭제하지 않고 호출자 이전 후 별도 삭제한다.

**기술 스택:** Python 3.12+, FastMCP 1.26+, Pydantic Settings, pytest/pytest-asyncio, Windows PSIM Python 브리지, 표준 라이브러리 `hashlib`·`json`·`pathlib`·`shutil`·`tomllib`.

## 전역 제약

- 새 런타임 의존성을 추가하지 않는다.
- 원본 `.psimsch`는 절대 열어서 수정하지 않는다. 모든 쓰기는 `prepare_edit`가 만든 새 사본에만 수행한다.
- 기본 작업 사본은 `PSIM_PROJECT_DIR/working/<원본명>_working.psimsch`에 만들며 기존 파일을 덮어쓰지 않는다.
- 첫 버전은 독립형 `.psimsch` 한 파일만 `shutil.copy2`로 복사한다. sidecar 의존성 복사는 실제 입력에서 필요성이 확인될 때 추가한다.
- 일반 문자열 파라미터는 최대 1,024자, `CONTENT`는 최대 65,536자이며 NUL 문자는 거부한다.
- `CONTENT` 쓰기는 PSIM에서 확인된 `CBLOCK` 또는 `SIMPLECBLOCK`에만 허용한다.
- 회로 분석과 수정은 시뮬레이션을 자동 실행하지 않는다. `run_simulation`은 사용자가 요청했을 때만 별도 호출한다.
- 자연어 해석은 Codex·ChatGPT·Claude가 담당한다. 서버에 두 번째 자연어 파서나 LLM 호출 계층을 추가하지 않는다.
- 기존 `include_graph` 동작과 공개 `set_parameter(component_id, parameter_name, value)` 서명은 유지한다.
- DQ 원본 SHA-256은 `70FCEAF9416DC025A5212B0E43A9ACA35D02CE9E3A80D6C2A123D26AB05FF924`이다.
- Interleaving Boost 원본 SHA-256은 `428BF7175CDAC61276FBD423A84B3C357B99EE58411988E605B05AE289FBA603`이다.
- 실파일은 저장소에 복사하지 않고 `PSIM_DQ_EXAMPLE_PATH`, `PSIM_INTERLEAVING_EXAMPLE_PATH`로 주입한다.
- 알려진 기준선 문제인 `test_hybrid_resolver_golden.py` 수집 오류, `test_elicitation.py` 실패, Windows `test_svg_renderer.py` 첫 실행 실패는 별도 변경으로 남긴다.

---

## 파일 구조와 책임

| 파일 | 변경 책임 |
|---|---|
| `src/psim_mcp/server.py` | 전용 파라미터·시뮬레이션 서비스와 실제 앱 설정을 도구에 주입한다. |
| `src/psim_mcp/tools/parameter.py` | `set_parameter`와 sweep가 서로 다른 전용 서비스를 사용하게 한다. |
| `src/psim_mcp/tools/project.py` | `include_source_code`와 `prepare_edit` MCP 계약을 노출한다. |
| `src/psim_mcp/services/project_service.py` | 전체 C-block 반환과 안전한 작업 사본 생성·열기를 담당한다. |
| `src/psim_mcp/services/parameter_service.py` | 일반 문자열/C-block 길이, NUL, 성공 메시지 노출을 검증한다. |
| `src/psim_mcp/bridge/bridge_script.py` | 실제 PSIM 소자 타입을 확인한 뒤 `CONTENT` 쓰기를 허용한다. |
| `src/psim_mcp/tools/__init__.py` | 서비스 응답을 데이터 손실 없이 JSON으로 직렬화한다. |
| `src/psim_mcp/utils/sanitize.py` | 크기 초과 응답을 잘린 문자열 대신 유효한 JSON 오류로 반환한다. |
| `src/psim_mcp/data/topology_metrics.py` | Interleaving Boost 비교에 필요한 `I(L1)` 리플 메트릭을 노출한다. |
| `tests/unit/*` | 서비스 배선, 사본 안전성, C-block 검증, JSON 무결성을 고정한다. |
| `tests/real/*` | 사용자가 제공한 두 원본으로 실제 PSIM 저장·재가져오기·리플 비교를 검증한다. |
| `README.md`, `.env.example`, `claude_desktop_config.example.json` | 세 데스크톱 클라이언트 설정과 안전한 사용 흐름을 문서화한다. |

## Task 1: 파라미터 도구를 전용 서비스에 연결

**Files:**
- Modify: `tests/unit/test_app_factory.py`
- Modify: `src/psim_mcp/tools/parameter.py`
- Modify: `src/psim_mcp/server.py`

**Interfaces:**
- Consumes: `ParameterService.set_parameter(component_id, parameter_name, value)`, `SimulationService.run_simulation(options=None)`, `AppConfig.max_sweep_steps`.
- Produces: `register_tools(mcp, parameter_service=None, simulation_service=None, config=None)`와 `register_all_tools(mcp, services, config=None)`.

- [ ] **Step 1: 운영 도구가 전용 서비스를 사용하는 실패 테스트를 작성한다**

`tests/unit/test_app_factory.py`에 `json`, `AsyncMock`을 가져오고 다음 테스트를 추가한다.

```python
import json
from unittest.mock import AsyncMock, patch


async def test_registered_parameter_tools_use_domain_services():
    app = create_app(AppConfig(psim_mode="mock", max_sweep_steps=4))
    parameter_service = app._services["parameter"]
    simulation_service = app._services["simulation"]

    parameter_service.set_parameter = AsyncMock(
        return_value={"success": True, "data": {}, "message": "set"}
    )
    simulation_service.set_parameter = AsyncMock(
        side_effect=AssertionError("legacy set_parameter was called")
    )
    simulation_service.run_simulation = AsyncMock(
        return_value={"success": True, "data": {"summary": {}}, "message": "run"}
    )

    raw = await app._tool_manager.call_tool(
        "set_parameter",
        {"component_id": "L1", "parameter_name": "inductance", "value": "250u"},
        convert_result=False,
    )
    assert json.loads(raw)["success"] is True
    parameter_service.set_parameter.assert_awaited_once_with("L1", "inductance", "250u")
    simulation_service.set_parameter.assert_not_awaited()

    parameter_service.set_parameter.reset_mock()
    raw = await app._tool_manager.call_tool(
        "sweep_parameter",
        {
            "component_id": "L1",
            "parameter_name": "inductance",
            "start": 1.0,
            "end": 2.0,
            "step": 1.0,
        },
        convert_result=False,
    )
    assert json.loads(raw)["success"] is True
    assert parameter_service.set_parameter.await_count == 2
    assert simulation_service.run_simulation.await_count == 2
    simulation_service.set_parameter.assert_not_awaited()


async def test_registered_sweep_uses_create_app_config():
    app = create_app(AppConfig(psim_mode="mock", max_sweep_steps=1))
    raw = await app._tool_manager.call_tool(
        "sweep_parameter",
        {
            "component_id": "L1",
            "parameter_name": "inductance",
            "start": 1.0,
            "end": 2.0,
            "step": 1.0,
        },
        convert_result=False,
    )
    result = json.loads(raw)
    assert result["success"] is False
    assert result["error"]["code"] == "SWEEP_LIMIT_EXCEEDED"
```

- [ ] **Step 2: 테스트가 현재 레거시 서비스 호출과 전역 설정 사용 때문에 실패하는지 확인한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_app_factory.py -v
```

Expected: 첫 테스트는 `legacy set_parameter was called`, 두 번째 테스트는 sweep 제한 미적용으로 FAIL한다.

- [ ] **Step 3: 도구에 파라미터·시뮬레이션 서비스와 앱 설정을 각각 주입한다**

`src/psim_mcp/tools/parameter.py`의 등록 함수와 내부 선택을 다음 구조로 바꾼다.

```python
def register_tools(
    mcp,
    parameter_service=None,
    simulation_service=None,
    config=None,
):
    """Register parameter mutation and sweep tools."""

    @mcp.tool(description="열린 프로젝트의 컴포넌트 파라미터를 변경합니다.")
    @tool_handler("set_parameter")
    async def set_parameter(component_id, parameter_name, value) -> str:
        svc = parameter_service or _get_service()
        return await svc.set_parameter(component_id, parameter_name, value)

    @mcp.tool(description="파라미터를 범위 안에서 변경하며 반복 시뮬레이션합니다.")
    @tool_handler("sweep_parameter")
    async def sweep_parameter(component_id, parameter_name, start, end, step, metrics=None) -> str:
        parameter_svc = parameter_service or _get_service()
        simulation_svc = simulation_service or _get_service()
        cfg = config or _get_config()
        # 기존 검증과 반복문은 유지한다.
```

기존 sweep 반복문 안의 두 호출만 다음과 같이 분리한다.

```python
await parameter_svc.set_parameter(component_id, parameter_name, current)
sim_result = await simulation_svc.run_simulation()
```

`src/psim_mcp/server.py`는 설정 인자를 선택적으로 받고 실제 앱 생성 시 명시적으로 전달한다.

```python
def register_all_tools(mcp: FastMCP, services: dict, config: AppConfig | None = None) -> None:
    project.register_tools(mcp, services["project"])
    parameter.register_tools(
        mcp,
        services["parameter"],
        services["simulation"],
        config,
    )
    simulation.register_tools(mcp, services["simulation"])
    # 나머지 등록은 현재 순서와 서비스를 유지한다.


# create_app 내부
register_all_tools(app, services, config)
```

- [ ] **Step 4: 앱 팩토리와 기존 파라미터 테스트를 실행한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_app_factory.py tests\unit\test_parameter_service.py tests\unit\test_tool_integration.py -q
```

Expected: PASS.

- [ ] **Step 5: 배선 교정을 커밋한다**

```powershell
git add src/psim_mcp/server.py src/psim_mcp/tools/parameter.py tests/unit/test_app_factory.py
git commit -m "refactor: route parameter tools through domain services"
```

## Task 2: 원본을 보존하는 `prepare_edit` 추가

**Files:**
- Modify: `tests/unit/test_project_service.py`
- Modify: `tests/unit/test_app_factory.py`
- Modify: `src/psim_mcp/services/project_service.py`
- Modify: `src/psim_mcp/tools/project.py`

**Interfaces:**
- Consumes: `validate_project_path`, `validate_save_path`, `BasePsimAdapter.open_project(path)`.
- Produces: `ProjectService.prepare_edit(path: str, save_path: str | None = None) -> dict`와 동명 MCP 도구.

- [ ] **Step 1: 복사·해시·덮어쓰기 거부·실패 정리 테스트를 작성한다**

`tests/unit/test_project_service.py`에 다음 테스트를 추가한다.

```python
import hashlib
from pathlib import Path

from psim_mcp.adapters.mock_adapter import MockPsimAdapter


async def test_prepare_edit_copies_opens_and_hashes_source(
    project_service, mock_adapter, test_config, sample_project_path
):
    source_bytes = b"original-psim-data"
    sample_project_path.write_bytes(source_bytes)

    result = await project_service.prepare_edit(str(sample_project_path))

    assert result["success"] is True
    working = Path(result["data"]["working_path"])
    assert working == Path(test_config.psim_project_dir) / "working" / "test_project_working.psimsch"
    assert working.read_bytes() == source_bytes
    assert result["data"]["source_sha256"] == hashlib.sha256(source_bytes).hexdigest().upper()
    assert result["data"]["status"] == "opened"
    assert mock_adapter.is_project_open is True


async def test_prepare_edit_refuses_existing_destination(
    project_service, sample_project_path, tmp_path
):
    destination = tmp_path / "already.psimsch"
    destination.write_bytes(b"keep-me")

    result = await project_service.prepare_edit(
        str(sample_project_path), save_path=str(destination)
    )

    assert result["success"] is False
    assert result["error"]["code"] == "WORKING_COPY_EXISTS"
    assert destination.read_bytes() == b"keep-me"


async def test_prepare_edit_removes_copy_when_open_fails(
    test_config, sample_project_path, tmp_path
):
    class RejectingAdapter(MockPsimAdapter):
        async def open_project(self, path: str) -> dict:
            return {
                "success": False,
                "error": {"code": "PSIM_ERROR", "message": "open rejected"},
            }

    destination = tmp_path / "rejected.psimsch"
    service = ProjectService(adapter=RejectingAdapter(), config=test_config)
    result = await service.prepare_edit(str(sample_project_path), str(destination))

    assert result["success"] is False
    assert result["error"]["code"] == "OPEN_PROJECT_FAILED"
    assert destination.exists() is False
```

- [ ] **Step 2: 새 메서드가 없어 테스트가 실패하는지 확인한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_project_service.py -v
```

Expected: `AttributeError: 'ProjectService' object has no attribute 'prepare_edit'`로 FAIL한다.

- [ ] **Step 3: 표준 라이브러리만 사용해 작업 사본을 생성하고 연다**

`src/psim_mcp/services/project_service.py`에 `hashlib`, `shutil`, `Path`, `validate_save_path`를 가져오고 다음 메서드를 추가한다.

```python
async def prepare_edit(self, path: str, save_path: str | None = None) -> dict:
    """Copy an existing schematic to a new path and open only the copy."""

    async def _handler():
        source_check = validate_project_path(
            path, self._config.allowed_project_dirs or None
        )
        if not source_check.is_valid:
            return ResponseBuilder.error(
                code=source_check.error_code or "VALIDATION_ERROR",
                message=source_check.error_message or "Invalid source path.",
            )

        source = Path(path).resolve()
        if save_path is None:
            if self._config.psim_project_dir is None:
                return ResponseBuilder.error(
                    code="CONFIG_ERROR",
                    message="PSIM_PROJECT_DIR is required when save_path is omitted.",
                )
            destination = (
                Path(self._config.psim_project_dir)
                / "working"
                / f"{source.stem}_working.psimsch"
            ).resolve()
        else:
            destination = Path(save_path).resolve()

        destination_check = validate_save_path(
            str(destination), self._config.allowed_project_dirs or None
        )
        if not destination_check.is_valid:
            return ResponseBuilder.error(
                code=destination_check.error_code or "VALIDATION_ERROR",
                message=destination_check.error_message or "Invalid destination path.",
            )
        if destination.exists():
            return ResponseBuilder.error(
                code="WORKING_COPY_EXISTS",
                message="The requested working copy already exists.",
            )

        with source.open("rb") as source_file:
            source_sha256 = hashlib.file_digest(source_file, "sha256").hexdigest().upper()

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except Exception:
            self._logger.exception("Failed to copy project")
            destination.unlink(missing_ok=True)
            return ResponseBuilder.error(
                code="COPY_FAILED", message="Failed to create the working copy."
            )

        try:
            opened = await self._adapter.open_project(str(destination))
            if isinstance(opened, dict) and opened.get("success") is False:
                destination.unlink(missing_ok=True)
                return ResponseBuilder.error(
                    code="OPEN_PROJECT_FAILED",
                    message=opened.get("error", {}).get("message", "Failed to open working copy."),
                )
        except Exception:
            self._logger.exception("Failed to open working copy")
            destination.unlink(missing_ok=True)
            return ResponseBuilder.error(
                code="OPEN_PROJECT_FAILED", message="Failed to open the working copy."
            )

        return ResponseBuilder.success(
            {
                "source_path": str(source),
                "working_path": str(destination),
                "source_sha256": source_sha256,
                "status": "opened",
            },
            "Working copy created and opened.",
        )

    return await self._audit.execute_with_audit(
        "prepare_edit", {"path_hash": hash_input(path)}, _handler
    )
```

- [ ] **Step 4: MCP 도구를 등록하고 도구 수 계약을 20개로 갱신한다**

`src/psim_mcp/tools/project.py`에 다음 도구를 추가한다.

```python
@mcp.tool(
    description=(
        "원본 .psimsch를 변경하지 않고 새 작업 사본을 만든 뒤 그 사본만 엽니다. "
        "set_parameter 전에 호출하세요. 기존 대상 파일은 덮어쓰지 않습니다."
    ),
)
@tool_handler("prepare_edit")
async def prepare_edit(path: str, save_path: str | None = None) -> str:
    svc = service or _get_service()
    return await svc.prepare_edit(path, save_path=save_path)
```

`tests/unit/test_app_factory.py`의 도구 수와 필수 도구를 갱신한다.

```python
assert len(tools) == 20
assert "prepare_edit" in tools
```

- [ ] **Step 5: 프로젝트 서비스와 앱 도구 계약을 실행한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_project_service.py tests\unit\test_app_factory.py -q
```

Expected: PASS.

- [ ] **Step 6: 안전한 쓰기 경계를 커밋한다**

```powershell
git add src/psim_mcp/services/project_service.py src/psim_mcp/tools/project.py tests/unit/test_project_service.py tests/unit/test_app_factory.py
git commit -m "feat: add safe working-copy edit boundary"
```

## Task 3: C-block 전체 원문을 선택적으로 가져오기

**Files:**
- Modify: `tests/unit/test_import_circuit.py`
- Modify: `src/psim_mcp/services/project_service.py`
- Modify: `src/psim_mcp/tools/project.py`

**Interfaces:**
- Consumes: 기존 `convert_to_python -> parse_converted_script -> reconstruct` 흐름.
- Produces: `import_circuit(path, include_graph=False, include_source_code=False)`.

- [ ] **Step 1: 기본 축약과 선택적 전체 원문 테스트를 작성한다**

`tests/unit/test_import_circuit.py`에 다음 테스트와 어댑터를 추가한다.

```python
class CBlockAdapter(MockPsimAdapter):
    def __init__(self, source: str):
        super().__init__()
        self.source = source

    async def convert_to_python(self, path: str, output_path: str = "") -> dict:
        script = (
            f"strScript = {self.source!r}\n"
            'nCreatedIndex = p1.PsimCreateNewElement(sch, "CBLOCK", "SCB1", '
            'PORTS=[0, 0], _InputCount=1, _OutputCount=1)\n'
            'p1.PsimSetElmValue2(sch, "CBLOCK", "SCB1", "CONTENT", strScript)\n'
        )
        return {
            "success": True,
            "data": {"script_text": script, "script_path": "converted.py"},
        }


async def test_import_circuit_returns_full_cblock_only_when_requested(
    test_config, sample_project_path
):
    source = "void SimulationStep(void) {\n" + ("x++;\n" * 100) + "}"
    service = ProjectService(adapter=CBlockAdapter(source), config=test_config)

    abbreviated = await service.import_circuit(str(sample_project_path))
    short_content = abbreviated["data"]["components"][0]["parameters"]["CONTENT"]
    assert short_content != source
    assert short_content.endswith(f"... ({len(source)} chars)")

    complete = await service.import_circuit(
        str(sample_project_path), include_source_code=True
    )
    assert complete["data"]["components"][0]["parameters"]["CONTENT"] == source
    assert "graph" not in complete["data"]
```

- [ ] **Step 2: 새 인자가 없어 테스트가 실패하는지 확인한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_import_circuit.py::test_import_circuit_returns_full_cblock_only_when_requested -v
```

Expected: `unexpected keyword argument 'include_source_code'`로 FAIL한다.

- [ ] **Step 3: C-block의 `CONTENT`만 축약 예외로 처리한다**

`ProjectService.import_circuit` 서명을 바꾸고 파라미터 컴프리헨션만 확장한다.

```python
async def import_circuit(
    self,
    path: str,
    include_graph: bool = False,
    include_source_code: bool = False,
) -> dict:
```

```python
"parameters": {
    key: (
        value
        if include_source_code
        and c.type in {"CBLOCK", "SIMPLECBLOCK"}
        and key == "CONTENT"
        else _short(value)
    )
    for key, value in c.parameters.items()
},
```

`src/psim_mcp/tools/project.py`의 MCP 서명도 동일하게 확장한다.

```python
async def import_circuit(
    path: str,
    include_graph: bool = False,
    include_source_code: bool = False,
) -> str:
    svc = service or _get_service()
    return await svc.import_circuit(
        path,
        include_graph=include_graph,
        include_source_code=include_source_code,
    )
```

- [ ] **Step 4: 가져오기·파서 회귀 테스트를 실행한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_import_circuit.py tests\unit\test_importer_reconstruction.py -q
```

Expected: PASS.

- [ ] **Step 5: 전체 C-block 읽기를 커밋한다**

```powershell
git add src/psim_mcp/services/project_service.py src/psim_mcp/tools/project.py tests/unit/test_import_circuit.py
git commit -m "feat: return complete c-block source on request"
```

## Task 4: C-block 쓰기 검증을 서비스와 브리지에 배치

**Files:**
- Modify: `tests/unit/test_parameter_service.py`
- Modify: `tests/unit/test_bridge_helpers.py`
- Modify: `src/psim_mcp/services/parameter_service.py`
- Modify: `src/psim_mcp/bridge/bridge_script.py`

**Interfaces:**
- Consumes: `ParameterService.set_parameter`, 브리지의 `_element_cache`, `PsimSetElmValue2`, `PsimFileSave`.
- Produces: 1,024/65,536자 제한, NUL 거부, C-block 타입 제한, 원문을 노출하지 않는 성공 메시지.

- [ ] **Step 1: 서비스 경계 테스트를 작성한다**

`tests/unit/test_parameter_service.py`에 기록용 어댑터와 다음 테스트를 추가한다.

```python
from psim_mcp.adapters.mock_adapter import MockPsimAdapter


class RecordingAdapter(MockPsimAdapter):
    def __init__(self):
        super().__init__()
        self.set_calls = []

    async def set_parameter(self, component_id, parameter_name, value):
        self.set_calls.append((component_id, parameter_name, value))
        return {
            "component_id": component_id,
            "parameter_name": parameter_name,
            "new_value": value,
        }


async def _open_recording_services(test_config, sample_project_path):
    adapter = RecordingAdapter()
    project = ProjectService(adapter=adapter, config=test_config)
    parameter = ParameterService(adapter=adapter, config=test_config, project_service=project)
    await project.open_project(str(sample_project_path))
    return adapter, parameter


async def test_cblock_content_accepts_2910_chars_without_echo(
    test_config, sample_project_path
):
    adapter, service = await _open_recording_services(test_config, sample_project_path)
    source = "x" * 2910
    result = await service.set_parameter("SCB1", "CONTENT", source)
    assert result["success"] is True
    assert adapter.set_calls == [("SCB1", "CONTENT", source)]
    assert source not in result["message"]


async def test_cblock_content_rejects_65537_chars(test_config, sample_project_path):
    adapter, service = await _open_recording_services(test_config, sample_project_path)
    result = await service.set_parameter("SCB1", "CONTENT", "x" * 65537)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_INPUT"
    assert adapter.set_calls == []


async def test_string_parameter_rejects_nul(test_config, sample_project_path):
    adapter, service = await _open_recording_services(test_config, sample_project_path)
    result = await service.set_parameter("SCB1", "CONTENT", "x\x00y")
    assert result["success"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert adapter.set_calls == []


async def test_regular_string_keeps_1024_character_limit(
    test_config, sample_project_path
):
    adapter, service = await _open_recording_services(test_config, sample_project_path)
    result = await service.set_parameter("R1", "Resistance", "x" * 1025)
    assert result["success"] is False
    assert adapter.set_calls == []


async def test_bridge_error_is_not_wrapped_as_success(test_config, sample_project_path):
    class RejectingAdapter(RecordingAdapter):
        async def set_parameter(self, component_id, parameter_name, value):
            return {
                "success": False,
                "error": {
                    "code": "UNSUPPORTED_PARAMETER",
                    "message": "CONTENT is not writable for this component.",
                },
            }

    adapter = RejectingAdapter()
    project = ProjectService(adapter=adapter, config=test_config)
    service = ParameterService(adapter=adapter, config=test_config, project_service=project)
    await project.open_project(str(sample_project_path))

    result = await service.set_parameter("R1", "CONTENT", "return 0;")

    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_PARAMETER"
```

- [ ] **Step 2: 브리지 타입 제한 테스트를 작성한다**

`tests/unit/test_bridge_helpers.py`의 `TestHandleSetParameter`에 다음 테스트를 추가한다.

```python
def test_rejects_content_for_non_cblock(self, monkeypatch):
    monkeypatch.setattr(bridge_script, "_current_sch", object())
    monkeypatch.setattr(bridge_script, "_current_path", "C:/tmp/test.psimsch")
    monkeypatch.setattr(bridge_script, "_element_cache", {"R1": "MULTI_RESISTOR"})

    result = bridge_script.handle_set_parameter({
        "component_id": "R1",
        "parameter_name": "CONTENT",
        "value": "return 0;",
    })

    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_PARAMETER"


def test_allows_content_for_cblock_and_persists(self, monkeypatch):
    sch = object()

    class FakePsim:
        def __init__(self):
            self.set_calls = []
            self.save_calls = []

        def PsimSetElmValue2(self, *args):
            self.set_calls.append(args)
            return 1

        def PsimFileSave(self, *args):
            self.save_calls.append(args)

    fake = FakePsim()
    monkeypatch.setattr(bridge_script, "_get_psim", lambda: fake)
    monkeypatch.setattr(bridge_script, "_current_sch", sch)
    monkeypatch.setattr(bridge_script, "_current_path", "C:/tmp/dq.psimsch")
    monkeypatch.setattr(bridge_script, "_element_cache", {"SCB1": "CBLOCK"})

    result = bridge_script.handle_set_parameter({
        "component_id": "SCB1",
        "parameter_name": "CONTENT",
        "value": "void SimulationStep(void) {}",
    })

    assert result["success"] is True
    assert fake.set_calls == [
        (sch, "CBLOCK", "SCB1", "CONTENT", "void SimulationStep(void) {}")
    ]
    assert fake.save_calls == [(sch, "C:/tmp/dq.psimsch")]
```

- [ ] **Step 3: 새 검증이 없어 테스트가 실패하는지 확인한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_parameter_service.py tests\unit\test_bridge_helpers.py -v
```

Expected: 2,910자 `CONTENT`는 현재 1,024자 제한으로 FAIL하고, 비 C-block `CONTENT`는 현재 허용되어 FAIL하며, 브리지 오류는 현재 성공 envelope 안에 감싸져 FAIL한다.

- [ ] **Step 4: 서비스에서 상태 비의존 검증을 적용한다**

`ParameterService.set_parameter`의 문자열 검증을 다음과 같이 바꾼다.

```python
if isinstance(value, str):
    if "\x00" in value:
        return ResponseBuilder.error(
            code="VALIDATION_ERROR",
            message="Parameter values must not contain NUL characters.",
        )
    max_length = 65_536 if parameter_name.upper() == "CONTENT" else 1_024
    vr = validate_string_length(
        value,
        max_length=max_length,
        field_name="parameter value",
    )
    if not vr.is_valid:
        return ResponseBuilder.error(
            code=vr.error_code or "VALIDATION_ERROR",
            message=vr.error_message or "Invalid parameter value.",
    )
```

어댑터 호출 뒤에는 Real 어댑터의 브리지 envelope만 이 서비스에서 풀어낸다. 다른 어댑터·서비스의 일반 계약 통일은 수행하지 않는다.

```python
data = await self._adapter.set_parameter(component_id, parameter_name, value)
if isinstance(data, dict) and data.get("success") is False:
    return data
if isinstance(data, dict) and data.get("success") is True and "data" in data:
    data = data["data"]
```

성공 메시지는 값을 포함하지 않게 바꾼다.

```python
return ResponseBuilder.success(
    data,
    f"Parameter '{parameter_name}' on '{component_id}' updated.",
)
```

- [ ] **Step 5: 브리지에서 실제 소자 타입을 확인한다**

`handle_set_parameter`가 `_element_cache`에서 타입을 결정한 직후 다음 가드를 추가한다.

```python
if (
    str(parameter_name).upper() == "CONTENT"
    and str(component_type).upper() not in ("CBLOCK", "SIMPLECBLOCK")
):
    return _error(
        "UNSUPPORTED_PARAMETER",
        "CONTENT is writable only for CBLOCK or SIMPLECBLOCK components.",
    )
```

- [ ] **Step 6: 서비스와 브리지 계약을 실행한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_parameter_service.py tests\unit\test_bridge_helpers.py tests\unit\test_bridge_contract.py -q
```

Expected: PASS.

- [ ] **Step 7: C-block 쓰기 경계를 커밋한다**

```powershell
git add src/psim_mcp/services/parameter_service.py src/psim_mcp/bridge/bridge_script.py tests/unit/test_parameter_service.py tests/unit/test_bridge_helpers.py
git commit -m "feat: validate c-block source updates"
```

## Task 5: MCP 응답의 JSON 및 원문 무결성 보장

**Files:**
- Modify: `tests/unit/test_tool_wrapper.py`
- Modify: `src/psim_mcp/tools/__init__.py`
- Modify: `src/psim_mcp/tools/project.py`
- Modify: `src/psim_mcp/utils/sanitize.py`

**Interfaces:**
- Consumes: 서비스가 반환한 Python `dict`.
- Produces: 정확한 데이터 JSON 또는 `RESPONSE_TOO_LARGE` JSON 오류. 잘린 JSON 문자열은 만들지 않는다.

- [ ] **Step 1: 정확한 원문과 유효한 크기 초과 오류 테스트를 작성한다**

`tests/unit/test_tool_wrapper.py`의 기존 truncation 테스트를 다음 세 테스트로 교체한다.

```python
def test_encode_response_preserves_source_verbatim():
    source = "// <system>literal</system>\n// <|token|>\nvoid step(void) {}"
    result = encode_response(
        {
            "success": True,
            "data": {"components": [{"parameters": {"CONTENT": source}}]},
            "message": "ok",
        },
        sanitize=False,
    )
    parsed = json.loads(result)
    assert parsed["data"]["components"][0]["parameters"]["CONTENT"] == source


def test_encode_response_allows_maximum_cblock_source():
    source = "x" * 65_536
    result = encode_response(
        {"success": True, "data": {"CONTENT": source}}, sanitize=False
    )
    assert json.loads(result)["data"]["CONTENT"] == source


def test_encode_response_returns_valid_json_when_too_large():
    result = encode_response({"success": True, "data": "x" * 600_000})
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert parsed["error"]["code"] == "RESPONSE_TOO_LARGE"
```

- [ ] **Step 2: 현재 sanitizer와 문자열 절단 때문에 테스트가 실패하는지 확인한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_tool_wrapper.py -v
```

Expected: 원문 보존 및 크기 초과 JSON 파싱 테스트가 FAIL한다.

- [ ] **Step 3: C-block 가져오기 응답만 원문 보존 모드로 직렬화한다**

`src/psim_mcp/tools/__init__.py`에서 기존 도구의 sanitizer 기본값은 유지하고, 명시한 도구만 원문 보존 모드를 선택할 수 있게 한다.

```python
def encode_response(result: dict, *, sanitize: bool = True) -> str:
    """Serialize a service response, optionally preserving exact data."""
    raw = json.dumps(result, ensure_ascii=False)
    if sanitize:
        raw = sanitize_for_llm_context(raw)
    return truncate_response(raw)


def tool_handler(tool_name: str, *, sanitize: bool = True):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                result = await fn(*args, **kwargs)
                return encode_response(result, sanitize=sanitize)
            except Exception as e:
                logger.exception("Tool error in %s", tool_name)
                return format_tool_error(
                    code="INTERNAL_ERROR",
                    message=f"도구 오류: {type(e).__name__}: {e}",
                )
        return wrapper
    return decorator
```

`src/psim_mcp/tools/project.py`의 `import_circuit` 데코레이터만 원문 보존 모드로 바꾼다.

```python
@tool_handler("import_circuit", sanitize=False)
async def import_circuit(
    path: str,
    include_graph: bool = False,
    include_source_code: bool = False,
) -> str:
    svc = service or _get_service()
    return await svc.import_circuit(
        path,
        include_graph=include_graph,
        include_source_code=include_source_code,
    )
```

`src/psim_mcp/utils/sanitize.py`에서 제한을 최대 C-block과 UTF-8/JSON 여유를 포함한 512,000바이트로 바꾸고 오류도 JSON으로 반환한다.

```python
import json
import re

MAX_RESPONSE_SIZE = 512_000


def truncate_response(response_str: str, max_size: int = MAX_RESPONSE_SIZE) -> str:
    """Return a valid JSON error instead of cutting a serialized document."""
    if len(response_str.encode("utf-8")) <= max_size:
        return response_str
    return json.dumps(
        {
            "success": False,
            "error": {
                "code": "RESPONSE_TOO_LARGE",
                "message": f"Response exceeds the {max_size}-byte limit.",
                "suggestion": "Request less graph data or one source block at a time.",
            },
        },
        ensure_ascii=False,
    )
```

- [ ] **Step 4: 도구 래퍼와 오류 정제 회귀 테스트를 실행한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_tool_wrapper.py tests\unit\test_sanitize.py tests\unit\test_error_sanitization.py -q
```

Expected: PASS.

- [ ] **Step 5: 응답 무결성 수정을 커밋한다**

```powershell
git add src/psim_mcp/tools/__init__.py src/psim_mcp/tools/project.py src/psim_mcp/utils/sanitize.py tests/unit/test_tool_wrapper.py
git commit -m "fix: keep MCP responses valid and source-exact"
```

## Task 6: 실제 DQ 및 Interleaving Boost 수락 테스트 추가

**Files:**
- Modify: `tests/real/conftest.py`
- Modify: `tests/real/test_psim_acceptance.py`
- Modify: `tests/real/README.md`
- Modify: `src/psim_mcp/data/topology_metrics.py`
- Modify: `tests/unit/test_acceptance_criteria.py`

**Interfaces:**
- Consumes: `PSIM_DQ_EXAMPLE_PATH`, `PSIM_INTERLEAVING_EXAMPLE_PATH`, `prepare_edit`, `import_circuit`, `set_parameter`, `run_simulation`, `RealPsimAdapter.compute_metrics`.
- Produces: 두 원본의 불변성과 작업 사본 저장 결과를 검증하는 opt-in 테스트.

- [ ] **Step 1: Boost 인덕터 리플 메트릭의 실패 테스트를 작성한다**

`tests/unit/test_acceptance_criteria.py`에 다음 테스트를 추가한다.

```python
def test_boost_exposes_inductor_current_ripple_metric():
    from psim_mcp.data.topology_metrics import get_topology_metrics

    metrics = get_topology_metrics("boost")["metrics"]
    assert {
        "name": "inductor_current_ripple_pp",
        "signal": "I(L1)",
        "function": "ripple_pp",
    } in metrics
```

- [ ] **Step 2: Boost 메트릭 목록에 한 항목만 추가한다**

`src/psim_mcp/data/topology_metrics.py`의 `boost` 메트릭에 다음 항목을 추가한다.

```python
{"name": "inductor_current_ripple_pp", "signal": "I(L1)", "function": "ripple_pp"},
```

- [ ] **Step 3: 실파일 경로와 전용 서비스 fixture를 추가한다**

`tests/real/conftest.py`에 다음 헬퍼와 fixture를 추가한다.

```python
_EXAMPLE_ENV_VARS = ("PSIM_DQ_EXAMPLE_PATH", "PSIM_INTERLEAVING_EXAMPLE_PATH")


def _example_path(env_name: str) -> Path:
    raw = os.getenv(env_name)
    if not raw:
        pytest.skip(f"Set {env_name} to run this real-PSIM scenario.")
    path = Path(raw).resolve()
    if not path.is_file():
        pytest.fail(f"{env_name} does not point to a file: {path}")
    return path


@pytest.fixture(scope="session")
def dq_example_path() -> Path:
    return _example_path("PSIM_DQ_EXAMPLE_PATH")


@pytest.fixture(scope="session")
def interleaving_example_path() -> Path:
    return _example_path("PSIM_INTERLEAVING_EXAMPLE_PATH")


@pytest.fixture(scope="session")
def project_service(real_app):
    return real_app._services["project"]


@pytest.fixture(scope="session")
def parameter_service(real_app):
    return real_app._services["parameter"]


@pytest.fixture(scope="session")
def real_adapter(real_app):
    return real_app._services["_adapter"]
```

`real_config()`의 허용 디렉터리에 설정된 예제 파일의 부모를 추가한다.

```python
allowed_dirs = {str(project_root), str(scenario_project_dir)}
for env_name in _EXAMPLE_ENV_VARS:
    if os.getenv(env_name):
        allowed_dirs.add(str(Path(os.environ[env_name]).resolve().parent))

# AppConfig 생성 인자
allowed_project_dirs=sorted(allowed_dirs),
```

- [ ] **Step 4: DQ C-block 원문 읽기·작업 사본 저장 테스트를 작성한다**

`tests/real/test_psim_acceptance.py`에 다음 헬퍼와 테스트를 추가한다.

```python
import hashlib


def _sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest().upper()


def _component(data: dict, component_id: str) -> dict:
    return next(item for item in data["components"] if item["id"] == component_id)


async def test_dq_cblock_source_round_trip_preserves_original(
    project_service,
    parameter_service,
    dq_example_path,
    real_test_workspace,
):
    expected_hash = "70FCEAF9416DC025A5212B0E43A9ACA35D02CE9E3A80D6C2A123D26AB05FF924"
    assert _sha256(dq_example_path) == expected_hash

    imported = await project_service.import_circuit(
        str(dq_example_path), include_source_code=True
    )
    assert imported["success"] is True, imported
    assert imported["data"]["stats"]["components"] == 36
    assert imported["data"]["stats"]["nets"] == 25
    source = _component(imported["data"], "SCB1")["parameters"]["CONTENT"]
    assert len(source) == 2910

    working = real_test_workspace["project_dir"] / "DQ_Transform_working.psimsch"
    working.unlink(missing_ok=True)
    prepared = await project_service.prepare_edit(
        str(dq_example_path), save_path=str(working)
    )
    assert prepared["success"] is True, prepared

    edited_source = source + "\n/* psim-mcp acceptance marker */\n"
    changed = await parameter_service.set_parameter("SCB1", "CONTENT", edited_source)
    assert changed["success"] is True, changed

    verified = await project_service.import_circuit(
        str(working), include_source_code=True
    )
    stored = _component(verified["data"], "SCB1")["parameters"]["CONTENT"]
    assert stored == edited_source
    assert _sha256(dq_example_path) == expected_hash
```

- [ ] **Step 5: Interleaving Boost 값 저장과 리플 감소 테스트를 작성한다**

```python
async def test_interleaving_inductor_change_persists_and_reduces_ripple(
    project_service,
    parameter_service,
    simulation_service,
    real_adapter,
    interleaving_example_path,
    real_test_workspace,
):
    expected_hash = "428BF7175CDAC61276FBD423A84B3C357B99EE58411988E605B05AE289FBA603"
    assert _sha256(interleaving_example_path) == expected_hash

    baseline_path = real_test_workspace["project_dir"] / "interleaving_baseline.psimsch"
    modified_path = real_test_workspace["project_dir"] / "interleaving_250u.psimsch"
    baseline_path.unlink(missing_ok=True)
    modified_path.unlink(missing_ok=True)

    baseline_copy = await project_service.prepare_edit(
        str(interleaving_example_path), str(baseline_path)
    )
    assert baseline_copy["success"] is True, baseline_copy
    baseline_run = _unwrap_service_data(
        await simulation_service.run_simulation({"simview": 0}), "baseline simulation"
    )
    baseline_metrics = await real_adapter.compute_metrics(
        metrics_spec=[{
            "name": "inductor_current_ripple_pp",
            "signal": "I(L1)",
            "function": "ripple_pp",
        }],
        graph_file=baseline_run["output_path"],
        skip_ratio=0.5,
    )
    baseline_ripple = _require_numeric_metric(
        baseline_metrics, "inductor_current_ripple_pp"
    )

    modified_copy = await project_service.prepare_edit(
        str(interleaving_example_path), str(modified_path)
    )
    assert modified_copy["success"] is True, modified_copy
    for component_id in ("L1", "L2", "L3"):
        changed = await parameter_service.set_parameter(
            component_id, "inductance", "250u"
        )
        assert changed["success"] is True, changed

    imported = await project_service.import_circuit(str(modified_path))
    assert imported["data"]["stats"]["components"] == 53
    assert imported["data"]["stats"]["nets"] == 38
    for component_id in ("L1", "L2", "L3"):
        assert _component(imported["data"], component_id)["parameters"]["Inductance"] == "250u"

    modified_run = _unwrap_service_data(
        await simulation_service.run_simulation({"simview": 0}), "modified simulation"
    )
    modified_metrics = await real_adapter.compute_metrics(
        metrics_spec=[{
            "name": "inductor_current_ripple_pp",
            "signal": "I(L1)",
            "function": "ripple_pp",
        }],
        graph_file=modified_run["output_path"],
        skip_ratio=0.5,
    )
    modified_ripple = _require_numeric_metric(
        modified_metrics, "inductor_current_ripple_pp"
    )

    assert modified_ripple < baseline_ripple
    assert _sha256(interleaving_example_path) == expected_hash
```

- [ ] **Step 6: Unit 메트릭 테스트를 실행한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_acceptance_criteria.py -q
```

Expected: PASS.

- [ ] **Step 7: 실제 PSIM 환경에서 두 예제 시나리오를 실행한다**

Run:

```powershell
$env:RUN_REAL_PSIM_TESTS="1"
$env:PSIM_MODE="real"
$env:PSIM_DQ_EXAMPLE_PATH="C:\Users\new92\OneDrive\문서\카카오톡 받은 파일\DQ_Transform.psimsch"
$env:PSIM_INTERLEAVING_EXAMPLE_PATH="C:\Users\new92\OneDrive\문서\카카오톡 받은 파일\Interleaving_Boost_Converter.psimsch"
& .\.venv\Scripts\python.exe -m pytest tests\real -m "real_psim and acceptance" -v
```

Expected: 기존 buck 시나리오와 새 DQ/Interleaving 시나리오가 PASS하고 두 원본 해시가 그대로다.

- [ ] **Step 8: 실파일 수락 경로를 커밋한다**

```powershell
git add src/psim_mcp/data/topology_metrics.py tests/unit/test_acceptance_criteria.py tests/real/conftest.py tests/real/test_psim_acceptance.py tests/real/README.md
git commit -m "test: cover existing-circuit edits with real PSIM"
```

## Task 7: Codex·ChatGPT Desktop·Claude Desktop 설정 문서 갱신

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `claude_desktop_config.example.json`

**Interfaces:**
- Consumes: 한 개의 로컬 STDIO 실행 파일과 동일한 PSIM 환경 변수.
- Produces: 세 클라이언트에서 동일한 20개 MCP 도구를 사용하는 설정 예제와 smoke 절차.

- [ ] **Step 1: README의 안전 워크플로와 도구 수를 갱신한다**

기존 “사본에서 작업하세요” 문장을 다음 실행 순서로 교체한다.

```text
1. import_circuit(path, include_source_code=true)로 원본을 읽는다.
2. prepare_edit(path)로 새 작업 사본을 만들고 그 사본만 연다.
3. set_parameter로 소자값 또는 SCB1.CONTENT를 수정한다.
4. import_circuit(working_path)로 실제 저장값을 다시 확인한다.
5. 사용자가 요청한 경우에만 run_simulation을 호출한다.
```

도구 개수 표기 `19개`를 `20개`로 바꾸고 `prepare_edit` 설명을 도구 표에 추가한다.

- [ ] **Step 2: Codex CLI/IDE와 ChatGPT Desktop 공용 TOML 예제를 추가한다**

README에 다음 예제를 추가한다. ChatGPT Desktop에서는 `Settings > Configuration > Open config.toml`, Codex CLI/IDE에서는 `~/.codex/config.toml`을 사용한다.

```toml
[mcp_servers.psim-mcp]
command = "C:\\Users\\new92\\psim-mcp\\.venv\\Scripts\\psim-mcp.exe"
cwd = "C:\\Users\\new92\\psim-mcp"

[mcp_servers.psim-mcp.env]
PSIM_MODE = "real"
PSIM_PATH = "C:\\Altair\\Altair_PSIM_2026"
PSIM_PYTHON_EXE = "C:\\Altair\\Altair_PSIM_2026\\python38\\python.exe"
PSIM_PROJECT_DIR = "C:\\Users\\new92\\psim-mcp\\projects"
PSIM_OUTPUT_DIR = "C:\\Users\\new92\\psim-mcp\\output"
ALLOWED_PROJECT_DIRS = "C:\\Users\\new92\\OneDrive\\문서\\카카오톡 받은 파일,C:\\Users\\new92\\psim-mcp\\projects,C:\\Users\\new92\\psim-mcp\\output"
```

검증 명령과 기대 결과를 함께 기록한다.

```powershell
codex mcp list
& .\.venv\Scripts\python.exe scripts\probe_mcp_init.py
```

Expected: `psim-mcp`가 enabled로 표시되고 probe가 protocol `2025-11-25`, server `psim-mcp`를 반환한다.

- [ ] **Step 3: Claude Desktop 예제에도 동일한 허용 경로를 넣는다**

`claude_desktop_config.example.json`의 real/uv 모드 `env`에 다음 값을 추가한다.

```json
"ALLOWED_PROJECT_DIRS": "C:\\Users\\{사용자}\\Documents\\circuits,C:\\Users\\{사용자}\\psim-projects,C:\\Users\\{사용자}\\psim-output"
```

Claude Desktop 재시작 후 `get_status`, `import_circuit`, `prepare_edit`가 보이는지 확인하는 절차를 README에 추가한다.

- [ ] **Step 4: 환경 변수 예제에 실파일 수락 경로를 기록한다**

`.env.example`에 다음 주석 예제를 추가한다.

```dotenv
# --- 실 PSIM 예제 수락 테스트 ---
# RUN_REAL_PSIM_TESTS=1
# PSIM_DQ_EXAMPLE_PATH=C:\circuits\DQ_Transform.psimsch
# PSIM_INTERLEAVING_EXAMPLE_PATH=C:\circuits\Interleaving_Boost_Converter.psimsch
```

- [ ] **Step 5: JSON과 TOML 예제를 표준 라이브러리로 검증한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -c "import json; json.load(open('claude_desktop_config.example.json', encoding='utf-8')); print('claude json ok')"
& .\.venv\Scripts\python.exe -c "import tomllib; tomllib.loads('''[mcp_servers.psim-mcp]\ncommand = \"psim-mcp\"\n[mcp_servers.psim-mcp.env]\nPSIM_MODE = \"real\"'''); print('codex toml syntax ok')"
```

Expected: `claude json ok`, `codex toml syntax ok`.

- [ ] **Step 6: 현재 PC의 Codex/ChatGPT Desktop 공용 설정에 서버를 등록한다**

현재 확인된 기준선은 `codex mcp list`에 등록 서버가 0개인 상태다. 다음 명령은 저장소 밖의 공용 Codex 설정을 변경하므로 실행 환경이 권한 승인을 요구하면 `psim-mcp` 등록 명령에 한해 승인한다.

Run:

```powershell
codex mcp add psim-mcp -- "C:\Users\new92\psim-mcp\.venv\Scripts\psim-mcp.exe"
codex mcp get psim-mcp --json
codex mcp list
```

Expected: `psim-mcp`가 STDIO 서버로 등록되고 enabled 상태로 표시된다. ChatGPT Desktop을 다시 열어 `Settings > MCP servers`에서도 같은 서버를 확인한다.

- [ ] **Step 7: 클라이언트 문서를 커밋한다**

```powershell
git add README.md .env.example claude_desktop_config.example.json
git commit -m "docs: add safe editing setup for desktop MCP clients"
```

## Task 8: 통합 검증과 기준선 비교

**Files:**
- Verify only: 구현에서 변경한 모든 소스·테스트·문서

**Interfaces:**
- Consumes: Task 1~7의 모든 결과.
- Produces: 새 회귀가 없다는 검증 로그와 실제 MCP 초기화 결과.

- [ ] **Step 1: 변경 파일 정적 검사를 실행한다**

Run:

```powershell
git diff --check
& .\.venv\Scripts\python.exe -m ruff check src\psim_mcp\server.py src\psim_mcp\tools\parameter.py src\psim_mcp\tools\project.py src\psim_mcp\services\project_service.py src\psim_mcp\services\parameter_service.py src\psim_mcp\bridge\bridge_script.py src\psim_mcp\utils\sanitize.py tests\unit\test_app_factory.py tests\unit\test_project_service.py tests\unit\test_import_circuit.py tests\unit\test_parameter_service.py tests\unit\test_bridge_helpers.py tests\unit\test_tool_wrapper.py
```

Expected: 오류 없음.

- [ ] **Step 2: 기존 회로 편집 집중 테스트를 실행한다**

Run:

```powershell
$env:TEMP="C:\Users\new92\psim-mcp\.pytest_tmp"
$env:TMP="C:\Users\new92\psim-mcp\.pytest_tmp"
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_app_factory.py tests\unit\test_project_service.py tests\unit\test_import_circuit.py tests\unit\test_importer_reconstruction.py tests\unit\test_parameter_service.py tests\unit\test_bridge_helpers.py tests\unit\test_bridge_contract.py tests\unit\test_tool_wrapper.py tests\unit\test_acceptance_criteria.py -q
```

Expected: PASS.

- [ ] **Step 3: 전체 기준선에서 새 실패가 없는지 확인한다**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit tests\integration --ignore=tests\integration\test_hybrid_resolver_golden.py -q
```

Expected: 새 실패는 0개이며, 별도 기준선 문제인 아래 두 실패만 동일하게 남는다.

```text
tests/unit/test_elicitation.py::test_service_merges_elicited_fields
tests/unit/test_svg_renderer.py::TestOpenSvgGating::test_opens_when_env_truthy[1]
```

- [ ] **Step 4: MCP STDIO 초기화를 다시 확인한다**

Run:

```powershell
& .\.venv\Scripts\python.exe scripts\probe_mcp_init.py
```

Expected: 10초 안에 초기화되고 protocol `2025-11-25`, server name `psim-mcp`가 출력된다.

- [ ] **Step 5: 실제 PSIM 검증이 활성화된 환경에서는 원본 해시를 마지막으로 재확인한다**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath $env:PSIM_DQ_EXAMPLE_PATH
Get-FileHash -Algorithm SHA256 -LiteralPath $env:PSIM_INTERLEAVING_EXAMPLE_PATH
```

Expected:

```text
DQ: 70FCEAF9416DC025A5212B0E43A9ACA35D02CE9E3A80D6C2A123D26AB05FF924
Interleaving: 428BF7175CDAC61276FBD423A84B3C357B99EE58411988E605B05AE289FBA603
```

- [ ] **Step 6: 작업 트리와 커밋 경계를 검토한다**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected: 사용자 소유의 기존 변경은 그대로이며, 구현 파일은 Task 1~7의 목적별 커밋으로 분리되어 있다.

## 이번 계획에서 제외한 작업

- `RealPsimAdapter`와 `MockPsimAdapter`의 모든 응답 envelope 통일
- `SimulationService` 레거시 파사드와 `app._psim_service` 즉시 삭제
- 사용되지 않는 `ParameterServiceProtocol` 정리
- 임의 회로도 자동 생성 파이프라인 재개
- Claude `.mcpb` 원클릭 패키지와 원격 MCP 배포
- 기존 golden resolver, elicitation, SVG mock 테스트 기준선 수정

이 항목들은 실제 필요가 확인되면 독립 계획과 커밋으로 처리한다.
