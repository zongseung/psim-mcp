"""Waveform rendering -- generates PNG plots from simulation signal data."""

from __future__ import annotations

import os
import tempfile


def render_waveforms(
    signals: dict[str, list[float]],
    time_step: float,
    title: str | None = None,
    output_path: str | None = None,
) -> str:
    """Render waveform data to PNG file. Returns file path.

    Parameters
    ----------
    signals:
        Mapping of signal name to list of sample values.
    time_step:
        Simulation time step in seconds (used to generate the time axis).
    title:
        Optional plot title.
    output_path:
        Optional explicit file path for the output PNG.  When *None* a
        deterministic path in the system temp directory is used.

    Returns
    -------
    str
        Absolute path to the generated PNG file, or ``""`` if rendering
        was not possible (e.g. matplotlib not installed, no signals).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        # matplotlib not available -- return empty path
        return ""

    n_signals = len(signals)
    if n_signals == 0:
        return ""

    fig, axes = plt.subplots(n_signals, 1, figsize=(10, 3 * n_signals), sharex=True)
    if n_signals == 1:
        axes = [axes]

    for ax, (name, values) in zip(axes, signals.items()):
        t_ms = [i * time_step * 1000 for i in range(len(values))]
        ax.plot(t_ms, values, linewidth=0.5, color="#2c3e50")
        ax.set_ylabel(name, fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)

    axes[-1].set_xlabel("Time (ms)", fontsize=9)
    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()

    if output_path is None:
        import hashlib

        content_hash = hashlib.sha256(str(signals).encode()).hexdigest()[:8]
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"psim_waveform_{content_hash}.png",
        )

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path
