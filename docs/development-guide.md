# PSIM-MCP Server: Development Guide

> **버전**: v1.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md) | [architecture.md](./architecture.md)

---

## 1. 개발 환경 구성

### 1.1 필수 사항

| 항목 | Mac (개발) | Windows (통합) |
|------|-----------|----------------|
| Python | 3.12+ | 3.12+ (MCP 서버용) |
| uv | 최신 | 최신 |
| Git | 최신 | 최신 |
| PSIM | 불필요 | Altair PSIM 2024/2025 |
| PSIM Python API | 불필요 | PSIM 설치 시 포함 |
| Claude Desktop | 선택 (테스트용) | 필수 |

### 1.2 Mac 초기 설정

```bash
# 1. 저장소 클론
git clone <repository-url>
cd psim-mcp

# 2. Python 환경 구성 (uv 사용)
uv sync

# 3. 환경 변수 설정
cp .env.example .env
# .env 편집: PSIM_MODE=mock 확인

# 4. 서버 실행 테스트
uv run python -m psim_mcp.server

# 5. 테스트 실행
uv run pytest tests/unit/
```

### 1.3 Windows 초기 설정

```powershell
# 1. 저장소 클론
git clone <repository-url>
cd psim-mcp

# 2. Python 환경 구성
uv sync

# 3. 환경 변수 설정
copy .env.example .env
# .env 편집: 아래 값들을 실제 경로로 변경
# PSIM_MODE=real
# PSIM_PATH=C:\Altair\Altair_PSIM_2025
# PSIM_PYTHON_EXE=C:\Program Files\Altair\2025\common\python\python3.8\win64\python.exe
# PSIM_PROJECT_DIR=C:\work\psim-projects
# PSIM_OUTPUT_DIR=C:\work\psim-output

# 4. PSIM 설치 확인
# - PSIM이 정상 실행되는지 GUI로 확인
# - PSIM Python API가 설치되었는지 확인:
& "C:\Program Files\Altair\2025\common\python\python3.8\win64\python.exe" -c "import psim; print('OK')"

# 5. 서버 실행
uv run python -m psim_mcp.server

# 6. 테스트 실행
uv run pytest tests/unit/          # 공통 테스트
uv run pytest tests/integration/   # 통합 테스트 (PSIM 필요)
```

---

## 2. 개발 단계별 가이드

### Phase 1: 서버 골격 (Mac)

#### Step 1: 프로젝트 구조 생성

```
src/psim_mcp/
├── __init__.py
├── server.py
├── config.py
├── tools/
├── services/
├── adapters/
├── models/
└── utils/
```

#### Step 2: FastMCP 서버 기본 구현

```python
# src/psim_mcp/server.py
from mcp.server.fastmcp import FastMCP
from psim_mcp.config import AppConfig

config = AppConfig()
mcp = FastMCP("psim-mcp")

# tool 등록은 tools/ 모듈에서 import 시 자동 등록
from psim_mcp.tools import project, parameter, simulation, results  # noqa: E402, F401

if __name__ == "__main__":
    mcp.run(transport=config.server_transport)
```

#### Step 3: Adapter 인터페이스 정의

`adapters/base.py`에 `BasePsimAdapter` ABC를 정의한다. ([architecture.md](./architecture.md) 참조)

#### Step 4: MockAdapter 구현

```python
# src/psim_mcp/adapters/mock_adapter.py
class MockPsimAdapter(BasePsimAdapter):
    """Mac 개발용 mock adapter. 더미 데이터를 반환한다."""

    def __init__(self):
        self._current_project = None
        self._parameters = {}

    async def open_project(self, path: str) -> dict:
        self._current_project = {
            "name": Path(path).stem,
            "path": path,
            "components": [
                {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}},
                {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000}},
                {"id": "L1", "type": "Inductor", "parameters": {"inductance": 47e-6}},
                {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}},
            ]
        }
        return self._current_project

    async def run_simulation(self, options=None) -> dict:
        return {
            "status": "completed",
            "duration_seconds": 1.23,
            "result_file": "/tmp/mock_result.smv",
            "summary": {
                "output_voltage_avg": 12.01,
                "output_voltage_ripple": 0.15,
                "efficiency": 95.3,
            }
        }
    # ... 나머지 메서드
```

#### Step 5: Service Layer 구현

`SimulationService`에 입력 검증 및 adapter 호출 로직을 구현한다.

핵심 검증 사항:
- 파일 경로: 존재 여부, 확장자, 읽기/쓰기 권한
- 파라미터: 컴포넌트 존재 여부, 값 타입
- 경로 보안: path traversal 방지 (`ALLOWED_PROJECT_DIRS` 체크)

#### Step 6: Tool 등록

각 tool 파일에서 `@mcp.tool()` 데코레이터로 tool을 등록한다. tool 함수 내에서 service를 호출한다.

#### Step 7: 테스트 작성

```python
# tests/unit/test_simulation_service.py
import pytest
from psim_mcp.services.simulation_service import SimulationService
from psim_mcp.adapters.mock_adapter import MockPsimAdapter

@pytest.fixture
def service():
    adapter = MockPsimAdapter()
    return SimulationService(adapter=adapter, config=test_config)

@pytest.mark.asyncio
async def test_open_project_success(service):
    result = await service.open_project("/fake/path/project.psimsch")
    assert result["success"] is True
    assert "components" in result["data"]

@pytest.mark.asyncio
async def test_open_project_invalid_extension(service):
    result = await service.open_project("/fake/path/project.txt")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_INPUT"
```

---

### Phase 2: Windows 통합

#### Step 1: PSIM 환경 검증

Windows에서 가장 먼저 확인할 사항:

```powershell
# 1. PSIM 실행 확인 (GUI)
# PSIM을 직접 열어서 정상 동작하는지 확인

# 2. PSIM Python API 확인
$PSIM_PYTHON = "C:\Program Files\Altair\2025\common\python\python3.8\win64\python.exe"
& $PSIM_PYTHON -c "import psim; print(dir(psim))"

# 3. 샘플 스크립트 실행
& $PSIM_PYTHON sample_psim_test.py

# 4. 결과 파일 경로 쓰기 권한 확인
New-Item -ItemType File -Path "C:\work\psim-output\test.txt" -Force
```

#### Step 2: Bridge Script 구현

MCP 서버(Python 3.12)와 PSIM API(Python 3.8)를 연결하는 브릿지 스크립트:

> **주의**: 아래 코드는 구현 확정본이 아니라 PSIM API 확인 전 단계의 pseudo-code 예시다.

```python
# src/psim_mcp/bridge/bridge_script.py
# 이 파일은 PSIM 번들 Python 3.8으로 실행된다
import sys
import json

def main():
    raw_input = sys.stdin.read()
    command = json.loads(raw_input)

    action = command["action"]
    params = command.get("params", {})

    try:
        import psim  # PSIM Python API

        if action == "open_project":
            # PSIM API 호출
            result = psim.open(params["path"])
            output = {"success": True, "data": serialize_result(result)}

        elif action == "set_parameter":
            result = psim.set_param(params["component"], params["name"], params["value"])
            output = {"success": True, "data": serialize_result(result)}

        elif action == "run_simulation":
            result = psim.run()
            output = {"success": True, "data": serialize_result(result)}

        elif action == "export_results":
            result = psim.export(params["output_dir"], params.get("format", "json"))
            output = {"success": True, "data": serialize_result(result)}

        else:
            output = {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        output = {"success": False, "error": str(e)}

    print(json.dumps(output))

if __name__ == "__main__":
    main()
```

> **주의**: 위 코드는 PSIM API의 실제 함수명을 가정한 것. Windows에서 `Save as Python Code`로 실제 API 패턴을 확인한 후 함수명, 반환값, 직렬화 방식을 맞춰야 한다.

#### Step 3: RealPsimAdapter 구현

```python
# src/psim_mcp/adapters/real_adapter.py
import subprocess
import json
from psim_mcp.config import AppConfig

class RealPsimAdapter(BasePsimAdapter):
    def __init__(self, config: AppConfig):
        self.psim_python = str(config.psim_python_exe)
        self.bridge_script = str(Path(__file__).parent.parent / "bridge" / "bridge_script.py")
        self.timeout = config.simulation_timeout

    async def _call_bridge(self, action: str, params: dict = None) -> dict:
        command = {"action": action, "params": params or {}}
        result = subprocess.run(
            [self.psim_python, self.bridge_script],
            input=json.dumps(command),
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            raise PsimError(f"Bridge failed: {result.stderr}")
        return json.loads(result.stdout)

    async def open_project(self, path: str) -> dict:
        return await self._call_bridge("open_project", {"path": path})

    async def run_simulation(self, options=None) -> dict:
        return await self._call_bridge("run_simulation", options or {})

    # ... 나머지 메서드
```

#### Step 4: 통합 테스트

```python
# tests/integration/test_real_adapter.py
import pytest
import os

# Windows + PSIM 환경에서만 실행
pytestmark = pytest.mark.skipif(
    os.getenv("PSIM_MODE") != "real",
    reason="PSIM real mode required"
)

@pytest.mark.asyncio
async def test_open_real_project(real_adapter, sample_project_path):
    result = await real_adapter.open_project(sample_project_path)
    assert result["success"] is True
    assert len(result["data"]["components"]) > 0

@pytest.mark.asyncio
async def test_full_workflow(real_adapter, sample_project_path):
    # Open
    await real_adapter.open_project(sample_project_path)
    # Set parameter
    await real_adapter.set_parameter("V1", "voltage", 24.0)
    # Run
    result = await real_adapter.run_simulation()
    assert result["status"] == "completed"
    # Export
    export = await real_adapter.export_results("/tmp/test_output")
    assert len(export["exported_files"]) > 0
```

---

### Phase 3: Claude Desktop 연동

#### Step 1: 로컬 MCP 서버 등록

`claude_desktop_config.json`에 서버 등록:

**Mac (mock 모드 테스트)**:
```json
{
  "mcpServers": {
    "psim": {
      "command": "uv",
      "args": [
        "--directory", "/Users/username/psim-mcp",
        "run", "python", "-m", "psim_mcp.server"
      ],
      "env": {
        "PSIM_MODE": "mock"
      }
    }
  }
}
```

**Windows (real 모드)**:
```json
{
  "mcpServers": {
    "psim": {
      "command": "uv",
      "args": [
        "--directory", "C:\\Users\\username\\psim-mcp",
        "run", "python", "-m", "psim_mcp.server"
      ],
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2025",
        "PSIM_PYTHON_EXE": "C:\\Program Files\\Altair\\2025\\common\\python\\python3.8\\win64\\python.exe",
        "PSIM_PROJECT_DIR": "C:\\work\\psim-projects",
        "PSIM_OUTPUT_DIR": "C:\\work\\psim-output"
      }
    }
  }
}
```

#### Step 2: 검증 체크리스트

- [ ] Claude Desktop 재시작 후 tool 목록에 psim tool들이 표시됨
- [ ] `get_status` 호출 시 정상 응답
- [ ] `open_project` 호출 시 프로젝트 정보 반환
- [ ] `set_parameter` 호출 시 파라미터 변경 확인
- [ ] `run_simulation` 호출 시 시뮬레이션 실행 및 결과 반환
- [ ] `export_results` 호출 시 파일 생성 확인
- [ ] 에러 상황에서 서버가 크래시하지 않음
- [ ] 로그 파일에 호출 기록이 남음

---

## 3. 코딩 컨벤션

### 3.1 Python 스타일

- **포매터/린터**: ruff
- **타입 힌트**: 모든 public 함수에 적용
- **네이밍**: snake_case (함수, 변수), PascalCase (클래스)
- **비동기**: adapter와 service 메서드는 `async`로 구현

### 3.2 프로젝트 규칙

- 환경 의존 값은 반드시 `.env`에서 로드
- 하드코딩된 경로 금지
- 모든 tool 호출에 대해 로그 기록
- 에러 발생 시 서버 크래시 방지 (try-except + 로깅)
- PSIM 관련 코드는 반드시 adapter 내부에만 존재

### 3.3 Git 규칙

- `.env` 파일은 절대 커밋하지 않음
- `.env.example`만 커밋
- 로그 파일, 시뮬레이션 결과 파일 커밋 금지
- 커밋 메시지는 한국어 또는 영어로 통일 (프로젝트 내 일관성 유지)

---

## 4. 테스트 전략

### 4.1 테스트 분류

| 분류 | 위치 | 실행 환경 | 대상 |
|------|------|-----------|------|
| Unit | `tests/unit/` | Mac/Windows | validators, service, mock adapter, schemas |
| Integration | `tests/integration/` | Windows (PSIM) | real adapter, 전체 워크플로우 |

### 4.2 실행 방법

```bash
# 전체 단위 테스트
uv run pytest tests/unit/ -v

# 특정 테스트
uv run pytest tests/unit/test_validators.py -v

# 통합 테스트 (Windows에서만)
PSIM_MODE=real uv run pytest tests/integration/ -v

# 커버리지
uv run pytest tests/unit/ --cov=psim_mcp --cov-report=html
```

### 4.3 테스트 작성 원칙

- 모든 tool에 대해 성공/실패 케이스를 포함
- mock adapter는 다양한 시나리오를 시뮬레이션할 수 있도록 설계
- 통합 테스트는 `PSIM_MODE=real`일 때만 실행
- 경로 관련 테스트는 OS별 차이를 고려

---

## 5. 트러블슈팅

### 5.1 흔한 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| `ModuleNotFoundError: mcp` | 의존성 미설치 | `uv sync` 실행 |
| Tool이 Claude Desktop에 안 보임 | config 경로 오류 또는 재시작 필요 | 경로 확인 후 Claude Desktop 완전 종료 → 재시작 |
| `PSIM_NOT_CONNECTED` | .env의 PSIM 경로 오류 | 경로 존재 여부 및 PSIM 설치 확인 |
| 시뮬레이션 타임아웃 | 시뮬레이션이 오래 걸림 | `SIMULATION_TIMEOUT` 값 증가 |
| Windows 경로 에러 | 백슬래시/공백 문제 | `pathlib.Path` 사용, 공백 경로 따옴표 처리 |
| `PermissionError` | 결과 폴더 쓰기 권한 없음 | 폴더 권한 확인 또는 다른 경로 사용 |
| Bridge script 실행 실패 | PSIM Python 3.8 경로 오류 | `PSIM_PYTHON_EXE` 값 확인 |

### 5.2 디버깅 방법

```bash
# 1. 로그 확인
tail -f logs/server.log
tail -f logs/tools.log
tail -f logs/psim.log

# 2. mock 모드로 서버 단독 테스트
PSIM_MODE=mock uv run python -m psim_mcp.server

# 3. MCP Inspector로 tool 테스트 (MCP CLI 도구)
uv run mcp dev src/psim_mcp/server.py

# 4. 환경 변수 확인
uv run python -c "from psim_mcp.config import AppConfig; print(AppConfig())"
```

---

## 6. 배포 준비

### 6.1 PyPI 패키지 구조

`pyproject.toml`에 다음 설정이 필요:

```toml
[project]
name = "psim-mcp"
version = "0.1.0"
description = "MCP server for Altair PSIM simulation automation"
requires-python = ">=3.12"
dependencies = [
    "mcp>=1.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
]

[project.scripts]
psim-mcp = "psim_mcp.server:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
]
```

### 6.2 배포 체크리스트

- [ ] `pyproject.toml` 메타데이터 완성
- [ ] README.md 작성 (설치, 설정, 사용법)
- [ ] LICENSE 파일 추가
- [ ] `.gitignore` 정리
- [ ] `CHANGELOG.md` 작성
- [ ] PyPI 테스트 업로드 (`uv publish --test`)
- [ ] PyPI 정식 업로드 (`uv publish`)
