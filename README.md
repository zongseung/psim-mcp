# psim-mcp

Claude Desktop에서 **기존 PSIM 회로를 읽고 이해하고 동적으로 수정·시뮬레이션**하는 MCP 서버.

**12개 Tool** | **기존 회로의 넷 재구성** | **파라미터 수정과 시뮬레이션 분석**

```
기존 .psimsch → import_circuit (소자 + 넷 + 파라미터 복원)
              → 회로 이해
              → set_parameter (열린 파일에 영속)
              → run_simulation → analyze_existing
```

## 주 워크플로 (VER2)

`import_circuit`는 PSIM의 `PsimConvertToPython` 출력을 파싱하고 union-find로 전기적 넷을 재구성합니다. 기존 회로를 열고, 구조를 확인하고, 파라미터를 수정한 뒤 시뮬레이션 결과를 분석하는 것이 제품의 흐름입니다.

주의: `set_parameter`는 **현재 열린 프로젝트 파일에 저장**됩니다. 원본을 보존하려면 사본에서 작업하세요.

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
| Altair PSIM 2026 | 선택 | 실제 회로 시뮬레이션 |
| Python 3.8/3.9 | 선택 | PSIM 브리지용 |

## Claude Desktop 설정

`claude_desktop_config.json`을 편집합니다.

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
      "env": {"PSIM_MODE": "mock"}
    }
  }
}
```

Claude Desktop을 완전히 종료한 뒤 다시 시작하면 12개 도구가 표시됩니다.

## 사용법

```
C:\circuits\my_boost.psimsch를 가져와서 구조를 설명해줘.
인덕터를 250uH로 바꾸고 다시 시뮬레이션해서 리플을 비교해줘.
```

`analyze_simulation`이 타임아웃되면 `run_simulation(simview=false)` 후 `analyze_existing`로 결과만 분석할 수 있습니다.

## MCP 도구 (12개)

| 도구 | 설명 |
|------|------|
| `open_project` | 기존 `.psimsch` 파일 열기 |
| `get_project_info` | 프로젝트 구조 조회 |
| `import_circuit` | 기존 회로의 소자·전기적 넷·파라미터·시뮬레이션 설정 복원 |
| `set_parameter` | 컴포넌트 파라미터 변경 (열린 파일에 영속) |
| `sweep_parameter` | 파라미터 스윕 시뮬레이션 |
| `run_simulation` | 시뮬레이션 실행 |
| `export_results` | 결과 내보내기 (JSON/CSV) |
| `compare_results` | 시뮬레이션 결과 비교 |
| `get_status` | 서버/PSIM 상태 확인 |
| `analyze_simulation` | 시뮬레이션 실행 후 토폴로지별 분석과 파형 PNG 생성 |
| `analyze_existing` | 기존 `.smv` 결과 파일 분석 |
| `optimize_circuit` | 회로 파라미터 자동 최적화 |

## VER2 Import Pipeline

```
기존 .psimsch
  → bridge: PsimConvertToPython
  → importer/parser.py
  → importer/net_builder.py (T-분기, 라벨, ground를 포함한 넷 재구성)
  → CircuitGraph (components + nets)
  → import_circuit 응답 → set_parameter / run_simulation / analysis
  → importer/roundtrip.py emit_script → PSIM 재생성
```

## 설정

환경 변수 또는 `.env` 파일을 사용합니다.

| 변수 | 기본값 | 설명 |
|------|------|------|
| `PSIM_MODE` | `mock` | `mock` 또는 `real` |
| `PSIM_PATH` | — | PSIM 설치 경로 (real 모드 필수) |
| `PSIM_PYTHON_EXE` | — | PSIM Python 실행 파일 경로 |
| `PSIM_OUTPUT_DIR` | — | 시뮬레이션 결과 디렉터리 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `SIMULATION_TIMEOUT` | `300` | 시뮬레이션 타임아웃 (초) |

## 개발

```bash
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

모든 Python 작업은 `uv run`을 사용합니다.

## 설계 문서

`docs/ver2/schematic-import-netlist-reconstruction-PRD.md`에 기존 회로 읽기·넷 재구성·동적 수정의 상세가 있습니다.

## 보안

- `Path.resolve()`와 `is_relative_to()`로 경로 이탈을 방지합니다.
- Pydantic 제약과 시뮬레이션 옵션 범위 검증을 사용합니다.
- bridge subprocess는 `shell=False`와 JSON stdin으로 실행합니다.
- 감사 로그는 SHA-256 입력 해싱과 분리된 서버·PSIM·보안·도구 로그를 사용합니다.

## 라이선스

MIT
