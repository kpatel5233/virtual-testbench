import logging

import pytest

from sim.inverter_sim import InverterSim
from tests.helpers import EXACT_TOL, P_TOL_W, check_ramp, p_at, record, settle

logger = logging.getLogger(__name__)


def test_tc_rp_001_default_ramp_rate(inv: InverterSim) -> None:
    logger.info("TC-RP-001: ramp_pct_per_s=%.1f, expected 10.0", inv.ramp_pct_per_s)
    assert inv.ramp_pct_per_s == pytest.approx(10.0, abs=EXACT_TOL)


def test_tc_rp_002_ramp_up(running_inv: InverterSim) -> None:
    running_inv.set_p_setpoint_w(6000.0)
    samples = record(running_inv, 10.0)
    for t_s, p_w in ((1.0, 600.0), (5.0, 3000.0), (10.0, 6000.0)):
        logger.info("TC-RP-002: p(%.1f s)=%.1f W, expected %.0f +/- %.0f W",
                    t_s, p_at(samples, t_s), p_w, P_TOL_W)
        assert p_at(samples, t_s) == pytest.approx(p_w, abs=P_TOL_W)
    check_ramp(samples, 6000.0, arrival_s=10.0)


def test_tc_rp_003_ramp_down(running_inv: InverterSim) -> None:
    settle(running_inv, 6000.0)
    running_inv.set_p_setpoint_w(0.0)
    samples = record(running_inv, 10.0)
    logger.info("TC-RP-003: p(5.0 s)=%.1f W, expected 3000 +/- %.0f W", p_at(samples, 5.0), P_TOL_W)
    assert p_at(samples, 5.0) == pytest.approx(3000.0, abs=P_TOL_W)
    check_ramp(samples, 0.0, arrival_s=10.0)


def test_tc_rp_004_ramp_through_zero(running_inv: InverterSim) -> None:
    settle(running_inv, 6000.0)
    running_inv.set_p_setpoint_w(-6000.0)
    samples = record(running_inv, 20.0)
    logger.info("TC-RP-004: p(10 s)=%.1f W (expected 0), p(20 s)=%.1f W (expected -6000), tol %.0f W",
                p_at(samples, 10.0), p_at(samples, 20.0), P_TOL_W)
    assert p_at(samples, 10.0) == pytest.approx(0.0, abs=P_TOL_W)
    assert p_at(samples, 20.0) == pytest.approx(-6000.0, abs=P_TOL_W)
    check_ramp(samples, -6000.0, arrival_s=20.0)


def test_tc_rp_010_ramp_restarts_from_zero(inv: InverterSim) -> None:
    inv.to_standby()
    inv.set_p_setpoint_w(6000.0)
    inv.to_running()
    inv.step(1.0)
    logger.info("TC-RP-010: p(1 s)=%.1f W, expected 600 +/- %.0f W", inv.p_ac_w, P_TOL_W)
    assert inv.p_ac_w == pytest.approx(600.0, abs=P_TOL_W)
