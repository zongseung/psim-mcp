"""Boost (step-up) converter topology generator."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class BoostGenerator(TopologyGenerator):
    """Generate a boost converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "boost"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return [
            "iout",
            "fsw",
            "ripple_ratio",
            "voltage_ripple_ratio",
            "closed_loop",
            "pi_gain",
            "pi_time_constant",
        ]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.boost import synthesize_boost
        return synthesize_boost(requirements)

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

        duty = 1 - vin / vout if vout else 0.5
        iin = iout / (1 - duty) if duty < 1 else iout
        delta_i = ripple_ratio * iin
        inductance = vin * duty / (fsw * delta_i) if delta_i else 1e-3
        capacitance = iout * duty / (fsw * vripple_ratio * vout) if vout else 100e-6
        r_load = vout / iout if iout else 10.0

        # Layout reference grid (x in [80,350] for the power stage,
        # GND bus at y=150, gate at y=130):
        # V1(80,100)-(80,150) -> L1(120,100)-(170,100) -> SW1.drain(200,100)
        # SW1: drain(200,100), source(200,150), gate(180,130)
        # D1(220,100)-(270,100) -> C1(300,100)-(300,150) -> Vout(350,100)-(350,150)
        power_components = [
            {
                "id": "V1", "type": "DC_Source",
                "parameters": {"voltage": vin},
                "position": {"x": 80, "y": 100}, "direction": 0,
                "ports": [80, 100, 80, 150],
            },
            {
                "id": "GND1", "type": "Ground",
                "parameters": {},
                "position": {"x": 80, "y": 150}, "direction": 0,
                "ports": [80, 150],
            },
            {
                "id": "L1", "type": "Inductor",
                "parameters": {"inductance": round(inductance, 9)},
                "position": {"x": 120, "y": 100},
                "position2": {"x": 170, "y": 100},
                "direction": 0,
                "ports": [120, 100, 170, 100],
            },
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 100}, "direction": 0,
                "ports": [200, 100, 200, 150, 180, 130],
            },
            {
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 220, "y": 100}, "direction": 0,
                "ports": [220, 100, 270, 100],
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
                "id": "Vout", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 350, "y": 100},
                "position2": {"x": 350, "y": 150},
                "direction": 90,
                "ports": [350, 100, 350, 150],
            },
        ]

        power_nets = [
            {"name": "net_vin_l", "pins": ["V1.positive", "L1.pin1"]},
            {"name": "net_l_sw_d", "pins": ["L1.pin2", "SW1.drain", "D1.anode"]},
            {"name": "net_d_out", "pins": ["D1.cathode", "C1.positive", "Vout.pin1"]},
        ]
        gnd_pins = [
            "V1.negative", "GND1.pin1", "SW1.source",
            "C1.negative", "Vout.pin2",
        ]

        if closed_loop:
            # Closed-loop routes through PSIM's stock peak-current-mode
            # boost reference (Power Supply Design Suite) rather than
            # synthesising a controller from discrete elements. This
            # sidesteps PSIM 2026's coincident-pin merging quirks that
            # broke the previous VSEN→SUM2→PI→COMP→VTRI chain and the
            # SIMPLECBLOCK→ONCTRL variant — the reference schematic is
            # validated by Altair so the only knobs we turn are Vin /
            # Vo / Po / fsw in the companion parameters file.
            return self._build_closed_loop_template_result(
                vin=vin, vout=vout, iout=iout, fsw=fsw,
                duty=duty, inductance=inductance,
                capacitance=capacitance, r_load=r_load,
            )

        (
            control_components,
            control_nets,
            control_wire_segments,
            gnd_extra,
            control_meta,
        ) = self._build_open_loop_gate(fsw=fsw, duty=duty)

        gnd_pins.extend(gnd_extra)
        power_nets.append({"name": "net_gnd", "pins": gnd_pins})

        components = power_components + control_components
        nets = power_nets + control_nets

        design_info = {
            "duty": round(duty, 6),
            "inductance": round(inductance, 9),
            "capacitance": round(capacitance, 9),
            "r_load": round(r_load, 4),
        }
        design_info.update(control_meta)

        mode_label = "closed-loop PI" if closed_loop else "open-loop"
        result = {
            "topology": self.topology_name,
            "metadata": {
                "name": "Boost Converter",
                "description": (
                    f"Boost DC-DC converter ({mode_label}): {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw / 1e3:.1f}kHz, D={duty:.3f}"
                ),
                "design": design_info,
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round((400 if closed_loop else 50) / fsw, 6),
            },
        }
        if control_wire_segments:
            result["wire_segments"] = control_wire_segments
        return result

    # ------------------------------------------------------------------
    # Closed-loop via PSIM stock template.
    # ------------------------------------------------------------------
    def _build_closed_loop_template_result(
        self, *,
        vin: float, vout: float, iout: float, fsw: float,
        duty: float, inductance: float, capacitance: float, r_load: float,
    ) -> dict:
        """Hand off closed-loop boost to Altair's validated reference
        schematic by emitting a ``psim_template`` directive.

        The MCP bridge picks up ``psim_template`` in
        ``handle_create_circuit`` and routes to
        ``_handle_template_circuit``, which (1) copies the reference
        .psimsch, (2) copies the ``parameters-main.txt`` sidecar, and
        (3) rewrites the text macros for Vin / Vo / Po. PSIM resolves
        the symbolic L / C / fsw / controller parameters from that
        file at simulation time, so we never touch the schematic
        electrically — sidestepping the SIMPLECBLOCK/ONCTRL node-
        merging quirk that defeated the inline closed-loop generator.
        """
        po = vout * iout

        psim_template = {
            "source": (
                r"examples\Power Supply Design Suite\Boost converter"
                r"\Boost converter with peak current mode control.psimsch"
            ),
            "sidecar_files": ["parameters-main.txt"],
            "parameter_overrides": [],
            "parameter_file_overrides": [
                # Stock defaults are Vin=5, Vo=12, Po=200. The macros
                # below are matched verbatim against the file text;
                # whitespace and trailing comments must mirror the
                # source EXACTLY for the substitution to land.
                {"file": "parameters-main.txt",
                 "find": "Vin = 5;", "replace": f"Vin = {vin:g};"},
                {"file": "parameters-main.txt",
                 "find": "Vin_rated = 5;",
                 "replace": f"Vin_rated = {vin:g};"},
                {"file": "parameters-main.txt",
                 "find": "Vin_min = 4;",
                 "replace": f"Vin_min = {vin * 0.8:g};"},
                {"file": "parameters-main.txt",
                 "find": "Vin_max = 6;",
                 "replace": f"Vin_max = {vin * 1.2:g};"},
                {"file": "parameters-main.txt",
                 "find": "Vo = 12;", "replace": f"Vo = {vout:g};"},
                {"file": "parameters-main.txt",
                 "find": "Po = 200;", "replace": f"Po = {po:g};"},
            ],
        }

        design_info = {
            "duty": round(duty, 6),
            "inductance": round(inductance, 9),
            "capacitance": round(capacitance, 9),
            "r_load": round(r_load, 4),
            "po_rating": round(po, 4),
            "control_mode": "closed_loop_psim_reference",
            "template_source": psim_template["source"],
        }

        # No inline components/nets — the schematic body is delivered
        # by the PSIM template path. Downstream callers must look at
        # ``psim_template`` and route to the bridge's template handler.
        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Boost Converter (closed-loop reference)",
                "description": (
                    f"Boost DC-DC converter (PSIM reference, closed-loop): "
                    f"{vin}V -> {vout}V @ {iout}A, fsw={fsw / 1e3:.1f}kHz, "
                    f"D={duty:.3f}"
                ),
                "design": design_info,
            },
            "components": [],
            "nets": [],
            "psim_template": psim_template,
            "simulation": {
                # Reference example sets its own SimControl values
                # (fsw=200 kHz, total_time≈10 ms) so we leave them
                # untouched; explicit settings would override the
                # parameters file's choices and de-tune the loop.
            },
        }

    # ------------------------------------------------------------------
    # Open-loop gate drive (legacy default).
    # ------------------------------------------------------------------
    def _build_open_loop_gate(self, *, fsw: float, duty: float):
        # GATING placed at the same y as the gate so the gate wire is
        # horizontal at y=130 — never crosses the GND bus at y=150.
        components = [
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {
                    "Frequency": fsw,
                    "NoOfPoints": 2,
                    "Switching_Points": f" 0 {int(duty * 360)}.",
                },
                "position": {"x": 150, "y": 130}, "direction": 0,
                "ports": [150, 130],
            },
        ]
        nets = [
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
        ]
        return components, nets, [], [], {}

    # ------------------------------------------------------------------
    # Closed-loop PI voltage-mode control (single SIMPLECBLOCK).
    # ------------------------------------------------------------------
    def _build_closed_loop_control(
        self,
        *,
        vout: float, fsw: float, duty: float,
        inductance: float, capacitance: float, r_load: float,
        pi_gain_override, pi_time_constant_override,
    ):
        # Voltage-mode Type-II PI tuning (research_boost_closed_loop_2026-05-11.md).
        kp, ti = self._compute_pi_tuning(
            vout=vout, fsw=fsw, duty=duty,
            inductance=inductance, capacitance=capacitance, r_load=r_load,
        )
        if pi_gain_override is not None:
            kp = float(pi_gain_override)
        if pi_time_constant_override is not None:
            ti = float(pi_time_constant_override)
        vsen_gain = 1.0 / vout if vout > 0 else 1.0
        ki = (kp / ti) if ti > 0 else 0.0

        # Single PSIM SIMPLECBLOCK replaces the discrete VSEN→SUM2→PI→
        # COMP→VTRI→CONSTANT chain. The compiled C function runs every
        # simulation step, integrates the error, and emits a PWM gate
        # signal directly — no inter-element wiring guesswork is needed
        # (which is what made the discrete chain so fragile to PSIM's
        # coincident-pin merging behaviour).
        #
        # Layout:
        #   - VSEN1 still measures Vout at the load node (x=380)
        #   - Vref CONSTANT at (10, 200) provides the normalized reference
        #   - C_Block sits below the GND rail at y∈[190,230]
        #     · inputs: in1=(40,200)=Vref, in2=(40,220)=Vsense
        #     · output: out1=(120,200) → wired up to SW1.gate (180,130)
        # Empty CONTENT to isolate: does the SIMPLECBLOCK element work
        # at all in our pipeline, or is there a structural issue?
        c_code = ""

        # Control-side element creation order MIRRORS the PSIM reference
        # (output/converted_cblock_buck.py): LABELs first → ONCTRL →
        # power-side elements (CONSTANT, VSEN) → SIMPLECBLOCK last.
        # Empirically the SIMPLECBLOCK output node is bound to coincident
        # pins ONLY for pins that already exist when the block is
        # created. If CTRL1 is created before ONCTL1, the ONCTL1.input
        # pin is added to a coord that PSIM has already "claimed" as
        # the SIMPLECBLOCK output, and the two never merge — leading
        # to the persistent "ONCTRL input floating" sim-time error.
        components = [
            {
                "id": "LBL_GATE_OUT", "type": "Label",
                "name": "GATE_DRV",
                "parameters": {},
                "position": {"x": 150, "y": 200}, "direction": 0,
                "ports": [150, 200],
            },
            {
                "id": "LBL_GATE_IN", "type": "Label",
                "name": "GATE_DRV",
                "parameters": {},
                "position": {"x": 180, "y": 130}, "direction": 180,
                "ports": [180, 130],
            },
            {
                # ONCTRL with DIRECTION=90 keeps the pins on the LEFT
                # and RIGHT edges (horizontal layout). Input pin
                # coincident with C_Block.out1 at (120, 200) — same
                # convention as output/converted_cblock_buck.py:303
                # where ON3.input shares coords with SSCB5.output #1.
                "id": "ONCTL1", "type": "OnCtrl",
                "parameters": {},
                "position": {"x": 135, "y": 200}, "direction": 90,
                "ports": [120, 200, 150, 200],
            },
            {
                "id": "Vref", "type": "CONSTANT",
                "parameters": {"Amplitude": 1.0},
                "position": {"x": 10, "y": 200}, "direction": 0,
                "ports": [10, 200],
            },
            {
                # PSIM's VSEN is a rigid 50×20 symbol whose pin spacing
                # is enforced internally: positive on the LEFT edge at
                # y0, negative on the LEFT edge at y0+20, output on the
                # RIGHT edge (50px away) at y0+10. Any other PORTS
                # layout gets silently rewritten to this form, so we
                # emit the exact geometry the element expects.
                "id": "VSEN1", "type": "VSEN",
                "parameters": {"Gain": round(vsen_gain, 9)},
                "position": {"x": 380, "y": 110}, "direction": 0,
                "ports": [380, 100, 380, 120, 430, 110],
            },
            {
                # SIMPLECBLOCK comes LAST so its output node is tied
                # to existing pins (ONCTL1.input) at the same coord.
                "id": "CTRL1", "type": "C_Block",
                "parameters": {
                    "c_code": c_code,
                    "input_count": 2,
                    "output_count": 1,
                },
                "position": {"x": 80, "y": 210}, "direction": 0,
                "ports": [40, 200, 40, 220, 120, 200],
            },
        ]

        nets = [
            # Power-side: VSEN samples the load node, shares the global GND.
            {"name": "net_vsen_high", "pins": ["VSEN1.positive", "Vout.pin1"]},
            # Control-side: Vref feeds C_Block input 1; VSEN1 output feeds
            # input 2; the block drives the MOSFET gate directly.
            {"name": "net_vref_in", "pins": ["Vref.output", "CTRL1.in1"]},
        ]

        # Wires that the bridge cannot derive from straight pin-chaining.
        # The gate signal is routed via matching LABEL elements rather
        # than a physical wire, so the only long-haul control wire here
        # is VSEN1.output → CTRL1.in2.
        wire_segments = [
            # VSEN1.output (430,110) → CTRL1.in2 (40,220). Route right
            # then down past y=220, then horizontally back to x=40.
            # x=430 sits to the right of every power pin (max x is
            # Vout at 350) so the vertical leg crosses nothing; the
            # horizontal leg at y=220 sits 70 px below the GND rail.
            {"x1": 430, "y1": 110, "x2": 430, "y2": 220},
            {"x1": 430, "y1": 220, "x2": 40, "y2": 220},
        ]

        # VSEN1.negative joins the GND chain so the bridge's auto-router
        # extends the rail to the sensor's lower terminal at (380,120).
        # A bare wire from (380,120) down to (380,150) is NOT enough —
        # the GND rail itself ends at Vout.pin2 (350,150), so an isolated
        # stub at x=380 would leave the sensor's negative floating.
        gnd_extra = ["VSEN1.negative"]

        meta = {
            "control_mode": "closed_loop_cblock_pi",
            "pi_gain": round(kp, 9),
            "pi_time_constant": round(ti, 9),
            "ki": round(ki, 9),
            "vsen_gain": round(vsen_gain, 9),
        }
        return components, nets, wire_segments, gnd_extra, meta

    @staticmethod
    def _compute_pi_tuning(
        *,
        vout: float, fsw: float, duty: float,
        inductance: float, capacitance: float, r_load: float,
    ) -> tuple[float, float]:
        if not (vout > 0 and inductance > 0 and capacitance > 0 and r_load > 0):
            return 0.001, 1e-3

        one_minus_d = max(1.0 - duty, 1e-3)
        fz_rhp = (one_minus_d ** 2) * r_load / (2 * math.pi * inductance)
        fp_lc = one_minus_d / (2 * math.pi * math.sqrt(inductance * capacitance))
        fc = min(fz_rhp / 5.0, fsw / 10.0)
        fc = max(min(fc, fsw / 5.0), 10.0)

        ti = 1.0 / (2 * math.pi * fp_lc) if fp_lc > 0 else 1e-3
        kp = (2 * math.pi * fc * inductance * (one_minus_d ** 2)) / vout

        kp = max(min(kp, 10.0), 1e-6)
        ti = max(min(ti, 1.0), 1e-6)
        return kp, ti
