# 09. Dynamic Circuit Design: LLM-as-Designer Architecture

## The Problem

The current PSIM-MCP circuit design pipeline has a fundamental scalability bottleneck:

1. **Only 3 topologies have auto-calculation.** The `generators/` module contains hardcoded design formulas for `buck`, `boost`, and `buck_boost` only. These generators compute component values (inductance, capacitance, R_load) from user specs (Vin, Vout, Iout).

2. **29 templates have fixed default values.** The remaining templates in `data/circuit_templates.py` provide static component parameters. When a user requests a flyback converter with specific specs, the tool returns a template with generic defaults (e.g., `inductance: 47e-6`) regardless of the user's requirements.

3. **The `design_circuit` tool falls back silently.** When a generator is not available, `design_circuit` falls through to the template path, applies a simple `_SPEC_MAP` substitution (V_in -> DC_Source.voltage), and ignores derived parameters like transformer turns ratio, resonant frequency, or duty cycle.

4. **Adding new topologies requires Python code.** Each new generator needs a dedicated Python file (`generators/flyback.py`, `generators/llc.py`, etc.) with manually derived formulas. This does not scale to the 40+ power electronics topologies that engineers work with.

5. **The NLP intent parser is a bottleneck.** `parsers/intent_parser.py` uses keyword matching to identify topology and extract specs. It cannot understand arbitrary natural language like "isolated 5V 2A power supply from rectified mains."

### Concrete Failure Examples

| User Request | Current Behavior | Desired Behavior |
|---|---|---|
| "Flyback 310V input 5V output 2A" | Falls back to `flyback` template with defaults (if template exists) or returns NO_MATCH | Properly designed flyback with calculated turns ratio (N=Vin*D/(Vout*(1-D))), Lm, output cap |
| "LLC resonant converter 400V to 48V 1kW" | NO_MATCH or template defaults | LLC with calculated Lr, Cr, Lm, resonant frequency, transformer ratio |
| "Phase-shifted full bridge 800V to 48V" | Uses `full_bridge` template (wrong topology) | PSFB with correct transformer, resonant inductor, timing parameters |
| "Two-stage PFC + LLC for 19V laptop charger" | NO_MATCH | Multi-stage design with PFC front-end + LLC post-regulator |


## The Solution: LLM-as-Designer

### Key Insight

In the MCP architecture, Claude (the LLM client) **is** the circuit designer. Claude has extensive knowledge of power electronics: transformer design equations, resonant tank calculations, control loop sizing, thermal considerations, and more.

The current design hardcodes domain knowledge into Python generators. This is the wrong layer. Instead:

- **The LLM's job:** Design the circuit -- choose topology, calculate component values, determine connections.
- **The tool's job:** Validate the design, render it visually, create the `.psimsch` file.

### How MCP Enables This

In MCP, the LLM reads tool descriptions to understand what tools can do and what arguments they accept. If `preview_circuit` clearly describes that it accepts arbitrary `components` and `connections` lists, Claude will construct them from its own knowledge.

```
Current flow:
  user → design_circuit → keyword parser → hardcoded generator → preview
  (tool does the thinking)

Proposed flow:
  user → Claude designs circuit → preview_circuit(components, connections) → validate → render
  (LLM does the thinking, tool does the execution)
```

### Why This Works

1. **Claude knows power electronics.** It can calculate: duty cycle, inductor/capacitor sizing, transformer turns ratios, resonant frequencies, snubber design, gate drive requirements, and more.

2. **Claude can handle ambiguity.** "Isolated 5V supply from mains" -- Claude knows this implies: AC-DC rectification, PFC (likely), isolated DC-DC (flyback for <100W, LLC for higher power), output filtering.

3. **Claude can self-correct.** If validation returns errors (e.g., "unknown component type `FET`" or "floating pin `T1.secondary_out`"), Claude can read the error, fix its design, and retry.

4. **No formula maintenance.** New topologies, emerging components, or unusual designs require zero code changes.


## Architecture Change

### Current Architecture

```
┌──────────────┐     ┌────────────────────┐     ┌──────────────────┐
│ design_circuit│────>│ intent_parser.py   │────>│ generators/      │
│   (tool)      │     │ (keyword matching) │     │ buck.py          │
│               │     │                    │     │ boost.py         │
│               │     │                    │     │ buck_boost.py    │
│               │     │                    │     │ (3 topologies)   │
│               │     └────────────────────┘     └──────────────────┘
│               │              │                          │
│               │              │ fallback                  │ generate()
│               │              v                          v
│               │     ┌────────────────────┐     ┌──────────────────┐
│               │     │ circuit_templates  │     │ components+nets  │
│               │     │ (29 static)        │     │ (calculated)     │
│               │     └────────────────────┘     └──────────────────┘
└──────────────┘
```

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude (LLM Client)                         │
│                                                                 │
│  1. Reads user request: "Flyback 310V→5V 2A"                  │
│  2. Calls get_component_library() → learns available parts     │
│  3. Designs circuit using power electronics knowledge          │
│  4. Calls preview_circuit(components=[...], connections=[...]) │
│  5. Reviews validation feedback, self-corrects if needed       │
│  6. Calls confirm_circuit(token, save_path) when satisfied     │
└──────────────┬──────────────────┬──────────────────┬───────────┘
               │                  │                  │
               v                  v                  v
┌──────────────────┐ ┌────────────────────┐ ┌──────────────────────┐
│get_component_    │ │ preview_circuit    │ │ confirm_circuit      │
│library (NEW)     │ │ (enhanced)         │ │ (unchanged)          │
│                  │ │                    │ │                      │
│Returns:          │ │Accepts:            │ │Saves .psimsch        │
│- all types       │ │- components[]      │ │                      │
│- pins per type   │ │- connections[]     │ │                      │
│- default params  │ │                    │ │                      │
│- categories      │ │Returns:            │ │                      │
│                  │ │- validation result │ │                      │
│                  │ │- SVG preview       │ │                      │
│                  │ │- preview_token     │ │                      │
└──────────────────┘ └────────────────────┘ └──────────────────────┘
```

### Role of Existing Generators

Generators become an **optional optimization**, not the primary path:

- For `buck`, `boost`, `buck_boost`: the generator can still be invoked as a fast path (no LLM round-trip needed for common topologies).
- For everything else: Claude designs the circuit directly.
- The `design_circuit` tool can remain as a convenience, but it is no longer the gatekeeper.


## What Needs to Change

## Remaining Hardcoded Areas in Current Code

Even after the recent refactors, the current implementation still contains several hardcoded layers that conflict with the long-term `LLM-as-Designer` direction.

These should be treated differently:

- some should be removed as the primary path
- some can remain as fallback or optimization
- some are placeholders that must be replaced with real PSIM-backed data

### A. Hardcoding that should be reduced aggressively

#### 1. `_SPEC_MAP` in `tools/circuit.py`

Current state:

- high-level specs like `V_in`, `R_load`, `switching_frequency` are mapped to specific component parameters through a static dict
- this works only for simple topologies
- it does not scale to transformer-based, resonant, multi-stage, or control-heavy designs

Why this is a problem:

- it encodes circuit design knowledge in the tool layer
- it silently ignores derived relationships
- it encourages template mutation instead of actual design synthesis

Desired state:

- Claude produces explicit `components` and `connections`
- or a richer intermediate design spec that is later validated
- the tool should not try to infer circuit equations from a small substitution table

#### 2. Pin-side assumptions in `bridge/wiring.py`

Current state:

- `_LEFT_PINS` / `_RIGHT_PINS` define pin positions through static name groups
- `resolve_pin_position()` uses these names to estimate coordinates

Why this is a problem:

- different PSIM symbols may have different geometry
- the same pin name does not guarantee the same physical location
- this will break on more complex components

Desired state:

- pin geometry should come from component metadata or PSIM-confirmed symbol data
- `wire_plan` should not rely on broad left/right naming heuristics as the long-term source of truth

#### 3. Bridge API probing by hardcoded function names

Current state:

- the bridge searches for `PsimCreateWire`, `PsimConnect`, `PsimCreateNewWire`

Why this is a problem:

- it is still an exploratory hardcoded probe
- once the real PSIM API contract is confirmed, the bridge should use the known correct path

Desired state:

- replace probing logic with a documented, version-checked implementation
- keep fallback probing only if PSIM version variance makes it necessary

### B. Hardcoding that can remain as fallback or optimization

#### 4. Static templates in `data/circuit_templates.py`

Current state:

- 29+ topologies are stored as static templates

Role in the new architecture:

- these can remain as:
  - fallback assets
  - demo fixtures
  - rendering/test samples
  - fast-path defaults for common topologies

Rule:

- templates must not be the only way to support a topology
- templates should not block fully custom LLM-designed circuits

#### 5. Python generators for `buck`, `boost`, `buck_boost`

Current state:

- only 3 topologies have formula-based generators

Role in the new architecture:

- keep them as optimization for common requests
- do not require every new topology to have a Python generator

Rule:

- generator exists → use it as a fast path
- generator missing → Claude should still be able to design the circuit through `preview_circuit`

### C. Placeholder hardcoding that must be replaced with real data

#### 6. Empty `psim_element_type` fields in `component_library.py`

Current state:

- the field exists for nearly all components
- most values are still empty strings

Why this matters:

- this is the bridge between logical component type and actual PSIM element creation
- until it is populated, the component catalog is structurally improved but not operationally complete

Desired state:

- populate from Windows `Save as Python Code`
- use the catalog mapping in bridge creation instead of raw `comp["type"]`

#### 7. Keyword-based NLP maps in `parsers/keyword_map.py`

Current state:

- topology detection and use-case detection still depend on static keyword maps

Role in the new architecture:

- acceptable as a convenience parser
- should not be the primary design intelligence layer

Rule:

- if parser succeeds, good
- if parser fails, Claude should still be able to directly call `get_component_library` + `preview_circuit` with a custom design

### D. Rendering-specific hardcoding

#### 8. Specialized ASCII renderers

Current state:

- some topologies still have dedicated ASCII renderer logic (`buck`, `boost`, `half_bridge`, `full_bridge`)

Impact:

- acceptable for UX/demo purposes
- not part of the core design bottleneck

Rule:

- keep as optional presentation enhancement
- do not couple design correctness to specialized renderer support

---

### 1. New Tool: `get_component_library`

Claude needs to know what components are available, what pins they have, and what parameters they accept. Without this, Claude would guess (and sometimes guess wrong).

**File:** `src/psim_mcp/tools/circuit.py` (add to existing registration)

```python
@mcp.tool(
    description=(
        "Returns the complete PSIM component library. "
        "Use this to learn available component types, their pins, "
        "and default parameters before designing a custom circuit. "
        "Each component has: type name, category, pins (for connections), "
        "and default parameters (with units). "
        "When building a circuit, use these exact type names and pin names."
    ),
)
@tool_handler("get_component_library")
async def get_component_library(category: str | None = None) -> str:
    """Return all available component types with their pins and parameters.

    Args:
        category: Optional filter — one of: switch, diode, passive, source,
            transformer, motor, sensor, filter, control, storage, thermal.
    """
    from psim_mcp.data.component_library import COMPONENTS, CATEGORIES

    result = {}
    for type_name, comp in COMPONENTS.items():
        if category and comp["category"] != category.lower():
            continue
        result[type_name] = {
            "category": comp["category"],
            "pins": comp["pins"],
            "default_parameters": comp["default_parameters"],
            "symbol": comp["symbol"],
        }

    return {
        "success": True,
        "data": {
            "components": result,
            "total": len(result),
            "categories": list(CATEGORIES.keys()),
        },
        "message": (
            f"{len(result)} component types available. "
            "Use these exact type names and pin names when building circuits."
        ),
    }
```

### 2. Enhanced `preview_circuit` Tool Description

The current description does not tell Claude that it can (and should) pass custom components and connections for any circuit. The description must explicitly guide Claude's behavior.

**File:** `src/psim_mcp/tools/circuit.py`

**Current description:**
```python
description=(
    "회로도를 SVG 미리보기로 생성합니다. "
    "Mac/Windows 모두 가능. 확인 후 confirm_circuit으로 실제 생성합니다. "
    "specs로 사양(입력전압, 출력전압, 부하 등)을 지정하면 템플릿에 자동 반영됩니다."
),
```

**Proposed description:**
```python
description=(
    "Generate an SVG preview of a circuit. Two modes of operation:\n\n"
    "MODE 1 — Template-based (simple): Pass circuit_type='buck' with specs={'V_in': 48, 'V_out': 12}.\n\n"
    "MODE 2 — Custom design (any topology): Pass circuit_type='custom' (or any name) with explicit "
    "components and connections lists. Use get_component_library() first to see available "
    "component types and their pin names.\n\n"
    "Components format: [{\"id\": \"V1\", \"type\": \"DC_Source\", \"parameters\": {\"voltage\": 310}, "
    "\"position\": {\"x\": 0, \"y\": 0}}, ...]\n\n"
    "Connections format: [{\"from\": \"V1.positive\", \"to\": \"SW1.drain\"}, ...]\n\n"
    "Validation warnings are returned in the response — use them to fix connection or parameter issues.\n\n"
    "After preview, call confirm_circuit(preview_token=..., save_path=...) to save the .psimsch file."
),
```

### 3. Improved Validation Feedback

Currently, validation results are included but not structured for self-correction. The validator should return actionable suggestions.

**File:** `src/psim_mcp/validators/structural.py` — enhance the validation response:

```python
# Add pin validation for connections
def validate_connections(spec: dict) -> ValidationResult:
    """Validate that all connection endpoints reference valid component.pin pairs."""
    errors = []
    warnings = []
    components = {c["id"]: c for c in spec.get("components", [])}
    connections = spec.get("connections", [])

    for conn in connections:
        for endpoint_key in ("from", "to"):
            endpoint = conn.get(endpoint_key, "")
            if "." not in endpoint:
                errors.append(ValidationIssue(
                    severity="error",
                    code="CONN_BAD_FORMAT",
                    message=f"Connection endpoint '{endpoint}' must be 'ComponentID.pin_name'.",
                    suggestion="Format: 'V1.positive', 'SW1.drain', etc.",
                ))
                continue
            comp_id, pin_name = endpoint.split(".", 1)
            if comp_id not in components:
                errors.append(ValidationIssue(
                    severity="error",
                    code="CONN_UNKNOWN_COMP",
                    message=f"Connection references unknown component '{comp_id}'.",
                    suggestion=f"Available components: {', '.join(sorted(components.keys()))}",
                ))
            else:
                comp_type = components[comp_id].get("type", "")
                from psim_mcp.data.component_library import get_component
                lib_comp = get_component(comp_type)
                if lib_comp and pin_name not in lib_comp.get("pins", []):
                    errors.append(ValidationIssue(
                        severity="error",
                        code="CONN_UNKNOWN_PIN",
                        message=f"Pin '{pin_name}' is not valid for {comp_type}.",
                        suggestion=f"Valid pins for {comp_type}: {', '.join(lib_comp['pins'])}",
                    ))

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
```

### 4. Updated `design_circuit` — Fallback, Not Primary

The `design_circuit` tool should still exist for backward compatibility, but its description should clarify its role and guide Claude to use `preview_circuit` directly for custom designs.

## Hardcoding Policy

To avoid architectural drift, future implementation should follow this policy:

### Remove from primary path

- `_SPEC_MAP`-style topology logic in tools
- rigid parser-only topology resolution
- pin-side heuristics as the only wiring source

### Keep as fallback

- static templates
- simple generators for common topologies
- keyword parser for convenience requests

### Replace with verified runtime knowledge

- `psim_element_type`
- bridge wiring contract
- symbol/pin geometry

## Practical Priority Order

1. Add `get_component_library`
2. Make `preview_circuit` custom-design-first in its tool description
3. Improve validation feedback so Claude can self-correct
4. Populate `psim_element_type` from Windows PSIM evidence
5. Replace `_SPEC_MAP`-driven template mutation as the default design path
6. Reduce parser/generator dependency to fast-path usage only

**File:** `src/psim_mcp/tools/design.py`

**Proposed description change:**
```python
description=(
    "Quick design shortcut for common topologies (buck, boost, buck_boost). "
    "Automatically calculates component values from specs. "
    "For other topologies or custom circuits, use preview_circuit() directly "
    "with explicit components and connections — call get_component_library() first "
    "to see available parts."
),
```


## Implementation Plan

### Phase 1: Enable Claude-as-Designer (Minimal Changes) ✅ 완료

These changes unlock the new architecture without breaking anything:

| Task | File | Change | 상태 |
|---|---|---|---|
| Add `get_component_library` tool | `src/psim_mcp/tools/circuit.py` | New tool registration (~30 lines) | ✅ |
| Update `preview_circuit` description | `src/psim_mcp/tools/circuit.py` | Replace description string | ✅ |
| Update `design_circuit` description | `src/psim_mcp/tools/design.py` | Replace description string | ✅ |
| Add connection validation | `src/psim_mcp/validators/structural.py` | New `validate_connections` function (~40 lines) | ✅ |
| Wire connection validation into preview | `src/psim_mcp/tools/circuit.py` | Call `validate_connections` in `preview_circuit` | ✅ |

**Estimated effort:** 1-2 hours of coding + testing.

### Phase 2: Improve Claude's Design Quality

These changes help Claude produce better designs on the first attempt:

| Task | File | Change |
|---|---|---|
| Add example circuits in tool docstrings | `src/psim_mcp/tools/circuit.py` | Add flyback, LLC examples in the description or as a separate `get_design_examples` tool |
| Enhance validation with electrical checks | `src/psim_mcp/validators/electrical.py` | Floating node detection, source-to-ground path check |
| Add `validate_circuit` as a standalone tool | `src/psim_mcp/tools/circuit.py` | Let Claude explicitly validate before previewing |
| Position auto-layout for custom circuits | `src/psim_mcp/generators/layout.py` | Apply `auto_layout` to any component list, not just generator output |

### Phase 3: Optimization

| Task | Description |
|---|---|
| Cache component library | Claude should only need to call `get_component_library` once per session. Consider MCP resources for this. |
| Generator as fast-path | Keep generators for buck/boost/buck_boost as optimization (skip LLM calculation round-trip) |
| Prompt engineering | Add system-level instructions for Claude about PSIM circuit design conventions |
| Multi-stage circuits | Support circuits with multiple power stages (PFC+LLC, interleaved converters) |


## Specific Code Changes Summary

### Files to Modify

1. **`src/psim_mcp/tools/circuit.py`**
   - Add `get_component_library` tool registration
   - Update `preview_circuit` description to explain custom design mode
   - Improve validation warning format in preview response

2. **`src/psim_mcp/tools/design.py`**
   - Update `design_circuit` description to position it as a shortcut, not the primary path

3. **`src/psim_mcp/validators/structural.py`**
   - Add `validate_connections()` function that checks component.pin references
   - Return actionable suggestions (list valid pins when a pin is wrong)

4. **`src/psim_mcp/validators/__init__.py`**
   - Wire `validate_connections` into the main `validate_circuit` pipeline

### Files to Create

None required for Phase 1. The existing file structure supports all changes.

### Files NOT to Change

- `src/psim_mcp/generators/` — Keep as-is. Generators remain a valid fast-path.
- `src/psim_mcp/data/circuit_templates.py` — Keep as-is. Templates remain available for simple cases.
- `src/psim_mcp/parsers/` — Keep as-is. The intent parser still works for `design_circuit`.
- `src/psim_mcp/bridge/` — No changes needed. The bridge layer already handles arbitrary components and connections.


## Validation Criteria

After Phase 1 implementation, these scenarios should work:

1. **"Flyback 310V input 5V output 2A"** — Claude calls `get_component_library()`, then `preview_circuit(circuit_type="flyback", components=[...], connections=[...])` with calculated values.

2. **"LLC resonant converter 400V to 48V 1kW"** — Claude designs LLC with Lr, Cr, Lm, transformer, and correct connections.

3. **"Simple RC low-pass filter 1kHz cutoff"** — Claude uses R + C with f = 1/(2*pi*R*C).

4. **Claude makes a pin name mistake** — Validation returns: "Pin 'output' is not valid for MOSFET. Valid pins: drain, source, gate." Claude self-corrects and retries.

5. **Existing buck/boost/buck_boost via `design_circuit`** — Still works exactly as before (generator fast-path).
