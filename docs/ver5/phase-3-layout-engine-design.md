# Phase 3 상세: Layout Engine 설계 문서
작성일: 2026-03-24

## 목적

Phase 3의 목표는 `CircuitGraph`를 사람이 읽기 좋은 schematic layout으로 변환하는
`Layout Engine`을 도입하는 것이다.

현재 코드에서는 이 역할이 다음 계층에 분산돼 있다.

- topology generator 내부의 `position`, `direction`, `ports` 하드코딩
- `src/psim_mcp/generators/layout.py`의 example-derived helper
- `src/psim_mcp/routing/router.py`의 방향 보정 heuristic
- `src/psim_mcp/utils/svg_renderer.py`의 심볼/핀 앵커 가정

이 문서는 그 책임을 별도 `layout` 계층으로 모으는 설계를 정의한다.

## 왜 별도 Layout Engine이 필요한가

현재 구조의 문제는 회로 구조와 회로도 배치가 너무 많이 섞여 있다는 점이다.

예:

- `buck.py`는 buck topology를 정의하는 동시에 MOSFET, diode, inductor의 좌표를 고정한다
- `llc.py`는 공진형 topology 구조와 PSIM reference 좌표 패턴을 함께 넣고 있다
- `router.py`는 position이 없는 component에 대해 방향을 추정한다

이 방식의 한계:

- topology variation 대응이 어렵다
- 예제 좌표가 구조 자체를 지배한다
- 동일한 graph에서 여러 layout style을 만들기 어렵다
- renderer와 bridge가 geometry를 재추론하게 된다

즉 Layout Engine은 단순한 보기 개선이 아니라,
`structure`와 `geometry`를 분리하기 위한 핵심 단계다.

## Layout Engine의 입력과 출력

### 입력

- `CircuitGraph`
- layout preference
- topology-specific placement rules
- symbol registry

### 출력

- `SchematicLayout`

이 단계에서는 wire를 아직 만들지 않는다.
오직 component geometry와 placement만 만든다.

## 제안 모델

### 1. LayoutComponent

```python
from dataclasses import dataclass, field

@dataclass
class LayoutComponent:
    id: str
    x: int
    y: int
    direction: int
    symbol_variant: str | None = None
    region_id: str | None = None
    anchor_policy: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
```

의미:

- `direction`: 0/90/180/270
- `symbol_variant`: 예: `ideal_transformer_horizontal`, `diode_bridge_4pin`
- `anchor_policy`: routing이 pin anchor를 해석하는 방법

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
    metadata: dict[str, object] = field(default_factory=dict)
```

이 모델은 topology-specific grouping을 시각 영역으로 나타낸다.

예:

- `primary_region`
- `secondary_region`
- `input_region`
- `switch_region`
- `output_region`
- `control_region`

### 3. LayoutConstraint

```python
@dataclass
class LayoutConstraint:
    kind: str
    subject_ids: list[str]
    value: object
    priority: str = "normal"
```

예:

- `same_row`
- `same_column`
- `left_of`
- `right_of`
- `inside_region`
- `align_to_rail`
- `symmetric_about`

### 4. SchematicLayout

```python
@dataclass
class SchematicLayout:
    topology: str
    components: list[LayoutComponent]
    regions: list[LayoutRegion] = field(default_factory=list)
    constraints: list[LayoutConstraint] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

## 파일 구조 제안

### 신설

- `src/psim_mcp/layout/models.py`
- `src/psim_mcp/layout/engine.py`
- `src/psim_mcp/layout/registry.py`
- `src/psim_mcp/layout/common.py`
- `src/psim_mcp/layout/strategies/buck.py`
- `src/psim_mcp/layout/strategies/flyback.py`
- `src/psim_mcp/layout/strategies/llc.py`
- `src/psim_mcp/layout/strategies/boost_pfc.py`

### 수정

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/shared/state_store.py`
- `src/psim_mcp/synthesis/legacy_layout_adapter.py`
- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/routing/router.py`
- `src/psim_mcp/data/component_library.py`

## Layout Engine 인터페이스 초안

```python
class LayoutStrategy(Protocol):
    def build_layout(
        self,
        graph: CircuitGraph,
        preferences: dict[str, object] | None = None,
    ) -> SchematicLayout:
        ...
```

```python
def generate_layout(
    graph: CircuitGraph,
    preferences: dict[str, object] | None = None,
) -> SchematicLayout:
    ...
```

### service 연동 초안

```python
graph = synthesize_topology(topology, requirements)
layout = generate_layout(graph, preferences=spec.layout_preferences)
routing = generate_routing(graph, layout)
```

즉 Phase 3부터는 service가 `layout`을 별도 step으로 다뤄야 한다.

## tool surface와 backend에 미치는 영향

Phase 3는 layout을 first-class payload로 승격하는 단계이지, tool surface를 바꾸는 단계는 아니다.

- `preview_circuit()`는 graph와 함께 layout을 저장한다.
- `confirm_circuit()`는 preview store에 저장된 layout을 재사용한다.
- `create_circuit_direct()`와 `SimulationService.create_circuit()`는 layout을 직접 소비하거나 legacy projection 경계를 명시해야 한다.
- renderer는 layout consumer가 되고, backend별 geometry 추론 책임은 줄어든다.
- 내부 구현이 바뀌어도 `design_circuit`, `preview_circuit`, `confirm_circuit`의 응답 계약은 유지해야 한다.

저장 계약도 같이 바뀌어야 한다.

- preview payload는 최소한 `graph`, `layout`, `legacy renderable fallback`을 함께 저장한다.
- `payload_version`이 없는 기존 preview/session payload는 compatibility adapter를 통해 읽는다.
- confirm/create/simulation 경로는 layout을 새로 추론하지 않고 저장된 payload를 우선 소비한다.

## 현재 코드 기준 세부 설계 포인트

## 1. `svg_renderer.py`에서 걷어내야 할 책임

현재 파일은 다음을 사실상 같이 한다.

- 심볼 SVG 렌더링
- component 기본 geometry 가정
- component preparation 재실행
- routing helper 재호출

Phase 3 이후 `svg_renderer.py`는 아래만 해야 한다.

- layout를 받아 symbol을 그림
- routing 결과를 line/polyline으로 그림
- junction, label, style을 적용

즉 renderer는 geometry를 추론하면 안 된다.
low-level draw primitive를 조합해 회로 구조를 다시 만드는 계층이 아니라, layout/routing payload를 소비하는 backend여야 한다.

## 2. `router.py`에서 걷어내야 할 layout 책임

현재 `prepare_components_for_layout()`는 명백히 layout 전단 책임이다.

예:

- simple part direction inference
- component direction heuristic

Phase 3 이후 이 로직은 `layout engine`으로 이동해야 한다.

`router.py`는 오직 아래만 남는 게 맞다.

- pin anchor resolution
- routing input normalization
- segment generation

## 3. `generators/layout.py`의 역할 재정의

현재 이 파일은 사실상 transition legacy helper다.

Phase 3 이후 방향:

- 새 `layout` 계층과 분리
- 가능하면 이름도 `legacy_psim_layout_helpers.py` 같은 식으로 재정의
- generator가 직접 import하지 않도록 막기

## topology별 layout 전략

## A. Buck

### 목표 레이아웃

- power flow 좌에서 우
- input source 좌측
- switch와 freewheel diode는 한 switch region 안에 배치
- inductor는 switch node 오른쪽
- capacitor/load는 출력 우측에 수직 shunt
- ground rail은 하단 공통 기준선

### 제약 예

- `V1` left of `SW1`
- `SW1`, `D1` same block
- `L1` right of `SW1`
- `C1`, `R1` align to output column
- `G1` below `SW1`

### 1차 placement 규칙

```text
input_region      switch_region         output_region
V1/GND1      ->   SW1 D1 G1       ->    L1 C1 R1
```

## B. Flyback

### 목표 레이아웃

- primary left
- transformer center
- secondary right
- clamp/snubber는 transformer primary 상단
- output rectifier/filter는 secondary right
- isolation boundary를 region으로 표시 가능

### 제약 예

- `VIN`, `SW1`, `clamp` in `primary_region`
- `T1` centered on isolation boundary
- `D1`, `COUT`, `LOAD` in `secondary_region`

## C. LLC

### 목표 레이아웃

- input and half-bridge left
- resonant tank center-left
- magnetizing branch near transformer primary
- transformer center
- bridge rectifier center-right
- output filter far right

### 필수 region

- `input_region`
- `half_bridge_region`
- `resonant_region`
- `magnetic_region`
- `secondary_region`
- `output_region`

### 중요한 이유

LLC는 block 의미를 배치에 반영하지 않으면 회로가 읽히지 않는다.

## symbol variant 결정

layout 단계에서 아래도 함께 결정해야 한다.

- 2-pin generic symbol인지
- multi-pin special symbol인지
- horizontal/vertical variant인지
- mirrored variant가 필요한지

예:

- `IdealTransformer` -> `transformer_4pin_horizontal`
- `DiodeBridge` -> `diode_bridge_4pin_box`
- `MOSFET` -> `mosfet_vertical_power`

이걸 renderer가 임의 추정하면 다시 계층이 섞인다.

## Phase 3에서 필요한 데이터화

### component-level layout hints

`component_library.py` 또는 별도 registry에 아래가 필요하다.

- preferred symbol variants
- pin anchor policies
- default orientations
- minimum bounding box

### topology-level layout metadata

`topology_metadata.py` 또는 별도 `layout_registry.py`에 아래가 필요하다.

- preferred flow direction
- isolated/non-isolated region template
- rail policies
- block ordering

## migration 전략

### Step 1. legacy adapter 유지

### Step 1.5. payload contract 유지

- `preview_payload_v1` 또는 동등한 versioned payload 계약을 먼저 고정한다.
- layout 도입 전후에도 `preview_circuit`, `confirm_circuit`, `create_circuit_direct`, `SimulationService.create_circuit()` 경로가 같은 payload 버전을 읽도록 맞춘다.

처음에는 아래 경로를 같이 유지한다.

- new: `CircuitGraph -> LayoutEngine -> Routing`
- old: `generator -> legacy positioned components`

### Step 2. buck 우선 전환

`buck`을 first layout target으로 삼는다.

이유:

- topology 구조가 단순하다
- 현재 preview 문제 관찰이 쉬움
- ground rail, switch node, output region 규칙이 명확하다

### Step 3. flyback, llc 확장

복잡한 절연형/공진형 topology에 region 개념을 확장한다.

## 완료 기준

아래가 만족되면 Phase 3 완료로 본다.

- `buck`, `flyback`, `llc`가 new layout engine으로 layout 생성
- `svg_renderer.py`가 layout geometry를 재추론하지 않음
- `prepare_components_for_layout()`가 routing 전처리에서 제거 또는 축소됨
- multi-pin component가 layout에서 symbol variant를 명시적으로 받음
- preview/store payload에 layout이 versioned contract로 저장됨
- 내부 layout 경로 전환 후에도 MCP/tool surface 응답 계약은 변하지 않음

## 테스트 전략

### 단위 테스트

- `tests/unit/test_layout_models.py`
- `tests/unit/test_layout_buck_strategy.py`
- `tests/unit/test_layout_flyback_strategy.py`
- `tests/unit/test_layout_llc_strategy.py`

### snapshot 테스트

- layout component positions snapshot
- region snapshot
- symbol_variant snapshot

### 통합 테스트

- `CircuitGraph -> Layout -> SVG` path
- preview store에 layout 저장 여부

## 최종 정리

Phase 3의 핵심은 좌표를 "어떻게 찍을까"가 아니다.

핵심은 다음 전환이다.

> topology generator가 예제 좌표를 직접 내보내는 구조에서
> graph 의미를 기반으로 별도 layout strategy가 회로도 배치를 결정하는 구조로 바꾸는 것

이 단계가 서야 Phase 4 routing이 geometry 품질을 본격적으로 개선할 수 있다.
