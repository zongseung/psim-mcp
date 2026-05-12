"""Buck (step-down) converter topology generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class BuckGenerator(TopologyGenerator):
    """Generate a buck converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "buck"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return [
            "iout", "fsw", "ripple_ratio", "voltage_ripple_ratio",
            "closed_loop",
            # Custom C-block CONTENT — the caller (typically an LLM)
            # writes the PI / MPC / 데드비트 controller source as a
            # string and we route it to PSIM's SIMPLECBLOCK via
            # ``c_block_overrides``. Active only on the closed-loop
            # template path (``examples\C Block\buck converter -
            # digital control - C block.psimsch``).
            "c_code",
            "c_block_name",
        ]

    def synthesize(self, requirements: dict) -> CircuitGraph:
        """Synthesize a CircuitGraph (no positions) from requirements."""
        from psim_mcp.synthesis.topologies.buck import synthesize_buck

        return synthesize_buck(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        iout: float = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
        fsw: float = float(requirements.get("fsw", 50_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))
        closed_loop: bool = bool(requirements.get("closed_loop", False))

        duty = vout / vin
        delta_i = ripple_ratio * iout
        inductance = vout * (1 - duty) / (fsw * delta_i) if delta_i else 1e-3
        capacitance = delta_i / (8 * fsw * vripple_ratio * vout) if vout else 100e-6
        r_load = vout / iout if iout else 10.0

        # Closed-loop branch routes through PSIM's stock C-block digital
        # buck reference. The reference schematic has a SIMPLECBLOCK
        # PI compensator (SSCB7) whose CONTENT we replace with the
        # LLM-supplied ``c_code`` — so the user's hand-written
        # controller actually drives the simulation, not the chassis's
        # built-in PI.
        if closed_loop:
            return self._build_closed_loop_template_result(
                vin=vin, vout=vout, iout=iout, fsw=fsw, duty=duty,
                inductance=inductance, capacitance=capacitance, r_load=r_load,
                c_code=requirements.get("c_code"),
                c_block_name=requirements.get("c_block_name"),
            )

        # Layout:
        # VDC(120,100)-(120,150) -> MOSFET drain(150,100) source(200,100) gate(180,120) DIR=270
        # GATING(180,170) -> wire to gate
        # DIODE anode(220,150) cathode(220,100) DIR=270
        # L(250,100)-(300,100) -> C(300,100)-(300,150) -> R(350,100)-(350,150)
        # GND bus at y=150
        components = [
            {
                "id": "V1", "type": "DC_Source",
                "parameters": {"voltage": vin},
                "position": {"x": 120, "y": 100}, "direction": 0,
                "ports": [120, 100, 120, 150],
            },
            {
                "id": "GND1", "type": "Ground",
                "parameters": {},
                "position": {"x": 120, "y": 150}, "direction": 0,
                "ports": [120, 150],
            },
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 150, "y": 100}, "direction": 270,
                "ports": [150, 100, 200, 100, 180, 120],
            },
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {
                    "Frequency": fsw,
                    "NoOfPoints": 2,
                    "Switching_Points": f" 0 {int(duty * 360)}.",
                },
                "position": {"x": 180, "y": 170}, "direction": 0,
                "ports": [180, 170],
            },
            {
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 220, "y": 150}, "direction": 270,
                "ports": [220, 150, 220, 100],
            },
            {
                "id": "L1", "type": "Inductor",
                "parameters": {"inductance": round(inductance, 9), "CurrentFlag": 1},
                "position": {"x": 250, "y": 100},
                "position2": {"x": 300, "y": 100},
                "direction": 0,
                "ports": [250, 100, 300, 100],
            },
            {
                "id": "C1", "type": "Capacitor",
                "parameters": {"capacitance": round(capacitance, 9)},
                "position": {"x": 300, "y": 100},
                "position2": {"x": 300, "y": 150},
                "direction": 90,
                "ports": [300, 100, 300, 150],
            },
            {
                # Named "Vout" so PSIM records V(Vout) matching topology_metrics
                "id": "Vout", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 350, "y": 100},
                "position2": {"x": 350, "y": 150},
                "direction": 90,
                "ports": [350, 100, 350, 150],
            },
        ]

        # Nets (canonical format: name + pins)
        nets = [
            {"name": "net_vin_sw", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_sw_junc", "pins": ["SW1.source", "D1.cathode", "L1.pin1"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_out", "pins": ["L1.pin2", "C1.positive", "Vout.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "D1.anode", "C1.negative", "Vout.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Buck Converter",
                "description": (
                    f"Buck DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "inductance": round(inductance, 9),
                    "capacitance": round(capacitance, 9),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 100), 9),
                "total_time": round(50 / fsw, 6),
            },
        }

    # ------------------------------------------------------------------
    # Closed-loop via PSIM digital-control C-block reference.
    # ------------------------------------------------------------------
    def _build_closed_loop_template_result(
        self, *,
        vin: float, vout: float, iout: float, fsw: float,
        duty: float, inductance: float, capacitance: float, r_load: float,
        c_code: str | None = None,
        c_block_name: str | None = None,
    ) -> dict:
        """Hand off closed-loop buck to PSIM's stock C-block digital
        reference and (optionally) overlay the caller's PI / MPC C code.

        The reference schematic ``examples\\C Block\\buck converter -
        digital control - C block.psimsch`` already wires:

        * Power stage: VDC1 → Q1/Q2 (MOSFET pair) → L1 → C1 → RLoad
        * Sensing: VSEN on output, current sense on inductor
        * Control: SSCB7 = PI compensator (the SIMPLECBLOCK we override),
          SSCB5 = digital PWM, SSCB6 = ADC sampler

        Only the PI compensator's CONTENT is swapped — sensing, PWM and
        sampling stay PSIM-validated. So an LLM-written ``c_code`` only
        needs to read ``x1`` (reference) / ``x2`` (feedback) / ``x3..x8``
        (Kp/Ti/Fsamp/limits/start signal) and write ``y1`` (duty word)
        / ``y2`` (integrator state).
        """
        po = vout * iout

        psim_template = {
            "source": (
                r"examples\C Block"
                r"\buck converter - digital control - C block.psimsch"
            ),
            # The stock chassis stores parameters inline (not in a sidecar
            # .txt) so no ``sidecar_files`` are needed. We override the
            # input voltage and load resistance directly on the elements
            # so the simulation reflects the caller's Vin/Vout/Iout.
            "sidecar_files": [],
            "parameter_overrides": [
                # Input voltage source
                {"type": "VDC", "name": "VDC1",
                 "param": "Amplitude", "value": f"{vin:g}"},
                # Output load — sized so V_o / I_o gives the requested
                # operating point under stock duty cycle. The PI loop
                # in SSCB7 will trim duty cycle to converge on Vo.
                {"type": "MULTI_RESISTOR", "name": "RLoad",
                 "param": "Resistance", "value": f"{r_load:g}"},
                # Cap initial voltage close to target so startup
                # transient is short (avoids long settling time).
                {"type": "MULTI_CAPACITOR", "name": "C1",
                 "param": "Init__Cap__Voltage", "value": f"{vout:g}"},
                # IL_ref source — chassis VDC T_step5 (stock=2800 counts).
                # NOTE: empirically PsimSetElmValue2-ing this parameter
                # destabilises the chassis even when the value matches
                # the stock 2800 byte-for-byte (Vo diverges to 91 V at
                # what should be a no-op write). Suspected cause:
                # touching a chassis param triggers PSIM to invalidate
                # an internal sample-rate / compile cache and the
                # chassis's tightly-tuned digital control loop falls
                # out of sync.
                #
                # For now we leave T_step5 untouched. Consequence:
                # ``iout`` only affects RLoad sizing, not the current
                # reference — so the chassis stays at its native ~3.6 A
                # target regardless of the user's iout. Real retargeting
                # of iout requires either a custom chassis (no PsimSet
                # quirk) or finding which other element actually owns
                # the reference signal.
                # {"type": "VDC", "name": "T_step5",
                #  "param": "Amplitude",
                #  "value": f"{iout * (2800 / 3.6):.0f}"},
            ],
        }

        # Optional caller-supplied C-block CONTENT. Default target is
        # SSCB7 — the PI compensator in this chassis (per
        # output/converted_cblock_buck.py:328). The caller can point at
        # a different SIMPLECBLOCK via ``c_block_name`` if they want to
        # override the PWM (SSCB5) or ADC (SSCB6) instead.
        if c_code:
            psim_template["c_block_overrides"] = [
                {"name": c_block_name or "SSCB7", "code": c_code},
            ]

        design_info = {
            "duty": round(duty, 6),
            "inductance": round(inductance, 9),
            "capacitance": round(capacitance, 9),
            "r_load": round(r_load, 4),
            "po_rating": round(po, 4),
            "control_mode": "closed_loop_psim_cblock_reference",
            "template_source": psim_template["source"],
            "c_block_overrides": (
                [ov["name"] for ov in psim_template.get("c_block_overrides", [])]
                or None
            ),
        }

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Buck Converter (closed-loop digital reference)",
                "description": (
                    f"Buck DC-DC converter (PSIM C-block reference, "
                    f"closed-loop): {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}"
                ),
                "design": design_info,
            },
            "components": [],
            "nets": [],
            "psim_template": psim_template,
            "simulation": {
                # Chassis sets its own SimControl (5 ns step, 5 ms total)
                # which is tuned for the 200 kHz digital PWM in SSCB5.
                # Leave it alone — overriding here de-tunes the loop.
            },
        }
