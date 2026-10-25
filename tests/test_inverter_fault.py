import logging

import pytest

from sim.grid_sim import GridSim
from sim.inverter_sim import InverterSim, InverterState
from tests.helpers import (DT_S, EXACT_TOL, NOMINAL_F_HZ, P_TOL_W, V_COARSE_V,
                           V_EDGE_V, settle)

logger = logging.getLogger(__name__)

# Limits are redeclared here on purpose: the tests must not import them from the
# model, otherwise a wrong limit in the model would also "fix" the test.
V_LN_MIN_V = 105.6
V_LN_MAX_V = 132.0
F_MIN_HZ = 59.3
F_MAX_HZ = 60.5
F_COARSE_HZ = 0.01

LEGS = ["v_l1n_v", "v_l2n_v"]
MARGINS = [pytest.param(V_COARSE_V, id="coarse"), pytest.param(V_EDGE_V, id="edge")]


@pytest.fixture
def run3k(running_inv: InverterSim) -> InverterSim:
    """RUNNING and settled at 3000 W."""
    settle(running_inv, 3000.0)
    assert running_inv.p_ac_w == pytest.approx(3000.0, abs=P_TOL_W)
    assert running_inv.state == InverterState.RUNNING
    return running_inv


def _assert_tripped(inv: InverterSim) -> None:
    logger.info("result: state=%s p_ac=%.1f W, expected FAULT / 0 W", inv.state.name, inv.p_ac_w)
    assert inv.state == InverterState.FAULT
    assert inv.p_ac_w == pytest.approx(0.0, abs=EXACT_TOL)


def test_tc_ft_001_nominal_grid_no_fault(run3k: InverterSim) -> None:
    for _ in range(100):
        run3k.step(DT_S)
    logger.info("TC-FT-001: state after 10 s nominal grid: %s, expected RUNNING", run3k.state.name)
    assert run3k.state == InverterState.RUNNING


@pytest.mark.parametrize("leg", LEGS)
@pytest.mark.parametrize("limit_v, inside_sign", [pytest.param(V_LN_MIN_V, 1, id="low"),
                                                  pytest.param(V_LN_MAX_V, -1, id="high")])
def test_tc_ft_003_edge_inside_is_healthy(grid: GridSim, run3k: InverterSim,
                                          leg: str, limit_v: float, inside_sign: int) -> None:
    value_v = limit_v + inside_sign * V_EDGE_V
    setattr(grid, leg, value_v)
    run3k.step(DT_S)
    logger.info("TC-FT-003: %s=%.6f V (limit %.1f V + edge), state %s, expected RUNNING",
                leg, value_v, limit_v, run3k.state.name)
    assert run3k.state == InverterState.RUNNING


@pytest.mark.parametrize("leg", LEGS)
@pytest.mark.parametrize("margin_v", MARGINS)
def test_tc_ft_004_undervoltage_trips(grid: GridSim, run3k: InverterSim,
                                      leg: str, margin_v: float) -> None:
    value_v = V_LN_MIN_V - margin_v
    setattr(grid, leg, value_v)
    logger.info("TC-FT-004: %s=%.6f V (limit %.1f V)", leg, value_v, V_LN_MIN_V)
    run3k.step(DT_S)
    _assert_tripped(run3k)


@pytest.mark.parametrize("leg", LEGS)
@pytest.mark.parametrize("margin_v", MARGINS)
def test_tc_ft_008_overvoltage_trips(grid: GridSim, run3k: InverterSim,
                                     leg: str, margin_v: float) -> None:
    value_v = V_LN_MAX_V + margin_v
    setattr(grid, leg, value_v)
    logger.info("TC-FT-008: %s=%.6f V (limit %.1f V)", leg, value_v, V_LN_MAX_V)
    run3k.step(DT_S)
    _assert_tripped(run3k)


def test_tc_ft_018_underfrequency_trips(grid: GridSim, run3k: InverterSim) -> None:
    grid.f_hz = F_MIN_HZ - F_COARSE_HZ
    logger.info("TC-FT-018: f=%.2f Hz (limit %.1f Hz)", grid.f_hz, F_MIN_HZ)
    run3k.step(DT_S)
    _assert_tripped(run3k)


def test_tc_ft_020_overfrequency_trips(grid: GridSim, run3k: InverterSim) -> None:
    grid.f_hz = F_MAX_HZ + F_COARSE_HZ
    logger.info("TC-FT-020: f=%.2f Hz (limit %.1f Hz)", grid.f_hz, F_MAX_HZ)
    run3k.step(DT_S)
    _assert_tripped(run3k)


def test_tc_ft_028_trip_zeroes_outputs_instantly(grid: GridSim, running_inv: InverterSim) -> None:
    settle(running_inv, 6000.0)
    assert running_inv.p_ac_w == pytest.approx(6000.0, abs=P_TOL_W)
    assert running_inv.i_dc_a != 0.0  # something to lose
    grid.f_hz = F_MAX_HZ + F_COARSE_HZ
    running_inv.step(DT_S)
    logger.info("TC-FT-028: after trip p_ac=%.1f W i_l1=%.2f A i_l2=%.2f A i_dc=%.2f A, expected all 0",
                running_inv.p_ac_w, running_inv.i_l1_a, running_inv.i_l2_a, running_inv.i_dc_a)
    for value in (running_inv.p_ac_w, running_inv.i_l1_a,
                  running_inv.i_l2_a, running_inv.i_dc_a):
        assert value == pytest.approx(0.0, abs=EXACT_TOL)


def test_tc_ft_032_fault_is_latched(grid: GridSim, run3k: InverterSim) -> None:
    grid.f_hz = F_MAX_HZ + F_COARSE_HZ
    run3k.step(DT_S)
    assert run3k.state == InverterState.FAULT
    grid.f_hz = NOMINAL_F_HZ
    for _ in range(100):
        run3k.step(DT_S)
    logger.info("TC-FT-032: state 10 s after grid recovered: %s, expected FAULT", run3k.state.name)
    assert run3k.state == InverterState.FAULT
