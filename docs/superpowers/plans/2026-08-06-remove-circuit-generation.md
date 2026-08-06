# Circuit Generation Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the seven arbitrary circuit-generation tools and all production code that becomes unreachable, while preserving the existing-circuit import, edit, simulation, analysis, and round-trip paths.

**Architecture:** First shrink the FastMCP interface from 19 tools to an exact 12-name contract without deleting the implementation behind it. Then apply the deletion test to remove only modules with no remaining production callers. Keep `CircuitGraph` as the importer domain model and keep the real/mock Adapter seam used by existing-circuit operations.

**Tech Stack:** Python 3.12, FastMCP, Pydantic Settings, pytest/pytest-asyncio, Ruff, `uv run`, PSIM Python 3.8 bridge.

## Global Constraints

- Preserve `src/psim_mcp/synthesis/graph.py` and all of `src/psim_mcp/importer/`.
- Preserve `convert_to_python`, parameter mutation, simulation, result export, signal extraction, and metric computation in both Adapters and the PSIM bridge.
- Remove, do not deprecate: no compatibility stub, feature flag, hidden registration, or replacement generation tool.
- Do not add dependencies or new abstractions.
- Use `uv run` for every Python command.
- Execute in an isolated worktree because the main checkout contains user-owned changes.
- Stage only files named by the task being committed.
- Keep the two product commits separate: public interface first, unreachable implementation second.

---

### Task 1: Remove the Public Generation Interface

**Files:**
- Modify: `tests/unit/test_app_factory.py`
- Modify: `tests/unit/test_tool_integration.py`
- Modify: `src/psim_mcp/server.py`
- Modify: `src/psim_mcp/tools/analysis.py`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Delete: `src/psim_mcp/tools/circuit.py`
- Delete: `src/psim_mcp/tools/design.py`

**Interfaces:**
- Consumes: existing `create_app(AppConfig(psim_mode="mock")) -> FastMCP` factory.
- Produces: an exact 12-tool FastMCP interface containing only existing-project, parameter, simulation, result, and analysis tools.

- [ ] **Step 1: Replace the tool-count assertion with a failing exact-name contract**

Replace `test_create_app_registers_19_tools` in `tests/unit/test_app_factory.py` with:

```python
EXPECTED_TOOLS = {
    "open_project",
    "get_project_info",
    "import_circuit",
    "set_parameter",
    "sweep_parameter",
    "run_simulation",
    "export_results",
    "compare_results",
    "get_status",
    "analyze_simulation",
    "analyze_existing",
    "optimize_circuit",
}


def test_create_app_registers_supported_tools():
    app = create_app(AppConfig(psim_mode="mock"))
    assert set(app._tool_manager._tools) == EXPECTED_TOOLS
```

- [ ] **Step 2: Run the contract test and verify it fails with the seven generation names as extras**

Run:

```powershell
uv run pytest tests/unit/test_app_factory.py::test_create_app_registers_supported_tools -v
```

Expected: FAIL; the actual set additionally contains `design_circuit`, `continue_design`, `preview_circuit`, `confirm_circuit`, `create_circuit`, `get_component_library`, and `list_circuit_templates`.

- [ ] **Step 3: Remove generation registration at the single composition root**

In `src/psim_mcp/server.py`, keep `CircuitDesignService` construction until Task 2 so this commit changes only the public contract. Change only tool imports and registrations:

```python
# register_all_tools(): do not import or register circuit/design modules
from psim_mcp.tools import analysis, parameter, project, results, simulation
```

Delete `circuit.register_tools(...)` and `design.register_tools(...)`. Do not add an environment switch.

Delete `src/psim_mcp/tools/circuit.py` and `src/psim_mcp/tools/design.py`. In `tests/unit/test_tool_integration.py`, delete `test_continue_design_keeps_asking_when_template_not_design_ready` and its now-unused `json` import.

In `src/psim_mcp/tools/analysis.py`, replace the stale closed-loop buck preview instruction with wording that refers only to opening/importing the real project and running analysis. Do not change the analysis tool signature or response shape.

- [ ] **Step 4: Make the public documentation describe only the 12-tool product**

In `README.md`:

- change the summary and MCP tool count from 19 to 12;
- delete the legacy creation status, template, prompt, topology, synthesis, routing, and “new topology/resolver” sections;
- remove the seven generation rows from the tool table;
- keep the existing-circuit workflow and the honest warning that `set_parameter` currently operates on the open project;
- keep installation, client configuration, simulation, analysis, security, and VER2 importer documentation.

In `CLAUDE.md`:

- change registered tools from 19 to 12;
- delete `CircuitDesignService`, canonical/legacy generation pipelines, generation registries, generation feature flags, and “Adding a New Topology” guidance;
- document `CircuitGraph` as the importer representation rather than a synthesis product;
- keep build commands, Adapter architecture, response contract, existing services, bridge constraints, and importer tests.

- [ ] **Step 5: Verify the public interface and focused non-generation workflows**

Run:

```powershell
uv run pytest tests/unit/test_app_factory.py tests/unit/test_tool_integration.py tests/unit/test_import_circuit.py tests/unit/test_importer_reconstruction.py -q
uv run ruff check src/psim_mcp/server.py tests/unit/test_app_factory.py
git diff --check
```

Expected: all selected tests pass, Ruff exits 0, and `git diff --check` exits 0.

- [ ] **Step 6: Commit the interface removal**

```powershell
git add src/psim_mcp/server.py src/psim_mcp/tools/analysis.py src/psim_mcp/tools/circuit.py src/psim_mcp/tools/design.py tests/unit/test_app_factory.py tests/unit/test_tool_integration.py README.md CLAUDE.md
git commit -m "refactor: remove circuit generation tools"
```

---

### Task 2: Delete the Unreachable Generation Implementation

**Files:**
- Modify: `src/psim_mcp/config.py`
- Modify: `src/psim_mcp/server.py`
- Modify: `src/psim_mcp/synthesis/__init__.py`
- Modify: `src/psim_mcp/shared/protocols.py`
- Modify: `src/psim_mcp/services/simulation_service.py`
- Modify: `src/psim_mcp/adapters/base.py`
- Modify: `src/psim_mcp/adapters/mock_adapter.py`
- Modify: `src/psim_mcp/adapters/real_adapter.py`
- Modify: `src/psim_mcp/bridge/bridge_script.py`
- Modify: `src/psim_mcp/data/bridge_mapping_registry.py`
- Modify: `.env.example`
- Modify: `claude_desktop_config.example.json`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/conftest.py`
- Modify: `tests/unit/test_bridge_contract.py`
- Modify: `tests/unit/test_bridge_mapping_registry.py`
- Modify: `tests/unit/test_bridge_helpers.py`
- Modify: `tests/unit/test_graph_models.py`
- Modify: `tests/unit/test_simulation_service.py`
- Modify: `tests/unit/test_app_factory.py`
- Modify: `tests/unit/test_analysis_tools.py`
- Modify: `tests/unit/test_real_adapter_resilience.py`
- Modify: `tests/unit/test_startup_validation.py`
- Modify: `tests/unit/test_tool_integration.py`
- Modify: `tests/integration/conftest.py`
- Modify: `pyproject.toml`
- Delete: `src/psim_mcp/tools/_preview_helpers.py`
- Delete: `src/psim_mcp/services/circuit_design_service.py`
- Delete: `src/psim_mcp/services/_circuit_generators.py`
- Delete: `src/psim_mcp/services/_circuit_pipeline.py`
- Delete: `src/psim_mcp/services/_circuit_render.py`
- Delete: `src/psim_mcp/services/preview_store.py`
- Delete: `src/psim_mcp/shared/state_store.py`
- Delete: `src/psim_mcp/bridge/wiring.py`
- Delete: `src/psim_mcp/utils/ascii_renderer.py`
- Delete: `src/psim_mcp/utils/svg_renderer.py`
- Delete: `src/psim_mcp/models/circuit_spec.py`
- Delete directories: `src/psim_mcp/generators/`, `src/psim_mcp/intent/`, `src/psim_mcp/layout/`, `src/psim_mcp/routing/`, `src/psim_mcp/parsers/`, `src/psim_mcp/validators/`
- Delete from synthesis: `src/psim_mcp/synthesis/graph_builders.py`, `src/psim_mcp/synthesis/models.py`, `src/psim_mcp/synthesis/sizing.py`, `src/psim_mcp/synthesis/topologies/`
- Delete generation data: `src/psim_mcp/data/capability_matrix.py`, `circuit_templates.py`, `component_library.py`, `design_rule_registry.py`, `layout_strategy_registry.py`, `routing_policy_registry.py`, `spec_mapping.py`, `symbol_registry.py`, `topology_metadata.py`
- Delete all tracked `__pycache__/*.pyc` files already covered by `.gitignore`
- Delete: the complete generation-only `tests/real/` tree
- Delete generation-only tests and legacy generation documentation identified below.

**Interfaces:**
- Consumes: the 12-name interface established by Task 1.
- Produces: a smaller implementation with `ProjectService`, `ParameterService`, `SimulationService`, analysis/results modules, two PSIM Adapters, the bridge, importer, and `CircuitGraph` as the remaining deep modules.

- [ ] **Step 1: Record the keep-path baseline before deletion**

Run:

```powershell
uv run pytest tests/unit/test_importer_reconstruction.py tests/unit/test_import_circuit.py tests/unit/test_project_service.py tests/unit/test_parameter_service.py tests/unit/test_simulation_service.py tests/unit/test_analysis_tools.py tests/unit/test_acceptance_criteria.py -q
```

Expected: record the exact pass/fail/skip counts. Stop and investigate any importer, project, parameter, or simulation failure before deleting code.

- [ ] **Step 2: Remove generation-only configuration and interfaces**

In `src/psim_mcp/config.py`, remove:

```python
psim_project_dir
preview_ttl
psim_intent_pipeline_v2
psim_synthesis_enabled_topologies
psim_graph_enabled_topologies
psim_layout_engine_enabled_topologies
psim_routing_enabled_topologies
intent_resolver_mode
```

Also remove the four generation topology-list fields from the `field_validator` declaration, leaving only `allowed_project_dirs`.

Remove `PSIM_PROJECT_DIR` from real-mode examples, required-field checks, `.env.example`, `claude_desktop_config.example.json`, `README.md`, `CLAUDE.md`, and the affected test configs. Preserve `psim_output_dir`, `allowed_project_dirs`, and their validations.

In `src/psim_mcp/shared/protocols.py`, delete `CircuitDesignServiceProtocol`. In `src/psim_mcp/synthesis/__init__.py`, export only `CircuitGraph`, `GraphComponent`, `GraphNet`, `FunctionalBlock`, and `DesignDecisionTrace` from `.graph`.

In `src/psim_mcp/server.py`, now delete the `CircuitDesignService` import, construction, and `"circuit_design"` service mapping entry left intentionally reachable during Task 1.

- [ ] **Step 3: Remove the old circuit-creation seam from services and Adapters**

- delete `SimulationService.create_circuit` and its generation-only local imports;
- delete `BasePsimAdapter.create_circuit`;
- delete `MockPsimAdapter.create_circuit`;
- delete `RealPsimAdapter.create_circuit` and its `_call_bridge("create_circuit", ...)` payload construction;

Do not change `convert_to_python`, `set_parameter`, `run_simulation`, `export_results`, `extract_signals`, or `compute_metrics`.

- [ ] **Step 4: Shrink the PSIM bridge without touching edit/simulation handlers**

In `src/psim_mcp/bridge/bridge_script.py`:

- keep only `get_parameter_mapping` from `bridge_mapping_registry` imports;
- delete `_SIMULATION_DEFAULTS`, `_GLOBAL_DEFAULT`, `_FALLBACK_PORT_PIN_GROUPS`, `_compute_psim_area`, `_build_port_pin_map`, and `_PSIM_TYPE_MAP`;
- keep `_PARAM_NAME_MAP`, `_PARAMETER_COMPONENT_ALIASES`, and `_get_parameter_name_mapping` because `handle_set_parameter` uses them;
- delete `_get_simulation_defaults`, `_calculate_simcontrol_position`, `_resolve_pin_positions`, `_group_connections_into_nets`, `_route_net_star`, `_seg_collides`, `_find_clear_offset`, `_route_wire`, `_handle_template_circuit`, and `handle_create_circuit`;
- remove the `"create_circuit": handle_create_circuit` dispatch entry.

The remaining `_ACTION_HANDLERS` names must be:

```python
{
    "open_project",
    "set_parameter",
    "run_simulation",
    "export_results",
    "get_status",
    "get_project_info",
    "convert_to_python",
    "extract_signals",
    "compute_metrics",
}
```

In `src/psim_mcp/data/bridge_mapping_registry.py`, keep `PARAMETER_NAME_MAP` and `get_parameter_mapping`; delete the generation-only PSIM type map, port-pin registry, and their lookup helpers. Update `tests/unit/test_bridge_mapping_registry.py` to retain only parameter-name mapping coverage.

- [ ] **Step 5: Delete generation-only modules, data, tests, docs, and tracked bytecode**

Delete the production paths listed in this task's **Files** section. Preserve exactly:

```text
src/psim_mcp/importer/**
src/psim_mcp/synthesis/graph.py
src/psim_mcp/data/bridge_mapping_registry.py
src/psim_mcp/data/simulation_defaults.py
src/psim_mcp/data/topology_metrics.py
src/psim_mcp/utils/waveform_renderer.py
src/psim_mcp/services/validators.py
```

Delete these generation-only test files/directories:

```text
tests/integration/test_canonical_pipeline.py
tests/integration/test_design_flow.py
tests/integration/test_hybrid_resolver_golden.py
tests/unit/test_auto_placer.py
tests/unit/test_auto_vs_hardcoded.py
tests/unit/test_build_need_specs_versioned.py
tests/unit/test_circuit_design_service.py
tests/unit/test_circuit_design_service_phase3.py
tests/unit/test_circuit_design_service_phase4.py
tests/unit/test_circuit_design_service_phase5.py
tests/unit/test_circuit_design_service_v2.py
tests/unit/test_circuit_spec.py
tests/unit/test_circuit_template_validity.py
tests/unit/test_circuit_validators.py
tests/unit/test_clarification_policy.py
tests/unit/test_design_session_compat.py
tests/unit/test_elicitation.py
tests/unit/test_feature_flags.py
tests/unit/test_force_directed.py
tests/unit/test_generators.py
tests/unit/test_graph_validator.py
tests/unit/test_hybrid_resolver.py
tests/unit/test_intent_extractor.py
tests/unit/test_intent_models.py
tests/unit/test_intent_resolver.py
tests/unit/test_layout_engine_buck.py
tests/unit/test_layout_engine_flyback.py
tests/unit/test_layout_engine_llc.py
tests/unit/test_layout_models.py
tests/unit/test_materialize_layout.py
tests/unit/test_parser_regression.py
tests/unit/test_pipeline_invariants.py
tests/unit/test_preview_store.py
tests/unit/test_role_classification.py
tests/unit/test_routing_buck_strategy.py
tests/unit/test_routing_crossing_minimization.py
tests/unit/test_routing_metrics.py
tests/unit/test_routing_models.py
tests/unit/test_routing_models_v2.py
tests/unit/test_routing_router.py
tests/unit/test_routing_trunk_branch.py
tests/unit/test_sampling_resolver.py
tests/unit/test_spec_builder.py
tests/unit/test_svg_renderer.py
tests/unit/test_synthesis_models.py
tests/unit/test_synthesize_buck_graph.py
tests/unit/test_topology_metadata.py
tests/unit/test_topology_ranker.py
tests/unit/test_unit_parser.py
tests/unit/test_wire_routing_legacy_compat.py
```

Keep `tests/unit/test_graph_models.py` because it covers the importer graph model, but remove its `graph_builders` import and the four builder-helper tests. Keep `tests/unit/test_import_circuit.py` and `tests/unit/test_importer_reconstruction.py` unchanged.

Keep `src/psim_mcp/models/schemas.py`, `src/psim_mcp/models/__init__.py`, and `tests/unit/test_schemas.py`; they are generic request/response schemas, not circuit-generation code.

Delete legacy generation documentation under `docs/ver1.1/`, `docs/ver1.1.1/`, `docs/ver1.1.4/`, and `docs/ver5/`, plus the two tracked Phase 1–4 generation gap documents. Preserve `docs/ver2/` and every `docs/superpowers/` spec/plan.

- [ ] **Step 6: Update mixed tests instead of deleting their supported assertions**

- `tests/unit/test_bridge_contract.py`: remove `create_circuit` from the expected bridge action set; keep all response, subprocess, and Adapter payload tests.
- `tests/unit/test_bridge_helpers.py`: remove creation helper imports and the creation helper test classes; keep `TestHandleSetParameter` and any later edit/simulation tests.
- `tests/unit/test_graph_models.py`: retain only direct `CircuitGraph`, `GraphComponent`, `GraphNet`, `FunctionalBlock`, and `DesignDecisionTrace` behavior tests.
- `tests/unit/test_simulation_service.py`: delete only `TestCreateCircuit`; keep open, parameter, simulation, result, and status tests.
- `tests/conftest.py`: remove the preview-SVG autouse cleanup and its now-unused `glob`, `os`, and `tempfile` imports; remove `psim_project_dir` from `test_config`.
- `tests/integration/conftest.py`: remove the `circuit_design_service` fixture and `psim_project_dir`; keep app, simulation, project, and file fixtures.
- `tests/unit/test_app_factory.py`, `test_analysis_tools.py`, `test_real_adapter_resilience.py`, `test_startup_validation.py`, and `test_tool_integration.py`: remove obsolete `psim_project_dir` construction and `PSIM_PROJECT_DIR` expectations while preserving all surviving behavior assertions.
- delete the entire `tests/real/` tree because every current real test and fixture is generation acceptance; add existing-circuit real tests later with the approved editing feature, not an empty harness now.
- `pyproject.toml`: remove Ruff per-file ignores for deleted `layout/auto_placer.py` and `parsers/intent_parser.py`.

- [ ] **Step 7: Prove there are no production callers or stale public references**

Run:

```powershell
rg -n "CircuitDesignService|design_circuit|continue_design|preview_circuit|confirm_circuit|create_circuit|get_component_library|list_circuit_templates" src tests README.md CLAUDE.md
rg -n "psim_mcp\.(generators|intent|layout|routing|parsers|validators)|psim_mcp\.synthesis\.(graph_builders|models|sizing|topologies)" src tests
```

Expected: no matches. Mentions inside the approved design and implementation plan are historical requirements and are excluded from these paths.

- [ ] **Step 8: Run focused and full verification**

Run:

```powershell
uv run pytest tests/unit/test_app_factory.py tests/unit/test_bridge_contract.py tests/unit/test_bridge_helpers.py tests/unit/test_importer_reconstruction.py tests/unit/test_import_circuit.py tests/unit/test_project_service.py tests/unit/test_parameter_service.py tests/unit/test_simulation_service.py tests/unit/test_analysis_tools.py tests/unit/test_tool_integration.py -q
uv run pytest tests/unit tests/integration -q
uv run ruff check src/ tests/
uv run python -c "from psim_mcp.config import AppConfig; from psim_mcp.server import create_app; app=create_app(AppConfig(psim_mode='mock')); assert len(app._tool_manager._tools)==12; print(sorted(app._tool_manager._tools))"
git diff --check
```

Expected: every command exits 0. If the full suite exposes a pre-existing baseline failure, compare it with Task 2 Step 1 and do not label it a regression without matching evidence.

- [ ] **Step 9: Commit the unreachable-code deletion**

Stage only the reviewed production, test, and documentation deletions/edits, then run `git diff --cached --check`.

```powershell
git commit -m "refactor: delete circuit generation pipeline"
```

The final diff must preserve the importer graph and round-trip modules and must not contain user-owned files from the original checkout.
