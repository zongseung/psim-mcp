# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
uv sync --all-extras

# Run all unit tests (845 tests, ~3s)
uv run pytest tests/unit -q

# Run a single test file
uv run pytest tests/unit/test_simulation_service.py -v

# Run tests matching a keyword
uv run pytest tests/unit -k "test_sweep" -v

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Start MCP server (stdio mode)
uv run psim-mcp

# MCP Inspector (debug without Claude Desktop)
uv run mcp dev src/psim_mcp/server.py
```

All Python operations must use `uv run`. Never use bare `python`, `pip`, or `python -m`.

## Verified Current Status

- Unit test collection: 845 tests
- Registered MCP tools: 17
- Total topologies in `topology_metadata.py`: 29
- End-to-end canonical topologies: `buck`, `flyback`, `llc`
- Topologies still using the legacy `design_circuit` path: 26
- Only topology currently marked `synthesize="none"`: `pv_grid_tied`

## Architecture

### Dual Python Environments

The MCP server runs on Python 3.12+. PSIM's API (`psimapipy`) requires its bundled Python 3.8. Communication happens via subprocess JSON IPC:

```
Claude Desktop ─stdio─→ MCP Server (Python 3.12+)
                              │
                       CircuitDesignService / SimulationService
                              │
                       RealPsimAdapter
                              │ stdin/stdout JSON lines
                       bridge_script.py (Python 3.8)
                              │
                       psimapipy → PSIM engine
```

### App Factory Pattern

`server.py` uses `create_app(config)` to wire everything. Tests create isolated instances — no global state leaks between tests:

```python
config = AppConfig(psim_mode="mock")
app = create_app(config)
```

Module-level `mcp` and `config` attributes use `__getattr__` for lazy singleton initialization (backward compatibility with tool modules that do `from psim_mcp.server import mcp`).

### Tool Handler Decorator

All 17 MCP tools use the `@tool_handler("name")` decorator from `tools/__init__.py`. It handles exception catching, JSON serialization, LLM output sanitization, and 50KB truncation. Tools return dicts; the decorator converts to JSON strings.

### Adapter Pattern

- `BasePsimAdapter` — abstract interface in `adapters/base.py`
- `MockPsimAdapter` — in-memory, used on macOS / in tests
- `RealPsimAdapter` — manages a long-running bridge subprocess, serializes calls with asyncio.Lock

Selection: `PSIM_MODE=mock` (default) or `PSIM_MODE=real`. Real mode requires `PSIM_PATH`, `PSIM_PYTHON_EXE`, `PSIM_PROJECT_DIR`, `PSIM_OUTPUT_DIR` environment variables.

### Canonical Circuit Design Pipeline

Two paths exist — canonical (graph-based) and legacy (generator/template). The canonical path is preferred; legacy is the automatic fallback.

```
Natural language
  → intent/ extractors     → topology + constraints extraction
  → intent/ ranker          → topology candidates scored
  → intent/ spec_builder    → CanonicalSpec
  → generators/ synthesize() → CircuitGraph (roles, blocks, nets)
  → validators/             → structural + electrical + parameter + graph
  → layout/ auto_placer     → SchematicLayout (force-directed, grid-snapped)
  → routing/ trunk_branch   → WireRouting (crossing-minimized)
  → layout/ materialize     → legacy component format
  → utils/ svg_renderer     → SVG + ASCII preview
  → shared/ state_store     → preview token (TTL-based)
  → confirm_circuit         → .psimsch file via bridge + PSIM GUI auto-open
```

**Legacy fallback path**: `generators/ generate()` → template lookup (`data/circuit_templates.py`, 29 templates, 9 categories) → validators → render → preview → confirm.

### Service Layer

Four services under `services/`:
- `CircuitDesignService` — orchestrates the full design pipeline (intent → synthesis → layout → routing → render → preview/confirm)
- `SimulationService` — run_simulation, sweep_parameter, export_results
- `ProjectService` — open_project, get_project_info
- `ParameterService` — set_parameter

All service calls go through `_execute_with_audit()` — timing, SHA-256 input hashing, structured logging to 4 separate log files (server, psim, security, tools).

### Response Format

All tools return:
```json
{"success": true, "data": {...}, "message": "..."}
{"success": false, "error": {"code": "...", "message": "...", "suggestion": "..."}}
```

Built via `ResponseBuilder.success()` / `ResponseBuilder.error()` in `shared/response.py`.

### Data Registries

`data/` contains 8 declarative registries that drive pipeline behavior:

| Registry | Purpose |
|----------|---------|
| `topology_metadata.py` | Topology attributes (29 topologies): required_fields, block_order, layout_family |
| `component_library.py` | 40+ component types with pin definitions and parameters |
| `capability_matrix.py` | Topology × feature support (synthesize, graph, layout, routing) |
| `layout_strategy_registry.py` | Placement rules, role classification (declarative, rule-based) |
| `routing_policy_registry.py` | Per-topology routing policies |
| `bridge_mapping_registry.py` | Python component type → PSIM native element type mapping |
| `design_rule_registry.py` | Design constraints and default values |
| `symbol_registry.py` | SVG symbol variants and pin anchors |

## Key Conventions

- Tool descriptions are in Korean (user-facing via Claude Desktop)
- `bridge_script.py` cannot import from `psim_mcp` — it runs in PSIM's Python 3.8
- Topology-specific simulation defaults (time_step, total_time) are in `data/simulation_defaults.py`
- Preview tokens have a TTL (default 3600s) managed by `StateStore` (aliased as `PreviewStore`)
- Path security: `allowed_project_dirs` whitelist in config; empty = no restriction (dev mode)
- `pytest-asyncio` with `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio`
- PSIM native elements use `MULTI_*` types (e.g., `MULTI_MOSFET`), PORTS must be a Python list (not string), `SubType="Ideal"` required
- Transformer uses `Np__primary_` / `Ns__secondary_` for turns ratio (`Ratio` parameter is ignored by PSIM)

## Adding a New Topology

1. `generators/my_topology.py` — implement `TopologyGenerator` with `generate()` (legacy) + `synthesize()` (canonical)
2. `synthesis/topologies/my_topology.py` — `synthesize_my_topology()` → CircuitGraph with roles, blocks, nets
3. `data/topology_metadata.py` — add metadata entry (required_fields, block_order, layout_family)
4. `generators/__init__.py` — register in the generator registry

Layout and routing are automatic if role naming conventions are followed:

| Keyword in role name | Placement | Direction |
|---------------------|-----------|-----------|
| `ground`, `gnd` | ground (rail) | 0 |
| `gate`, `drive`, `pwm`, `controller` | control (bottom) | 0 |
| `capacitor`, `cap` | shunt (below power path) | 90 (vertical) |
| `switch`, `source`, `inductor`, `transformer`, `rectifier` | power_path (top) | 0 |
| `high_side`, `low_side` | power_path | 0 (vertical stack) |
| `load` | shunt | 90 |

Exceptions go in `_PLACEMENT_OVERRIDES` / `_DIRECTION_OVERRIDES` in `layout_strategy_registry.py`.

## Test Fixtures

`tests/conftest.py` provides:
- `test_config` — `AppConfig(psim_mode="mock")` with temp dirs
- `sample_project_path` — pre-created `.psimsch` file
- `_cleanup_preview_svgs` — session-level SVG cleanup

## Current PRDs

| Version | Location | Focus |
|---------|----------|-------|
| v1.1.2 | `docs/ver1.1.2/` | Bridge persistence, hardcoding removal, auto-simulation flow, MSA refactoring |
| v1.1.4 | `docs/ver1.1.4/` | Formula-based generators, PSIM native format discovery, constraint engine |
| v5 | `docs/ver5/` | Algorithmic layout, circuit graph synthesis, routing, phase execution plans |
