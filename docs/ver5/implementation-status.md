# ver5 Implementation Status

Updated: 2026-03-26
Baseline: `uv run pytest tests/unit` (1002 passed) + real-mode PSIM E2E (13/25 topologies)

This document tracks the current state of the ver5 canonical pipeline against the planning documents in `docs/ver5/`.

---

## Summary

| Area | Completion | Notes |
|------|-----------|-------|
| Phase 1. Generator Decomposition | 95% | 28/29 topologies have synthesizers; pv_grid_tied remains legacy-only |
| Phase 2. CircuitGraph | 85% | Graph model, builder, validator, 28 topology synthesizers |
| Phase 3. Layout Engine | 90% | 100% algorithmic auto_place; no hardcoded strategies active |
| Phase 4. Routing | 70% | Trunk-and-branch + crossing minimization; no cost-function or symmetry-aware routing |
| Phase 5. Intent Resolution | 75% | V2 pipeline active by default; no multi-hop clarification |
| Simulation Feedback | 50% | Waveform rendering, simview exposure; optimization service incomplete |
| Cross-cutting (versioning, metrics) | 60% | Quality gate metrics incomplete (4/8+); no canonical model versioning |

---

## Quantitative Snapshot

| Metric | Value |
|--------|-------|
| Unit tests passing | 1002 |
| Registered MCP tools | 17 |
| Total topologies (topology_metadata.py) | 29 |
| Topologies with `synthesize: "new"` | 28 (only `pv_grid_tied` is `"none"`) |
| PSIM real-mode simulation success | 13/25 tested |
| Data registries implemented | 8/8 |
| Layout algorithm coverage | 100% algorithmic (auto_place) |
| Topology-specific routing strategies | 3 (buck, flyback, llc) |

---

## PSIM Real-Mode Simulation Results (13/25)

**Working** (13):
buck, boost, flyback, buck_boost, sepic, cuk, forward, llc, cc_cv_charger, bidirectional_buck_boost, dab, pv_mppt_boost, ev_obc

**Failing** (12 -- floating node errors):
full_bridge, push_pull, thyristor_rectifier, boost_pfc, totem_pole_pfc, three_level_npc, pv_grid_tied, bldc_drive, pmsm_foc_drive, induction_motor_vf, half_bridge, diode_bridge_rectifier

**Not tested** (4):
vienna_rectifier, interleaved_boost, stacked_buck, resonant_llc_full_bridge

---

## Phase 1. Generator Decomposition

### Implemented

- Synthesis transition model -- `synthesis/models.py`
- Sizing logic separation -- `synthesis/sizing.py`
- Generator `synthesize()` boundary -- `generators/base.py` + 28 topology implementations
- Preview payload version field -- `circuit_design_service.py`
- Feature flag topology on/off -- `config.py` (5 flags)
- Capability matrix runtime reflection -- `circuit_design_service.py`
- All 13 remaining legacy topologies migrated to canonical pipeline (commit `2f38bda`)

### Remaining

- `pv_grid_tied` has no synthesizer (`synthesize="none"`)
- `SimulationService` consumes enriched `circuit_spec` but retains compatibility-service character

---

## Phase 2. CircuitGraph

### Implemented

- `GraphComponent`, `GraphNet`, `FunctionalBlock`, `DesignDecisionTrace`, `CircuitGraph` -- `synthesis/graph.py`
- Graph builder helpers -- `synthesis/graph_builders.py`
- Graph validator -- `validators/graph.py`
- 28 topology graph synthesizers -- `synthesis/topologies/*.py`
- Preview payload graph save/restore -- `circuit_design_service.py`
- Capability matrix graph support check -- `circuit_design_service.py`

### Remaining

- Graph validator `_REQUIRED_ROLES` only covers 3/28 topologies
- Block-level semantic validation is shallow

---

## Phase 3. Layout Engine

### Implemented

- `SchematicLayout`, `LayoutComponent`, `LayoutRegion`, `LayoutConstraint` -- `layout/models.py`
- Algorithmic auto-layout engine -- `layout/auto_placer.py`
  - Block-based region assignment
  - Role-based component placement (registry-driven)
  - Force-directed fine adjustment -- `layout/force_directed.py`
  - Grid snap (PSIM 50px)
  - Constraint enforcement -- `layout/constraint_solver.py` (7 constraint kinds)
  - Symbol variant selection from `symbol_registry`
- `generate_layout()` -- `layout/engine.py` (all topologies use auto_place)
- `materialize_to_legacy()` -- `layout/materialize.py`
  - 5 component types added: Thyristor, Center_Tap_Transformer, motors
- Service preview/store layout persistence
- SVG renderer consumes `layout` + `wire_segments`
- `data/symbol_registry.py` -- symbol variants, pin anchors, bounding boxes
- `data/layout_strategy_registry.py` -- placement rules, role classification, PLACEMENT_ROWS

### Remaining

- Hardcoded reference strategies moved to `layout/strategies/_reference/` (not used in production)
- Renderer retains legacy component-dict rendering path as fallback

---

## Phase 4. Routing

### Implemented

- `WireRouting`, `RoutedSegment`, `JunctionPoint`, `RoutingPreference` -- `routing/models.py`
- `generate_routing()` -- `routing/engine.py`
- Pin anchor resolution -- `routing/anchors.py`
  - Port generation from position added for legacy generators
- Trunk-and-branch routing -- `routing/trunk_branch.py`
- Crossing minimization -- `routing/trunk_branch.py` (`minimize_crossings()`)
- Routing metrics -- `routing/metrics.py`
- Topology-specific routing strategies: `routing/strategies/buck.py`, `flyback.py`, `llc.py`
- Preview payload routing/wire_segments persistence
- SVG consumes `wire_segments` first
- Bridge generates coordinate-based WIRE elements from `wire_segments`
- `data/routing_policy_registry.py` -- per-topology routing policies

### Remaining

- No cost-function-based routing
- No region-aware or symmetry-aware routing (models exist, strategies do not use them deeply)
- Bridge internal `_route_wire` fallback retained for legacy compatibility

---

## Phase 5. Intent Resolution

### Implemented

- `intent/` hierarchy: `extractors.py`, `ranker.py`, `clarification.py`, `spec_builder.py`, `models.py`
- `CircuitDesignService._resolve_intent_v2()` -- V2 pipeline active by default
- `design_circuit()` V2-first with legacy fallback
- Action contract: `confirm_intent`, `need_specs`, `suggest_candidates`
- Response extensions: `candidate_scores`, `decision_trace`
- Design session payload versioning
- Feature flag `PSIM_INTENT_PIPELINE_V2`
- `continue_design()` v1/v2 normalization
- Spec alias normalization: `vout` -> `vout_target`, `iout` -> `iout_target`
- Single-pass clarification

### Remaining

- Multi-hop clarification (question -> answer -> re-evaluate -> re-question) not implemented
- Clarification results not fully promoted to service actions

---

## Data Registries (8/8)

| File | Purpose | Consumed by |
|------|---------|-------------|
| `topology_metadata.py` | 29 topologies: required_fields, block_order, layout_family | service, auto_placer |
| `component_library.py` | 40+ component types with pin definitions | auto_placer, materialize |
| `symbol_registry.py` | Symbol variants, pin anchors, bounding boxes | auto_placer, renderer |
| `layout_strategy_registry.py` | Placement rules, role classification, PLACEMENT_ROWS | auto_placer |
| `routing_policy_registry.py` | Per-topology routing policies | routing strategies |
| `design_rule_registry.py` | Design constraints, defaults, feasibility | reference data |
| `bridge_mapping_registry.py` | PSIM type mapping, parameter map | bridge_script |
| `capability_matrix.py` | Topology x feature support matrix | service pipeline |

### Remaining

- `design_rule_registry.py` exists but sizing logic does not call it directly
- No automated cross-validation between registries (e.g., topology_metadata required_blocks vs. actual graph)

---

## Service Integration

### Entrypoint canonical pipeline status

| Entrypoint | Status | Graph | Layout | Routing |
|------------|--------|-------|--------|---------|
| `design_circuit()` -> `_auto_generate_preview()` | Implemented | Yes | Yes | Yes |
| `preview_circuit()` | Implemented | Yes | Yes | Yes |
| `confirm_circuit()` | Implemented | Rematerialize | -- | -- |
| `create_circuit_direct()` | Implemented | Synthesis-first | -- | -- |
| `SimulationService.create_circuit()` | Partial | Enriched spec | -- | -- |

### Preview payload fields

`payload_kind`, `payload_version`, `components`, `connections`, `nets`, `wire_segments`, `graph`, `layout`, `routing`

---

## Key Issues Fixed (2026-03-26)

- GATING `Switching_Points` format fixed across all generators (comma -> space+period)
- 5 circuit topology connection bugs fixed (buck_boost, full_bridge, half_bridge, push_pull, boost_pfc)
- SVG file accumulation fixed (cross-topology cleanup + TTL-based disk deletion)
- Waveform `time_step` hardcoding fixed (topology-specific lookup from `simulation_defaults.py`)
- Spec alias normalization added (vout -> vout_target, iout -> iout_target)
- Port generation from position added for legacy generators
- `test_expired` flaky test fixed (time mock)
- 5 component types added to `materialize.py` and `anchors.py` (Thyristor, Center_Tap_Transformer, motors)
- `matplotlib` added as dependency for waveform rendering
- `tool_handler` now exposes exception details to LLM
- `run_simulation` and `analyze_simulation` now expose `simview` parameter
- Save path validation before creating PSIM schematics (commit `d1dc7d3`)

---

## Known Gaps

1. **Phase 4 routing**: No cost-function routing, no region-aware or symmetry-aware routing
2. **Phase 5 clarification**: No multi-hop clarification loop
3. **Graph validator**: `_REQUIRED_ROLES` only covers 3/28 topologies
4. **Canonical model versioning**: Not implemented
5. **Quality gate metrics**: Incomplete (4/8+ tracked)
6. **Optimization service**: Optuna-based service incomplete
7. **12 topologies fail PSIM simulation**: Floating node errors in full_bridge, push_pull, thyristor_rectifier, boost_pfc, totem_pole_pfc, three_level_npc, pv_grid_tied, bldc_drive, pmsm_foc_drive, induction_motor_vf, half_bridge, diode_bridge_rectifier
8. **Registry cross-validation**: No automated consistency checks between topology_metadata, graph, and layout_strategy

---

## Verification

| Method | Result |
|--------|--------|
| `uv run pytest tests/unit -q` | 1002 passed |
| PSIM real-mode E2E | 13/25 topologies simulate successfully |
| Buck E2E (intent -> SVG) | 8 comp, 5 net, 3 block, 8 seg |
| Flyback E2E | 8 comp, 7 net, 5 block, 10 seg |
| LLC E2E | 14 comp, 11 net, 7 block, 19 seg |
| Service preview graph/layout save | All canonical topologies OK |
| Bridge JSON IPC | Normal (stdout pollution blocked) |

---

## Conclusion

The ver5 canonical pipeline covers 28/29 topologies with synthesizers and 100% algorithmic layout. 13 topologies are verified end-to-end through real PSIM simulation. The primary remaining risk is not structural gaps but simulation-level correctness for the 12 failing topologies (floating node errors requiring connection debugging) and the absence of advanced routing and multi-hop clarification features.
