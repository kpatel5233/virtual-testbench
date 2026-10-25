"""Split-phase grid simulator (120/240 V, 60 Hz) for the inverter model."""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GridState:
    """Immutable snapshot of the grid at one instant."""

    v_l1n_v: float
    v_l2n_v: float
    v_l1l2_v: float
    f_hz: float


class GridSim:
    """Settable grid. L1-L2 is derived so it can never disagree with L1-N/L2-N."""

    def __init__(self, v_l1n_v: float = 120.0, v_l2n_v: float = 120.0, f_hz: float = 60.0) -> None:
        self.v_l1n_v = v_l1n_v
        self.v_l2n_v = v_l2n_v
        self.f_hz = f_hz

    @property
    def v_l1l2_v(self) -> float:
        """Line-to-line voltage, read-only: sum of the two leg voltages."""
        return self.v_l1n_v + self.v_l2n_v

    def read(self) -> GridState:
        """Return a frozen snapshot; later grid changes do not affect it."""
        state = GridState(self.v_l1n_v, self.v_l2n_v, self.v_l1l2_v, self.f_hz)
        logger.debug("grid read: L1-N=%.2f V L2-N=%.2f V L1-L2=%.2f V f=%.3f Hz",
                     state.v_l1n_v, state.v_l2n_v, state.v_l1l2_v, state.f_hz)
        return state
