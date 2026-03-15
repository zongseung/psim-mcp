"""Tests for unit parser."""
from psim_mcp.parsers.unit_parser import extract_values


def test_voltage():
    result = extract_values("48V input")
    assert 48.0 in result.get("voltage", [])


def test_current():
    result = extract_values("5A load")
    assert 5.0 in result.get("current", [])


def test_frequency_khz():
    result = extract_values("100kHz switching")
    assert 100000.0 in result.get("frequency", [])


def test_inductance_uh():
    result = extract_values("47\u03bcH inductor")
    vals = result.get("inductance", [])
    assert len(vals) > 0
    assert abs(vals[0] - 47e-6) < 1e-9


def test_resistance_ohm():
    result = extract_values("10\u03a9 resistor")
    assert 10.0 in result.get("resistance", [])


def test_multiple_values():
    result = extract_values("48V input 12V output 5A load")
    assert len(result.get("voltage", [])) == 2
    assert len(result.get("current", [])) == 1


def test_korean_units():
    result = extract_values("48\ubcfc\ud2b8 10\uc634")
    assert 48.0 in result.get("voltage", [])
    assert 10.0 in result.get("resistance", [])
