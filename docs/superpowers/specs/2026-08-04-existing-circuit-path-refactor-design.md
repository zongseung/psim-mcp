# Existing Circuit Path Refactor Design

**Date:** 2026-08-04
**Status:** Approved for implementation planning
**Related design:** `2026-08-04-existing-circuit-editing-multiclient-design.md`

## Goal

Make the existing-circuit workflow run through the domain services that already
exist, without rewriting the server or breaking legacy callers. The refactor
must create one production path for:

```text
MCP tool -> domain service -> adapter -> PSIM bridge
```

The work is limited to the path needed for importing a schematic, preparing a
working copy, changing component values or C-block source, and verifying the
saved result.

## Verified Current State

### Production call path

| Location | Current behavior | Consequence |
|---|---|---|
| `server.py:55` | Builds a dedicated `ParameterService`. | The intended service exists. |
| `server.py:72` | Stores `SimulationService` as `_legacy`. | Legacy callers retain a combined facade. |
| `server.py:93` | Registers parameter tools with `_legacy`. | Desktop MCP calls bypass `ParameterService`. |
| `tools/parameter.py:31` | `set_parameter` calls the injected service. | It currently reaches `SimulationService.set_parameter`. |
| `tools/parameter.py:44` | `sweep_parameter` needs both parameter mutation and simulation. | One injected god service was used to satisfy both operations. |
| `parameter_service.py:47` | Contains the dedicated parameter implementation. | Changes here alone do not affect real MCP clients. |
| `simulation_service.py:230` | Duplicates `set_parameter`. | Validation can drift between two copies. |
| `bridge_script.py:585` | Resolves component type, calls `PsimSetElmValue2`, then saves. | This is the correct single PSIM mutation boundary to retain. |

The immediate defect is wiring, not a missing abstraction: production creates
the correct service and then does not use it.

### Contract drift found during tracing

1. `ParameterServiceProtocol` declares `sweep_parameter`, but
   `ParameterService` does not implement it and the protocol has no production
   consumer.
2. `SimulationService` still contains project delegates, duplicated parameter
   validation, circuit creation, and legacy helpers despite the domain-service
   extraction.
3. `MockPsimAdapter` generally returns domain data, while `RealPsimAdapter`
   generally returns the bridge `{success, data}` envelope. Services therefore
   produce nested envelopes in real mode. Some acceptance tests explicitly
   unwrap both shapes.
4. `truncate_response()` cuts a serialized JSON string at a byte limit and
   appends text. An oversized tool result is therefore invalid JSON.
5. `encode_response()` sanitizes the complete serialized payload. Exact source
   code must not be silently modified when `include_source_code=True`.

Items 3 and the general sanitization policy affect every MCP tool. They are not
required to correct service ownership and should not be mixed into the first
refactor commit. The existing-circuit implementation still needs a focused,
valid response-size rule for full source retrieval.

## Existing Test Baseline

The circuit-related focused suite currently passes: **35 passed**.

The broader unit and integration suite, excluding one collection blocker,
reports **1339 passed, 2 failed**. These failures predate this design and are
outside the existing-circuit path:

- `test_hybrid_resolver_golden.py` imports
  `build_legacy_resolution_dict`, which was added to the test but never added to
  `intent/resolver.py`; the only similar implementation is the private
  `SamplingResolver._build_legacy_dict`.
- `test_elicitation.py` calls
  `CircuitDesignService._maybe_elicit_missing_fields`, which was added to the
  test but never implemented or called by production code.
- `test_svg_renderer.py` patches all `subprocess.Popen` calls and on the first
  Windows run also counts the subprocess used internally by
  `platform.system()`, producing two mock calls although only one viewer opener
  is requested.

These are recorded as baseline defects. They must not be reported as
regressions from the circuit refactor, and fixing them is a separate change.

## Options Considered

### A. Correct the production route, preserve the facade temporarily

Change the parameter tool registration to receive a parameter service and a
simulation service. `set_parameter` uses the former; the existing sweep loop
uses the former for mutation and the latter for simulation. Keep
`app._psim_service` and legacy delegates until their callers are migrated.

**Advantages:** smallest root-cause fix, no new service, preserves compatibility,
and makes C-block validation land on the real desktop-client path.

**Cost:** duplicate legacy methods remain temporarily.

### B. Normalize all service and adapter contracts now

Make every adapter return domain data, migrate all services and tests, remove
the legacy facade, and make every tool depend only on protocols.

**Advantages:** clean final architecture in one pass.

**Cost:** broad behavioral change across project, simulation, results,
analysis, and circuit-generation paths. It is too risky for the requested
existing-circuit workflow.

### C. Add the feature only to `SimulationService`

Keep the current registration and extend the duplicate implementation.

**Advantage:** smallest initial diff.

**Cost:** preserves the known wiring defect and guarantees further drift.

## Decision

Use **Option A**. It fixes the actual production route with the fewest moving
parts. Option B becomes a separate project only if nested response envelopes
cause a demonstrated client problem. Option C is rejected.

## Target Design

### Parameter tool ownership

Keep the sweep algorithm in `tools/parameter.py`; it is orchestration, not a
new domain object. Change only its dependencies:

```python
register_tools(mcp, parameter_service=None, simulation_service=None)
```

- `set_parameter` calls `parameter_service.set_parameter`.
- `sweep_parameter` calls `parameter_service.set_parameter`, then
  `simulation_service.run_simulation`.
- If services are omitted, both fall back to `mcp._psim_service` for existing
  direct-registration tests and legacy imports.
- `server.register_all_tools()` passes `services["parameter"]` and
  `services["simulation"]` explicitly.

No `SweepService`, dependency container, registry, or new protocol is added.

### Existing-circuit feature placement

| Behavior | Owner | Reason |
|---|---|---|
| Read and reconstruct `.psimsch` | `ProjectService.import_circuit` | Already owns path validation and conversion/import flow. |
| Create and open safe copy | `ProjectService.prepare_edit` | It is a project lifecycle and path-safety operation. |
| Validate parameter/C-block input | `ParameterService.set_parameter` | It is the active parameter trust boundary after wiring is fixed. |
| Confirm `CONTENT` component type | `bridge_script.handle_set_parameter` | The bridge already resolves the real PSIM element type. |
| Persist parameter | Existing `PsimSetElmValue2` + `PsimFileSave` | Reuse the working PSIM mutation path. |
| Verify saved value/source | Re-run `ProjectService.import_circuit` | Avoid a second parser or cached-state assumption. |

### C-block validation split

`ParameterService` performs validation that does not require PSIM state:

- standard strings: current 1,024-character maximum;
- `CONTENT`: 65,536-character maximum;
- reject NUL characters;
- do not echo the complete source in the success message.

The bridge performs the type-dependent rule after resolving the component:

- allow `CONTENT` only for `CBLOCK` and `SIMPLECBLOCK`;
- otherwise return `UNSUPPORTED_PARAMETER` before calling PSIM.

This avoids an extra component lookup API and keeps hardware-specific knowledge
at the existing hardware boundary.

### Response integrity

Full C-block retrieval must still be valid JSON. The implementation plan should
make the smallest focused correction:

1. stop cutting serialized JSON mid-document;
2. return a valid `RESPONSE_TOO_LARGE` envelope on overflow;
3. set the response ceiling high enough for one maximum-size C-block plus JSON
   overhead; and
4. add one exact-source regression test covering content that the current
   global sanitizer would alter.

If exact source cannot safely pass through the existing global sanitizer, the
implementation must bypass it only for the explicitly requested source field,
not redesign sanitization for every tool.

## Refactor Sequence

### Phase 0 — Characterize the route

Add tests that fail under the current wiring:

1. registered `set_parameter` reaches the dedicated `ParameterService`;
2. registered `sweep_parameter` uses the parameter service for writes and the
   simulation service for runs;
3. omitted injected services retain the legacy fallback.

### Phase 1 — Correct production wiring

Update only `tools/parameter.py` and `server.py`. Do not delete the legacy
facade yet. Run the route tests and the existing app/tool integration tests.

### Phase 2 — Implement the approved existing-circuit design

Add `include_source_code`, `prepare_edit`, C-block validation, bridge type
checking, and valid response overflow handling. Use the existing validators,
`hashlib`, `shutil.copy2`, importer, and bridge save path.

### Phase 3 — Verify the actual workflow

Use copies of the two supplied originals:

1. import original without mutation;
2. prepare a working copy;
3. change DQ `SCB1.CONTENT` and verify exact persisted source;
4. change Interleaving Boost component values and verify persistence;
5. confirm original SHA-256 values remain unchanged;
6. smoke-test the shared MCP route from Codex, ChatGPT Desktop, and Claude
   Desktop configuration examples.

### Phase 4 — Remove legacy duplication separately

Only after callers and tests stop depending on `app._psim_service`:

- delete `SimulationService.set_parameter`;
- migrate or delete legacy project delegates and creation helpers by actual
  usage;
- delete the unused `ParameterServiceProtocol` instead of adding methods solely
  to satisfy it;
- remove `create_service()` and `_legacy` only when no supported caller remains.

This phase is intentionally not a prerequisite for the user-visible feature.

## Verification Gates

- Route characterization tests pass.
- Existing circuit-focused tests remain green.
- Each new validation branch has one direct test.
- Every tool response is parseable with `json.loads`.
- Real-PSIM acceptance verifies persisted values/source and unchanged originals.
- The three recorded baseline defects are either still identical or fixed in
  separately reviewed commits.

## Files Expected in the First Implementation

The initial route correction should touch only:

- `src/psim_mcp/server.py`
- `src/psim_mcp/tools/parameter.py`
- one focused tool-registration test file

The existing-circuit feature then touches only the owners listed above and
their focused tests. General adapter normalization, new dependency injection
frameworks, and arbitrary schematic-generation refactors are excluded.

## Completion Criteria

- Production MCP `set_parameter` uses `ParameterService`.
- Sweep behavior still uses the same algorithm and limits.
- The existing-circuit workflow has a single explicit write boundary.
- C-block validation executes on the real client path.
- Oversized responses remain valid JSON.
- Legacy removal is tracked as a separate, deletion-focused phase rather than
  mixed into the feature diff.
