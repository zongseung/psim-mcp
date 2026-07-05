"""Tests for import_circuit (service) and roundtrip (emit/compare)."""

from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.importer import (
    compare_nets,
    emit_script,
    parse_converted_script,
    reconstruct,
)
from psim_mcp.services.project_service import ProjectService

_SCRIPT = """
p1.PsimSetElmValue(sch, None, "TIMESTEP", "1E-06")
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_INDUCTOR", "L1", SubType="Level 1", AREA = [100, 90, 150, 110], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[100, 100, 150, 100], Inductance = "125u")
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_CAPACITOR", "C1", SubType="Level 1", AREA = [190, 100, 210, 150], DIRECTION = 90, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[200, 100, 200, 150], Capacitance = "10u")
nCreatedIndex = p1.PsimCreateNewElement(sch, "Ground", "Ground", AREA = [190, 150, 210, 170], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[200, 150])
nCreatedIndex = p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="150", Y1="100", X2="200", Y2="100")
nCreatedIndex = p1.PsimCreateNewElement(sch, "LABEL", "IN", DIRECTION = 0, PORTS=[100, 100], PAGE=0, XFLIP=0, _OPTIONS_=16)
"""


class TestRoundTrip:
    def test_emit_reparse_preserves_nets(self):
        parsed = parse_converted_script(_SCRIPT)
        graph_a = reconstruct(parsed).graph

        emitted = emit_script(parsed)
        graph_b = reconstruct(parse_converted_script(emitted)).graph

        report = compare_nets(graph_a, graph_b)
        assert report["identical"], report
        assert report["pin_pair_precision"] == 1.0
        assert report["pin_pair_recall"] == 1.0

    def test_emit_is_runnable_python(self):
        parsed = parse_converted_script(_SCRIPT)
        emitted = emit_script(parsed)
        compile(emitted, "<emitted>", "exec")  # SyntaxError → test failure
        assert "PsimFileSave" in emitted
        assert "PsimSetElmValue(sch, None, 'TIMESTEP', '1E-06')" in emitted

    def test_emit_defers_multiline_params(self):
        script = (
            'strScript = "line1\\r\\nline2"\n'
            'nCreatedIndex = p1.PsimCreateNewElement(sch, "CBLOCK", "SCB1", '
            "PORTS=[0, 0], _InputCount=1, _OutputCount=1)\n"
            'p1.PsimSetElmValue2(sch, "CBLOCK", "SCB1", "CONTENT", strScript)\n'
        )
        parsed = parse_converted_script(script)
        emitted = emit_script(parsed)
        compile(emitted, "<emitted>", "exec")
        # CONTENT must be emitted via PsimSetElmValue2, not inline kwargs
        assert "PsimSetElmValue2(sch, 'CBLOCK', 'SCB1', 'CONTENT'" in emitted
        assert "_InputCount=1" in emitted

    def test_emit_preserves_disabled_flag(self):
        script = (
            'nCreatedIndex = p1.PsimCreateNewElement(sch, "VDC", "V1", '
            'PORTS=[0, 0, 0, 50], Amplitude = "20")\n'
            "p1.PsimEnableElm3(sch, nCreatedIndex, 0)\n"
        )
        emitted = emit_script(parse_converted_script(script))
        assert "PsimEnableElm3(sch, nCreatedIndex, 0)" in emitted

    def test_compare_detects_missing_connection(self):
        parsed = parse_converted_script(_SCRIPT)
        graph_a = reconstruct(parsed).graph
        # Remove the wire → L1.1-C1.0 net disappears
        broken = parse_converted_script(_SCRIPT)
        broken.wires.clear()
        graph_b = reconstruct(broken).graph

        report = compare_nets(graph_a, graph_b)
        assert not report["identical"]
        assert report["pin_pair_recall"] < 1.0
        assert report["nets_missing"]


class TestImportCircuitService:
    async def test_import_circuit_mock_end_to_end(self, test_config, sample_project_path):
        service = ProjectService(adapter=MockPsimAdapter(), config=test_config)
        result = await service.import_circuit(str(sample_project_path))

        assert result["success"], result
        data = result["data"]
        assert data["stats"]["components"] == 5  # V1 L1 C1 R1 Ground (SIMCONTROL skipped)
        net_pins = {net["id"]: set(net["pins"]) for net in data["nets"]}
        # Mock script: V1-L1 input net, Vout net (L1.1/C1.0/R1.0), GND rail
        assert net_pins["Vout"] == {"L1.1", "C1.0", "R1.0"}
        assert net_pins["GND"] == {"V1.1", "C1.1", "R1.1", "Ground.0"}
        assert data["simulation"]["TOTALTIME"] == "0.05"
        assert "graph" not in data

    async def test_import_circuit_include_graph(self, test_config, sample_project_path):
        service = ProjectService(adapter=MockPsimAdapter(), config=test_config)
        result = await service.import_circuit(str(sample_project_path), include_graph=True)
        assert result["success"]
        graph = result["data"]["graph"]
        assert graph["topology"] == sample_project_path.stem
        assert graph["metadata"]["source"] == "psim_convert_to_python"

    async def test_import_circuit_rejects_disallowed_path(self, test_config):
        service = ProjectService(adapter=MockPsimAdapter(), config=test_config)
        result = await service.import_circuit("C:\\somewhere\\else\\x.psimsch")
        assert not result["success"]

    async def test_import_circuit_unsupported_adapter(self, test_config, sample_project_path):
        class NoConvertAdapter(MockPsimAdapter):
            async def convert_to_python(self, path, output_path=""):
                raise NotImplementedError

        service = ProjectService(adapter=NoConvertAdapter(), config=test_config)
        result = await service.import_circuit(str(sample_project_path))
        assert not result["success"]
        assert result["error"]["code"] == "NOT_SUPPORTED"
