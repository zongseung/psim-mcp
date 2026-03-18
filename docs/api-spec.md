# PSIM-MCP Server: API Specification

> **버전**: v1.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md) | [architecture.md](./architecture.md)

---

## 1. 개요

이 문서는 PSIM-MCP Server가 Claude Desktop에 노출하는 MCP Tool의 상세 인터페이스를 정의한다. 각 tool의 입력 스키마, 출력 형식, 에러 코드, 사용 예시를 포함한다.

---

## 2. 공통 규격

### 2.1 응답 형식

모든 tool은 아래 구조의 JSON 객체를 문자열로 직렬화하여 반환한다.
이 문서의 예시는 특별한 언급이 없으면 모두 `data` 내부 구조를 설명한다.

**성공 응답**:
```json
{
  "success": true,
  "data": { ... },
  "message": "프로젝트가 성공적으로 열렸습니다."
}
```

**실패 응답**:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "사람이 읽을 수 있는 에러 메시지",
    "suggestion": "해결 방법 제안 (선택)"
  }
}
```

### 2.2 공통 에러 코드

| 코드 | 설명 |
|------|------|
| `INVALID_INPUT` | 입력값이 유효하지 않음 |
| `FILE_NOT_FOUND` | 지정된 파일이 존재하지 않음 |
| `PERMISSION_DENIED` | 파일/디렉터리 접근 권한 없음 |
| `PROJECT_NOT_OPEN` | 프로젝트가 열려있지 않은 상태에서 작업 시도 |
| `PSIM_NOT_CONNECTED` | PSIM이 연결되지 않음 (real 모드) |
| `PSIM_ERROR` | PSIM 내부 에러 |
| `SIMULATION_TIMEOUT` | 시뮬레이션 시간 초과 |
| `SIMULATION_FAILED` | 시뮬레이션 실행 실패 |
| `PATH_NOT_ALLOWED` | 허용되지 않은 경로 접근 시도 |
| `EXPORT_FAILED` | 결과 내보내기 실패 |

---

## 3. P0 Tools (핵심)

### 3.1 `open_project`

PSIM 프로젝트 파일을 열고 프로젝트 정보를 반환한다.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `path` | `string` | O | `.psimsch` 파일의 절대 경로 |

**성공 응답 (`data`)**:
```json
{
  "project_name": "buck_converter",
  "file_path": "C:\\projects\\buck_converter.psimsch",
  "components": [
    {
      "id": "V1",
      "type": "DC_Source",
      "parameters": {
        "voltage": 48.0
      }
    },
    {
      "id": "SW1",
      "type": "MOSFET",
      "parameters": {
        "on_resistance": 0.01,
        "switching_frequency": 50000
      }
    }
  ],
  "component_count": 12,
  "parameter_count": 28
}
```

**에러 코드**:
- `FILE_NOT_FOUND`: 파일이 존재하지 않음
- `INVALID_INPUT`: `.psimsch` 확장자가 아님
- `PERMISSION_DENIED`: 읽기 권한 없음
- `PSIM_ERROR`: PSIM에서 파일 열기 실패

**사용 예시**:
```
사용자: "C:\projects\buck_converter.psimsch 파일 열어줘"
Claude → open_project(path="C:\\projects\\buck_converter.psimsch")
```

---

### 3.2 `set_parameter`

열린 프로젝트의 컴포넌트 파라미터를 변경한다.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `component_id` | `string` | O | 컴포넌트 식별자 (예: `"V1"`, `"SW1"`) |
| `parameter_name` | `string` | O | 파라미터 이름 (예: `"voltage"`, `"switching_frequency"`) |
| `value` | `number \| string` | O | 새 값 |

**성공 응답 (`data`)**:
```json
{
  "component_id": "SW1",
  "parameter_name": "switching_frequency",
  "previous_value": 50000,
  "new_value": 100000,
  "unit": "Hz"
}
```

**에러 코드**:
- `PROJECT_NOT_OPEN`: 프로젝트가 열려있지 않음
- `INVALID_INPUT`: 컴포넌트 ID 또는 파라미터 이름이 유효하지 않음
- `PSIM_ERROR`: 파라미터 변경 실패

**사용 예시**:
```
사용자: "스위칭 주파수를 100kHz로 바꿔줘"
Claude → set_parameter(component_id="SW1", parameter_name="switching_frequency", value=100000)
```

---

### 3.3 `run_simulation`

현재 열린 프로젝트의 시뮬레이션을 실행한다.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `time_step` | `number` | X | 시뮬레이션 타임 스텝 (초). 미지정 시 프로젝트 기본값 |
| `total_time` | `number` | X | 총 시뮬레이션 시간 (초). 미지정 시 프로젝트 기본값 |
| `timeout` | `number` | X | 실행 타임아웃 (초). 기본값: 환경 변수 `SIMULATION_TIMEOUT` |

**성공 응답 (`data`)**:
```json
{
  "status": "completed",
  "duration_seconds": 4.52,
  "result_file": "C:\\output\\buck_sim_001.smv",
  "summary": {
    "output_voltage_avg": 12.01,
    "output_voltage_ripple": 0.15,
    "efficiency": 95.3,
    "warnings": []
  }
}
```

**에러 코드**:
- `PROJECT_NOT_OPEN`: 프로젝트가 열려있지 않음
- `SIMULATION_TIMEOUT`: 시간 초과
- `SIMULATION_FAILED`: 시뮬레이션 수렴 실패 등
- `PSIM_ERROR`: PSIM 내부 에러

**사용 예시**:
```
사용자: "시뮬레이션 돌려줘. 시간은 0.1초로 해"
Claude → run_simulation(total_time=0.1)
```

---

### 3.4 `export_results`

시뮬레이션 결과를 지정된 형식으로 내보낸다.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `output_dir` | `string` | X | 출력 디렉터리. 기본값: 환경 변수 `PSIM_OUTPUT_DIR` |
| `format` | `string` | X | 출력 형식. `"json"` (기본) \| `"csv"` |
| `signals` | `list[string]` | X | 추출할 신호 이름 목록. 미지정 시 전체 |

**성공 응답 (`data`)**:
```json
{
  "exported_files": [
    {
      "path": "C:\\output\\result_001.json",
      "format": "json",
      "size_bytes": 15420
    }
  ],
  "signals_exported": ["Vout", "IL", "Isw"],
  "data_points": 10000,
  "time_range": {
    "start": 0.0,
    "end": 0.1
  }
}
```

**에러 코드**:
- `PROJECT_NOT_OPEN`: 프로젝트가 열려있지 않음
- `EXPORT_FAILED`: 결과 데이터가 없거나 내보내기 실패
- `PERMISSION_DENIED`: 출력 디렉터리 쓰기 권한 없음

**사용 예시**:
```
사용자: "결과를 CSV로 내보내줘. Vout이랑 IL만"
Claude → export_results(format="csv", signals=["Vout", "IL"])
```

---

### 3.5 `get_status`

서버 및 PSIM 연결 상태를 반환한다.

**입력 파라미터**: 없음

**성공 응답 (`data`)**:
```json
{
  "mode": "real",
  "psim_connected": true,
  "psim_version": "2025.0.1",
  "current_project": {
    "name": "buck_converter",
    "path": "C:\\projects\\buck_converter.psimsch"
  },
  "last_simulation": {
    "timestamp": "2026-03-15T14:30:00Z",
    "status": "completed",
    "duration_seconds": 4.52
  },
  "server": {
    "transport": "stdio",
    "log_level": "INFO",
    "uptime_seconds": 3600
  }
}
```

**mock 모드 응답**:
```json
{
  "mode": "mock",
  "psim_connected": false,
  "psim_version": null,
  "current_project": null,
  "last_simulation": null,
  "server": {
    "transport": "stdio",
    "log_level": "DEBUG",
    "uptime_seconds": 120
  }
}
```

---

## 4. P1 Tools (중요)

### 4.1 `sweep_parameter`

하나의 파라미터를 범위 내에서 변경하며 반복 시뮬레이션을 실행한다.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `component_id` | `string` | O | 컴포넌트 식별자 |
| `parameter_name` | `string` | O | 파라미터 이름 |
| `start` | `number` | O | 시작값 |
| `end` | `number` | O | 끝값 |
| `step` | `number` | O | 스텝 크기 |
| `metrics` | `list[string]` | X | 수집할 결과 지표 이름 |

**성공 응답 (`data`)**:
```json
{
  "parameter": "inductance",
  "range": {"start": 10e-6, "end": 100e-6, "step": 10e-6},
  "total_runs": 10,
  "completed_runs": 10,
  "results": [
    {
      "value": 10e-6,
      "metrics": {"output_ripple": 0.85, "efficiency": 93.1}
    },
    {
      "value": 20e-6,
      "metrics": {"output_ripple": 0.42, "efficiency": 94.5}
    }
  ],
  "total_duration_seconds": 45.2
}
```

**제약**:
- 최대 스텝 수: `MAX_SWEEP_STEPS` (기본 100)
- 각 시뮬레이션에 `SIMULATION_TIMEOUT` 적용

---

### 4.2 `get_project_info`

열린 프로젝트의 상세 구조 정보를 반환한다.

**입력 파라미터**: 없음

**성공 응답 (`data`)**:
```json
{
  "project_name": "buck_converter",
  "file_path": "C:\\projects\\buck_converter.psimsch",
  "components": [
    {
      "id": "V1",
      "type": "DC_Source",
      "category": "Sources",
      "parameters": {
        "voltage": {"value": 48.0, "unit": "V"}
      },
      "connections": ["node_1", "node_gnd"]
    }
  ],
  "total_components": 12,
  "total_parameters": 28,
  "simulation_settings": {
    "time_step": 1e-6,
    "total_time": 0.05,
    "print_step": 1e-5
  }
}
```

---

### 4.3 `compare_results`

두 시뮬레이션 결과를 비교한다.

> **v1.0 범위**: 결과 ID의 생성/보존 규칙은 아직 확정되지 않았으므로, 현재는 결과 파일 경로 입력만 공식 지원한다. ID 기반 조회는 추후 버전에서 정의한다.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `result_a` | `string` | O | 첫 번째 결과 파일 경로 |
| `result_b` | `string` | O | 두 번째 결과 파일 경로 |
| `signals` | `list[string]` | X | 비교할 신호 목록 |

**성공 응답 (`data`)**:
```json
{
  "comparison": [
    {
      "signal": "Vout",
      "result_a": {"avg": 12.01, "max": 12.15, "min": 11.86, "ripple": 0.29},
      "result_b": {"avg": 12.00, "max": 12.08, "min": 11.92, "ripple": 0.16},
      "diff": {"avg": -0.01, "ripple_change": "-44.8%"}
    }
  ]
}
```

---

## 5. P2 Tools (부가)

### 5.1 `add_component`

회로에 새 컴포넌트를 추가한다. PSIM Python API 기반.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | `string` | O | 컴포넌트 타입 (예: `"resistor"`, `"capacitor"`, `"mosfet"`) |
| `parameters` | `object` | O | 초기 파라미터 (키-값 쌍) |
| `position` | `object` | X | 배치 좌표 `{"x": 100, "y": 200}` |

### 5.2 `generate_netlist`

현재 프로젝트의 XML 넷리스트를 생성하고 구조를 반환한다.

**입력 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `output_path` | `string` | X | 넷리스트 저장 경로 |

### 5.3 `list_templates` / `load_template`

미리 준비된 회로 템플릿 목록을 조회하고 로드한다.

**`list_templates` 입력**: 없음
**`load_template` 입력**: `template_name: string`

---

## 6. Tool 호출 흐름 예시

### 6.1 기본 워크플로우

```
사용자: "Buck 컨버터 프로젝트 열어서 스위칭 주파수 100kHz로 바꾸고 시뮬레이션 돌려줘"

1. Claude → get_status()
   ← { success: true, data: { mode: "real", psim_connected: true, current_project: null } }

2. Claude → open_project(path="C:\\projects\\buck_converter.psimsch")
   ← { success: true, data: { components: [...], component_count: 12 } }

3. Claude → set_parameter(component_id="SW1", parameter_name="switching_frequency", value=100000)
   ← { success: true, data: { previous_value: 50000, new_value: 100000 } }

4. Claude → run_simulation()
   ← { success: true, data: { status: "completed", duration_seconds: 4.52, summary: {...} } }

5. Claude → export_results(format="json")
   ← { success: true, data: { exported_files: [...] } }

6. Claude가 결과를 자연어로 요약하여 사용자에게 전달
```

### 6.2 파라미터 스터디 워크플로우

```
사용자: "인덕턴스를 10uH~100uH까지 바꿔가면서 리플 비교해줘"

1. Claude → open_project(path="...")
2. Claude → sweep_parameter(
     component_id="L1",
     parameter_name="inductance",
     start=10e-6,
     end=100e-6,
     step=10e-6,
     metrics=["output_ripple", "efficiency"]
   )
3. Claude가 결과 테이블을 생성하여 사용자에게 전달
```

---

## 7. 버전 관리

이 API 명세는 프로젝트의 개발 진행에 따라 업데이트된다.

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| v1.0 | 2026-03-15 | 초기 작성 |
