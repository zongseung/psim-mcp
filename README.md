# psim-mcp

Claude Desktop에서 자연어로 전력전자 회로를 설계하고 Altair PSIM으로 시뮬레이션하는 MCP 서버.

**15개 Tool** | **821개 테스트** | **130개 소스 파일** | **29개 topology** | **40+ 부품 라이브러리**

```
"buck converter 48V to 12V 5A"
  → Intent 추출 → Topology 선택 → CircuitGraph → Auto Layout → Routing → SVG Preview → .psimsch
```

---

## 주요 기능

- **자연어 회로 설계** — 한국어/영어로 회로를 설명하면 topology 자동 선택, 파라미터 계산, 회로도 생성
- **29개 전력전자 topology** — Buck, Boost, Flyback, LLC, Full-Bridge, 3-Phase Inverter, BLDC Drive 등
- **알고리즘 기반 자동 배치** — 좌표 하드코딩 없이 CircuitGraph에서 schematic layout 자동 생성
- **SVG + ASCII 미리보기** — 생성 전 회로도 확인, 수정, 확정 (브라우저 자동 열기)
- **PSIM 연동** — 확정된 회로를 `.psimsch` 파일로 생성, 시뮬레이션 실행, 결과 분석
- **대화형 설계 루프** — `design_circuit` → 질문 → `continue_design` → 미리보기 → `confirm_circuit`
- **Mock 모드** — PSIM 없이 개발/테스트 가능 (macOS, Linux 포함)

---

## 설치

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync --all-extras
```

### 요구 사항

| 항목 | 필수 | 비고 |
|------|------|------|
| Python 3.12+ | 필수 | MCP 서버 런타임 |
| [uv](https://docs.astral.sh/uv/) | 필수 | 패키지 관리 |
| Claude Desktop | 필수 | MCP 클라이언트 |
| Altair PSIM 2026 | 선택 | 실제 회로 생성/시뮬레이션 시 필요 |

---

## Claude Desktop 설정

`claude_desktop_config.json` 편집:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

### PSIM 있을 때 (Real 모드)

```json
{
  "mcpServers": {
    "psim-mcp": {
      "command": "C:\\Users\\{사용자}\\psim-mcp\\.venv\\Scripts\\psim-mcp.exe",
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2026",
        "PSIM_PYTHON_EXE": "C:\\Users\\{사용자}\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
        "PSIM_PROJECT_DIR": "C:\\Users\\{사용자}\\psim-projects",
        "PSIM_OUTPUT_DIR": "C:\\Users\\{사용자}\\psim-output"
      }
    }
  }
}
```

### PSIM 없을 때 (Mock 모드)

```json
{
  "mcpServers": {
    "psim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/psim-mcp", "psim-mcp"],
      "env": {
        "PSIM_MODE": "mock"
      }
    }
  }
}
```

Claude Desktop을 **완전 종료** 후 재실행하면 15개 tool이 표시됩니다.

---

## 사용법

Claude Desktop에서 자연어로 요청:

```
buck converter 48V 입력 12V 출력 5A

flyback 310V 입력 5V 출력 2A 어댑터

LLC 공진 컨버터 400V에서 24V 1kW

충전기 48V 배터리 10A

양방향 DC-DC 48V to 400V

절연형 보조전원 설계해줘

3상 인버터 회로 만들어줘
```

### 설계 흐름

```
1. design_circuit("buck 48V to 12V 5A")
   → topology 선택, 파라미터 계산, SVG 미리보기 자동 생성
   → preview_token 반환

2. confirm_circuit(preview_token, save_path="./buck.psimsch")
   → PSIM .psimsch 파일 생성

3. run_simulation(project_path="./buck.psimsch")
   → 시뮬레이션 실행, 파형 데이터 반환
```

---

## MCP 도구 (15개)

### 회로 설계

| 도구 | 설명 |
|------|------|
| `design_circuit` | 자연어 → 회로 설계 (topology 선택 + auto preview) |
| `continue_design` | 추가 정보 입력하여 설계 계속 (세션 토큰 기반) |
| `preview_circuit` | 회로 미리보기 (SVG + ASCII) |
| `confirm_circuit` | 미리보기 확정 → .psimsch 생성 |
| `create_circuit` | 미리보기 없이 직접 생성 |
| `get_component_library` | 부품 라이브러리 조회 (40+ 부품) |
| `list_circuit_templates` | 회로 템플릿 목록 (29개, 9 카테고리) |

### 시뮬레이션

| 도구 | 설명 |
|------|------|
| `open_project` | 기존 .psimsch 파일 열기 |
| `get_project_info` | 프로젝트 구조 조회 |
| `set_parameter` | 컴포넌트 파라미터 변경 |
| `sweep_parameter` | 파라미터 스윕 시뮬레이션 |
| `run_simulation` | 시뮬레이션 실행 |
| `export_results` | 결과 내보내기 (JSON/CSV) |
| `compare_results` | 시뮬레이션 결과 비교 |
| `get_status` | 서버/PSIM 상태 확인 |

---

## 지원 topology (29개)

| 카테고리 | topology |
|----------|----------|
| DC-DC 비절연 | buck, boost, buck_boost, cuk, sepic |
| DC-DC 절연 | flyback, forward, push_pull, llc, dab, phase_shifted_full_bridge |
| DC-AC 인버터 | half_bridge, full_bridge, three_phase_inverter, three_level_npc |
| AC-DC 정류 | diode_bridge_rectifier, thyristor_rectifier |
| PFC | boost_pfc, totem_pole_pfc |
| 재생 에너지 | pv_mppt_boost, pv_grid_tied |
| 모터 드라이브 | bldc_drive, pmsm_foc_drive, induction_motor_vf |
| 배터리 | cc_cv_charger, ev_obc, bidirectional_buck_boost |
| 필터 | lc_filter, lcl_filter |

---

## 아키텍처

### Canonical Synthesis Pipeline

```
자연어
  → extract_intent()         # 도메인 제약/값 추출 (intent/)
  → rank_topologies()        # topology 후보 점수화
  → build_canonical_spec()   # canonical spec 생성
  → generator.synthesize()   # CircuitGraph 합성 (synthesis/)
  → validate_graph()         # 구조 검증 (validators/)
  → generate_layout()        # SchematicLayout 자동 배치 (layout/)
  → generate_routing()       # WireRouting trunk/branch (routing/)
  → materialize_to_legacy()  # legacy 포맷 변환
  → SVG renderer / PSIM bridge
```

Legacy 경로 (generator/template)는 fallback으로 유지됩니다. Canonical pipeline이 실패하면 자동으로 legacy 경로를 사용합니다.

### Dual Python 환경

```
Claude Desktop ─stdio─→ MCP Server (Python 3.12+)
                              │
                       CircuitDesignService
                              │
                       RealPsimAdapter
                              │ stdin/stdout JSON lines
                       bridge_script.py (Python 3.8/3.9)
                              │
                       psimapipy → PSIM engine
```

PSIM API(`psimapipy`)는 별도 Python 프로세스에서 실행됩니다. 두 프로세스 사이는 JSON IPC로 통신합니다.

### 프로젝트 구조

```
src/psim_mcp/
├── intent/              # 자연어 → IntentModel → CanonicalSpec
│   ├── extractors.py    #   도메인 제약 추출
│   ├── ranker.py        #   topology 후보 점수화
│   ├── clarification.py #   추가 정보 필요 여부 판단
│   └── spec_builder.py  #   canonical spec 조립
│
├── synthesis/           # CircuitGraph 합성
│   ├── graph.py         #   CircuitGraph, GraphComponent, GraphNet, FunctionalBlock
│   ├── graph_builders.py#   make_component(), make_net(), make_block()
│   ├── sizing.py        #   topology별 파라미터 계산 (duty, L, C, ...)
│   └── topologies/      #   buck, flyback, llc graph synthesizer
│
├── layout/              # 알고리즘 기반 자동 배치
│   ├── auto_placer.py   #   block 할당 → role 배치 → force-directed → grid snap
│   ├── force_directed.py#   스프링 기반 위치 미세 조정
│   ├── constraint_solver.py # 범용 constraint dispatcher (7개 kind)
│   ├── engine.py        #   generate_layout() 디스패처
│   └── materialize.py   #   SchematicLayout → legacy 포맷 변환
│
├── routing/             # trunk/branch 라우팅
│   ├── engine.py        #   generate_routing() 디스패처
│   ├── trunk_branch.py  #   net role 기반 trunk/branch 알고리즘
│   ├── anchors.py       #   핀 좌표 해석
│   ├── metrics.py       #   crossing/duplicate/wire_length 측정
│   └── strategies/      #   topology별 라우팅 전략
│
├── generators/          # 29개 topology generator (generate + synthesize)
├── validators/          # 구조/전기/파라미터/graph 검증
├── services/            # CircuitDesignService, SimulationService
├── adapters/            # Mock/Real PSIM 어댑터
├── bridge/              # PSIM Python 3.8 IPC bridge
├── data/                # 메타데이터 레지스트리 (8개)
│   ├── topology_metadata.py        # topology 속성 (29개)
│   ├── component_library.py        # 부품 핀/파라미터 (40+)
│   ├── symbol_registry.py          # 심볼 variant/앵커
│   ├── layout_strategy_registry.py # 배치 규칙/role 분류 (선언적)
│   ├── routing_policy_registry.py  # 라우팅 정책
│   ├── design_rule_registry.py     # 설계 규칙/default값
│   ├── bridge_mapping_registry.py  # PSIM 타입 매핑
│   └── capability_matrix.py        # topology × feature 지원 상태
├── parsers/             # intent_parser (legacy), keyword_map, unit_parser
├── tools/               # 15개 MCP 도구 핸들러
├── utils/               # SVG renderer, ASCII renderer
└── shared/              # state_store, audit, response builder
```

---

## 설정

환경 변수 또는 `.env` 파일:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `PSIM_MODE` | `mock` | `mock` (개발) 또는 `real` (PSIM 연동) |
| `PSIM_PATH` | — | PSIM 설치 경로 (real 모드 필수) |
| `PSIM_PYTHON_EXE` | — | PSIM Python 실행 파일 경로 |
| `PSIM_PROJECT_DIR` | — | .psimsch 저장 디렉터리 |
| `PSIM_OUTPUT_DIR` | — | 시뮬레이션 결과 디렉터리 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `SIMULATION_TIMEOUT` | `300` | 시뮬레이션 타임아웃 (초) |
| `PREVIEW_TTL` | `3600` | 미리보기 토큰 유효시간 (초) |
| `PSIM_SYNTHESIS_ENABLED_TOPOLOGIES` | (빈값=전체) | canonical pipeline 허용 topology (쉼표 구분) |
| `PSIM_INTENT_PIPELINE_V2` | `true` | V2 intent pipeline 활성화 |

---

## 개발

```bash
# 테스트 (821개)
uv run pytest tests/unit -q

# 단일 파일
uv run pytest tests/unit/test_circuit_design_service.py -v

# 키워드 매칭
uv run pytest tests/unit -k "test_buck" -v

# 린트 + 포맷
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# MCP Inspector (Claude Desktop 없이 디버그)
uv run mcp dev src/psim_mcp/server.py
```

### 새 topology 추가

1. `generators/my_topology.py` — `TopologyGenerator` 구현 (`generate()` + `synthesize()`)
2. `synthesis/topologies/my_topology.py` — `synthesize_my_topology()` → CircuitGraph (roles, blocks, nets)
3. `data/topology_metadata.py` — 메타데이터 항목 추가 (required_fields, block_order, layout_family 등)
4. `generators/__init__.py` — registry 등록

**Layout과 routing은 자동 처리됩니다:**
- `auto_placer.py`가 block/role 기반으로 배치 자동 생성
- Role 이름 규칙만 따르면 placement/direction 분류 자동
- 규칙: `layout_strategy_registry.py` 상단 주석 참조

### Role 네이밍 규칙

| 키워드 | placement | direction |
|--------|-----------|-----------|
| `ground`, `gnd` | ground (rail) | 0 |
| `gate`, `drive`, `pwm`, `controller` | control (하단) | 0 |
| `capacitor`, `cap` | shunt (전력 경로 아래) | 90 (수직) |
| `switch`, `source`, `inductor`, `transformer`, `rectifier` | power_path (상단) | 0 (기본) |
| `high_side`, `low_side` | power_path | 0 (수직 스위치) |
| `load` | shunt | 90 |

예외는 `_PLACEMENT_OVERRIDES` / `_DIRECTION_OVERRIDES`에 등록. 자세한 규칙은 `layout_strategy_registry.py` 참조.

---

## 설계 문서

`docs/ver5/`에 전체 설계 문서가 있습니다:

| 문서 | 내용 |
|------|------|
| `prd-and-architecture-*.md` | 최상위 PRD + 아키텍처 |
| `phase-execution-plan.md` | Phase 1~5 실행 계획 |
| `phase-1~5-*.md` | 각 Phase 상세 설계 |
| `algorithmic-layout-plan.md` | 알고리즘 레이아웃 설계 + 업계 조사 |
| `implementation-status.md` | 구현 현황 감사 |
| `circuit-metadata-schema.md` | 메타데이터 스키마 |
| `metadata-to-code-ownership-map.md` | 메타데이터 ownership |

---

## 보안

- **경로 보안**: `Path.resolve()` + `is_relative_to()`로 path traversal 방지
- **입력 검증**: Pydantic 제약 + 시뮬레이션 옵션 범위 검증
- **출력 보안**: LLM 컨텍스트 sanitization, 50KB 응답 크기 제한
- **subprocess 보안**: `shell=False`, JSON stdin 전달, 환경 격리
- **감사 로깅**: SHA-256 입력 해싱, 4개 로그 파일 분리 (server, psim, security, tools)
- **Bridge stdout 보호**: PSIM API stdout 오염 차단 (`_suppress_stdout`)

---

## 라이선스

MIT
