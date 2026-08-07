# psim-mcp

<!-- mcp-name: io.github.zongseung/psim-mcp -->

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="assets/psim-mcp-icon.png" alt="PSIM-MCP icon" width="180">
</p>

<p align="center">
  AI 에이전트가 Altair PSIM 전력전자 회로를 열고, 이해하고, 수정하고, 시뮬레이션하게 하는 MCP 서버.
</p>

<p align="center">
  <a href="https://github.com/zongseung/psim-mcp/actions/workflows/ci.yml"><img src="https://github.com/zongseung/psim-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

## 주요 기능

- **기존 회로 자동화**: `.psimsch` 회로를 열어 소자·파라미터·전기적 넷을 복원하고 수정합니다.
- **실제 PSIM 시뮬레이션**: PSIM 2026 엔진으로 시간 영역 시뮬레이션을 실행하고 `.smv` 결과를 분석합니다.
- **파라미터 스윕**: 단일 파라미터 범위 실험(`sweep_parameter`)으로 반복 시뮬레이션을 자동화합니다.
- **제한된 Optuna 최적화**: 원본을 보존하는 격리 사본에서 L/C/설계 저항 값을 최적화합니다(`optimize_circuit`).
- **에이전트 스킬 내장**: 회로 워크플로·최적화 절차를 스킬로 제공해 Claude Code와 Codex가 같은 원칙으로 작업합니다.

## 빠른 시작

### Claude Code 플러그인 (권장 — MCP 서버 + 스킬 일괄 설치)

```text
/plugin marketplace add zongseung/psim-mcp
/plugin install psim-mcp@psim-mcp
```

플러그인은 MCP 서버(`uvx psim-mcp`)와 `psim-circuit-workflow`, `psim-circuit-optimization` 스킬을 함께 설치합니다. 자세한 내용은 [Claude Code 플러그인과 스킬](#claude-code-플러그인과-스킬)을 참고하세요.

### Claude Code (MCP 서버만)

```bash
# PyPI 배포 후
claude mcp add psim-mcp -- uvx psim-mcp

# 저장소 클론 기준 (현재)
claude mcp add psim-mcp -- uv run --directory C:\path\to\psim-mcp psim-mcp
```

### Claude Desktop

[MCP 클라이언트 설정](#mcp-클라이언트-설정) 섹션의 `claude_desktop_config.json` 예제를 사용합니다.

`real` 모드(실제 PSIM 실행)는 [환경 변수 설정](#real과-mock-실행-모드)이 필요합니다. 기본값은 `mock` 모드입니다.

## 시스템 개요와 지원 범위

psim-mcp는 MCP 클라이언트가 기존 Altair PSIM 회로를 열고, 구조와 결과를 분석하고, 파라미터를 변경하고, 실제 PSIM 시뮬레이션과 제한된 Optuna 최적화를 실행할 수 있게 하는 서버입니다.

지원 범위는 기존 `.psimsch` 회로의 자동화입니다. 새 토폴로지나 회로를 생성하는 도구는 제공하지 않습니다.

대표 실행 흐름은 다음과 같습니다.

1. `open_project`로 기존 회로를 엽니다.
2. `get_project_info` 또는 `import_circuit`로 소자, 파라미터, 연결을 확인합니다.
3. 단일 변경은 `set_parameter`, 반복 실험은 `sweep_parameter`, 제한 최적화는 `optimize_circuit`를 사용합니다.
4. `run_simulation`으로 PSIM을 실행합니다.
5. `analyze_simulation`, `analyze_existing`, `export_results`로 결과를 확인합니다.

지원하지 않는 것: 새 토폴로지 생성 도구, 결과 간 자동 비교(before/after 비교는 두 결과를 각각 `analyze_existing`으로 분석해 대조).

`real` 모드는 실제 PSIM을 사용합니다. `mock` 모드는 개발과 MCP 연결 시험을 위한 결정론적 대체 구현이며 실제 회로 성능의 근거가 아닙니다.

## PSIM MCP 동작 구조

```text
MCP client
    │  stdio 또는 SSE
    ▼
FastMCP tool layer
    │  요청 검증·응답 표준화·감사 로그
    ▼
Project / Simulation / Analysis / Optimization services
    │
    ├─ mock adapter ── 개발용 결정론적 결과
    │
    └─ real adapter ── Python 3.9 bridge ── PSIM 2026
                                             │
                                             ├─ .psimsch
                                             └─ .smv / JSON / CSV / PNG
```

MCP 서버는 Python 3.12 이상에서 동작합니다. `real` adapter는 별도의 PSIM 호환 Python 3.9 프로세스를 시작하고 JSON 라인 프로토콜로 PSIM API를 호출합니다. PSIM 객체는 브리지 프로세스에만 존재합니다.

모든 공개 도구 응답은 기본적으로 다음 envelope를 사용합니다.

```json
{"success": true, "data": {}, "message": "..."}
```

실패 응답은 `success=false`와 `error.code`, `error.message`를 제공합니다. `optimize_circuit` 실패 응답은 실행 상태를 `data`에도 보존합니다.

서버는 세션 시작 시 MCP server instructions로 표준 워크플로를 안내하고, `guidelines://workflow`, `guidelines://gotchas`, `guidelines://templates`, `guidelines://control-patterns` 리소스로 도메인 지식(파라미터 이름 함정, 검증된 회로 템플릿, C-Block 제어 패턴)을 제공합니다.

## 요구사항과 설치

| 항목 | 필수 조건 | 용도 |
| --- | --- | --- |
| Python | 3.12 이상 | MCP 서버 |
| [uv](https://docs.astral.sh/uv/) | 최신 안정 버전 | 의존성·실행 관리 |
| MCP 클라이언트 | 선택 | Claude Desktop, Claude Code, Codex 등 |
| Altair PSIM | 2026, `real` 모드에서 필수 | 실제 시뮬레이션 |
| PSIM 호환 Python | 3.9, `real` 모드에서 필수 | PSIM 브리지 |

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync
```

Optuna `>=4.9,<5`는 기본 dependency입니다. 별도 설치가 필요하지 않습니다. 개발 도구까지 설치하려면 `uv sync --all-extras`를 사용합니다.

## `real`과 `mock` 실행 모드

| 모드 | PSIM 필요 | 목적 | 결과 해석 |
| --- | --- | --- | --- |
| `real` | 필요 | 실제 회로 열기·수정·시뮬레이션·최적화 | PSIM artifact와 함께 제품 결과로 사용 가능 |
| `mock` | 불필요 | 도구 연결, 요청 검증, 테스트 | 실제 회로 성능으로 해석 금지 |

저장소 루트의 `.env.example`을 `.env`로 복사하고 실제 설치 경로를 설정합니다.

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<user>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
ALLOWED_PROJECT_DIRS=C:\work\psim-projects,D:\shared\verified-circuits
```

`real` 모드에는 `PSIM_PATH`, `PSIM_PYTHON_EXE`, `PSIM_OUTPUT_DIR`가 모두 필요합니다. `ALLOWED_PROJECT_DIRS`는 쉼표로 구분한 절대 경로 목록입니다. 비어 있으면 프로젝트 validator가 허용하는 절대 경로를 사용할 수 있습니다.

| 환경 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock` 또는 `real` |
| `PSIM_PATH` | 없음 | PSIM 설치 디렉터리 |
| `PSIM_PYTHON_EXE` | 없음 | 브리지용 Python 실행 파일 |
| `PSIM_OUTPUT_DIR` | 없음 | 시뮬레이션·최적화 artifact 루트 |
| `ALLOWED_PROJECT_DIRS` | 비어 있음 | 허용할 절대 프로젝트 경로 목록 |
| `LOG_DIR` | `<저장소>/logs` | 서버 로그 디렉터리 |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `SERVER_TRANSPORT` | `stdio` | `stdio` 또는 `sse` |
| `SERVER_HOST` | `127.0.0.1` | SSE bind 주소 |
| `SERVER_PORT` | `8000` | SSE port |
| `SIMULATION_TIMEOUT` | `300` | 기본 시뮬레이션 제한 시간(초) |
| `MAX_SWEEP_STEPS` | `100` | `sweep_parameter` 최대 단계 수 |

## MCP 클라이언트 설정

Claude Desktop의 `claude_desktop_config.json`에 다음 서버 정의를 추가합니다.

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS에서 mock/원격 사용: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "psim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\psim-mcp", "psim-mcp"],
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2026",
        "PSIM_PYTHON_EXE": "C:\\Users\\<user>\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
        "PSIM_OUTPUT_DIR": "C:\\path\\to\\psim-mcp\\output",
        "ALLOWED_PROJECT_DIRS": "C:\\work\\psim-projects"
      }
    }
  }
}
```

설정 후 MCP 클라이언트를 완전히 종료하고 다시 시작합니다. 서버만 직접 실행하려면 저장소 루트에서 `uv run psim-mcp`를 사용합니다.

## Claude Code 플러그인과 스킬

이 저장소는 그 자체로 Claude Code 플러그인 마켓플레이스입니다. 플러그인 하나로 MCP 서버와 스킬이 함께 설치됩니다.

```text
/plugin marketplace add zongseung/psim-mcp
/plugin install psim-mcp@psim-mcp
```

번들 구성:

| 구성 요소 | 내용 |
| --- | --- |
| MCP 서버 | `uvx psim-mcp` (기본 `mock` 모드; `real` 모드는 환경 변수 설정 필요) |
| `psim-circuit-workflow` 스킬 | 기존 회로 읽기 → 파라미터 수정 → 시뮬레이션 → 분석의 표준 절차와 silent no-op 파라미터 함정 검증 루프 |
| `psim-circuit-optimization` 스킬 | 원본 보존·증거 기반의 제한된 Optuna 최적화 절차 |

Codex 등 [agentskills.io](https://agentskills.io) 스펙을 따르는 에이전트는 저장소의 `.agents/skills/` 디렉터리에서 동일한 스킬을 사용합니다. 두 위치의 스킬 파일은 CI 테스트(`tests/unit/test_skills_sync.py`)로 동기화가 강제됩니다.

## 공개 도구 11개 기술 명세

| 도구 | 입력 개요 | 동작과 파일 영향 |
| --- | --- | --- |
| `open_project` | `.psimsch` 절대 경로 | 기존 프로젝트를 열고 메타데이터를 반환 |
| `get_project_info` | 없음 | 열린 프로젝트의 소자와 파라미터를 조회 |
| `import_circuit` | 경로, `include_graph` | 소자·넷·미연결 핀·시뮬레이션 설정을 복원 |
| `set_parameter` | 소자 ID, 파라미터명, 값 | 현재 열린 `.psimsch`에 값을 저장하므로 원본을 변경할 수 있음 |
| `sweep_parameter` | 단일 파라미터 범위와 step | 값을 순차 저장·시뮬레이션하며 마지막 값이 열린 프로젝트에 남음; 최대 단계 제한 적용 |
| `run_simulation` | 선택적 timestep, total time, timeout, Simview | 현재 프로젝트를 실행하고 `.smv` 결과를 생성 |
| `export_results` | 출력 디렉터리, `json`/`csv`, 신호 목록 | 최근 시뮬레이션 결과를 파일로 내보냄 |
| `get_status` | 없음 | PSIM 가용성, 버전, 현재 프로젝트 상태 조회 |
| `analyze_simulation` | topology, 목표, 파형 옵션 | 시뮬레이션 후 topology별 메트릭·샘플·선택적 PNG 생성 |
| `analyze_existing` | `.smv`, topology, 목표, 파형 옵션 | 재실행 없이 기존 결과 분석; 메트릭이 비면 `available_signals` 확인 필요 |
| `optimize_circuit` | 동적 최적화 request | 원본이 아닌 격리된 사본에서 순차 Optuna study 실행 |

`set_parameter`와 `sweep_parameter`는 현재 열린 파일을 변경합니다. 원본을 보존해야 하는 수동 실험에는 사용자가 작업 사본을 준비해야 합니다. `optimize_circuit`는 아래의 별도 사본·복원 계약을 갖습니다.

## `optimize_circuit` 요청·실행·결과 계약

프로젝트에 포함된 `psim-circuit-optimization` 스킬을 사용하면 에이전트가 이 계약에 따라 제한된 study를 구성하도록 지시할 수 있습니다.

### 최상위 요청

| 필드 | 형식 | 제약과 의미 |
| --- | --- | --- |
| `source_project_path` | string | 기존 `.psimsch` 절대 경로; 비어 있을 수 없음 |
| `variables` | array | 1–3개의 고유 decision variable |
| `measurements` | array | 1개 이상; 이름은 고유해야 함 |
| `objective` | array | 1개 이상의 측정값 target term |
| `constraints` | array | 1개 이상의 hard constraint |
| `n_trials` | integer | 기본 50, 허용 범위 1–50 |
| `time_budget_seconds` | integer | 기본 300, 허용 범위 1–300; 실행 중 trial을 중단하지 않고 다음 trial 시작 여부만 제한 |
| `seed` | integer | 기본 0, 허용 범위 0–4,294,967,295 |

알 수 없는 필드는 거부됩니다. 이름은 영문자로 시작하고 영문자·숫자·밑줄만 포함하며 최대 64자입니다.

### Decision variable과 binding

| 필드 | 형식 | 제약 |
| --- | --- | --- |
| `name` | string | variable 간 고유 이름 |
| `min` / `max` | number | 둘 다 0보다 크고 `min < max` |
| `bindings` | array | 1개 이상; 동일 소자·파라미터 중복 금지 |
| `log_scale` | boolean | 기본 `true`; Optuna log sampling 사용 여부 |

| `component_kind` | `parameter_name` | 추가 규칙 |
| --- | --- | --- |
| `L` | `Inductance` | 검증된 인덕터 binding |
| `C` | `Capacitance` | 검증된 커패시터 binding |
| `R` | `Resistance` | 반드시 `role: "design"`; load 저항은 거부 |

하나의 variable에 여러 binding을 넣으면 같은 제안값이 모든 binding에 적용됩니다. 소자 ID와 범위는 실제 프로젝트 정보와 설계 근거로 확인해야 합니다.

### Measurement, objective, constraint

| Measurement 필드 | 형식 | 제약 |
| --- | --- | --- |
| `name` | string | 측정값 고유 이름 |
| `signal` | string | 실제 `.smv` 신호명, 1–128자 |
| `function` | enum | `mean`, `ripple_pp`, `ripple_percent`, `peak`, `rms` |
| `window.start_fraction` | number | `0 <= start < 1` |
| `window.end_fraction` | number | `0 < end <= 1`, `start < end` |
| `window.min_samples` | integer | 기본 2, 최소 2 |

목적함수는 다음 normalized squared error의 합입니다.

```text
cost = Σ weight × ((measurement - target) / normalization_scale)²
```

`weight` 기본값은 1입니다. `scale`을 생략하면 `abs(target)`을 사용하며, target이 0이면 양수 `scale`을 명시해야 합니다.

Hard constraint의 `operator`는 `<=` 또는 `>=`입니다. `scale`은 양수여야 합니다. 정규화 residual이 0 이하인 trial만 feasible합니다.

```text
operator <= : residual = (measurement - limit) / scale
operator >= : residual = (limit - measurement) / scale
```

### Study 생명주기

1. 소스 경로와 `PSIM_OUTPUT_DIR`를 검증합니다.
2. `optuna-*` study 디렉터리와 `study.jsonl`을 생성합니다.
3. `source-copy.psimsch`와 `working.psimsch`를 만들고 SHA-256을 대조합니다.
4. 이전 PSIM 프로젝트 경로를 보관하고 adapter session lease를 획득합니다.
5. 작업 사본에서 baseline을 실행합니다.
6. seeded TPE sampler가 trial 값을 제안하고 PSIM을 순차 실행합니다.
7. measurement와 hard constraint가 유효한 feasible trial 중 최소 cost를 선택합니다.
8. 소스 사본에서 `best.psimsch`를 새로 만들고 선택값을 적용한 뒤 `best.smv`를 재실행합니다.
9. 이전 프로젝트를 다시 열고 소스 SHA-256을 재확인합니다.
10. trial·terminal 레코드를 JSONL ledger에 기록하고 결과를 반환합니다.

### 결과 필드와 상태

| 필드 | 의미 |
| --- | --- |
| `state` | `completed`, `time_budget_reached`, `no_feasible_trial`, `failed`, `cancelled` 등 terminal 상태 |
| `stop_reason` | `trials_exhausted`, `time_budget_reached`, validation/setup/restore 실패 원인 |
| `trials_complete` / `trials_failed` | 완료·실패 trial 수 |
| `best_params` / `best_cost` / `best_metrics` | 최종 재실행으로 검증한 선택값과 결과 |
| `constraint_residuals` | 0 이하이면 해당 hard constraint 충족 |
| `study_dir` / `ledger_path` | study 디렉터리와 JSONL 증거 ledger |
| `best_project_path` | 최종 값을 적용한 `best.psimsch` |
| `result_paths` | 실제로 존재하는 baseline, trial, best `.smv` 경로 |
| `source_hash_before` / `source_hash_after` | 원본 불변성 확인용 SHA-256 |
| `restoration_status` | `restored`, `no_previous_project`, 또는 실패 설명 |
| `elapsed_seconds` | setup부터 terminal 기록까지 경과 시간 |
| `error` | 실패 설명; 성공 시 `null` |

누락 신호, 표본 부족, 비유한 수치, binding 오류, 실행 실패, feasible trial 부재, 소스 변경, 세션 복원 실패는 성공으로 보고되지 않습니다.

## JSON 요청·응답 예제

다음 수치와 신호명은 특정 회로를 위한 형식 예제입니다. 다른 회로에 그대로 적용할 설계 권장값이 아닙니다.

```json
{
  "request": {
    "source_project_path": "C:\\work\\psim-projects\\inverter.psimsch",
    "variables": [
      {
        "name": "L1_inductance",
        "min": 0.002,
        "max": 0.0032,
        "bindings": [
          {
            "component_id": "L1",
            "component_kind": "L",
            "parameter_name": "Inductance"
          }
        ],
        "log_scale": true
      },
      {
        "name": "C1_capacitance",
        "min": 0.0000024,
        "max": 0.0000027,
        "bindings": [
          {
            "component_id": "C1",
            "component_kind": "C",
            "parameter_name": "Capacitance"
          }
        ],
        "log_scale": true
      }
    ],
    "measurements": [
      {
        "name": "vout_rms",
        "signal": "Vout",
        "function": "rms",
        "window": {
          "start_fraction": 0.8,
          "end_fraction": 1.0,
          "min_samples": 2000
        }
      },
      {
        "name": "vout_ripple_pp",
        "signal": "Vout",
        "function": "ripple_pp",
        "window": {
          "start_fraction": 0.8,
          "end_fraction": 1.0,
          "min_samples": 2000
        }
      }
    ],
    "objective": [
      {"measurement": "vout_rms", "target": 155.6}
    ],
    "constraints": [
      {
        "measurement": "vout_ripple_pp",
        "operator": "<=",
        "limit": 446.0,
        "scale": 1.0
      }
    ],
    "n_trials": 3,
    "time_budget_seconds": 60,
    "seed": 7
  }
}
```

축약된 성공 응답 예제:

```json
{
  "success": true,
  "data": {
    "success": true,
    "state": "completed",
    "stop_reason": "trials_exhausted",
    "trials_complete": 3,
    "trials_failed": 0,
    "best_params": {
      "L1_inductance": 0.00305,
      "C1_capacitance": 0.00000258
    },
    "best_cost": 7.6e-11,
    "best_metrics": {
      "vout_rms": 155.601,
      "vout_ripple_pp": 443.604
    },
    "constraint_residuals": [-2.396],
    "best_project_path": "C:\\output\\optuna-example\\best.psimsch",
    "source_hash_before": "<sha256>",
    "source_hash_after": "<sha256>",
    "source_changed_during_study": false,
    "restoration_status": "restored",
    "study_dir": "C:\\output\\optuna-example",
    "ledger_path": "C:\\output\\optuna-example\\study.jsonl",
    "result_paths": [
      "C:\\output\\optuna-example\\baseline.smv",
      "C:\\output\\optuna-example\\trial-0000.smv",
      "C:\\output\\optuna-example\\best.smv"
    ],
    "elapsed_seconds": 13.1,
    "error": null
  },
  "message": "Optimization completed"
}
```

## 안전 규칙과 제외 대상

- 신뢰할 수 있는 `.psimsch`와 `.smv` 파일만 사용합니다.
- `ALLOWED_PROJECT_DIRS`로 접근 가능한 프로젝트 경로를 최소화합니다.
- `set_parameter`와 `sweep_parameter`를 원본에서 실행하지 않습니다. 사용자가 명시적으로 준비한 작업 사본을 엽니다.
- `optimize_circuit`에는 실제 프로젝트에서 확인한 소자 ID, 신호명, 단위, 범위, target과 hard limit만 전달합니다.
- solver timestep, safety/protection limit, topology, load 저항, 임의 gate schedule은 최적화하지 않습니다.
- `window`는 단순히 파형의 일부를 선택합니다. 물리적 settling 근거가 없으면 steady-state 결과라고 부르지 않습니다.
- `time_budget_seconds`는 실행 중인 PSIM trial을 강제 종료하지 않습니다.
- 성공 보고에는 feasible best trial, 최종 rerun artifact, 복원 상태와 동일한 before/after 소스 해시가 필요합니다.
- `mock` 결과는 실제 PSIM 성능 또는 안전성의 증거가 아닙니다.

## 개발과 검증

```bash
uv sync --all-extras
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
claude plugin validate . --strict
```

CI(GitHub Actions)는 push/PR마다 ruff lint·format 검사, ubuntu·windows 매트릭스에서 `PSIM_MODE=mock` 단위 테스트, 플러그인 매니페스트 검증을 실행합니다. `v*` 태그를 push하면 release 워크플로가 빌드 후 PyPI Trusted Publishing으로 배포합니다.

실제 PSIM이 필요한 검증은 Windows 호스트에서 `PSIM_MODE=real`과 필수 경로를 설정한 뒤 별도로 실행합니다. 저장소에는 단위 테스트, stdio integration test, opt-in real-PSIM marker가 분리되어 있습니다.

## 라이선스

MIT
