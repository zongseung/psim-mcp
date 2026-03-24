"""Sizing formulas extracted from topology generators.

Pure functions that compute component values from requirements.
No component creation, no layout, no nets -- just math.
"""

from __future__ import annotations

import math


def size_buck(requirements: dict) -> dict[str, float]:
    """Compute buck converter component values.

    Parameters
    ----------
    requirements : dict
        Must contain 'vin' and 'vout_target'. Optional: 'iout', 'fsw',
        'ripple_ratio', 'voltage_ripple_ratio'.

    Returns
    -------
    dict with keys: duty, inductance, capacitance, r_load
    """
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
    fsw = float(requirements.get("fsw", 50_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    duty = vout / vin
    delta_i = ripple_ratio * iout
    inductance = vout * (1 - duty) / (fsw * delta_i) if delta_i else 1e-3
    capacitance = delta_i / (8 * fsw * vripple_ratio * vout) if vout else 100e-6
    r_load = vout / iout if iout else 10.0

    return {
        "duty": round(duty, 6),
        "inductance": round(inductance, 9),
        "capacitance": round(capacitance, 9),
        "r_load": round(r_load, 4),
    }


def size_flyback(requirements: dict) -> dict[str, float]:
    """Compute flyback converter component values.

    Parameters
    ----------
    requirements : dict
        Must contain 'vin' and 'vout_target'. Optional: 'iout', 'fsw',
        'n_ratio', 'ripple_ratio', 'voltage_ripple_ratio'.

    Returns
    -------
    dict with keys: turns_ratio, duty, Lm, Cout, r_load
    """
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
    fsw = float(requirements.get("fsw", 100_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    # Turns ratio Ns/Np
    if requirements.get("n_ratio"):
        n = float(requirements["n_ratio"])
    else:
        d_target = 0.45
        n = d_target * vin / (vout * (1 - d_target)) if vout else 1.0
        n = max(0.1, min(n, 10.0))

    # Duty cycle: D = (Vout * n) / (Vin + Vout * n)
    denom = vin + vout * n
    duty = (vout * n) / denom if denom else 0.5
    duty = max(0.05, min(duty, 0.95))

    # Input current
    pout = vout * iout
    iin = pout / (vin * duty) if (vin and duty) else iout

    # Magnetizing inductance: Lm = Vin * D / (fsw * delta_I)
    delta_i = ripple_ratio * iin
    lm = vin * duty / (fsw * delta_i) if (fsw and delta_i) else 1e-3
    lm = max(lm, 1e-9)

    # Output capacitance: Cout = Iout * D / (fsw * Vripple)
    vripple = vripple_ratio * vout
    cout = iout * duty / (fsw * vripple) if (fsw and vripple) else 100e-6
    cout = max(cout, 1e-12)

    r_load = vout / iout if iout else 10.0

    return {
        "turns_ratio": round(n, 6),
        "duty": round(duty, 6),
        "Lm": round(lm, 9),
        "Cout": round(cout, 9),
        "r_load": round(r_load, 4),
    }


def size_llc(requirements: dict) -> dict[str, float]:
    """Compute LLC resonant converter component values.

    Parameters
    ----------
    requirements : dict
        Must contain 'vin' and 'vout_target'. Optional: 'iout', 'fsw',
        'power', 'quality_factor'.

    Returns
    -------
    dict with keys: n, Lr, Cr, Lm, Cout, r_load
    """
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    fsw = float(requirements.get("fsw", 100_000))
    ln_ratio = float(requirements.get("quality_factor", 6.0))
    ln_ratio = max(3.0, min(ln_ratio, 10.0))

    # Output power
    if requirements.get("power"):
        pout = float(requirements["power"])
        iout = pout / vout if vout else 1.0
    elif requirements.get("iout"):
        iout = float(requirements["iout"])
        pout = vout * iout
    else:
        iout = 1.0
        pout = vout * iout

    r_load = vout / iout if iout else 10.0
    r_load = max(r_load, 0.1)

    # Turns ratio for half-bridge: n = Vin / (2 * Vout)
    n = vin / (2 * vout) if vout else 1.0
    n = max(0.1, min(n, 20.0))

    # Resonant frequency = switching frequency (design at resonance)
    fr = fsw

    # Equivalent AC load resistance: Rac = 8 * n^2 * Rload / pi^2
    rac = 8 * n**2 * r_load / (math.pi**2)

    # Characteristic impedance: Zr = Rac (at matched load for unity gain)
    zr = rac if rac > 0 else 10.0

    # Resonant inductor: Lr = Zr / (2 * pi * fr)
    lr = zr / (2 * math.pi * fr) if fr else 1e-6
    lr = max(lr, 1e-9)

    # Resonant capacitor: Cr = 1 / ((2*pi*fr)^2 * Lr)
    cr = 1 / ((2 * math.pi * fr) ** 2 * lr) if (fr and lr) else 10e-9
    cr = max(cr, 1e-12)

    # Magnetizing inductance: Lm = Ln_ratio * Lr
    lm = ln_ratio * lr
    lm = max(lm, 1e-9)

    # Output capacitor: sized for ripple at 2*fsw (full-bridge rectifier)
    vripple_ratio = 0.01
    vripple = vripple_ratio * vout
    cout = iout / (2 * 2 * fsw * vripple) if (fsw and vripple) else 100e-6
    cout = max(cout, 1e-12)

    return {
        "n": round(n, 6),
        "Lr": round(lr, 9),
        "Cr": round(cr, 9),
        "Lm": round(lm, 9),
        "Cout": round(cout, 9),
        "r_load": round(r_load, 4),
    }
