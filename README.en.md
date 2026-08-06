# psim-mcp

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

## Product scope

An MCP server for Claude Desktop that opens existing PSIM circuits, analyzes their structure and results, changes needed parameters, and runs simulations. It does not provide tools for creating new circuits.

## Existing-circuit workflow

1. Open an existing `.psimsch` file with `open_project`.
2. Inspect the circuit structure with `get_project_info` or `import_circuit`.
3. Use `set_parameter` or `sweep_parameter` when needed.
4. Run `run_simulation`, then inspect results with `analyze_simulation`, `analyze_existing`, and `export_results`.

`set_parameter` saves changes to the original project file. Copy the original before working on it.

## Capabilities and limits

The eight stable tools are `open_project`, `get_project_info`, `import_circuit`, `run_simulation`, `export_results`, `get_status`, `analyze_simulation`, and `analyze_existing`.

`sweep_parameter` is experimental and uses a fixed-loop approach. `compare_results` is a P1 stub, and `optimize_circuit` is experimental. Optuna, required for optimization, is not included in the default installation.

## Requirements

| Item | Required | Notes |
| --- | --- | --- |
| Python 3.12+ | Yes | MCP server |
| [uv](https://docs.astral.sh/uv/) | Yes | Package management |
| Claude Desktop | Optional | MCP client |
| Altair PSIM 2026 | Yes in real mode | Real simulation |
| PSIM Python 3.9 | Yes in real mode | PSIM bridge |

## Installation

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync --all-extras
```

## Real-mode quickstart

Copy `.env.example` to `.env`, then set your installation paths. Git ignores `.env`; do not add it to the repository.

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<사용자>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
```

When `ALLOWED_PROJECT_DIRS` is omitted, any absolute project path accepted by the validator may be used. To restrict access, set comma-separated absolute paths.

## Claude Desktop configuration

Add the following to `claude_desktop_config.json`.

Local real mode requires a Windows host with PSIM installed. Replace every placeholder path in the JSON below with the actual local path.

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS (mock or remote use): `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "psim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\psim-mcp", "psim-mcp"],
      "env": {
        "PSIM_MODE": "real",
        "PSIM_PATH": "C:\\Altair\\Altair_PSIM_2026",
        "PSIM_PYTHON_EXE": "C:\\Users\\<사용자>\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
        "PSIM_OUTPUT_DIR": "./output"
      }
    }
  }
}
```

After changing the configuration, fully quit and restart Claude Desktop.

## 12-tool reference

| Tool | Description |
| --- | --- |
| `open_project` | Open an existing project |
| `get_project_info` | View project structure |
| `import_circuit` | Import an existing circuit |
| `set_parameter` | Change a component parameter and save the original |
| `sweep_parameter` | Parameter sweep (experimental fixed-loop) |
| `run_simulation` | Run a simulation |
| `export_results` | Export results as JSON or CSV |
| `compare_results` | Compare results (P1 stub) |
| `get_status` | Check server and PSIM status |
| `analyze_simulation` | Run a simulation and analyze results |
| `analyze_existing` | Analyze an existing `.smv` result |
| `optimize_circuit` | Optimize circuit parameters (experimental; install Optuna separately) |

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock` or `real` |
| `PSIM_PATH` | None | PSIM installation path for real mode |
| `PSIM_PYTHON_EXE` | None | PSIM Python 3.9 executable |
| `PSIM_OUTPUT_DIR` | None | Simulation-results directory required in real mode |
| `LOG_DIR` | `<저장소>/logs` | Log directory |
| `LOG_LEVEL` | `INFO` | Log level |
| `SERVER_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `SERVER_HOST` | `127.0.0.1` | SSE server host |
| `SERVER_PORT` | `8000` | SSE server port |
| `SIMULATION_TIMEOUT` | `300` | Simulation timeout in seconds |
| `MAX_SWEEP_STEPS` | `100` | Maximum sweep steps |
| `ALLOWED_PROJECT_DIRS` | Omitted | Allowed absolute project paths; when omitted, all validator-accepted paths may be used |

## Safety

- Open only project files you trust.
- `set_parameter` changes the original file; work on a backup copy.
- Use `ALLOWED_PROJECT_DIRS` to limit the project-path scope.

## Development

```bash
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

## License

MIT
