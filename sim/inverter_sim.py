"""Pure-Python model of a 6 kW split-phase hybrid inverter.

Time only advances through step(dt_s); there are no sleeps or wall clock.
Sign convention: positive power = feed-in to the grid (battery discharging).
"""
from __future__ import annotations

import logging
import math
from enum import Enum

from sim.grid_sim import GridSim, GridState

logger = logging.getLogger(__name__)

V_LN_NOM_V = 120.0
V_LL_NOM_V = 240.0
F_NOM_HZ = 60.0
# Limits are computed once (0.88 * 120.0 is not exactly 105.6 in binary floats).
V_LN_MIN_V, V_LN_MAX_V = 0.88 * V_LN_NOM_V, 1.10 * V_LN_NOM_V
V_LL_MIN_V, V_LL_MAX_V = 0.88 * V_LL_NOM_V, 1.10 * V_LL_NOM_V
F_MIN_HZ, F_MAX_HZ = 59.3, 60.5

V_DC_V = 200.0
EFFICIENCY = 0.97


class InverterState(Enum):
    OFF = "OFF"
    STANDBY = "STANDBY"
    RUNNING = "RUNNING"
    FAULT = "FAULT"


class InvalidTransitionError(RuntimeError):
    """Raised when a state command is not allowed from the current state."""


def grid_violation(grid: GridState) -> str | None:
    """Return a description of the first out-of-band quantity, or None if healthy.

    Limits are inclusive; NaN counts as a violation (comparisons with NaN are False).
    The L1-L2 check is a safety net (plan A-16).
    """
    checks = (
        ("v_l1n_v", grid.v_l1n_v, V_LN_MIN_V, V_LN_MAX_V, "V"),
        ("v_l2n_v", grid.v_l2n_v, V_LN_MIN_V, V_LN_MAX_V, "V"),
        ("v_l1l2_v", grid.v_l1l2_v, V_LL_MIN_V, V_LL_MAX_V, "V"),
        ("f_hz", grid.f_hz, F_MIN_HZ, F_MAX_HZ, "Hz"),
    )
    for name, value, lo, hi, unit in checks:
        if not lo <= value <= hi:
            return f"{name}={value:.2f} {unit} outside {lo:.2f}-{hi:.2f} {unit}"
    return None


def grid_is_healthy(grid: GridState) -> bool:
    """True if every quantity is inside its band."""
    return grid_violation(grid) is None


class InverterSim:
    """Inverter reading its grid from a GridSim once per step()."""

    def __init__(self, grid: GridSim, rated_power_w: float = 6000.0, ramp_pct_per_s: float = 10.0) -> None:
        if not (math.isfinite(rated_power_w) and rated_power_w > 0):
            raise ValueError(f"rated_power_w must be finite and > 0, got {rated_power_w}")
        self._grid = grid
        self.rated_power_w = rated_power_w
        self.ramp_pct_per_s = ramp_pct_per_s  # validated by the property setter
        self.state = InverterState.OFF
        self.p_ac_w = 0.0
        self.p_setpoint_w = 0.0
        self._winding_down = False  # RUNNING -> STANDBY ramp in progress
        self._v_l1l2_v = grid.read().v_l1l2_v  # from the last grid.read()
        self._t_s = 0.0  # simulated time, only used for log messages

    @property
    def ramp_pct_per_s(self) -> float:
        """Ramp rate in % of rated power per second."""
        return self._ramp_pct_per_s

    @ramp_pct_per_s.setter
    def ramp_pct_per_s(self, value: float) -> None:
        if not (math.isfinite(value) and value > 0):
            raise ValueError(f"ramp_pct_per_s must be finite and > 0, got {value}")
        self._ramp_pct_per_s = value

    def _set_state(self, new: InverterState, why: str) -> None:
        """Change state and log it."""
        logger.info("t=%.3f s state %s -> %s (%s)", self._t_s, self.state.name, new.name, why)
        self.state = new

    # --- commands -----------------------------------------------------
    def set_p_setpoint_w(self, p_w: float) -> None:
        """Store the setpoint clamped to +/- rated power. NaN is rejected."""
        if math.isnan(p_w):
            raise ValueError("setpoint must not be NaN")
        applied_w = max(-self.rated_power_w, min(self.rated_power_w, p_w))
        if applied_w != p_w:
            logger.info("setpoint requested %.1f W, clamped to %.1f W (rated +/-%.0f W)",
                        p_w, applied_w, self.rated_power_w)
        else:
            logger.info("setpoint set to %.1f W", applied_w)
        self.p_setpoint_w = applied_w

    def to_standby(self) -> None:
        """OFF->STANDBY; RUNNING starts a wind-down (STANDBY once p_ac reaches 0)."""
        if self.state is InverterState.OFF:
            self._set_state(InverterState.STANDBY, "to_standby() command")
        elif self.state is InverterState.RUNNING:
            if self.p_ac_w == 0.0:
                self._set_state(InverterState.STANDBY, "to_standby() with p_ac already 0 W")
            else:
                self._winding_down = True
                logger.info("wind-down started from %.1f W at %.0f W/s", self.p_ac_w, self._ramp_w_per_s())
        elif self.state is InverterState.FAULT:
            raise InvalidTransitionError("to_standby() not allowed in FAULT")

    def to_running(self) -> None:
        """STANDBY->RUNNING. In RUNNING it cancels a wind-down."""
        if self.state is InverterState.STANDBY:
            self._set_state(InverterState.RUNNING, "to_running() command")
        elif self.state is InverterState.RUNNING:
            if self._winding_down:
                logger.info("wind-down cancelled by to_running()")
            self._winding_down = False
        else:
            raise InvalidTransitionError(f"to_running() not allowed in {self.state.name}")

    def to_off(self) -> None:
        """STANDBY->OFF only."""
        if self.state is InverterState.STANDBY:
            self._set_state(InverterState.OFF, "to_off() command")
        elif self.state is not InverterState.OFF:
            raise InvalidTransitionError(f"to_off() not allowed in {self.state.name}")

    def reset(self) -> None:
        """Clear a FAULT (to OFF) if the grid is healthy now. No-op outside FAULT."""
        if self.state is not InverterState.FAULT:
            logger.info("reset() ignored: state is %s, not FAULT (no-op)", self.state.name)
            return
        reason = grid_violation(self._grid.read())
        if reason is None:
            self._set_state(InverterState.OFF, "reset() with healthy grid")
            logger.info("reset() succeeded")
        else:
            logger.info("reset() refused, grid unhealthy: %s", reason)

    # --- time ---------------------------------------------------------
    def step(self, dt_s: float) -> None:
        """Advance simulated time: sample the grid, trip if bad, then ramp power."""
        if not (math.isfinite(dt_s) and dt_s >= 0):
            raise ValueError(f"dt_s must be finite and >= 0, got {dt_s}")
        grid = self._grid.read()
        self._v_l1l2_v = grid.v_l1l2_v
        self._t_s += dt_s

        if self.state is not InverterState.FAULT:
            reason = grid_violation(grid)
            if reason is not None:
                logger.info("t=%.3f s TRIP: %s", self._t_s, reason)
                self._set_state(InverterState.FAULT, "grid out of range")
                self._winding_down = False
        if self.state is not InverterState.RUNNING:
            self.p_ac_w = 0.0  # includes FAULT: instant 0 W
            self._log_step(dt_s, 0.0)
            return

        target_w = 0.0 if self._winding_down else self.p_setpoint_w
        max_delta_w = self._ramp_w_per_s() * dt_s
        diff_w = target_w - self.p_ac_w
        snapped = abs(diff_w) <= max_delta_w
        if snapped:
            self.p_ac_w = target_w  # snap: no overshoot or oscillation
        else:
            self.p_ac_w += math.copysign(max_delta_w, diff_w)

        if self._winding_down and snapped:
            self._winding_down = False
            logger.info("t=%.3f s wind-down finished, p_ac = 0 W", self._t_s)
            self._set_state(InverterState.STANDBY, "wind-down complete")
        self._log_step(dt_s, target_w)

    def _ramp_w_per_s(self) -> float:
        return self.rated_power_w * self._ramp_pct_per_s / 100.0

    def _log_step(self, dt_s: float, target_w: float) -> None:
        logger.debug("step t=%.3f s dt=%.3f s state=%s p_ac=%.1f W target=%.1f W i_l1=%.2f A i_dc=%.2f A",
                     self._t_s, dt_s, self.state.name, self.p_ac_w, target_w, self.i_l1_a, self.i_dc_a)

    # --- outputs ------------------------------------------------------
    @property
    def i_l1_a(self) -> float:
        """Leg current, balanced load at the L1-L2 voltage of the last step."""
        if self.p_ac_w == 0.0 or self._v_l1l2_v <= 0:
            return 0.0
        return self.p_ac_w / self._v_l1l2_v

    @property
    def i_l2_a(self) -> float:
        return self.i_l1_a

    @property
    def i_n_a(self) -> float:
        """Neutral current, always 0 for a balanced load."""
        return 0.0

    @property
    def p_dc_w(self) -> float:
        """Battery power: feed-in draws more, charging stores less (losses)."""
        if self.p_ac_w >= 0:
            return self.p_ac_w / EFFICIENCY
        return self.p_ac_w * EFFICIENCY

    @property
    def i_dc_a(self) -> float:
        """Battery current at fixed 200 V; positive = discharging."""
        return self.p_dc_w / V_DC_V
