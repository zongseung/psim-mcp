# PSIM-MCP v1.1.1 구현 상태 점검

> 작성일: 2026-03-15
> 기준: 현재 `src/psim_mcp` 코드 + `uv run pytest -q`
> 목적: `docs/ver1.1.1` 계획 대비 실제 구현 상태를 완료 / 부분 완료 / 미완료로 정리

---

## 0. 요약

현재 기준으로 `ver1.1.1` 계획은 상당 부분 코드로 반영되어 있다.

재확인 결과:

- 테스트: `249 passed`
- 문서의 큰 방향: 대부분 코드에 반영됨
- 핵심 미완료: `CircuitSpec -> nets -> wire_plan -> bridge -> Windows real`의 마지막 구간

즉 현재 상태는:

- 골격과 보조 계층은 많이 구현됨
- service / tool 레벨에서는 `CircuitSpec`과 `nets`를 일부 수용하기 시작함
- 그러나 bridge와 Windows real 검증은 아직 legacy `connections` 중심이 남아 있음

---

## 1. 완료된 항목

### 1.1 CircuitSpec 모델 추가

상태:

- [x] 완료

확인 내용:

- `CircuitSpec`, `ComponentSpec`, `NetSpec`, `SimulationSettings`가 정의되어 있다
- `from_legacy()` / `to_legacy()` 변환도 구현되어 있다

파일:

- `src/psim_mcp/models/circuit_spec.py`

---

### 1.2 Generator 패키지 추가

상태:

- [x] 완료

확인 내용:

- generator registry가 존재한다
- `buck`, `boost`, `buck_boost` generator가 등록되어 있다
- 관련 테스트가 존재한다

파일:

- `src/psim_mcp/generators/__init__.py`
- `src/psim_mcp/generators/buck.py`
- `src/psim_mcp/generators/boost.py`
- `src/psim_mcp/generators/buck_boost.py`
- `tests/unit/test_generators.py`

---

### 1.3 Preview token 기반 상태 저장

상태:

- [x] 완료

확인 내용:

- 전역 `_pending_preview` 대신 `PreviewStore`가 도입되었다
- token 저장 / 조회 / 삭제 / TTL 만료 테스트가 있다
- `preview_circuit`이 `preview_token`을 반환하고 `confirm_circuit`이 이를 사용한다

파일:

- `src/psim_mcp/services/preview_store.py`
- `src/psim_mcp/tools/circuit.py`
- `tests/unit/test_preview_store.py`

---

### 1.4 Validation 계층 추가

상태:

- [x] 완료

확인 내용:

- `validators` 패키지가 존재한다
- structural / electrical / parameter validator가 분리되어 있다
- 통합 진입점 `validate_circuit()`가 있다
- 기본 validator 테스트가 존재한다

파일:

- `src/psim_mcp/validators/__init__.py`
- `src/psim_mcp/validators/structural.py`
- `src/psim_mcp/validators/electrical.py`
- `src/psim_mcp/validators/parameter.py`
- `tests/unit/test_circuit_validators.py`

---

### 1.5 자연어 parser 및 design tool 추가

상태:

- [x] 완료

확인 내용:

- `parse_circuit_intent()`가 존재한다
- topology 키워드 / use-case / unit extraction 경로가 있다
- `design_circuit` tool이 등록되어 있다

파일:

- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/parsers/unit_parser.py`
- `src/psim_mcp/parsers/keyword_map.py`
- `src/psim_mcp/tools/design.py`
- `src/psim_mcp/server.py`

---

## 2. 부분 완료 항목

### 2.1 Component Catalog 정비

상태:

- [~] 부분 완료

확인 내용:

- 핀 정의, 기본 파라미터, helper 함수는 추가되었다
- 하지만 `psim_element_type`은 아직 비어 있다
- 즉 catalog는 구조는 생겼지만 Windows real mapping은 미완이다

파일:

- `src/psim_mcp/data/component_library.py`

남은 작업:

- `Save as Python Code` 기준 실제 PSIM element type 채우기
- bridge에서 `kind -> psim_element_type` 변환 실제 사용

---

### 2.2 preview/create에서 generator 우선 사용

상태:

- [~] 부분 완료

확인 내용:

- `preview_circuit`와 `create_circuit`이 generator를 먼저 시도한다
- generator가 없으면 템플릿 fallback을 사용한다
- `preview_circuit`은 generator 결과의 `nets`를 preview store에 함께 저장한다
- `confirm_circuit`은 저장된 `nets`가 있으면 `nets_to_connections()`로 변환해 생성 경로에 전달한다

파일:

- `src/psim_mcp/tools/circuit.py`
- `src/psim_mcp/bridge/wiring.py`

남은 작업:

- generator 결과의 `nets`를 adapter/bridge까지 1급 입력으로 유지
- 현재는 `nets -> legacy connections` 변환을 거친다

---

### 2.3 Circuit validation의 service 연결

상태:

- [~] 부분 완료

확인 내용:

- `SimulationService.create_circuit()`에서 validation을 호출한다
- `circuit_spec` 인자를 받을 수 있게 확장되었다
- `circuit_spec["nets"]`가 있으면 `_nets_to_connections(...)`로 연결 변환 후 adapter에 전달한다

파일:

- `src/psim_mcp/services/simulation_service.py`

남은 작업:

- adapter/base 계약도 `CircuitSpec` 중심으로 맞춰야 한다
- bridge까지 `nets` 또는 `wire_plan`을 직접 받는 구조는 아직 아니다

---

### 2.4 Bridge wiring 모듈 추가

상태:

- [~] 부분 완료

확인 내용:

- `nets_to_wire_plan()`과 `resolve_pin_position()`가 별도 파일로 분리되었다
- `nets_to_connections()` helper가 추가되어 현재 tool/service 경로에서 사용된다

파일:

- `src/psim_mcp/bridge/wiring.py`

남은 작업:

- `wire_plan` 자체는 아직 bridge 실행 경로에서 사용되지 않는다
- 좌표 계산과 pin offset은 아직 Windows 확인이 필요하다

---

### 2.5 design_circuit의 자연어 흐름

상태:

- [~] 부분 완료

확인 내용:

- topology 판단
- 누락 필드 질문 생성
- template/generator 추천
- high/medium confidence일 때 자동 preview 생성
- `preview_token`을 반환해 `confirm_circuit`으로 바로 이어질 수 있다

까지는 구현되어 있다.

파일:

- `src/psim_mcp/tools/design.py`

남은 작업:

- 별도 tool-level integration 검증이 더 필요하다
- generator 실패/preview 렌더링 예외에 대한 회귀 테스트가 부족하다

---

## 3. 아직 미완료인 핵심 항목

### 3.1 CircuitSpec 중심 end-to-end 실행 경로

상태:

- [~] 부분 완료

현재 문제:

- service는 이제 `circuit_spec` 인자를 받을 수 있다
- tool 계층도 generator 결과의 `nets`를 저장하고 변환에 사용한다
- 하지만 실제 생성 경로는 여전히 최종적으로 `components + connections` 중심이다
- generator의 `nets`가 `wire_plan` 또는 bridge native 입력으로 전달되지는 않는다

영향:

- 문서에서 목표로 한 `CircuitSpec -> validator -> wire_plan -> bridge` 구조가 절반 정도 연결된 상태다

핵심 파일:

- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/tools/circuit.py`
- `src/psim_mcp/adapters/base.py`

---

### 3.2 Bridge의 pin-aware wiring

상태:

- [ ] 미완료

현재 문제:

- bridge는 여전히 `connections`를 순회한다
- `from_pin`, `to_pin`에서 component id만 사실상 사용한다
- 실제 핀 이름 기반 연결이나 `wire_plan` 실행 경로는 아직 없다

파일:

- `src/psim_mcp/bridge/bridge_script.py`

영향:

- 다핀 소자에서 배선 정확성이 보장되지 않는다

---

### 3.3 kind -> psim_element_type 매핑 적용

상태:

- [ ] 미완료

현재 문제:

- catalog에 `psim_element_type` 필드는 있지만 아직 값이 비어 있다
- bridge도 아직 `comp["type"]`를 그대로 `PsimCreateNewElement()`에 넘긴다

파일:

- `src/psim_mcp/data/component_library.py`
- `src/psim_mcp/bridge/bridge_script.py`

---

### 3.4 Windows smoke test 실구현

상태:

- [ ] 미완료

현재 문제:

- smoke test 파일은 있지만 TODO 상태다
- 실제 Buck 생성 / 검증 / 시뮬레이션 확인 코드가 아직 없다

파일:

- `tests/smoke/test_create_buck.py`

---

## 4. 현재 상태 판단

현재 구현은 다음 수준으로 보는 것이 맞다.

- `ver1.1.1` 계획의 기반 구조: 많이 구현됨
- token store / generator / validator / parser: 사용 가능한 수준
- Windows real / wire_plan / CircuitSpec end-to-end: 아직 미완료

즉 현재 단계는:

> "설계 문서를 따라 구조를 올리고 있는 중간 단계"

로 보는 것이 가장 정확하다.

---

## 5. 다음 우선순위

가장 먼저 닫아야 할 순서는 아래가 맞다.

1. `SimulationService.create_circuit()`를 `CircuitSpec` 중심으로 바꾸기
2. generator의 `nets`를 `wire_plan`으로 변환하는 경로 연결
3. bridge에서 pin-aware wiring 구현
4. `psim_element_type` 실제 값 채우기
5. Windows smoke test 실구현

---

## 6. 결론

현재 코드베이스는 문서상 계획을 많이 따라왔고, 테스트 수도 `249 passed`까지 올라왔다.

다만 아직 "문서에 적은 최종 구조가 완전히 구현됐다"고 보기는 어렵다.
이전보다 진전된 점은 service/tool 레벨에서 `CircuitSpec`과 `nets`를 일부 수용하기 시작했다는 것이다.
가장 큰 남은 이유는 실제 bridge와 Windows real 경로가 여전히 legacy `components + connections` 중심이기 때문이다.

따라서 현재 상태를 한 줄로 정리하면 다음과 같다.

> 기반 구조는 많이 완성됐고, 남은 핵심은 `CircuitSpec / wire_plan / Windows real`의 마지막 실행 구간을 끝까지 연결하는 것이다.
