# PSIM-MCP Refactor Plan

> 작성일: 2026-03-15
> 목적: 현재 구현을 전면 재작성하지 않고, 유지보수성과 MCP 실운영 안정성을 높이기 위한 단계별 리팩터링 계획 정리

---

## 1. 결론

현재 코드는 전면 리팩터링이 필요한 상태는 아니다.  
다만 다음 이유로 **국소적이지만 구조적인 리팩터링**은 필요하다.

- `server.py`가 전역 초기화와 wiring 책임을 모두 가짐
- tool 레이어에 반복 코드가 많음
- `SimulationService`에 검증, 감사 로깅, 포맷팅, orchestration 책임이 집중됨
- real mode는 adapter 계약이 아직 완전히 닫히지 않음

따라서 방향은 **“작게 나누어 정리하는 리팩터링”** 이 맞다.

---

## 2. 리팩터링 목표

이번 리팩터링의 목표는 다음 5가지다.

1. 서버 초기화 과정을 명시적인 앱 팩토리 구조로 바꾸기
2. tool 등록/응답 처리의 중복 제거
3. service 레이어 책임 축소
4. real mode 계약을 명시적으로 고정
5. 테스트를 service 중심에서 tool/startup 경로까지 확장

비목표:

- 전체 기능 재설계
- 프레임워크 교체
- 문서 전체 재작성
- P1/P2 기능 확장 우선 개발

---

## 3. 우선순위

### P0: 바로 손대야 하는 리팩터링

- `server.py` 앱 팩토리화
- tool 공통 wrapper 도입
- real mode bridge 경로/계약 정리

### P1: 다음 단계에서 해야 하는 리팩터링

- `SimulationService` 책임 분리
- adapter 상태 계약 표준화
- startup validation 정교화

### P2: 여유 있을 때 정리해도 되는 항목

- 루트 `main.py` 정리
- logger / audit utility 인터페이스 다듬기
- schema와 service 응답 관계 정리

---

## 4. 단계별 계획

### Phase 1. 서버 초기화 구조 정리

대상 파일:

- `src/psim_mcp/server.py`
- `src/psim_mcp/config.py`

현재 문제:

- import 시점에 config, adapter, service, tool 등록이 모두 실행된다
- 테스트나 확장 시 전역 상태 의존성이 커진다
- 여러 인스턴스를 만들기 어렵다

목표 구조:

```python
def create_app(config: AppConfig | None = None) -> FastMCP:
    ...
    return mcp

def create_service(config: AppConfig) -> SimulationService:
    ...

def create_adapter(config: AppConfig) -> BasePsimAdapter:
    ...
```

권장 작업:

1. `AppConfig()` 생성을 `main()` 또는 `create_app()` 내부로 이동
2. adapter 생성 로직을 별도 팩토리 함수로 분리
3. tool 등록도 `register_all_tools(mcp, service)` 함수로 묶기
4. `mcp._psim_service` 같은 사설 속성 의존은 제거 방향으로 정리

완료 기준:

- `import psim_mcp.server`만으로 무거운 초기화가 일어나지 않음
- 테스트에서 독립적인 app/service 인스턴스 생성 가능
- startup validation과 logging 초기화 위치가 명확해짐

---

### Phase 2. Tool 레이어 공통화

대상 파일:

- `src/psim_mcp/tools/project.py`
- `src/psim_mcp/tools/parameter.py`
- `src/psim_mcp/tools/simulation.py`
- `src/psim_mcp/tools/results.py`
- `src/psim_mcp/tools/__init__.py`

현재 문제:

- 모든 tool이 거의 같은 패턴을 반복한다
- service 호출
- `json.dumps`
- sanitize/truncate
- 예외 처리
- logger 호출

이 반복은 유지보수 리스크를 높인다.

권장 방향:

```python
async def run_tool(handler, *args, **kwargs) -> str:
    result = await handler(*args, **kwargs)
    return encode_tool_response(result)

def encode_tool_response(payload: dict) -> str:
    ...
```

또는 decorator 형태:

```python
def tool_response_wrapper(tool_name: str):
    ...
```

권장 작업:

1. 공통 직렬화 함수 추출
2. 공통 내부 오류 응답 포맷 고정
3. 공통 sanitize/truncate 처리 함수 추출
4. logger 호출 패턴 표준화

완료 기준:

- 각 tool 함수는 “입력 -> service 호출” 중심으로 짧아짐
- 예외 응답 계약이 모든 tool에서 동일함
- 새 tool 추가 시 boilerplate 복제가 크게 줄어듦

---

### Phase 3. SimulationService 책임 분리

대상 파일:

- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/services/validators.py`
- `src/psim_mcp/utils/logging.py`

현재 문제:

- `SimulationService`가 다음을 모두 처리한다
- 입력 검증
- path/security 감사
- adapter orchestration
- 성공/실패 응답 포맷팅
- fallback 규칙
- tool 호출 audit logging

이 구조는 기능이 늘수록 비대해진다.

권장 분리:

1. `ResponseBuilder` 또는 formatter 유틸
2. `AuditService` 또는 얇은 감사 logger wrapper
3. export/simulation/project 관련 세부 로직 helper 분리

예시 방향:

```python
class ServiceResponseBuilder:
    def success(...)
    def error(...)

class AuditRecorder:
    def tool_call(...)
    def invalid_input(...)
```

권장 작업:

1. `_format_success`, `_format_error`를 공용 builder로 이동
2. audit 호출을 공용 helper 또는 context manager로 정리
3. `open_project`, `set_parameter`, `run_simulation`, `export_results` 공통 패턴 단순화

완료 기준:

- `SimulationService`는 orchestration 중심으로 남음
- 응답 포맷과 audit 코드가 재사용 가능해짐
- 메서드당 길이와 분기 수가 줄어듦

---

### Phase 4. Adapter 계약 정리

대상 파일:

- `src/psim_mcp/adapters/base.py`
- `src/psim_mcp/adapters/mock_adapter.py`
- `src/psim_mcp/adapters/real_adapter.py`
- `src/psim_mcp/bridge/`

현재 문제:

- real mode 경로는 아직 bridge script 부재로 미완성
- adapter 상태 확인 방식이 최근에 개선됐지만, interface 수준 고정이 필요함
- bridge 위치, 실행 계약, 오류 매핑이 명확히 문서화/구현되어 있지 않음

권장 작업:

1. `BasePsimAdapter`에 `is_project_open` 계약을 명시적으로 선언
2. `RealPsimAdapter`의 bridge path 계산을 패키지 기준으로 고정
3. `src/psim_mcp/bridge/bridge_script.py` 실제 구현 추가
4. bridge 응답 규약 정의:
   - 성공 응답 형식
   - 실패 응답 형식
   - stderr 처리 원칙
5. adapter 예외를 service 에러 코드와 매핑하기 쉬운 형태로 정리

완료 기준:

- mock/real adapter가 같은 추상 계약을 만족
- real mode smoke test가 가능
- bridge script 위치가 설정값에 과도하게 의존하지 않음

---

### Phase 5. 진입점/보조 파일 정리

대상 파일:

- `main.py`
- `README.md`
- `pyproject.toml`

현재 문제:

- 루트 `main.py`는 현재 패키지 구조와 무관한 스텁이다
- 실제 엔트리포인트와 중복되어 혼란을 만든다

권장 작업:

1. `main.py` 제거 또는 `psim_mcp.server:main`을 호출하는 얇은 래퍼로 변경
2. README 실행 방법을 실제 구조에 맞게 고정
3. `pyproject.toml`의 script entry와 README를 일치시킴

완료 기준:

- 진입점이 하나의 흐름으로 이해됨
- 사용자/운영자가 어떤 파일로 실행해야 하는지 헷갈리지 않음

---

## 5. 파일별 권장 분류

### 지금 리팩터링해야 함

- `src/psim_mcp/server.py`
- `src/psim_mcp/tools/project.py`
- `src/psim_mcp/tools/parameter.py`
- `src/psim_mcp/tools/results.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/adapters/real_adapter.py`

### 계약 고정 후 정리하면 됨

- `src/psim_mcp/config.py`
- `src/psim_mcp/utils/logging.py`
- `src/psim_mcp/services/validators.py`
- `src/psim_mcp/models/schemas.py`

### 당장 건드릴 필요 낮음

- `src/psim_mcp/adapters/mock_adapter.py`
- `src/psim_mcp/utils/paths.py`
- 테스트 fixture 기본 구조

### 정리 대상이지만 우선순위 낮음

- `main.py`

---

## 6. 테스트 보강 계획

리팩터링과 함께 반드시 추가해야 할 테스트:

1. app factory 생성 테스트
2. tool 함수 직접 호출 테스트
3. `output_dir=None` fallback 테스트
4. `sweep_parameter` metric 추출 테스트
5. `compare_results` 응답 envelope 테스트
6. `real` 모드 설정값 누락 시 startup validation 실패 테스트
7. bridge script 존재/미존재 smoke test

추가 원칙:

- service 테스트만으로 충분하다고 가정하지 말 것
- tool 레이어 계약 테스트를 별도 축으로 유지할 것
- startup 경로와 real mode 경로는 최소 smoke test라도 둘 것

---

## 7. 추천 작업 순서

가장 현실적인 실행 순서:

1. `server.py` 앱 팩토리화
2. tool 공통 wrapper 도입
3. `SimulationService` 응답/audit 분리
4. adapter 계약 정리 및 bridge 실제 구현
5. 루트 진입점 정리
6. 테스트 보강

이 순서를 권장하는 이유:

- 앞 단계가 뒤 단계의 중복 작업을 줄여준다
- tool/service/adapter 경계를 먼저 고정해야 real mode 구현도 깔끔해진다

---

## 8. 예상 효과

이 계획대로 정리하면 다음 효과를 기대할 수 있다.

- MCP tool 추가 속도 향상
- 오류 응답 계약 안정화
- 테스트의 신뢰도 상승
- real mode 디버깅 용이성 개선
- 전역 상태 의존성 감소
- 코드 읽기 난이도 하락

---

## 9. 결론

현재 코드는 “망가진 구조”는 아니다.  
하지만 기능을 더 올리기 전에 한 번 구조를 정리해두지 않으면, 다음 단계에서 빠르게 복잡도가 올라갈 가능성이 높다.

따라서 권장 전략은 다음과 같다.

- 전면 재작성하지 않는다
- 기능 추가보다 구조 경계 정리를 먼저 한다
- `server -> tools -> service -> adapter` 경계를 명시적으로 고정한다

즉, 지금 필요한 것은 대수술이 아니라 **경계 정리 중심의 계획적 리팩터링**이다.
