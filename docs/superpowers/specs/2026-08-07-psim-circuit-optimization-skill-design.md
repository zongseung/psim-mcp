# PSIM circuit optimization skill design

## Goal

Create one repository-owned skill named `psim-circuit-optimization` that guides agents through safe, real-PSIM Optuna experiments on existing power-electronics schematics. The skill must distinguish a DQ-transform circuit from machine-learning DQN/Decision Transformer work, preserve the source schematic, and verify results through PSIM rather than describing an unexecuted plan.

## Placement and distribution

The tracked source lives at:

```text
.agents/skills/psim-circuit-optimization/
├── SKILL.md
└── agents/openai.yaml
```

This repository path makes the skill available to users who clone the project in runtimes that discover project `.agents/skills`. After validation, install the same two files at `~/.agents/skills/psim-circuit-optimization/` for cross-runtime use by the current OS user. The repository copy remains the single source of truth; installation must produce matching hashes. Do not edit or depend on the separate Ponytail marketplace plugin.

External marketplace or package publication is outside this change. That requires a separate release decision and credentials.

## Skill contract

Use only Codex-compatible frontmatter fields. The description starts with `Use when`, contains trigger conditions rather than workflow, and stays below 500 characters. Keep the complete `SKILL.md` below 500 words because it is a frequently useful project skill.

The body must make these decisions predictable:

1. Identify the requested artifact. Treat `DQ_Transform.psimsch` as a circuit unless the user explicitly supplies an ML training environment; do not route it to DQN/Decision Transformer tuning.
2. Inspect the existing schematic, public optimization request model, and current tool behavior before constructing a request. Use real component `name` values and normalized response envelopes.
3. Accept user-selected design variables dynamically, but restrict the first public surface to verified L/C/design-R bindings and supported operating frequency. Never optimize solver timestep, safety limits, topology, or arbitrary gate patterns.
4. Work from a verified copy, keep the source hash unchanged, use unique study/trial result paths, and restore the prior PSIM session state.
5. Express target-voltage error as the objective and ripple or peak-current limits as hard constraints. Treat windowed measurements as windowed; do not claim steady state without physical evidence.
6. Run the actual public PSIM optimization surface with a small bounded trial budget before claiming success. Open the best schematic in PSIM, rerun it, and report exact artifacts, parameters, metrics, stop reason, restoration status, and source-hash evidence.
7. Fail closed on missing signals, non-finite values, invalid bindings, result-path mismatches, unavailable PSIM, or no feasible completed trial.

Use the repository's existing test framework. Add an ad-hoc self-check only when no relevant harness exists.

## TDD evaluation

Before creating the skill, run a fresh-context baseline without its instructions. The pressure scenario combines a short deadline, an already-open original schematic, and a request to optimize arbitrary values quickly. A baseline fails when it mutates the original, treats circuit DQ as ML DQN, optimizes excluded controls, omits real PSIM execution, or reports success without artifact evidence.

Run at least five no-guidance repetitions and read every response. If none exhibits a target failure, remove guidance for that behavior instead of adding no-op rules.

After writing the minimal skill, run the same scenario at least five times with the skill. Every treatment response must preserve the source, separate circuit and ML work, constrain variables, require real PSIM execution, and produce an evidence-oriented result shape. Add wording only for observed loopholes, then rerun affected cases.

## Validation and manual QA

The completion gates are:

- `quick_validate.py` accepts the repository skill.
- `agents/openai.yaml` matches the final skill metadata.
- `SKILL.md` contains fewer than 500 words and no unsupported frontmatter.
- Repository and global installed copies have identical hashes.
- Fresh-session treatment tests pass and no debug/test artifacts remain.
- One bounded optimization runs through the public PSIM surface on a disposable schematic copy; the best artifact opens successfully and the original hash is unchanged.

## Non-goals

- DQN or Decision Transformer hyperparameter tuning.
- Background job/status APIs, parallel or distributed trials, Pareto optimization, or durable resume storage.
- Automatic classification of every arbitrary resistor as a safe design variable.
- External marketplace, NPM, or plugin release.
