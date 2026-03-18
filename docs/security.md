# PSIM-MCP Server: Application Security

> **버전**: v1.1
> **작성일**: 2026-03-15
> **범위**: 애플리케이션 수준의 일반 보안 (MCP 프로토콜 특화 보안은 [`security-mcp.md`](./security-mcp.md) 참조)
> **상위 문서**: [PRD.md](./PRD.md) | [architecture.md](./architecture.md)

---

## 1. 보안 개요

이 문서는 PSIM-MCP Server의 **애플리케이션 레벨 보안**을 다룬다. 파일 시스템 접근, 프로세스 실행, 입력 검증, 비밀 정보 관리, 리소스 제한 등 MCP 프로토콜과 무관하게 적용되는 보안 사항을 포함한다.

### 1.1 보안 원칙

1. **최소 권한**: 서버 프로세스는 필요한 디렉터리/리소스에만 접근
2. **입력 불신**: 모든 외부 입력은 검증 없이 신뢰하지 않음
3. **방어적 실행**: 외부 프로세스 호출 시 셸을 거치지 않음
4. **실패 안전**: 에러 시 민감 정보를 노출하지 않음
5. **감사 가능성**: 모든 주요 작업을 로깅

### 1.2 위협 요약

| 위협 | 공격 경로 | 영향도 | 대응 섹션 |
|------|-----------|--------|-----------|
| **Path Traversal** | `../../` 등으로 허용 범위 밖 파일 접근 | 높음 | §2 |
| **Command Injection** | subprocess 호출에 셸 명령 삽입 | 치명적 | §3 |
| **정보 노출** | 에러 메시지/로그에 시스템 정보 유출 | 중간 | §5 |
| **리소스 고갈 (DoS)** | 무한 시뮬레이션, 대용량 파일 생성 | 중간 | §6 |
| **비밀 정보 유출** | `.env`, 토큰, 경로가 Git에 포함 | 높음 | §5 |

---

## 2. 파일 시스템 보안

### 2.1 Path Traversal 방지

**위협**: tool 입력에 `../`, 심볼릭 링크, 또는 절대 경로를 넣어 허용 범위 밖의 파일에 접근

**대책**:

```python
# src/psim_mcp/utils/paths.py
from pathlib import Path

class PathSecurityError(Exception):
    pass

def validate_path(user_path: str, allowed_dirs: list[str], must_exist: bool = True) -> Path:
    """
    사용자 입력 경로를 검증한다.

    1. 절대 경로로 변환
    2. 심볼릭 링크 해석 (resolve)
    3. 허용된 디렉터리 내부인지 확인
    4. 존재 여부 확인 (선택)
    """
    resolved = Path(user_path).resolve()

    # 허용 디렉터리 목록이 비어있으면 검증 스킵 (개발 모드)
    if allowed_dirs:
        is_allowed = any(
            resolved.is_relative_to(Path(d).resolve())
            for d in allowed_dirs
        )
        if not is_allowed:
            raise PathSecurityError(
                f"접근이 허용되지 않은 경로입니다: {resolved}"
            )

    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {resolved}")

    return resolved


def validate_project_path(user_path: str, allowed_dirs: list[str]) -> Path:
    """프로젝트 파일 경로 전용 검증 (확장자 포함)"""
    resolved = validate_path(user_path, allowed_dirs)

    if resolved.suffix.lower() != ".psimsch":
        raise PathSecurityError(
            f"지원하지 않는 파일 형식입니다: {resolved.suffix} (*.psimsch만 허용)"
        )

    return resolved


def validate_output_dir(user_path: str, allowed_dirs: list[str]) -> Path:
    """출력 디렉터리 검증 (쓰기 권한 포함)"""
    resolved = validate_path(user_path, allowed_dirs, must_exist=False)

    resolved.mkdir(parents=True, exist_ok=True)

    import os
    if not os.access(resolved, os.W_OK):
        raise PermissionError(f"쓰기 권한이 없습니다: {resolved}")

    return resolved
```

**설정**:
```env
# .env — 쉼표 구분으로 허용 디렉터리 지정
# 비어있으면 모든 경로 허용 (개발 모드에서만 사용)
ALLOWED_PROJECT_DIRS=C:\work\psim-projects,C:\work\templates
```

### 2.2 파일 접근 규칙

| 작업 | 허용 범위 | 검증 항목 |
|------|-----------|-----------|
| 프로젝트 열기 (읽기) | `ALLOWED_PROJECT_DIRS` 내부 | 경로, 확장자, 읽기 권한 |
| 결과 내보내기 (쓰기) | `PSIM_OUTPUT_DIR` 내부 | 경로, 쓰기 권한 |
| 템플릿 로드 (읽기) | `templates/` 디렉터리 내부 | 경로, 확장자 |
| 로그 쓰기 | `LOG_DIR` 내부 | 디렉터리 존재, 쓰기 권한 |

### 2.3 심볼릭 링크 처리

- `Path.resolve()`로 심볼릭 링크를 실제 경로로 해석한 후 허용 범위를 체크
- 해석된 경로가 허용 범위 밖이면 거부

---

## 3. Subprocess 보안 (Command Injection 방지)

### 3.1 위협

RealPsimAdapter가 PSIM 번들 Python을 subprocess로 호출할 때, 사용자 입력이 셸 명령에 삽입될 수 있다.

**위험한 예**:
```python
# 절대 이렇게 하지 않는다
os.system(f"python bridge.py {user_input}")
subprocess.run(f"python bridge.py {user_input}", shell=True)
```

### 3.2 안전한 호출 패턴

```python
result = subprocess.run(
    [self.psim_python, self.bridge_script],  # 리스트로 분리
    input=json.dumps(command),               # stdin으로 데이터 전달
    capture_output=True,
    text=True,
    timeout=self.timeout,
    shell=False,                             # 명시적으로 False
    env=self._get_sanitized_env(),           # 정리된 환경 변수
)
```

### 3.3 환경 변수 정리

subprocess에 시스템 전체 환경 변수를 그대로 전달하지 않는다.

```python
def _get_sanitized_env(self) -> dict:
    """subprocess에 전달할 최소 환경 변수"""
    import os
    base_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows 필수
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
    }
    if self.config.psim_path:
        base_env["PSIM_PATH"] = str(self.config.psim_path)
    return base_env
```

### 3.4 체크리스트

- [ ] `shell=False` 사용 (기본값이지만 명시 권장)
- [ ] 사용자 입력을 명령줄 인자가 아닌 `stdin`으로 전달
- [ ] `timeout` 설정으로 무한 실행 방지
- [ ] subprocess에 전달하는 환경 변수를 최소한으로 제한
- [ ] 실행 파일 경로를 설정 파일에서 로드 (하드코딩 금지)

---

## 4. 입력 검증 (Input Validation)

### 4.1 검증 계층

```
외부 입력 (LLM 출력 또는 사용자 직접 입력)
    │
    ▼
┌────────────────────────────┐
│  스키마 검증               │  ← FastMCP 자동 (타입, 필수 파라미터)
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│  비즈니스 검증             │  ← Service Layer
│  - 경로 보안 검증           │
│  - 값 범위 검증             │
│  - 상태 검증 (프로젝트 열림) │
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│  실행 전 최종 검증          │  ← Adapter Layer
│  - PSIM 연결 상태           │
│  - 파일 실제 존재 여부       │
└────────────────────────────┘
```

### 4.2 Tool별 검증 규칙

#### `open_project`
| 파라미터 | 검증 |
|----------|------|
| `path` | 비어있지 않음, `.psimsch` 확장자, `ALLOWED_PROJECT_DIRS` 내부, 파일 존재, 읽기 권한 |

#### `set_parameter`
| 파라미터 | 검증 |
|----------|------|
| `component_id` | 영숫자+언더스코어만 허용 (`^[A-Za-z_][A-Za-z0-9_]*$`) |
| `parameter_name` | 영숫자+언더스코어만 허용 |
| `value` | 숫자 또는 문자열, 최대 길이 1024자 |

#### `run_simulation`
| 파라미터 | 검증 |
|----------|------|
| `time_step` | 양수, 최소 1e-12 |
| `total_time` | 양수, 최대 3600초 |
| `timeout` | 양수, 최대 `SIMULATION_TIMEOUT` |

#### `export_results`
| 파라미터 | 검증 |
|----------|------|
| `output_dir` | `PSIM_OUTPUT_DIR` 하위, 쓰기 권한 |
| `format` | `"json"` 또는 `"csv"`만 허용 (화이트리스트) |
| `signals` | 리스트 최대 100개, 각 이름은 영숫자+언더스코어 |

#### `sweep_parameter`
| 파라미터 | 검증 |
|----------|------|
| `start`, `end`, `step` | 숫자, `step > 0`, `(end - start) / step <= MAX_SWEEP_STEPS` |

### 4.3 Pydantic 모델을 이용한 검증

```python
# src/psim_mcp/models/schemas.py
from pydantic import BaseModel, Field, field_validator
import re

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

class SetParameterInput(BaseModel):
    component_id: str = Field(..., min_length=1, max_length=128)
    parameter_name: str = Field(..., min_length=1, max_length=128)
    value: float | str = Field(...)

    @field_validator("component_id", "parameter_name")
    @classmethod
    def must_be_safe_identifier(cls, v: str) -> str:
        if not SAFE_IDENTIFIER.match(v):
            raise ValueError(f"영문자, 숫자, 언더스코어만 허용됩니다: {v!r}")
        return v

    @field_validator("value")
    @classmethod
    def limit_string_length(cls, v):
        if isinstance(v, str) and len(v) > 1024:
            raise ValueError("값의 최대 길이는 1024자입니다")
        return v
```

---

## 5. 비밀 정보 관리 및 정보 노출 방지

### 5.1 민감 정보 분류

| 정보 | 저장 위치 | Git 포함 |
|------|-----------|----------|
| PSIM 설치 경로 | `.env` | X |
| Python 실행 파일 경로 | `.env` | X |
| 프로젝트 디렉터리 경로 | `.env` | X |
| PSIM 라이선스 정보 | PSIM 자체 관리 | X |
| API 키/토큰 (원격 배포 시) | `.env` 또는 시크릿 매니저 | X |
| 로그 파일 | `LOG_DIR` | X |
| `.env.example` (값 없는 템플릿) | 저장소 | O |

### 5.2 .gitignore 보안 항목

```gitignore
# 비밀 정보
.env
*.env.local

# 로그 (시스템 경로 포함 가능)
logs/
*.log

# 시뮬레이션 결과 (민감 데이터 포함 가능)
output/
*.smv

# PSIM 프로젝트 파일 (지적 재산)
*.psimsch

# OS/IDE
.DS_Store
__pycache__/
.vscode/
.idea/
```

### 5.3 에러 메시지 정보 노출 방지

```python
# 위험: 시스템 내부 정보가 외부로 유출
{"error": "FileNotFoundError: [Errno 2] No such file: 'C:\\Users\\john\\AppData\\...'"}

# 안전: 필요한 정보만 노출
{
    "error": {
        "code": "FILE_NOT_FOUND",
        "message": "프로젝트 파일을 찾을 수 없습니다.",
        "suggestion": "경로를 다시 확인해주세요."
    }
}
```

**원칙**:
- 에러 응답에 전체 시스템 경로를 포함하지 않음
- 스택 트레이스는 **로그에만** 기록하고 응답에는 포함하지 않음
- PSIM 내부 에러 메시지는 정리(새니타이징)하여 전달

---

## 6. 리소스 제한 (DoS 방지)

### 6.1 리소스 한도

| 리소스 | 제한 | 설정 |
|--------|------|------|
| 시뮬레이션 실행 시간 | 최대 300초 (설정 가능) | `SIMULATION_TIMEOUT` |
| 파라미터 스윕 횟수 | 최대 100회 | `MAX_SWEEP_STEPS` |
| 결과 파일 크기 | 최대 100MB | 코드 내 상수 |
| 동시 시뮬레이션 | 1개 (순차 처리) | PSIM 단일 인스턴스 제약 |
| 입력 문자열 길이 | 최대 1024자 (값), 4096자 (경로) | Pydantic 모델 |

### 6.2 타임아웃 처리

```python
async def run_simulation(self, options=None) -> dict:
    try:
        result = subprocess.run(
            [self.psim_python, self.bridge_script],
            input=json.dumps(command),
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": {
                "code": "SIMULATION_TIMEOUT",
                "message": f"시뮬레이션이 {self.timeout}초 내에 완료되지 않아 중단되었습니다.",
                "suggestion": "SIMULATION_TIMEOUT 값을 늘리거나 시뮬레이션 설정을 확인해주세요."
            }
        }
```

---

## 7. 감사 로깅 (Audit Logging)

### 7.1 기록 항목

```json
{
  "timestamp": "2026-03-15T14:30:00.123Z",
  "event_type": "tool_call",
  "tool": "open_project",
  "input_hash": "sha256:abc123...",
  "path_accessed": "/projects/buck_converter.psimsch",
  "path_allowed": true,
  "result": "success",
  "duration_ms": 245
}
```

### 7.2 보안 이벤트 유형

| 이벤트 | 로그 레벨 | 설명 |
|--------|-----------|------|
| `path_blocked` | WARNING | 허용 범위 밖의 경로 접근 시도 |
| `invalid_input` | WARNING | 검증 실패한 입력값 |
| `subprocess_timeout` | WARNING | PSIM 프로세스 타임아웃 |
| `subprocess_error` | ERROR | PSIM 프로세스 비정상 종료 |
| `tool_call` | INFO | 정상 tool 호출 |

### 7.3 로그 보호

- 로그 파일은 `.gitignore`에 포함
- 로그에 사용자 입력 원본을 저장할 때는 해시 또는 truncation 적용
- 로그 디렉터리의 파일 권한을 서버 프로세스 사용자만 읽기/쓰기 가능하게 설정
- 로그 로테이션 설정 권장 (일별 또는 크기 기반)

---

## 8. 보안 체크리스트

### 개발 시

- [ ] 모든 파일 경로 입력에 `validate_path()` 적용
- [ ] subprocess 호출 시 `shell=False` 확인
- [ ] 사용자 입력을 stdin으로 전달 (명령줄 인자에 넣지 않음)
- [ ] Pydantic 모델로 모든 tool 입력 검증
- [ ] 에러 응답에 시스템 내부 경로를 노출하지 않음
- [ ] `.env` 파일이 `.gitignore`에 포함되어 있음
- [ ] 로그에 민감 정보가 평문으로 기록되지 않음

### 배포 전

- [ ] `ALLOWED_PROJECT_DIRS` 설정 (빈 값이 아닌 구체적 경로)
- [ ] `SIMULATION_TIMEOUT`과 `MAX_SWEEP_STEPS` 적정값 설정
- [ ] 로그 디렉터리 권한 확인
- [ ] `.env.example`에 민감 정보가 포함되지 않음 확인
- [ ] 의존성 패키지 보안 취약점 스캔 (`pip audit` 또는 `safety check`)

---

## 부록: OWASP Top 10 매핑

| OWASP (2021) | 관련성 | 대응 |
|--------------|--------|------|
| A01: Broken Access Control | 높음 | Path traversal 방지, 허용 디렉터리 제한 (§2) |
| A03: Injection | 높음 | Command injection 방지 (§3), 입력 검증 (§4) |
| A04: Insecure Design | 중간 | Adapter 분리, 최소 권한 (§1.1) |
| A05: Security Misconfiguration | 중간 | `.env.example` 제공, 기본값 안전 설정 (§5) |
| A06: Vulnerable Components | 낮음 | 의존성 최소화, 정기 업데이트 |
| A09: Logging Failures | 중간 | 구조화된 감사 로그 (§7) |
