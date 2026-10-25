import logging

import pytest

from sim.inverter_sim import InverterSim
from tests.helpers import EXACT_TOL

logger = logging.getLogger(__name__)


def _check(inv: InverterSim, tc: str, requested_w: float, expected_w: float) -> None:
    inv.set_p_setpoint_w(requested_w)
    logger.info("%s: requested %.1f W -> setpoint %.1f W, expected %.1f W",
                tc, requested_w, inv.p_setpoint_w, expected_w)
    assert inv.p_setpoint_w == pytest.approx(expected_w, abs=EXACT_TOL)


def test_tc_sp_002_setpoint_stored(running_inv: InverterSim) -> None:
    _check(running_inv, "TC-SP-002", 3000.0, 3000.0)


def test_tc_sp_004_positive_limit(running_inv: InverterSim) -> None:
    _check(running_inv, "TC-SP-004", 6000.0, 6000.0)


def test_tc_sp_005_negative_limit(running_inv: InverterSim) -> None:
    _check(running_inv, "TC-SP-005", -6000.0, -6000.0)


def test_tc_sp_006_clamp_above(running_inv: InverterSim) -> None:
    _check(running_inv, "TC-SP-006", 6000.1, 6000.0)


def test_tc_sp_007_clamp_below(running_inv: InverterSim) -> None:
    _check(running_inv, "TC-SP-007", -6000.1, -6000.0)
