import logging

import pytest

from sim.inverter_sim import InverterSim, InverterState
from tests.helpers import EXACT_TOL, P_TOL_W

logger = logging.getLogger(__name__)


def test_tc_st_001_initial_state_off(inv: InverterSim) -> None:
    logger.info("TC-ST-001: initial state %s, expected OFF", inv.state.name)
    assert inv.state == InverterState.OFF


def test_tc_st_002_off_to_standby(inv: InverterSim) -> None:
    inv.to_standby()
    logger.info("TC-ST-002: after to_standby() state %s, expected STANDBY", inv.state.name)
    assert inv.state == InverterState.STANDBY


def test_tc_st_003_standby_to_running(inv: InverterSim) -> None:
    inv.to_standby()
    inv.to_running()
    logger.info("TC-ST-003: after to_running() state %s, expected RUNNING", inv.state.name)
    assert inv.state == InverterState.RUNNING


def test_tc_st_006_no_power_in_standby(inv: InverterSim) -> None:
    inv.to_standby()
    inv.set_p_setpoint_w(6000.0)
    for _ in range(10):
        inv.step(1.0)
        assert inv.p_ac_w == pytest.approx(0.0, abs=EXACT_TOL)
    logger.info("TC-ST-006: STANDBY with setpoint 6000 W, p_ac=%.1f W after 10 s, expected 0", inv.p_ac_w)


def test_tc_st_008_power_flows_in_running(running_inv: InverterSim) -> None:
    running_inv.set_p_setpoint_w(6000.0)
    running_inv.step(1.0)
    logger.info("TC-ST-008: p_ac(1 s)=%.1f W, expected 600 +/- %.0f W", running_inv.p_ac_w, P_TOL_W)
    assert running_inv.p_ac_w == pytest.approx(600.0, abs=P_TOL_W)
