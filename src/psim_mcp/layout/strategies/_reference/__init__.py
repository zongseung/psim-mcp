"""Reference layout strategies — NOT used in production.

These files contain the original hardcoded coordinate tables from
Phase 3.  They are kept ONLY as baselines for comparing auto_place()
output quality.  They are NOT registered with the layout engine.

To compare auto-layout vs reference for testing::

    from psim_mcp.layout.strategies._reference.buck import BuckLayoutStrategy
    ref_layout = BuckLayoutStrategy().build_layout(graph)
"""
