"""Fixtures: nominal grid, OFF inverter, RUNNING inverter at 0 W.

How to run (log output is on by default, see pyproject.toml):
    python -m pytest                                                   # INFO log per test
    python -m pytest --log-cli-level=DEBUG tests/test_inverter_ramp.py # every step()
    python -m pytest -k tc_ft                                          # only fault tests
"""
import pytest

from sim.grid_sim import GridSim
from sim.inverter_sim import InverterSim


@pytest.fixture
def grid() -> GridSim:
    return GridSim()


@pytest.fixture
def inv(grid: GridSim) -> InverterSim:
    return InverterSim(grid)


@pytest.fixture
def running_inv(inv: InverterSim) -> InverterSim:
    inv.to_standby()
    inv.to_running()
    return inv
