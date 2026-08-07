# PSIM-MCP Icon and Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the busy README hero with an approved minimal app icon, commit the completed Optuna MVP and multilingual documentation without unrelated local files, and merge the feature branch into `main`.

**Architecture:** The visual change is one generated square PNG consumed identically by four README files. Git integration is split into an optimization implementation commit and a documentation/image commit so each unit can be reviewed and reverted independently; local settings, unrelated skill bundles, circuit inputs, archives, and workspace metadata remain uncommitted.

**Tech Stack:** Built-in image generator, Markdown/HTML, Git, uv, pytest, Ruff.

## Global Constraints

- The icon is a square dark-navy rounded-square field with one centered flat circuit-node, sine-wave, and connection symbol.
- Use only electric blue and cyan accents; include no text, 3D, neon bloom, gradients, charts, schematics, logos, trademarks, or watermarks.
- Display the icon at 180 px in each README while retaining the native Markdown `# PSIM-MCP` heading.
- Preserve unrelated dirty files and do not push.
- Merge locally into `main` only after the full quality gate passes.

---

### Task 1: Generate and validate the icon asset

**Files:**
- Create: `assets/psim-mcp-icon.png`
- Preserve until validation: `assets/psim-mcp-hero.png`

**Interfaces:**
- Consumes: the approved visual constraints in `docs/superpowers/specs/2026-08-08-psim-mcp-icon-design.md`.
- Produces: one square PNG referenced by every README.

- [ ] **Step 1: Generate the square icon in built-in mode**

Use this prompt:

```text
Use case: logo-brand
Asset type: GitHub README project icon
Primary request: Create an original minimal app icon for PSIM-MCP that communicates power-electronics simulation connected through MCP.
Subject: One centered geometric symbol combining four circuit nodes, a clean sine waveform, and a simple connection motif.
Style/medium: Flat vector-style brand mark with a strong silhouette and precise uniform strokes.
Composition/framing: Square icon; dark navy rounded-square field; centered symbol; generous outer padding; balanced negative space; legible at 180 pixels.
Color palette: Dark navy background with electric blue and cyan accents only.
Constraints: No text or letters; no gradients; no 3D; no chrome; no photorealism; no glow or neon bloom; no charts; no dashboard; no circuit schematic; no decorative particles; no logo, trademark, or watermark; no tiny details.
```

- [ ] **Step 2: Copy the selected built-in output without overwriting another file**

Copy the selected generated image from the built-in generated-images directory to `assets/psim-mcp-icon.png`. Fail if the destination already exists.

- [ ] **Step 3: Inspect the project asset**

Run `file assets/psim-mcp-icon.png` and `sha256sum assets/psim-mcp-icon.png`, then open it at original detail. Confirm a square canvas, one centered flat icon, no readable text, and clean small-size silhouette.

### Task 2: Integrate the icon into every README

**Files:**
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `README.ja.md`
- Modify: `README.zh-CN.md`
- Remove after successful replacement: `assets/psim-mcp-hero.png`

**Interfaces:**
- Consumes: `assets/psim-mcp-icon.png` from Task 1.
- Produces: four language entry points with identical icon markup.

- [ ] **Step 1: Replace the hero Markdown in all four files**

Use this exact block directly below the language switcher:

```html
<p align="center">
  <img src="assets/psim-mcp-icon.png" alt="PSIM-MCP icon" width="180">
</p>
```

- [ ] **Step 2: Verify the replacement before removing the old asset**

Require one `assets/psim-mcp-icon.png` reference and zero `assets/psim-mcp-hero.png` references in each README. Require ten numbered level-two sections in every file.

- [ ] **Step 3: Remove the superseded hero**

After the reference checks pass, delete only `assets/psim-mcp-hero.png` and confirm `assets/psim-mcp-icon.png` is not ignored by Git.

### Task 3: Verify and commit the Optuna MVP

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/psim_mcp/adapters/base.py`
- Modify: `src/psim_mcp/adapters/mock_adapter.py`
- Modify: `src/psim_mcp/adapters/real_adapter.py`
- Modify: `src/psim_mcp/bridge/bridge_script.py`
- Modify: `src/psim_mcp/server.py`
- Create: `src/psim_mcp/models/optimization.py`
- Modify: `src/psim_mcp/services/optimization_service.py`
- Create: `src/psim_mcp/services/optimization_study.py`
- Modify: `src/psim_mcp/tools/analysis.py`
- Create: `tests/integration/test_optimize_stdio.py`
- Modify: `tests/unit/test_analysis_tools.py`
- Modify: `tests/unit/test_bridge_contract.py`
- Modify: `tests/unit/test_mock_adapter.py`
- Create: `tests/unit/test_optimization_models.py`
- Create: `tests/unit/test_optimization_service.py`
- Create: `tests/unit/test_optimization_setup.py`
- Modify: `tests/unit/test_real_adapter_resilience.py`

**Interfaces:**
- Consumes: the existing PSIM adapter, bridge, service, and MCP tool contracts.
- Produces: the public dynamic `optimize_circuit` tool with bounded L/C/design-R variables, hard constraints, copy/restore isolation, and auditable study artifacts.

- [ ] **Step 1: Run the complete quality gate**

Run:

```bash
uv run ruff check src/ tests/
uv run pytest -q
```

Expected: every command exits 0; pytest reports zero failures.

- [ ] **Step 2: Stage only the listed implementation and test paths**

Do not stage `.claude/`, `.agents/skills/` other than already committed work, `.codex-local-marketplaces/`, `.omo/`, `paper_data*`, `projects/`, or `skills-lock.json`.

- [ ] **Step 3: Inspect and commit the staged feature**

Require the staged diff to contain only the files listed in this task, then commit:

```bash
git commit -m "feat: add safe PSIM circuit optimization"
```

### Task 4: Verify and commit the multilingual documentation and icon

**Files:**
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `README.ja.md`
- Modify: `README.zh-CN.md`
- Create: `assets/psim-mcp-icon.png`
- Create: `docs/superpowers/plans/2026-08-08-psim-mcp-icon-and-merge.md`

**Interfaces:**
- Consumes: the public tool contract committed in Task 3.
- Produces: aligned technical documentation and the tracked minimal project icon.

- [ ] **Step 1: Run documentation checks**

Require ten numbered sections, twelve public tool names, one icon reference, balanced code fences, no DQN or Decision Transformer text, identical JSON/dotenv/bash blocks across all four README files, and clean `git diff --check` output.

- [ ] **Step 2: Stage only the four README files, icon, and this plan**

Force-add the ignored plan path; stage no other ignored or untracked content.

- [ ] **Step 3: Inspect and commit the staged documentation**

Require the staged diff to contain only the six listed paths, then commit:

```bash
git commit -m "docs: expand multilingual PSIM-MCP guide"
```

### Task 5: Merge locally into main and verify the merged tree

**Files:**
- Modify: Git history only.

**Interfaces:**
- Consumes: committed `refactor/simplify-leftovers` history.
- Produces: local `main` containing the feature and documentation commits.

- [ ] **Step 1: Confirm repository and branch safety**

Record the current branch, Git directory, common Git directory, worktree root, upstream status, `main...origin/main` counts, remaining dirty paths, and commits in `main..refactor/simplify-leftovers`.

- [ ] **Step 2: Switch to main and update without rewriting**

Run `git checkout main` followed by `git pull --ff-only`. If local unrelated changes block the checkout or pull, stop without stashing or resetting them.

- [ ] **Step 3: Merge the feature branch**

Run `git merge --no-ff refactor/simplify-leftovers`. Do not push.

- [ ] **Step 4: Re-run the complete quality gate on merged main**

Run:

```bash
uv run ruff check src/ tests/
uv run pytest -q
```

Expected: every command exits 0; pytest reports zero failures.

- [ ] **Step 5: Preserve unrelated work and remove the merged branch**

Confirm unrelated dirty paths are still present and unstaged, then delete the fully merged local feature branch with `git branch -d refactor/simplify-leftovers`.
