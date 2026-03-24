# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
uv sync --all-extras

# Run all unit tests (311 tests, ~1s)
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

## Architecture

### Dual Python Environments

The MCP server runs on Python 3.12+. PSIM's API (`psimapipy`) requires its bundled Python 3.8. Communication happens via subprocess JSON IPC:

```
Claude Desktop ─stdio─→ MCP Server (Python 3.12+)
                            │
                     SimulationService
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

All 15 MCP tools use the `@tool_handler("name")` decorator from `tools/__init__.py`. It handles exception catching, JSON serialization, LLM output sanitization, and 50KB truncation. Tools return dicts; the decorator converts to JSON strings.

### Adapter Pattern

- `BasePsimAdapter` — abstract interface in `adapters/base.py`
- `MockPsimAdapter` — in-memory, used on macOS / in tests
- `RealPsimAdapter` — manages a long-running bridge subprocess, serializes calls with asyncio.Lock

Selection: `PSIM_MODE=mock` (default) or `PSIM_MODE=real`. Real mode requires `PSIM_PATH`, `PSIM_PYTHON_EXE`, `PSIM_PROJECT_DIR`, `PSIM_OUTPUT_DIR` environment variables.

### Circuit Design Pipeline

```
Natural language → intent_parser → topology + specs
    → Generator (buck/boost/buck_boost with design formulas)
    → OR Template fallback (29 templates, 9 categories)
    → Validators (structural, electrical, parameter, connection)
    → ASCII + SVG render → PreviewStore (token-based)
    → confirm_circuit → .psimsch file via bridge
```

Generators live in `generators/`. Templates in `data/circuit_templates.py`. Component library with pin definitions in `data/component_library.py`.

### Service Layer

`SimulationService` wraps every tool call with `_execute_with_audit()` — timing, SHA-256 input hashing, structured logging to 4 separate log files.

### Response Format

All tools return:
```json
{"success": true, "data": {...}, "message": "..."}
{"success": false, "error": {"code": "...", "message": "...", "suggestion": "..."}}
```

Built via `ResponseBuilder.success()` / `ResponseBuilder.error()` in `services/response.py`.

## Key Conventions

- Tool descriptions are in Korean (user-facing via Claude Desktop)
- `bridge_script.py` cannot import from `psim_mcp` — it runs in PSIM's Python 3.8
- Topology-specific simulation defaults (time_step, total_time) are in `data/simulation_defaults.py`
- Preview tokens have a TTL (default 3600s) managed by `PreviewStore`
- Path security: `allowed_project_dirs` whitelist in config; empty = no restriction (dev mode)
- `pytest-asyncio` with `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio`

## Test Fixtures

`tests/conftest.py` provides:
- `test_config` — `AppConfig(psim_mode="mock")` with temp dirs
- `sample_project_path` — pre-created `.psimsch` file

## Current PRD

`docs/ver1.1.2/` contains the active PRD:
- 01: Bridge persistent process (subprocess state preservation)
- 02: Hardcoding removal (SIMCONTROL position, simulation defaults)
- 03: Auto simulation flow (element cache, export path connection, sweep policy)
- 04: Claude Desktop integration config
