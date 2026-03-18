# PSIM-MCP Server: Architecture Document

> **버전**: v1.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md)

---

## 1. 시스템 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│                    사용자 (자연어 입력)                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Claude Desktop                         │
│              (MCP Client, LLM 추론)                      │
└──────────────────────┬──────────────────────────────────┘
                       │ MCP Protocol (stdio / streamable-http)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  PSIM-MCP Server                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              MCP Tool Layer                        │  │
│  │   open_project | set_parameter | run_simulation   │  │
│  │   export_results | get_status | sweep_parameter   │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │                               │
│  ┌───────────────────────▼───────────────────────────┐  │
│  │           Service / Business Logic Layer           │  │
│  │   입력 검증 | 경로 검증 | 결과 요약 | 에러 표준화    │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │                               │
│  ┌───────────────────────▼───────────────────────────┐  │
│  │              Adapter Layer (DI)                    │  │
│  │   ┌──────────────┐    ┌─────────────────────┐     │  │
│  │   │ MockAdapter  │    │   RealPsimAdapter    │     │  │
│  │   │  (Mac 개발)   │    │ (Windows + PSIM)    │     │  │
│  │   └──────────────┘    └──────────┬──────────┘     │  │
│  └──────────────────────────────────┼────────────────┘  │
└─────────────────────────────────────┼────────────────────┘
                                      │ subprocess / API
                                      ▼
                        ┌──────────────────────────┐
                        │    Altair PSIM            │
                        │  (Windows, Python 3.8)    │
                        │  .psimsch → 시뮬레이션     │
                        │  → .smv 결과 파일          │
                        └──────────────────────────┘
```

---

## 2. 레이어 상세

### 2.1 MCP Tool Layer

Claude Desktop이 호출하는 tool을 정의하는 계층. FastMCP의 `@mcp.tool()` 데코레이터로 등록.

**책임**:
- Tool 이름, 설명, 파라미터 스키마 정의
- MCP 프로토콜 규격에 맞는 요청/응답 처리
- Service Layer 호출 위임

**원칙**:
- 이 레이어에 비즈니스 로직을 넣지 않는다
- 모든 tool은 구조화된 JSON 응답을 반환한다
- 에러 시에도 MCP 에러 포맷으로 반환한다

```python
# 예시 구조
@mcp.tool()
async def open_project(path: str, ctx: Context) -> str:
    """PSIM 프로젝트 파일을 열고 정보를 반환합니다."""
    result = await simulation_service.open_project(path)
    return json.dumps(result, ensure_ascii=False)
```

### 2.2 Service / Business Logic Layer

입력 검증, 결과 가공, 에러 표준화를 담당하는 핵심 로직 계층.

**책임**:
- 입력값 유효성 검증 (파일 존재, 타입, 범위)
- 경로 정규화 및 보안 검증 (path traversal 방지)
- Adapter 호출 및 결과 변환
- 에러 메시지 표준화
- 실행 결과 요약 생성

**원칙**:
- PSIM에 직접 의존하지 않는다 (Adapter를 통해서만 접근)
- 순수 Python으로 구현하여 Mac/Windows 모두 동작
- 모든 public 메서드는 단위 테스트 가능

```python
class SimulationService:
    def __init__(self, adapter: BasePsimAdapter, config: AppConfig):
        self.adapter = adapter
        self.config = config

    async def open_project(self, path: str) -> dict:
        validated_path = self._validate_project_path(path)
        result = await self.adapter.open_project(validated_path)
        return self._format_response("open_project", result)
```

### 2.3 Adapter Layer

PSIM 실행 환경을 추상화하는 계층. 의존성 주입(DI)으로 교체 가능.

**BasePsimAdapter (추상 인터페이스)**:
```python
from abc import ABC, abstractmethod
from typing import Any

class BasePsimAdapter(ABC):
    @abstractmethod
    async def open_project(self, path: str) -> dict:
        """프로젝트를 열고 정보를 반환"""
        ...

    @abstractmethod
    async def set_parameter(self, component: str, param: str, value: Any) -> dict:
        """파라미터를 변경하고 결과를 반환"""
        ...

    @abstractmethod
    async def run_simulation(self, options: dict | None = None) -> dict:
        """시뮬레이션을 실행하고 결과를 반환"""
        ...

    @abstractmethod
    async def export_results(self, output_dir: str, format: str = "json") -> dict:
        """결과를 내보내고 파일 경로를 반환"""
        ...

    @abstractmethod
    async def get_status(self) -> dict:
        """현재 상태를 반환"""
        ...

    @abstractmethod
    async def get_project_info(self) -> dict:
        """열린 프로젝트의 상세 정보를 반환"""
        ...
```

**MockPsimAdapter**: Mac/Linux 개발용. 더미 데이터 반환.

**RealPsimAdapter**: Windows 전용. 실제 PSIM Python API 호출.

---

## 3. 디렉터리 구조

```
psim-mcp/
├── src/
│   └── psim_mcp/
│       ├── __init__.py
│       ├── server.py              # FastMCP 서버 진입점
│       ├── config.py              # 환경 변수 및 설정 관리
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── project.py         # open_project, get_project_info
│       │   ├── parameter.py       # set_parameter, sweep_parameter
│       │   ├── simulation.py      # run_simulation
│       │   └── results.py         # export_results, compare_results
│       ├── services/
│       │   ├── __init__.py
│       │   ├── simulation_service.py  # 핵심 비즈니스 로직
│       │   └── validators.py          # 입력 검증 유틸리티
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py            # BasePsimAdapter ABC
│       │   ├── mock_adapter.py    # MockPsimAdapter
│       │   └── real_adapter.py    # RealPsimAdapter (Windows)
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py         # 데이터 모델 (Pydantic)
│       └── utils/
│           ├── __init__.py
│           ├── logging.py         # 로깅 설정
│           └── paths.py           # 경로 유틸리티
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/                      # Mac/공통 테스트
│   │   ├── test_validators.py
│   │   ├── test_simulation_service.py
│   │   ├── test_mock_adapter.py
│   │   └── test_schemas.py
│   └── integration/               # Windows/PSIM 통합 테스트
│       ├── test_real_adapter.py
│       └── test_claude_desktop.py
├── templates/                     # PSIM 회로 템플릿 (선택)
│   └── buck_converter.psimsch
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── api-spec.md
│   └── development-guide.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 4. 설정 관리

### 4.1 환경 변수 (.env)

```env
# ===== 모드 설정 =====
PSIM_MODE=mock                  # mock | real

# ===== PSIM 경로 (Windows real 모드에서만 필요) =====
PSIM_PATH=                      # ex: C:\Altair\Altair_PSIM_2025
PSIM_PYTHON_EXE=                # ex: C:\Program Files\Altair\2025\common\python\python3.8\win64\python.exe
PSIM_PROJECT_DIR=               # ex: C:\work\psim-projects
PSIM_OUTPUT_DIR=                # ex: C:\work\psim-output

# ===== 서버 설정 =====
LOG_DIR=./logs
LOG_LEVEL=INFO                  # DEBUG | INFO | WARNING | ERROR
SERVER_TRANSPORT=stdio          # stdio | streamable-http
SERVER_HOST=127.0.0.1           # streamable-http 전용
SERVER_PORT=8000                # streamable-http 전용

# ===== 시뮬레이션 기본값 =====
SIMULATION_TIMEOUT=300          # 초
MAX_SWEEP_STEPS=100

# ===== 보안 =====
ALLOWED_PROJECT_DIRS=           # 쉼표 구분, 빈 값이면 제한 없음
```

### 4.2 Config 클래스

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class AppConfig(BaseSettings):
    psim_mode: str = "mock"
    psim_path: Path | None = None
    psim_python_exe: Path | None = None
    psim_project_dir: Path | None = None
    psim_output_dir: Path | None = None
    log_dir: Path = Path("./logs")
    log_level: str = "INFO"
    server_transport: str = "stdio"
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    simulation_timeout: int = 300
    max_sweep_steps: int = 100
    allowed_project_dirs: list[str] = []

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

---

## 5. 이중 Python 환경 처리

MCP SDK는 Python 3.10+를 요구하지만, PSIM Python API는 번들 Python 3.8에서 동작한다. 이를 해결하기 위한 아키텍처:

```
┌──────────────────────────────┐
│  MCP Server (Python 3.12)    │
│  ┌────────────────────────┐  │
│  │   RealPsimAdapter      │  │
│  │                        │  │
│  │   subprocess.run(      │  │
│  │     psim_python_exe,   │  │
│  │     "bridge_script.py",│  │
│  │     input=json_args    │  │
│  │   )                    │  │
│  └───────────┬────────────┘  │
└──────────────┼───────────────┘
               │ subprocess (stdin/stdout JSON)
               ▼
┌──────────────────────────────┐
│  PSIM Bridge (Python 3.8)    │
│  ┌────────────────────────┐  │
│  │  bridge_script.py      │  │
│  │  - JSON 입력 파싱       │  │
│  │  - PSIM API 호출        │  │
│  │  - JSON 결과 출력       │  │
│  └────────────────────────┘  │
└──────────────────────────────┘
```

**bridge_script.py** 는 PSIM 번들 Python으로 실행되며:
1. stdin에서 JSON 명령을 읽음
2. PSIM Python API를 호출
3. 결과를 JSON으로 stdout에 출력

이 방식으로 두 Python 환경을 완전히 격리한다.

---

## 6. 로깅 아키텍처

### 6.1 로그 구조

```
logs/
├── server.log          # MCP 서버 전체 로그
├── tools.log           # tool 호출 기록 (구조화)
└── psim.log            # PSIM adapter 실행 로그
```

### 6.2 Tool 호출 로그 형식

```json
{
  "timestamp": "2026-03-15T14:30:00.123Z",
  "tool": "run_simulation",
  "request_id": "abc-123",
  "input": {
    "options": {"time_step": 0.001}
  },
  "duration_ms": 4520,
  "status": "success",
  "output_summary": "시뮬레이션 완료, 결과 파일: output/result_001.json",
  "error": null
}
```

### 6.3 로깅 원칙
- 모든 tool 호출의 입력/출력/소요시간을 기록
- 에러 시 스택 트레이스 포함
- PSIM subprocess의 stdout/stderr를 별도 파일로 캡처
- 로그 레벨은 환경 변수로 제어
- 민감 정보(경로 제외)는 로그에서 마스킹

---

## 7. 에러 처리 전략

### 7.1 에러 분류

| 카테고리 | 예시 | 처리 방식 |
|----------|------|-----------|
| **입력 에러** | 잘못된 경로, 없는 파라미터 | 즉시 반환, 유효한 입력 안내 |
| **PSIM 에러** | 시뮬레이션 실패, 라이선스 만료 | PSIM 에러 메시지 전달 + 로그 |
| **시스템 에러** | 디스크 부족, 권한 없음 | 시스템 상태 안내 + 로그 |
| **타임아웃** | 시뮬레이션 시간 초과 | 중단 안내 + 타임아웃 값 조정 제안 |

### 7.2 에러 응답 형식

```json
{
  "success": false,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "프로젝트 파일을 찾을 수 없습니다: /path/to/project.psimsch",
    "suggestion": "파일 경로를 확인하고 다시 시도해주세요. get_status로 현재 프로젝트 디렉터리를 확인할 수 있습니다."
  }
}
```

---

## 8. 배포 구성

### 8.1 로컬 배포 (1차 목표)

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "psim": {
      "command": "uv",
      "args": [
        "--directory", "C:\\path\\to\\psim-mcp",
        "run", "python", "-m", "psim_mcp.server"
      ],
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2025"
      }
    }
  }
}
```

### 8.2 PyPI 배포 (2차 목표)

```json
{
  "mcpServers": {
    "psim": {
      "command": "uvx",
      "args": ["psim-mcp"],
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2025"
      }
    }
  }
}
```

### 8.3 원격 배포 (3차 목표)

- streamable-http 전송 방식 사용
- Windows 서버에 MCP 서버 + PSIM 설치
- 인증 레이어 추가 필요
- 현 단계에서는 설계만 고려, 구현은 후순위

---

## 9. 의존성

### 9.1 런타임 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `mcp` | >=1.0 | MCP 서버 프레임워크 |
| `pydantic` | >=2.0 | 데이터 검증 및 스키마 |
| `pydantic-settings` | >=2.0 | 환경 변수 기반 설정 |
| `python-dotenv` | >=1.0 | .env 파일 로드 |

### 9.2 개발 의존성

| 패키지 | 용도 |
|--------|------|
| `pytest` | 테스트 프레임워크 |
| `pytest-asyncio` | 비동기 테스트 |
| `ruff` | 린터/포매터 |

### 9.3 PSIM 의존성 (Windows real 모드)

| 항목 | 비고 |
|------|------|
| Altair PSIM 2024/2025 | Windows에 설치 필요 |
| PSIM Python API | PSIM과 함께 설치됨 |
| PSIM 번들 Python 3.8 | PSIM 설치 경로에 포함 |
