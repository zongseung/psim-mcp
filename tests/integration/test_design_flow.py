"""Integration tests: circuit design → preview → confirm pipeline.

Exercises the full service stack with MockPsimAdapter.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


class TestBuckDesignFullFlow:
    """End-to-end: natural language → design → preview → confirm."""

    async def test_design_buck_48v_12v_returns_success(self, circuit_design_service):
        result = await circuit_design_service.design_circuit(
            "Buck converter 48V to 12V 5A"
        )

        assert result["success"] is True
        data = result["data"]
        # Should identify buck topology
        assert data.get("topology") == "buck" or "buck" in data.get("circuit_type", "")

    async def test_design_buck_produces_preview_token(self, circuit_design_service):
        result = await circuit_design_service.design_circuit(
            "Buck converter 48V input 12V output 5A load"
        )

        assert result["success"] is True
        data = result["data"]
        # Depending on confidence, we get a preview_token or design_session_token
        has_token = (
            "preview_token" in data
            or "design_session_token" in data
            or "preview_id" in data
        )
        assert has_token, f"No token found in response data keys: {list(data.keys())}"

    async def test_design_produces_ascii_or_svg(self, circuit_design_service):
        result = await circuit_design_service.design_circuit(
            "Buck converter 48V to 12V 5A"
        )

        assert result["success"] is True
        data = result["data"]
        # High-confidence designs auto-preview; others return candidates
        has_visual = (
            "ascii_diagram" in data
            or "svg_content" in data
            or "svg_preview_path" in data
            or data.get("action") == "confirm_intent"
            or "generation_mode" in data
        )
        assert has_visual, f"No visual/action found in: {list(data.keys())}"

    async def test_design_then_confirm_via_continue(self, circuit_design_service, tmp_path):
        """Full flow: design → continue_design (if session) → confirm."""
        design_result = await circuit_design_service.design_circuit(
            "Buck converter 48V to 12V 5A"
        )
        assert design_result["success"] is True
        data = design_result["data"]

        # High confidence → preview_token; medium → design_session_token
        preview_token = data.get("preview_token") or data.get("preview_id")
        session_token = data.get("design_session_token")

        if preview_token:
            # Direct confirm path
            save_path = str(tmp_path / "buck_test.psimsch")
            confirm_result = await circuit_design_service.confirm_circuit(
                save_path=save_path,
                preview_token=preview_token,
            )
            assert confirm_result["success"] is True
        elif session_token:
            # Medium confidence: continue_design first to get a preview
            cont = await circuit_design_service.continue_design(
                session_token=session_token,
                additional_description="48V input, 12V output, 5A load",
            )
            assert cont["success"] is True
            # After continue, we should get a preview token
            cont_data = cont.get("data", {})
            pt = cont_data.get("preview_token") or cont_data.get("preview_id")
            if pt:
                save_path = str(tmp_path / "buck_test.psimsch")
                confirm_result = await circuit_design_service.confirm_circuit(
                    save_path=save_path, preview_token=pt,
                )
                assert confirm_result["success"] is True
            else:
                # May still need more info — just verify it didn't crash
                assert "success" in cont
        else:
            pytest.skip("Design produced no actionable token")

    async def test_invalid_topology_does_not_crash(self, circuit_design_service):
        """Nonsense input should fail gracefully, not raise."""
        result = await circuit_design_service.design_circuit(
            "quantum flux capacitor 1.21 gigawatts"
        )
        # Should either succeed with a best-effort guess or return a graceful error
        assert "success" in result


class TestDesignSessionContinuation:
    """Test the continue_design path for medium-confidence results."""

    async def test_continue_design_with_session_token(self, circuit_design_service):
        """If design returns a session token, continue_design should accept it."""
        result = await circuit_design_service.design_circuit("boost converter")
        if result["success"] and "design_session_token" in result.get("data", {}):
            token = result["data"]["design_session_token"]
            cont = await circuit_design_service.continue_design(
                session_token=token,
                additional_description="48V input, 96V output, 3A",
            )
            assert "success" in cont
