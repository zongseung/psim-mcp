# Existing PSIM Circuit Editing and Multi-Client MCP Design

**Date:** 2026-08-04
**Status:** Approved for implementation planning

## Goal

Let Codex, ChatGPT Desktop, and Claude Desktop use one local `psim-mcp` server to:

1. analyze an existing `.psimsch` without modifying it;
2. read complete C-block source code;
3. create and open a safe working copy;
4. apply requested component-value or C-block changes;
5. re-import the working copy to verify persistence; and
6. run PSIM only when the user explicitly requests simulation.

Natural-language interpretation remains the responsibility of the MCP host. The server exposes precise tools and validation; it does not add another natural-language parser.

## Verified Acceptance Inputs

The local acceptance run uses the user-provided originals named:

- `DQ_Transform.psimsch`
  - SHA-256: `70FCEAF9416DC025A5212B0E43A9ACA35D02CE9E3A80D6C2A123D26AB05FF924`
  - 36 components, 25 nets
  - `CBLOCK` `SCB1`, 2,910 source characters
- `Interleaving_Boost_Converter.psimsch`
  - SHA-256: `428BF7175CDAC61276FBD423A84B3C357B99EE58411988E605B05AE289FBA603`
  - 53 components, 38 nets
  - `CBLOCK` `SCB1`, 2,910 source characters

The binaries remain outside the repository. Real-PSIM acceptance tests receive their paths through `PSIM_DQ_EXAMPLE_PATH` and `PSIM_INTERLEAVING_EXAMPLE_PATH` so the suite stays portable and the originals are not redistributed.

## Architecture

```text
Codex / ChatGPT Desktop / Claude Desktop
                   | MCP STDIO
                   v
               psim-mcp
                   |
          import_circuit(original)
                   |
          +--------+---------+
          |                  |
       analysis          edit requested
          |                  |
      return data      prepare_edit(original)
                             |
                     open working copy
                             |
                 set_parameter / CONTENT
                             |
                  import_circuit(working)
                             |
                    optional simulation
```

One server implementation and one tool contract serve all three clients. Only their local MCP registration formats differ.

## Tool Contract Changes

### `import_circuit`

Extend the existing signature:

```python
import_circuit(
    path: str,
    include_graph: bool = False,
    include_source_code: bool = False,
) -> str
```

- The operation remains read-only and does not open the file for editing.
- With `include_source_code=False`, long strings keep the current abbreviated response.
- With `include_source_code=True`, `parameters.CONTENT` is returned without truncation for `CBLOCK` and `SIMPLECBLOCK` components.
- `include_graph` remains available for callers that need the complete graph. Full C-block retrieval no longer requires returning the entire graph.

### `prepare_edit`

Add one explicit write-boundary tool:

```python
prepare_edit(path: str, save_path: str | None = None) -> str
```

- Validate the source as an allowed existing `.psimsch` file.
- Compute the source SHA-256 using `hashlib`.
- Copy with `shutil.copy2`.
- Default destination: `PSIM_PROJECT_DIR/working/<source-stem>_working.psimsch`.
- Refuse to overwrite an existing destination.
- Open the copied schematic through the existing adapter.
- Return `source_path`, `working_path`, `source_sha256`, and `status="opened"`.

The first version copies only the `.psimsch`. The two verified acceptance files are standalone. Sidecar dependency copying is deferred until a real input requires it.

### `set_parameter`

Keep the public signature unchanged. Add only C-block-specific validation:

- ordinary strings retain the existing 1,024-character limit;
- `parameter_name="CONTENT"` accepts at most 65,536 characters;
- reject NUL characters;
- permit `CONTENT` only when the bridge-resolved component type is `CBLOCK` or `SIMPLECBLOCK`;
- persist through the existing `PsimSetElmValue2` and `PsimFileSave` path;
- avoid echoing the entire source in the success message.

No C parser or source rewriting layer is added. PSIM remains the compiler and execution authority.

## Data Flow

### Analysis-only request

1. The host calls `import_circuit` with the original path.
2. PSIM converts the schematic to Python.
3. The existing AST parser reconstructs components, wires, labels, nets, parameters, simulation settings, and C-block contents.
4. The host explains the result. No file is opened for mutation.

### Component-value change

1. Analyze the original and identify the exact component and native parameter name.
2. Call `prepare_edit`.
3. Call `set_parameter` on the open working copy.
4. Re-import the working copy and compare the requested value.
5. Run simulation only if requested.

### C-block change

1. Analyze with `include_source_code=True`.
2. Call `prepare_edit`.
3. Produce a complete replacement for `parameters.CONTENT`.
4. Call `set_parameter(component_id="SCB1", parameter_name="CONTENT", value=<source>)`.
5. Re-import with `include_source_code=True` and compare length/hash or exact source.
6. Run simulation only if requested; surface PSIM compilation or simulation errors unchanged except for existing sanitization.

## Safety and Error Handling

- Original files are never mutation targets in the documented workflow.
- `prepare_edit` returns `FILE_NOT_FOUND`, `VALIDATION_ERROR`, or `WORKING_COPY_EXISTS` without creating a partial result.
- A destination must remain inside the configured project directories.
- `CONTENT` on a non-C-block returns `UNSUPPORTED_PARAMETER`.
- oversized or NUL-containing code returns `VALIDATION_ERROR` before reaching PSIM.
- a PSIM exception does not report success;
- persistence is verified by re-importing the working copy, which detects PSIM's otherwise silent rejection of an unsupported parameter name;
- simulation is a separate explicit call so source inspection or editing cannot execute C code by itself.

## Client Integration

- **Codex CLI/IDE and ChatGPT Desktop:** add one STDIO entry to shared `config.toml`; verify with `codex mcp list`, `/mcp`, `get_status`, then `import_circuit`.
- **Claude Desktop:** keep a JSON STDIO example using the same executable and environment variables; verify through its MCP/connector status and `get_status`.
- Both examples include `ALLOWED_PROJECT_DIRS` covering the user-selected source folder, working-copy folder, and output folder.
- A one-click Claude `.mcpb` package is deferred until distribution to other users is needed.

## Examples

### DQ transform

1. Read the existing circuit and explain its topology and signal flow.
2. Return the complete `SCB1` source.
3. Explain the DQ-transform implementation.
4. On an explicit edit request, create a working copy, replace the requested code, re-import, and confirm the stored source.

### Interleaving boost

1. Read the existing circuit and identify the phase inductors and `SCB1`.
2. Create a working copy.
3. Change the requested inductor values.
4. Re-import and verify the persisted values.
5. If requested, simulate and compare ripple metrics before and after.

## Verification

### Unit tests

- `import_circuit` abbreviates C code by default and returns all 2,910 characters when requested.
- `prepare_edit` preserves the source, copies metadata, opens the copy, and refuses overwrite.
- ordinary parameter strings remain capped at 1,024 characters.
- a 2,910-character C-block value succeeds; values above 65,536 characters, NUL characters, and non-C-block `CONTENT` writes fail.
- tool registration and descriptions expose the new workflow.

### Real-PSIM acceptance

- Opt in through the existing `RUN_REAL_PSIM_TESTS=1` mechanism.
- Supply the two original paths through `PSIM_DQ_EXAMPLE_PATH` and `PSIM_INTERLEAVING_EXAMPLE_PATH`.
- Confirm the original hashes before and after every scenario.
- Confirm DQ full-source read, append a harmless marker comment to the working-copy source, and verify the exact persisted source without simulating it.
- Change the Interleaving Boost phase inductors from `125u` to `250u`, verify persistence, and use the existing simulation analysis to compare ripple.

### Client smoke checks

For each desktop host:

1. server initializes over STDIO;
2. `get_status` succeeds;
3. `import_circuit` returns the expected DQ statistics;
4. the host can follow `prepare_edit -> set_parameter -> import_circuit` on a working copy.

## Non-goals

- generating arbitrary schematics from scratch;
- an additional server-side natural-language engine;
- remote/cloud hosting, accounts, billing, or a UI;
- automatic execution after C-block changes;
- one-click installer packaging in this phase;
- copying unknown sidecar dependency trees.

## Completion Criteria

- Both verified originals remain byte-identical.
- DQ `SCB1` is returned and persisted without truncation.
- Interleaving Boost component changes persist in a working copy.
- the focused unit suite and opt-in real-PSIM scenarios pass.
- Codex, ChatGPT Desktop, and Claude Desktop configuration and smoke-check instructions are accurate and executable.
