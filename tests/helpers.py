"""Shared constants and helpers for the inverter tests (simulated time only)."""
from __future__ import annotations

import logging

import pytest

from sim.grid_sim import GridSim
from sim.inverter_sim import InverterSim, InverterState

logger = logging.getLogger(__name__)

RATED_W = 6000.0
P_TOL_W = 0.001 * RATED_W      # 0.1 % of rated
RAMP_W_PER_S = 600.0           # default 10 %/s of rated
DT_S = 0.1
I_TOL_A = 0.01
EXACT_TOL = 1e-9
SNAP_TOL = 1e-6
V_COARSE_V = 0.1
V_EDGE_V = 1e-6
TIME_EPS_S = 1e-9
OVER_FREQ_HZ = 61.0            # clearly above the 60.5 Hz limit
NOMINAL_F_HZ = 60.0

Samples = list[tuple[float, float]]


def settle(inv: InverterSim, p_w: float) -> None:
    """Set a setpoint, run until it is reached, and assert it was reached."""
    was_running = inv.state == InverterState.RUNNING
    inv.set_p_setpoint_w(p_w)
    inv.step(30.0)  # one big step: the model snaps to the target
    expected_w = max(-RATED_W, min(RATED_W, p_w))
    logger.info("settle: setpoint %.1f W -> p_ac=%.1f W (expected %.1f W)",
                p_w, inv.p_ac_w, expected_w)
    assert inv.p_ac_w == pytest.approx(expected_w, abs=EXACT_TOL)
    if was_running:
        assert inv.state == InverterState.RUNNING


def trip(grid: GridSim, inv: InverterSim) -> None:
    """Fault the inverter with an over-frequency grid, assert it, restore the grid."""
    grid.f_hz = OVER_FREQ_HZ
    inv.step(DT_S)
    assert inv.state == InverterState.FAULT
    grid.f_hz = NOMINAL_F_HZ


def record(inv: InverterSim, duration_s: float, dt_s: float = DT_S) -> Samples:
    """Step the inverter; return (t_s, p_ac_w) including the t=0 sample."""
    samples: Samples = [(0.0, inv.p_ac_w)]
    for i in range(1, round(duration_s / dt_s) + 1):
        inv.step(dt_s)
        samples.append((i * dt_s, inv.p_ac_w))
    return samples


def p_at(samples: Samples, t_s: float) -> float:
    """Power at the sample nearest to t_s."""
    return min(samples, key=lambda s: abs(s[0] - t_s))[1]


def check_ramp(samples: Samples, target_w: float, arrival_s: float,
               rate_w_per_s: float = RAMP_W_PER_S, dt_s: float = DT_S) -> None:
    """Ramp criteria R1-R4 from the plan, plus a lower slope bound while ramping."""
    slope_tol = P_TOL_W / dt_s
    max_step_w = rate_w_per_s * dt_s
    slopes = []
    for (_, p0), (_, p1) in zip(samples, samples[1:]):
        slope = abs(p1 - p0) / dt_s
        slopes.append(slope)
        assert slope <= rate_w_per_s + slope_tol                       # R1 upper slope
        if abs(p0 - target_w) > max_step_w:                            # still ramping
            assert slope >= rate_w_per_s - slope_tol                   # R1 lower slope
    arrived = [t for t, p in samples if abs(p - target_w) <= P_TOL_W]  # R2 arrival
    assert arrived, "never reached target"
    assert abs(arrived[0] - arrival_s) <= dt_s + TIME_EPS_S
    direction = 1.0 if target_w >= samples[0][1] else -1.0
    for _, p in samples:                                               # R3 overshoot
        assert direction * (p - target_w) <= EXACT_TOL
    for (_, p0), (_, p1) in zip(samples, samples[1:]):                 # R4 monotonic
        assert direction * (p1 - p0) >= -EXACT_TOL
    logger.info("ramp check: %d samples, slope %.1f..%.1f W/s (rate %.0f W/s), "
                "arrived at %.2f s (expected %.2f +/- %.2f s)",
                len(samples), min(slopes), max(slopes), rate_w_per_s,
                arrived[0], arrival_s, dt_s)
