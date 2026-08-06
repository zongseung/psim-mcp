# psim-mcp

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

## 製品の範囲

Claude Desktopから既存のPSIM回路を開き、構成と結果を解析し、必要なパラメーターを変更してシミュレーションを実行できるMCPサーバーです。新しい回路を作成するツールは提供しません。

`real`は実際の製品利用向けモードで、`mock`はPSIMを利用できない場合の開発・テスト専用の補助モードです。

## 既存回路のワークフロー

1. `open_project`で既存の`.psimsch`ファイルを開きます。
2. `get_project_info`または`import_circuit`で回路構成を確認します。
3. 必要に応じて`set_parameter`または`sweep_parameter`を使用します。
4. `run_simulation`を実行し、`analyze_simulation`、`analyze_existing`、`export_results`で結果を確認します。

`set_parameter`は元のプロジェクトファイルに変更を保存します。作業を始める前に元のファイルをコピーしてください。

## 機能と制限

12個のツールのうち、安定して利用できるのは`open_project`、`get_project_info`、`import_circuit`、`run_simulation`、`export_results`、`get_status`、`analyze_simulation`、`analyze_existing`です。

`sweep_parameter`は固定ループ方式の実験的機能です。`compare_results`はP1スタブで、`optimize_circuit`も実験的機能です。最適化に必要なOptunaはデフォルトのインストールには含まれません。

## 要件

| 項目 | 必須 | 備考 |
| --- | --- | --- |
| Python 3.12+ | はい | MCPサーバー |
| [uv](https://docs.astral.sh/uv/) | はい | パッケージ管理 |
| Claude Desktop | 任意 | MCPクライアント |
| Altair PSIM 2026 | realモードでは必須 | 実際のシミュレーション |
| PSIM Python 3.9 | realモードでは必須 | PSIMブリッジ |

## インストール

```bash
git clone https://github.com/zongseung/psim-mcp.git
cd psim-mcp
uv sync --all-extras
```

## realモードのクイックスタート

`.env.example`を`.env`にコピーし、インストール先のパスを設定します。`.env`はGitで無視されるため、リポジトリに追加しないでください。

```dotenv
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\<사용자>\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=./output
```

`ALLOWED_PROJECT_DIRS`を省略すると、validatorが許可する任意の絶対プロジェクトパスを使用できます。アクセスを制限するには、絶対パスをカンマ区切りで設定してください。

## Claude Desktopの設定

`claude_desktop_config.json`に次の内容を追加します。

ローカルのrealモードには、PSIMがインストールされたWindowsホストが必要です。以下のJSONにあるすべてのplaceholderパスを、実際のローカルパスに置き換えてください。

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS（mockまたはリモート利用）: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

設定を変更したら、Claude Desktopを完全に終了してから再起動してください。

## 12個のツール一覧

| ツール | 説明 |
| --- | --- |
| `open_project` | 既存のプロジェクトを開く |
| `get_project_info` | プロジェクト構成を表示する |
| `import_circuit` | 既存の回路をインポートする |
| `set_parameter` | コンポーネントのパラメーターを変更し、元のファイルに保存する |
| `sweep_parameter` | パラメータースイープ（実験的な固定ループ） |
| `run_simulation` | シミュレーションを実行する |
| `export_results` | 結果をJSONまたはCSVとしてエクスポートする |
| `compare_results` | 結果を比較する（P1スタブ） |
| `get_status` | サーバーとPSIMの状態を確認する |
| `analyze_simulation` | シミュレーションを実行して結果を解析する |
| `analyze_existing` | 既存の`.smv`結果を解析する |
| `optimize_circuit` | 回路パラメーターを最適化する（実験的、Optunaは別途インストールが必要） |

## 環境変数

| 変数 | デフォルト | 説明 |
| --- | --- | --- |
| `PSIM_MODE` | `mock` | `mock`または`real` |
| `PSIM_PATH` | なし | realモードのPSIMインストールパス |
| `PSIM_PYTHON_EXE` | なし | PSIM Python 3.9の実行ファイル |
| `PSIM_OUTPUT_DIR` | なし | realモードで必要なシミュレーション結果ディレクトリ |
| `LOG_DIR` | `<저장소>/logs` | ログディレクトリ |
| `LOG_LEVEL` | `INFO` | ログレベル |
| `SERVER_TRANSPORT` | `stdio` | `stdio`または`sse` |
| `SERVER_HOST` | `127.0.0.1` | SSEサーバーのホスト |
| `SERVER_PORT` | `8000` | SSEサーバーのポート |
| `SIMULATION_TIMEOUT` | `300` | シミュレーションのタイムアウト（秒） |
| `MAX_SWEEP_STEPS` | `100` | スイープの最大ステップ数 |
| `ALLOWED_PROJECT_DIRS` | 省略 | 許可する絶対プロジェクトパスの一覧。省略時はvalidatorが許可するすべてのパスを使用可能 |

## 安全上の注意

- 信頼できるプロジェクトファイルだけを開いてください。
- `set_parameter`は元のファイルを変更するため、コピーを作成してから作業してください。
- `ALLOWED_PROJECT_DIRS`でプロジェクトパスの範囲を制限できます。

## 開発

```bash
uv run pytest tests/unit -q
uv run ruff check src/ tests/
uv run mcp dev src/psim_mcp/server.py
```

## ライセンス

MIT
