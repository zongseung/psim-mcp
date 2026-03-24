# Phase 2 상세: CircuitGraph 모델 도입 설계
작성일: 2026-03-24

## 목적

Phase 1이 `generator -> graph assembler + sizing` 분리라면,
Phase 2의 핵심은 그 결과를 진짜 `CircuitGraph 중심 파이프라인`으로 끌어올리는 것이다.

이 문서는 아래를 구체적으로 정의한다.

- `CircuitGraph`가 정확히 무엇을 담아야 하는지
- 현재 `components + nets` dict 흐름을 어떻게 graph 모델로 바꿀지
- 어떤 파일을 수정해야 하는지
- service, validator, layout 준비 계층이 graph를 어떻게 소비해야 하는지

## Phase 2의 목표

Phase 2에서 끝내야 할 것은 다음이다.

- `CircuitGraph`를 canonical intermediate model로 도입
- `TopologySynthesisResult`가 내부적으로 `CircuitGraph`를 포함하거나 대체하도록 변경
- service가 raw dict보다 graph 객체를 기준으로 흐르도록 전환
- validator가 graph 수준에서 구조 검증을 수행하도록 분리
- 이후 Phase 3 layout engine이 graph를 직접 입력으로 받을 수 있게 만들기

중요한 점은 이 단계가 아직 `layout engine` 단계는 아니라는 것이다.
즉 Phase 2는 좌표를 만드는 단계가 아니라,
좌표를 만들기 전의 구조 표현을 제대로 세우는 단계다.

## 왜 Phase 2가 별도로 필요한가

Phase 1만으로는 generator 내부 결합을 줄일 수는 있어도,
시스템 전체가 여전히 `components/nets dict` 중심으로 움직일 가능성이 크다.

문제는 이 상태로는 아래가 어렵다는 점이다.

- optional block 모델링
- role 기반 layout
- functional block grouping
- topology structural validation
- intent traceability

즉 `구조를 합성했다`는 사실을 시스템이 이해하려면,
단순 component list보다 richer model이 필요하다.

## CircuitGraph의 정의

`CircuitGraph`는 회로의 전기적 구조를 표현하는 canonical object다.

이 모델은 다음을 포함해야 한다.

- component identity
- component type
- component role
- net membership
- block membership
- optional feature flags
- design provenance

포함하면 안 되는 것:

- absolute position
- symbol size
- SVG line geometry
- renderer-specific anchor

즉 `CircuitGraph`는 schematic drawing이 아니라 electrical structure다.

## 제안 모델

### 1. GraphComponent

```python
from dataclasses import dataclass, field

@dataclass
class GraphComponent:
    id: str
    type: str
    role: str | None = None
    parameters: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    block_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

역할:

- 회로 소자 정의
- role은 layout/validation에서 사용
- `tags`는 예: `["primary", "power_path"]`

### 2. GraphNet

```python
@dataclass
class GraphNet:
    id: str
    pins: list[str]
    role: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

예:

- `input_positive`
- `switch_node`
- `output_ground`
- `gate_drive`

### 3. FunctionalBlock

```python
@dataclass
class FunctionalBlock:
    id: str
    type: str
    role: str | None = None
    component_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

예:

- `input_stage`
- `primary_power_stage`
- `resonant_tank`
- `secondary_rectifier`
- `output_filter`
- `feedback_stage`

### 4. DesignDecisionTrace

```python
@dataclass
class DesignDecisionTrace:
    source: str
    key: str
    value: object
    confidence: float | None = None
    rationale: str | None = None
```

역할:

- 사용자 입력인지
- 시스템 기본값인지
- topology rule에서 나온 값인지

를 추적한다.

이건 나중에 `왜 이런 회로가 나왔는가`를 설명할 때 중요하다.

### 5. CircuitGraph

```python
@dataclass
class CircuitGraph:
    topology: str
    components: list[GraphComponent]
    nets: list[GraphNet]
    blocks: list[FunctionalBlock] = field(default_factory=list)
    design: dict[str, object] = field(default_factory=dict)
    simulation: dict[str, object] = field(default_factory=dict)
    traces: list[DesignDecisionTrace] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
```

이게 Phase 2의 중심 모델이다.

## 왜 block과 role이 꼭 필요한가

현재 `components + nets`만 있으면 전기적 연결은 표현되지만,
구조적 의미는 약하다.

예를 들어 `llc`에서 다음은 다르다.

- `Cr`, `Lr`, `Lm`, `T1`이 공진/자화/전력전달 관계라는 것
- `BD1`, `Cout`, `R1`이 2차측 정류/출력 필터라는 것
- `SW1`, `SW2`가 half-bridge leg라는 것

이걸 component list만으로는 안정적으로 표현하기 어렵다.

role과 block이 있으면:

- layout가 primary/secondary를 분리할 수 있고
- routing이 block-aware가 될 수 있고
- validator가 topology 완전성을 검사할 수 있다

## 현재 코드에서 바뀌는 흐름

현재:

```text
requirements
  -> generator.generate()
  -> components + nets
  -> service normalize
  -> routing
  -> SVG / bridge
```

Phase 2 이후:

```text
requirements
  -> generator.synthesize()
  -> CircuitGraph
  -> graph validation
  -> legacy layout adapter or future layout engine
  -> routing
  -> SVG / bridge
```

포인트는 `service normalize`보다 먼저 `graph validation`이 들어간다는 것이다.

## 파일별 수정 계획

### 직접 수정 대상

- `src/psim_mcp/synthesis/models.py`
- `src/psim_mcp/generators/base.py`
- `src/psim_mcp/synthesis/topologies/buck.py`
- `src/psim_mcp/synthesis/topologies/flyback.py`
- `src/psim_mcp/synthesis/topologies/llc.py`
- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/shared/state_store.py`
- `src/psim_mcp/validators/structural.py`
- `src/psim_mcp/validators/__init__.py`

### 신설 권장 대상

- `src/psim_mcp/synthesis/graph.py`
- `src/psim_mcp/synthesis/graph_builders.py`
- `src/psim_mcp/synthesis/trace.py`
- `src/psim_mcp/validators/graph.py`

## 인터페이스 초안

### A. synthesis 결과 인터페이스 재정의

Phase 1:

```python
TopologySynthesisResult(
    topology=...,
    components=...,
    nets=...,
)
```

Phase 2:

```python
@dataclass
class TopologySynthesisResult:
    graph: CircuitGraph
    legacy_renderable: dict | None = None
```

또는 더 단순하게:

```python
def synthesize(self, requirements: dict) -> CircuitGraph:
    ...
```

권장:

- 내부 표준은 `CircuitGraph`
- transition payload는 service가 별도로 관리

### B. graph validator 초안

신설:

- `src/psim_mcp/validators/graph.py`

```python
def validate_graph(graph: CircuitGraph) -> list[ValidationIssue]:
    ...
```

검사 항목:

- duplicate component id
- duplicate net id
- invalid pin reference
- required block missing
- required role missing
- orphan component
- orphan net

### C. graph builder helper 초안

신설:

- `src/psim_mcp/synthesis/graph_builders.py`

```python
def make_component(
    component_id: str,
    component_type: str,
    *,
    role: str | None = None,
    parameters: dict[str, object] | None = None,
    tags: list[str] | None = None,
    block_ids: list[str] | None = None,
) -> GraphComponent:
    ...

def make_net(
    net_id: str,
    pins: list[str],
    *,
    role: str | None = None,
    tags: list[str] | None = None,
) -> GraphNet:
    ...

def make_block(
    block_id: str,
    block_type: str,
    component_ids: list[str],
    *,
    role: str | None = None,
) -> FunctionalBlock:
    ...
```

의도:

- topology 파일에서 dict 직접 조립을 줄임

### D. service 저장 형태 초안

preview store 저장 예:

```python
{
    "circuit_type": "buck",
    "graph": graph.to_dict(),
    "components": legacy.components,
    "nets": legacy.nets,
    "wire_segments": ...,
}
```

즉 preview는 두 층을 같이 저장한다.

- canonical graph
- legacy renderable projection

또한 이 payload는 version 없이 저장하면 안 된다.

```python
{
    "payload_kind": "preview_payload",
    "payload_version": "preview_payload_v1",
    "circuit_type": "buck",
    "graph": graph.to_dict(),
    "components": legacy.components,
    "nets": legacy.nets,
    "wire_segments": ...,
}
```

하위 호환 규칙:

- `payload_version`이 없으면 legacy preview payload로 간주하고 compatibility adapter를 탄다.
- `confirm_circuit()`와 `create_circuit_direct()`는 `preview_payload_v1`을 우선 처리한다.
- `SimulationService`는 graph 직소비 또는 legacy projection 소비 중 어느 경로인지 문서와 코드에서 동일하게 표현해야 한다.

## topology별 graph 모델 예시

## 1. Buck

### component roles

- `V1`: `input_source`
- `SW1`: `main_switch`
- `D1`: `freewheel_diode`
- `L1`: `output_inductor`
- `C1`: `output_capacitor`
- `R1`: `load`
- `G1`: `gate_drive`

### blocks

- `input_stage`: `["V1"]`
- `switch_stage`: `["SW1", "D1", "G1"]`
- `output_filter`: `["L1", "C1", "R1"]`

### net roles

- `net_vin_sw`: `input_positive`
- `net_sw_junc`: `switch_node`
- `net_out`: `output_positive`
- `net_gnd`: `ground`
- `net_gate`: `drive_signal`

## 2. Flyback

필수 block 예시:

- `primary_input`
- `switch_primary`
- `magnetic_transfer`
- `secondary_rectifier`
- `output_filter`

옵션:

- `snubber`
- `clamp`
- `feedback`

## 3. LLC

필수 block 예시:

- `input_stage`
- `half_bridge`
- `resonant_tank`
- `magnetizing_branch`
- `transformer_stage`
- `secondary_rectifier`
- `output_filter`

이 구조가 없으면 layout에서 공진형 topology를 읽기 좋게 그릴 수 없다.

## `circuit_design_service.py` 변경 초안

현재 `_try_generate()`는 generator result를 dict로 기대한다.

Phase 2에서는 아래처럼 바뀌어야 한다.

```python
graph = synthesize_topology(circuit_type, req)
graph_issues = validate_graph(graph)
legacy = materialize_legacy_layout(graph)
```

그 뒤:

```python
resolved_components, resolved_connections, resolved_wire_segments = _resolve_wire_geometry(
    components=legacy.components,
    nets=legacy.nets,
)
```

즉 routing은 아직 legacy projection을 쓰지만,
service 내부의 canonical source는 graph가 된다.

## tool surface와 backend에 미치는 영향

Phase 2는 내부 canonical source를 graph로 바꾸는 단계이지, MCP/tool surface를 바꾸는 단계는 아니다.

- `preview_circuit()`는 graph를 저장하되 기존 preview 응답 계약을 유지한다.
- `confirm_circuit()`는 preview store에서 graph를 읽어 legacy projection 또는 다음 단계 payload로 투영한다.
- `create_circuit_direct()`는 graph-first 경로를 도입하되 응답 shape는 유지한다.
- `SimulationService.create_circuit()`도 graph 또는 graph에서 projection된 payload를 소비하는 경계를 명시해야 한다.
- backend는 아직 mixed-mode일 수 있지만 service entrypoint contract는 그대로 유지해야 한다.

## validators 계층 변경

현재 validator는 주로 `component.pin` 참조 유효성과 connection 중심이다.

Phase 2에서는 validator를 두 층으로 나눠야 한다.

### graph validator

- topology completeness
- role completeness
- block membership consistency
- pin reference sanity

### renderable validator

- positioned component consistency
- symbol compatibility
- routing input sanity

이 분리가 되면 Phase 3, 4에서 오류 위치를 더 정확히 잡을 수 있다.

## 마이그레이션 전략

### 1. buck부터 graph를 완전 도입

- graph builder
- graph validator
- service 저장

### 2. flyback, llc는 부분 도입

- component role
- block structure
- 핵심 net role

### 3. 나머지 topology는 legacy generator 유지

- graph 미지원 topology는 compatibility path로 유지

즉 Phase 2에서도 전면 전환보다 `mixed mode`를 허용해야 한다.

추가 원칙:

- mixed-mode 동안에도 tool surface는 topology별 capability matrix 기준으로만 달라져야 한다.
- preview/create/confirm/simulation 각 entrypoint가 어떤 graph 경로를 타는지 명시해야 한다.
- backend 경계는 service 내부 if-else에 묻지 말고 payload/version 계약으로 드러내야 한다.

## 완료 기준

아래를 만족하면 Phase 2 완료로 본다.

- `buck` preview/create가 `CircuitGraph`를 canonical source로 사용
- preview store에 graph가 저장됨
- graph validator가 동작함
- `flyback`, `llc`에서 최소 role/block 모델이 들어감
- 이후 layout engine이 graph를 직접 받을 수 있는 인터페이스가 확정됨
- `preview_payload_v1` 또는 동등한 versioned payload 계약이 문서와 코드에 반영됨
- `preview_circuit`, `confirm_circuit`, `create_circuit_direct`, `SimulationService.create_circuit()`의 entrypoint contract가 유지됨

## 테스트 권장안

### 단위 테스트

- `tests/unit/test_graph_models.py`
- `tests/unit/test_graph_builder.py`
- `tests/unit/test_graph_validator.py`
- `tests/unit/test_synthesize_buck_graph.py`

### 서비스 테스트

- preview store에 `graph` 포함 여부
- graph validation 실패 시 명확한 오류 노출

## 최종 정리

Phase 2의 본질은 `새 객체 하나 추가`가 아니다.

핵심은 이 전환이다.

> `components/nets dict를 조립해서 우연히 회로처럼 보이게 만드는 구조`에서
> `회로 구조 자체를 시스템이 이해하는 graph 중심 구조`로 넘어가는 것

이 단계가 제대로 서야 이후 Phase 3 layout과 Phase 4 routing이
예제 좌표가 아니라 구조 의미를 기준으로 동작할 수 있다.
