# Phase 3~5 상세 로드맵
작성일: 2026-03-24

## 목적

상위 계획 문서에는 `Phase 3`, `Phase 4`, `Phase 5`가 정의돼 있지만,
구현 관점의 세부 설계는 아직 분리돼 있지 않았다.

이 문서는 남은 단계들을 실제 엔지니어링 작업 기준으로 구체화한다.

대상 단계:

- Phase 3. Layout Engine 도입
- Phase 4. Advanced Routing 도입
- Phase 5. Intent Resolution 개선

상세 설계 문서는 아래에 별도로 정리했다.

- `phase-3-layout-engine-design.md`
- `phase-4-advanced-routing-design.md`
- `phase-5-intent-resolution-design.md`

이 문서의 성격은 단순 보충 설명이 아니다.
`Phase 3~5`를 실제 개발 기획 단위로 운영하기 위한 상위 실행 로드맵이며,
각 상세 문서의 읽기 순서와 의존 관계를 고정하는 역할을 한다.

## 전체 순서 재확인

현재 정의된 전환 단계는 총 5개다.

1. Phase 1. Generator 분해
2. Phase 2. CircuitGraph 모델 도입
3. Phase 3. Layout Engine 도입
4. Phase 4. Advanced Routing 도입
5. Phase 5. Intent Resolution 개선

즉 현재 기준으로 추가 단계는 이미 `Phase 5`까지 있다.
이 문서는 그중 `Phase 3~5`를 상세화한 것이다.

또한 이 단계들은 단순 알고리즘 추가가 아니라, backend와 payload를 교체하면서도 tool surface를 안정적으로 유지하는 migration 단계로 읽어야 한다.

## Phase 3. Layout Engine 도입

## 목표

`CircuitGraph`를 입력으로 받아
사람이 읽기 좋은 schematic layout을 생성하는 엔진을 도입한다.

이 단계의 핵심은 `example-derived absolute coordinates`를 생성의 중심에서 제거하는 것이다.

## 해결해야 할 문제

현재는 topology generator나 transition adapter가 사실상 좌표를 공급한다.
이 구조는 아래 문제를 만든다.

- 같은 topology 안에서도 variation 대응이 어렵다
- readable schematic 규칙이 예제 좌표에 종속된다
- graph 의미와 layout 의미가 섞인다

## Phase 3 산출물

- `SchematicLayout` 모델
- `LayoutEngine`
- topology별 layout strategy
- block-aware component placement
- orientation / symbol-variant selection
- versioned preview payload 내 `layout` 저장 규칙

## 제안 모델

### 1. LayoutComponent

```python
@dataclass
class LayoutComponent:
    id: str
    x: int
    y: int
    direction: int
    symbol_variant: str | None = None
    region_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
```

### 2. LayoutRegion

```python
@dataclass
class LayoutRegion:
    id: str
    role: str
    x: int
    y: int
    width: int
    height: int
```

예:

- `primary_region`
- `secondary_region`
- `control_region`
- `input_region`
- `output_region`

### 3. SchematicLayout

```python
@dataclass
class SchematicLayout:
    topology: str
    components: list[LayoutComponent]
    regions: list[LayoutRegion] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

## 신설 권장 파일

- `src/psim_mcp/layout/models.py`
- `src/psim_mcp/layout/engine.py`
- `src/psim_mcp/layout/common.py`
- `src/psim_mcp/layout/strategies/buck.py`
- `src/psim_mcp/layout/strategies/flyback.py`
- `src/psim_mcp/layout/strategies/llc.py`

## 수정 대상

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/shared/state_store.py`
- `src/psim_mcp/synthesis/legacy_layout_adapter.py`
- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/routing/router.py`

## 레이아웃 규칙 초안

### Buck

- 입력 소스는 좌측
- main switch와 diode는 switch stage region
- 인덕터는 switch node 오른쪽
- capacitor와 load는 출력 region
- ground return은 하단 rail

### Flyback

- primary left, secondary right
- transformer는 isolation boundary 중앙
- clamp/snubber는 primary 상단 또는 상부 보조영역
- output rectifier와 filter는 secondary right

### LLC

- half-bridge left
- resonant tank center-left
- transformer center
- secondary rectifier center-right
- output filter right
- primary/secondary 영역 분리 강조

## 완료 기준

- `buck`, `flyback`, `llc`가 example 좌표 없이 readable layout 생성
- `legacy_layout_adapter` 의존도가 축소됨
- renderer가 layout 결과를 직접 소비할 수 있는 형태가 됨
- tool surface 응답 계약은 유지된 채 내부 payload에 `layout`이 추가됨

## 테스트 권장안

- `tests/unit/test_layout_engine_buck.py`
- `tests/unit/test_layout_engine_flyback.py`
- `tests/unit/test_layout_engine_llc.py`
- golden layout snapshot test

## Phase 4. Advanced Routing 도입

## 목표

layout 결과를 기반으로
가독성 높은 `wire_segments`를 생성하는 routing engine을 만든다.

Phase 2가 구조 의미,
Phase 3가 geometry placement라면,
Phase 4는 연결 선의 품질을 담당한다.

## 현재 한계

현재 routing은 canonical consistency 쪽으로는 개선됐지만,
아래는 부족하다.

- trunk/branch 구조 부족
- block-aware routing 부족
- 교차 최소화 부족
- symmetry 부족
- 버스/레일 정렬 부족

## Phase 4 산출물

- `RoutingPlan`
- advanced routing engine
- crossing minimization
- duplicate suppression
- rail/bus-aware routing
- backend 공통 `WireRouting` payload

## 제안 모델

### 1. RoutedSegment

```python
@dataclass
class RoutedSegment:
    id: str
    start: tuple[int, int]
    end: tuple[int, int]
    net_id: str
    role: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
```

### 2. WireRouting

```python
@dataclass
class WireRouting:
    topology: str
    segments: list[RoutedSegment]
    metadata: dict[str, object] = field(default_factory=dict)
```

## 신설 권장 파일

- `src/psim_mcp/routing/engine.py`
- `src/psim_mcp/routing/models.py`
- `src/psim_mcp/routing/heuristics.py`
- `src/psim_mcp/routing/metrics.py`

## 수정 대상

- `src/psim_mcp/routing/router.py`
- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/shared/state_store.py`
- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/bridge/bridge_script.py`

## 주요 알고리즘 방향

### 1. rail-aware routing

- ground는 공통 하단 rail
- DC input은 상단 또는 좌측 trunk
- output positive는 우측 trunk

### 2. block-aware routing

- block 내부는 짧고 직접적으로
- block 간 연결은 trunk-and-branch 패턴

### 3. multi-pin component routing

- transformer
- diode bridge
- half/full bridge

이 부품들은 generic 2-pin 가정으로 다루면 안 된다.

### 4. crossing minimization

- 같은 net segment 병합
- 불필요한 우회 제거
- 직교 routing 우선

## 품질 지표

- segment count
- duplicate count
- crossing count
- total detour length
- unreadable branch count

## 완료 기준

- `buck`, `flyback`, `llc` preview의 어색한 큰 루프가 눈에 띄게 감소
- 다핀 부품 주변 배선이 심볼과 일치
- preview와 bridge가 동일 routing 산출물 사용
- 가능하면 simulation/create도 동일 routing payload를 소비하고, 예외는 capability matrix에 명시됨

## 테스트 권장안

- `tests/unit/test_routing_engine_buck.py`
- `tests/unit/test_routing_engine_llc.py`
- `tests/unit/test_routing_metrics.py`
- SVG regression snapshot tests

## Phase 5. Intent Resolution 개선

## 목표

현재의 parser shortcut 중심 구조를
`candidate generation -> ranking -> clarification -> canonical spec` 구조로 바꾼다.

이 단계는 가장 마지막에 와야 한다.
이유는 내부 synthesis 모델이 먼저 준비되어야
자연어 해석 결과를 안정적으로 연결할 수 있기 때문이다.

## 현재 문제

- keyword 기반 one-shot topology 확정
- use-case에서 topology로 너무 빨리 점프
- `vin/vout` role heuristic가 parser 내부에 과도하게 섞임
- ambiguity를 표현하기보다 빨리 결론내림

## Phase 5 산출물

- `IntentModel`
- topology candidate ranking
- clarification policy
- canonical spec builder
- design traceability
- service compatibility adapter
- versioned design-session payload

## 신설 권장 파일

- `src/psim_mcp/intent/models.py`
- `src/psim_mcp/intent/extractors.py`
- `src/psim_mcp/intent/ranker.py`
- `src/psim_mcp/intent/spec_builder.py`
- `src/psim_mcp/intent/clarification.py`

## 수정 대상

- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/parsers/keyword_map.py`
- `src/psim_mcp/data/topology_metadata.py`
- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/shared/state_store.py`

## 목표 흐름

```text
user text
  -> intent extraction
  -> topology candidate ranking
  -> missing-field analysis
  -> clarification or defaulting
  -> canonical spec
  -> synthesis
```

## 세부 정책

### 1. keyword map 역할 축소

- topology 확정기가 아니라 candidate generator

### 2. ranker 도입

입력:

- intent
- topology metadata
- design feasibility
- domain heuristics

출력:

- ranked candidates
- confidence
- unresolved ambiguities

### 3. clarification policy

질문이 필요한 경우:

- topology score가 비슷함
- 필수 전기 조건이 빠짐
- 절연 여부가 불명확함
- power range가 topology 선택에 크게 영향 줌

### 4. spec builder

- 사용자 명시값
- 시스템 기본값
- topology rule 값

을 구분해서 canonical spec 생성

## 완료 기준

- `design_circuit()`가 one-shot parser shortcut보다 structured resolution 사용
- ambiguity가 있으면 질문 또는 ranked suggestion 제공
- canonical spec과 graph trace가 연결됨
- `confirm_intent`, `need_specs`, `suggest_candidates`, `design_session_token` 계약이 유지됨

## 테스트 권장안

- `tests/unit/test_intent_extractor.py`
- `tests/unit/test_topology_ranker.py`
- `tests/unit/test_spec_builder.py`
- `tests/unit/test_clarification_policy.py`

## 단계 간 의존 관계

이 순서는 바꾸지 않는 것이 좋다.

1. Phase 1 없이는 generator 분리가 안 됨
2. Phase 2 없이는 graph canonical model이 없음
3. Phase 3 없이는 layout가 example 좌표에서 독립 못 함
4. Phase 4 없이는 readable routing이 안 나옴
5. Phase 5는 앞단 모델이 안정된 후에야 의미 있게 개선 가능

추가 의존 관계:

- Phase 3는 preview/store payload가 graph와 layout을 함께 저장할 수 있어야 한다.
- Phase 4는 backend 공통 `WireRouting` payload를 먼저 고정해야 한다.
- Phase 5는 내부 intent pipeline을 바꾸더라도 tool action contract를 유지해야 한다.

즉 가장 마지막의 자연어 고도화보다,
중간 구조 모델링이 먼저다.

## 최종 정리

남은 단계는 단순 보완이 아니다.

- Phase 3은 `좌표 생성 방식`을 바꾸는 단계
- Phase 4는 `회로도 품질`을 바꾸는 단계
- Phase 5는 `자연어 해석 구조`를 바꾸는 단계

실행 계층 관점에서는 아래처럼 읽는 것이 정확하다.

- Phase 3은 layout payload를 승격하는 단계
- Phase 4는 backend 공통 geometry를 고정하는 단계
- Phase 5는 parser를 교체하면서 service contract를 유지하는 단계

정리하면 현재 로드맵의 끝은 Phase 5다.
그 이후에는 새 phase를 늘리기보다,
이 다섯 단계를 topology별 커버리지 확대와 품질 개선으로 반복하는 구조가 더 현실적이다.
