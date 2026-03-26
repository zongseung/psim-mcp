"""Tests for topology-specific acceptance criteria evaluation."""

from __future__ import annotations

from psim_mcp.data.topology_metrics import evaluate_acceptance, get_acceptance_criteria


class TestGetAcceptanceCriteria:
    def test_buck_has_criteria(self):
        criteria = get_acceptance_criteria("buck")
        assert criteria is not None
        assert "output_voltage_mean" in criteria
        assert "output_voltage_ripple_pct" in criteria

    def test_unknown_topology_returns_none(self):
        assert get_acceptance_criteria("nonexistent") is None


class TestEvaluateAcceptance:
    def test_buck_passes_normal_output(self):
        result = evaluate_acceptance(
            "buck",
            metrics={"output_voltage_mean": 12.05, "output_voltage_ripple_pct": 2.3},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is True
        assert result["results"]["output_voltage_mean"]["status"] == "pass"
        assert result["results"]["output_voltage_ripple_pct"]["status"] == "pass"

    def test_buck_fails_zero_voltage(self):
        """0V output should fail the min_absolute check."""
        result = evaluate_acceptance(
            "buck",
            metrics={"output_voltage_mean": 0.0, "output_voltage_ripple_pct": 0.0},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is False
        assert result["results"]["output_voltage_mean"]["status"] == "fail"
        assert "min_absolute" in result["results"]["output_voltage_mean"]["reason"]

    def test_buck_fails_excessive_ripple(self):
        result = evaluate_acceptance(
            "buck",
            metrics={"output_voltage_mean": 12.0, "output_voltage_ripple_pct": 15.0},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is False
        assert result["results"]["output_voltage_ripple_pct"]["status"] == "fail"

    def test_buck_fails_voltage_out_of_tolerance(self):
        result = evaluate_acceptance(
            "buck",
            metrics={"output_voltage_mean": 10.0, "output_voltage_ripple_pct": 1.0},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is False
        vout = result["results"]["output_voltage_mean"]
        assert vout["status"] == "fail"
        assert vout["error_pct"] > 5.0

    def test_llc_fails_zero_output(self):
        """LLC 0V issue — should be caught by acceptance criteria."""
        result = evaluate_acceptance(
            "llc",
            metrics={
                "output_voltage_mean": 0.0,
                "output_voltage_ripple_pct": 0.0,
                "resonant_current_rms": 0.0,
            },
            targets={"output_voltage_mean": 24.0},
        )
        assert result["passed"] is False
        assert "FAIL" in result["summary"]

    def test_no_criteria_topology_passes(self):
        result = evaluate_acceptance("nonexistent", metrics={"foo": 1.0})
        assert result["passed"] is True
        assert result["summary"] == "No criteria defined."

    def test_missing_metric_is_skipped(self):
        result = evaluate_acceptance(
            "buck",
            metrics={"output_voltage_mean": 12.0},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is True
        assert result["results"]["output_voltage_ripple_pct"]["status"] == "skipped"

    def test_no_targets_skips_tolerance_check(self):
        """Without targets, only absolute checks apply."""
        result = evaluate_acceptance(
            "buck",
            metrics={"output_voltage_mean": 5.0, "output_voltage_ripple_pct": 3.0},
        )
        # No target → tolerance check skipped, but min_absolute still applies
        assert result["passed"] is True
        assert result["results"]["output_voltage_mean"]["status"] == "pass"

    def test_forward_has_criteria(self):
        from psim_mcp.data.topology_metrics import get_acceptance_criteria
        criteria = get_acceptance_criteria("forward")
        assert criteria is not None
        assert "output_voltage_mean" in criteria
        assert "output_voltage_ripple_pct" in criteria

    def test_forward_passes_normal_output(self):
        """Forward converter nominal 48V->12V output."""
        result = evaluate_acceptance(
            "forward",
            metrics={"output_voltage_mean": 12.1, "output_voltage_ripple_pct": 3.5},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is True
        assert result["results"]["output_voltage_mean"]["status"] == "pass"
        assert result["results"]["output_voltage_ripple_pct"]["status"] == "pass"

    def test_forward_fails_zero_voltage(self):
        """0V output (open circuit or wiring error) must fail."""
        result = evaluate_acceptance(
            "forward",
            metrics={"output_voltage_mean": 0.0, "output_voltage_ripple_pct": 0.0},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is False
        assert result["results"]["output_voltage_mean"]["status"] == "fail"
        assert "min_absolute" in result["results"]["output_voltage_mean"]["reason"]

    def test_forward_fails_excessive_ripple(self):
        """Ripple >15% should fail for forward converter."""
        result = evaluate_acceptance(
            "forward",
            metrics={"output_voltage_mean": 12.0, "output_voltage_ripple_pct": 20.0},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is False
        assert result["results"]["output_voltage_ripple_pct"]["status"] == "fail"

    def test_forward_fails_voltage_out_of_tolerance(self):
        """Output >10% from target fails the tolerance check."""
        result = evaluate_acceptance(
            "forward",
            metrics={"output_voltage_mean": 9.0, "output_voltage_ripple_pct": 2.0},
            targets={"output_voltage_mean": 12.0},
        )
        assert result["passed"] is False
        vout = result["results"]["output_voltage_mean"]
        assert vout["status"] == "fail"
        assert vout["error_pct"] > 10.0
