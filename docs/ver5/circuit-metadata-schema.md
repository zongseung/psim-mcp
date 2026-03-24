# 회로 기본정보 메타데이터 스키마
작성일: 2026-03-24

## 목적

이 문서는 `사용자 의도 기반 회로 합성기`가 회로를 만들기 위해
반드시 참고해야 하는 `회로 기본정보`를 하나의 스키마로 정리한 문서다.

핵심 원칙은 다음이다.

- 회로의 원리와 구조 규칙은 메타데이터로 참고해야 한다
- 특정 예제 회로도의 좌표나 배선을 정답처럼 복제하면 안 된다
- 메타데이터는 `Intent -> Spec -> Graph -> Layout -> Routing -> PSIM` 전 단계에서 재사용 가능해야 한다

## 전체 계층

회로 기본정보는 아래 7개 계층으로 나뉜다.

1. Topology Metadata
2. Component Metadata
3. Design Rule Metadata
4. Circuit Graph Metadata
5. Layout Metadata
6. Routing Metadata
7. Emission Metadata

## 1. Topology Metadata

회로 topology 자체에 대한 정보다.

### 필수 항목

- `topology_name`
- `display_name`
- `category`
- `conversion_type`
- `input_domain`
- `output_domain`
- `isolated`
- `supports_step_up`
- `supports_step_down`
- `supports_bidirectional`
- `typical_use_cases`
- `power_range`
- `required_fields`
- `design_ready_fields`
- `optional_fields`
- `single_voltage_role`

### 권장 항목

- `required_blocks`
- `optional_blocks`
- `required_component_roles`
- `required_net_roles`
- `default_options`
- `layout_family`
- `routing_family`
- `bridge_constraints`

### 예시

```json
{
  "topology_name": "flyback",
  "display_name": "Flyback Converter",
  "category": "dc_dc",
  "conversion_type": "dc_dc",
  "input_domain": "dc",
  "output_domain": "dc",
  "isolated": true,
  "supports_step_up": true,
  "supports_step_down": true,
  "supports_bidirectional": false,
  "typical_use_cases": ["adapter", "auxiliary_supply", "charger"],
  "power_range": "low",
  "required_fields": ["vin", "vout_target"],
  "design_ready_fields": ["vin", "vout_target"],
  "optional_fields": ["iout", "fsw"],
  "single_voltage_role": "vout_target",
  "required_blocks": ["primary_stage", "transformer_stage", "secondary_rectifier", "output_filter"]
}
```

## 2. Component Metadata

개별 부품에 대한 기본정보다.

### 필수 항목

- `component_type`
- `display_name`
- `pins`
- `pin_aliases`
- `default_parameters`
- `required_parameters`
- `psim_element_type`

### 권장 항목

- `role_candidates`
- `symbol_family`
- `symbol_variants`
- `default_orientation`
- `pin_anchor_policy`
- `bounding_box`
- `port_policy`
- `supports_rotation`

### 예시

```json
{
  "component_type": "MOSFET",
  "display_name": "MOSFET",
  "pins": ["drain", "source", "gate"],
  "pin_aliases": {
    "drain": ["drain", "pin1"],
    "source": ["source", "pin2"],
    "gate": ["gate", "control"]
  },
  "required_parameters": [],
  "default_parameters": {
    "on_resistance": 0.01
  },
  "psim_element_type": "MOSFET",
  "role_candidates": ["main_switch", "sync_switch"],
  "symbol_family": "mosfet",
  "symbol_variants": ["mosfet_vertical_power", "mosfet_horizontal"],
  "default_orientation": 270,
  "pin_anchor_policy": "mosfet_standard"
}
```

## 3. Design Rule Metadata

회로를 합성할 때 참고하는 전기적/구조적 규칙이다.

### 포함 항목

- `sizing_rules`
- `feasibility_rules`
- `default_design_values`
- `variant_selection_rules`
- `required_constraints`
- `forbidden_combinations`

### 예시

```json
{
  "topology": "buck",
  "sizing_rules": ["buck_inductor_rule", "buck_output_cap_rule"],
  "feasibility_rules": ["vout_less_than_vin"],
  "default_design_values": {
    "fsw": 50000,
    "ripple_ratio": 0.3
  },
  "required_constraints": ["vin", "vout_target"],
  "forbidden_combinations": ["isolated=true"]
}
```

## 4. Circuit Graph Metadata

회로를 실제로 합성한 뒤 필요한 구조 정보다.

### Component-level

- `id`
- `type`
- `role`
- `parameters`
- `tags`
- `block_ids`

### Net-level

- `net_id`
- `pins`
- `role`
- `tags`

### Block-level

- `block_id`
- `block_type`
- `role`
- `component_ids`

### Trace-level

- `source`
- `field`
- `value`
- `confidence`
- `rationale`

### 예시

```json
{
  "topology": "buck",
  "components": [
    {"id": "V1", "type": "DC_Source", "role": "input_source"},
    {"id": "SW1", "type": "MOSFET", "role": "main_switch"},
    {"id": "D1", "type": "Diode", "role": "freewheel_diode"},
    {"id": "L1", "type": "Inductor", "role": "output_inductor"}
  ],
  "nets": [
    {"net_id": "net_vin_sw", "pins": ["V1.positive", "SW1.drain"], "role": "input_positive"},
    {"net_id": "net_sw_junc", "pins": ["SW1.source", "D1.cathode", "L1.pin1"], "role": "switch_node"}
  ],
  "blocks": [
    {"block_id": "switch_stage", "block_type": "power_stage", "component_ids": ["SW1", "D1"]}
  ]
}
```

## 5. Layout Metadata

회로도를 읽기 좋게 배치하기 위한 정보다.

### Component layout metadata

- `preferred_region`
- `preferred_orientation`
- `symbol_variant`
- `alignment_group`

### Region metadata

- `region_id`
- `role`
- `placement_order`
- `boundary_policy`

### Topology layout metadata

- `flow_direction`
- `rail_policy`
- `primary_secondary_split`
- `block_order`
- `symmetry_policy`

### 예시

```json
{
  "topology": "llc",
  "flow_direction": "left_to_right",
  "primary_secondary_split": true,
  "block_order": [
    "input_stage",
    "half_bridge",
    "resonant_tank",
    "transformer_stage",
    "secondary_rectifier",
    "output_filter"
  ],
  "rail_policy": {
    "ground": "bottom_horizontal"
  }
}
```

## 6. Routing Metadata

배선 품질과 routing 정책에 대한 정보다.

### Net routing metadata

- `net_role`
- `routing_style`
- `preferred_axis`
- `allow_trunk`
- `allow_branch`

### Topology routing metadata

- `ground_policy`
- `power_trunk_policy`
- `control_signal_policy`
- `crossing_policy`
- `symmetry_policy`

### Component anchor metadata

- `pin_anchor_policy`
- `junction_preference`
- `multi_pin_strategy`

### 예시

```json
{
  "topology": "buck",
  "ground_policy": "bottom_rail",
  "power_trunk_policy": "left_to_right",
  "control_signal_policy": "shortest_direct",
  "crossing_policy": "minimize",
  "net_roles": {
    "ground": {"preferred_axis": "horizontal", "allow_trunk": true},
    "switch_node": {"preferred_axis": "local", "allow_branch": true}
  }
}
```

## 7. Emission Metadata

SVG와 PSIM 생성에 필요한 마지막 계약 정보다.

### SVG emission metadata

- `symbol_variant`
- `pin_anchor_map`
- `label_policy`
- `style_policy`

### PSIM emission metadata

- `psim_element_type`
- `parameter_name_map`
- `port_pin_groups`
- `bridge_constraints`

### 예시

```json
{
  "component_type": "IdealTransformer",
  "symbol_variant": "transformer_4pin_horizontal",
  "pin_anchor_map": {
    "primary1": [0, 10],
    "primary2": [0, 20],
    "secondary1": [80, 10],
    "secondary2": [80, 20]
  },
  "psim_element_type": "TF_IDEAL",
  "parameter_name_map": {
    "np_turns": "NP",
    "ns_turns": "NS"
  }
}
```

## 계층 간 관계

각 메타데이터는 독립이 아니라 아래 흐름으로 연결된다.

```text
Topology Metadata
  + Component Metadata
  + Design Rule Metadata
    -> Canonical Intent Spec
    -> Circuit Graph Metadata
    -> Layout Metadata
    -> Routing Metadata
    -> Emission Metadata
```

즉 회로 기본정보는 단순히 topology 이름 몇 개를 적는 수준이 아니라,
합성 전 단계에 걸쳐 일관된 계약으로 존재해야 한다.

## 이 문서 기준으로 꼭 있어야 하는 저장소 계층

실제 코드 구조로 옮기면 최소한 아래 registry가 필요하다.

- `topology_metadata`
- `component_library`
- `design_rule_registry`
- `symbol_registry`
- `layout_strategy_registry`
- `routing_policy_registry`
- `bridge_mapping_registry`

## 현재 ver5 문서와의 연결

이 문서는 기존 ver5 문서에 흩어진 내용을 스키마 관점으로 묶은 것이다.

- `phase-2-circuit-graph-design.md`
  - graph metadata
- `phase-3-layout-engine-design.md`
  - layout metadata
- `phase-4-advanced-routing-design.md`
  - routing metadata
- `phase-5-intent-resolution-design.md`
  - intent/spec metadata
- `prd-and-architecture-user-intent-driven-circuit-synthesis.md`
  - 상위 목표와 아키텍처

## 최종 정리

회로를 합성하려면 `기본정보를 참고`하는 것은 맞다.
하지만 그 기본정보는 `예제 회로도 복제 데이터`가 아니라,
아래처럼 구조화된 메타데이터여야 한다.

- topology 규칙
- component 계약
- 설계 규칙
- graph 구조 규칙
- layout 규칙
- routing 규칙
- bridge 계약

즉 이 문서의 핵심은 다음 한 문장이다.

> 회로 기본정보는 참고해야 하지만,
> 참고 대상은 특정 예제 도면이 아니라
> 합성 가능한 수준으로 구조화된 메타데이터 스키마여야 한다.
