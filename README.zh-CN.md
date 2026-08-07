# psim-mcp

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="assets/psim-mcp-icon.png" alt="PSIM-MCP icon" width="180">
</p>

## 1. 系统概述与支持范围

psim-mcp 是一个 MCP 服务器，使客户端能够打开现有 Altair PSIM 电路、检查结构与结果、修改参数，并运行真实 PSIM 仿真和有界 Optuna 优化。

支持范围是现有 `.psimsch` 电路的自动化。本服务器不提供生成新拓扑或新电路的工具。

典型执行流程如下：

1. 使用 `open_project` 打开现有电路。
2. 使用 `get_project_info` 或 `import_circuit` 检查元件、参数与连接。
3. 单次修改使用 `set_parameter`，重复实验使用 `sweep_parameter`，有界优化使用 `optimize_circuit`。
4. 使用 `run_simulation` 运行 PSIM。
5. 使用 `analyze_simulation`、`analyze_existing` 或 `export_results` 检查结果。

`real` 模式使用实际安装的 PSIM。`mock` 模式是用于开发和 MCP 连接测试的确定性替代实现，不能作为真实电路性能的证据。

## 2. PSIM MCP 执行架构

```text
MCP client
    │  stdio 或 SSE
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

MCP 服务器运行于 Python 3.12 或更高版本。`real` adapter 会启动独立的 PSIM 兼容 Python 3.9 进程，并通过 JSON Lines 协议调用 PSIM API。PSIM 对象只存在于 bridge 进程中。

公开工具响应通常使用以下 envelope：

```json
{"success": true, "data": {}, "message": "..."}
```

失败响应提供 `success=false`、`error.code` 与 `error.message`。`optimize_circuit` 失败时还会在 `data` 中保留执行状态。

## 3. 要求与安装

| 项目 | 要求 | 用途 |
| --- | --- | --- |
| Python | 3.12 或更高 | MCP 服务器 |
| [uv](https://docs.astral.sh/uv/) | 最新稳定版 | 依赖与运行管理 |
| MCP 客户端 | 可选 | Claude Desktop、Codex 等 |
| Altair PSIM | 2026，`real` 模式必需 | 真实仿真 |
| PSIM 兼容 Python | 3.9，`real` 模式必需 | PSIM bridge |

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync
```

Optuna `>=4.9,<5` 是项目的普通 dependency，无需单独安装。若还需安装开发工具，请使用 `uv sync --all-extras`。

## 4. `real` 与 `mock` 执行模式

| 模式 | 是否需要 PSIM | 用途 | 结果解释 |
| --- | --- | --- | --- |
| `real` | 需要 | 打开、修改、仿真与优化真实电路 | 可与 PSIM artifact 一同作为产品结果 |
| `mock` | 不需要 | 工具连接、请求验证与测试 | 不得解释为真实电路性能 |

将仓库根目录中的 `.env.example` 复制为 `.env`，并设置实际安装路径。

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<user>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
ALLOWED_PROJECT_DIRS=C:\work\psim-projects,D:\shared\verified-circuits
```

`real` 模式要求同时设置 `PSIM_PATH`、`PSIM_PYTHON_EXE` 和 `PSIM_OUTPUT_DIR`。`ALLOWED_PROJECT_DIRS` 是以逗号分隔的绝对路径列表。为空时，可以使用 project validator 接受的绝对路径。

| 环境变量 | 默认值 | 含义 |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock` 或 `real` |
| `PSIM_PATH` | 无 | PSIM 安装目录 |
| `PSIM_PYTHON_EXE` | 无 | bridge 使用的 Python 可执行文件 |
| `PSIM_OUTPUT_DIR` | 无 | simulation 与 optimization artifact 根目录 |
| `ALLOWED_PROJECT_DIRS` | 空 | 允许访问的绝对 project path |
| `LOG_DIR` | `<repository>/logs` | 服务器日志目录 |
| `LOG_LEVEL` | `INFO` | `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL` |
| `SERVER_TRANSPORT` | `stdio` | `stdio` 或 `sse` |
| `SERVER_HOST` | `127.0.0.1` | SSE bind address |
| `SERVER_PORT` | `8000` | SSE port |
| `SIMULATION_TIMEOUT` | `300` | 默认 simulation timeout（秒） |
| `MAX_SWEEP_STEPS` | `100` | `sweep_parameter` 最大 step 数 |

## 5. MCP 客户端配置

在 Claude Desktop 的 `claude_desktop_config.json` 中添加以下服务器定义。

- Windows：`%APPDATA%\Claude\claude_desktop_config.json`
- macOS 上的 mock 或远程使用：`~/Library/Application Support/Claude/claude_desktop_config.json`

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

修改配置后，请完全退出并重新启动 MCP 客户端。若要直接运行服务器，请在仓库根目录执行 `uv run psim-mcp`。

## 6. 12 个公开工具的技术参考

| 工具 | 输入概要 | 行为与文件影响 |
| --- | --- | --- |
| `open_project` | `.psimsch` 绝对路径 | 打开现有 project 并返回 metadata |
| `get_project_info` | 无 | 读取已打开 project 的元件与 parameter |
| `import_circuit` | path、`include_graph` | 重建元件、net、dangling pin 与 simulation setting |
| `set_parameter` | component ID、parameter name、value | 将值保存到当前 `.psimsch`，因此可能修改 source |
| `sweep_parameter` | 单个 parameter range 与 step | 依次保存数值并仿真；最后一个值保留在已打开 project 中；受最大 step 限制 |
| `run_simulation` | 可选 timestep、total time、timeout、Simview | 运行当前 project 并生成 `.smv` 结果 |
| `export_results` | output directory、`json`/`csv`、signal list | 将最新 simulation 结果写入文件 |
| `compare_results` | 两个 result path、signal list | 基础比较 interface；没有 service 实现时返回 comparison 为 `null` 的 P1 响应 |
| `get_status` | 无 | 读取 PSIM availability、version 与 current project state |
| `analyze_simulation` | topology、target、waveform option | 仿真后生成 topology 特定 metric、sample 与可选 PNG |
| `analyze_existing` | `.smv`、topology、target、waveform option | 无需重新仿真即可分析现有结果；metric 为空时检查 `available_signals` |
| `optimize_circuit` | dynamic optimization request | 在隔离 copy 而非 source 上运行 sequential Optuna study |

`set_parameter` 与 `sweep_parameter` 会修改当前已打开文件。若手动实验需要保留 source，用户必须准备 working copy。`optimize_circuit` 使用下述独立 copy 与 restore 契约。

## 7. `optimize_circuit` 请求、执行与结果契约

使用项目提供的 `$psim-circuit-optimization` skill，可以指导 agent 按照此契约构造有界 study。

### 7.1 顶层 request

| 字段 | 类型 | 约束与含义 |
| --- | --- | --- |
| `source_project_path` | string | 现有 `.psimsch` 的绝对 path；不能为空 |
| `variables` | array | 1–3 个 unique decision variable |
| `measurements` | array | 至少1个；name 必须 unique |
| `objective` | array | 至少1个 measurement target term |
| `constraints` | array | 至少1个 hard constraint |
| `n_trials` | integer | 默认50，范围1–50 |
| `time_budget_seconds` | integer | 默认300，范围1–300；决定是否启动下一个 trial，不中断正在运行的 trial |
| `seed` | integer | 默认0，范围0–4,294,967,295 |

未知 field 会被拒绝。name 必须以 ASCII 字母开头，只能包含字母、数字和下划线，最长64个字符。

### 7.2 Decision variable 与 binding

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `name` | string | unique variable name |
| `min` / `max` | number | 两者均大于0，且 `min < max` |
| `bindings` | array | 至少1个；不得重复 component-parameter pair |
| `log_scale` | boolean | 默认 `true`；控制 Optuna log sampling |

| `component_kind` | `parameter_name` | 附加规则 |
| --- | --- | --- |
| `L` | `Inductance` | 已验证的 inductor binding |
| `C` | `Capacitance` | 已验证的 capacitor binding |
| `R` | `Resistance` | 必须设置 `role: "design"`；load resistor 会被拒绝 |

一个 variable 含有多个 binding 时，同一个建议值会应用到所有 binding。component ID 与 range 必须根据真实 project 和 engineering evidence 确认。

### 7.3 Measurement、objective 与 constraint

| Measurement 字段 | 类型 | 约束 |
| --- | --- | --- |
| `name` | string | unique measurement name |
| `signal` | string | 真实 `.smv` signal name，1–128字符 |
| `function` | enum | `mean`、`ripple_pp`、`ripple_percent`、`peak`、`rms` |
| `window.start_fraction` | number | `0 <= start < 1` |
| `window.end_fraction` | number | `0 < end <= 1` 且 `start < end` |
| `window.min_samples` | integer | 默认2，最小2 |

objective 是归一化平方误差之和：

```text
cost = Σ weight × ((measurement - target) / normalization_scale)²
```

`weight` 默认为1。省略 `scale` 时使用 `abs(target)`。target 为0时必须显式指定正 `scale`。

hard constraint 的 `operator` 为 `<=` 或 `>=`，`scale` 必须为正。只有归一化 residual 不大于0的 trial 才是 feasible。

```text
operator <= : residual = (measurement - limit) / scale
operator >= : residual = (limit - measurement) / scale
```

### 7.4 Study lifecycle

1. 验证 source path 与 `PSIM_OUTPUT_DIR`。
2. 创建 `optuna-*` study directory 与 `study.jsonl`。
3. 创建 `source-copy.psimsch` 和 `working.psimsch`，并比较 SHA-256。
4. 保存之前的 PSIM project path，并获取 adapter session lease。
5. 在 working copy 上运行 baseline。
6. seeded TPE sampler 提出 trial 数值，PSIM 依次运行。
7. 在 measurement 有效且满足 hard constraint 的 trial 中选择 cost 最小者。
8. 从 source copy 创建 `best.psimsch`，应用选定值，并作为 `best.smv` 重新运行。
9. 重新打开之前的 project，再次验证 source SHA-256。
10. 将 trial 与 terminal record 写入 JSONL ledger 并返回结果。

### 7.5 结果字段与状态

| 字段 | 含义 |
| --- | --- |
| `state` | `completed`、`time_budget_reached`、`no_feasible_trial`、`failed`、`cancelled` 等 terminal state |
| `stop_reason` | `trials_exhausted`、`time_budget_reached` 或 validation/setup/restore 失败原因 |
| `trials_complete` / `trials_failed` | completed 与 failed trial 数 |
| `best_params` / `best_cost` / `best_metrics` | 经 final rerun 验证的选定值与结果 |
| `constraint_residuals` | 不大于0表示相应 hard constraint 通过 |
| `study_dir` / `ledger_path` | study directory 与 JSONL evidence ledger |
| `best_project_path` | 含选定值的最终 `best.psimsch` |
| `result_paths` | 实际存在的 baseline、trial 与 best `.smv` path |
| `source_hash_before` / `source_hash_after` | source 保持不变的 SHA-256 evidence |
| `restoration_status` | `restored`、`no_previous_project` 或失败说明 |
| `elapsed_seconds` | 从 setup 到 terminal 记录的耗时 |
| `error` | 失败说明；成功时为 `null` |

signal 缺失、sample 不足、non-finite value、非法 binding、simulation 失败、无 feasible trial、source 被修改或 session restore 失败都不会报告为成功。

## 8. JSON 请求与响应示例

以下数值与 signal name 仅演示某个特定电路的 request shape，并不是其他电路的 engineering recommendation。

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

缩略成功响应示例：

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

## 9. 安全规则与排除目标

- 只使用可信的 `.psimsch` 与 `.smv` 文件。
- 使用 `ALLOWED_PROJECT_DIRS` 将可访问 project path 限制到最小范围。
- 不要在 source 上运行 `set_parameter` 或 `sweep_parameter`。请打开用户明确准备的 working copy。
- 仅向 `optimize_circuit` 传递在真实 project 中确认过的 component ID、signal name、unit、range、target 与 hard limit。
- 不优化 solver timestep、safety/protection limit、topology、load resistance 或 arbitrary gate schedule。
- `window` 只选择 waveform 的一部分。没有独立的物理 settling evidence 时，不要称为 steady state。
- `time_budget_seconds` 不会强制停止正在运行的 PSIM trial。
- 成功报告必须具有 feasible best trial、final rerun artifact、restore 成功以及相同的 before/after source hash。
- `mock` 结果不是实际 PSIM 性能或安全性的证据。

## 10. 开发与验证

```bash
uv sync --all-extras
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

需要实际 PSIM 的检查应在 Windows 主机上设置 `PSIM_MODE=real` 和必需路径后单独运行。仓库将 unit test、stdio integration test 和 opt-in real-PSIM marker 分开维护。

## 许可证

MIT
