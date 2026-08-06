# Real Mode and Multilingual READMEs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the verified local PSIM 2026 installation in real mode and publish accurate Korean, English, Japanese, and Simplified Chinese documentation for the 12-tool existing-circuit workflow.

**Architecture:** Machine-specific paths live only in an ignored repository-root `.env`; tracked documentation uses portable examples. `README.md` is the Korean source of truth, and three translations mirror its structure and capability limits. The main worktree is synchronized only after proving remote changes do not overlap the user's existing dirty files.

**Tech Stack:** PowerShell, Python 3.12 MCP server, Python 3.9 PSIM bridge, Altair PSIM 2026, Pydantic Settings, Markdown, Git.

## Global Constraints

- Use `C:\Altair\Altair_PSIM_2026` and `C:\Users\new92\AppData\Local\Programs\Python\Python39\python.exe` only in the ignored local `.env`; tracked examples must explain that installation paths vary.
- Leave `ALLOWED_PROJECT_DIRS` unset so users may open any validator-accepted absolute `.psimsch` path.
- Keep `README.md` Korean and create `README.en.md`, `README.ja.md`, and `README.zh-CN.md` with the same section order and language selector.
- Document exactly the merged 12 tools. Do not restore `design_circuit`, `continue_design`, `preview_circuit`, `confirm_circuit`, `create_circuit`, `get_component_library`, or `list_circuit_templates`.
- Mark `compare_results` as a P1 stub, `sweep_parameter` as experimental, and `optimize_circuit` as experimental and unavailable without non-default Optuna.
- Warn in all four READMEs that `set_parameter` persists to the open project and users should work on a copy.
- Preserve all pre-existing user changes and untracked files in the main worktree.

---

### Task 1: Synchronize main and enable local real mode

**Files:**
- Create, ignored: `.env`
- Create, ignored: `output/`
- Preserve: `.claude/settings.local.json`, `src/psim_mcp/tools/__pycache__/project.cpython-312.pyc`, `.agents/`, `.codex-local-marketplaces/`, `paper_data.zip`, `paper_data/`, `projects/`, `skills-lock.json`

**Interfaces:**
- Consumes: `AppConfig.validate_real_mode()`, `RealPsimAdapter.get_status()`, `ProjectService.import_circuit(path, include_graph=False)`
- Produces: a valid local real-mode configuration and read-only PSIM bridge evidence

- [ ] **Step 1: Fetch and prove the remote merge does not overlap dirty tracked files**

Run:

```powershell
git fetch origin
git diff --name-only HEAD..origin/main
git status --short
```

Compare the remote-change list with the two dirty tracked files. Stop before merging if any path overlaps.

- [ ] **Step 2: Merge the already-reviewed remote main into local main**

Run:

```powershell
git merge --no-edit origin/main
git status --short --branch
```

Expected: merge succeeds and the pre-existing dirty files remain present but unstaged.

- [ ] **Step 3: Create the ignored real-mode configuration and output directory**

Write `.env` exactly as:

```env
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\new92\AppData\Local\Programs\Python\Python39\python.exe
PSIM_PROJECT_DIR=C:\Users\new92\psim-mcp\projects
PSIM_OUTPUT_DIR=C:\Users\new92\psim-mcp\output
LOG_DIR=./logs
LOG_LEVEL=INFO
SERVER_TRANSPORT=stdio
SIMULATION_TIMEOUT=300
MAX_SWEEP_STEPS=100
```

Create `C:\Users\new92\psim-mcp\output` only if it does not exist. Do not set `ALLOWED_PROJECT_DIRS`.

- [ ] **Step 4: Validate configuration without exposing local paths in Git**

Run:

```powershell
uv run python -c "from psim_mcp.config import AppConfig; c=AppConfig(); c.validate_real_mode(); print(c.psim_mode); print(c.psim_path.is_dir()); print(c.psim_python_exe.is_file())"
git check-ignore -v .env output
```

Expected: `real`, `True`, `True`; `.env` and `output` are ignored.

- [ ] **Step 5: Verify the real bridge and a read-only schematic import**

Use `RealPsimAdapter` to call `get_status`, then use `ProjectService.import_circuit` on `C:\Altair\Altair_PSIM_2026\Python\Samples\PythonTest\buck.psimsch`. Always call `adapter.shutdown()` in `finally`.

Expected: real PSIM reports a valid 2026 version and import returns `success=true` with at least one component. Do not call `open_project`, `set_parameter`, or `run_simulation` in this task.

### Task 2: Establish the Korean canonical documentation

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: the 12 registered tool names and verified real-mode paths from Task 1
- Produces: the portable configuration example and translation source structure

- [ ] **Step 1: Update `.env.example`**

Set `PSIM_MODE=real` in the real-mode example, show `C:\Altair\Altair_PSIM_2026` and a generic `<사용자>` Python 3.9 path, retain `./projects` and `./output`, and state that an omitted `ALLOWED_PROJECT_DIRS` permits any validator-accepted absolute project path.

- [ ] **Step 2: Rewrite `README.md` against the merged product surface**

Add this selector immediately below the title:

```markdown
[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)
```

Use this section order: product scope, existing-circuit workflow, capabilities and limits, requirements, installation, real-mode quickstart, Claude Desktop configuration, 12-tool reference, environment variables, safety, development, license. Keep all code identifiers in English.

- [ ] **Step 3: Check the canonical README contract**

Run searches that prove all 12 names are present and all seven removed generation names are absent. Check the language selector, real-mode setup, unrestricted-path explanation, original-file warning, and maturity warnings.

Expected tool names:

```text
open_project get_project_info import_circuit set_parameter sweep_parameter
run_simulation export_results compare_results get_status
analyze_simulation analyze_existing optimize_circuit
```

### Task 3: Create the three translations with parallel subagents

**Files:**
- Create: `README.en.md`
- Create: `README.ja.md`
- Create: `README.zh-CN.md`

**Interfaces:**
- Consumes: the reviewed `README.md` from Task 2
- Produces: three natural-language translations with identical technical contracts

- [ ] **Step 1: Dispatch one agent per language**

Give each agent exclusive ownership of one file. Agents may read `README.md` but must not modify it, stage files, or commit. Require UTF-8, the common selector, identical headings/order, exact code blocks, exact tool/environment names, and localized prose.

- [ ] **Step 2: Review each translation against the Korean source**

Check that no translation invents capabilities, reintroduces generation, changes paths or commands, omits the mutation warning, or promotes experimental tools.

- [ ] **Step 3: Run mechanical parity checks**

For each README, assert all 12 current tool names exist, all seven removed tool names are absent, and all four language links exist. Run `git diff --check` on the four READMEs and `.env.example`.

### Task 4: Verify, commit, and push main

**Files:**
- Commit: `.env.example`, `README.md`, `README.en.md`, `README.ja.md`, `README.zh-CN.md`
- Do not commit: `.env`, `output/`, or any pre-existing user changes

**Interfaces:**
- Consumes: Tasks 1-3
- Produces: verified documentation on `main` and a working local real-mode setup

- [ ] **Step 1: Run full automated verification**

Run:

```powershell
uv run pytest -q
uv run ruff check src tests
```

Expected: the complete suite passes and Ruff reports no errors in product/test code.

- [ ] **Step 2: Re-run the real-mode status/import smoke check**

Expected: the same PSIM version and successful read-only import as Task 1.

- [ ] **Step 3: Stage only intended tracked files**

Run:

```powershell
git add -- .env.example README.md README.en.md README.ja.md README.zh-CN.md
git diff --cached --name-status
git check-ignore -v .env output
```

Expected: exactly five tracked documentation files are staged; local operational files remain ignored.

- [ ] **Step 4: Commit and push main**

Run:

```powershell
git commit -m "docs: enable real mode and add multilingual readmes"
git push origin main
```

- [ ] **Step 5: Verify remote and local state**

Run:

```powershell
git status --short --branch
git log -3 --oneline --decorate
```

Expected: `main` tracks `origin/main` with no ahead/behind count. Pre-existing user changes remain untouched and visible.
