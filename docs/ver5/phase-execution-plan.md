# Phase 실행 계획서
작성일: 2026-03-24

## 목적

이 문서는 `ver5`의 `개발 기획서 + 아키텍처 설계 패키지`를
실제 구현 가능한 실행 계획으로 내리기 위한 문서다.

핵심 목적은 다음이다.

- 각 phase의 착수 조건을 고정
- 각 phase의 산출물과 acceptance 기준을 명확히 정의
- 실패 시 fallback / rollback 기준을 정의
- 실제 작업을 PR 단위로 분해

즉 이 문서는 `설계 문서`가 아니라,
실제 개발 진행과 리뷰, 병합, 회귀 대응에 쓰는 실행 기준 문서다.

## 공통 원칙

모든 phase는 아래 원칙을 따른다.

1. public API와 사용자 visible behavior는 가능한 한 단계적으로 바꾼다
2. 새 경로를 붙일 때는 legacy path를 즉시 삭제하지 않는다
3. preview와 actual generation의 geometry mismatch를 늘리면 안 된다
4. 각 phase는 최소 1개 topology를 기준 implementation으로 삼는다
5. `buck -> flyback -> llc` 순으로 복잡도를 올린다
6. 저수준 drawing primitive 확장보다 canonical payload 완성도를 우선한다

## 공통 실행 설계 원칙

이 프로젝트는 일반 CAD 도면 자동화와 달리
저수준 draw command 조합이 아니라 canonical synthesis pipeline을 중심으로 개발한다.

따라서 phase별 작업에서도 아래를 우선한다.

- MCP/tool surface는 고수준 capability 중심으로 유지
- 내부 구현은 `spec -> graph -> layout -> routing` 계층을 따라감
- backend는 교체 가능하지만 tool contract는 쉽게 바꾸지 않음
- renderer/bridge는 추론보다 canonical payload 소비를 우선함

## 공통 release gate

모든 phase에서 병합 전 확인해야 하는 공통 항목:

- 관련 단위 테스트 통과
- 기존 핵심 preview topology 회귀 없음
- preview/create 경로가 최소 1개 기준 topology에서 유지
- 새 canonical intermediate가 preview store 또는 내부 pipeline에 저장됨
- 명시된 fallback path가 실제로 동작함

## 공통 계약 명시

실행 계획 문서 기준으로 아래 계약은 별도 acceptance 대상으로 간주한다.

### 1. preview/store payload 계약

- preview token payload는 phase 전환 중에도 버전 필드를 가져야 한다
- 최소 필드:
  - `payload_kind`
  - `payload_version`
  - `circuit_type`
  - `components`
  - `connections`
  - `nets`
  - `wire_segments`
  - optional `canonical_spec`
  - optional `synthesis_result`
  - optional `graph`
  - optional `layout`
  - optional `routing`
  - optional `psim_template`
- 권장 버전명:
  - `preview_payload_v1`
  - `design_session_v1`
- confirm/create 경로는 저장된 payload 버전을 보고 하위 호환 복구가 가능해야 한다

### 2. 서비스 엔트리포인트 계약

phase 전환은 topology 기준만이 아니라 실제 엔트리포인트 기준으로 추적해야 한다.

- `design_circuit()`
- `continue_design()`
- `preview_circuit()` generator path
- `preview_circuit()` template path
- `preview_circuit()` custom components path
- `confirm_circuit()`
- `create_circuit_direct()`
- `SimulationService.create_circuit()`

각 phase의 완료 판단에는 적어도 위 엔트리포인트 중 영향 범위와 fallback 대상이 문서화되어야 한다.

### 3. feature flag 계약

문서상 feature flag는 개념 수준이 아니라 실제 설정 키 수준으로 내려와야 한다.

- `PSIM_SYNTHESIS_ENABLED_TOPOLOGIES`
- `PSIM_GRAPH_ENABLED_TOPOLOGIES`
- `PSIM_LAYOUT_ENGINE_ENABLED_TOPOLOGIES`
- `PSIM_ROUTING_ENABLED_TOPOLOGIES`
- `PSIM_INTENT_PIPELINE_V2`

초기 구현에서는 env/config 기반으로 시작해도 되지만,
기본값과 topology 단위 on/off 규칙이 phase 착수 전에 고정돼야 한다.

## 공통 지원 매트릭스 기준

지원 매트릭스는 topology별 상태만 적지 말고, 엔트리포인트별 상태도 같이 기록해야 한다.

권장 최소 표:

| topology | design_circuit | preview(generator) | preview(template) | confirm | create_direct | simulation_service.create | synthesize | graph | layout | routing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| buck | legacy/new/mixed | legacy/new/mixed | yes/no | legacy/new/mixed | legacy/new/mixed | legacy/new/mixed | yes/no | yes/no | yes/no | yes/no |
| flyback | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

## 공통 fallback 원칙

각 phase에서 새 경로가 실패하면 아래 우선순위로 fallback한다.

1. topology 단위 fallback
- 새 구조 미지원 topology만 legacy path 사용

2. 기능 단위 fallback
- graph는 유지하고 layout/routing만 legacy adapter 사용

3. phase 단위 fallback
- 새 phase feature flag를 꺼서 이전 안정 경로로 복귀

## 공통 rollback 원칙

다음 경우에는 phase 수준 rollback을 검토한다.

- preview와 actual generation mismatch 증가
- 기준 topology 2개 이상에서 create 실패
- public tool 응답 shape가 호환성 없이 깨짐
- 회귀 테스트가 안정적으로 복구되지 않음

권장 방식:

- destructive revert보다 feature-flag rollback 우선
- 새 모델 저장은 유지하되 실행 경로만 legacy로 되돌리기

## Phase 1 실행 계획

## 목표

- generator에서 `structure + sizing + layout` 결합을 풀기
- `synthesize()` 경로 도입
- legacy generator path와 공존 가능한 adapter 만들기

## 선행 조건

- 현재 generator/preview/create 경로가 기본 동작하는 상태
- `buck` topology를 기준 implementation으로 선정
- `CircuitDesignService`와 `SimulationService`가 현재 create 경로를 어떻게 소비하는지 기준선 확보
- preview/store payload에 버전 필드를 도입할 최소 설계 확정

## 산출물

- `TopologyGenerator.synthesize()` 도입
- `TopologySynthesisResult` 도입
- `synthesis/models.py`
- `synthesis/sizing.py`
- `synthesis/topologies/buck.py`
- `legacy_layout_adapter`
- `preview_payload_v1` 저장 규약
- `design_session_v1` 저장 규약

## Acceptance

- `buck`이 synthesize 경로로 structure-only 합성 가능
- 기존 preview/create가 계속 동작
- preview store에 synthesis intermediate 저장
- generator 본체에서 `buck` 기준 좌표 직접 생성이 빠짐
- 관련 단위 테스트 추가 및 통과
- `confirm_circuit()`와 `create_circuit_direct()`가 저장된 payload로 계속 동작
- `SimulationService.create_circuit()`가 phase 1 payload와 충돌하지 않음

## 정량 기준

- `buck` preview 생성 성공률 100%
- `buck` create path 성공
- `buck` 관련 테스트 전부 통과
- 기존 `buck` preview 대비 구조적 component/net count 동일
- preview payload version mismatch에 대한 하위 호환 실패 0건

## Fallback

- `buck`만 new synthesize path 사용
- 나머지 topology는 전부 legacy `generate()` 유지
- `SimulationService.create_circuit()`는 phase 1 동안 legacy circuit_spec 입력 유지

## Rollback 기준

- `buck` preview/create 중 하나라도 안정적으로 깨질 경우
- service 응답 shape 변경으로 기존 도구 연동이 깨질 경우
- preview token payload 변경으로 confirm/create가 깨질 경우

## PR 단위

PR 1. `synthesis` 기본 모델 도입
- `synthesis/models.py`
- `generators/base.py`

PR 2. `buck` sizing / structure 분리
- `synthesis/sizing.py`
- `synthesis/topologies/buck.py`
- `generators/buck.py`

PR 3. legacy adapter + service 연결
- `synthesis/legacy_layout_adapter.py`
- `services/circuit_design_service.py`
- `shared/state_store.py`

PR 4. tests / docs 정리
- unit tests
- preview store assertions
- `services/simulation_service.py` 영향 범위 정리

## Phase 2 실행 계획

## 목표

- `CircuitGraph`를 canonical source로 도입
- graph validator 도입
- service를 graph 중심 흐름으로 전환

## 선행 조건

- Phase 1의 synthesize 경로 존재
- 최소 `buck`이 structure-only synthesis 가능

## 산출물

- `CircuitGraph`, `GraphComponent`, `GraphNet`, `FunctionalBlock`
- graph validator
- graph builder helper
- preview store graph 저장
- graph 포함 `preview_payload_v1` 확장

## Acceptance

- `buck` preview/create가 graph를 canonical source로 사용
- graph validation 실패가 명시적 오류로 노출
- legacy renderable은 graph에서 projection됨
- `flyback`, `llc`에 최소 role/block 모델 설계 시작
- `SimulationService.create_circuit()`가 graph 포함 payload를 허용하거나 명시적으로 legacy-only로 고정됨

## 정량 기준

- `buck` graph validation pass
- graph -> legacy renderable projection 테스트 통과
- graph가 preview token payload에 포함됨

## Fallback

- graph 저장은 유지하되 rendering은 legacy projection 사용
- graph 미지원 topology는 legacy path 유지

## Rollback 기준

- graph projection이 legacy renderable과 구조적으로 불일치
- graph validation false positive가 과도하게 발생

## PR 단위

PR 1. graph 모델 / builder / validator 추가
- `synthesis/models.py`
- `synthesis/graph_builders.py`
- `validators/graph.py`

PR 2. `buck` graph synthesize 완성
- `synthesis/topologies/buck.py`

PR 3. service graph 저장 및 projection 연결
- `services/circuit_design_service.py`
- `services/simulation_service.py`
- `shared/state_store.py`

PR 4. `flyback`, `llc` role/block 최소 도입
- `synthesis/topologies/flyback.py`
- `synthesis/topologies/llc.py`

## Phase 3 실행 계획

## 목표

- example-derived coordinate path를 줄이고
- graph 기반 `Layout Engine` 도입

## 선행 조건

- Phase 2 graph 모델 정착
- `buck` graph canonical source 동작

## 산출물

- `layout/models.py`
- `layout/engine.py`
- `layout/strategies/buck.py`
- topology별 region / orientation / symbol_variant 규칙
- layout 포함 `preview_payload_v1` 확장

## Acceptance

- `buck`이 new layout engine으로 layout 생성
- `svg_renderer.py`가 layout geometry를 재추론하지 않음
- `prepare_components_for_layout()` 의존이 줄어듦
- multi-pin component는 layout에서 symbol_variant를 명시적으로 받음
- `SimulationService.create_circuit()`와 `confirm_circuit()`가 동일 layout input을 기준으로 동작

## 정량 기준

- `buck` preview 생성 성공
- 기존 대비 `buck` component orientation heuristic 감소
- layout snapshot 테스트 통과

## Fallback

- `buck`만 new layout 사용
- `flyback`, `llc`는 legacy layout adapter 유지

## Rollback 기준

- `buck` preview가 visibly broken 상태가 지속
- renderer가 new layout을 소비하지 못함

## PR 단위

PR 1. layout 모델 / 엔진 골격
- `layout/models.py`
- `layout/engine.py`

PR 2. buck layout strategy
- `layout/strategies/buck.py`
- service integration
- `services/simulation_service.py` 입력 계약 정리

PR 3. renderer consume-only 정리
- `utils/svg_renderer.py`

PR 4. flyback/llc layout skeleton
- `layout/strategies/flyback.py`
- `layout/strategies/llc.py`

## Phase 4 실행 계획

## 목표

- readable schematic 기준의 advanced routing 도입

## 선행 조건

- Phase 3에서 최소 1개 topology가 new layout 사용
- preview와 create가 동일 layout input 사용

## 산출물

- `routing/engine.py`
- `routing/strategies/buck.py`
- `routing/metrics.py`
- trunk/branch routing
- rail-aware routing
- bridge-consumable routing payload

## Acceptance

- `buck`에서 큰 우회 루프와 중복 segment 감소
- preview와 bridge가 동일 routing output 사용
- routing이 component direction을 수정하지 않음
- `confirm_circuit()`와 `SimulationService.create_circuit()`가 같은 routing payload를 소비

## 정량 기준

- `buck` duplicate segment count = 0
- `buck` routing crossing count 기존 대비 감소 또는 동일
- preview vs bridge geometry mismatch = 0

## Fallback

- new layout은 유지하되 routing만 legacy `resolve_wire_segments()` 사용

## Rollback 기준

- geometry mismatch 재발
- routing 변경으로 create path wire generation 실패

## PR 단위

PR 1. routing engine / models / metrics
- `routing/engine.py`
- `routing/metrics.py`

PR 2. buck routing strategy
- `routing/strategies/buck.py`

PR 3. service + bridge integration
- `services/circuit_design_service.py`
- `services/simulation_service.py`
- `bridge/bridge_script.py`

PR 4. llc/flyback routing strategy 초안
- `routing/strategies/flyback.py`
- `routing/strategies/llc.py`

## Phase 5 실행 계획

## 목표

- parser shortcut 구조를
  `intent extraction -> candidate ranking -> clarification -> spec builder`
  구조로 교체

## 선행 조건

- Phase 2 이상 완료
- 최소 1개 topology가 graph 기반 synthesize path 사용

## 산출물

- `intent/models.py`
- `intent/extractors.py`
- `intent/ranker.py`
- `intent/clarification.py`
- `intent/spec_builder.py`
- `design_session_v2` 또는 하위 호환되는 `design_session_v1` 서비스 계약

## Acceptance

- `design_circuit()`가 내부적으로 ranked topology candidate 사용
- ambiguity가 질문 또는 ranked suggestion으로 표현됨
- canonical spec에 trace가 남음
- 기존 action shape(`confirm_intent`, `need_specs`, `suggest_candidates`)와 `design_session_token` 호환 유지 또는 명시적 versioning 제공

## 정량 기준

- 대표 자연어 시나리오 5개 이상에서 candidate ranking 결과가 합리적
- single-voltage ambiguity 케이스에서 잘못된 one-shot topology 확정 감소
- spec builder 테스트 통과

## Fallback

- old parser path 유지
- feature flag로 new intent pipeline on/off 가능
- service response contract는 fallback 시에도 동일 action 이름 유지

## Rollback 기준

- 대표 시나리오에서 topology misclassification 급증
- clarification 흐름이 기존 UX를 과도하게 깨뜨림

## PR 단위

PR 1. intent models / extractor
- `intent/models.py`
- `intent/extractors.py`

PR 2. topology ranker / clarification policy
- `intent/ranker.py`
- `intent/clarification.py`

PR 3. spec builder + service integration
- `intent/spec_builder.py`
- `services/circuit_design_service.py`
- `shared/state_store.py`

PR 4. legacy parser 축소
- `parsers/intent_parser.py`
- `parsers/keyword_map.py`
- response/session compatibility tests

## 권장 구현 순서

실제 착수 순서는 아래가 가장 안전하다.

1. Phase 1을 `buck` 기준으로 완료
2. Phase 2에서 `buck` graph canonical source 완성
3. Phase 3에서 `buck` layout engine 연결
4. Phase 4에서 `buck` routing engine 연결
5. 같은 패턴으로 `flyback`, `llc` 확장
6. 마지막에 Phase 5 intent resolution 본격 교체

## 최종 정리

이 문서의 역할은 phase 문서들을 실행형 계획으로 묶는 것이다.

핵심은 다음이다.

> 각 phase는 설계 아이디어로 끝나면 안 되고,
> 최소 기준 topology, acceptance, fallback, rollback, PR 단위가 있어야
> 실제 개발 계획으로 기능한다.

ver5는 이제 `설계 문서 모음`에 더해,
이 문서를 통해 `실행 가능한 개발 계획`까지 갖춘 상태로 보는 것이 맞다.
