import logging

import pytest

from sim.grid_sim import GridSim
from tests.helpers import EXACT_TOL

logger = logging.getLogger(__name__)


def test_tc_gr_001_defaults() -> None:
    g = GridSim()
    logger.info("TC-GR-001: defaults L1-N=%.1f V L2-N=%.1f V f=%.1f Hz (expected 120/120/60)",
                g.v_l1n_v, g.v_l2n_v, g.f_hz)
    assert g.v_l1n_v == pytest.approx(120.0, abs=EXACT_TOL)
    assert g.v_l2n_v == pytest.approx(120.0, abs=EXACT_TOL)
    assert g.f_hz == pytest.approx(60.0, abs=EXACT_TOL)


def test_tc_gr_003_l1l2_default_is_sum() -> None:
    v_l1l2_v = GridSim().v_l1l2_v
    logger.info("TC-GR-003: L1-L2=%.1f V, expected 240.0 V", v_l1l2_v)
    assert v_l1l2_v == pytest.approx(240.0, abs=EXACT_TOL)
