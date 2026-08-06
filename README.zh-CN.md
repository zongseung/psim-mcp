# psim-mcp

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

## 产品范围

这是一个 MCP 服务器，可在 Claude Desktop 中打开现有 PSIM 电路、分析其结构和结果、按需修改参数，然后运行仿真。不提供新建电路的工具。

## 现有电路工作流程

1. 使用 `open_project` 打开现有 `.psimsch` 文件。
2. 使用 `get_project_info` 或 `import_circuit` 查看电路结构。
3. 如有需要，使用 `set_parameter` 或 `sweep_parameter`。
4. 运行 `run_simulation`，再使用 `analyze_simulation`、`analyze_existing` 或 `export_results` 查看结果。

`set_parameter` 会将更改写入原始项目文件。操作前请先复制原始文件。

## 功能与限制

在 12 个工具中，稳定工具包括 `open_project`、`get_project_info`、`import_circuit`、`run_simulation`、`export_results`、`get_status`、`analyze_simulation` 和 `analyze_existing`。

`sweep_parameter` 是采用固定循环方式的实验性功能。`compare_results` 是 P1 存根，`optimize_circuit` 也是实验性功能。优化所需的 Optuna 默认不会安装。

## 要求

| 项目 | 必需 | 说明 |
| --- | --- | --- |
| Python 3.12+ | 是 | MCP 服务器 |
| [uv](https://docs.astral.sh/uv/) | 是 | 包管理 |
| Claude Desktop | 可选 | MCP 客户端 |
| Altair PSIM 2026 | real 模式下必需 | 实际仿真 |
| PSIM Python 3.9 | real 模式下必需 | PSIM 桥接 |

## 安装

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync --all-extras
```

## real 模式快速开始

将 `.env.example` 复制为 `.env`，然后设置安装路径。Git 会忽略 `.env`，请勿将其添加到仓库。

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<사용자>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
```

省略 `ALLOWED_PROJECT_DIRS` 时，可以使用 validator 接受的任何绝对项目路径。如需限制，请设置以逗号分隔的绝对路径。

## Claude Desktop 配置

将以下内容添加到 `claude_desktop_config.json`。

本地 real 模式需要 Windows PSIM 主机。请将以下 JSON 中的所有占位路径替换为实际本地路径。

- Windows：`%APPDATA%\Claude\claude_desktop_config.json`
- macOS（用于 mock 或远程场景）：`~/Library/Application Support/Claude/claude_desktop_config.json`

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

更改配置后，请完全退出并重新启动 Claude Desktop。

## 12 个工具参考

| 工具 | 说明 |
| --- | --- |
| `open_project` | 打开现有项目 |
| `get_project_info` | 查看项目结构 |
| `import_circuit` | 导入现有电路 |
| `set_parameter` | 修改组件参数并写入原始文件 |
| `sweep_parameter` | 参数扫描（实验性固定循环） |
| `run_simulation` | 运行仿真 |
| `export_results` | 将结果导出为 JSON 或 CSV |
| `compare_results` | 比较结果（P1 存根） |
| `get_status` | 查看服务器和 PSIM 状态 |
| `analyze_simulation` | 运行仿真并分析结果 |
| `analyze_existing` | 分析现有 `.smv` 结果 |
| `optimize_circuit` | 优化电路参数（实验性，需要单独安装 Optuna） |

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock` 或 `real` |
| `PSIM_PATH` | 无 | real 模式下的 PSIM 安装路径 |
| `PSIM_PYTHON_EXE` | 无 | PSIM Python 3.9 可执行文件 |
| `PSIM_OUTPUT_DIR` | 无 | real 模式所需的仿真结果目录 |
| `LOG_DIR` | `<저장소>/logs` | 日志目录 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `SERVER_TRANSPORT` | `stdio` | `stdio` 或 `sse` |
| `SERVER_HOST` | `127.0.0.1` | SSE 服务器主机 |
| `SERVER_PORT` | `8000` | SSE 服务器端口 |
| `SIMULATION_TIMEOUT` | `300` | 仿真超时时间（秒） |
| `MAX_SWEEP_STEPS` | `100` | 最大扫描步数 |
| `ALLOWED_PROJECT_DIRS` | 省略 | 允许的绝对项目路径列表；省略时可使用 validator 接受的所有路径 |

## 安全

- 仅打开可信的项目文件。
- `set_parameter` 会修改原始文件，请使用备份副本操作。
- 可使用 `ALLOWED_PROJECT_DIRS` 限制项目路径范围。

## 开发

```bash
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

## 许可证

MIT
