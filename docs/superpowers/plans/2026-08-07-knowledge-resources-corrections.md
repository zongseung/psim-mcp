# Knowledge Resources Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all four `guidelines://` resources truthful and executable, including a safe 65,536-character C-Block `CONTENT` mutation path and seven available template files.

**Architecture:** Keep parameter validation in the service layer and component-type authority in the Python 3.8-compatible bridge. Split parameter tool registration across the existing `ParameterService` and `SimulationService`, then correct the Markdown resources to match the real runtime flow.

**Tech Stack:** Python 3.12 server, Python 3.8/3.9 bridge boundary, FastMCP, pytest, Ruff, Markdown, PSIM `.psimsch` assets.

## Global Constraints

- Use no new dependency or circuit-generation abstraction.
- All Python and test commands use `uv run`.
- Preserve unrelated dirty and untracked user files.
- Ordinary string parameters keep the 1,024-character limit.
- `CONTENT` alone accepts at most 65,536 characters and rejects NUL.
- Only `CBLOCK` and `SIMPLECBLOCK` accept `CONTENT` at the bridge boundary.
- Keep `bridge_script.py` Python 3.8-compatible and JSON-only across IPC.
- Template paths remain relative to the repository checkout; do not package schematics in the wheel.
- Do not add `.claude/skills`, automatic resource injection, or a C parser.

---

### Task 1: Share the C-Block string validation rule

**Files:**
- Modify: `src/psim_mcp/services/validators.py`
- Modify: `src/psim_mcp/services/parameter_service.py`
- Modify: `src/psim_mcp/services/simulation_service.py`
- Test: `tests/unit/test_validators.py`
- Test: `tests/unit/test_parameter_service.py`
- Test: `tests/unit/test_simulation_service.py`

**Interfaces:**
- Produces: `validate_parameter_string(value: str, parameter_name: str) -> ValidationResult`
- Preserves: `validate_string_length(value, max_length=1024, field_name="값")`

- [ ] **Step 1: Write failing validator boundary tests**

Add this import and test class to `tests/unit/test_validators.py`:

```python
from psim_mcp.services.validators import validate_parameter_string


class TestValidateParameterString:
    @pytest.mark.parametrize(
        ("name", "value"),
        [("CONTENT", "x" * 65_536), ("Resistance", "x" * 1_024)],
    )
    def test_accepts_boundary(self, name: str, value: str) -> None:
        assert validate_parameter_string(value, name).is_valid is True

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("CONTENT", "x" * 65_537),
            ("CONTENT", "x\x00y"),
            ("Resistance", "x" * 1_025),
        ],
    )
    def test_rejects_unsafe_or_oversized_value(self, name: str, value: str) -> None:
        result = validate_parameter_string(value, name)
        assert result.is_valid is False
        assert result.error_code == "INVALID_INPUT"
```

- [ ] **Step 2: Run the validator tests and confirm RED**

Run: `uv run pytest tests/unit/test_validators.py::TestValidateParameterString -q`

Expected: collection fails because `validate_parameter_string` does not exist.

- [ ] **Step 3: Implement the shared validator**

Add to `validators.py`:

```python
def validate_parameter_string(value: str, parameter_name: str) -> ValidationResult:
    """Validate string parameter limits, including C-Block source."""
    if parameter_name == "CONTENT" and "\x00" in value:
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_INPUT",
            error_message="CONTENT must not contain NUL characters.",
        )
    max_length = 65_536 if parameter_name == "CONTENT" else 1_024
    return validate_string_length(value, max_length, "parameter value")
```

Replace the direct `validate_string_length(..., max_length=1024, ...)` calls in both services with `validate_parameter_string(value, parameter_name)`.

- [ ] **Step 4: Add service regression tests**

Add `from unittest.mock import AsyncMock` and this test to
`test_parameter_service.py`:

```python
async def test_content_uses_extended_limit(
    parameter_service, project_service, mock_adapter, sample_project_path, monkeypatch,
):
    await project_service.open_project(str(sample_project_path))
    adapter_set = AsyncMock(return_value={"component_id": "SCB1"})
    monkeypatch.setattr(mock_adapter, "set_parameter", adapter_set)

    accepted = await parameter_service.set_parameter("SCB1", "CONTENT", "x" * 65_536)
    rejected = await parameter_service.set_parameter("SCB1", "CONTENT", "x" * 65_537)

    assert accepted["success"] is True
    assert rejected["success"] is False
    assert rejected["error"]["code"] == "INVALID_INPUT"
    adapter_set.assert_awaited_once()
```

Add `from unittest.mock import AsyncMock` and this compatibility test to
`test_simulation_service.py`:

```python
async def test_content_uses_extended_limit(
    self, service, mock_adapter, sample_project_path, monkeypatch,
):
    await service.open_project(str(sample_project_path))
    adapter_set = AsyncMock(return_value={"component_id": "SCB1"})
    monkeypatch.setattr(mock_adapter, "set_parameter", adapter_set)

    result = await service.set_parameter("SCB1", "CONTENT", "x" * 65_536)

    assert result["success"] is True
    adapter_set.assert_awaited_once()
```

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run: `uv run pytest tests/unit/test_validators.py tests/unit/test_parameter_service.py tests/unit/test_simulation_service.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add src/psim_mcp/services/validators.py src/psim_mcp/services/parameter_service.py src/psim_mcp/services/simulation_service.py tests/unit/test_validators.py tests/unit/test_parameter_service.py tests/unit/test_simulation_service.py
git commit -m "fix: validate C-Block source length"
```

### Task 2: Route parameter tools through their domain services

**Files:**
- Modify: `src/psim_mcp/tools/parameter.py`
- Modify: `src/psim_mcp/server.py`
- Test: `tests/unit/test_app_factory.py`

**Interfaces:**
- Changes: `register_tools(mcp, service=None, simulation_service=None)`
- Consumes: `ParameterService.set_parameter(...)` and `SimulationService.run_simulation(...)`

- [ ] **Step 1: Write a failing MCP-surface wiring test**

Add `from unittest.mock import AsyncMock` and this async test to
`test_app_factory.py`:

```python
async def test_parameter_tools_use_domain_services(monkeypatch):
    app = create_app(AppConfig(psim_mode="mock"))
    parameter_set = AsyncMock(return_value={"success": True, "data": {}})
    simulation_run = AsyncMock(return_value={"success": True, "data": {}})
    legacy_set = AsyncMock(return_value={"success": True, "data": {}})
    monkeypatch.setattr(app._services["parameter"], "set_parameter", parameter_set)
    monkeypatch.setattr(app._services["simulation"], "run_simulation", simulation_run)
    monkeypatch.setattr(app._services["_legacy"], "set_parameter", legacy_set)

    await app._tool_manager.call_tool(
        "set_parameter",
        {"component_id": "R1", "parameter_name": "Resistance", "value": 10},
        convert_result=False,
    )
    await app._tool_manager.call_tool(
        "sweep_parameter",
        {
            "component_id": "R1",
            "parameter_name": "Resistance",
            "start": 10,
            "end": 10,
            "step": 1,
        },
        convert_result=False,
    )

    assert parameter_set.await_count == 2
    assert simulation_run.await_count == 1
    legacy_set.assert_not_awaited()
```

- [ ] **Step 2: Run the wiring test and confirm RED**

Run: `uv run pytest tests/unit/test_app_factory.py::test_parameter_tools_use_domain_services -q`

Expected: failure because registered `set_parameter` still calls `_legacy`.

- [ ] **Step 3: Split the service dependencies at the existing registration seam**

Keep the `service` parameter name for compatibility and add `simulation_service=None`:

```python
def register_tools(mcp, service=None, simulation_service=None):
```

Resolve the parameter service from `mcp._services["parameter"]` and the simulation service from `mcp._services["simulation"]` only when explicit services are absent. Use the parameter service for every mutation and the simulation service only for `run_simulation` inside the sweep.

Replace `_get_service` with:

```python
def _get_services():
    """Resolve domain services from the lazy module-level app."""
    from psim_mcp.server import mcp

    return mcp._services["parameter"], mcp._services["simulation"]
```

Inside `set_parameter`, resolve `parameter_svc = service or _get_services()[0]`.
Inside `sweep_parameter`, resolve both
`parameter_svc = service or _get_services()[0]` and
`simulation_svc = simulation_service or _get_services()[1]`, then use:

```python
await parameter_svc.set_parameter(component_id, parameter_name, current)
sim_result = await simulation_svc.run_simulation()
```

Change `server.py` registration to:

```python
parameter.register_tools(mcp, services["parameter"], services["simulation"])
```

Do not remove the legacy service or its public compatibility methods.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `uv run pytest tests/unit/test_app_factory.py tests/unit/test_tool_integration.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/psim_mcp/tools/parameter.py src/psim_mcp/server.py tests/unit/test_app_factory.py
git commit -m "fix: route parameter tools to domain services"
```

### Task 3: Enforce C-Block component type in the bridge

**Files:**
- Modify: `src/psim_mcp/bridge/bridge_script.py`
- Test: `tests/unit/test_bridge_helpers.py`

**Interfaces:**
- Consumes: bridge-resolved `component_type`
- Produces: `UNSUPPORTED_PARAMETER` before any PSIM mutation when `CONTENT` targets another type

- [ ] **Step 1: Write the failing bridge guard test**

Add to `TestHandleSetParameter`:

```python
def test_rejects_content_for_non_cblock(self, monkeypatch):
    monkeypatch.setattr(bridge_script, "_current_sch", object())
    monkeypatch.setattr(bridge_script, "_current_path", "C:/tmp/test.psimsch")
    monkeypatch.setattr(bridge_script, "_element_cache", {"R1": "MULTI_RESISTOR"})

    result = bridge_script.handle_set_parameter({
        "component_id": "R1",
        "parameter_name": "CONTENT",
        "value": "void SimulationStep() {}",
    })

    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_PARAMETER"
```

- [ ] **Step 2: Run the bridge test and confirm RED**

Run: `uv run pytest tests/unit/test_bridge_helpers.py::TestHandleSetParameter::test_rejects_content_for_non_cblock -q`

Expected: failure because the bridge currently forwards `CONTENT` for every component type.

- [ ] **Step 3: Add the minimal type guard**

After resolving `component_type` and before calling `_get_psim()`, add:

```python
if parameter_name == "CONTENT" and component_type not in ("CBLOCK", "SIMPLECBLOCK"):
    return _error(
        "UNSUPPORTED_PARAMETER",
        "CONTENT is only writable for CBLOCK or SIMPLECBLOCK components.",
    )
```

Keep the code compatible with Python 3.8: do not use `match`, `|` type unions, or other newer syntax.

- [ ] **Step 4: Run bridge tests and confirm GREEN**

Run: `uv run pytest tests/unit/test_bridge_helpers.py tests/unit/test_bridge_contract.py tests/unit/test_bridge_mapping_registry.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/psim_mcp/bridge/bridge_script.py tests/unit/test_bridge_helpers.py
git commit -m "fix: restrict C-Block source updates"
```

### Task 4: Correct the knowledge resources and ship seven templates

**Files:**
- Modify: `src/psim_mcp/knowledge/workflow.md`
- Modify: `src/psim_mcp/knowledge/control_patterns.md`
- Modify: `src/psim_mcp/knowledge/gotchas.md`
- Modify: `src/psim_mcp/knowledge/templates.md`
- Add: `projects/interleaving_demo.psimsch`
- Add: `projects/verify_dq.psimsch`
- Test: `tests/unit/test_knowledge_resources.py`

**Interfaces:**
- Preserves: four existing `guidelines://` URIs
- Produces: seven repository-relative `.psimsch` paths that exist in a clean checkout

- [ ] **Step 1: Write a failing template-catalog test**

Add this test to `test_knowledge_resources.py`:

```python
import re
from pathlib import Path


def test_catalogued_templates_exist():
    root = Path(__file__).resolve().parents[2]
    markdown = (root / "src/psim_mcp/knowledge/templates.md").read_text(encoding="utf-8")
    paths = re.findall(r"`((?:paper_data|projects)/[^`]+\.psimsch)`", markdown)

    assert len(paths) == 7
    assert all((root / path).is_file() for path in paths)
```

- [ ] **Step 2: Prove the test fails in a clean-tree equivalent**

Run: `git cat-file -e HEAD:projects/interleaving_demo.psimsch`

Expected: non-zero exit because the first project template is not committed. Repeat for `projects/verify_dq.psimsch`.

- [ ] **Step 3: Correct the documented workflows and facts**

Use these exact workflow shapes in `workflow.md`, `templates.md`, and
`control_patterns.md`:

```text
import_circuit(path) -> understand -> open_project(path) -> set_parameter(...)
  -> run_simulation(simview=false) -> analyze_existing(...)
```

```text
import_circuit(path, include_graph=true) -> inspect full CONTENT
  -> open_project(path) -> set_parameter(SCB_id, "CONTENT", new_code)
  -> run_simulation(simview=false) -> analyze_existing(...)
```

In `gotchas.md`, replace the blanket subtype and SimControl claims with:

```markdown
| 시뮬 시간의 raw PSIM 이름 | `TotalTime` / `TimeStep` |

MCP `set_parameter`에서는 `TOTALTIME`/`TIMESTEP` 별칭도 같은 이름으로 매핑된다.

- 이상형 스위치 `MULTI_MOSFET`/`MULTI_IGBT`: `SubType="Ideal"`
- 수동소자 `MULTI_RESISTOR`/`MULTI_INDUCTOR`/`MULTI_CAPACITOR`: 검증 예제는 `SubType="Level 1"`
- C-Block `CONTENT`: 최대 65,536자, NUL 문자 금지
```

Also make these semantic changes:

- insert `open_project(path)` after inspection and before every mutation loop;
- use `import_circuit(path, include_graph=true)` when reading full C-Block `CONTENT`;
- document the 65,536-character and NUL constraints for `CONTENT`;
- scope `SubType="Ideal"` to verified ideal MOSFET/IGBT switches and state that passive R/L/C examples use `SubType="Level 1"`;
- state that raw PSIM uses `TotalTime`/`TimeStep`, while MCP accepts the `TOTALTIME`/`TIMESTEP` aliases;
- state that catalog paths are relative to the repository root.

Keep all four URIs, resource filenames, and the seven catalog rows unchanged.

- [ ] **Step 4: Add only the two catalogued project files**

Stage `projects/interleaving_demo.psimsch` and `projects/verify_dq.psimsch`. Do not stage other files currently under `projects/`.

- [ ] **Step 5: Run resource tests and confirm GREEN**

Run: `uv run pytest tests/unit/test_knowledge_resources.py -q`

Expected: all tests pass and the catalog contains exactly seven existing paths.

- [ ] **Step 6: Commit Task 4**

```powershell
git add src/psim_mcp/knowledge/workflow.md src/psim_mcp/knowledge/control_patterns.md src/psim_mcp/knowledge/gotchas.md src/psim_mcp/knowledge/templates.md tests/unit/test_knowledge_resources.py projects/interleaving_demo.psimsch projects/verify_dq.psimsch
git commit -m "docs: correct PSIM knowledge resources"
```

### Task 5: Final verification

**Files:**
- Verify only; modify files only for findings confirmed by the final review.

**Interfaces:**
- Consumes: commits from Tasks 1-4
- Produces: full test, lint, diff, and whole-branch review evidence

- [ ] **Step 1: Run the complete unit suite**

Run: `uv run pytest tests/unit -q`

Expected: all tests pass.

- [ ] **Step 2: Run Ruff and whitespace validation**

Run: `uv run ruff check src/ tests/`

Run: `git diff --check 8a1292f...HEAD`

Expected: both commands exit zero.

- [ ] **Step 3: Confirm the shipped artifacts and commit ancestry**

Run: `git ls-tree -r --name-only HEAD src/psim_mcp/knowledge projects | Select-String -Pattern 'knowledge/|interleaving_demo|verify_dq'`

Expected: four knowledge Markdown files and both project templates are present.

- [ ] **Step 4: Dispatch the final whole-branch reviewer**

Review `8a1292f...HEAD` against the design spec and this plan. Require separate spec-compliance and code-quality verdicts, with no unresolved load-bearing findings.
