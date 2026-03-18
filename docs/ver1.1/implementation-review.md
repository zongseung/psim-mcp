# PSIM-MCP Implementation Review

> 작성일: 2026-03-15
> 범위: 현재 `src/psim_mcp` 구현 기준 점검
> 목적: 실제 MCP 연결 전, 현재 코드 구성의 동작 리스크와 수정 우선순위 정리

---

## 0. 재확인 상태

> 재확인 기준: 현재 코드 재검토 + `uv run pytest -q`

- [x] `get_project_info` tool 오류 수정됨
- [x] `export_results(output_dir=None)` fallback 수정됨
- [x] `sweep_parameter` metric 추출 수정됨
- [x] bridge script 파일 추가 및 패키지 내부 경로 고정됨
- [ ] real mode end-to-end smoke test 여부는 문서/테스트 기준으로 아직 명확하지 않음

---

## 1. 요약

현재 저장소는 문서상의 아키텍처와 유사한 골격을 갖추고 있으며, mock 기반 서비스/validator 단위 테스트는 통과한다.

이 문서의 본문은 최초 점검 시점의 발견 사항을 기록한 것이다.  
현재 재확인 결과는 상단 `재확인 상태`를 기준으로 보는 것이 맞다.

검증 결과:

- 최초 점검 시점: `120 passed`
- 재확인 시점: `190 passed`

---

## 2. 주요 발견 사항

### 2.1 Critical: real mode bridge가 실제로 연결되지 않음

상태:

- [x] **부분 해결됨**

파일:

- `src/psim_mcp/adapters/real_adapter.py`
- `src/psim_mcp/bridge/`

초기 문제:

- `RealPsimAdapter`는 `bridge_script.py`를 subprocess로 실행하도록 되어 있었다.
- 하지만 당시 저장소에는 bridge script 구현이 없고 `src/psim_mcp/bridge/__init__.py`만 존재했다.
- 따라서 real mode에서는 adapter 호출이 즉시 실패했다.

현재 코드:

- 패키지 내부의 `src/psim_mcp/bridge/bridge_script.py`를 고정 경로로 사용
- startup 시 bridge script 존재 여부를 검증

재확인 결과:

- `src/psim_mcp/bridge/bridge_script.py`가 실제로 추가됨
- `RealPsimAdapter`가 패키지 내부 bridge 경로를 사용하도록 변경됨

남은 사항:

- 실제 Windows + PSIM 환경에서의 end-to-end smoke test는 별도 확인이 필요함

권장 조치:

1. Windows 실환경 smoke test 추가
2. bridge script의 실제 PSIM API 호환성 검증
3. real mode 통합 테스트 보강

---

### 2.2 High: `get_project_info` tool이 현재 코드로는 실패함

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/tools/project.py`

초기 문제:

- `get_project_info()`가 `svc.adapter.get_project_info()`를 호출했다.
- 하지만 `SimulationService`는 `adapter` 공개 속성을 제공하지 않고 내부 `_adapter`만 가졌다.

재확인 결과:

- tool이 `svc.get_project_info()`를 호출하도록 변경됨
- `SimulationService.get_project_info()`가 추가됨
- 현재는 정상 응답 경로가 연결되어 있음

남은 사항:

- tool 직접 호출 테스트는 더 보강할 여지가 있음

---

### 2.3 High: `export_results(output_dir=None)` 경로가 잘못 처리됨

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/tools/results.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/adapters/mock_adapter.py`

초기 문제:

- tool에서는 `output_dir`를 optional로 받는다.
- 하지만 service는 `None`일 때 `config.psim_output_dir`로 대체하지 않고 그대로 adapter에 넘겼다.
- mock adapter는 이를 문자열 보간해 `None/results.json` 같은 잘못된 경로를 생성했다.

재확인 결과:

- service가 `output_dir is None`일 때 `config.psim_output_dir`로 fallback 하도록 수정됨
- 기본 출력 디렉터리가 없을 경우 명시적 에러를 반환하도록 보완됨
- 재현 시 더 이상 `None/results.json` 경로가 생성되지 않음

남은 사항:

- 이 fallback 경로에 대한 명시적 테스트는 더 추가해두는 편이 안전함

---

### 2.4 Medium: `sweep_parameter`가 metric을 잘못 읽어 항상 `null`을 반환함

상태:

- [x] **해결됨**

파일:

- `src/psim_mcp/tools/parameter.py`

초기 문제:

- `svc.run_simulation()`은 `{success, data, message}` 형식의 응답을 반환한다.
- 그런데 `sweep_parameter`는 `sim_result.get("summary", {})`를 읽고 있었다.
- 실제 summary는 `sim_result["data"]["summary"]` 아래에 있으므로 metric 추출이 실패했다.

재확인 결과:

- `sweep_parameter`가 `sim_result["data"]["summary"]` 구조를 읽도록 수정됨
- 재실행 시 `metrics`에 실제 값이 채워지는 것을 확인함

남은 사항:

- 실패 응답이 중간 단계에서 나올 때 sweep 전체 정책은 여전히 명확히 정리할 필요가 있음

---

## 3. 테스트 상태 해석

현재 테스트는 많이 작성되어 있고 service/validator 기준으로는 좋은 출발점이다.

하지만 아래 경로는 충분히 검증되지 않았다.

- MCP tool 함수 자체 호출
- real mode adapter 경로
- bridge script 존재 여부 및 subprocess 왕복
- 기본값 fallback 동작 (`output_dir=None`)
- sweep 결과 구조

즉, **테스트가 모두 통과하는 상태와 실제 MCP 동작 가능 상태는 아직 동일하지 않다**.

---

## 4. 현재 상태 판단

현 시점 판단:

- mock 기반 내부 로직: 대체로 진행 가능
- MCP tool 완성도: 일부 보완 필요
- real mode/Windows 연동: 아직 미완성

따라서 이 프로젝트는 현재 **프로토타입 중간 단계**로 보는 것이 맞다.

---

## 5. 우선 수정 순서

권장 순서:

1. `get_project_info` tool 오류 수정
2. `export_results` 기본 출력 디렉터리 fallback 정리
3. `sweep_parameter` metric 추출 구조 수정
4. bridge script 실제 구현 및 real mode smoke test 추가
5. tool 레이어 직접 호출 테스트 추가

---

## 6. 결론

현재 구조 자체는 크게 잘못되지 않았다.  
다만 “테스트는 통과하지만 실제 MCP 경로에서는 깨지는 부분”이 남아 있다.

가장 중요한 포인트는 다음 두 가지다.

- real mode는 아직 구현 완료 상태가 아니다
- tool 레이어 검증이 부족해서 service 레이어와의 계약 불일치가 남아 있다

따라서 다음 단계는 리팩토링보다, **tool/service 계약 정리와 real bridge 구현 완성**이 우선이다.
