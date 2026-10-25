import logging

import pytest

from sim.inverter_sim import InverterSim
from tests.helpers import I_TOL_A, settle

logger = logging.getLogger(__name__)

P_DC_TOL_W = 0.5


def test_tc_bt_001_feed_in(running_inv: InverterSim) -> None:
    settle(running_inv, 6000.0)
    logger.info("TC-BT-001: p_dc=%.2f W (expected 6185.57 +/- %.1f), i_dc=%.2f A (expected 30.93 +/- %.2f)",
                running_inv.p_dc_w, P_DC_TOL_W, running_inv.i_dc_a, I_TOL_A)
    assert running_inv.p_dc_w == pytest.approx(6185.57, abs=P_DC_TOL_W)
    assert running_inv.i_dc_a == pytest.approx(30.93, abs=I_TOL_A)


def test_tc_bt_003_charging(running_inv: InverterSim) -> None:
    settle(running_inv, -6000.0)
    logger.info("TC-BT-003: p_dc=%.2f W (expected -5820.00 +/- %.1f), i_dc=%.2f A (expected -29.10 +/- %.2f)",
                running_inv.p_dc_w, P_DC_TOL_W, running_inv.i_dc_a, I_TOL_A)
    assert running_inv.p_dc_w == pytest.approx(-5820.0, abs=P_DC_TOL_W)
    assert running_inv.i_dc_a == pytest.approx(-29.10, abs=I_TOL_A)
