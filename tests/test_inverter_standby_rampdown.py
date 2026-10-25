import logging

import pytest

from sim.inverter_sim import InverterSim, InverterState
from tests.helpers import (DT_S, EXACT_TOL, P_TOL_W, TIME_EPS_S, check_ramp,
                           p_at, record, settle)

logger = logging.getLogger(__name__)


def test_tc_sb_001_winddown_ramps_to_zero(running_inv: InverterSim) -> None:
    settle(running_inv, 3000.0)
    running_inv.to_standby()
    assert running_inv.p_ac_w == pytest.approx(3000.0, abs=P_TOL_W)  # no instant drop
    samples = record(running_inv, 5.0)
    logger.info("TC-SB-001: p(2.5 s)=%.1f W, expected 1500 +/- %.0f W", p_at(samples, 2.5), P_TOL_W)
    assert p_at(samples, 2.5) == pytest.approx(1500.0, abs=P_TOL_W)
    check_ramp(samples, 0.0, arrival_s=5.0)


def test_tc_sb_002_state_follows_power(running_inv: InverterSim) -> None:
    settle(running_inv, 3000.0)
    running_inv.to_standby()
    first_standby_t = None
    for i in range(1, 61):
        running_inv.step(DT_S)
        t = i * DT_S
        # STANDBY exactly when power has reached 0.
        is_standby = running_inv.state == InverterState.STANDBY
        assert is_standby == (abs(running_inv.p_ac_w) <= EXACT_TOL)
        if is_standby:
            if first_standby_t is None:
                first_standby_t = t
        else:
            assert first_standby_t is None  # never leaves STANDBY again
            assert running_inv.state == InverterState.RUNNING
        if running_inv.p_ac_w > P_TOL_W:
            assert running_inv.state == InverterState.RUNNING
    logger.info("TC-SB-002: STANDBY first seen at %s s, expected 5.0 +/- %.1f s", first_standby_t, DT_S)
    assert first_standby_t is not None
    assert abs(first_standby_t - 5.0) <= DT_S + TIME_EPS_S


def test_tc_sb_006_setpoint_during_winddown_does_not_stop_it(running_inv: InverterSim) -> None:
    settle(running_inv, 3000.0)
    running_inv.to_standby()
    samples = record(running_inv, 2.5)
    assert running_inv.p_ac_w == pytest.approx(1500.0, abs=P_TOL_W)
    running_inv.set_p_setpoint_w(6000.0)
    logger.info("TC-SB-006: setpoint written mid wind-down at p=%.1f W -> p_setpoint=%.1f W",
                running_inv.p_ac_w, running_inv.p_setpoint_w)
    assert running_inv.p_setpoint_w == pytest.approx(6000.0, abs=EXACT_TOL)
    rest = record(running_inv, 3.0)[1:]
    samples += [(2.5 + t, p) for t, p in rest]
    for (_, p0), (_, p1) in zip(samples, samples[1:]):
        assert p1 <= p0 + EXACT_TOL  # never increases
    check_ramp(samples, 0.0, arrival_s=5.0)
    logger.info("TC-SB-006: final state %s, expected STANDBY", running_inv.state.name)
    assert running_inv.state == InverterState.STANDBY
