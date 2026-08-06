# Real Mode and Multilingual README Design

## Goal

Run PSIM-MCP against the installed PSIM 2026 instance and document the supported existing-circuit workflow in Korean, English, Japanese, and Simplified Chinese.

## Scope

### Local real-mode configuration

Create an ignored repository-root `.env` with:

```env
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2026
PSIM_PYTHON_EXE=C:\Users\new92\AppData\Local\Programs\Python\Python39\python.exe
PSIM_OUTPUT_DIR=C:\Users\new92\psim-mcp\output
```

Do not set `ALLOWED_PROJECT_DIRS`. Users may open an existing `.psimsch` from any absolute path accepted by the existing path validator. Simulation and export artifacts default to `PSIM_OUTPUT_DIR`, while tools that accept an explicit output directory remain configurable per call.

The `.env` file remains untracked because it contains machine-specific paths. Create the output directory if it does not exist; preserve the existing project directory and all user files.

### Tracked configuration documentation

Update `.env.example` to show the verified Altair PSIM 2026 installation layout and Python 3.9 interpreter while retaining generic placeholders where a path is machine-specific. Explain that omitting `ALLOWED_PROJECT_DIRS` allows unrestricted absolute project paths.

### README set

- `README.md`: Korean source README and language selector.
- `README.en.md`: English translation.
- `README.ja.md`: Japanese translation.
- `README.zh-CN.md`: Simplified Chinese translation.

Each README describes only the merged 12-tool existing-circuit product surface. It must not restore removed circuit-generation claims. Keep tool names, environment-variable names, paths, file extensions, and code identifiers untranslated. Each file links to all four languages at the top.

Use the same language selector in every file:

```markdown
[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)
```

Keep a common section order: product scope, existing-circuit workflow, capabilities and limits, requirements, installation, real-mode quickstart, Claude Desktop configuration, 12-tool reference, environment variables, safety, development, and license. Describe `real` as the product path and `mock` as a development/test aid.

The tool reference must distinguish maturity. `compare_results` is a P1 stub, `sweep_parameter` is a fixed-range experimental loop, and `optimize_circuit` is experimental and unavailable without the non-default Optuna package. Do not present these three tools as production-ready.

The translations cover the same sections and facts, but natural phrasing is preferred over sentence-for-sentence literal translation. The Korean README is the source of truth for future behavior changes.

## Runtime flow

1. `AppConfig` loads the repository-root `.env` and validates all real-mode fields.
2. `RealPsimAdapter` starts the bridge with Python 3.9.
3. The bridge imports the installed `psimapipy` package and instantiates PSIM from `PSIM_PATH`.
4. A status call confirms `PSIM 2026.0.0.7209` and bridge health.
5. A read-only import of an existing local `.psimsch` confirms the real bridge without changing the schematic.

## Safety and errors

- Do not modify or commit unrelated dirty files in the main worktree.
- Do not run `set_parameter` or a simulation during the initial mode switch; those can mutate a project or consume a PSIM license for longer work.
- If startup validation, bridge startup, status, or read-only import fails, keep the diagnostic output and do not claim real mode is operational.
- Documentation must warn that `set_parameter` persists changes to the currently open project and recommend working on a copy.

## Verification

- Load `AppConfig` from `.env`; assert `psim_mode == "real"` and all required paths resolve.
- Start the real adapter and call status/version.
- Run `import_circuit` against one existing local `.psimsch` without opening it for mutation.
- Run the full automated test suite in its isolated test configuration.
- Run Ruff against `src` and `tests`. The repository-wide `ruff check .` baseline issue under `.claire` is outside this change.
- Check that every README contains the same 12 tool names and no removed public generation tools.
- Confirm `git status` stages only the design/configuration documentation and multilingual README files; `.env` stays ignored.

## Git integration

Commit the reviewed tracked files to `main` without staging pre-existing user changes. The local `.env` and generated output directory are operational state and are not committed.

## Non-goals

- Improving `sweep_parameter` or `optimize_circuit`.
- Adding C-block source replacement.
- Running a destructive or mutating real-PSIM scenario.
- Reintroducing arbitrary circuit generation.
