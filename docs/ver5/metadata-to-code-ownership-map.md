# 메타데이터-코드 소유권 매핑 문서
작성일: 2026-03-24

## 목적

`circuit-metadata-schema.md`에서 정의한 회로 기본정보 메타데이터를
실제 코드베이스의 어느 파일이 담당해야 하는지 정리한다.

이 문서의 목표는 다음이다.

- 메타데이터 종류별 현재 소유 파일을 식별
- 구조상 잘못된 ownership을 분리
- 향후 `ver5` 아키텍처 기준으로 목표 소유 파일을 정의
- 단계별 migration 우선순위를 제시

즉 이 문서는 `메타데이터 스키마`와 `실제 코드 리팩터링` 사이의 연결표다.

## 기본 원칙

메타데이터 ownership은 아래 원칙을 따라야 한다.

1. `의미 metadata`와 `실행 metadata`를 분리한다
2. generator는 metadata의 소비자여야지, primary 저장소가 되면 안 된다
3. renderer와 bridge는 metadata를 추론하지 않고 registry를 소비해야 한다
4. topology rule, symbol rule, routing rule은 각자 별도 registry를 가져야 한다

## 전체 ownership 구조

목표 구조는 아래와 같다.

```text
data/
  topology_metadata.py
  component_library.py
  design_rule_registry.py
  symbol_registry.py
  layout_strategy_registry.py
  routing_policy_registry.py
  bridge_mapping_registry.py

intent/
  models.py
  extractors.py
  ranker.py
  spec_builder.py

synthesis/
  models.py
  topologies/*.py

layout/
  models.py
  strategies/*.py

routing/
  models.py
  strategies/*.py
```

## 1. Topology Metadata

### 메타데이터 내용

- topology identity
- domain compatibility
- isolation
- power range
- required fields
- design-ready fields
- optional blocks
- default options

### 현재 소유 파일

- `src/psim_mcp/data/topology_metadata.py`
- 부분적으로 `src/psim_mcp/parsers/keyword_map.py`
- 부분적으로 각 `src/psim_mcp/generators/*.py`

### 현재 문제

- topology identity는 `topology_metadata.py`에 있는데
  use-case/topology shortcut은 `keyword_map.py`에 분산돼 있다
- optional block나 required block 정보는 generator 안 주석/구조로 숨어 있다
- power suitability나 topology structural completeness 정보가 충분히 formalized되지 않았다

### 목표 소유 파일

- primary: `src/psim_mcp/data/topology_metadata.py`
- 확장 분리 권장:
  - `src/psim_mcp/data/topology_registry.py`
  - 또는 `src/psim_mcp/data/topology_metadata.py` 유지 + block/rule 필드 확장

### 유지할 것

- `required_fields`
- `design_ready_fields`
- `isolated`
- `single_voltage_role`

### 추가해야 할 것

- `required_blocks`
- `optional_blocks`
- `required_component_roles`
- `required_net_roles`
- `layout_family`
- `routing_family`
- `power_range`
- `bridge_constraints`

## 2. Component Metadata

### 메타데이터 내용

- pins
- pin aliases
- default params
- symbol family
- anchor policy
- PSIM type mapping related identity

### 현재 소유 파일

- `src/psim_mcp/data/component_library.py`
- 부분적으로 `src/psim_mcp/utils/svg_renderer.py`
- 부분적으로 `src/psim_mcp/routing/router.py`
- 부분적으로 `src/psim_mcp/bridge/bridge_script.py`

### 현재 문제

- component identity와 pin 정보 자체는 이미 상당 부분 `component_library.py`에 중앙화돼 있다
- 특히 pin side, terminal alias, `PORT_PIN_GROUPS`, `build_port_pin_map()`는 중앙 registry 성격을 가진다
- 하지만 symbol anchor 정보는 아직 `svg_renderer.py`, `router.py` 내부 상수로 분산
- bridge mapping은 `bridge_script.py` 내부 상수에 존재하고, 일부는 bridge 런타임 제약 때문에 인라인 유지된다

즉 현재 상태는 `완전 분산`보다는 `구조 metadata는 일부 중앙화됐지만 geometry/emission metadata가 여전히 분산`된 상태다.

### 목표 소유 파일

- primary structural ownership: `src/psim_mcp/data/component_library.py`
- symbol-level ownership: `src/psim_mcp/data/symbol_registry.py`
- bridge-level ownership: `src/psim_mcp/data/bridge_mapping_registry.py`

### 유지할 것

- component type
- pins
- pin aliases
- library lookup
- `LEFT_PINS`, `RIGHT_PINS`
- `PORT_PIN_GROUPS`
- `build_port_pin_map()`

### 옮겨야 할 것

- `_PIN_ANCHOR_MAP` from `svg_renderer.py`
- `_PIN_ANCHOR_MAP` from `router.py`
- symbol variant 관련 하드코딩
- bridge-specific PSIM mapping 상수

## 3. Design Rule Metadata

### 메타데이터 내용

- sizing rules
- feasibility rules
- default values
- forbidden combinations
- variant selection policy

### 현재 소유 파일

- `src/psim_mcp/generators/*.py`
- `src/psim_mcp/generators/constraints.py`
- 부분적으로 `src/psim_mcp/data/spec_mapping.py`

### 현재 문제

- sizing rule가 generator 안에 박혀 있다
- feasibility는 `constraints.py`에 있지만 topology synthesis와 느슨하게 연결돼 있다
- default design assumption이 generator 구현 내부에 숨어 있다

### 목표 소유 파일

- `src/psim_mcp/data/design_rule_registry.py`
- `src/psim_mcp/synthesis/sizing.py`
- `src/psim_mcp/generators/constraints.py`는 validator-style feasibility layer로 축소

### 유지할 것

- 설계 제약 검증 함수

### 옮겨야 할 것

- topology sizing default
- variant-specific selection rule
- structure-independent calculation rule

## 4. Intent Metadata

### 메타데이터 내용

- keyword candidates
- use-case hints
- field aliases
- clarification priorities
- ranking hints

### 현재 소유 파일

- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/parsers/keyword_map.py`
- `src/psim_mcp/data/topology_metadata.py`

### 현재 문제

- extractor metadata와 ranking metadata와 final decision logic이 한데 섞여 있다
- `keyword_map.py`가 candidate registry인지 확정기인지 경계가 흐리다

### 목표 소유 파일

- `src/psim_mcp/intent/extractors.py`
- `src/psim_mcp/intent/ranker.py`
- `src/psim_mcp/intent/spec_builder.py`
- `src/psim_mcp/parsers/keyword_map.py`는 candidate dictionary로 축소

### 유지할 것

- keyword inventory
- field alias table

### 옮겨야 할 것

- topology finalization logic
- clarification decision logic
- voltage role resolution policy 일부

## 5. Circuit Graph Metadata

### 메타데이터 내용

- component roles
- net roles
- block structure
- design trace

### 현재 소유 파일

- 사실상 없음
- 일부 구조 정보가 `src/psim_mcp/generators/*.py`의 component/nets에 암묵적으로 존재

### 현재 문제

- graph metadata가 코드 상 명시 모델이 아니라 dict 조립 결과에 숨어 있다

### 목표 소유 파일

- `src/psim_mcp/synthesis/models.py`
- `src/psim_mcp/synthesis/graph.py`
- `src/psim_mcp/synthesis/topologies/*.py`

### Phase 2 이후 primary owner

- `synthesis` 계층

## 6. Layout Metadata

### 메타데이터 내용

- flow direction
- region template
- block ordering
- component preferred orientation
- symbol variant

### 현재 소유 파일

- `src/psim_mcp/generators/layout.py`
- 각 `src/psim_mcp/generators/*.py`
- 부분적으로 `src/psim_mcp/utils/svg_renderer.py`
- 부분적으로 `src/psim_mcp/routing/router.py`

### 현재 문제

- layout rule가 generator에 직접 박혀 있다
- symbol variant 판단이 renderer에 있다
- orientation heuristic이 router에 있다

### 목표 소유 파일

- `src/psim_mcp/layout/models.py`
- `src/psim_mcp/layout/engine.py`
- `src/psim_mcp/layout/strategies/*.py`
- `src/psim_mcp/data/layout_strategy_registry.py`
- symbol-related geometry는 `src/psim_mcp/data/symbol_registry.py`

### 유지할 것

- `generators/layout.py`는 transition helper로만 한시 유지 가능

### 옮겨야 할 것

- topology별 position/direction 규칙
- component region assignment
- symbol variant selection
- direction inference heuristic

## 7. Routing Metadata

### 메타데이터 내용

- net role routing policy
- rail policy
- trunk policy
- control signal policy
- multi-pin routing strategy

### 현재 소유 파일

- `src/psim_mcp/routing/router.py`
- 부분적으로 `src/psim_mcp/utils/svg_renderer.py`

### 현재 문제

- routing rule, anchor policy, fallback geometry 규칙이 router 내부 상수에 묶여 있다
- topology별 routing 특성이 별도 policy로 분리되지 않았다
- 다만 port alias 자체는 `component_library.py`로 일부 중앙화되어 있으므로,
  실제 미분리 대상은 `routing policy`와 `symbol anchor geometry`다

### 목표 소유 파일

- `src/psim_mcp/routing/models.py`
- `src/psim_mcp/routing/engine.py`
- `src/psim_mcp/routing/strategies/*.py`
- `src/psim_mcp/data/routing_policy_registry.py`
- pin anchor geometry는 `src/psim_mcp/data/symbol_registry.py`

## 8. Emission Metadata

### 메타데이터 내용

- PSIM element type map
- parameter name map
- fallback port group
- symbol render variant
- label policy

### 현재 소유 파일

- `src/psim_mcp/bridge/bridge_script.py`
- `src/psim_mcp/utils/svg_renderer.py`

### 현재 문제

- emission metadata가 구현 내부 상수로 들어가 있다
- registry가 아니라 code path 안쪽에 숨어 있다
- 추가로 `bridge_script.py`는 PSIM의 별도 Python runtime에서 실행되므로
  단순 import 기반 registry 이동이 바로 가능하지 않다

### 목표 소유 파일

- `src/psim_mcp/data/bridge_mapping_registry.py`
- `src/psim_mcp/data/symbol_registry.py`

### 유지할 것

- 실제 bridge API 호출 로직은 `bridge_script.py`
- SVG draw logic은 `svg_renderer.py`
- bridge runtime이 직접 읽을 수 있는 frozen export 또는 generated snapshot

### 옮겨야 할 것

- `_PSIM_TYPE_MAP`
- `_PARAM_NAME_MAP`
- `_FALLBACK_PORT_PIN_GROUPS`
- symbol-specific anchor/render selection table

### 구현 시 주의

- `bridge_mapping_registry.py`는 런타임 import만 가정하면 안 된다
- 현실적인 1차안:
  - source of truth는 `data/bridge_mapping_registry.py`
  - bridge가 읽는 별도 generated JSON/py snapshot을 배포
  - `bridge_script.py`는 그 snapshot을 읽거나, 실패 시 인라인 fallback 사용

## 9. Preview / Session State Metadata

### 메타데이터 내용

- preview token payload schema
- design session payload schema
- payload version
- backward compatibility rule

### 현재 소유 파일

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/shared/state_store.py`
- 부분적으로 `src/psim_mcp/services/simulation_service.py`

### 현재 문제

- 저장 payload가 버전 없이 dict로 저장된다
- confirm/create가 같은 payload를 재사용하므로 필드 변경 리스크가 높다
- design session과 preview payload의 schema가 코드 상 명시 모델이 아니다

### 목표 소유 파일

- `src/psim_mcp/shared/state_store.py`
- `src/psim_mcp/services/circuit_design_service.py`
- 필요 시 `src/psim_mcp/models/schemas.py` 또는 `src/psim_mcp/shared/protocols.py`

### 유지할 것

- TTL 기반 store 자체
- token lookup / delete 책임

### 옮겨야 할 것

- preview payload schema definition
- design session schema definition
- payload version compatibility rule

## 메타데이터별 현재/목표 ownership 요약

| 메타데이터 | 현재 중심 파일 | 목표 중심 파일 |
| --- | --- | --- |
| Topology | `data/topology_metadata.py`, `parsers/keyword_map.py`, `generators/*.py` | `data/topology_metadata.py` |
| Component | `data/component_library.py`, `svg_renderer.py`, `router.py`, `bridge_script.py` | `data/component_library.py`, `data/symbol_registry.py`, `data/bridge_mapping_registry.py` |
| Design Rule | `generators/*.py`, `generators/constraints.py` | `data/design_rule_registry.py`, `synthesis/sizing.py` |
| Intent | `intent_parser.py`, `keyword_map.py` | `intent/*`, `parsers/keyword_map.py` |
| Circuit Graph | 암묵적으로 generator 내부 | `synthesis/models.py`, `synthesis/topologies/*.py` |
| Layout | `generators/layout.py`, `generators/*.py`, `router.py`, `svg_renderer.py` | `layout/*`, `data/layout_strategy_registry.py` |
| Routing | `routing/router.py` | `routing/*`, `data/routing_policy_registry.py` |
| Emission | `svg_renderer.py`, `bridge_script.py` | `data/symbol_registry.py`, `data/bridge_mapping_registry.py` |
| Preview / Session State | `circuit_design_service.py`, `state_store.py`, `simulation_service.py` | `shared/state_store.py`, shared schema model |

## 단계별 migration 우선순위

## Phase 1

우선 ownership 분리:

- Design Rule
- Circuit Graph
- 일부 Topology Metadata
- Preview / Session State Metadata

작업:

- sizing rule를 generator 밖으로 뺌
- synthesize 결과를 구조 중심으로 만듦
- preview payload versioning 도입

## Phase 2

우선 ownership 분리:

- Circuit Graph Metadata
- Design Trace

작업:

- `synthesis/models.py`와 graph validator 도입

## Phase 3

우선 ownership 분리:

- Layout Metadata
- Symbol Metadata 일부

작업:

- `layout/*` 도입
- `svg_renderer.py`, `router.py`에서 layout 추정 제거

## Phase 4

우선 ownership 분리:

- Routing Metadata
- Anchor Policy

작업:

- `routing_policy_registry.py`
- topology별 routing strategy

## Phase 5

우선 ownership 분리:

- Intent Metadata
- Candidate Ranking Metadata
- Clarification Metadata

작업:

- `intent/*` 계층 도입
- `keyword_map.py` 역할 축소

## 실무적으로 먼저 손대야 할 파일

현재 기준 최우선은 아래다.

1. `src/psim_mcp/generators/base.py`
2. `src/psim_mcp/generators/buck.py`
3. `src/psim_mcp/services/circuit_design_service.py`
4. `src/psim_mcp/data/topology_metadata.py`
5. `src/psim_mcp/data/component_library.py`
6. `src/psim_mcp/services/simulation_service.py`
7. `src/psim_mcp/shared/state_store.py`
8. `src/psim_mcp/routing/router.py`
9. `src/psim_mcp/utils/svg_renderer.py`
10. `src/psim_mcp/bridge/bridge_script.py`

이 파일들이 현재 메타데이터 ownership이 가장 많이 섞여 있는 지점이다.

## 최종 정리

지금 문제는 단순히 코드가 하드코딩돼 있다는 게 아니다.
더 정확히는 `회로 기본정보 메타데이터의 ownership이 여러 구현 파일에 흩어져 있다`는 점이다.

따라서 ver5 전환의 핵심 중 하나는 아래다.

> 어떤 메타데이터를 어디서 소유하고,
> 어느 계층이 그것을 생성하고,
> 어느 계층이 그것을 소비해야 하는지
> ownership을 분리하는 것

이 문서의 역할은 그 ownership 기준을 고정하는 것이다.
