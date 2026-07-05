"""Importer — reconstruct a CircuitGraph from an existing .psimsch.

Pipeline (docs/ver2/schematic-import-netlist-reconstruction-PRD.md):

    .psimsch → PsimConvertToPython (bridge)  → generated Python script
             → parser.parse_converted_script → ParsedSchematic
             → net_builder.reconstruct       → CircuitGraph + net report

PsimConvertToPython is the only complete text representation the PSIM API
exposes: PsimGetElementList omits wires, positions and node indices
(verified 2026-07-06, PSIM 2026 / psimapipy 2026.0).
"""

from .net_builder import ReconstructionResult, reconstruct
from .parser import (
    ParsedComponent,
    ParsedLabel,
    ParsedSchematic,
    ParsedWire,
    parse_converted_script,
)
from .roundtrip import compare_nets, emit_script

__all__ = [
    "ParsedComponent",
    "ParsedLabel",
    "ParsedSchematic",
    "ParsedWire",
    "ReconstructionResult",
    "compare_nets",
    "emit_script",
    "parse_converted_script",
    "reconstruct",
]
