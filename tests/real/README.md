# Real PSIM Acceptance Tests

`tests/real/` is reserved for opt-in scenarios that must run against a real PSIM installation on Windows. The default unit and integration suites remain mock-based.

## Current scenario

- `test_buck_given_48v_12v_5a_when_simulated_then_output_meets_spec`
- Given: buck converter, `Vin=48V`, `Vout=12V`, `Iout=5A`, `fsw=100kHz`
- When: run PSIM for `20 ms`
- Then: `output_voltage_mean` is within `5%` of `12V`, `output_voltage_ripple_pct < 2%`, and inductor current is positive

## Required environment

- `RUN_REAL_PSIM_TESTS=1`
- `PSIM_MODE=real`
- `PSIM_PATH=C:\Powersim\PSIM`
- `PSIM_PYTHON_EXE=C:\Powersim\PSIM\python38\python.exe`
- `PSIM_PROJECT_DIR=<writable directory for generated .psimsch files>`
- `PSIM_OUTPUT_DIR=<writable directory for exported artifacts>`

`PSIM_PYTHON_EXE` may be omitted if `PSIM_PATH\python38\python.exe` exists.

## Run

```powershell
$env:RUN_REAL_PSIM_TESTS="1"
$env:PSIM_MODE="real"
$env:PSIM_PATH="C:\Powersim\PSIM"
$env:PSIM_PROJECT_DIR="C:\psim-projects"
$env:PSIM_OUTPUT_DIR="C:\psim-output"
uv run pytest tests\real -m "real_psim and acceptance" -v
```

Generated schematics and artifacts are written under `PSIM_PROJECT_DIR\pytest_real` and `PSIM_OUTPUT_DIR\pytest_real`.
