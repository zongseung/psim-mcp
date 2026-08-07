# psim-mcp

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="assets/psim-mcp-icon.png" alt="PSIM-MCP icon" width="180">
</p>

## 1. System overview and supported scope

psim-mcp is a server that lets MCP clients open existing Altair PSIM circuits, inspect their structure and results, change parameters, and run real PSIM simulations and bounded Optuna optimization.

The supported scope is automation of existing `.psimsch` circuits. The server does not provide a tool for generating new topologies or circuits.

A typical execution flow is:

1. Open an existing circuit with `open_project`.
2. Inspect components, parameters, and connections with `get_project_info` or `import_circuit`.
3. Use `set_parameter` for one change, `sweep_parameter` for repeated experiments, or `optimize_circuit` for bounded optimization.
4. Run PSIM with `run_simulation`.
5. Inspect results with `analyze_simulation`, `analyze_existing`, or `export_results`.

`real` mode uses an installed PSIM instance. `mock` mode is a deterministic substitute for development and MCP connection tests; it is not evidence of real circuit performance.

## 2. PSIM MCP execution architecture

```text
MCP client
    │  stdio or SSE
    ▼
FastMCP tool layer
    │  request validation · response normalization · audit logging
    ▼
Project / Simulation / Analysis / Optimization services
    │
    ├─ mock adapter ── deterministic development results
    │
    └─ real adapter ── Python 3.9 bridge ── PSIM 2026
                                             │
                                             ├─ .psimsch
                                             └─ .smv / JSON / CSV / PNG
```

The MCP server runs on Python 3.12 or later. The `real` adapter starts a separate PSIM-compatible Python 3.9 process and calls the PSIM API over a JSON-lines protocol. PSIM objects exist only inside the bridge process.

Public tool responses normally use this envelope:

```json
{"success": true, "data": {}, "message": "..."}
```

Failure responses provide `success=false`, `error.code`, and `error.message`. A failed `optimize_circuit` response also retains the execution state under `data`.

## 3. Requirements and installation

| Item | Requirement | Purpose |
| --- | --- | --- |
| Python | 3.12 or later | MCP server |
| [uv](https://docs.astral.sh/uv/) | Current stable release | Dependency and execution management |
| MCP client | Optional | Claude Desktop, Codex, and others |
| Altair PSIM | 2026, required for `real` mode | Real simulation |
| PSIM-compatible Python | 3.9, required for `real` mode | PSIM bridge |

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync
```

Optuna `>=4.9,<5` is a normal project dependency and requires no separate installation. Use `uv sync --all-extras` to install the development tools as well.

## 4. `real` and `mock` execution modes

| Mode | PSIM required | Purpose | Result interpretation |
| --- | --- | --- | --- |
| `real` | Yes | Open, edit, simulate, and optimize real circuits | May be used as product evidence together with PSIM artifacts |
| `mock` | No | Tool wiring, request validation, and tests | Must not be interpreted as real circuit performance |

Copy `.env.example` to `.env` in the repository root and set the actual installation paths.

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<user>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
ALLOWED_PROJECT_DIRS=C:\work\psim-projects,D:\shared\verified-circuits
```

`real` mode requires `PSIM_PATH`, `PSIM_PYTHON_EXE`, and `PSIM_OUTPUT_DIR`. `ALLOWED_PROJECT_DIRS` is a comma-separated list of absolute paths. When empty, paths accepted by the project validator may be used.

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock` or `real` |
| `PSIM_PATH` | None | PSIM installation directory |
| `PSIM_PYTHON_EXE` | None | Python executable for the bridge |
| `PSIM_OUTPUT_DIR` | None | Root for simulation and optimization artifacts |
| `ALLOWED_PROJECT_DIRS` | Empty | Allowed absolute project paths |
| `LOG_DIR` | `<repository>/logs` | Server log directory |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `SERVER_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `SERVER_HOST` | `127.0.0.1` | SSE bind address |
| `SERVER_PORT` | `8000` | SSE port |
| `SIMULATION_TIMEOUT` | `300` | Default simulation timeout in seconds |
| `MAX_SWEEP_STEPS` | `100` | Maximum `sweep_parameter` steps |

## 5. MCP client configuration

Add the following server definition to Claude Desktop's `claude_desktop_config.json`.

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS for mock or remote use: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "psim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\psim-mcp", "psim-mcp"],
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2026",
        "PSIM_PYTHON_EXE": "C:\\Users\\<user>\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
        "PSIM_OUTPUT_DIR": "C:\\path\\to\\psim-mcp\\output",
        "ALLOWED_PROJECT_DIRS": "C:\\work\\psim-projects"
      }
    }
  }
}
```

After changing the configuration, fully quit and restart the MCP client. To run the server directly, use `uv run psim-mcp` from the repository root.

## 6. Technical reference for the 12 public tools

| Tool | Input summary | Behavior and file impact |
| --- | --- | --- |
| `open_project` | Absolute `.psimsch` path | Opens an existing project and returns metadata |
| `get_project_info` | None | Reads components and parameters from the open project |
| `import_circuit` | Path, `include_graph` | Reconstructs components, nets, dangling pins, and simulation settings |
| `set_parameter` | Component ID, parameter name, value | Saves a value to the current `.psimsch` and can therefore modify the source |
| `sweep_parameter` | One parameter range and step | Saves values and simulates sequentially; the final value remains in the open project; maximum-step limit applies |
| `run_simulation` | Optional timestep, total time, timeout, Simview | Runs the current project and creates an `.smv` result |
| `export_results` | Output directory, `json`/`csv`, signal list | Writes the latest simulation result to files |
| `compare_results` | Two result paths, signal list | Basic comparison interface; returns a P1 response with `null` comparison when no service implementation exists |
| `get_status` | None | Reads PSIM availability, version, and current project state |
| `analyze_simulation` | Topology, targets, waveform options | Simulates and produces topology-specific metrics, samples, and an optional PNG |
| `analyze_existing` | `.smv`, topology, targets, waveform options | Analyzes an existing result without rerunning; inspect `available_signals` when metrics are empty |
| `optimize_circuit` | Dynamic optimization request | Runs a sequential Optuna study on isolated copies rather than the source |

`set_parameter` and `sweep_parameter` modify the currently open file. For manual experiments that must preserve the source, the user must prepare a working copy. `optimize_circuit` provides the separate copy and restoration contract described below.

## 7. `optimize_circuit` request, execution, and result contract

The project-provided `$psim-circuit-optimization` skill can direct an agent to construct a bounded study according to this contract.

### 7.1 Top-level request

| Field | Type | Constraint and meaning |
| --- | --- | --- |
| `source_project_path` | string | Absolute path to an existing `.psimsch`; cannot be empty |
| `variables` | array | 1–3 unique decision variables |
| `measurements` | array | One or more; names must be unique |
| `objective` | array | One or more measurement target terms |
| `constraints` | array | One or more hard constraints |
| `n_trials` | integer | Default 50, allowed range 1–50 |
| `time_budget_seconds` | integer | Default 300, allowed range 1–300; decides whether another trial may start and does not interrupt an in-flight trial |
| `seed` | integer | Default 0, allowed range 0–4,294,967,295 |

Unknown fields are rejected. Names start with an ASCII letter, contain only letters, digits, and underscores, and are at most 64 characters long.

### 7.2 Decision variables and bindings

| Field | Type | Constraint |
| --- | --- | --- |
| `name` | string | Unique variable name |
| `min` / `max` | number | Both greater than zero, with `min < max` |
| `bindings` | array | One or more; duplicate component-parameter pairs are rejected |
| `log_scale` | boolean | Defaults to `true`; controls Optuna log sampling |

| `component_kind` | `parameter_name` | Additional rule |
| --- | --- | --- |
| `L` | `Inductance` | Verified inductor binding |
| `C` | `Capacitance` | Verified capacitor binding |
| `R` | `Resistance` | Requires `role: "design"`; load resistors are rejected |

When one variable has multiple bindings, its proposed value is applied to every binding. Confirm component IDs and ranges from the real project and engineering evidence.

### 7.3 Measurements, objectives, and constraints

| Measurement field | Type | Constraint |
| --- | --- | --- |
| `name` | string | Unique measurement name |
| `signal` | string | Actual `.smv` signal name, 1–128 characters |
| `function` | enum | `mean`, `ripple_pp`, `ripple_percent`, `peak`, `rms` |
| `window.start_fraction` | number | `0 <= start < 1` |
| `window.end_fraction` | number | `0 < end <= 1`, with `start < end` |
| `window.min_samples` | integer | Default 2, minimum 2 |

The objective is the sum of normalized squared errors:

```text
cost = Σ weight × ((measurement - target) / normalization_scale)²
```

`weight` defaults to 1. When `scale` is omitted, `abs(target)` is used. A target of zero requires an explicit positive `scale`.

The hard-constraint `operator` is `<=` or `>=`, and `scale` must be positive. Only trials whose normalized residuals are at most zero are feasible.

```text
operator <= : residual = (measurement - limit) / scale
operator >= : residual = (limit - measurement) / scale
```

### 7.4 Study lifecycle

1. Validate the source path and `PSIM_OUTPUT_DIR`.
2. Create an `optuna-*` study directory and `study.jsonl`.
3. Create `source-copy.psimsch` and `working.psimsch`, then compare SHA-256 hashes.
4. Preserve the previous PSIM project path and acquire an adapter session lease.
5. Run a baseline on the working copy.
6. Let the seeded TPE sampler propose trial values and run PSIM sequentially.
7. Select the minimum-cost result among trials with valid measurements and satisfied hard constraints.
8. Create `best.psimsch` from the source copy, apply the selected values, and rerun it as `best.smv`.
9. Reopen the previous project and verify the source SHA-256 again.
10. Write trial and terminal records to the JSONL ledger and return the result.

### 7.5 Result fields and states

| Field | Meaning |
| --- | --- |
| `state` | Terminal state such as `completed`, `time_budget_reached`, `no_feasible_trial`, `failed`, or `cancelled` |
| `stop_reason` | `trials_exhausted`, `time_budget_reached`, or a validation/setup/restoration failure reason |
| `trials_complete` / `trials_failed` | Counts of completed and failed trials |
| `best_params` / `best_cost` / `best_metrics` | Selected values and results verified by the final rerun |
| `constraint_residuals` | A value at most zero means the corresponding hard constraint passed |
| `study_dir` / `ledger_path` | Study directory and JSONL evidence ledger |
| `best_project_path` | Final `best.psimsch` with the selected values |
| `result_paths` | Existing baseline, trial, and best `.smv` paths |
| `source_hash_before` / `source_hash_after` | SHA-256 evidence that the source stayed unchanged |
| `restoration_status` | `restored`, `no_previous_project`, or a failure description |
| `elapsed_seconds` | Elapsed time from setup through terminal recording |
| `error` | Failure description; `null` on success |

Missing signals, insufficient samples, non-finite values, invalid bindings, simulation failure, no feasible trial, source mutation, and session restoration failure are not reported as success.

## 8. JSON request and response examples

The following values and signal names demonstrate the request shape for one particular circuit. They are not engineering recommendations for another circuit.

```json
{
  "request": {
    "source_project_path": "C:\\work\\psim-projects\\inverter.psimsch",
    "variables": [
      {
        "name": "L1_inductance",
        "min": 0.002,
        "max": 0.0032,
        "bindings": [
          {
            "component_id": "L1",
            "component_kind": "L",
            "parameter_name": "Inductance"
          }
        ],
        "log_scale": true
      },
      {
        "name": "C1_capacitance",
        "min": 0.0000024,
        "max": 0.0000027,
        "bindings": [
          {
            "component_id": "C1",
            "component_kind": "C",
            "parameter_name": "Capacitance"
          }
        ],
        "log_scale": true
      }
    ],
    "measurements": [
      {
        "name": "vout_rms",
        "signal": "Vout",
        "function": "rms",
        "window": {
          "start_fraction": 0.8,
          "end_fraction": 1.0,
          "min_samples": 2000
        }
      },
      {
        "name": "vout_ripple_pp",
        "signal": "Vout",
        "function": "ripple_pp",
        "window": {
          "start_fraction": 0.8,
          "end_fraction": 1.0,
          "min_samples": 2000
        }
      }
    ],
    "objective": [
      {"measurement": "vout_rms", "target": 155.6}
    ],
    "constraints": [
      {
        "measurement": "vout_ripple_pp",
        "operator": "<=",
        "limit": 446.0,
        "scale": 1.0
      }
    ],
    "n_trials": 3,
    "time_budget_seconds": 60,
    "seed": 7
  }
}
```

Abbreviated success response:

```json
{
  "success": true,
  "data": {
    "success": true,
    "state": "completed",
    "stop_reason": "trials_exhausted",
    "trials_complete": 3,
    "trials_failed": 0,
    "best_params": {
      "L1_inductance": 0.00305,
      "C1_capacitance": 0.00000258
    },
    "best_cost": 7.6e-11,
    "best_metrics": {
      "vout_rms": 155.601,
      "vout_ripple_pp": 443.604
    },
    "constraint_residuals": [-2.396],
    "best_project_path": "C:\\output\\optuna-example\\best.psimsch",
    "source_hash_before": "<sha256>",
    "source_hash_after": "<sha256>",
    "source_changed_during_study": false,
    "restoration_status": "restored",
    "study_dir": "C:\\output\\optuna-example",
    "ledger_path": "C:\\output\\optuna-example\\study.jsonl",
    "result_paths": [
      "C:\\output\\optuna-example\\baseline.smv",
      "C:\\output\\optuna-example\\trial-0000.smv",
      "C:\\output\\optuna-example\\best.smv"
    ],
    "elapsed_seconds": 13.1,
    "error": null
  },
  "message": "Optimization completed"
}
```

## 9. Safety rules and excluded targets

- Use only trusted `.psimsch` and `.smv` files.
- Minimize accessible project paths with `ALLOWED_PROJECT_DIRS`.
- Do not run `set_parameter` or `sweep_parameter` on the source. Open an explicitly prepared user working copy.
- Pass only component IDs, signal names, units, ranges, targets, and hard limits confirmed from the real project to `optimize_circuit`.
- Do not optimize solver timestep, safety/protection limits, topology, load resistance, or arbitrary gate schedules.
- A `window` only selects part of a waveform. Do not call a result steady state without independent physical settling evidence.
- `time_budget_seconds` does not force-stop an in-flight PSIM trial.
- A success report requires a feasible best trial, final rerun artifact, successful restoration, and identical before/after source hashes.
- `mock` results are not evidence of real PSIM performance or safety.

## 10. Development and verification

```bash
uv sync --all-extras
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

Run checks that require real PSIM separately on a Windows host after setting `PSIM_MODE=real` and the required paths. The repository separates unit tests, the stdio integration test, and opt-in real-PSIM markers.

## License

MIT
