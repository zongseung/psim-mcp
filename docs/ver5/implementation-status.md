# ver5 Implementation Status

작성일: 2026-03-24  
기준 커밋: `424dfba`  
검증 기준: 로컬 코드 정적 확인 + `py_compile`  

이 문서는 `docs/ver5/` 기획 문서와 현재 코드 구현 상태를 대조한 최신 상태 문서다.
완료율 숫자나 테스트 통과 개수처럼 이 환경에서 직접 검증하지 못한 수치는 적지 않는다.

---

## 전체 요약

| 영역 | 상태 | 메모 |
|------|------|------|
| Phase 1. Generator 분해 | 대부분 구현 | synthesis model/sizing/synthesize 경계는 도입됨 |
| Phase 2. CircuitGraph | 대부분 구현 | graph 모델, builder, validator, topology synthesizer 존재 |
| Phase 3. Layout Engine | 부분 구현 | layout engine/materialize/store 연동은 됐지만 완전 consumer-only는 아님 |
| Phase 4. Routing | 부분 구현 | routing 모델/engine/store 연동은 됐고 wire_segments 소비 경로도 연결됨 |
| Phase 5. Intent Resolution | 부분 구현 | V2 intent pipeline 도입, session versioning은 일부만 반영 |
| Registry/Metadata Ownership | 미구현 중심 | 설계 문서는 있으나 registry 파일 계층은 대부분 없음 |
| Renderer/Bridge Consumer화 | 부분 구현 | renderer는 layout/wire_segments 소비 시작, bridge는 wire_segments 우선 소비 |

---

## 검증 결과

### 확인한 사실

- `CircuitGraph`, graph builder, sizing 모델, topology synthesizer가 실제 코드에 존재한다.
- `layout/engine.py`, `layout/models.py`, `layout/materialize.py`가 존재하고 service와 연결된다.
- `routing/models.py`, `routing/engine.py`, `routing/anchors.py`, `routing/trunk_branch.py`, `routing/metrics.py`가 존재한다.
- `intent/` 아래 `extractors.py`, `ranker.py`, `clarification.py`, `spec_builder.py`, `models.py`가 존재한다.
- `CircuitDesignService`는 `design_circuit`, `preview_circuit`, `confirm_circuit`, `create_circuit_direct`에서 canonical pipeline을 우선 시도한다.
- preview payload에는 `payload_kind`, `payload_version`, `graph`, `layout`, `routing`, `wire_segments`를 저장할 수 있다.
- `SimulationService.create_circuit()`는 이제 `circuit_spec` 내부의 `graph/layout/routing/wire_segments`를 읽을 수 있다.
- SVG renderer는 `layout`과 `wire_segments`를 입력으로 받을 수 있다.
- bridge는 `wire_segments`가 있으면 그것을 우선 connection 입력으로 사용한다.

### 이 문서에서 직접 검증하지 못한 것

- `pytest` 전체 통과 개수
- 퍼센트 기반 완료율
- 성능 수치
- topology별 실제 PSIM 생성 성공률

---

## Phase 1. Generator 분해

### 구현됨

- synthesis transition model
  - `src/psim_mcp/synthesis/models.py`
- sizing logic 분리
  - `src/psim_mcp/synthesis/sizing.py`
- generator의 `synthesize()` 경계
  - `src/psim_mcp/generators/base.py`
  - topology별 generator 구현
- preview payload version 필드
  - `src/psim_mcp/services/circuit_design_service.py`

### 부분 구현

- `SimulationService`는 더 이상 순수 legacy-only는 아니다.
  - enriched `circuit_spec`를 읽을 수 있다.
  - 다만 compatibility service 성격은 여전히 강하다.

### 미구현

- feature flag 기반 topology on/off
- capability matrix의 실제 config/runtime 반영

---

## Phase 2. CircuitGraph

### 구현됨

- `GraphComponent`, `GraphNet`, `FunctionalBlock`, `DesignDecisionTrace`, `CircuitGraph`
  - `src/psim_mcp/synthesis/graph.py`
- graph builder helpers
  - `src/psim_mcp/synthesis/graph_builders.py`
- graph validator
  - `src/psim_mcp/validators/graph.py`
- buck/flyback/llc graph synthesizer
  - `src/psim_mcp/synthesis/topologies/*.py`
- preview payload의 graph 저장/복원
  - `src/psim_mcp/services/circuit_design_service.py`

### 부분 구현

- graph validation은 존재하지만 block-level semantic validation은 아직 얕다.
- graph-only projection보다 `graph + layout -> legacy materialize` 경로가 중심이다.

---

## Phase 3. Layout Engine

### 구현됨

- `SchematicLayout`, `LayoutComponent`, `LayoutRegion`, `LayoutConstraint`
  - `src/psim_mcp/layout/models.py`
- `generate_layout()`
  - `src/psim_mcp/layout/engine.py`
- buck/flyback/llc layout strategy
  - `src/psim_mcp/layout/strategies/*.py`
- `materialize_to_legacy()`
  - `src/psim_mcp/layout/materialize.py`
- service preview/store에 layout 저장
  - `src/psim_mcp/services/circuit_design_service.py`
- SVG renderer가 `layout` 파라미터를 받아 component position/direction에 반영
  - `src/psim_mcp/utils/svg_renderer.py`

### 부분 구현

- renderer는 `layout`을 소비하지만, 아직 `SchematicLayout` 전용 consumer-only backend는 아니다.
  - legacy component dict 기반 렌더링을 유지한다.
- layout constraint solver/enforcer는 아직 없다.
- 일부 기존 routing helper가 layout 이전 시대의 호환 코드로 남아 있다.

### 미구현

- `data/symbol_registry.py`
- `data/layout_strategy_registry.py`

---

## Phase 4. Routing

### 구현됨

- `WireRouting`, `RoutedSegment`, `JunctionPoint`, `RoutingPreference`
  - `src/psim_mcp/routing/models.py`
- `generate_routing()`
  - `src/psim_mcp/routing/engine.py`
- pin anchor resolution
  - `src/psim_mcp/routing/anchors.py`
- trunk-and-branch routing
  - `src/psim_mcp/routing/trunk_branch.py`
- routing metrics
  - `src/psim_mcp/routing/metrics.py`
- preview payload의 routing / wire_segments 저장
  - `src/psim_mcp/services/circuit_design_service.py`
- SVG는 `wire_segments`를 우선 소비
  - `src/psim_mcp/utils/svg_renderer.py`
- bridge는 `wire_segments`를 우선 소비
  - `src/psim_mcp/bridge/bridge_script.py`
- `SimulationService.create_circuit()`도 routing/wire_segments를 읽을 수 있음
  - `src/psim_mcp/services/simulation_service.py`

### 부분 구현

- bridge 내부 `_route_wire()`와 pin-position resolution 로직은 여전히 남아 있다.
- layer-aware / symmetry-aware / advanced crossing minimization은 모델보다 구현이 약하다.
- routing policy registry 계층은 아직 없다.

### 미구현

- `data/routing_policy_registry.py`
- bridge runtime용 별도 mapping/geometry registry

---

## Phase 5. Intent Resolution

### 구현됨

- `intent/` 계층 도입
  - `extractors.py`
  - `ranker.py`
  - `clarification.py`
  - `spec_builder.py`
  - `models.py`
- `CircuitDesignService._resolve_intent_v2()` 도입
- `design_circuit()`의 V2-first, legacy fallback 구조
- 기존 action contract 유지
  - `confirm_intent`
  - `need_specs`
  - `suggest_candidates`
- `candidate_scores`, `decision_trace` 응답 확장
- design session payload versioning 시작
  - `_make_design_session_payload()`
  - `_normalize_design_session_payload()`

### 부분 구현

- `design_circuit()`에서 생성하는 session payload는 versioned다.
- `continue_design()`는 v1/v2를 normalize해서 읽는다.
- 하지만 `_build_need_specs_response()`는 아직 plain dict session을 저장한다.

### 미구현

- multi-hop clarification
- clarification 결과를 service action으로 완전히 승격하는 경로
- feature flag `PSIM_INTENT_PIPELINE_V2`

---

## Registry / Ownership

### 현재 있는 것

- `data/topology_metadata.py`
- `data/component_library.py`
- `data/simulation_defaults.py`
- `data/spec_mapping.py`
- `data/circuit_templates.py`

### 아직 없는 것

- `data/design_rule_registry.py`
- `data/symbol_registry.py`
- `data/layout_strategy_registry.py`
- `data/routing_policy_registry.py`
- `data/bridge_mapping_registry.py`

즉 ownership 문서는 설계 기준으로 유효하지만, registry 파일 계층은 아직 대부분 구현되지 않았다.

---

## Service Integration

### Entrypoint별 canonical pipeline 적용 상태

| Entrypoint | 상태 | 메모 |
|------------|------|------|
| `design_circuit()` -> `_auto_generate_preview()` | 구현 | synthesis-first, legacy fallback |
| `preview_circuit()` | 구현 | synthesis-first, legacy fallback |
| `confirm_circuit()` | 구현 | graph/layout rematerialize 사용 가능 |
| `create_circuit_direct()` | 구현 | synthesis-first, legacy fallback |
| `SimulationService.create_circuit()` | 부분 구현 | enriched `circuit_spec` 소비 가능, compatibility path 유지 |

### Preview payload

현재 preview payload는 다음 필드를 가질 수 있다.

- `payload_kind`
- `payload_version`
- `components`
- `connections`
- `nets`
- `wire_segments`
- `graph`
- `layout`
- `routing`

### Design session payload

현재 상태는 혼합이다.

- `design_circuit()`의 medium/missing flow는 versioned session payload를 쓴다.
- `continue_design()`는 v1/v2 normalize를 한다.
- `_build_need_specs_response()`는 아직 legacy plain dict를 저장한다.

즉 design session versioning은 `부분 구현`이다.

---

## Renderer / Bridge Consumer 전환

### SVG Renderer

현재 상태:

- `layout` 입력 지원
- `wire_segments` 입력 지원
- `layout -> component position merge` 구현

아직 남은 점:

- renderer 자체는 여전히 legacy component dict 중심이다.
- 진정한 `consumer-only`로 보려면 symbol/anchor 책임이 registry로 더 빠져야 한다.

### Bridge

현재 상태:

- `wire_segments`가 있으면 우선 사용
- 없으면 기존 `connections` fallback

아직 남은 점:

- bridge 내부에 자체 pin resolution / wire routing 성격 코드가 남아 있다.
- 완전한 consumer-only backend라고 보기는 이르다.

---

## 남은 핵심 gap

1. `_build_need_specs_response()`도 versioned design session payload를 쓰게 맞추기
2. symbol/layout/routing/bridge registry 파일 계층 도입
3. bridge 내부 geometry 추론을 더 줄이고 canonical payload consumer 경계 강화
4. feature flag / capability matrix를 실제 config/runtime로 내리기
5. 고급 routing 품질 기능
   - crossing minimization
   - symmetry-aware routing
   - layer-aware policy 적용

---

## 검증 방법

이번 상태 문서는 아래 기준으로 작성했다.

- 코드 존재 여부 확인
- service 연결 여부 확인
- 최신 수정 반영 여부 확인
- `python -m py_compile` 기준 문법 확인

실행하지 못한 것:

- `pytest`
- 실제 PSIM GUI/bridge 동작 end-to-end

---

## 결론

`implementation-status.md`의 이전 버전은 방향성은 맞았지만, 최신 코드 기준으로는 stale한 항목이 있었다.

현재 더 정확한 상태 평가는 다음과 같다.

- Phase 1~2는 `대부분 구현`
- Phase 3~5는 `부분 구현`
- renderer/bridge consumer-only 전환은 `부분 구현`
- registry ownership 구조는 `대부분 미구현`

즉 ver5는 이미 `설계만 있는 상태`는 아니고, canonical pipeline이 실제 서비스 경로에 꽤 들어와 있다.
다만 아직 `완전한 정리 상태`라기보다 `migration이 많이 진행된 중간 단계`로 보는 것이 맞다.
