# 11. Non-Hardcoding Risks Review

> 작성일: 2026-03-15
> 기준: 현재 `src/psim_mcp` 코드 + `uv run pytest -q` (`249 passed`)
> 목적: 하드코딩 외에 자연어 기반 회로 설계/생성 흐름에서 문제가 될 수 있는 구조 리스크를 정리

---

## 1. 요약

현재 코드는 parser, generator, preview, validator, service, bridge가 모두 존재한다.

하지만 가장 큰 남은 리스크는 하드코딩 자체보다:

- 회로 표현 데이터 계약이 계층마다 다르고
- preview와 실제 생성이 같은 표현을 보지 않으며
- validator도 `connections`와 `nets`를 혼용하고
- bridge는 여전히 legacy `connections` 중심이라는 점이다.

즉 지금 문제의 핵심은:

- "설계 지능이 부족하다"보다
- "같은 회로를 각 계층이 서로 다른 구조로 이해한다"에 더 가깝다.

---

## 2. 주요 리스크

### 2.1 `nets` 데이터 계약 불일치

현재 상태:

- generator는 `{"id": ..., "connections": [...]}` 형태의 net을 반환한다.
- `wiring.py`의 `nets_to_wire_plan()` / `nets_to_connections()`는 `{"name": ..., "pins": [...]}` 형태를 기대한다.

영향:

- generator 기반 preview/confirm/create 경로에서 net 변환이 일관되게 동작하지 않을 수 있다.
- 일부 경로에서는 net 정보가 사실상 무시될 수 있다.

관련 파일:

- `src/psim_mcp/generators/buck.py`
- `src/psim_mcp/generators/boost.py`
- `src/psim_mcp/generators/buck_boost.py`
- `src/psim_mcp/bridge/wiring.py`
- `src/psim_mcp/tools/circuit.py`

우선 조치:

- `NetSpec`의 canonical shape를 하나로 고정
- generator / validator / preview / bridge 전부 그 구조만 사용

### 2.2 preview와 실제 생성 경로의 표현 차이

현재 상태:

- `preview_circuit()`은 validator에 `nets`를 전달한다.
- 하지만 ASCII/SVG 렌더링은 `connections`만 사용한다.
- generator 경로에서는 `resolved_connections = []`인 경우가 존재한다.

영향:

- 검증은 통과했는데 미리보기 선이 비어 있거나 부정확할 수 있다.
- 사용자가 본 preview와 실제 confirm/create 결과가 다를 수 있다.

관련 파일:

- `src/psim_mcp/tools/circuit.py`
- `src/psim_mcp/utils/ascii_renderer.py`
- `src/psim_mcp/utils/svg_renderer.py`

우선 조치:

- preview 렌더러도 canonical `nets` 또는 canonical `wire_plan` 기준으로 렌더링
- preview와 confirm이 동일한 회로 표현을 공유하도록 강제

### 2.3 validator 입력 계약 분리

현재 상태:

- structural validator는 `connections`를 본다.
- electrical validator는 `nets`를 본다.
- service validation은 `nets` 중심으로 호출된다.

영향:

- 어떤 경로에서는 structural 오류가 빠지고
- 어떤 경로에서는 electrical 오류만 잡히는 식의 불균형이 생길 수 있다.

관련 파일:

- `src/psim_mcp/validators/structural.py`
- `src/psim_mcp/validators/electrical.py`
- `src/psim_mcp/services/simulation_service.py`

우선 조치:

- validator 입력도 하나의 canonical schema로 통일
- validator 내부에서 필요한 파생 표현을 생성하도록 변경

### 2.4 parser / metadata / generator 간 schema 불일치

현재 상태:

- parser는 `iout`, `fsw`, `r_load`를 생성한다.
- metadata는 `load_resistance`, `switching_frequency`, `output_frequency` 등을 사용한다.
- generator는 다시 `vin`, `vout_target`, `iout`, `fsw`를 기대한다.

영향:

- 자연어에서 값 추출은 됐지만 generator나 질문 로직으로 온전히 전달되지 않을 수 있다.
- confidence, missing_fields, 질문 생성이 실제 설계 필요값과 어긋날 수 있다.

관련 파일:

- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/data/topology_metadata.py`
- `src/psim_mcp/generators/*.py`

우선 조치:

- canonical field schema 정의
- alias는 parser 입구에서만 허용하고 내부 계층은 canonical key만 사용

### 2.5 generator 실패가 조용히 숨겨짐

현재 상태:

- `design_circuit()`에서 generator 예외가 나면 template fallback으로 조용히 내려간다.

영향:

- 사용자는 "자동 설계"라고 이해하지만 실제로는 정적 템플릿일 수 있다.
- 실패 원인이 드러나지 않아 회귀나 설계 품질 저하를 숨길 수 있다.

관련 파일:

- `src/psim_mcp/tools/design.py`

우선 조치:

- fallback 시 `generation_mode = generator | template_fallback` 같은 메타데이터를 응답에 포함
- generator 예외를 debug 정보나 warning으로 노출

### 2.6 preview token store의 운영 제약

현재 상태:

- preview store는 in-memory singleton이다.
- 프로세스 재시작이나 멀티 인스턴스 환경을 고려하지 않는다.

영향:

- token 기반 confirm 흐름이 프로세스 경계에서 깨질 수 있다.
- 로컬 단일 프로세스 데모에는 괜찮지만 구조적으로는 제한적이다.

관련 파일:

- `src/psim_mcp/services/preview_store.py`

우선 조치:

- 현재 범위에서는 "single-process only" 제약을 문서화
- 추후에는 file/db-backed preview store 검토

### 2.7 topology metadata의 required fields가 느슨한 구간

현재 상태:

- 일부 inverter/drive 계열은 `vin`만 필수다.

영향:

- 실제로는 출력 주파수, 부하, 전력 레벨이 중요한데도 너무 쉽게 high/medium confidence로 갈 수 있다.
- 자연어를 "알아먹었다"는 것과 "설계 가능한 상태"를 혼동하게 만든다.

관련 파일:

- `src/psim_mcp/data/topology_metadata.py`

우선 조치:

- topology별 `minimum_preview_fields`와 `minimum_design_fields`를 분리
- candidate 제시와 실제 생성 허용 기준을 나눔

### 2.8 Windows real mode에서만 드러날 수 있는 통합 리스크

현재 상태:

- 단위 테스트는 모두 통과한다.
- 하지만 end-to-end에서는 `parser -> preview -> confirm -> service -> bridge -> PSIM` 전체 계약이 동일하게 검증되지 않았다.

영향:

- 로컬 테스트는 통과해도 Windows real mode에서 데이터 shape mismatch가 드러날 수 있다.

우선 조치:

- `design_circuit -> confirm_circuit -> create_circuit` 흐름을 real-mode smoke test로 추가
- generator net shape와 bridge 입력 shape를 통합 테스트에서 직접 검증

---

## 3. 우선순위

### P0

1. `nets` canonical schema 통일
2. preview/confirm/service/bridge가 같은 회로 표현 사용
3. validator 입력 계약 통일

### P1

4. parser/metadata/generator field schema 통일
5. generator fallback이 발생했는지 사용자에게 명시
6. topology별 생성 허용 기준 정교화

### P2

7. preview store persistence 전략 검토
8. Windows real-mode end-to-end smoke test 확장

---

## 4. 완료 기준

- [x] `NetSpec` shape가 generator, validator, preview, bridge에서 동일하다 (canonical: `{"name", "pins"}`)
- [x] preview와 confirm이 동일한 회로 표현을 사용한다 (nets→connections 자동 변환)
- [x] validator가 canonical schema 하나만 입력으로 받는다 (entry에서 nets→connections 정규화)
- [x] parser/metadata/generator의 내부 field key가 통일된다 (FIELD_ALIASES + normalized_specs)
- [x] template fallback 여부가 응답에 드러난다 (generation_mode: generator/template/template_fallback)
- [x] topology별 생성 허용 기준이 명확해진다 (design_ready_fields 분리)
- [x] preview store single-process 제약 문서화
- [ ] real-mode smoke test가 design flow까지 덮는다 (Windows 필요)
