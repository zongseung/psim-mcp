# Knowledge Resources Corrections Design

## Goal

Make the four `guidelines://` resources executable and truthful in a clean
checkout. Fix the active C-Block parameter path instead of documenting a broken
1,024-character ceiling.

## Runtime design

`ParameterService` remains the owner of parameter validation and mutation.
`tools/parameter.py` will receive both the parameter and simulation services:

- `set_parameter` delegates to `ParameterService`;
- `sweep_parameter` uses `ParameterService` for mutation and
  `SimulationService` for simulation;
- the legacy `SimulationService.set_parameter` entry point remains for backward
  compatibility and follows the same validation rules.

String parameters keep the existing 1,024-character limit. `CONTENT` alone may
contain up to 65,536 characters and must not contain NUL. The bridge confirms
that `CONTENT` targets only `CBLOCK` or `SIMPLECBLOCK`, because the bridge has the
authoritative PSIM component type.

No C parser, source rewriting layer, or automatic read-back is added. PSIM stays
the compiler and the existing `import_circuit` reread remains the verification
mechanism.

## Knowledge corrections

- Every edit workflow becomes `import_circuit` -> understand -> `open_project`
  -> `set_parameter` -> `run_simulation` -> `analyze_existing`.
- C-Block inspection uses `import_circuit(..., include_graph=true)` so `CONTENT`
  is not the 300-character summary.
- The `SubType="Ideal"` rule is limited to ideal switching elements; verified
  passive examples use `SubType="Level 1"`.
- The SimControl table distinguishes raw PSIM names (`TotalTime`/`TimeStep`) from
  MCP aliases (`TOTALTIME`/`TIMESTEP`), which the bridge accepts.
- `projects/interleaving_demo.psimsch` and `projects/verify_dq.psimsch` are added
  to version control so all seven catalog entries exist in a clean checkout.

Template paths remain repository-relative. Packaging the schematics inside the
Python wheel is out of scope because the server currently runs from a repository
checkout and no installed-package template-copy API exists.

## Verification

Add the smallest regression coverage that proves:

1. the registered `set_parameter` tool uses `ParameterService`;
2. `CONTENT` accepts 65,536 characters, rejects 65,537 characters and NUL, while
   ordinary string parameters retain the 1,024-character limit;
3. the bridge rejects `CONTENT` for non-C-Block components;
4. every path listed by `guidelines://templates` exists in a clean checkout;
5. all four resources still register and read successfully.

Run the full unit suite and Ruff after the focused tests.

## Non-goals

- No `.claude/skills` wrapper or automatic resource injection.
- No new circuit-generation API.
- No refactor beyond separating parameter mutation from sweep simulation at the
  existing registration seam.
