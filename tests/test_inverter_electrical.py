import logging

import pytest

from sim.grid_sim import GridSim
from sim.inverter_sim import InverterSim
from tests.helpers import I_TOL_A, settle

logger = logging.getLogger(__name__)


def test_tc_el_002_currents_at_6000w(running_inv: InverterSim) -> None:
    settle(running_inv, 6000.0)
    logger.info("TC-EL-002: i_l1=%.2f A i_l2=%.2f A, expected 25.00 +/- %.2f A",
                running_inv.i_l1_a, running_inv.i_l2_a, I_TOL_A)
    assert running_inv.i_l1_a == pytest.approx(25.0, abs=I_TOL_A)
    assert running_inv.i_l2_a == pytest.approx(25.0, abs=I_TOL_A)


def test_tc_el_005_currents_when_charging(running_inv: InverterSim) -> None:
    settle(running_inv, -6000.0)
    logger.info("TC-EL-005: i_l1=%.2f A i_l2=%.2f A, expected -25.00 +/- %.2f A",
                running_inv.i_l1_a, running_inv.i_l2_a, I_TOL_A)
    assert running_inv.i_l1_a == pytest.approx(-25.0, abs=I_TOL_A)
    assert running_inv.i_l2_a == pytest.approx(-25.0, abs=I_TOL_A)


def test_tc_el_008_current_uses_actual_l1l2_voltage(grid: GridSim, running_inv: InverterSim) -> None:
    """Added after reviewer round 1 (gap found by the reviewer; not a CORE test)."""
    grid.v_l1n_v = 114.0
    grid.v_l2n_v = 114.0  # L1-L2 = 228 V, still inside the healthy band
    settle(running_inv, 6000.0)
    logger.info("TC-EL-008: L1-L2=%.0f V, i_l1=%.3f A i_l2=%.3f A, expected 26.316 +/- %.2f A",
                grid.v_l1l2_v, running_inv.i_l1_a, running_inv.i_l2_a, I_TOL_A)
    assert running_inv.i_l1_a == pytest.approx(6000.0 / 228.0, abs=I_TOL_A)
    assert running_inv.i_l2_a == pytest.approx(6000.0 / 228.0, abs=I_TOL_A)
