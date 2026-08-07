---
name: psim-circuit-workflow
description: Use when working with an existing PSIM .psimsch power-electronics circuit through psim-mcp tools — reading its structure and nets, changing component parameters, running a time-domain simulation, sweeping a value, or explaining simulated waveforms. For Optuna-based component-value optimization, use psim-circuit-optimization instead.
---

# PSIM Circuit Workflow

## Overview

Operate on an existing `.psimsch` only through the public psim-mcp tools. PSIM fails silently more often than it errors: a wrong parameter name is a **silent no-op** (PSIM keeps the default without complaint), and mock mode returns synthetic data. Every claim about the circuit must trace to a tool response.

## Workflow

1. `get_status` — record the mode and open project before anything else. Mock output is synthetic: never present it as PSIM evidence. Real mode requires `PSIM_MODE=real` plus `PSIM_PATH`, `PSIM_PYTHON_EXE`, `PSIM_OUTPUT_DIR`.
2. `import_circuit(path)` — always the first look at a circuit: it restores components, electrical nets, and current parameter values. `open_project` only opens the file and recovers no structure. Done when every component you will touch is identified with its exact PSIM parameter name.
3. `set_parameter` — writes to the file immediately (no undo; back up first when the original matters). Because a wrong name is a silent no-op, verify every change: re-run `import_circuit` and confirm the value actually moved. High-frequency naming traps (PSIM 2026, verified in this repo — full table in the `guidelines://gotchas` resource):
   - Sources: `Amplitude`, not `V1`; AC frequency is `Freq`, not `Frequency`
   - Transformers: `Np__primary_` / `Ns__secondary_` / `Lm__magnetizing_` — `Ratio` and `Lm` are ignored
   - IGBT on-resistance is `R_transistor` (MOSFET uses `On_Resistance`); simulation time lives on the SimControl element as `TotalTime` / `TimeStep`
   - Native `MULTI_*` elements need `PORTS` as a Python list and `SubType="Ideal"`
4. `run_simulation` — run only when the user asks, with `simview=false` (Simview takes tens of seconds to open on Windows). Size `TotalTime` to reach settling (buck-class converters settle near 50 ms, not 1 ms) and `TimeStep` fine enough to resolve the switching frequency. If the all-in-one `analyze_simulation` times out, split it: `run_simulation(simview=false)` then `analyze_existing`.
5. `analyze_existing` — describe waveforms only from the returned `signal_samples`; scalar metrics (average, ripple, final value) cannot reconstruct a waveform shape. Report ripple and peak values as windowed unless settling is independently proven.
6. Sweeps and comparison — one-dimensional scan: `sweep_parameter` (bounded step count, early-stops after 3 consecutive failures). Judgment-driven tuning: loop `set_parameter → run_simulation → analyze_existing` one step at a time. Before/after evidence: `compare_results`.
7. Hand-offs — a new circuit starts from a verified template (`guidelines://templates` resource), never from scratch. Component-value or frequency optimization moves to the psim-circuit-optimization skill.
