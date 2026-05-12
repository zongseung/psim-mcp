# psim-mcp

Claude Desktop에서 자연어로 전력전자 회로를 설계하고 Altair PSIM으로 시뮬레이션하는 MCP 서버.

**18개 Tool** | **1075개 테스트** | **173개 소스 파일** | **29개 topology** | **40+ 부품 라이브러리** | **LLM-native intent (regex / sampling / hybrid)**

```
"buck converter 48V to 12V 5A"
  → Intent 추출 → Topology 선택 → CircuitGraph → Auto Layout → Routing → SVG Preview → .psimsch
```

---

## 주요 기능

- **자연어 회로 설계** — 한국어/영어로 회로를 설명하면 topology 자동 선택, 파라미터 계산, 회로도 생성
- **LLM-native intent layer** — Strategy 패턴 기반 `IntentResolver` (regex / MCP sampling / hybrid 선택 가능); `Vin=12V` / `12V input` / `입력 400V` 같은 명시·암묵 라벨 모두 인식
- **29개 전력전자 topology** — Buck, Boost, Flyback, LLC, Full-Bridge, 3-Phase Inverter, BLDC Drive 등
- **PSIM 템플릿 기반 폐루프 제어** — Altair 검증된 reference schematic을 chassis로 가져와 파라미터 / C 블록 코드를 MCP가 주입. Boost vin=12V→vout=48V 정상상태 V<sub>o</sub>=48.07V·I<sub>o</sub>=2.003A 검증 완료
- **알고리즘 기반 자동 배치** — 좌표 하드코딩 없이 CircuitGraph에서 schematic layout 자동 생성
- **Pin-aware 와이어 라우팅** — L-shape 꺾임점이 다른 핀과 충돌하지 않도록 자동 우회
- **PSIM 2026 강체 element 호환** — `MULTI_MOSFET` 게이트 / `VSEN` / `GATING` 등 PSIM이 PORTS를 강제 재배치하는 element에 대해 `AREA` 자동 산출 (이전 "gate floating" 에러 원인 해결)
- **SVG + ASCII 미리보기** — 생성 전 회로도 확인, 수정, 확정 (브라우저 자동 열기)
- **PSIM Simview 파형** — 시뮬레이션 후 Simview에서 자동으로 파형 그래프 표시
- **대화형 설계 루프** — `design_circuit` → 질문 → `continue_design` → 미리보기 → `confirm_circuit`
- **Mock 모드** — PSIM 없이 개발/테스트 가능 (macOS, Linux 포함)

---

## PSIM 시뮬레이션 검증 현황

| 상태 | topology (15/25) |
|------|-----------------|
| **검증 완료** (open-loop) | buck, boost, flyback, buck_boost, sepic, cuk, forward, llc, cc_cv_charger, bidirectional_buck_boost, dab, pv_mppt_boost, ev_obc, diode_bridge_rectifier, boost_pfc |
| **검증 완료** (closed-loop) | boost (`closed_loop=True` → PSIM peak-current-mode reference, V<sub>o</sub>=48V @ 2A 정착) · buck (`closed_loop=True` + 선택적 `c_code` → PSIM C-block digital reference, Claude 작성 PI 코드를 SSCB7에 install 후 시뮬) |
| 검증 진행 중 | half_bridge, full_bridge, push_pull, thyristor_rectifier, totem_pole_pfc, three_level_npc, bldc_drive, pmsm_foc_drive, induction_motor_vf, pv_grid_tied |

---

## PSIM 템플릿 활용

PSIM에 동봉된 검증된 예제 회로를 chassis로 가져와 **파라미터 / C 코드만 MCP가 갈아끼우는** 방식. 좌표 / 와이어 / element 배치를 직접 합성하는 것보다 안정적이며 PSIM 2026의 강체 element / 노드 병합 quirk을 우회합니다.

`psim_template` directive를 generator가 emit하면 bridge의 `_handle_template_circuit`이 받아 sidecar 파일 복사 + 3종 override를 차례로 적용:

```python
psim_template = {
    "source": r"examples\Power Supply Design Suite\Boost converter\Boost converter with peak current mode control.psimsch",

    # (1) 동반 파라미터 파일을 dst 옆에 복사
    "sidecar_files": ["parameters-main.txt"],

    # (2) UTF-16 텍스트 치환으로 매크로 갈아끼우기 (Vin/Vo/Po/fsw 등)
    "parameter_file_overrides": [
        {"file": "parameters-main.txt", "find": "Vin = 5;",  "replace": "Vin = 12;"},
        {"file": "parameters-main.txt", "find": "Vo = 12;",  "replace": "Vo = 48;"},
        {"file": "parameters-main.txt", "find": "Po = 200;", "replace": "Po = 96;"},
    ],

    # (3) 회로 내부 element 파라미터 직접 갈아끼우기 (PsimSetElmValue2)
    "parameter_overrides": [
        {"type": "MULTI_RESISTOR", "name": "RL", "param": "Resistance", "value": "24"},
    ],

    # (4) SIMPLECBLOCK C 코드 통째 교체 — MCP가 LLM 생성 PI / MPC / 데드비트 로직을 주입
    "c_block_overrides": [
        {"name": "SSCB7", "code": "// MCP-generated PI\r\ny1 = x1 - x2;\r\n..."},
    ],
}
```

**활용 패턴**:
- 검증된 토폴로지 → 파라미터만 치환 (안전·빠름)
- 커스텀 제어기 실험 → PSIM chassis 유지하고 `c_block_overrides`로 알고리즘 주입 (iteration 빠름)
- 혼합 → 한 회로의 SIMPLECBLOCK 일부만 선택적 override

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
| `mcp>=1.26.0` | 필수 | sampling/elicitation 지원 (자동 설치) |
| Claude Desktop | 필수 | MCP 클라이언트 |
| Altair PSIM 2026 | 선택 | 실제 회로 생성/시뮬레이션 시 필요 |
| Python 3.8/3.9 | 선택 | PSIM 브리지용 (PSIM 설치 시 동봉) |
| matplotlib | 선택 | 파형 PNG 렌더링 (`uv add matplotlib`) |

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
        "PSIM_OUTPUT_DIR": "C:\\Users\\{사용자}\\psim-output",
        "INTENT_RESOLVER_MODE": "regex"
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
        "PSIM_MODE": "mock",
        "INTENT_RESOLVER_MODE": "regex"
      }
    }
  }
}
```

Claude Desktop을 **완전 종료** 후 재실행하면 17개 tool이 표시됩니다.

---

## 사용법

### Claude Desktop에서 프롬프트 예시

```
design_circuit 도구로 buck converter vin=48 vout_target=12 iout=5 설계하고,
confirm_circuit으로 PSIM 파일 생성한 후,
run_simulation simview=true로 파형 보여줘.
```

### 다양한 topology 예시

```
design_circuit으로 boost converter vin=12 vout_target=48 iout=2 만들고 confirm 후 시뮬레이션

design_circuit으로 boost vin=12V vout=48V iout=2A 폐루프 시뮬레이션
   ↳ "폐루프" / "closed loop" / "피드백" 키워드 감지 시 PSIM 검증된 reference로 라우팅

design_circuit으로 flyback converter vin=400 vout_target=24 iout=3 설계해서 시뮬레이션까지

design_circuit으로 llc converter vin=400 vout_target=48 iout=10 만들고 PSIM 파형 보여줘

design_circuit으로 sepic converter vin=12 vout_target=24 iout=1 설계하고 시뮬레이션

design_circuit으로 ev_obc vin=220 vout_target=400 설계하고 시뮬레이션

design_circuit으로 pv_mppt_boost 설계해서 PSIM에서 돌려줘
```

### Claude가 C 코드를 작성해 SIMPLECBLOCK에 주입하기

폐루프 토폴로지(현재 `buck`)는 PSIM 디지털 제어 reference schematic을 chassis로 가져오고, **Claude가 직접 작성한 C 코드를 그 안의 `SSCB7` 컴펜세이터에 install**합니다. 사용자는 알고리즘 의도만 자연어로 던지면 됩니다.

```
buck converter 48V→12V 2A 폐루프 시뮬 돌려줘.
PI 컨트롤러는 네가 직접 C 코드로 짜서 SSCB7에 넣어줘. Kp=0.2, Ti=50μs로.
```

이 한 줄을 받으면 Claude가:

1. `preview_circuit` description에서 SSCB7 호출 규약 (입력 `x1=IL_ref / x2=IL_sense / x3=Kp / x4=Ti / x5=Fsamp / x6=upper_limit / x7=lower_limit / x8=ap_start`, 출력 `y1=duty / y2=integ`) 을 읽고
2. 그 시그니처에 맞춰 PI 컨트롤러 C 소스를 즉석 작성
3. `preview_circuit(specs={..., "closed_loop": True, "c_code": "<생성한 코드>"})` 호출
4. Generator → `psim_template.c_block_overrides` → bridge → `PsimSetElmValue2(sch, "SIMPLECBLOCK", "SSCB7", "CONTENT", code)` 로 자동 install
5. PSIM이 Claude 작성 PI로 시뮬레이션 → Vo / IL / Duty 파형 반환

직접 호출 형태로도 가능:

```python
preview_circuit(
    circuit_type="buck",
    specs={
        "vin": 48, "vout_target": 12, "iout": 2,
        "closed_loop": True,
        "c_code": (
            "static float integ = 0.0f;\r\n"
            "float Kp = x3, Ti = x4, Fsamp = x5;\r\n"
            "float A0 = Kp, A1 = Kp / (Ti * 2.0f * Fsamp);\r\n"
            "if (x8) {\r\n"
            "    float e = x1 - x2;\r\n"
            "    integ += A1 * e;\r\n"
            "    y1 = A0 * e + integ;\r\n"
            "    if (y1 > x6) y1 = x6;\r\n"
            "    if (y1 < x7) y1 = x7;\r\n"
            "}\r\n"
            "y2 = integ;\r\n"
        ),
    },
)
```

> **검증 흐름**: chassis 파일에 Claude 코드 tag를 박아 `PsimConvertToPython`으로 다시 덤프해 보면 SSCB7 CONTENT에 해당 코드가 들어가 있음을 확인할 수 있습니다 (`[LLM-INJECTED-PI ...]` 태그). 즉 *Claude가 짠 코드 그대로* PSIM이 컴파일·실행합니다.

### 핵심 규칙

| 규칙 | 이유 |
|------|------|
| `vout` 말고 **`vout_target`** 사용 | generator가 이 키를 인식 |
| **`design_circuit` → `confirm_circuit` → `run_simulation`** 순서 명시 | LLM이 단계를 건너뛰지 않게 |
| `simview=true` 추가 | PSIM Simview에서 파형 자동 열림 |

### 설계 흐름

```
1. design_circuit("buck converter vin=48 vout_target=12 iout=5")
   → topology 선택, 파라미터 계산, SVG 미리보기 자동 생성
   → preview_token 반환

2. confirm_circuit(preview_token, save_path="output/buck.psimsch")
   → PSIM .psimsch 파일 생성 + PSIM GUI 자동 실행

3. run_simulation(simview=true)
   → 시뮬레이션 실행 + PSIM Simview에서 파형 표시
```

---

## MCP 도구 (18개)

### 회로 설계

| 도구 | 설명 |
|------|------|
| `design_circuit` | 자연어 → 회로 설계 (topology 선택 + auto preview) |
| `continue_design` | 추가 정보 입력하여 설계 계속 (세션 토큰 기반) |
| `preview_circuit` | 회로 미리보기 (SVG + ASCII) |
| `confirm_circuit` | 미리보기 확정 → .psimsch 생성 + PSIM 자동 실행 |
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
| `run_simulation` | 시뮬레이션 실행 (simview=true로 Simview 자동 열기) |
| `export_results` | 결과 내보내기 (JSON/CSV) |
| `compare_results` | 시뮬레이션 결과 비교 |
| `get_status` | 서버/PSIM 상태 확인 |

### 분석

| 도구 | 설명 |
|------|------|
| `analyze_simulation` | 시뮬레이션 실행 + 토폴로지별 자동 분석 + 파형 PNG 생성 (PSIM Simview는 `open_simview=True`로 옵트인) |
| `analyze_existing` | **이미 존재하는 .smv** 결과 파일을 분석만 — 시뮬을 재실행하지 않아 빠름. `analyze_simulation` 타임아웃 시 `run_simulation` → `analyze_existing` 2단계로 우회 |
| `optimize_circuit` | 베이지안 최적화로 회로 파라미터 자동 튜닝 |

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

> 28개는 canonical `synthesize()` 구현, `pv_grid_tied`는 legacy template 경로 사용.

---

## 아키텍처

### 디렉터리 구성

```
src/psim_mcp/
├── server.py              # FastMCP 앱 팩토리 (create_app)
├── config.py              # AppConfig (Pydantic settings)
├── adapters/              # MockPsimAdapter / RealPsimAdapter
├── bridge/                # PSIM Python 3.8/3.9 브리지 IPC
├── data/                  # 8개 선언적 레지스트리 (topology, component, capability...)
├── generators/            # 토폴로지별 generate() / synthesize()
├── intent/                # 자연어 → 의도 추출 (Strategy 패턴)
│   ├── resolver.py        #   IntentResolver ABC + RegexResolver + factory
│   ├── sampling_resolver.py  # MCP sampling 기반 LLM 추출
│   ├── sampling_schema.py    # Pydantic v2 응답 스키마
│   ├── extractors.py      #   regex 기반 추출 (RegexResolver 백엔드)
│   ├── ranker.py          #   토폴로지 후보 점수화 (결정론적 안전망)
│   ├── spec_builder.py    #   CanonicalSpec 빌더
│   └── clarification.py   #   누락 정보 질문 정책
├── synthesis/             # CircuitGraph 합성 (28 토폴로지)
├── validators/            # 구조/전기/파라미터/그래프 검증
├── layout/                # SchematicLayout 자동 배치 (force-directed)
├── routing/               # WireRouting (trunk-branch, pin-aware)
├── services/              # CircuitDesign / Simulation / Project / Parameter
├── shared/                # ResponseBuilder, StateStore (preview tokens)
├── tools/                 # 18개 MCP 도구 (FastMCP 등록)
└── utils/                 # SVG/ASCII 렌더러, 로깅, 경로 보안
```

### Canonical Synthesis Pipeline

```
자연어
  → IntentResolver.resolve()   # regex | sampling | hybrid 전략 선택
       ├─ RegexResolver         # extractors → ranker → spec_builder (결정론)
       └─ SamplingResolver      # ctx.session.create_message() → LLM JSON → ranker 검증
  → generator.synthesize()     # CircuitGraph 합성 (synthesis/)
  → validate_graph()           # 구조 검증 (validators/)
  → generate_layout()          # SchematicLayout 자동 배치 (layout/)
  → generate_routing()         # WireRouting trunk/branch (routing/)
  → materialize_to_legacy()    # legacy 포맷 변환
  → SVG renderer / PSIM bridge
```

**핵심 설계 원칙**: LLM은 의도/토폴로지 제안만, 공학 계산(인덕터·캐패시터 값, 시뮬레이션 파라미터)은 결정론적 Python이 담당. `ranker.py`가 LLM의 제안을 `topology_metadata` 룰로 검증하는 안전망 역할.

### Intent Resolver Strategy

`INTENT_RESOLVER_MODE` 환경 변수 또는 `AppConfig.intent_resolver_mode`로 선택:

| 모드 | 백엔드 | 특성 |
|------|--------|------|
| `regex` (default) | `extractors.py` 정규식 28개 | 결정론적, LLM 호출 0회, CI/테스트 최적 |
| `sampling` | MCP `ctx.session.create_message` | 의미 기반 추출, "휴대폰 충전기" 같은 자연어 인식 |
| `hybrid` | sampling 시도 → 실패 시 regex | 프로덕션 권장 (Phase 2, 부분 구현) |

`get_resolver(mode)` 팩토리에서 라우팅 — `src/psim_mcp/intent/resolver.py:172`.

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

Bridge는 두 가지 회로 생성 경로를 지원합니다:

| 경로 | 트리거 | 동작 |
|------|--------|------|
| **컴포넌트 합성** | generator가 `components` / `nets` / `wire_segments`를 emit | bridge가 `PsimCreateNewElement`로 element 하나씩 만들고 wire 라우팅. `MULTI_MOSFET` / `VSEN` / `GATING` 등 강체 element에 대해 `AREA` 자동 산출 (이 값 없으면 PSIM이 PORTS를 임의 재배치) |
| **PSIM 템플릿 복제** | generator가 `psim_template` directive를 emit | bridge가 PSIM 예제 .psimsch를 dst로 복사한 뒤 (i) sidecar 파일 자동 동반 (ii) UTF-16 텍스트 치환 (iii) element 파라미터 갈아끼우기 (iv) SIMPLECBLOCK CONTENT 통째 교체 |

### Pin-aware Wire Routing

PSIM은 와이어 **끝점(endpoint)**에서만 전기적 연결을 인식합니다. L-shape 와이어의 꺾임점이 다른 컴포넌트 핀과 겹치면 의도하지 않은 단락이 발생합니다.

`_route_wire`는 모든 핀 위치를 알고:
1. **H-first L-shape**: 꺾임점이 안전하면 수평→수직
2. **V-first L-shape**: H-first 꺾임점이 핀과 겹기면 수직→수평
3. **Z-shape detour**: 양쪽 꺾임점 모두 충돌 시 중간 오프셋 경유

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
| `INTENT_RESOLVER_MODE` | `regex` | intent 추출 전략 (`regex` / `sampling` / `hybrid`) |
| `PSIM_INTENT_PIPELINE_V2` | `true` | V2 intent pipeline 활성화 |
| `PSIM_SYNTHESIS_ENABLED_TOPOLOGIES` | (빈값=전체) | canonical pipeline 허용 topology (쉼표 구분) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `SIMULATION_TIMEOUT` | `300` | 시뮬레이션 타임아웃 (초) |
| `PREVIEW_TTL` | `3600` | 미리보기 토큰 유효시간 (초) |
| `PSIM_AUTO_OPEN_PREVIEW` | `false` | 렌더 직후 SVG를 OS 기본 뷰어로 자동 오픈 (opt-in) |

---

## 개발

```bash
# 단위 테스트 (1075개 collected, 1074 passing)
uv run pytest tests/unit -q

# 단일 파일
uv run pytest tests/unit/test_intent_resolver.py -v

# 키워드 매칭
uv run pytest tests/unit -k "test_sampling" -v

# 린트 + 포맷
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# MCP Inspector (Claude Desktop 없이 디버그)
uv run mcp dev src/psim_mcp/server.py
```

> 모든 Python 작업은 `uv run` 사용. 절대 bare `python` / `pip` 사용 금지.

### 새 topology 추가

1. `generators/my_topology.py` — `TopologyGenerator` 구현 (`generate()` + `synthesize()`)
2. `synthesis/topologies/my_topology.py` — `synthesize_my_topology()` → CircuitGraph (roles, blocks, nets)
3. `data/topology_metadata.py` — 메타데이터 항목 추가 (required_fields, block_order, layout_family 등)
4. `generators/__init__.py` — registry 등록

**Layout과 routing은 자동 처리됩니다.**

### 새 IntentResolver 추가

1. `intent/my_resolver.py` — `IntentResolver` ABC 상속, `async resolve(description, ctx)` 구현
2. `intent/resolver.py:get_resolver()` — `mode == "my_resolver"` 분기 추가
3. `tests/unit/test_my_resolver.py` — 모킹 기반 단위 테스트

반환 dict는 `RESOLVER_RESULT_KEYS` 12개 키를 모두 포함해야 함 (`intent/resolver.py:34`).

---

## 설계 문서

`docs/ver5/`에 전체 설계 문서:

| 문서 | 내용 |
|------|------|
| `prd-and-architecture-*.md` | 최상위 PRD + 아키텍처 |
| `phase-execution-plan.md` | Phase 1~5 실행 계획 |
| `phase-4-routing-fix-plan.md` | PSIM 와이어 연결 문제 해결 기획서 |
| `implementation-status.md` | 구현 현황 |

LLM-native intent layer 마이그레이션 설계: `claudedocs/design-llm-native-intent-2026-04-28.md`.

---

## 보안

- **경로 보안**: `Path.resolve()` + `is_relative_to()`로 path traversal 방지
- **입력 검증**: Pydantic 제약 + 시뮬레이션 옵션 범위 검증
- **출력 보안**: LLM 컨텍스트 sanitization, 50KB 응답 크기 제한
- **subprocess 보안**: `shell=False`, JSON stdin 전달, 환경 격리
- **감사 로깅**: SHA-256 입력 해싱, 4개 로그 파일 분리 (server, psim, security, tools)
- **LLM 응답 검증**: Sampling 모드에서 LLM 제안 토폴로지를 `TOPOLOGY_METADATA` 키로 화이트리스트 검증, 미일치 시 ranker fallback

---

## 라이선스

MIT
