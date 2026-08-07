# psim-mcp

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="assets/psim-mcp-icon.png" alt="PSIM-MCP icon" width="180">
</p>

## 1. システム概要とサポート範囲

psim-mcpは、MCPクライアントから既存のAltair PSIM回路を開き、構造と結果を調査し、パラメーターを変更し、実際のPSIMシミュレーションと制限付きOptuna最適化を実行するためのサーバーです。

サポート範囲は既存の`.psimsch`回路の自動化です。新しいトポロジーや回路を生成するツールは提供しません。

代表的な実行フローは次のとおりです。

1. `open_project`で既存回路を開きます。
2. `get_project_info`または`import_circuit`で部品、パラメーター、接続を確認します。
3. 1回の変更には`set_parameter`、反復実験には`sweep_parameter`、制限付き最適化には`optimize_circuit`を使用します。
4. `run_simulation`でPSIMを実行します。
5. `analyze_simulation`、`analyze_existing`、`export_results`で結果を確認します。

`real`モードは実際のPSIMを使用します。`mock`モードは開発とMCP接続試験用の決定論的な代替実装であり、実回路性能の根拠ではありません。

## 2. PSIM MCP実行アーキテクチャ

```text
MCP client
    │  stdio または SSE
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

MCPサーバーはPython 3.12以降で動作します。`real` adapterはPSIM互換のPython 3.9プロセスを別途起動し、JSON LinesプロトコルでPSIM APIを呼び出します。PSIMオブジェクトはbridgeプロセス内にのみ存在します。

公開ツールの応答は通常、次のenvelopeを使用します。

```json
{"success": true, "data": {}, "message": "..."}
```

失敗応答は`success=false`、`error.code`、`error.message`を返します。`optimize_circuit`が失敗した場合は、実行状態も`data`に保持されます。

## 3. 要件とインストール

| 項目 | 要件 | 用途 |
| --- | --- | --- |
| Python | 3.12以降 | MCPサーバー |
| [uv](https://docs.astral.sh/uv/) | 最新安定版 | 依存関係と実行管理 |
| MCPクライアント | 任意 | Claude Desktop、Codexなど |
| Altair PSIM | 2026、`real`モードで必須 | 実シミュレーション |
| PSIM互換Python | 3.9、`real`モードで必須 | PSIM bridge |

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync
```

Optuna `>=4.9,<5`は通常のproject dependencyであり、別途インストールする必要はありません。開発ツールも含める場合は`uv sync --all-extras`を使用します。

## 4. `real`と`mock`実行モード

| モード | PSIM | 用途 | 結果の解釈 |
| --- | --- | --- | --- |
| `real` | 必須 | 実回路を開く・変更する・シミュレーションする・最適化する | PSIM artifactとともに製品結果として利用可能 |
| `mock` | 不要 | ツール接続、要求検証、テスト | 実回路性能として解釈しない |

リポジトリルートの`.env.example`を`.env`へコピーし、実際のインストールパスを設定します。

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<user>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
ALLOWED_PROJECT_DIRS=C:\work\psim-projects,D:\shared\verified-circuits
```

`real`モードには`PSIM_PATH`、`PSIM_PYTHON_EXE`、`PSIM_OUTPUT_DIR`が必要です。`ALLOWED_PROJECT_DIRS`はカンマ区切りの絶対パス一覧です。空の場合はproject validatorが許可する絶対パスを使用できます。

| 環境変数 | 既定値 | 意味 |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock`または`real` |
| `PSIM_PATH` | なし | PSIMインストールディレクトリ |
| `PSIM_PYTHON_EXE` | なし | bridge用Python実行ファイル |
| `PSIM_OUTPUT_DIR` | なし | simulation・optimization artifactのルート |
| `ALLOWED_PROJECT_DIRS` | 空 | 許可する絶対project path |
| `LOG_DIR` | `<repository>/logs` | サーバーログディレクトリ |
| `LOG_LEVEL` | `INFO` | `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL` |
| `SERVER_TRANSPORT` | `stdio` | `stdio`または`sse` |
| `SERVER_HOST` | `127.0.0.1` | SSE bind address |
| `SERVER_PORT` | `8000` | SSE port |
| `SIMULATION_TIMEOUT` | `300` | 既定simulation timeout（秒） |
| `MAX_SWEEP_STEPS` | `100` | `sweep_parameter`の最大step数 |

## 5. MCPクライアント設定

Claude Desktopの`claude_desktop_config.json`に次のサーバー定義を追加します。

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOSでmockまたはremote使用: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

設定変更後はMCPクライアントを完全に終了して再起動します。サーバーを直接実行する場合は、リポジトリルートで`uv run psim-mcp`を使用します。

## 6. 公開ツール12個の技術リファレンス

| ツール | 入力概要 | 動作とファイルへの影響 |
| --- | --- | --- |
| `open_project` | `.psimsch`絶対パス | 既存projectを開きmetadataを返す |
| `get_project_info` | なし | 開いているprojectの部品とparameterを取得 |
| `import_circuit` | path、`include_graph` | 部品、net、dangling pin、simulation settingを復元 |
| `set_parameter` | component ID、parameter name、value | 現在の`.psimsch`へ値を保存するためsourceを変更可能 |
| `sweep_parameter` | 1つのparameter rangeとstep | 値を順次保存してsimulationし、最後の値が開いたprojectに残る。最大step制限あり |
| `run_simulation` | 任意のtimestep、total time、timeout、Simview | 現在のprojectを実行して`.smv`結果を生成 |
| `export_results` | output directory、`json`/`csv`、signal list | 最新simulation結果をファイルへ出力 |
| `compare_results` | 2つのresult path、signal list | 基本比較interface。service実装がなければcomparisonが`null`のP1応答 |
| `get_status` | なし | PSIM availability、version、current project stateを取得 |
| `analyze_simulation` | topology、target、waveform option | simulation後にtopology別metric、sample、任意PNGを生成 |
| `analyze_existing` | `.smv`、topology、target、waveform option | 再実行せず既存結果を解析。metricが空なら`available_signals`を確認 |
| `optimize_circuit` | dynamic optimization request | sourceではなく分離copy上でsequential Optuna studyを実行 |

`set_parameter`と`sweep_parameter`は現在開いているファイルを変更します。sourceを保持する手動実験では、ユーザーがworking copyを準備する必要があります。`optimize_circuit`には以下のcopy・restore契約があります。

## 7. `optimize_circuit`の要求・実行・結果契約

projectに含まれる`$psim-circuit-optimization` skillを使うと、この契約に従って制限付きstudyを構成するようagentへ指示できます。

### 7.1 最上位request

| フィールド | 型 | 制約と意味 |
| --- | --- | --- |
| `source_project_path` | string | 既存`.psimsch`の絶対path。空は不可 |
| `variables` | array | 1–3個のunique decision variable |
| `measurements` | array | 1個以上。nameはunique |
| `objective` | array | 1個以上のmeasurement target term |
| `constraints` | array | 1個以上のhard constraint |
| `n_trials` | integer | 既定50、範囲1–50 |
| `time_budget_seconds` | integer | 既定300、範囲1–300。次のtrial開始可否を決め、実行中trialは中断しない |
| `seed` | integer | 既定0、範囲0–4,294,967,295 |

未知のfieldは拒否されます。nameはASCII英字で始まり、英数字とunderscoreのみを含み、最大64文字です。

### 7.2 Decision variableとbinding

| フィールド | 型 | 制約 |
| --- | --- | --- |
| `name` | string | unique variable name |
| `min` / `max` | number | 両方とも0より大きく`min < max` |
| `bindings` | array | 1個以上。component・parameter pairの重複は不可 |
| `log_scale` | boolean | 既定`true`。Optuna log samplingを制御 |

| `component_kind` | `parameter_name` | 追加規則 |
| --- | --- | --- |
| `L` | `Inductance` | 検証済みinductor binding |
| `C` | `Capacitance` | 検証済みcapacitor binding |
| `R` | `Resistance` | `role: "design"`が必須。load resistorは拒否 |

1つのvariableに複数bindingがある場合、同じ提案値をすべてに適用します。component IDとrangeは実際のprojectとengineering evidenceから確認してください。

### 7.3 Measurement、objective、constraint

| Measurementフィールド | 型 | 制約 |
| --- | --- | --- |
| `name` | string | unique measurement name |
| `signal` | string | 実際の`.smv` signal name、1–128文字 |
| `function` | enum | `mean`、`ripple_pp`、`ripple_percent`、`peak`、`rms` |
| `window.start_fraction` | number | `0 <= start < 1` |
| `window.end_fraction` | number | `0 < end <= 1`かつ`start < end` |
| `window.min_samples` | integer | 既定2、最小2 |

objectiveは正規化二乗誤差の合計です。

```text
cost = Σ weight × ((measurement - target) / normalization_scale)²
```

`weight`の既定値は1です。`scale`を省略すると`abs(target)`を使用します。targetが0の場合は正の`scale`を明示する必要があります。

hard constraintの`operator`は`<=`または`>=`で、`scale`は正でなければなりません。正規化residualが0以下のtrialだけがfeasibleです。

```text
operator <= : residual = (measurement - limit) / scale
operator >= : residual = (limit - measurement) / scale
```

### 7.4 Study lifecycle

1. source pathと`PSIM_OUTPUT_DIR`を検証します。
2. `optuna-*` study directoryと`study.jsonl`を作成します。
3. `source-copy.psimsch`と`working.psimsch`を作成し、SHA-256を比較します。
4. 直前のPSIM project pathを保持し、adapter session leaseを取得します。
5. working copyでbaselineを実行します。
6. seeded TPE samplerがtrial値を提案し、PSIMを順次実行します。
7. 有効なmeasurementとhard constraintを満たすtrialから最小costを選びます。
8. source copyから`best.psimsch`を作成して選択値を適用し、`best.smv`として再実行します。
9. 直前のprojectを再度開き、source SHA-256を再確認します。
10. trial・terminal recordをJSONL ledgerへ書き、結果を返します。

### 7.5 結果フィールドと状態

| フィールド | 意味 |
| --- | --- |
| `state` | `completed`、`time_budget_reached`、`no_feasible_trial`、`failed`、`cancelled`などのterminal state |
| `stop_reason` | `trials_exhausted`、`time_budget_reached`、validation/setup/restore失敗理由 |
| `trials_complete` / `trials_failed` | completed・failed trial count |
| `best_params` / `best_cost` / `best_metrics` | final rerunで検証した選択値と結果 |
| `constraint_residuals` | 0以下なら対応するhard constraintを満たす |
| `study_dir` / `ledger_path` | study directoryとJSONL evidence ledger |
| `best_project_path` | 選択値を持つfinal `best.psimsch` |
| `result_paths` | 存在するbaseline、trial、best `.smv` path |
| `source_hash_before` / `source_hash_after` | source不変を示すSHA-256 evidence |
| `restoration_status` | `restored`、`no_previous_project`、または失敗説明 |
| `elapsed_seconds` | setupからterminal記録までの経過時間 |
| `error` | 失敗説明。成功時は`null` |

signal不足、sample不足、non-finite value、不正binding、simulation失敗、feasible trial不在、source変更、session restore失敗は成功として報告されません。

## 8. JSON要求・応答例

次の値とsignal nameは、ある特定回路のrequest shapeを示す例です。他の回路に対するengineering recommendationではありません。

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

省略した成功応答例:

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

## 9. 安全規則と除外対象

- 信頼できる`.psimsch`と`.smv`だけを使用します。
- `ALLOWED_PROJECT_DIRS`でアクセス可能なproject pathを最小化します。
- sourceで`set_parameter`や`sweep_parameter`を実行しません。ユーザーが明示的に用意したworking copyを開きます。
- `optimize_circuit`には、実際のprojectで確認したcomponent ID、signal name、unit、range、target、hard limitだけを渡します。
- solver timestep、safety/protection limit、topology、load resistance、arbitrary gate scheduleは最適化しません。
- `window`はwaveformの一部を選択するだけです。独立した物理的settling evidenceがなければsteady stateと呼びません。
- `time_budget_seconds`は実行中のPSIM trialを強制終了しません。
- 成功報告にはfeasible best trial、final rerun artifact、restore成功、同一のbefore/after source hashが必要です。
- `mock`結果は実PSIM性能や安全性の根拠ではありません。

## 10. 開発と検証

```bash
uv sync --all-extras
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

実PSIMが必要な検証は、Windowsホストで`PSIM_MODE=real`と必須pathを設定して別途実行します。リポジトリではunit test、stdio integration test、opt-in real-PSIM markerを分離しています。

## ライセンス

MIT
