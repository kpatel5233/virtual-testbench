import logging

import pytest

from sim.inverter_sim import InverterSim, InverterState
from tests.helpers import EXACT_TOL, RATED_W, SNAP_TOL

logger = logging.getLogger(__name__)


def test_tc_tm_002_negative_dt_rejected(running_inv: InverterSim) -> None:
    running_inv.set_p_setpoint_w(6000.0)
    with pytest.raises(ValueError):
        running_inv.step(-0.1)
    logger.info("TC-TM-002: step(-0.1) raised ValueError; p_ac=%.1f W state=%s",
                running_inv.p_ac_w, running_inv.state.name)
    assert running_inv.p_ac_w == pytest.approx(0.0, abs=EXACT_TOL)
    assert running_inv.state == InverterState.RUNNING


def test_tc_tm_004_huge_step_no_overshoot(running_inv: InverterSim) -> None:
    running_inv.set_p_setpoint_w(6000.0)
    running_inv.step(1000.0)
    logger.info("TC-TM-004: p_ac after step(1000)=%.3f W, expected 6000 (max %.0f W)",
                running_inv.p_ac_w, RATED_W)
    assert running_inv.p_ac_w == pytest.approx(6000.0, abs=SNAP_TOL)
    assert running_inv.p_ac_w <= RATED_W + SNAP_TOL


@pytest.mark.parametrize(
    "dts, expected_w",
    [
        pytest.param([0.01] * 1000, 6000.0, id="A-1000x0.01-at-10s"),
        pytest.param([0.1] * 100, 6000.0, id="B-100x0.1-at-10s"),
        pytest.param([10.0], 6000.0, id="C-1x10-at-10s"),
        pytest.param([3.0, 3.0, 3.0, 1.0], 6000.0, id="D-3-3-3-1-at-10s"),
        pytest.param([0.01] * 500, 3000.0, id="A-500x0.01-at-5s"),
        pytest.param([0.1] * 50, 3000.0, id="B-50x0.1-at-5s"),
        pytest.param([5.0], 3000.0, id="E-1x5-at-5s"),
    ],
)
def test_tc_tm_007_step_size_independence(
    running_inv: InverterSim, dts: list[float], expected_w: float
) -> None:
    running_inv.set_p_setpoint_w(6000.0)
    for dt_s in dts:
        running_inv.step(dt_s)
    logger.info("TC-TM-007: %d steps, t=%.2f s, p_ac=%.6f W, expected %.1f +/- %.0e W",
                len(dts), sum(dts), running_inv.p_ac_w, expected_w, SNAP_TOL)
    assert running_inv.p_ac_w == pytest.approx(expected_w, abs=SNAP_TOL)
