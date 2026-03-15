"""Tests for topology generators."""
from psim_mcp.generators import get_generator, list_generators
from psim_mcp.generators.buck import BuckGenerator
import pytest


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
