# ver5 Implementation Status

작성일: 2026-03-25
기준 커밋: `a3d738f`
검증 기준: `uv run pytest tests/unit` (821 passed) + 코드 레벨 E2E + `py_compile`

이 문서는 `docs/ver5/` 기획 문서와 현재 코드 구현 상태를 대조한 최신 상태 문서다.

---

## 전체 요약

| 영역 | 상태 | 메모 |
|------|------|------|
| Phase 1. Generator 분해 | 구현 완료 | synthesis model/sizing/synthesize 경계, feature flag 도입 |
| Phase 2. CircuitGraph | 구현 완료 | graph 모델, builder, validator, topology synthesizer, capability 체크 |
| Phase 3. Layout Engine | 구현 완료 | 알고리즘 auto-layout, constraint solver, 29 topology 지원 |
| Phase 4. Routing | 대부분 구현 | trunk/branch, crossing minimization, bridge wire_segments 직접 소비 |
| Phase 5. Intent Resolution | 대부분 구현 | V2 intent pipeline, versioned session, feature flag 연동 |
| Registry/Metadata Ownership | 구현 완료 | 8개 registry 파일 존재, auto_placer에서 소비 |
| Renderer/Bridge Consumer화 | 대부분 구현 | renderer는 layout/wire_segments 소비, bridge는 wire_segments 직접 소비 |

---

## 검증 결과

### 확인한 사실 (코드 실행으로 검증)

- `uv run pytest tests/unit` — 821 passed, 0 failed
- buck/flyback/llc E2E 파이프라인 통과 (intent → graph → layout → routing → materialize → SVG)
- 서비스 레벨: `preview_circuit()`에서 graph/layout/routing/wire_segments 전부 저장됨
- `confirm_circuit()`, `create_circuit_direct()` mock 모드 성공
- bridge_script.py JSON IPC 통신 정상 (PSIM API stdout 오염 차단)

### 이 문서에서 직접 검증하지 못한 것

- topology별 실제 PSIM 생성 성공률 (real 모드 E2E)
- 성능 수치 (SVG 렌더링 시간, 시뮬레이션 속도)

---

## Phase 1. Generator 분해

### 구현됨

- synthesis transition model — `src/psim_mcp/synthesis/models.py`
- sizing logic 분리 — `src/psim_mcp/synthesis/sizing.py`
- generator의 `synthesize()` 경계 — `src/psim_mcp/generators/base.py` + topology별 구현
- preview payload version 필드 — `circuit_design_service.py`
- feature flag 기반 topology on/off — `config.py:50-54` (5개 flag)
- capability matrix runtime 반영 — `circuit_design_service.py:143`

### 부분 구현

- `SimulationService`는 enriched `circuit_spec` 소비 가능하지만 compatibility service 성격 유지

---

## Phase 2. CircuitGraph

### 구현됨

- `GraphComponent`, `GraphNet`, `FunctionalBlock`, `DesignDecisionTrace`, `CircuitGraph`
  - `src/psim_mcp/synthesis/graph.py`
- graph builder helpers — `src/psim_mcp/synthesis/graph_builders.py`
- graph validator — `src/psim_mcp/validators/graph.py`
- buck/flyback/llc graph synthesizer — `src/psim_mcp/synthesis/topologies/*.py`
- preview payload의 graph 저장/복원 — `circuit_design_service.py`
- capability matrix에서 graph 지원 여부 체크 — `circuit_design_service.py:143`

### 부분 구현

- graph validation은 존재하지만 block-level semantic validation은 아직 얕다.

---

## Phase 3. Layout Engine

### 구현됨

- `SchematicLayout`, `LayoutComponent`, `LayoutRegion`, `LayoutConstraint` — `layout/models.py`
- 알고리즘 auto-layout 엔진 — `layout/auto_placer.py`
  - block 기반 region 할당
  - role 기반 component 배치 (registry-driven)
  - force-directed 미세 조정 — `layout/force_directed.py`
  - grid snap (PSIM 50px)
  - constraint enforcement — `layout/constraint_solver.py:21` (`enforce_all()` dispatcher, 7개 kind)
  - symbol variant 선택 (symbol_registry에서 동적 빌드)
- `generate_layout()` — `layout/engine.py` (모든 topology에 auto_place fallback)
- `materialize_to_legacy()` — `layout/materialize.py`
- service preview/store에 layout 저장 — `circuit_design_service.py`
- SVG renderer가 `layout` + `wire_segments` 소비 — `svg_renderer.py`
- `data/symbol_registry.py` — 심볼 variant, pin anchor, bounding box
- `data/layout_strategy_registry.py` — 배치 규칙, role 분류 (규칙 기반 추론 + override), PLACEMENT_ROWS

### 부분 구현

- renderer는 layout을 소비하지만 legacy component dict 기반 렌더링도 유지
- 하드코딩 reference strategy는 `layout/strategies/_reference/`로 이동 (프로덕션 미사용)

---

## Phase 4. Routing

### 구현됨

- `WireRouting`, `RoutedSegment`, `JunctionPoint`, `RoutingPreference` — `routing/models.py`
- `generate_routing()` — `routing/engine.py`
- pin anchor resolution — `routing/anchors.py`
- trunk-and-branch routing — `routing/trunk_branch.py`
- crossing minimization — `routing/trunk_branch.py:332` (`minimize_crossings()`)
- routing metrics — `routing/metrics.py`
- topology별 routing strategy — `routing/strategies/buck.py`, `flyback.py`, `llc.py`
- preview payload의 routing / wire_segments 저장 — `circuit_design_service.py`
- SVG는 `wire_segments` 우선 소비 — `svg_renderer.py`
- bridge는 `wire_segments`가 있으면 좌표 기반 직접 WIRE 생성 — `bridge_script.py:872`
- `SimulationService.create_circuit()`도 routing/wire_segments 소비 가능 — `simulation_service.py`
- `data/routing_policy_registry.py` — topology별 routing 정책

### 부분 구현

- bridge 내부 `_route_wire()` fallback 경로가 남아 있음 (wire_segments 없을 때만 사용)
- layer-aware / symmetry-aware routing은 모델은 있으나 전략에서 깊게 활용하지 않음

---

## Phase 5. Intent Resolution

### 구현됨

- `intent/` 계층 — `extractors.py`, `ranker.py`, `clarification.py`, `spec_builder.py`, `models.py`
- `CircuitDesignService._resolve_intent_v2()` — `circuit_design_service.py`
- `design_circuit()`의 V2-first, legacy fallback 구조
- 기존 action contract 유지 — `confirm_intent`, `need_specs`, `suggest_candidates`
- `candidate_scores`, `decision_trace` 응답 확장
- design session payload versioning — `_make_design_session_payload()` 모든 저장 지점에서 사용
- `_build_need_specs_response()`도 versioned session 사용 — `circuit_design_service.py:1406`
- feature flag `PSIM_INTENT_PIPELINE_V2` — `config.py:50`
- `continue_design()` v1/v2 normalize — `circuit_design_service.py`

### 부분 구현

- multi-hop clarification (질문 → 답변 → 재평가) 미구현
- clarification 결과를 service action으로 완전히 승격하는 경로 미구현

---

## Registry / Ownership

### 구현됨 (8개 registry)

| 파일 | 역할 | auto_placer/service 소비 |
|------|------|------------------------|
| `data/topology_metadata.py` | topology 속성 (29개), required_blocks/roles/nets | Yes |
| `data/component_library.py` | 부품 핀/파라미터 (40+) | Yes |
| `data/symbol_registry.py` | 심볼 variant, pin anchor, bounding box | Yes (auto_placer) |
| `data/layout_strategy_registry.py` | 배치 규칙, role 분류, PLACEMENT_ROWS | Yes (auto_placer) |
| `data/routing_policy_registry.py` | topology별 routing 정책 | Yes (routing strategies) |
| `data/design_rule_registry.py` | 설계 규칙, default값, feasibility | 참조 가능 |
| `data/bridge_mapping_registry.py` | PSIM 타입 매핑, parameter map | Yes (bridge_script) |
| `data/capability_matrix.py` | topology × feature 지원 상태 | Yes (service pipeline) |

### 부분 구현

- `design_rule_registry.py`는 존재하지만 sizing 로직이 registry에서 직접 호출되지는 않음 (참조 데이터)
- registry 간 cross-validation (예: topology_metadata의 required_blocks가 실제 graph와 일치하는지) 자동 검증 없음

---

## Service Integration

### Entrypoint별 canonical pipeline 적용 상태

| Entrypoint | 상태 | graph 저장 | layout 저장 | routing 저장 |
|------------|------|-----------|------------|-------------|
| `design_circuit()` → `_auto_generate_preview()` | 구현 | Yes | Yes | Yes |
| `preview_circuit()` | 구현 | Yes | Yes | Yes |
| `confirm_circuit()` | 구현 | graph/layout rematerialize | — | — |
| `create_circuit_direct()` | 구현 | synthesis-first | — | — |
| `SimulationService.create_circuit()` | 부분 구현 | enriched spec 소비 가능 | — | — |

### Preview payload 필드

`payload_kind`, `payload_version`, `components`, `connections`, `nets`, `wire_segments`, `graph`, `layout`, `routing`

### Design session payload

- 모든 저장 지점에서 `_make_design_session_payload()` 사용 (versioned)
- `continue_design()` v1/v2 normalize 지원

---

## Renderer / Bridge Consumer 전환

### SVG Renderer

- `layout` 입력 지원, `wire_segments` 우선 렌더링
- `layout → component position merge` 구현
- legacy component dict 기반 심볼 렌더링은 유지 (symbol_registry 참조 가능하지만 renderer가 직접 읽지는 않음)

### Bridge

- `wire_segments` 있으면 좌표 기반 직접 WIRE 생성 (`_suppress_stdout` 보호)
- 없으면 기존 `connections` fallback (`_route_wire` + `_resolve_pin_positions`)
- bridge 내부 fallback 코드는 legacy 호환을 위해 유지

---

## 남은 작업

1. **실제 PSIM E2E 검증** — real 모드에서 buck/flyback/llc 생성 → 시뮬레이션 성공 확인
2. **multi-hop clarification** — 질문 → 답변 → 재평가 → 재질문 흐름
3. **나머지 26개 topology synthesize()** — 현재 buck/flyback/llc만 new path, 나머지는 legacy
4. **renderer symbol_registry 직접 소비** — SVG renderer가 registry에서 심볼 정의를 직접 읽는 구조
5. **registry cross-validation** — topology_metadata ↔ graph ↔ layout_strategy 자동 일치 검증

---

## 검증 방법

| 방법 | 결과 |
|------|------|
| `uv run pytest tests/unit -q` | 821 passed |
| Buck E2E (intent → SVG) | 8 comp, 5 net, 3 block, 8 seg, 5546 char SVG |
| Flyback E2E | 8 comp, 7 net, 5 block, 10 seg, 6567 char SVG |
| LLC E2E | 14 comp, 11 net, 7 block, 19 seg, 9864 char SVG |
| Service preview graph/layout 저장 | buck/flyback/llc 전부 OK |
| `py_compile` | 전 소스 통과 |
| Bridge JSON IPC | 정상 (stdout 오염 차단) |

---

## 결론

ver5 canonical pipeline은 buck/flyback/llc 범위에서 **구현 완료 + 코드 레벨 검증 완료** 상태다.

- Phase 1~3: 구현 완료
- Phase 4~5: 대부분 구현 (고급 routing 품질, multi-hop clarification 제외)
- Registry/ownership: 8개 파일 전부 존재, 대부분 소비 경로 연결
- 서비스 통합: 4개 entrypoint 전부 canonical pipeline 우선, legacy fallback 유지
- 테스트: 821개 통과, E2E 3 topology 검증

남은 리스크는 **구조 부족이 아니라 실행 검증 부족**이다. 특히 real 모드 PSIM E2E와 나머지 topology 확장이 다음 단계다.
