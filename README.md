# psim-mcp

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

## 제품 범위

Claude Desktop에서 기존 PSIM 회로를 열고, 구조와 결과를 분석하고, 필요한 파라미터를 수정한 뒤 시뮬레이션할 수 있는 MCP 서버입니다. 새 회로를 생성하는 도구는 제공하지 않습니다.

## 기존 회로 워크플로

1. `open_project`로 기존 `.psimsch` 파일을 엽니다.
2. `get_project_info` 또는 `import_circuit`로 회로 구조를 확인합니다.
3. 필요하면 `set_parameter` 또는 `sweep_parameter`를 사용합니다.
4. `run_simulation`을 실행하고 `analyze_simulation`, `analyze_existing`, `export_results`로 결과를 확인합니다.

`set_parameter`는 원본 프로젝트 파일에 변경 사항을 저장합니다. 작업 전에는 원본을 복사해 두세요.

## 기능 및 제한

12개 도구 중 안정적으로 사용할 수 있는 도구는 `open_project`, `get_project_info`, `import_circuit`, `run_simulation`, `export_results`, `get_status`, `analyze_simulation`, `analyze_existing`입니다.

`sweep_parameter`는 고정 반복 방식의 실험적 기능입니다. `compare_results`는 P1 스텁이며, `optimize_circuit`도 실험적 기능입니다. 최적화에 필요한 Optuna는 기본 설치에 포함되지 않습니다.

## 요구 사항

| 항목 | 필수 | 비고 |
| --- | --- | --- |
| Python 3.12+ | 예 | MCP 서버 |
| [uv](https://docs.astral.sh/uv/) | 예 | 패키지 관리 |
| Claude Desktop | 선택 | MCP 클라이언트 |
| Altair PSIM 2026 | real 모드에서 예 | 실제 시뮬레이션 |
| PSIM Python 3.9 | real 모드에서 예 | PSIM 브리지 |

## 설치

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync --all-extras
```

## real 모드 빠른 시작

`.env.example`을 `.env`로 복사한 뒤 설치 경로를 설정합니다. `.env`는 Git에서 무시되므로 저장소에 추가하지 마세요.

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<사용자>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
```

`ALLOWED_PROJECT_DIRS`를 생략하면 validator가 허용하는 모든 절대 프로젝트 경로를 사용할 수 있습니다. 제한하려면 절대 경로를 쉼표로 구분해 설정하세요.

## Claude Desktop 설정

`claude_desktop_config.json`에 다음을 추가합니다.

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "psim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\psim-mcp", "psim-mcp"],
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2026",
        "PSIM_PYTHON_EXE": "C:\\Users\\<사용자>\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
        "PSIM_OUTPUT_DIR": "./output"
      }
    }
  }
}
```

설정을 바꾼 뒤 Claude Desktop을 완전히 종료한 후 다시 시작하세요.

## 12개 도구 참고

| 도구 | 설명 |
| --- | --- |
| `open_project` | 기존 프로젝트 열기 |
| `get_project_info` | 프로젝트 구조 조회 |
| `import_circuit` | 기존 회로 가져오기 |
| `set_parameter` | 컴포넌트 파라미터 변경 및 원본 저장 |
| `sweep_parameter` | 파라미터 스윕(실험적 고정 반복) |
| `run_simulation` | 시뮬레이션 실행 |
| `export_results` | 결과를 JSON 또는 CSV로 내보내기 |
| `compare_results` | 결과 비교(P1 스텁) |
| `get_status` | 서버와 PSIM 상태 확인 |
| `analyze_simulation` | 시뮬레이션 실행 및 결과 분석 |
| `analyze_existing` | 기존 `.smv` 결과 분석 |
| `optimize_circuit` | 회로 파라미터 최적화(실험적, Optuna 별도 설치 필요) |

## 환경 변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock` 또는 `real` |
| `PSIM_PATH` | 없음 | real 모드의 PSIM 설치 경로 |
| `PSIM_PYTHON_EXE` | 없음 | PSIM Python 3.9 실행 파일 |
| `PSIM_OUTPUT_DIR` | 없음 | real 모드에서 필요한 시뮬레이션 결과 디렉터리 |
| `LOG_DIR` | `./logs` | 로그 디렉터리 |
| `LOG_LEVEL` | `INFO` | 로그 수준 |
| `SERVER_TRANSPORT` | `stdio` | `stdio` 또는 `sse` |
| `SERVER_HOST` | `127.0.0.1` | SSE 서버 호스트 |
| `SERVER_PORT` | `8000` | SSE 서버 포트 |
| `SIMULATION_TIMEOUT` | `300` | 시뮬레이션 제한 시간(초) |
| `MAX_SWEEP_STEPS` | `100` | 스윕 최대 단계 수 |
| `ALLOWED_PROJECT_DIRS` | 생략 | 허용할 절대 프로젝트 경로 목록; 생략 시 validator 허용 경로 모두 사용 |

## 안전

- 신뢰할 수 있는 프로젝트 파일만 여세요.
- `set_parameter`는 원본 파일을 변경하므로 백업본에서 작업하세요.
- `ALLOWED_PROJECT_DIRS`로 프로젝트 경로 범위를 제한할 수 있습니다.

## 개발

```bash
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

## 라이선스

MIT
