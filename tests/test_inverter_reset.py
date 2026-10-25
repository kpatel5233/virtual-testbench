import logging

import pytest

from sim.grid_sim import GridSim
from sim.inverter_sim import InverterSim, InverterState
from tests.helpers import (DT_S, EXACT_TOL, OVER_FREQ_HZ, P_TOL_W, check_ramp,
                           p_at, record, settle, trip)

logger = logging.getLogger(__name__)


def test_tc_rs_001_reset_with_healthy_grid(grid: GridSim, running_inv: InverterSim) -> None:
    trip(grid, running_inv)
    running_inv.reset()
    logger.info("TC-RS-001: after reset state=%s p_ac=%.1f W, expected OFF / 0 W",
                running_inv.state.name, running_inv.p_ac_w)
    assert running_inv.state == InverterState.OFF
    assert running_inv.p_ac_w == pytest.approx(0.0, abs=EXACT_TOL)


def test_tc_rs_002_normal_operation_after_reset(grid: GridSim, running_inv: InverterSim) -> None:
    trip(grid, running_inv)
    running_inv.reset()
    assert running_inv.state == InverterState.OFF
    running_inv.to_standby()
    running_inv.to_running()
    running_inv.set_p_setpoint_w(3000.0)
    samples = record(running_inv, 5.0)
    logger.info("TC-RS-002: p(5 s)=%.1f W, expected 3000 +/- %.0f W", p_at(samples, 5.0), P_TOL_W)
    assert p_at(samples, 5.0) == pytest.approx(3000.0, abs=P_TOL_W)
    check_ramp(samples, 3000.0, arrival_s=5.0)


def test_tc_rs_003_reset_refused_while_grid_bad(grid: GridSim, running_inv: InverterSim) -> None:
    settle(running_inv, 3000.0)  # non-zero power so the 0 W check below means something
    grid.f_hz = OVER_FREQ_HZ
    running_inv.step(DT_S)
    assert running_inv.state == InverterState.FAULT
    running_inv.reset()  # must not raise
    logger.info("TC-RS-003: reset with bad grid -> state=%s p_ac=%.1f W, expected FAULT / 0 W",
                running_inv.state.name, running_inv.p_ac_w)
    assert running_inv.state == InverterState.FAULT
    assert running_inv.p_ac_w == pytest.approx(0.0, abs=EXACT_TOL)


def test_tc_rs_006_reset_outside_fault_is_noop(running_inv: InverterSim) -> None:
    settle(running_inv, 3000.0)
    running_inv.reset()
    logger.info("TC-RS-006: reset in RUNNING -> state=%s p_ac=%.1f W setpoint=%.1f W, expected unchanged",
                running_inv.state.name, running_inv.p_ac_w, running_inv.p_setpoint_w)
    assert running_inv.state == InverterState.RUNNING
    assert running_inv.p_ac_w == pytest.approx(3000.0, abs=EXACT_TOL)
    assert running_inv.p_setpoint_w == pytest.approx(3000.0, abs=EXACT_TOL)
