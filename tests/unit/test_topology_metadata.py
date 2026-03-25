"""Tests for topology metadata helpers."""

from psim_mcp.data.topology_metadata import get_slot_questions


def test_forward_slot_questions_expose_pwm_and_diode_overrides():
    questions = get_slot_questions("forward")

    assert "switching_points" in questions
    assert "rectifier_diode_drop" in questions
    assert "freewheel_diode_drop" in questions
