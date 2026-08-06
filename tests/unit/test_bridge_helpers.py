"""bridge_script.py 헬퍼 함수 테스트.

bridge_script.py는 PSIM Python 3.8에서 실행되지만,
순수 함수인 헬퍼들은 테스트 환경에서도 import하여 검증할 수 있다.
"""

from __future__ import annotations

import psim_mcp.bridge.bridge_script as bridge_script

class TestHandleSetParameter:
    def test_maps_alias_parameter_and_persists(self, monkeypatch):
        sch = object()

        class FakePsim:
            def __init__(self):
                self.set_calls = []
                self.save_calls = []

            def PsimSetElmValue2(self, sch_obj, comp_type, comp_name, param_name, value):
                self.set_calls.append((sch_obj, comp_type, comp_name, param_name, value))
                return 1

            def PsimFileSave(self, sch_obj, path):
                self.save_calls.append((sch_obj, path))

        fake_psim = FakePsim()
        monkeypatch.setattr(bridge_script, "_get_psim", lambda: fake_psim)
        monkeypatch.setattr(bridge_script, "_current_sch", sch)
        monkeypatch.setattr(bridge_script, "_current_path", "C:/tmp/forward.psimsch")
        monkeypatch.setattr(bridge_script, "_element_cache", {"G1": "GATING"})

        result = bridge_script.handle_set_parameter({
            "component_id": "G1",
            "parameter_name": "Switching_Points",
            "value": "0,181",
        })

        assert result["success"] is True
        assert result["data"]["psim_parameter_name"] == "Switching_Points"
        assert result["data"]["persisted"] is True
        assert fake_psim.set_calls == [
            (sch, "GATING", "G1", "Switching_Points", "0,181")
        ]
        assert fake_psim.save_calls == [
            (sch, "C:/tmp/forward.psimsch")
        ]
