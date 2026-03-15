"""CircuitSpec Pydantic model — canonical representation of a PSIM circuit."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class Position(BaseModel):
    """X/Y coordinate on the schematic canvas."""

    x: int = 0
    y: int = 0


class CircuitMetadata(BaseModel):
    """Descriptive metadata for a circuit design."""

    name: str
    version: str = "1.0"
    description: str = ""
    category: str = ""


class CircuitRequirements(BaseModel):
    """Electrical requirements / design targets."""

    vin: float | None = None
    vout_target: float | None = None
    iout_target: float | None = None
    switching_frequency: float | None = None
    power_rating: float | None = None


class ComponentSpec(BaseModel):
    """A single component in the circuit."""

    id: str
    kind: str  # internal standard name, maps to component_library
    params: dict[str, float | int | str] = {}
    position: Position | None = None


class NetSpec(BaseModel):
    """A named net connecting multiple pins together."""

    name: str
    pins: list[str]  # e.g. ["V1.positive", "SW1.drain"]


class SimulationSettings(BaseModel):
    """Transient simulation configuration."""

    time_step: float = 1e-5
    total_time: float = 0.1
    print_step: float | None = None


# ---------------------------------------------------------------------------
# Top-level model
# ---------------------------------------------------------------------------


class CircuitSpec(BaseModel):
    """Full specification of a PSIM circuit."""

    topology: str
    metadata: CircuitMetadata
    requirements: CircuitRequirements = Field(default_factory=CircuitRequirements)
    components: list[ComponentSpec]
    nets: list[NetSpec]
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)

    # -- conversion helpers --------------------------------------------------

    @classmethod
    def from_legacy(cls, data: dict) -> CircuitSpec:
        """Convert the legacy dict format into a *CircuitSpec*.

        Legacy format example::

            {
                "topology": "buck",
                "components": [
                    {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48},
                     "position": {"x": 0, "y": 0}},
                    ...
                ],
                "connections": [
                    {"from": "V1.positive", "to": "SW1.drain"},
                    ...
                ]
            }
        """
        topology = data.get("topology", "unknown")

        # -- components ------------------------------------------------------
        components: list[ComponentSpec] = []
        for comp in data.get("components", []):
            kind = comp.get("type", comp.get("kind", "unknown"))
            kind_normalised = kind.lower()
            pos = comp.get("position")
            position = Position(**pos) if pos else None
            components.append(
                ComponentSpec(
                    id=comp["id"],
                    kind=kind_normalised,
                    params=comp.get("parameters", comp.get("params", {})),
                    position=position,
                )
            )

        # -- connections  → nets ---------------------------------------------
        # Group pins by using Union-Find so that transitive connections share
        # a single net.
        parent: dict[str, str] = {}

        def find(pin: str) -> str:
            while parent.get(pin, pin) != pin:
                parent[pin] = parent[parent[pin]]
                pin = parent[pin]
            return pin

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for conn in data.get("connections", []):
            pin_from = conn["from"]
            pin_to = conn["to"]
            parent.setdefault(pin_from, pin_from)
            parent.setdefault(pin_to, pin_to)
            union(pin_from, pin_to)

        groups: dict[str, list[str]] = defaultdict(list)
        for pin in parent:
            groups[find(pin)].append(pin)

        nets: list[NetSpec] = []
        for idx, (_root, pins) in enumerate(sorted(groups.items())):
            nets.append(NetSpec(name=f"net_{idx}", pins=sorted(pins)))

        # -- metadata --------------------------------------------------------
        metadata = data.get("metadata")
        if metadata:
            meta = CircuitMetadata(**metadata)
        else:
            meta = CircuitMetadata(name=topology)

        # -- requirements & simulation ---------------------------------------
        requirements = CircuitRequirements(**data["requirements"]) if "requirements" in data else CircuitRequirements()
        sim_data = data.get("simulation", {})
        simulation = SimulationSettings(**sim_data) if sim_data else SimulationSettings()

        return cls(
            topology=topology,
            metadata=meta,
            requirements=requirements,
            components=components,
            nets=nets,
            simulation=simulation,
        )

    def to_legacy(self) -> dict:
        """Convert back to the legacy dict format for backward compatibility."""
        components: list[dict] = []
        for comp in self.components:
            entry: dict = {
                "id": comp.id,
                "type": _kind_to_legacy_type(comp.kind),
                "parameters": dict(comp.params),
            }
            if comp.position is not None:
                entry["position"] = {"x": comp.position.x, "y": comp.position.y}
            components.append(entry)

        # Convert nets back to point-to-point connections.
        connections: list[dict] = []
        for net in self.nets:
            if len(net.pins) < 2:
                continue
            anchor = net.pins[0]
            for pin in net.pins[1:]:
                connections.append({"from": anchor, "to": pin})

        result: dict = {
            "topology": self.topology,
            "components": components,
            "connections": connections,
        }
        return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Map of lowercase kind → canonical legacy type name
_LEGACY_TYPE_MAP: dict[str, str] = {
    "dc_source": "DC_Source",
    "ac_source": "AC_Source",
    "dc_current_source": "DC_Current_Source",
    "ac_current_source": "AC_Current_Source",
    "mosfet": "MOSFET",
    "igbt": "IGBT",
    "thyristor": "Thyristor",
    "triac": "TRIAC",
    "gto": "GTO",
    "ideal_switch": "Ideal_Switch",
    "diode": "Diode",
    "zener_diode": "Zener_Diode",
    "schottky_diode": "Schottky_Diode",
    "resistor": "Resistor",
    "inductor": "Inductor",
    "capacitor": "Capacitor",
    "coupled_inductor": "Coupled_Inductor",
    "pv_panel": "PV_Panel",
    "transformer": "Transformer",
    "three_phase_transformer": "Three_Phase_Transformer",
    "center_tap_transformer": "Center_Tap_Transformer",
    "dc_motor": "DC_Motor",
    "induction_motor": "Induction_Motor",
    "pmsm": "PMSM",
    "bldc_motor": "BLDC_Motor",
    "srm": "SRM",
    "voltage_probe": "Voltage_Probe",
    "current_probe": "Current_Probe",
    "l_filter": "L_Filter",
    "lc_filter": "LC_Filter",
    "lcl_filter": "LCL_Filter",
    "emi_filter": "EMI_Filter",
    "pi_controller": "PI_Controller",
    "pid_controller": "PID_Controller",
    "pwm_generator": "PWM_Generator",
    "pll": "PLL",
    "battery": "Battery",
    "supercapacitor": "Supercapacitor",
    "heatsink": "Heatsink",
}


def _kind_to_legacy_type(kind: str) -> str:
    """Convert a lowercase *kind* back to the original PascalCase type name."""
    return _LEGACY_TYPE_MAP.get(kind.lower(), kind)
