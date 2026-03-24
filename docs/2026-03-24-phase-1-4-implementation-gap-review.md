# Phase 1~4 구현 갭 리뷰

작성일: 2026-03-24

## 목적

`docs/ver5`의 Phase 1~4 문서와 현재 코드를 대조해서, 이미 구현된 부분과 아직 빠진 부분을 정리한다.

검토 기준 문서:

- `docs/ver5/phase-1-file-impact-and-interface-draft.md`
- `docs/ver5/phase-2-circuit-graph-design.md`
- `docs/ver5/phase-3-layout-engine-design.md`
- `docs/ver5/phase-4-advanced-routing-design.md`

검토 기준 코드:

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/synthesis/*`
- `src/psim_mcp/layout/*`
- `src/psim_mcp/routing/*`
- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/bridge/bridge_script.py`
- `src/psim_mcp/shared/state_store.py`

## 전체 판단

- Phase 1: 부분 구현
- Phase 2: 부분 구현
- Phase 3: alpha 수준
- Phase 4: 부분 구현

공통 패턴은 같다.

1. `graph/layout/routing`은 내부 모델과 preview payload에는 들어왔다.
2. 하지만 `confirm/create/simulation/backend`가 그 산출물을 source of truth로 소비하는 전환은 아직 덜 끝났다.
3. 따라서 현재 상태는 `새 파이프라인 추가`에 가깝고, `기존 legacy 경로 대체`까지는 아니다.

## 핵심 요약

### 1. preview 저장은 됐지만 confirm/create/backend 소비 전환이 안 끝났다

현재 `preview_circuit()`는 synthesis -> layout -> routing -> legacy 변환 경로를 시도하고, `graph`, `layout`, `routing`을 preview payload에 저장한다.

- `src/psim_mcp/services/circuit_design_service.py:136`
- `src/psim_mcp/services/circuit_design_service.py:177`
- `src/psim_mcp/services/circuit_design_service.py:308`

하지만 `confirm_circuit()`는 저장된 `graph/layout/routing`을 다시 쓰지 않고, 여전히 `components`, `connections`, `nets`만 꺼내서 legacy create 경로로 넘긴다.

- `src/psim_mcp/services/circuit_design_service.py:778`
- `src/psim_mcp/services/circuit_design_service.py:801`
- `src/psim_mcp/services/circuit_design_service.py:843`

`create_circuit_direct()`도 Phase 2~4 경로를 타지 않고 `_try_generate()` 기반 legacy 생성 흐름을 사용한다.

- `src/psim_mcp/services/circuit_design_service.py:851`
- `src/psim_mcp/services/circuit_design_service.py:863`

의미:

- preview에 새 payload를 저장하는 것과
- create path의 canonical source를 바꾸는 것은 별개다.

현재는 전자만 됐고 후자는 남아 있다.

### 2. 서비스 end-to-end 활성화는 사실상 buck 중심이다

서비스에서 synthesis 경로로 등록된 topology는 현재 `buck`만 보인다.

- `src/psim_mcp/services/circuit_design_service.py:58`
- `src/psim_mcp/services/circuit_design_service.py:61`

반면 `synthesize_flyback()`와 `synthesize_llc()`는 이미 존재한다.

- `src/psim_mcp/synthesis/topologies/flyback.py:18`
- `src/psim_mcp/synthesis/topologies/llc.py:20`

layout/routing 전략도 `buck/flyback/llc`가 다 등록되어 있다.

- `src/psim_mcp/layout/__init__.py:21`
- `src/psim_mcp/routing/__init__.py:27`

즉 현재 상태는:

- 모델 계층은 3개 topology를 지원
- 서비스 계층은 사실상 buck만 Phase 2~4 경로 활성화

문서의 완료 기준과 비교하면 coverage가 좁다.

### 3. SVG/Bridge/Simulation이 아직 consumer-only backend로 바뀌지 않았다

`svg_renderer.py`는 `SchematicLayout`이나 `WireRouting`을 직접 받지 않는다.
여전히 `components`, `connections`, `nets`를 입력으로 받아 핀 위치와 junction을 내부에서 다시 계산한다.

- `src/psim_mcp/utils/svg_renderer.py:214`
- `src/psim_mcp/utils/svg_renderer.py:292`
- `src/psim_mcp/utils/svg_renderer.py:537`

`SimulationService.create_circuit()`도 명시적으로 legacy 포맷을 소비한다고 적혀 있다.

- `src/psim_mcp/services/simulation_service.py:269`
- `src/psim_mcp/services/simulation_service.py:270`
- `src/psim_mcp/services/simulation_service.py:302`

bridge 쪽도 여전히 `connections`를 읽고 자체 pin position map 기반으로 wire를 만든다.

- `src/psim_mcp/bridge/bridge_script.py:738`
- `src/psim_mcp/bridge/bridge_script.py:842`

즉 Phase 3~4 문서가 기대하는

- `renderer = layout/routing consumer`
- `bridge = routing consumer`

상태는 아직 아니다.

## Phase별 갭 정리

## Phase 1

문서 기대:

- `SizedComponentSpec`, `NetSpec`, `TopologySynthesisResult` 같은 중간 모델 도입
- `legacy_layout_adapter` 경계 도입
- preview payload version 고정
- `SimulationService.create_circuit()` 입력 계약 고정
- 가능하면 `synthesis_result` 저장

현재 구현 상태:

- preview payload의 `payload_kind`, `payload_version`은 들어감
  - `src/psim_mcp/services/circuit_design_service.py:308`
- `SimulationService.create_circuit()`는 legacy boundary라는 주석이 있음
  - `src/psim_mcp/services/simulation_service.py:269`

빠진 부분:

1. `TopologySynthesisResult`, `SizedComponentSpec`, `NetSpec` 전용 구현이 없다.
   - `src/psim_mcp/synthesis/graph.py`는 존재하지만 문서의 Phase 1 중간 모델 계층과는 다르다.
   - `src/psim_mcp/synthesis/models.py` 파일은 없다.

2. `legacy_layout_adapter.py`가 없다.
   - 현재는 `src/psim_mcp/layout/materialize.py`가 그 역할 일부를 대체한다.
   - 하지만 문서가 의도한 `Phase 1 transition boundary`와 이름/계층은 아직 다르다.

3. preview payload에 `synthesis_result` 저장이 없다.
   - 저장되는 것은 `graph`, `layout`, `routing` 또는 legacy fields다.
   - `src/psim_mcp/services/circuit_design_service.py:300`

4. design session schema가 아직 Phase 1 문서 수준으로 고정되지 않았다.
   - 일부 경로는 `payload_version`을 넣지만
   - `_build_need_specs_response()`는 여전히 plain dict 세션을 저장한다.
   - `src/psim_mcp/services/circuit_design_service.py:397`
   - `src/psim_mcp/services/circuit_design_service.py:446`
   - `src/psim_mcp/services/circuit_design_service.py:1208`

5. `StateStore`에는 schema/version compatibility layer가 없다.
   - 그냥 dict save/get/delete만 한다.
   - `src/psim_mcp/shared/state_store.py:31`

평가:

- Phase 1의 `payload version 도입`은 됐다.
- 하지만 `중간 모델/adapter boundary/세션 schema 고정`은 아직 부분 구현이다.

## Phase 2

문서 기대:

- `CircuitGraph`를 canonical source로 사용
- graph validator 도입
- preview store에 graph 저장
- `confirm/create/simulation` 경계에서 graph 계약 유지
- mixed-mode topology matrix 명시

현재 구현 상태:

- `CircuitGraph` 모델 존재
  - `src/psim_mcp/synthesis/graph.py:61`
- graph validator 존재
  - `src/psim_mcp/validators/graph.py:23`
- preview payload에 graph 저장
  - `src/psim_mcp/services/circuit_design_service.py:300`

빠진 부분:

1. graph가 create path의 canonical source가 아니다.
   - `confirm_circuit()`는 stored graph를 읽지 않는다.
   - `create_circuit_direct()`도 graph pipeline을 사용하지 않는다.
   - `src/psim_mcp/services/circuit_design_service.py:801`
   - `src/psim_mcp/services/circuit_design_service.py:851`

2. graph validator가 문서 기대보다 훨씬 얕다.
   - 현재 검사:
     - empty components
     - empty nets
     - duplicate component id
     - dangling pin ref
   - 빠진 검사:
     - duplicate net id
     - required role completeness
     - required block completeness
     - orphan component/net
     - block membership consistency
   - `src/psim_mcp/validators/graph.py:23`

3. 서비스 mixed-mode coverage가 문서보다 좁다.
   - synth 함수는 `buck/flyback/llc`가 있지만
   - service `_SYNTHESIZERS` 등록은 `buck`만 있다.
   - `src/psim_mcp/services/circuit_design_service.py:61`

4. payload version 호환 규칙이 실제 코드에는 없다.
   - 문서는 `payload_version` 없는 legacy payload를 compatibility adapter로 읽으라고 하지만
   - 현재 confirm path는 version을 거의 보지 않는다.
   - `src/psim_mcp/services/circuit_design_service.py:801`

평가:

- Phase 2의 모델 뼈대는 들어왔다.
- 하지만 `graph-first service contract` 전환은 아직 안 끝났다.

## Phase 3

문서 기대:

- `CircuitGraph -> SchematicLayout`
- layout payload 저장
- renderer가 layout consumer로 축소
- `confirm/create/simulation`이 저장된 layout를 우선 소비
- `prepare_components_for_layout()` 축소 또는 제거
- `buck/flyback/llc`가 new layout engine으로 생성

현재 구현 상태:

- `SchematicLayout` 모델 존재
  - `src/psim_mcp/layout/models.py:47`
- `generate_layout()` 존재
  - `src/psim_mcp/layout/engine.py:31`
- topology별 layout 전략 존재
  - `src/psim_mcp/layout/strategies/buck.py:53`
  - `src/psim_mcp/layout/strategies/flyback.py:52`
  - `src/psim_mcp/layout/strategies/llc.py:70`
- preview payload에 layout 저장
  - `src/psim_mcp/services/circuit_design_service.py:305`

빠진 부분:

1. service end-to-end는 여전히 buck 중심이다.
   - flyback/llc layout 전략은 있어도 service synth 등록이 안 되어 있어 preview 실사용 경로는 제한적이다.

2. layout 전략이 아직 `generator-derived fixed coordinate table` 수준이다.
   - 세 전략 파일 모두 `Position mapping derived from generators/...`로 시작한다.
   - `preferences`를 실제로 쓰지 않는다.
   - `anchor_policy`도 실질적으로 채워지지 않는다.
   - `src/psim_mcp/layout/strategies/buck.py:3`
   - `src/psim_mcp/layout/strategies/flyback.py:3`
   - `src/psim_mcp/layout/strategies/llc.py:3`

3. `svg_renderer.py`는 여전히 layout consumer가 아니다.
   - layout를 직접 입력으로 받지 않는다.
   - geometry를 legacy ports/pin map으로 재구성한다.
   - `src/psim_mcp/utils/svg_renderer.py:214`
   - `src/psim_mcp/utils/svg_renderer.py:537`

4. confirm/create/simulation이 stored layout를 다시 사용하지 않는다.
   - layout는 payload에 저장만 되고 create path source는 legacy components/nets다.

5. `prepare_components_for_layout()`는 아직 routing 공개 API에 남아 있다.
   - `src/psim_mcp/routing/__init__.py:14`
   - `src/psim_mcp/routing/router.py:141`

6. 문서가 요구한 `layout/registry.py`는 없다.
   - 현재는 per-topology hardcoded strategy만 있고
   - 중앙 registry 또는 metadata 기반 layout hint layer는 없다.

평가:

- Phase 3는 `구조 분리`는 됐다.
- 하지만 `layout payload가 실제 runtime source of truth`가 된 상태는 아니다.
- 상태 평가는 `Phase 3 alpha`가 적절하다.

## Phase 4

문서 기대:

- `CircuitGraph + SchematicLayout -> WireRouting`
- preview와 bridge가 동일 routing output 소비
- backend가 rerouting하지 않음
- `SimulationService`도 가능하면 같은 routing payload 소비
- router legacy facade 유지

현재 구현 상태:

- `WireRouting` 모델 존재
  - `src/psim_mcp/routing/models.py:62`
- `generate_routing()` 존재
  - `src/psim_mcp/routing/engine.py:34`
- buck/flyback/llc routing 전략 존재
  - `src/psim_mcp/routing/strategies/buck.py`
  - `src/psim_mcp/routing/strategies/flyback.py:22`
  - `src/psim_mcp/routing/strategies/llc.py:26`
- preview payload에 routing 저장
  - `src/psim_mcp/services/circuit_design_service.py:323`

빠진 부분:

1. preview와 bridge가 같은 routing output을 end-to-end로 쓰지 않는다.
   - service는 routing이 있으면 `to_legacy_segments()`로 변환해 `wire_segments`를 저장한다.
   - bridge main path는 여전히 `connections` 중심이다.
   - `src/psim_mcp/services/circuit_design_service.py:651`
   - `src/psim_mcp/bridge/bridge_script.py:738`

2. renderer도 stored routing를 소비하지 않는다.
   - `render_circuit_svg()`는 routing payload를 받지 않는다.
   - nets 또는 connections로 다시 geometry를 만든다.

3. `SimulationService.create_circuit()`는 여전히 legacy-only다.
   - 코드 주석도 direct `WireRouting` consumption은 Phase 5+라고 적고 있다.
   - `src/psim_mcp/services/simulation_service.py:269`

4. `create_circuit_direct()`는 routing engine 경로를 타지 않는다.
   - preview 경로와 create 경로의 내부 source가 아직 다르다.

5. routing 전략은 존재하지만 문서가 기대한 advanced 정책의 상당수는 아직 간단하다.
   - flyback/llc 전략도 대부분 `resolve_pin_positions -> route_net_trunk_branch()` 패턴이다.
   - region-aware, symmetry-aware, backend contract 수준의 고급 처리까지는 아직 아니다.
   - `src/psim_mcp/routing/strategies/flyback.py:35`
   - `src/psim_mcp/routing/strategies/llc.py:39`

평가:

- Phase 4는 모델과 기본 엔진은 들어왔다.
- 하지만 `backend-common geometry contract`로 완결된 상태는 아니다.

## 우선순위별 후속 작업

## P0

1. `confirm_circuit()`가 `graph/layout/routing` 저장 payload를 실제로 읽도록 전환
2. `create_circuit_direct()`에도 synthesis -> layout -> routing 경로 연결
3. `SimulationService.create_circuit()`의 legacy-only 경계를 capability matrix와 코드에서 명시적으로 통일

## P1

1. `_SYNTHESIZERS`에 `flyback`, `llc` 연결
2. graph validator 확장
3. design session payload schema를 일관되게 버전 고정
4. preview payload version compatibility adapter 추가

## P2

1. `svg_renderer.py`를 layout/routing consumer API로 축소
2. bridge main path가 `WireRouting` 또는 동일 geometry payload를 직접 소비하도록 변경
3. `prepare_components_for_layout()`를 fallback 경로로 격하
4. layout registry / anchor policy / preference 반영 계층 추가

## 권장 결론

현재 1~4단계 구현은 `실패`가 아니라 `1차 구조 이식`에 가깝다.

즉 다음처럼 보는 게 정확하다.

- Phase 1: payload/version과 일부 boundary는 도입됨
- Phase 2: graph 모델은 도입됐지만 service canonical source 전환은 미완료
- Phase 3: layout engine은 생겼지만 runtime source of truth 전환은 미완료
- Phase 4: routing engine은 생겼지만 backend consumer 전환은 미완료

가장 중요한 남은 일은 새 모델을 더 만드는 것이 아니라,
이미 저장되는 `graph/layout/routing`을 `confirm/create/simulation/backend`가 실제로 읽게 만드는 것이다.

## 검증 한계

- 이 환경에서는 `python -m pytest` 실행이 불가능했다.
- 오류: `No module named pytest`
- 따라서 이번 문서는 코드 정적 리뷰 기준이다.
