"""Post-generation design constraint validation engine.

Validates that generated circuit parameters are electrically feasible
using topology-specific design rules. All checks are formula-based,
not hardcoded thresholds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ConstraintIssue:
    """A single constraint violation or warning."""

    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    parameter: str
    actual_value: float
    limit_value: float | None = None
    suggestion: str = ""


@dataclass
class ConstraintResult:
    """Result of constraint validation."""

    is_feasible: bool
    issues: list[ConstraintIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ConstraintIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ConstraintIssue]:
        return [i for i in self.issues if i.severity == "warning"]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_TOPOLOGY_CHECKS: dict[str, list[Callable]] = {}


def _register_check(topologies: list[str]):
    """Decorator to register a check function for given topologies.

    Use ``["*"]`` to register a check that applies to every topology.
    """

    def decorator(fn: Callable) -> Callable:
        for t in topologies:
            _TOPOLOGY_CHECKS.setdefault(t, []).append(fn)
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_design(design_result: dict) -> dict:
    """Extract design metadata from generator result."""
    return design_result.get("metadata", {}).get("design", {})


def _get_simulation(design_result: dict) -> dict:
    """Extract simulation parameters from generator result."""
    return design_result.get("simulation", {})


def _safe_float(value, default: float = 0.0) -> float:
    """Convert to float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Common checks (all topologies)
# ---------------------------------------------------------------------------

@_register_check(["*"])
def _check_duty_cycle_bounds(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Duty cycle must be strictly between 0 and 1."""
    design = _get_design(design_result)
    duty = design.get("duty")
    if duty is None:
        return

    duty = _safe_float(duty)
    if duty <= 0:
        issues.append(ConstraintIssue(
            severity="error",
            code="DUTY_CYCLE_ZERO_OR_NEGATIVE",
            message=f"Duty cycle {duty:.4f} is <= 0, circuit cannot operate.",
            parameter="duty",
            actual_value=duty,
            limit_value=0.0,
            suggestion="Check that Vout and Vin are correctly specified for this topology.",
        ))
    elif duty >= 1.0:
        issues.append(ConstraintIssue(
            severity="error",
            code="DUTY_CYCLE_GEQ_ONE",
            message=f"Duty cycle {duty:.4f} >= 1.0, physically unrealizable.",
            parameter="duty",
            actual_value=duty,
            limit_value=1.0,
            suggestion="Verify voltage ratio is achievable with the selected topology.",
        ))


@_register_check(["*"])
def _check_power_balance(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Check that output power is within reasonable efficiency bounds of input."""
    vin = _safe_float(requirements.get("vin"))
    vout = _safe_float(requirements.get("vout_target"))
    iout = _safe_float(requirements.get("iout", requirements.get("iout_target", 0)))

    if not (vin > 0 and vout > 0 and iout > 0):
        return

    design = _get_design(design_result)
    duty = _safe_float(design.get("duty"))
    if duty <= 0:
        return

    p_out = vout * iout
    # Estimate input current from topology duty relationship
    # Use a broad efficiency window: 70%–100%
    r_load = design.get("r_load")
    if r_load:
        r_load = _safe_float(r_load)
        p_load = vout ** 2 / r_load if r_load > 0 else 0
        if p_load > 0 and abs(p_load - p_out) / p_out > 0.1:
            issues.append(ConstraintIssue(
                severity="warning",
                code="POWER_BALANCE_MISMATCH",
                message=(
                    f"Load power V^2/R = {p_load:.2f}W differs from "
                    f"Vout*Iout = {p_out:.2f}W by >{10}%."
                ),
                parameter="r_load",
                actual_value=p_load,
                limit_value=p_out,
                suggestion="Verify R_load matches the specified output current.",
            ))


@_register_check(["*"])
def _check_simulation_feasibility(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Validate simulation parameters provide adequate resolution and duration."""
    sim = _get_simulation(design_result)
    time_step = _safe_float(sim.get("time_step"))
    total_time = _safe_float(sim.get("total_time"))

    # Determine switching frequency from requirements or components
    fsw = _safe_float(requirements.get("fsw"))
    if fsw <= 0:
        # Try to infer from components
        for comp in design_result.get("components", []):
            params = comp.get("parameters", {})
            if "switching_frequency" in params:
                fsw = _safe_float(params["switching_frequency"])
                break

    if fsw <= 0 or time_step <= 0:
        return

    # Nyquist: need at least 20 points per switching period
    max_step = 1.0 / (fsw * 20)
    if time_step > max_step:
        issues.append(ConstraintIssue(
            severity="error",
            code="TIME_STEP_TOO_LARGE",
            message=(
                f"Time step {time_step:.2e}s exceeds Nyquist limit "
                f"{max_step:.2e}s (fsw={fsw/1e3:.1f}kHz, 20 pts/period)."
            ),
            parameter="time_step",
            actual_value=time_step,
            limit_value=max_step,
            suggestion="Reduce time_step to at least 1/(fsw * 20).",
        ))

    if total_time <= 0:
        return

    # Need at least 10 switching cycles
    min_total = 10.0 / fsw
    if total_time < min_total:
        issues.append(ConstraintIssue(
            severity="warning",
            code="TOTAL_TIME_TOO_SHORT",
            message=(
                f"Total time {total_time:.2e}s provides < 10 switching cycles "
                f"(need >= {min_total:.2e}s at fsw={fsw/1e3:.1f}kHz)."
            ),
            parameter="total_time",
            actual_value=total_time,
            limit_value=min_total,
            suggestion="Increase total_time to at least 10/fsw for steady-state observation.",
        ))


@_register_check(["*"])
def _check_inductor_ripple(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Check if inductor current ripple indicates DCM operation."""
    iout = _safe_float(requirements.get("iout", requirements.get("iout_target", 0)))
    if iout <= 0:
        return

    ripple_ratio = _safe_float(requirements.get("ripple_ratio"))
    if ripple_ratio <= 0:
        # Try to derive from design
        design = _get_design(design_result)
        delta_i = _safe_float(design.get("delta_i"))
        if delta_i > 0:
            ripple_ratio = delta_i / iout
        else:
            return

    if ripple_ratio > 1.0:
        issues.append(ConstraintIssue(
            severity="warning",
            code="DCM_OPERATION",
            message=(
                f"Current ripple ratio {ripple_ratio:.2f} > 1.0 indicates "
                f"Discontinuous Conduction Mode (DCM). Design formulas assume CCM."
            ),
            parameter="ripple_ratio",
            actual_value=ripple_ratio,
            limit_value=1.0,
            suggestion="Reduce ripple_ratio or increase iout to stay in CCM.",
        ))
    elif ripple_ratio > 0.8:
        issues.append(ConstraintIssue(
            severity="info",
            code="NEAR_DCM_BOUNDARY",
            message=(
                f"Current ripple ratio {ripple_ratio:.2f} is near DCM boundary. "
                f"Circuit may enter DCM at light load."
            ),
            parameter="ripple_ratio",
            actual_value=ripple_ratio,
            limit_value=1.0,
        ))


# ---------------------------------------------------------------------------
# Buck-specific checks
# ---------------------------------------------------------------------------

@_register_check(["buck"])
def _check_buck_voltage_ratio(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Buck requires Vout < Vin."""
    vin = _safe_float(requirements.get("vin"))
    vout = _safe_float(requirements.get("vout_target"))
    if vin <= 0 or vout <= 0:
        return

    if vout >= vin:
        issues.append(ConstraintIssue(
            severity="error",
            code="BUCK_VOUT_GEQ_VIN",
            message=f"Buck converter requires Vout ({vout}V) < Vin ({vin}V).",
            parameter="vout_target",
            actual_value=vout,
            limit_value=vin,
            suggestion="Use a boost converter for step-up or verify voltage values.",
        ))


@_register_check(["buck"])
def _check_buck_switch_stress(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Buck switch sees full Vin."""
    vin = _safe_float(requirements.get("vin"))
    if vin <= 0:
        return

    # Switch voltage stress = Vin (with margin for ringing)
    v_switch = vin
    # Warn if Vin is very high relative to typical MOSFET ratings
    if v_switch > 600:
        issues.append(ConstraintIssue(
            severity="warning",
            code="HIGH_SWITCH_VOLTAGE_STRESS",
            message=(
                f"Switch voltage stress {v_switch:.1f}V is high. "
                f"Consider SiC/GaN devices or series-connected topology."
            ),
            parameter="vin",
            actual_value=v_switch,
            limit_value=600.0,
            suggestion="Consider using a two-stage approach or wide-bandgap devices.",
        ))


# ---------------------------------------------------------------------------
# Boost-specific checks
# ---------------------------------------------------------------------------

@_register_check(["boost", "boost_pfc"])
def _check_boost_duty_practical(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Boost duty > 0.85 leads to severe efficiency degradation."""
    design = _get_design(design_result)
    duty = _safe_float(design.get("duty"))
    if duty <= 0:
        return

    # Practical limit: efficiency drops sharply above D=0.85
    if duty > 0.85:
        issues.append(ConstraintIssue(
            severity="warning",
            code="BOOST_HIGH_DUTY",
            message=(
                f"Boost duty cycle {duty:.3f} > 0.85. Efficiency will degrade "
                f"significantly due to high conduction losses and parasitic effects."
            ),
            parameter="duty",
            actual_value=duty,
            limit_value=0.85,
            suggestion="Consider a two-stage approach or different topology for this voltage ratio.",
        ))

    # Extreme duty
    if duty > 0.95:
        issues.append(ConstraintIssue(
            severity="error",
            code="BOOST_EXTREME_DUTY",
            message=(
                f"Boost duty cycle {duty:.3f} > 0.95. Practically unrealizable "
                f"with real components."
            ),
            parameter="duty",
            actual_value=duty,
            limit_value=0.95,
            suggestion="Use a different topology (e.g., flyback, forward) for this voltage ratio.",
        ))


@_register_check(["boost", "boost_pfc"])
def _check_boost_voltage_ratio(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Boost requires Vout > Vin."""
    vin = _safe_float(requirements.get("vin"))
    vout = _safe_float(requirements.get("vout_target"))
    if vin <= 0 or vout <= 0:
        return

    if vout <= vin:
        issues.append(ConstraintIssue(
            severity="error",
            code="BOOST_VOUT_LEQ_VIN",
            message=f"Boost converter requires Vout ({vout}V) > Vin ({vin}V).",
            parameter="vout_target",
            actual_value=vout,
            limit_value=vin,
            suggestion="Use a buck converter for step-down or verify voltage values.",
        ))


@_register_check(["boost", "boost_pfc"])
def _check_boost_switch_stress(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Boost switch and diode see Vout."""
    vout = _safe_float(requirements.get("vout_target"))
    if vout <= 0:
        return

    # Switch voltage stress = Vout
    if vout > 600:
        issues.append(ConstraintIssue(
            severity="warning",
            code="HIGH_SWITCH_VOLTAGE_STRESS",
            message=(
                f"Switch/diode voltage stress equals Vout = {vout:.1f}V. "
                f"Consider SiC/GaN devices for reliable operation."
            ),
            parameter="vout_target",
            actual_value=vout,
            limit_value=600.0,
            suggestion="Use wide-bandgap devices or a multi-level topology.",
        ))


# ---------------------------------------------------------------------------
# Buck-boost specific checks
# ---------------------------------------------------------------------------

@_register_check(["buck_boost"])
def _check_buck_boost_switch_stress(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Buck-boost switch sees Vin + Vout."""
    vin = _safe_float(requirements.get("vin"))
    vout = _safe_float(requirements.get("vout_target"))
    if vin <= 0 or vout <= 0:
        return

    v_stress = vin + vout
    if v_stress > 600:
        issues.append(ConstraintIssue(
            severity="warning",
            code="HIGH_SWITCH_VOLTAGE_STRESS",
            message=(
                f"Buck-boost switch voltage stress Vin+Vout = {v_stress:.1f}V. "
                f"Select devices rated for this voltage with adequate margin."
            ),
            parameter="switch_voltage_stress",
            actual_value=v_stress,
            limit_value=600.0,
            suggestion="Consider a SEPIC or Cuk topology for lower switch stress.",
        ))


# ---------------------------------------------------------------------------
# Flyback-specific checks
# ---------------------------------------------------------------------------

@_register_check(["flyback"])
def _check_flyback_duty(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Flyback typically operates with D < 0.65."""
    design = _get_design(design_result)
    duty = _safe_float(design.get("duty"))
    if duty <= 0:
        return

    if duty > 0.65:
        issues.append(ConstraintIssue(
            severity="warning",
            code="FLYBACK_HIGH_DUTY",
            message=(
                f"Flyback duty cycle {duty:.3f} > 0.65. "
                f"High duty increases transformer core stress and switch current."
            ),
            parameter="duty",
            actual_value=duty,
            limit_value=0.65,
            suggestion="Increase turns ratio to reduce duty cycle.",
        ))


@_register_check(["flyback"])
def _check_flyback_switch_stress(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Flyback switch sees Vin + Vout*N (reflected voltage)."""
    vin = _safe_float(requirements.get("vin"))
    vout = _safe_float(requirements.get("vout_target"))
    if vin <= 0 or vout <= 0:
        return

    design = _get_design(design_result)
    turns_ratio = _safe_float(design.get("turns_ratio", design.get("n")))
    if turns_ratio <= 0:
        # Estimate: N ≈ Vin * D / (Vout * (1-D))
        duty = _safe_float(design.get("duty"))
        if 0 < duty < 1:
            turns_ratio = (vin * duty) / (vout * (1 - duty))
        else:
            return

    v_reflected = vout * turns_ratio
    v_switch = vin + v_reflected
    # With typical 30% voltage spike margin
    v_switch_peak = v_switch * 1.3

    if v_switch_peak > 600:
        issues.append(ConstraintIssue(
            severity="warning",
            code="FLYBACK_HIGH_SWITCH_STRESS",
            message=(
                f"Flyback switch peak stress ~{v_switch_peak:.0f}V "
                f"(Vin + N*Vout + spike). Consider snubber or clamp circuit."
            ),
            parameter="switch_voltage_stress",
            actual_value=v_switch_peak,
            limit_value=600.0,
            suggestion="Add RCD clamp or active clamp to limit voltage spike.",
        ))


# ---------------------------------------------------------------------------
# Forward-specific checks
# ---------------------------------------------------------------------------

@_register_check(["forward"])
def _check_forward_duty(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Forward converter requires D < 0.5 for core reset."""
    design = _get_design(design_result)
    duty = _safe_float(design.get("duty"))
    if duty <= 0:
        return

    if duty >= 0.5:
        issues.append(ConstraintIssue(
            severity="error",
            code="FORWARD_DUTY_GEQ_HALF",
            message=(
                f"Forward converter duty {duty:.3f} >= 0.5. "
                f"Transformer core cannot reset within the off-time."
            ),
            parameter="duty",
            actual_value=duty,
            limit_value=0.5,
            suggestion="Increase turns ratio or reduce voltage conversion ratio.",
        ))
    elif duty > 0.45:
        issues.append(ConstraintIssue(
            severity="warning",
            code="FORWARD_DUTY_NEAR_LIMIT",
            message=(
                f"Forward converter duty {duty:.3f} is near the 0.5 limit. "
                f"Leaves little margin for transients."
            ),
            parameter="duty",
            actual_value=duty,
            limit_value=0.5,
            suggestion="Target D < 0.45 for adequate reset margin.",
        ))


# ---------------------------------------------------------------------------
# Cuk / SEPIC checks
# ---------------------------------------------------------------------------

@_register_check(["cuk", "sepic"])
def _check_coupling_cap_voltage(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Coupling capacitor in Cuk/SEPIC sees Vin + Vout."""
    vin = _safe_float(requirements.get("vin"))
    vout = _safe_float(requirements.get("vout_target"))
    if vin <= 0 or vout <= 0:
        return

    v_cap = vin + vout
    # Coupling cap voltage stress info
    if v_cap > 400:
        issues.append(ConstraintIssue(
            severity="warning",
            code="HIGH_COUPLING_CAP_VOLTAGE",
            message=(
                f"Coupling capacitor voltage Vin+Vout = {v_cap:.1f}V. "
                f"Ensure capacitor voltage rating is adequate (>= {v_cap * 1.5:.0f}V rated)."
            ),
            parameter="coupling_cap_voltage",
            actual_value=v_cap,
            limit_value=400.0,
            suggestion="Select capacitor with voltage rating >= 1.5x the DC voltage.",
        ))


# ---------------------------------------------------------------------------
# Full-bridge / Half-bridge inverter checks
# ---------------------------------------------------------------------------

@_register_check(["full_bridge", "half_bridge"])
def _check_inverter_dc_link(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Check DC link voltage vs output voltage requirements."""
    vdc = _safe_float(requirements.get("vin", requirements.get("vdc")))
    vout = _safe_float(requirements.get("vout_target", requirements.get("vout_rms")))
    topology = design_result.get("topology", "")

    if vdc <= 0 or vout <= 0:
        return

    if topology == "half_bridge":
        # Half-bridge: max fundamental output = Vdc/2 * 2/pi (square wave)
        # For sinusoidal: Vout_rms_max ≈ Vdc / (2*sqrt(2))
        v_max_rms = vdc / (2 * math.sqrt(2))
    else:
        # Full-bridge: Vout_rms_max ≈ Vdc / sqrt(2)
        v_max_rms = vdc / math.sqrt(2)

    if vout > v_max_rms * 1.1:  # Allow 10% for PWM modulation index > 1
        issues.append(ConstraintIssue(
            severity="warning",
            code="INVERTER_OVERMODULATION",
            message=(
                f"Requested output {vout:.1f}Vrms exceeds linear modulation range "
                f"({v_max_rms:.1f}Vrms max) for {topology}. Overmodulation needed."
            ),
            parameter="vout_rms",
            actual_value=vout,
            limit_value=v_max_rms,
            suggestion="Increase DC link voltage or accept harmonic distortion from overmodulation.",
        ))


# ---------------------------------------------------------------------------
# LLC-specific checks
# ---------------------------------------------------------------------------

@_register_check(["llc"])
def _check_llc_resonant_params(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Validate LLC resonant parameters."""
    design = _get_design(design_result)

    lr = _safe_float(design.get("lr", design.get("Lr")))
    cr = _safe_float(design.get("cr", design.get("Cr")))
    lm = _safe_float(design.get("lm", design.get("Lm")))

    if lr <= 0 or cr <= 0:
        return

    # Resonant frequency
    fr = 1.0 / (2.0 * math.pi * math.sqrt(lr * cr))

    # Check Lm/Lr ratio (typically 3-10)
    if lm > 0:
        ratio = lm / lr
        if ratio < 2:
            issues.append(ConstraintIssue(
                severity="warning",
                code="LLC_LOW_LM_LR_RATIO",
                message=(
                    f"Lm/Lr ratio = {ratio:.2f} is low (<3). "
                    f"Magnetizing current will be high, increasing conduction losses."
                ),
                parameter="lm_lr_ratio",
                actual_value=ratio,
                limit_value=3.0,
                suggestion="Increase Lm or decrease Lr to improve efficiency.",
            ))
        elif ratio > 12:
            issues.append(ConstraintIssue(
                severity="warning",
                code="LLC_HIGH_LM_LR_RATIO",
                message=(
                    f"Lm/Lr ratio = {ratio:.2f} is high (>10). "
                    f"Gain range will be narrow, reducing regulation capability."
                ),
                parameter="lm_lr_ratio",
                actual_value=ratio,
                limit_value=10.0,
                suggestion="Decrease Lm or increase Lr for wider gain range.",
            ))

    # Check resonant frequency vs switching frequency
    fsw = _safe_float(requirements.get("fsw"))
    if fsw <= 0:
        for comp in design_result.get("components", []):
            params = comp.get("parameters", {})
            if "switching_frequency" in params:
                fsw = _safe_float(params["switching_frequency"])
                break

    if fsw > 0 and fr > 0:
        ratio_f = fsw / fr
        if ratio_f < 0.5:
            issues.append(ConstraintIssue(
                severity="error",
                code="LLC_FSW_FAR_BELOW_FR",
                message=(
                    f"Switching frequency {fsw/1e3:.1f}kHz is far below "
                    f"resonant frequency {fr/1e3:.1f}kHz (ratio {ratio_f:.2f}). "
                    f"LLC cannot operate in this region stably."
                ),
                parameter="fsw_fr_ratio",
                actual_value=ratio_f,
                limit_value=0.5,
                suggestion="Increase fsw or adjust Lr/Cr to lower resonant frequency.",
            ))
        elif ratio_f > 2.0:
            issues.append(ConstraintIssue(
                severity="warning",
                code="LLC_FSW_FAR_ABOVE_FR",
                message=(
                    f"Switching frequency {fsw/1e3:.1f}kHz is much higher than "
                    f"resonant frequency {fr/1e3:.1f}kHz (ratio {ratio_f:.2f}). "
                    f"Circulating current and losses increase."
                ),
                parameter="fsw_fr_ratio",
                actual_value=ratio_f,
                limit_value=2.0,
                suggestion="Reduce fsw or increase resonant frequency.",
            ))

    # Quality factor Q
    iout = _safe_float(requirements.get("iout", requirements.get("iout_target", 0)))
    vout = _safe_float(requirements.get("vout_target"))
    if iout > 0 and vout > 0 and fr > 0 and lr > 0:
        r_ac = (8.0 / (math.pi ** 2)) * (vout / iout)  # Equivalent AC resistance
        if r_ac > 0:
            q = (2 * math.pi * fr * lr) / r_ac
            if q > 1.0:
                issues.append(ConstraintIssue(
                    severity="warning",
                    code="LLC_HIGH_Q",
                    message=(
                        f"Quality factor Q = {q:.2f} is high (>1.0). "
                        f"Gain characteristic will be peaky, reducing stability margin."
                    ),
                    parameter="quality_factor",
                    actual_value=q,
                    limit_value=1.0,
                    suggestion="Reduce Lr or increase load resistance to lower Q.",
                ))


# ---------------------------------------------------------------------------
# Bidirectional buck-boost checks
# ---------------------------------------------------------------------------

@_register_check(["bidirectional_buck_boost"])
def _check_bidirectional_overlap(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """Check for shoot-through risk in bidirectional topology."""
    design = _get_design(design_result)
    dead_time = _safe_float(design.get("dead_time"))
    fsw = _safe_float(requirements.get("fsw"))

    if dead_time <= 0 or fsw <= 0:
        return

    period = 1.0 / fsw
    dead_time_ratio = dead_time / period

    if dead_time_ratio < 0.005:
        issues.append(ConstraintIssue(
            severity="warning",
            code="DEAD_TIME_TOO_SHORT",
            message=(
                f"Dead time {dead_time*1e9:.0f}ns is < 0.5% of switching period. "
                f"Risk of shoot-through in half-bridge legs."
            ),
            parameter="dead_time",
            actual_value=dead_time,
            limit_value=period * 0.005,
            suggestion="Increase dead time to at least 1% of switching period.",
        ))


# ---------------------------------------------------------------------------
# Boost PFC checks
# ---------------------------------------------------------------------------

@_register_check(["boost_pfc"])
def _check_pfc_output_voltage(
    requirements: dict,
    design_result: dict,
    issues: list[ConstraintIssue],
) -> None:
    """PFC output must be above peak AC input."""
    vin = _safe_float(requirements.get("vin", requirements.get("vac_rms")))
    vout = _safe_float(requirements.get("vout_target"))

    if vin <= 0 or vout <= 0:
        return

    # vin could be RMS; peak = vin * sqrt(2)
    # If vin > 50, it's likely an AC RMS value
    v_peak = vin * math.sqrt(2) if vin > 50 else vin

    if vout < v_peak * 1.05:
        issues.append(ConstraintIssue(
            severity="error",
            code="PFC_VOUT_TOO_LOW",
            message=(
                f"PFC output {vout:.1f}V must be above peak input "
                f"{v_peak:.1f}V (with margin) for boost operation."
            ),
            parameter="vout_target",
            actual_value=vout,
            limit_value=v_peak * 1.05,
            suggestion=f"Set Vout >= {v_peak * 1.1:.0f}V for reliable PFC operation.",
        ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_design_constraints(
    topology: str,
    requirements: dict,
    design_result: dict,
) -> ConstraintResult:
    """Validate generated design against electrical feasibility constraints.

    Args:
        topology: Topology name (e.g. "buck", "flyback")
        requirements: Original user requirements
        design_result: The full result from generator.generate()

    Returns:
        ConstraintResult with feasibility assessment and issues
    """
    issues: list[ConstraintIssue] = []

    # Run wildcard checks (apply to all topologies)
    for check_fn in _TOPOLOGY_CHECKS.get("*", []):
        try:
            check_fn(requirements, design_result, issues)
        except Exception:
            pass  # Don't let a check failure block others

    # Run topology-specific checks
    topo_lower = topology.lower()
    for check_fn in _TOPOLOGY_CHECKS.get(topo_lower, []):
        try:
            check_fn(requirements, design_result, issues)
        except Exception:
            pass

    has_errors = any(i.severity == "error" for i in issues)

    return ConstraintResult(
        is_feasible=not has_errors,
        issues=issues,
    )
