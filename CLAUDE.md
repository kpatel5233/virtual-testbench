# Virtual Test Bench

Learning project: simulated inverter / EV charger + pytest test framework. No real hardware.

## Layout
- `sim/` simulators (grid, inverter, EVSE, fake SCPI instruments)
- `framework/drivers/` one interface per device type, real or simulated
- `tests/` pytest suites
- `docs/test_plans/` written by the test-planner agent

## Team workflow
test-planner -> coder -> reviewer. Ask mentor for explanations.

## Conventions
- Python 3.11+, pytest, type hints
- Power sign: positive = feed-in to grid
- Units in variable names: `p_w`, `f_hz`, `ramp_pct_per_s`
