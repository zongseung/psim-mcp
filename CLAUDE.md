# CLAUDE.md

## Build & Test Commands

```bash
uv sync --all-extras
uv run pytest tests/unit -q
uv run pytest tests/unit/test_simulation_service.py -v
uv run pytest tests/unit -k "test_sweep" -v
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run psim-mcp
uv run mcp dev src/psim_mcp/server.py
```

All Python operations must use `uv run`. Never use bare `python`, `pip`, or `python -m`.

## Project Direction

VER2 is the public product: `import_circuit` → understand → `set_parameter` → `run_simulation` → analysis. The server registers 12 MCP tools for existing-project, parameter, simulation, result, and analysis workflows.

`CircuitGraph` is the importer representation of an existing circuit: components plus electrical nets reconstructed from PSIM conversion output. Treat it as the format returned by the read-modify workflow.

## Architecture

### Dual Python Environments

The MCP server runs on Python 3.12+. PSIM's `psimapipy` runs in its bundled Python 3.8/3.9 process. Communication is JSON IPC over a subprocess bridge.

```
Claude Desktop ─stdio─→ MCP Server (Python 3.12+)
                              │
                       RealPsimAdapter
                              │ stdin/stdout JSON lines
                       bridge_script.py (Python 3.8/3.9)
                              │
                       psimapipy → PSIM engine
```

`bridge_script.py` cannot import from `psim_mcp`. Keep bridge inputs and outputs JSON-compatible, run subprocesses with `shell=False`, and preserve the Python 3.8-compatible bridge boundary.

### App Factory Pattern

`server.py` uses `create_app(config)` to create isolated FastMCP instances. Module-level `mcp` and `config` use `__getattr__` for lazy singleton initialization.

```python
app = create_app(AppConfig(psim_mode="mock"))
```

### Adapter Pattern

- `BasePsimAdapter`: adapter interface.
- `MockPsimAdapter`: in-memory adapter for tests and development.
- `RealPsimAdapter`: long-running bridge subprocess, serialized with `asyncio.Lock`.

Select with `PSIM_MODE=mock` (default) or `PSIM_MODE=real`. Real mode requires `PSIM_PATH`, `PSIM_PYTHON_EXE`, `PSIM_PROJECT_DIR`, and `PSIM_OUTPUT_DIR`.

### Services and Response Contract

- `ProjectService`: open and inspect existing projects.
- `ParameterService`: modify parameters on the open project.
- `SimulationService`: simulate, sweep, export, compare, and report status.

Tools use `@tool_handler("name")` for exception handling, JSON serialization, LLM-output sanitization, and the 50KB response limit. Responses use `ResponseBuilder`:

```json
{"success": true, "data": {}, "message": "..."}
{"success": false, "error": {"code": "...", "message": "...", "suggestion": "..."}}
```

## Existing-Circuit Import

`importer/parser.py` parses `PsimConvertToPython` output. `importer/net_builder.py` reconstructs electrical nets, including T-branches, non-connecting crossovers, labels, and ground. `importer/roundtrip.py` emits scripts and compares reconstructed nets.

Keep the importer coverage in `tests/unit/test_import_circuit.py` and `tests/unit/test_importer_reconstruction.py` passing when changing this path.

## Key Conventions

- Tool descriptions are Korean user-facing text.
- `allowed_project_dirs` is the project-path whitelist; an empty list is unrestricted development mode.
- `pytest-asyncio` uses `asyncio_mode = "auto"`.
- PSIM native `MULTI_*` elements require a Python-list `PORTS` value; transformers use `Np__primary_` and `Ns__secondary_` rather than `Ratio`.
