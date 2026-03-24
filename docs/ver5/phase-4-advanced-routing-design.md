# Phase 4 상세: Advanced Routing 설계 문서
작성일: 2026-03-24

## 목적

Phase 4의 목표는 `CircuitGraph + SchematicLayout`를 입력으로 받아
읽기 좋은 schematic wire geometry를 만드는 `Advanced Routing` 계층을 도입하는 것이다.

현재 `src/psim_mcp/routing/router.py`는 아래 역할을 동시에 수행한다.

- pin position 계산
- simple direction inference의 일부 후처리
- ordered net을 chain connection으로 변환
- 단순 L자 orthogonal segment 생성
- 중복 segment 제거

이 문서는 이 구조를 `routing engine`으로 확장하기 위한 상세 설계를 정의한다.

## 왜 새 Routing 단계가 필요한가

현재 라우팅의 개선점은 분명하다.

- preview와 bridge가 같은 canonical geometry를 공유하기 시작함
- 중복 segment 제거가 들어감
- multi-pin component symbol 지원이 일부 늘어남

하지만 readable schematic 관점에선 한계가 크다.

- 큰 우회 루프가 많음
- block 간 연결이 trunk/branch 형태가 아님
- ground / power rail 정렬이 약함
- transformer, bridge 주변 다핀 라우팅이 일관되지 않음
- crossing과 detour를 비용 함수로 다루지 않음

즉 지금은 `일관성`은 올랐지만 `회로도 품질`은 아직 낮다.

## Routing Engine의 입력과 출력

### 입력

- `CircuitGraph`
- `SchematicLayout`
- pin anchor registry
- routing preferences

### 출력

- `WireRouting`

즉 라우팅은 layout 이후 단계여야 한다.
layout 없이 routing이 읽기 좋은 geometry를 만들기는 어렵다.

## 제안 모델

### 1. RoutedSegment

```python
from dataclasses import dataclass, field

@dataclass
class RoutedSegment:
    id: str
    net_id: str
    x1: int
    y1: int
    x2: int
    y2: int
    role: str | None = None
    layer: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
```

### 2. JunctionPoint

```python
@dataclass
class JunctionPoint:
    x: int
    y: int
    net_id: str
```

### 3. WireRouting

```python
@dataclass
class WireRouting:
    topology: str
    segments: list[RoutedSegment]
    junctions: list[JunctionPoint] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

### 4. RoutingPreference

```python
@dataclass
class RoutingPreference:
    style: str = "schematic"
    use_ground_rail: bool = True
    minimize_crossings: bool = True
    prefer_symmetry: bool = True
    prefer_trunk_branch: bool = True
```

## 파일 구조 제안

### 신설

- `src/psim_mcp/routing/engine.py`
- `src/psim_mcp/routing/models.py`
- `src/psim_mcp/routing/anchors.py`
- `src/psim_mcp/routing/costs.py`
- `src/psim_mcp/routing/strategies/buck.py`
- `src/psim_mcp/routing/strategies/flyback.py`
- `src/psim_mcp/routing/strategies/llc.py`
- `src/psim_mcp/routing/metrics.py`

### 수정

- `src/psim_mcp/routing/router.py`
- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/bridge/bridge_script.py`
- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/shared/state_store.py`
- `src/psim_mcp/data/component_library.py`

## 인터페이스 초안

```python
class RoutingStrategy(Protocol):
    def route(
        self,
        graph: CircuitGraph,
        layout: SchematicLayout,
        preferences: RoutingPreference | None = None,
    ) -> WireRouting:
        ...
```

```python
def generate_routing(
    graph: CircuitGraph,
    layout: SchematicLayout,
    preferences: RoutingPreference | None = None,
) -> WireRouting:
    ...
```

## tool surface와 backend에 미치는 영향

Phase 4는 routing을 backend 공통 geometry payload로 고정하는 단계이지, tool surface를 바꾸는 단계는 아니다.

- `preview_circuit()`는 `WireRouting`을 저장하고 SVG preview에 그대로 사용한다.
- `confirm_circuit()`는 같은 `WireRouting` payload를 bridge에 넘긴다.
- `SimulationService.create_circuit()`도 가능하면 같은 routing payload를 소비하고, 불가하면 legacy-only 경계를 명시해야 한다.
- routing은 backend마다 다시 계산하지 않고, backend adapter가 같은 geometry를 소비해야 한다.
- service 응답 계약은 유지하고 내부 routing source of truth만 교체한다.

## routing의 책임 경계

### routing이 해야 하는 것

- pin anchor를 기준으로 geometry 생성
- trunk/branch 구조로 wire 배치
- rail/bus 정렬
- segment dedupe
- junction 생성
- crossing 비용 최소화

### routing이 하면 안 되는 것

- component orientation 변경
- component position 재계산
- symbol variant 결정
- topology 구조 추론

이건 각각 layout 또는 synthesis 책임이다.

## 현재 코드 기준 문제점과 이동 방향

## 1. `route_connections_to_segments()`의 한계

현재 방식:

- ordered connection pair로 만든 뒤
- 각 pair에 대해 단순 orthogonal L자 경로 생성

문제:

- 3개 이상 pin이 붙은 net이 chain으로만 해석됨
- trunk 없이 긴 우회선이 많아짐
- 회로도 관점의 branch 표현이 약함

개선 방향:

- `net role`과 `block relation`을 보고 trunk point 생성
- multi-pin net은 chain이 아니라 trunk-branch로 생성

## 2. `build_pin_position_map()`의 역할은 유지하되 registry화 필요

이 함수는 유지 가능하지만,
현재 `_PIN_ANCHOR_MAP`이 router 내부 상수인 건 바람직하지 않다.

개선 방향:

- `routing/anchors.py`
- 또는 `component_library.py`의 symbol/pin geometry metadata

로 이동

## 3. `prepare_components_for_layout()`는 routing 계층에서 제거 대상

이 함수는 Phase 3 이후 layout engine 책임이다.
Phase 4 시점에는 routing이 component direction을 고치면 안 된다.

## topology별 routing 전략

## A. Buck

### 목표

- 입력 positive line은 상단 또는 좌측 trunk
- ground는 하단 rail
- switch node는 중앙 짧은 junction
- output positive는 인덕터 이후 우측 trunk
- capacitor/load는 output trunk에서 수직 branch

### 기대 geometry

```text
VIN ---- SW ---- L ----+---- LOAD
          |            |
          D           COUT
          |            |
GND -------------------+---------
```

즉 chain보다 branch가 중요하다.

## B. Flyback

### 목표

- primary와 secondary 사이 isolation boundary 존중
- transformer를 기준으로 primary/secondary wiring 분리
- clamp/snubber branch를 transformer primary 근처에 짧게 유지
- output rectifier/filter branch 정리

## C. LLC

### 목표

- half-bridge midpoint에서 resonant tank가 자연스럽게 이어짐
- `Cr -> Lr -> transformer primary`가 main trunk
- `Lm`은 primary node에서 vertical branch
- secondary rectifier는 transformer secondary에서 짧게 연결
- output capacitor/load는 rectified output trunk에서 branch

## routing 알고리즘 제안

## 1. trunk-and-branch routing

다핀 net에 대해:

1. anchor 후보 계산
2. net role 기반 trunk axis 선택
3. trunk segment 생성
4. 각 pin에서 trunk로 branch 연결

예:

- `ground` -> horizontal trunk
- `output_positive` -> horizontal trunk
- `gate_drive` -> short direct route

## 2. region-aware routing

layout region을 이용해:

- primary와 secondary를 불필요하게 가로지르지 않기
- control region 배선을 power path에서 분리
- branch 출발점을 region edge 근처에 맞추기

## 3. symmetry-aware routing

다음 topology에서 중요하다.

- half_bridge
- full_bridge
- three_phase_inverter
- LLC half-bridge

좌우 대칭 또는 상하 대칭을 비용 함수에 반영해야 한다.

## 4. crossing minimization

간단한 비용 함수 예:

```text
cost =
  crossing_penalty * crossing_count +
  detour_penalty * total_length +
  bend_penalty * bend_count +
  asymmetry_penalty * asymmetry_score
```

초기엔 완전 최적화보다 heuristic scoring이면 충분하다.

## net role 기반 기본 정책

다음 role이 있으면 routing 품질이 많이 올라간다.

- `ground`
- `input_positive`
- `switch_node`
- `output_positive`
- `gate_drive`
- `feedback`
- `sense`

예:

- `ground` -> bottom rail 선호
- `gate_drive` -> shortest route 선호
- `feedback` -> power trunk와 분리

## bridge와 SVG의 역할 재정의

### SVG Renderer

- `WireRouting`을 받아 그대로 그림
- junction도 routing이 준 좌표만 그림
- geometry 재추론 금지

즉 SVG는 routing engine의 결과를 소비하는 backend이지, 별도의 routing 재해석 계층이 아니다.

### PSIM Bridge

- `WireRouting`을 받아 동일 순서/동일 geometry로 wire 생성
- fallback path는 유지하더라도 main path는 routing 결과 소비

즉 bridge도 main path에서는 routing consumer여야 하며, backend 차이 때문에 routing을 다시 만들면 안 된다.

이 단계가 돼야 preview와 actual PSIM geometry 차이가 사라진다.

## migration 전략

### Step 1. 기존 `router.py`를 compatibility facade로 유지

- 외부 호출은 `resolve_wire_segments()` 유지
- 내부 구현은 gradually new engine으로 위임

### Step 2. `buck` 전략 우선 구현

이유:

- trunk/branch 효과가 가장 잘 드러남
- ground rail과 switch node 규칙이 명확함

### Step 3. `llc` 전략 구현

이유:

- multi-pin, multi-branch 구조가 복잡해 고급 routing 가치가 큼

### Step 4. bridge main path를 `WireRouting` 소비로 전환

### Step 5. service/backend contract 정리

- preview payload에 `routing`과 `payload_version`을 같이 저장한다.
- `preview_circuit`, `confirm_circuit`, `create_circuit_direct`, `SimulationService.create_circuit()`가 어떤 routing payload를 읽는지 명시한다.
- backend geometry mismatch는 adapter 책임으로 제한하고 rerouting을 기본 전략으로 두지 않는다.

## 완료 기준

- `buck`, `flyback`, `llc`에서 segment 중복, 큰 루프, 불필요한 detour가 감소
- routing이 `layout`을 입력으로 사용
- preview와 bridge가 동일 routing output을 사용
- router 내부 방향 추정 heuristic이 제거 또는 최소화
- backend별 geometry mismatch가 rerouting 없이 통제됨
- 가능하면 simulation/create도 동일 routing payload를 소비하고, 예외 topology는 capability matrix에 legacy-only로 표시됨

## 테스트 전략

### 단위 테스트

- `tests/unit/test_routing_trunk_branch.py`
- `tests/unit/test_routing_buck_strategy.py`
- `tests/unit/test_routing_llc_strategy.py`
- `tests/unit/test_routing_costs.py`
- `tests/unit/test_routing_metrics.py`

### 회귀 테스트

- buck SVG snapshot
- llc SVG snapshot
- boost_pfc SVG snapshot

### 품질 메트릭

- crossing count
- duplicate segment count
- total detour length
- junction consistency count
- branch count per multi-pin net

## 최종 정리

Phase 4의 핵심은 단순히 선을 더 예쁘게 긋는 것이 아니다.

핵심은 이 전환이다.

> `ordered connection pair를 기계적으로 L자 선분으로 바꾸는 구조`에서
> `graph 의미와 layout region을 기준으로 readable schematic geometry를 합성하는 구조`로 바꾸는 것

이 단계가 완료돼야 SVG의 "어색함"이 구조적으로 줄어든다.
