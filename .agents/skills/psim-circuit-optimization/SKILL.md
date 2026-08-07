---
name: psim-circuit-optimization
description: Use when optimizing component values or operating frequency in an existing PSIM power-electronics schematic with Optuna, especially for L/C/design-R selection, voltage targets, ripple or peak-current constraints, or distinguishing DQ-transform circuits from ML DQN or Decision Transformer work.
---

# PSIM Circuit Optimization

## Overview

Optimize an existing `.psimsch` only through the public PSIM MCP surface. Preserve the source and claim only results rerun and observed in real PSIM.

## Quick Reference

| Decision | Rule |
|---|---|
| Artifact | Treat `DQ_Transform.psimsch` as a circuit. Use ML tuning only when a training environment is supplied. |
| Variables | Follow the live request schema. Use verified L/C/design-R bindings; use operating frequency only when the schema supports it. |
| Excluded | Keep solver timestep, safety limits, topology, and arbitrary gate patterns fixed. Do not reintroduce them through an outer search. |
| Metrics | Minimize voltage-target error; enforce ripple and peak-current limits as hard constraints. |
| Evidence | Require real PSIM artifacts, final rerun metrics, source hashes, and restoration state. |

## Workflow

1. Use exactly `get_status`, `get_project_info`, `open_project`, `run_simulation`, `analyze_existing`, and `optimize_circuit` for this workflow. If they cannot supply required evidence, stop. Do not add `import_circuit` or `export_results`, even for structural detail or signal export.
2. Resolve the source path and record its SHA-256. Preserve the current PSIM session. Run the study on verified working copies with unique result paths; never open or mutate the source for a trial.
3. Bind only user-selected variables accepted by the current public request model. Require user-supplied or verified engineering bounds, targets, and limits; never invent percentage ranges or baseline ceilings. Reject unsupported frequency bindings instead of approximating them with gate edits. Never optimize timestep or gate schedules for a lower numerical error.
4. Run a real baseline. Define a voltage-error objective and at least one ripple or current constraint from confirmed signals. Use explicit measurement windows and sample counts. Call results `windowed`; use `steady-state` only after independent physical evidence proves settling.
5. Run bounded sequential Optuna trials. Fail closed on missing signals, invalid bindings, non-finite metrics, path mismatch, unavailable PSIM, or no feasible completed trial.
6. Open the returned best schematic in PSIM, rerun it, and analyze that new output. Reopen the prior project and verify the source hash again before reporting success.

## Result Contract

Report exact source, study, ledger, best-schematic, and result paths; sampled and final parameters; window definitions, sample counts, objective and constraint values; completed/failed trial counts; stop reason and elapsed time; best-rerun agreement; restoration status; and source hashes before and after.

If real PSIM execution is unavailable, report the blocker. Mock output or an attractive first metric is not result evidence.

## Common Mistakes

- Tuning gate timing or timestep outside `optimize_circuit` after correctly excluding them inside it.
- Labeling the final fraction of a short waveform as settled without proof.
- Reporting “optimized” without a feasible best rerun and unchanged source hash.
