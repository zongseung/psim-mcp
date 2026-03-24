# Phase 1~4 보완 TODO

작성일: 2026-03-24

관련 문서:

- `docs/2026-03-24-phase-1-4-implementation-gap-review.md`
- `docs/ver5/phase-1-file-impact-and-interface-draft.md`
- `docs/ver5/phase-2-circuit-graph-design.md`
- `docs/ver5/phase-3-layout-engine-design.md`
- `docs/ver5/phase-4-advanced-routing-design.md`

## 목적

이 문서는 현재 구현된 Phase 1~4를 `preview 중심 부분 구현`에서
`confirm/create/backend까지 이어지는 실제 canonical pipeline`으로 마무리하기 위한 실행 TODO다.

핵심 목표는 새 모델을 더 만드는 것이 아니라,
이미 있는 `graph/layout/routing`을 실제 런타임 source of truth로 승격하는 것이다.

## 최우선 목표

1. `confirm_circuit()`가 preview payload의 `graph/layout/routing`을 실제로 읽는다.
2. `create_circuit_direct()`도 preview 경로와 같은 synthesis pipeline을 사용한다.
3. `buck`만 연결된 service 경로를 `flyback`, `llc`까지 확장한다.
4. `svg_renderer`와 bridge가 가능한 한 재추론 없이 canonical geometry를 소비하게 만든다.

## PR 순서

1. PR-1. payload contract 고정 및 compat adapter
2. PR-2. confirm/create를 graph-first로 전환
3. PR-3. flyback/llc service 활성화
4. PR-4. renderer consumer화
5. PR-5. bridge/simulation contract 정리
6. PR-6. validator 및 session schema 보강

## PR-1. payload contract 고정 및 compat adapter

목표:

- preview/session payload를 문서와 코드에서 같은 계약으로 고정
- legacy payload도 읽을 수 있게 compat adapter 추가

수정 대상:

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/shared/state_store.py`
- 필요 시 `src/psim_mcp/shared/protocols.py` 또는 새 schema 파일

작업:

- preview payload loader 함수 추가
- session payload loader 함수 추가
- `payload_kind`, `payload_version` 없는 경우 legacy로 처리
- `preview_payload_v1`과 `design_session_v1/v2`를 코드 상수로 고정
- `_build_need_specs_response()` 경로에도 session version 저장 일관화

체크리스트:

- `confirm_circuit()`가 payload version을 검사한다
- `continue_design()`가 versioned session payload를 읽는다
- preview/session 저장 경로가 모두 동일한 kind/version 규칙을 쓴다

합격 기준:

- payload version 없는 기존 테스트 fixture도 읽힌다
- 새 preview/session 저장값이 모두 version field를 가진다

## PR-2. confirm/create를 graph-first로 전환

목표:

- preview에서 저장한 `graph/layout/routing`이 confirm/create의 실제 source가 되게 만들기

수정 대상:

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/layout/materialize.py`
- 필요 시 `src/psim_mcp/synthesis/__init__.py`

작업:

- `confirm_circuit()`에서 저장된 `graph/layout/routing` 우선 사용
- `layout -> legacy materialization` 재실행 경로와 fallback 경로 분리
- `routing`이 있으면 `to_legacy_segments()`를 사용
- `create_circuit_direct()`에도 `_try_synthesize_and_layout()` 경로 연결
- preview 경로와 create 경로의 topology 처리 순서를 맞춤

체크리스트:

- `confirm_circuit()`가 `preview["graph"]`, `preview["layout"]`, `preview["routing"]`를 읽는다
- `create_circuit_direct()`가 specs 기반 synthesis path를 먼저 시도한다
- graph/layout/routing 없는 topology는 legacy fallback을 탄다

합격 기준:

- buck confirm/create가 같은 synthesis path를 공유한다
- preview 결과와 create 입력 geometry가 불필요하게 다시 계산되지 않는다

## PR-3. flyback/llc service 활성화

목표:

- 현재 모델/전략만 존재하는 `flyback`, `llc`를 service에 실제 연결

수정 대상:

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/synthesis/topologies/__init__.py`
- 필요 시 topology metadata/constraints 테스트

작업:

- `_SYNTHESIZERS`에 `synthesize_flyback`, `synthesize_llc` 등록
- preview/create에서 두 topology의 synthesis -> layout -> routing 경로 활성화
- fallback 테스트를 phase4 기준 active-path 테스트로 전환

체크리스트:

- `preview_circuit("flyback", specs=...)`가 graph/layout를 저장한다
- `preview_circuit("llc", specs=...)`가 graph/layout/routing을 저장한다
- topology별 capability matrix를 문서와 코드에서 일치시킨다

합격 기준:

- service 레벨에서 `buck`, `flyback`, `llc` 모두 new path 동작
- 기존 template/custom path 회귀 없음

## PR-4. renderer consumer화

목표:

- `svg_renderer.py`가 layout/routing consumer가 되게 축소

수정 대상:

- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/services/circuit_design_service.py`
- 필요 시 `src/psim_mcp/routing/anchors.py`

작업:

- 새 renderer entry 추가
  - 예: `render_circuit_svg_from_layout(...)`
- `components + routing` 또는 `layout + routing + renderable metadata` 기반 렌더링 경로 추가
- `_PIN_ANCHOR_MAP` 의존 축소
- hub/junction 재계산 로직을 routing 결과 소비 형태로 교체

체크리스트:

- preview가 routing payload가 있으면 consumer path를 사용한다
- renderer가 junction를 자체 추론하지 않고 routing junction를 우선 사용한다
- legacy render 함수는 fallback으로 유지한다

합격 기준:

- buck/flyback/llc preview가 stored routing 기반으로 그려진다
- layout/routing 존재 시 renderer 내부 geometry 재추론이 최소화된다

## PR-5. bridge/simulation contract 정리

목표:

- bridge와 simulation이 canonical geometry와 어떤 관계인지 명확히 고정

수정 대상:

- `src/psim_mcp/bridge/bridge_script.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/services/circuit_design_service.py`

작업:

- bridge main path가 `connections` 재구성이 아니라 canonical geometry 소비 방향으로 갈 수 있는지 분리
- 당장 direct `WireRouting` 소비가 어렵다면
  - service에서 `routing -> legacy wire_segments` 변환을 표준화
  - bridge는 그 geometry만 소비
- `SimulationService.create_circuit()`의 legacy-only 범위를 capability matrix와 코드 주석에 동일하게 반영

체크리스트:

- bridge path가 어떤 geometry source를 쓰는지 단일 경로로 문서화
- simulation/create가 topology별로 new path 또는 legacy-only인지 명시
- preview/create 간 geometry mismatch 발생 지점을 줄인다

합격 기준:

- 최소한 buck 경로에서는 preview/create geometry source가 일관된다
- legacy-only topology는 코드와 문서에서 동일하게 표시된다

## PR-6. validator 및 session schema 보강

목표:

- graph/session contract를 문서 수준에 맞게 강화

수정 대상:

- `src/psim_mcp/validators/graph.py`
- `src/psim_mcp/services/circuit_design_service.py`
- 필요 시 `src/psim_mcp/intent/models.py`

작업:

- graph validator에 아래 추가
  - duplicate net id
  - required role completeness
  - required block completeness
  - orphan component/net
  - block membership consistency
- session payload schema 정리
  - `payload_kind`
  - `payload_version`
  - `candidate_scores`
  - `decision_trace`
  - `resolution_version`

체크리스트:

- graph validator가 topology completeness를 최소한 일부 검증한다
- design session 생성 경로가 모두 같은 schema를 사용한다
- action contract는 그대로 유지된다

합격 기준:

- `confirm_intent`, `need_specs`, `suggest_candidates`, `design_session_token` 계약 유지
- session payload 혼합 저장 문제가 사라진다

## 파일별 바로 할 일

### `src/psim_mcp/services/circuit_design_service.py`

- preview payload loader 추가
- session payload loader 추가
- `_SYNTHESIZERS`에 flyback/llc 연결
- `confirm_circuit()`의 graph/layout/routing 우선 소비
- `create_circuit_direct()`를 synth-layout-routing 경로에 연결
- preview/create 경로의 generation mode/capability 분기 정리

### `src/psim_mcp/services/simulation_service.py`

- legacy-only boundary를 코드/테스트/문서에서 고정
- 향후 direct payload consumption 전환 전까지 허용 범위 명시

### `src/psim_mcp/utils/svg_renderer.py`

- consumer API 추가
- routing/junction 재추론 축소
- legacy path는 fallback 유지

### `src/psim_mcp/bridge/bridge_script.py`

- geometry source를 일관화
- connection 기반 재추론과 canonical geometry 소비 경계 분리

### `src/psim_mcp/validators/graph.py`

- topology completeness 검사 보강

### `src/psim_mcp/layout/strategies/*.py`

- `preferences` 실제 반영
- fallback position 처리 개선
- hardcoded coordinate table 의존을 단계적으로 줄일 계획 세우기

## 테스트 TODO

## 서비스 테스트

- `tests/unit/test_circuit_design_service_phase3.py`
  - confirm이 stored layout를 읽는지 검증 추가
- `tests/unit/test_circuit_design_service_phase4.py`
  - confirm/create가 stored routing를 읽는지 검증 추가
- flyback/llc가 fallback이 아니라 active path인지 검증 추가

## renderer 테스트

- layout/routing consumer path snapshot test 추가
- junction 재추론 없이 routing junction를 쓰는지 검증

## bridge/simulation 테스트

- buck create path geometry source 일치 검증
- legacy-only topology capability test 추가

## validator 테스트

- duplicate net id
- orphan component/net
- required block/role 누락

## 추천 실행 순서

1. PR-1 먼저
2. PR-2로 confirm/create 전환
3. PR-3로 flyback/llc 활성화
4. PR-4와 PR-5로 renderer/bridge/backend 정리
5. PR-6로 validator/session 마무리

## 완료 정의

아래를 만족하면 Phase 1~4 보완이 끝난 것으로 본다.

- preview payload의 `graph/layout/routing`이 단순 저장값이 아니라 confirm/create의 실제 source다
- `buck`, `flyback`, `llc`가 서비스 레벨에서 같은 canonical path를 탄다
- renderer와 bridge가 불필요한 geometry 재추론을 줄인다
- simulation/create의 legacy-only 예외가 문서와 코드에서 일치한다
- design session과 preview payload의 version contract가 일관된다
