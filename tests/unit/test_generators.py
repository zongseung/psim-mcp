"""Tests for topology generators."""
from psim_mcp.generators import get_generator, list_generators
from psim_mcp.generators.layout import make_mosfet_h
import pytest
from psim_mcp.validators import validate_circuit


def _nets_to_connections(nets: list[dict]) -> list[dict]:
    connections = []
    for net in nets:
        pins = net.get("pins", [])
        for i in range(len(pins) - 1):
            connections.append({"from": pins[i], "to": pins[i + 1]})
    return connections


def test_list_generators():
    gens = list_generators()
    assert "buck" in gens
    assert "boost" in gens
    assert "buck_boost" in gens


def test_get_generator():
    gen = get_generator("buck")
    assert gen is not None
    assert gen.topology_name == "buck"


def test_get_generator_unknown():
    with pytest.raises(KeyError, match="nonexistent"):
        get_generator("nonexistent")


def test_buck_generator_required_fields():
    gen = get_generator("buck")
    assert "vin" in gen.required_fields
    assert "vout_target" in gen.required_fields


def test_buck_generator_missing_fields():
    gen = get_generator("buck")
    missing = gen.missing_fields({"vin": 48})
    assert "vout_target" in missing


def test_buck_generator_generate():
    gen = get_generator("buck")
    result = gen.generate({
        "vin": 48.0,
        "vout_target": 12.0,
        "iout": 5.0,
        "fsw": 50000,
    })
    assert result["topology"] == "buck"
    assert len(result["components"]) > 0
    assert len(result["nets"]) > 0
    # Check that inductor value is reasonable
    inductor = next(c for c in result["components"] if c.get("type") == "Inductor")
    params = inductor.get("parameters", {})
    L = params.get("inductance", 0)
    assert 1e-7 < L < 1e-2  # reasonable inductance range


def test_boost_generator_generate():
    gen = get_generator("boost")
    result = gen.generate({
        "vin": 12.0,
        "vout_target": 48.0,
        "iout": 2.0,
        "fsw": 100000,
    })
    assert result["topology"] == "boost"
    assert len(result["components"]) > 0


def test_llc_generator_exposes_psim_native_reference_contract():
    gen = get_generator("llc")
    result = gen.generate({
        "vin": 400.0,
        "vout_target": 48.0,
        "power": 1000.0,
        "fsw": 100000,
    })

    design = result["metadata"]["design"]
    native_ref = result["metadata"]["psim_native_reference"]

    assert result["topology"] == "llc"
    assert design["np_turns"] > 1
    assert design["ns_turns"] == 1
    assert native_ref["source"] == "output/converted_ResonantLLC_CurrentAndVoltageLoop.py"
    assert native_ref["transformer"]["element_type"] == "TF_IDEAL"
    assert native_ref["transformer"]["parameter_names"] == {
        "np_turns": "Np__primary_",
        "ns_turns": "Ns__secondary_",
    }


@pytest.mark.parametrize(
    ("topology", "requirements"),
    [
        ("buck", {"vin": 48.0, "vout_target": 12.0}),
        ("boost", {"vin": 12.0, "vout_target": 48.0}),
        ("buck_boost", {"vin": 24.0, "vout_target": 12.0}),
    ],
)
def test_generated_circuits_validate(topology: str, requirements: dict):
    gen = get_generator(topology)
    result = gen.generate(requirements)
    validation = validate_circuit(
        {
            "components": result["components"],
            "connections": _nets_to_connections(result["nets"]),
            "nets": result["nets"],
        }
    )
    assert validation.is_valid is True, [
        (issue.code, issue.message) for issue in validation.errors
    ]


def test_forward_generator_generate():
    gen = get_generator("forward")
    result = gen.generate({
        "vin": 48.0,
        "vout_target": 12.0,
        "iout": 2.0,
        "fsw": 100000,
    })
    assert result["topology"] == "forward"
    components = result["components"]
    nets = result["nets"]
    design = result["metadata"]["design"]

    # Design sanity checks
    assert 0.05 < design["duty"] <= 0.95
    assert 0.05 < design["turns_ratio"] <= 10.0
    assert design["inductance"] > 0
    assert design["capacitance"] > 0
    assert design["r_load"] > 0

    # Required component types present
    types = {c["type"] for c in components}
    assert "Transformer" in types
    assert "MOSFET" in types
    assert "Diode" in types
    assert "Inductor" in types
    assert "Capacitor" in types
    assert "Resistor" in types

    # Simulation time: at least 200 switching cycles for steady-state
    fsw = 100000
    assert result["simulation"]["total_time"] >= 200 / fsw

    # Net completeness: all expected nets present
    net_names = {n["name"] for n in nets}
    assert "net_gate" in net_names
    assert "net_out" in net_names
    assert "net_pri_gnd" in net_names
    assert "net_sec_gnd" in net_names


def test_forward_generator_required_fields():
    gen = get_generator("forward")
    assert "vin" in gen.required_fields
    assert "vout_target" in gen.required_fields


def test_forward_generator_missing_fields():
    gen = get_generator("forward")
    missing = gen.missing_fields({"vin": 48})
    assert "vout_target" in missing


def test_forward_generator_custom_turns_ratio():
    """n_ratio override should be respected."""
    gen = get_generator("forward")
    result = gen.generate({
        "vin": 100.0,
        "vout_target": 24.0,
        "iout": 3.0,
        "n_ratio": 0.6,
    })
    assert abs(result["metadata"]["design"]["turns_ratio"] - 0.6) < 1e-9


def test_forward_generator_respects_explicit_duty_override():
    gen = get_generator("forward")
    result = gen.generate({
        "vin": 48.0,
        "vout_target": 12.0,
        "n_ratio": 5.0 / 9.0,
        "duty_cycle": 181 / 360,
    })

    design = result["metadata"]["design"]
    gating = next(c for c in result["components"] if c["id"] == "G1")

    assert design["duty"] == pytest.approx(181 / 360, rel=0, abs=1e-6)
    assert design["switching_points"] == " 0 181."
    assert gating["parameters"]["Switching_Points"] == " 0 181."


def test_forward_generator_accepts_switching_frequency_alias():
    gen = get_generator("forward")
    result = gen.generate({
        "vin": 48.0,
        "vout_target": 12.0,
        "switching_frequency": 80_000,
    })

    gating = next(c for c in result["components"] if c["id"] == "G1")
    assert gating["parameters"]["Frequency"] == 80_000
    assert result["simulation"]["time_step"] == pytest.approx(round(1 / (80_000 * 200), 9))


def test_forward_generator_uses_diode_compensated_duty_with_fixed_turns_ratio():
    gen = get_generator("forward")
    result = gen.generate({
        "vin": 48.0,
        "vout_target": 12.0,
        "n_ratio": 5.0 / 9.0,
        "rectifier_diode_drop": 0.7,
        "freewheel_diode_drop": 0.7,
    })

    duty = result["metadata"]["design"]["duty"]
    assert duty == pytest.approx((12.0 + 0.7) / (48.0 * (5.0 / 9.0)), rel=0, abs=1e-6)


def test_forward_generator_simulation_defaults():
    """Embedded simulation time should be >= 200 cycles regardless of fsw."""
    from psim_mcp.generators import get_generator
    for fsw in [50000, 100000, 200000]:
        gen = get_generator("forward")
        result = gen.generate({"vin": 48.0, "vout_target": 12.0, "fsw": fsw})
        min_cycles = 200
        assert result["simulation"]["total_time"] >= min_cycles / fsw, (
            f"fsw={fsw}: total_time={result['simulation']['total_time']} < {min_cycles/fsw}"
        )


def test_forward_in_simulation_defaults():
    """forward must appear in SIMULATION_DEFAULTS so get_simulation_defaults works."""
    from psim_mcp.data.simulation_defaults import SIMULATION_DEFAULTS, get_simulation_defaults
    assert "forward" in SIMULATION_DEFAULTS
    defaults = get_simulation_defaults("forward")
    assert "time_step" in defaults
    assert "total_time" in defaults


def test_forward_topology_metrics_defined():
    """forward must have topology_metrics entry with acceptance_criteria."""
    from psim_mcp.data.topology_metrics import get_topology_metrics, get_acceptance_criteria
    metrics = get_topology_metrics("forward")
    assert metrics is not None
    assert "metrics" in metrics
    assert "steady_state_skip" in metrics
    assert "primary_signals" in metrics
    assert "tunable_params" in metrics
    criteria = get_acceptance_criteria("forward")
    assert criteria is not None
    assert "output_voltage_mean" in criteria
    assert "output_voltage_ripple_pct" in criteria
    tunable_components = {item["component"] for item in metrics["tunable_params"]}
    assert "Vout" in tunable_components
    assert "R1" not in tunable_components


def test_layout_factories_follow_port_contract_lengths():
    comp = make_mosfet_h("SW1", 100, 120, switching_frequency=50000)

    assert comp["type"] == "MOSFET"
    assert len(comp["ports"]) == 6
