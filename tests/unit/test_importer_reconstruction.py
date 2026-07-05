"""Tests for the importer — PsimConvertToPython parsing + net reconstruction."""

from psim_mcp.importer import parse_converted_script, reconstruct

# Minimal synthetic script mirroring PsimConvertToPython output format.
_BASIC = """
p1.PsimSetElmValue(sch, None, "TIMESTEP", "1E-06")
p1.PsimSetElmValue(sch, None, "TOTALTIME", "0.5")
nCreatedIndex = p1.PsimCreateNewElement(sch, "SIMCONTROL", "", DIRECTION = 0, AREA = [0, 0, 40, 40], PAGE=0, XFLIP=0, _OPTIONS_=0)
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_INDUCTOR", "L1", SubType="Level 1", AREA = [100, 90, 150, 110], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[100, 100, 150, 100], Inductance = "125u")
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_CAPACITOR", "C1", SubType="Level 1", AREA = [190, 100, 210, 150], DIRECTION = 90, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[200, 100, 200, 150], Capacitance = "10u")
nCreatedIndex = p1.PsimCreateNewElement(sch, "TEXT", "annotation only", AREA = [0, 0, 10, 10], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=0, FontName="Arial")
nCreatedIndex = p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="150", Y1="100", X2="200", Y2="100")
nCreatedIndex = p1.PsimCreateNewElement(sch, "LABEL", "OUT", DIRECTION = 0, PORTS=[200, 100], PAGE=0, XFLIP=0, _OPTIONS_=16)
nCreatedIndex = p1.PsimCreateNewElement(sch, "LABEL", "OUT", DIRECTION = 0, PORTS=[300, 300], PAGE=0, XFLIP=0, _OPTIONS_=16)
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R1", SubType="Level 1", AREA = [300, 290, 350, 310], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[300, 300, 350, 300], Resistance = "10")
"""


def _net_pins(result):
    return {net.id: set(net.pins) for net in result.graph.nets}


class TestParser:
    def test_components_wires_labels_parsed(self):
        parsed = parse_converted_script(_BASIC)
        assert [c.id for c in parsed.components] == ["L1", "C1", "R1"]
        assert len(parsed.wires) == 1
        assert parsed.wires[0].points == [(150, 100), (200, 100)]
        assert [lb.name for lb in parsed.labels] == ["OUT", "OUT"]

    def test_parameters_extracted_layout_keys_dropped(self):
        parsed = parse_converted_script(_BASIC)
        l1 = parsed.components[0]
        assert l1.parameters == {"Inductance": "125u"}
        assert l1.pins == [(100, 100), (150, 100)]
        assert l1.metadata["subtype"] == "Level 1"

    def test_simulation_settings_captured(self):
        parsed = parse_converted_script(_BASIC)
        assert parsed.simulation["TIMESTEP"] == "1E-06"
        assert parsed.simulation["TOTALTIME"] == "0.5"

    def test_multiseg_wire(self):
        script = 'p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="0", Y1="0", X2="0", Y2="50", X3="100", Y3="50")'
        parsed = parse_converted_script(script)
        assert parsed.wires[0].segments == [((0, 0), (0, 50)), ((0, 50), (100, 50))]

    def test_disabled_element_flagged(self):
        script = (
            'nCreatedIndex = p1.PsimCreateNewElement(sch, "VDC", "V1", PORTS=[0, 0, 0, 50], Amplitude = "20")\n'
            "p1.PsimEnableElm3(sch, nCreatedIndex, 0)\n"
        )
        parsed = parse_converted_script(script)
        assert parsed.components[0].metadata["enabled"] is False

    def test_string_var_resolution_setelmvalue2(self):
        script = (
            'strScript_SCB1 = "void SimulationStep() {}"\n'
            'nCreatedIndex = p1.PsimCreateNewElement(sch, "CBLOCK", "SCB1", PORTS=[0, 0], _InputCount=1, _OutputCount=1)\n'
            'p1.PsimSetElmValue2(sch, "CBLOCK", "SCB1", "CONTENT", strScript_SCB1)\n'
        )
        parsed = parse_converted_script(script)
        assert parsed.components[0].parameters["CONTENT"] == "void SimulationStep() {}"

    def test_duplicate_names_uniquified(self):
        script = (
            'p1.PsimCreateNewElement(sch, "Ground", "Ground", PORTS=[0, 0])\n'
            'p1.PsimCreateNewElement(sch, "Ground", "Ground", PORTS=[100, 0])\n'
        )
        parsed = parse_converted_script(script)
        assert [c.id for c in parsed.components] == ["Ground", "Ground_2"]


class TestNetReconstruction:
    def test_wire_and_label_merge(self):
        # L1.1 -(wire)- C1.0, and label OUT bridges C1.0 to R1.0
        result = reconstruct(parse_converted_script(_BASIC))
        nets = _net_pins(result)
        assert nets == {"OUT": {"L1.1", "C1.0", "R1.0"}}
        assert set(result.dangling_pins) == {"L1.0", "C1.1", "R1.1"}

    def test_t_junction_connects_endpoint_on_midspan(self):
        script = (
            'p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R1", PORTS=[0, 0, 0, 0])\n'
            'p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R2", PORTS=[100, 0, 100, 0])\n'
            'p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R3", PORTS=[50, 50, 50, 50])\n'
            'p1.PsimCreateNewElement(sch, "WIRE", "", X1="0", Y1="0", X2="100", Y2="0")\n'
            'p1.PsimCreateNewElement(sch, "WIRE", "", X1="50", Y1="0", X2="50", Y2="50")\n'
        )
        result = reconstruct(parse_converted_script(script))
        # T-junction: vertical wire endpoint (50,0) lies mid-span on the
        # horizontal wire -> all three connect.
        assert len(result.graph.nets) == 1
        assert set(result.graph.nets[0].pins) >= {"R1.0", "R2.0", "R3.0"}

    def test_crossover_does_not_connect(self):
        script = (
            'p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R1", PORTS=[0, 50, 100, 50])\n'
            'p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R2", PORTS=[50, 0, 50, 100])\n'
            'p1.PsimCreateNewElement(sch, "WIRE", "", X1="0", Y1="50", X2="100", Y2="50")\n'
            'p1.PsimCreateNewElement(sch, "WIRE", "", X1="50", Y1="0", X2="50", Y2="100")\n'
        )
        result = reconstruct(parse_converted_script(script))
        nets = _net_pins(result)
        # Two wires crossing mid-span (no endpoint at 50,50) stay separate.
        assert len(nets) == 2
        pin_sets = sorted(nets.values(), key=sorted)
        assert pin_sets == [{"R1.0", "R1.1"}, {"R2.0", "R2.1"}]

    def test_ground_symbols_merge_into_one_net(self):
        script = (
            'p1.PsimCreateNewElement(sch, "VDC", "V1", PORTS=[0, 0, 0, 50], Amplitude = "10")\n'
            'p1.PsimCreateNewElement(sch, "Ground", "Ground", PORTS=[0, 50])\n'
            'p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R1", PORTS=[200, 0, 200, 50])\n'
            'p1.PsimCreateNewElement(sch, "Ground", "Ground", PORTS=[200, 50])\n'
        )
        result = reconstruct(parse_converted_script(script))
        nets = _net_pins(result)
        assert nets == {"GND": {"V1.1", "Ground.0", "Ground_2.0", "R1.1"}}
        gnd = result.graph.get_net("GND")
        assert gnd.role == "ground"

    def test_coincident_pins_connect_without_wire(self):
        # CONSTANT output placed exactly on SUM2 input (seen in real files)
        script = (
            'p1.PsimCreateNewElement(sch, "SUM2", "SUM1", PORTS=[820, 1390, 840, 1410, 860, 1390])\n'
            'p1.PsimCreateNewElement(sch, "CONSTANT", "Vref", PORTS=[820, 1390], Amplitude = "20")\n'
        )
        result = reconstruct(parse_converted_script(script))
        nets = _net_pins(result)
        assert any({"SUM1.0", "Vref.0"} <= pins for pins in nets.values())

    def test_simulation_settings_flow_into_graph(self):
        result = reconstruct(parse_converted_script(_BASIC))
        assert result.graph.simulation["TOTALTIME"] == "0.5"

    def test_stats(self):
        result = reconstruct(parse_converted_script(_BASIC))
        assert result.stats["components"] == 3
        assert result.stats["nets"] == 1
        assert result.stats["dangling_pins"] == 3
        assert result.stats["connected_pins"] == 3
