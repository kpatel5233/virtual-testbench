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

## System under development: residential storage system (US market)
- Inverter: 6 kW hybrid, split phase 120/240 V, 60 Hz (L1, L2, N), battery side 200 V nominal (HV)
- Battery: 2 modules × 100 V nominal, connected in series = 200 V nominal
- BMS: one BMS for the string of 2 modules (module details defined in step 3)
- EMS: controls setpoints
- Bus: RS485 / Modbus RTU,  baud, 8N1. EMS = master, inverter = slave ID 1, BMS = slave ID 2
- Sign convention: P_ac > 0 = inverter exports to AC (battery discharging), P_ac < 0 = charging
- Build step by step. Only build what the current step asks for.