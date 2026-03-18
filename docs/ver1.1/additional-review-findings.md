# PSIM-MCP Additional Review Findings

> 작성일: 2026-03-15
> 범위: `docs/ver2/implementation-review.md`에 기록한 4개 항목 외 추가 점검 결과
> 목적: 현재 구현에서 남아 있는 계약 불일치와 운영 리스크를 별도 정리

---

## 0. 재확인 상태

> 재확인 기준: 현재 코드 재검토 + `uv run pytest -q`

- [x] 서버 시작 시 `setup_logging()` 호출되도록 수정됨
- [x] `real` 모드 필수 설정값 검증 추가됨
- [x] adapter의 `is_project_open` 계약이 추가됨
- [x] `compare_results` 응답이 `data` envelope 형식으로 정리됨
- [x] tool 공통 내부 오류 응답 formatter가 도입됨

---

## 1. 요약

이 문서의 본문은 최초 추가 점검 시점의 발견 사항을 기록한 것이다.  
현재 재확인 결과는 상단 `재확인 상태`를 기준으로 보는 것이 맞다.

최초 추가 점검 시점에는 다음 문제가 확인되었다.

- 로깅 유틸리티가 구현되어 있지만 서버 시작 시 실제로 초기화되지 않음
- `real` 모드에서 필수 설정값이 없어도 서버가 그대로 올라감
- non-mock adapter에서는 “프로젝트 미오픈” 상태를 service가 올바르게 판별하지 못함
- `compare_results`는 현재 표준 응답 계약을 따르지 않는 임시 응답을 반환함

이 항목들은 모두 테스트 통과 여부와 별개로, 실제 MCP 연결이나 운영 환경에서 문제를 만들 수 있다.

---

## 2. 추가 발견 사항

### 2.1 High: 로깅 설정 함수가 존재하지만 서버에서 호출되지 않음

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/utils/logging.py`
- `src/psim_mcp/server.py`

초기 문제:

- `setup_logging()`은 `server.log`, `tools.log`, `psim.log`, `security.log`를 구성하도록 구현되어 있었다.
- 하지만 `server.py`에서는 이 함수를 호출하지 않았다.

재확인 결과:

- `server.main()`에서 `setup_logging(config.log_dir, config.log_level)`를 호출하도록 수정됨

남은 사항:

- import 시점이 아니라 실행 시점 초기화라는 점은 오히려 현재 구조상 적절함

---

### 2.2 High: `real` 모드 필수 설정값이 없어도 AppConfig가 통과함

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/config.py`
- `src/psim_mcp/server.py`

초기 문제:

- `AppConfig(psim_mode="real")` 생성 시 `psim_path`, `psim_python_exe`, `psim_project_dir`, `psim_output_dir`가 모두 `None`이어도 검증 오류가 발생하지 않았다.
- 서버는 이 설정으로도 그대로 `RealPsimAdapter`를 생성했다.

재확인 결과:

- `AppConfig.validate_real_mode()`가 추가됨
- `server.py`에서 startup 시 해당 검증을 호출함

남은 사항:

- bridge script/PSIM API 실환경 검증은 별도 통합 테스트로 남음

---

### 2.3 Medium: non-mock adapter에서는 프로젝트 미오픈 상태를 잘못 판별함

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/services/simulation_service.py`

초기 문제:

- `_is_project_open`은 adapter가 `_current_project` 속성을 가지면 그 값을 보고, 그렇지 않으면 무조건 `True`를 반환했다.
- 따라서 `RealPsimAdapter` 같은 non-mock adapter에서는 실제로 프로젝트가 열리지 않았어도 service가 열린 것으로 간주했다.

재확인 결과:

- `BasePsimAdapter`에 `is_project_open` 계약이 추가됨
- `MockPsimAdapter`, `RealPsimAdapter`가 이를 구현함
- `SimulationService._is_project_open`은 이제 `self._adapter.is_project_open`을 사용함

남은 사항:

- real adapter가 실제 PSIM 세션 종료/리셋까지 정확히 반영하는지는 실환경 검증 필요

---

### 2.4 Medium: `compare_results`는 현재 표준 응답 envelope를 따르지 않음

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/tools/results.py`

초기 문제:

- service에 `compare_results`가 없으면 tool이 임시 stub 응답을 직접 만들었다.
- 이 응답은 `{success, result_a, result_b, signals, message}` 형태이며, 다른 tool이 사용하는 `{success, data, message}` 계약과 달랐다.

재확인 결과:

- 현재 stub 응답도 `{success, data, message}` 형식으로 정리됨

남은 사항:

- 아직 실제 비교 로직은 stub 수준이므로 기능 완성은 별도 과제임

---

### 2.5 Medium: tool 레이어의 직접 예외 응답 형식이 service 응답과 다름

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/tools/project.py`
- `src/psim_mcp/tools/parameter.py`
- `src/psim_mcp/tools/simulation.py`
- `src/psim_mcp/tools/results.py`

초기 문제:

- service는 `{success: false, error: {code, message, suggestion}}` 형식을 사용했다.
- 하지만 tool 함수의 `except` 블록은 대부분 `{success: false, error: str(exc)}` 형식으로 직접 반환했다.

재확인 결과:

- `psim_mcp.tools.format_tool_error()` 공통 formatter가 도입됨
- tool들이 공통 내부 오류 envelope를 사용하도록 변경됨

남은 사항:

- 공통 formatter가 `suggestion`까지 포함하도록 확장할지는 추후 결정 가능

---

## 3. 종합 판단

이전 문서의 4개 이슈와 이번 추가 항목을 합치면, 현재 코드의 핵심 문제는 아래 두 축으로 정리된다.

- real mode와 운영 환경을 고려한 초기화/설정 검증이 아직 약함
- service와 tool 사이의 응답 계약, 상태 판별 계약이 완전히 고정되지 않음

즉, 현재 구조는 방향은 맞지만, MCP 클라이언트가 안정적으로 붙기 위해 필요한 “운영 가능한 계약”은 아직 다 닫히지 않았다.

---

## 4. 추가 우선순위

이전 문서의 우선순위 다음으로는 아래 순서를 권장한다.

1. 서버 시작 시 로깅 초기화 연결
2. `real` 모드 설정 검증 추가
3. 프로젝트 열림 상태 판별 방식 정리
4. `compare_results`와 tool-level error envelope 통일

---

## 5. 결론

추가 검토 결과, 현재 구현은 “mock 기반 개발 골격”으로는 충분히 의미가 있다.  
하지만 실제 MCP 연결과 real mode 운영을 기준으로 보면 아직 초기화, 설정 검증, 응답 계약 일관성에서 보완이 더 필요하다.

따라서 다음 단계는 기능 추가보다, **startup 검증과 공통 응답/에러 계약 고정**에 우선순위를 두는 것이 맞다.
