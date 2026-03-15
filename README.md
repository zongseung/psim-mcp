# PSIM-MCP Server

> Claude Desktop에서 자연어로 전력전자 회로를 설계하고 Altair PSIM 시뮬레이션을 제어하는 MCP 서버

**15개 Tool** | **288개 테스트** | **51개 소스 파일** | **29개 회로 템플릿** | **40+ 부품 라이브러리**

---

## 주요 기능

- **자연어 회로 설계**: "절연형 5V 보조전원 설계해줘" → flyback 토폴로지 추천 + 사양 질문
- **LLM-as-Designer**: Claude가 직접 회로를 설계하고 `preview_circuit`에 전달
- **대화형 설계 루프**: `design_circuit` → 질문 → `continue_design` → 미리보기 → `confirm_circuit`
- **SVG + ASCII 미리보기**: 브라우저 자동 열기로 회로 구조 즉시 확인
- **29개 회로 템플릿**: DC-DC, 인버터, 정류기, PFC, 태양광, 모터, 배터리, 필터 (9 카테고리)
- **3개 자동 계산 Generator**: Buck, Boost, Buck-Boost — 설계 공식 기반 파라미터 자동 산출
- **40+ 부품 라이브러리**: 핀 정의, 기본값, 카테고리별 분류
- **Constraint 기반 토폴로지 추천**: keyword 없이도 "고전압→저전압" 의미 해석
- **CircuitSpec 중심 파이프라인**: 설계 → 검증 → 미리보기 → 생성 전 과정 통합
- **4단계 검증**: structural, electrical, parameter, connection 검증
- **Mac mock 모드 + Windows real 모드**: PSIM 없이 개발/테스트 가능

---

## 빠른 시작 (Mac mock 모드)

```bash
# 1. 클론 및 설치
git clone <repository-url>
cd psim-mcp
uv sync --all-extras

# 2. 환경 설정
cp .env.example .env
# PSIM_MODE=mock (기본값)

# 3. 서버 실행
uv run python -m psim_mcp.server

# 4. 테스트
uv run pytest tests/unit/ -v
```

---

## Claude Desktop 연동

### 설정

`~/Library/Application Support/Claude/claude_desktop_config.json` 편집:

```json
{
  "mcpServers": {
    "psim": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "--directory", "/Users/yourname/psim-mcp",
        "run", "python", "-m", "psim_mcp.server"
      ],
      "env": {
        "PSIM_MODE": "mock"
      }
    }
  }
}
```

> `uv` 경로는 `which uv`로 확인. `--directory`는 실제 프로젝트 경로로 변경.

Claude Desktop을 **Cmd+Q로 완전 종료** 후 재실행하면 15개 tool이 표시됩니다.

### 트러블슈팅

| 증상 | 해결 |
|------|------|
| Tool이 안 보임 | Cmd+Q로 완전 종료 후 재시작 (Dock 닫기만으로는 반영 안 됨) |
| 서버 시작 실패 | `which uv`로 경로 확인, `--directory` 경로 확인 |
| 에러 로그 확인 | `tail -f ~/Library/Logs/Claude/mcp-server-psim.log` |
| `ModuleNotFoundError` | `uv sync --all-extras` 실행 |

---

## 사용 예시

### 시뮬레이션

```
"Buck 컨버터 프로젝트를 열고, 스위칭 주파수를 100kHz로 변경한 다음 시뮬레이션 돌려서 결과 보여줘"
→ open_project → set_parameter → run_simulation → export_results

"인덕턴스를 10uH에서 100uH까지 10단계로 스윕하고 출력 리플 비교해줘"
→ open_project → sweep_parameter → compare_results
```

### 회로 설계 (자연어)

```
"절연형 5V 보조전원 설계해줘"
→ design_circuit: flyback 추천, "입력 전압 범위?" 질문
→ continue_design: "AC 85-265V" 응답
→ preview_circuit: SVG 미리보기 → 브라우저 열림
→ confirm_circuit: .psimsch 파일 생성

"3상 인버터 회로 만들어줘"
→ list_circuit_templates → create_circuit 또는 preview_circuit → confirm_circuit

"BLDC 모터 드라이브 템플릿 보여줘"
→ list_circuit_templates (motor 카테고리) → preview_circuit
```

### 설계 흐름

```
[자연어 요청] → design_circuit (토폴로지 추천 + 질문)
                    ↓
              continue_design (사양 보완, 반복 가능)
                    ↓
              preview_circuit (SVG + ASCII 미리보기)
                    ↓
              confirm_circuit (.psimsch 생성)
```

---

## Tools Reference

### 프로젝트 / 시뮬레이션 (8개)

| # | Tool | 설명 |
|---|------|------|
| 1 | `open_project` | PSIM 프로젝트 파일(.psimsch) 열기 |
| 2 | `get_project_info` | 열린 프로젝트의 상세 구조 반환 |
| 3 | `set_parameter` | 컴포넌트 파라미터 변경 |
| 4 | `sweep_parameter` | 파라미터 범위 스윕 + 반복 시뮬레이션 |
| 5 | `run_simulation` | 시뮬레이션 실행 |
| 6 | `export_results` | 결과를 JSON/CSV로 내보내기 |
| 7 | `compare_results` | 두 시뮬레이션 결과 비교 |
| 8 | `get_status` | 서버/PSIM 상태 조회 |

### 회로 설계 (7개)

| # | Tool | 설명 |
|---|------|------|
| 9 | `get_component_library` | 부품 라이브러리 조회 (부품/핀 확인) |
| 10 | `preview_circuit` | 회로 SVG + ASCII 미리보기 (브라우저 자동 열기) |
| 11 | `confirm_circuit` | 미리보기 확정 → .psimsch 파일 생성 |
| 12 | `create_circuit` | 미리보기 없이 직접 .psimsch 생성 |
| 13 | `list_circuit_templates` | 29개 템플릿 목록 (9 카테고리) |
| 14 | `design_circuit` | 자연어 회로 설계 (constraint 기반 토폴로지 추천) |
| 15 | `continue_design` | 대화형 보완 루프 (세션 토큰 기반) |

---

## 회로 템플릿 (29개, 9 카테고리)

| 카테고리 | 템플릿 |
|----------|--------|
| **DC-DC (비절연)** | buck, boost, buck_boost, cuk, sepic, bidirectional_buck_boost |
| **DC-DC (절연)** | flyback, forward, push_pull, llc, dab, phase_shifted_full_bridge |
| **인버터** | half_bridge, full_bridge, three_phase_inverter, three_level_npc |
| **정류기** | diode_bridge_rectifier, thyristor_rectifier |
| **PFC** | boost_pfc, totem_pole_pfc |
| **태양광** | pv_mppt_boost, pv_grid_tied |
| **모터 드라이브** | bldc_drive, pmsm_foc_drive, induction_motor_vf |
| **배터리** | cc_cv_charger, ev_obc |
| **필터** | lc_filter, lcl_filter |

---

## 아키텍처

```
사용자 (자연어)
    ↓
Claude Desktop (MCP Client + LLM 추론)
    ↓  MCP Protocol (stdio)
PSIM-MCP Server
    ↓
┌─────────────────────────────────────────────┐
│  Tool Layer (@tool_handler 데코레이터)       │
│  - 15개 tool 정의                           │
│  - 예외 처리, 직렬화, sanitize 자동화        │
├─────────────────────────────────────────────┤
│  Service Layer                              │
│  - 입력 검증 + 경로 보안                     │
│  - ResponseBuilder 표준 응답                 │
│  - _execute_with_audit 감사 로깅             │
├─────────────────────────────────────────────┤
│  Circuit Pipeline                           │
│  - Parsers: intent_parser, unit_parser      │
│  - Generators: buck, boost, buck_boost      │
│  - Validators: structural, electrical,      │
│    parameter, connection                    │
│  - Data: templates, components, topology    │
├─────────────────────────────────────────────┤
│  Adapter Layer (DI)                         │
│  - MockAdapter (Mac 개발)                    │
│  - RealAdapter (Windows PSIM)               │
│       ↓ subprocess + JSON IPC               │
│    Bridge Script (Python 3.8)               │
│       ↓ PSIM Python API                     │
│    Altair PSIM (.psimsch → .smv)            │
└─────────────────────────────────────────────┘
```

### 이중 Python 환경

PSIM Python API는 번들 Python 3.8에서만 동작하고, MCP SDK는 Python 3.12+를 요구합니다. `RealAdapter`가 subprocess로 `bridge_script.py`를 호출하여 JSON IPC로 통신합니다.

```
MCP Server (Python 3.12+)  ──stdin/stdout JSON──>  bridge_script.py (Python 3.8)  ──>  PSIM API
```

---

## 프로젝트 구조

```
psim-mcp/
├── src/psim_mcp/
│   ├── server.py                 # App factory (create_app, create_service, create_adapter)
│   ├── config.py                 # 환경 변수 기반 설정 (Pydantic)
│   ├── tools/                    # MCP Tool 정의 (15개)
│   │   ├── project.py            #   open_project, get_project_info
│   │   ├── parameter.py          #   set_parameter, sweep_parameter
│   │   ├── simulation.py         #   run_simulation
│   │   ├── results.py            #   export_results, compare_results, get_status
│   │   ├── circuit.py            #   get_component_library, preview/confirm/create_circuit, list_templates
│   │   └── design.py             #   design_circuit, continue_design
│   ├── services/                 # 비즈니스 로직
│   │   ├── simulation_service.py #   오케스트레이션 + 감사 로깅
│   │   ├── preview_store.py      #   Preview token 관리
│   │   ├── response.py           #   ResponseBuilder
│   │   └── validators.py         #   입력 검증
│   ├── adapters/                 # PSIM 실행 환경 추상화
│   │   ├── base.py               #   BasePsimAdapter (ABC)
│   │   ├── mock_adapter.py       #   Mac 개발용 mock
│   │   └── real_adapter.py       #   Windows PSIM 연동
│   ├── bridge/                   # PSIM Python 3.8 브릿지
│   │   ├── bridge_script.py      #   JSON IPC
│   │   └── wiring.py             #   배선 유틸리티
│   ├── models/                   # 데이터 모델
│   │   ├── schemas.py            #   Pydantic 모델 (시뮬레이션)
│   │   └── circuit_spec.py       #   CircuitSpec (회로 설계)
│   ├── data/                     # 정적 데이터
│   │   ├── circuit_templates.py  #   29개 회로 템플릿
│   │   ├── component_library.py  #   40+ 부품 정의 (핀, 파라미터)
│   │   ├── topology_metadata.py  #   토폴로지 메타데이터 + constraint
│   │   └── spec_mapping.py       #   스펙 매핑
│   ├── generators/               # 회로 자동 생성
│   │   ├── base.py               #   BaseGenerator
│   │   ├── buck.py               #   Buck 설계 공식
│   │   ├── boost.py              #   Boost 설계 공식
│   │   ├── buck_boost.py         #   Buck-Boost 설계 공식
│   │   └── layout.py             #   레이아웃 배치
│   ├── parsers/                  # 입력 해석
│   │   ├── intent_parser.py      #   자연어 의도 분석
│   │   ├── keyword_map.py        #   키워드 매핑
│   │   └── unit_parser.py        #   단위 파싱 (10uH → 10e-6)
│   ├── validators/               # 회로 검증
│   │   ├── structural.py         #   구조 검증
│   │   ├── electrical.py         #   전기적 검증
│   │   ├── parameter.py          #   파라미터 범위 검증
│   │   └── models.py             #   검증 모델
│   └── utils/                    # 유틸리티
│       ├── logging.py            #   구조화 로깅 + SecurityAuditLogger
│       ├── paths.py              #   경로 보안
│       ├── sanitize.py           #   출력 sanitization
│       ├── ascii_renderer.py     #   ASCII 회로 렌더러
│       └── svg_renderer.py       #   SVG 회로 렌더러
├── tests/
│   ├── unit/                     # 288개 단위 테스트
│   └── integration/              # Windows + PSIM 통합 테스트
├── docs/
├── main.py                       # psim_mcp.server.main() 위임
├── pyproject.toml
└── .env.example
```

**10개 패키지**: adapters, bridge, data, generators, models, parsers, services, tools, utils, validators

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `PSIM_MODE` | `mock` | 동작 모드 (`mock` / `real`) |
| `PSIM_PATH` | — | PSIM 설치 경로 (real 모드 필수) |
| `PSIM_PYTHON_EXE` | — | PSIM 번들 Python 3.8 경로 |
| `PSIM_PROJECT_DIR` | — | PSIM 프로젝트 디렉터리 |
| `PSIM_OUTPUT_DIR` | — | 결과 출력 디렉터리 |
| `LOG_DIR` | `./logs` | 로그 저장 디렉터리 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `SIMULATION_TIMEOUT` | `300` | 시뮬레이션 타임아웃 (초) |
| `MAX_SWEEP_STEPS` | `100` | 스윕 최대 단계 수 |
| `PREVIEW_TTL` | `3600` | 미리보기 토큰 유효시간 (초) |
| `ALLOWED_PROJECT_DIRS` | — | 허용 디렉터리 (쉼표 구분) |

### Windows (real 모드) 설정 예시

```env
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2025
PSIM_PYTHON_EXE=C:\Program Files\Altair\2025\common\python\python3.8\win64\python.exe
PSIM_PROJECT_DIR=C:\work\psim-projects
PSIM_OUTPUT_DIR=C:\work\psim-output
```

---

## 개발

### App Factory 패턴

```python
from psim_mcp.server import create_app, create_service
from psim_mcp.config import AppConfig

# 독립 인스턴스로 테스트 — 전역 상태 없음
config = AppConfig(psim_mode="mock")
service = create_service(config)

result = await service.get_status()
assert result["success"] is True
```

### 새 Tool 추가

```python
# src/psim_mcp/tools/my_tool.py
from psim_mcp.tools import tool_handler

def register_tools(mcp, service=None):
    @mcp.tool(description="새 도구 설명")
    @tool_handler("my_new_tool")
    async def my_new_tool(param: str) -> str:
        svc = service or _get_service()
        return await svc.some_method(param)
        # 예외 처리, JSON 직렬화, sanitize, truncate는 데코레이터가 처리
```

### MCP Inspector (Claude Desktop 없이 테스트)

```bash
uv run mcp dev src/psim_mcp/server.py
```

---

## 테스트

```bash
# 전체 단위 테스트 (288개)
uv run pytest tests/unit/ -v

# 통합 테스트 (Windows + PSIM)
PSIM_MODE=real uv run pytest tests/integration/ -v

# 커버리지 리포트
uv run pytest tests/unit/ --cov=psim_mcp --cov-report=html
```

### 테스트 구성

| 카테고리 | 대상 |
|----------|------|
| validators | 입력 검증 함수 |
| schemas | Pydantic 모델 |
| path_security | 경로 보안 |
| mock_adapter | MockAdapter |
| simulation_service | Service Layer |
| error_responses | 에러 응답 일관성 |
| sanitize | 출력 sanitization |
| security_validation | 보안 검증 |
| security_audit | 감사 로깅 |
| error_sanitization | 에러 정보 누출 방지 |
| app_factory | 앱 팩토리 |
| tool_wrapper | tool_handler 데코레이터 |
| response_builder | ResponseBuilder |
| tool_integration | Tool E2E 워크플로우 |
| startup_validation | 설정 검증 |
| circuit_spec | CircuitSpec 모델 |
| circuit_validators | 회로 검증 (structural, electrical) |
| generators | 자동 계산 Generator |
| preview_store | Preview token 관리 |
| unit_parser | 단위 파싱 |
| parser_regression | 파서 회귀 테스트 |

---

## 보안

- **경로 보안**: `Path.resolve()` + `is_relative_to()`로 path traversal 방지
- **입력 검증**: Pydantic Field 제약 + 정규식 + 시뮬레이션 옵션 범위 검증
- **출력 보안**: LLM 컨텍스트 sanitization, 50KB 응답 크기 제한, 에러 메시지 보호
- **subprocess 보안**: `shell=False`, JSON stdin 전달, 환경 격리 (`_get_sanitized_env`)
- **감사 로깅**: SecurityAuditLogger, 입력 SHA-256 해싱, 4개 로그 파일 분리

---

## 기술 스택

| 항목 | 기술 |
|------|------|
| 언어 | Python 3.12+ |
| MCP | FastMCP (`mcp>=1.26`) |
| 데이터 검증 | Pydantic v2 |
| 설정 관리 | pydantic-settings + python-dotenv |
| 테스트 | pytest + pytest-asyncio (288개) |
| 린터 | ruff |
| 패키지 관리 | uv |
| 빌드 | hatchling |

---

## 라이선스

TBD
