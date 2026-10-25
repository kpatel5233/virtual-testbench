# Test Plan: Step 1 - Pure Python Inverter Model (`sim/inverter_sim.py`)

Status: REVISION 3 (Keyur's decisions incorporated: grid object, derived L1-L2, edge handling, STANDBY ramp-down, instant trip, battery sign/efficiency, reset() behaviour, setpoint during wind-down, L-L safety net). Planner does not write code.

## 1. Requirement (one sentence)
A communication-free Python model of a 6 kW split-phase (120/240 V, 60 Hz) hybrid inverter that reads its grid from a separate `GridSim` object, clamps its power setpoint to +/-6000 W, moves through OFF/STANDBY/RUNNING/FAULT, ramps P_ac at a configurable rate (default 10 %/s of rated) including on the way to STANDBY, reports AC leg currents and battery-side current (200 V, 97 % efficiency), trips to a latched FAULT on out-of-range grid voltage or frequency, and advances only through `step(dt)` in simulated time.

## 2. Assumed interface (names are placeholders; coder may rename, tests must follow)

| Item | Assumed name |
|---|---|
| Grid class | `GridSim` in `sim/grid_sim.py`; constructor `GridSim(v_l1n_v=120.0, v_l2n_v=120.0, f_hz=60.0)` |
| Grid settable attributes | `grid.v_l1n_v`, `grid.v_l2n_v`, `grid.f_hz` (plain read/write properties, for tests) |
| Grid derived | `grid.v_l1l2_v` (read-only property) = `v_l1n_v + v_l2n_v` |
| Grid snapshot (DECISION: method, not properties) | `grid.read() -> GridState`, where `GridState` is a frozen dataclass with `v_l1n_v`, `v_l2n_v`, `v_l1l2_v`, `f_hz`. The inverter calls `grid.read()` once per `step()`; it never reads grid attributes directly. |
| Inverter constructor | `InverterSim(grid: GridSim, rated_power_w=6000.0, ramp_pct_per_s=10.0)` |
| Setpoint | `set_p_setpoint_w(p_w)`; read back `p_setpoint_w` (the clamped value) |
| State | `state` (enum `InverterState`: OFF, STANDBY, RUNNING, FAULT) |
| State commands | `to_standby()`, `to_running()`, `to_off()` |
| Time | `step(dt_s)` |
| Fault latch clear | `reset()` |
| Outputs | `p_ac_w`, `i_l1_a`, `i_l2_a`, `i_n_a`, `p_dc_w`, `i_dc_a` (grid voltages/frequency are read from the grid object, not duplicated on the inverter) |

## 3. Global assumptions and decisions
Items marked CONFIRMED were decided by Keyur; the rest are planner assumptions (some still listed in section 10).
- A-01 Sign: P_ac > 0 = export to AC (battery discharging); P_ac < 0 = charging. Per CLAUDE.md.
- A-02 CONFIRMED: battery current `i_dc_a` is positive when discharging / feeding in (same sign as `p_ac_w`), negative when charging. `i_dc_a = p_dc_w / 200`.
- A-03 CONFIRMED: feed-in / discharge `p_dc_w = p_ac_w / 0.97`; charging `p_dc_w = p_ac_w * 0.97`. At P_ac = 0, p_dc = 0 (no standby losses).
- A-04 CONFIRMED: battery voltage fixed at 200 V (no SoC model in step 1).
- A-05 AC load is balanced at the grid's L1-L2 voltage: `i_l1_a = i_l2_a = p_ac_w / v_l1l2_v` (value from the last `grid.read()`), same sign as P_ac, `i_n_a = 0`. With p_ac = 0 all currents are 0 (OQ-10).
- A-06 Initial state: OFF, p_ac = 0, setpoint 0. Default `GridSim` is 120/120 V, 60 Hz, L1-L2 = 240 V.
- A-07 Trip is evaluated once per `step()` on the `grid.read()` snapshot, in every state except FAULT (OFF and STANDBY included). It is INSTANTANEOUS: no clearing time, FAULT after the very `step()` that sees the bad grid. (IEEE 1547 / UL 1741 SB clearing times and ride-through are a later step; see section 8.)
- A-08 Limits: voltage healthy band 88 %..110 % of nominal per quantity (L1-N and L2-N 105.6..132.0 V, L1-L2 211.2..264.0 V), frequency 59.3..60.5 Hz. Values exactly on a limit are HEALTHY; only strictly outside trips. Any one violating quantity trips.
- A-09 FAULT: `p_ac_w` becomes 0 immediately (no ramp), all currents 0.
- A-10 Allowed transitions: OFF->STANDBY, STANDBY->RUNNING, RUNNING->STANDBY (via ramp-down, A-14), STANDBY->OFF, any non-FAULT state->FAULT (automatic). FAULT->OFF only via `reset()`. OFF->RUNNING and RUNNING->OFF (direct) are rejected with an exception (OQ-3).
- A-11 CONFIRMED `reset()`: in FAULT it succeeds only if the current `grid.read()` is within range; then state = OFF and p_ac = 0. If the grid is still out of range it stays FAULT (no exception). Calling `reset()` when NOT in FAULT is a no-op: state, p_ac and setpoint unchanged, no exception.
- A-12 Ramp acts on P_ac, linear, rate = `rated * ramp_pct_per_s / 100` W/s (default 600 W/s), symmetric up/down and through zero.
- A-13 Invalid inputs (ramp rate <= 0 or NaN, negative/NaN/inf dt, NaN setpoint) raise `ValueError`. Out-of-range setpoints clamp.
- A-14 CONFIRMED wind-down: `to_standby()` while RUNNING starts a wind-down: p_ac ramps to 0 at the configured ramp rate. `state` REPORTS RUNNING during the wind-down and becomes STANDBY in the `step()` in which p_ac_w reaches 0 (if p_ac is already 0 at the call, STANDBY immediately). A setpoint written during wind-down is NOT ignored: it is stored (clamped, `p_setpoint_w` reflects it at once) and applied when the inverter returns to RUNNING; it does NOT stop or alter the wind-down. A FAULT during wind-down drops p_ac to 0 instantly.
- A-15 Float edge handling: because `0.88 * 120.0 != 105.6` in binary floating point, NO test sets a grid value exactly on a limit. Edge tests use a margin of 1e-6 V / 1e-6 Hz inside (must be healthy) or outside (must trip); coarse tests use +/-0.1 V (L-N), +/-0.01 Hz. Any test comparing a limit constant uses `pytest.approx(105.6, abs=1e-9)`.
- A-16 CONFIRMED L1-L2 trip check is kept as a safety net. Because L1-L2 is derived (`v_l1n_v + v_l2n_v`), if L1-N and L2-N are each inside 88..110 % their sum is automatically inside 211.2..264.0 V, so the L-L check can never be the sole cause of a trip; it is reachable only when an L-N check also trips. Tests TC-FT-013..016 keep it covered through L-N values and assert the resulting FAULT (they cannot prove which check fired).

## 4. Common conventions for all tests
- Tolerance base: rated power 6000 W. `P_TOL_W = 0.001 * 6000 = 6 W` (0.1 % of rated, NOT of the measured value) unless stated. Exact arithmetic cases may use `pytest.approx(x, abs=1e-6)`.
- Currents `abs=0.01 A`. Pass-through voltages/frequencies `abs=1e-9`. Always `pytest.approx(..., abs=...)`; never `==` on floats; no `rel=` for values that can be 0.
- Time: simulated only. No `time.sleep`, no wall clock. Default `dt_s = 0.1`.
- Fixture `grid`: fresh `GridSim()` nominal. Fixture `inv`: `InverterSim(grid)` in OFF. Fixture `running_inv`: brought to RUNNING with `to_standby()`, `to_running()`, p_ac = 0. Tests change the grid only via `grid.v_l1n_v`, `grid.v_l2n_v`, `grid.f_hz`, then call `step()`.
- Ramp limit `R = 600 W/s` at default.
- Tag `[CORE]` on an ID = coder implements first (section 7). Untagged = implement afterwards.

## 5. Test cases

### 5.0 GridSim (TC-GR)
| ID | Stimulus | Expected | Pass/fail |
|---|---|---|---|
| TC-GR-001 [CORE] | `GridSim()` defaults | v_l1n 120.0, v_l2n 120.0, f 60.0 | approx abs 1e-9 |
| TC-GR-002 | `GridSim(v_l1n_v=125, v_l2n_v=118, f_hz=59.9)` | values echoed | abs 1e-9 |
| TC-GR-003 [CORE] | Read `v_l1l2_v` defaults | 240.0 (= 120 + 120) | abs 1e-9 |
| TC-GR-004 | Set `v_l1n_v=110`, `v_l2n_v=130` | `v_l1l2_v` = 240.0 (follows sum, not hardcoded) | abs 1e-9 |
| TC-GR-005 | Set `v_l1n_v=100` then read `v_l1l2_v` | 220.0 (derived updates immediately) | abs 1e-9 |
| TC-GR-006 | Assign `grid.v_l1l2_v = 250` | `AttributeError` (read-only) | raises |
| TC-GR-007 | `grid.read()` after setting L1=126, L2=124, f=60.2 | `GridState(126, 124, 250, 60.2)` | abs 1e-9 each |
| TC-GR-008 | Mutate grid after `read()` | Previously returned `GridState` unchanged (frozen snapshot) | old values intact; assigning to a GridState field raises |
| TC-GR-009 | Inverter reads grid per `step()` | Change grid, no `step()`: state unchanged; after `step()` reacts | RUNNING before, FAULT after |

### 5.1 Setpoint and clamp (TC-SP)
| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-SP-001 | Fresh `inv` | Read `p_setpoint_w` | 0.0 | abs 1e-9 |
| TC-SP-002 [CORE] | RUNNING | set 3000 W | `p_setpoint_w` = 3000 | abs 1e-9 |
| TC-SP-003 | RUNNING | set -3000 W | -3000 | abs 1e-9 |
| TC-SP-004 [CORE] | RUNNING | set +6000 W (limit) | 6000 | abs 1e-9 |
| TC-SP-005 [CORE] | RUNNING | set -6000 W (limit) | -6000 | abs 1e-9 |
| TC-SP-006 [CORE] | RUNNING | set 6000.1 W (just outside) | 6000 | abs 1e-9 |
| TC-SP-007 [CORE] | RUNNING | set -6000.1 W | -6000 | abs 1e-9 |
| TC-SP-008 | RUNNING | set 5999.9 W (just inside) | 5999.9 | abs 1e-9 |
| TC-SP-009 | RUNNING | set 1e9 then -1e9 | 6000, then -6000; no exception | abs 1e-9 |
| TC-SP-010 | RUNNING | set `inf`, `-inf` | clamp to +/-6000 (OQ-5) | abs 1e-9 |
| TC-SP-011 | RUNNING | set `nan` | `ValueError`; setpoint unchanged | raises, old value kept |
| TC-SP-012 | RUNNING, p=2000 | set 9000, run 20 s | p settles 6000; max(p_ac) <= 6006 | bound |
| TC-SP-013 | OFF | set 3000 W, `step(1)` x10 | Stored; p_ac stays 0 | p = 0 at every sample |

### 5.2 State machine (TC-ST)
| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-ST-001 [CORE] | Fresh | read state | OFF | == OFF |
| TC-ST-002 [CORE] | OFF | `to_standby()` | STANDBY | == STANDBY |
| TC-ST-003 [CORE] | STANDBY | `to_running()` | RUNNING | == RUNNING |
| TC-ST-004 | STANDBY | `to_off()` | OFF | == OFF |
| TC-ST-005 | OFF | `to_running()` | Rejected (exception, OQ-3); state OFF | raises |
| TC-ST-006 [CORE] | STANDBY, setpoint 6000 | 10 x `step(1.0)` | p_ac = 0 throughout | abs 1e-9 each |
| TC-ST-007 | OFF, setpoint 6000 | 10 x `step(1.0)` | p_ac = 0 throughout | abs 1e-9 each |
| TC-ST-008 [CORE] | RUNNING, setpoint 6000 | `step(1.0)` | p_ac = 600 W (flow only in RUNNING) | abs 6 W |
| TC-ST-009 | RUNNING | `to_off()` direct | Rejected (OQ-3); state RUNNING | raises |
| TC-ST-010 | FAULT | `to_standby()`, `to_running()`, `to_off()` | All rejected; state FAULT | raises x3 |
| TC-ST-011 | Each of OFF, STANDBY, RUNNING | out-of-range grid, `step(0.1)` | FAULT from each | parametrised |
| TC-ST-012 | RUNNING | `to_running()` again | No-op, no error | state/p unchanged |
| TC-ST-013 | RUNNING, p=0, setpoint 0 | `to_standby()` | STANDBY immediately (A-14) | == STANDBY |

### 5.3 RUNNING -> STANDBY wind-down (TC-SB)
All with `R = 600 W/s`, samples every 0.1 s; ramp criteria R1-R4 of section 5.4 apply (target 0).

| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-SB-001 [CORE] | RUNNING settled 3000 W | `to_standby()` then `step(0.1)` x50 | p(t) = 3000 - 600 t; p(2.5 s)=1500, reaches 0 at 5.0 s +/- 0.1 s; no instant drop (p right after the call, before stepping, = 3000 +/- 6) | abs 6 W; R1-R4 |
| TC-SB-002 [CORE] | Same | Observe `state` per sample | RUNNING for all samples while p_ac > 0; STANDBY from the step in which p_ac = 0 (within one dt of t=5.0 s); never STANDBY while p_ac > 6 W | state/time check |
| TC-SB-003 | RUNNING settled 6000 W | `to_standby()` | Reaches 0 at 10.0 s +/- 0.1 | R1-R4 |
| TC-SB-004 | RUNNING settled -6000 W (charging) | `to_standby()` | Ramps up to 0 at 600 W/s; STANDBY at 10.0 s +/- 0.1; never above 0 + 6 W | R1-R4 |
| TC-SB-005 | RUNNING, mid-ramp up at p=2400 | `to_standby()` | Immediately reverses; ramps down 600 W/s; STANDBY 4.0 s later +/- 0.1 | no jump; R1, R3 |
| TC-SB-006 [CORE] | Wind-down in progress from 3000 W, p=1500 (t=2.5 s), setpoint was 3000 | `set_p_setpoint_w(6000)` mid-wind-down | `p_setpoint_w` = 6000 immediately; the wind-down is NOT stopped or altered: p keeps falling at 600 W/s, reaches 0 at 5.0 s +/- 0.1 s, state STANDBY, p never increases | setpoint abs 1e-9; p monotone non-increasing; R1, R2 |
| TC-SB-007 | Same as TC-SB-006, then complete the wind-down, `to_running()`, step 1 s | Stored setpoint applied after return to RUNNING | p ramps from 0 toward 6000: p(1 s) = 600 +/- 6 W; reaches 6000 at 10 s +/- 0.1 | R1-R4 |
| TC-SB-008 | Wind-down, p=1500 | grid trip | FAULT, p = 0 instantly (not ramped) | p abs 1e-9 on that step |
| TC-SB-009 | Wind-down completed (STANDBY), setpoint 3000 | `to_running()`, step 1 s | Ramp restarts from 0: p(1 s)=600 +/- 6 | abs 6 W |
| TC-SB-010 | Wind-down | `to_off()` while still RUNNING | Rejected (OQ-3); wind-down continues | raises, p still decreasing |
| TC-SB-011 | Wind-down, one `step(1000)` | huge step | p = 0 exactly, state STANDBY, no sign overshoot | abs 1e-6 |
| TC-SB-012 | Currents during wind-down | at p=1200 | `i_l1_a`=`i_l2_a`=5.0 A; `i_dc_a` = 1200/0.97/200 = 6.186 A | abs 0.01 |
| TC-SB-013 | Wind-down in progress, setpoint written 9000 | | Stored clamped: `p_setpoint_w` = 6000; wind-down unaffected | abs 1e-9 |
| TC-SB-014 | Wind-down in progress, `to_running()` called (cancel, OQ-4) | | Wind-down cancelled; p ramps from current value toward the stored setpoint with no jump | no jump; R1 |

### 5.4 Ramp (TC-RP)
Common method: record `(t_s, p_ac_w)` after each `step(dt_s)`, including the t=0 sample. Criteria for every ramp test:
- R1 Slope: for every consecutive pair, `|dP|/dt <= R + tol` with `tol = 6 W / dt_s` (60 W/s at dt=0.1).
- R2 Time to setpoint: reaches `setpoint +/- 6 W` within `expected_time +/- dt_s`.
- R3 No overshoot: never beyond the setpoint by more than 6 W in the direction of travel.
- R4 Monotonic: no direction reversal during a single-direction ramp.

| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-RP-001 [CORE] | Default | read `ramp_pct_per_s` | 10.0 (600 W/s) | abs 1e-9 |
| TC-RP-002 [CORE] | RUNNING p=0 | setpoint 6000; 100 x 0.1 s | p(1 s)=600, p(5 s)=3000, p(10 s)=6000 (each abs 6 W) | R1-R4; arrival 10.0 s +/- 0.1 |
| TC-RP-003 [CORE] | RUNNING at 6000 | setpoint 0 | p = 6000 - 600 t; 0 at 10 s | R1-R4 |
| TC-RP-004 [CORE] | RUNNING at 6000 | setpoint -6000 | p(10 s)=0, p(20 s)=-6000; same slope both sides of zero | R1-R4; arrival 20.0 s +/- 0.1 |
| TC-RP-005 | RUNNING at 0 | setpoint -6000 | p(10 s) = -6000 | R1-R4 |
| TC-RP-006 | RUNNING at 0 | setpoint 3000 | Reaches 3000 at 5.0 s +/- 0.1, holds 10 steps | R1-R4, hold |
| TC-RP-007 | Ramping up, t=4 s (p=2400) | setpoint 1000 | No jump (p(4.0)=2400 +/- 6); down at 600 W/s; reaches 1000 at 6.333 s +/- 0.1 | R1-R3 vs new target |
| TC-RP-008 | Ramping up, t=4 s | setpoint -2000 | Smooth through 0 (t=8 s) to -2000 (t=11.33 s +/- 0.1) | R1-R3 |
| TC-RP-009 | Settled 3000 | same setpoint again | No change | abs 6 W |
| TC-RP-010 [CORE] | STANDBY, setpoint 6000 | `to_running()`, step 1 s | Starts from 0: p(1 s)=600 +/- 6 (not 6000) | abs 6 W |
| TC-RP-011 | `ramp_pct_per_s=20` | setpoint 6000 | 1200 W/s, arrives at 5 s +/- 0.1 | R1 (R=1200), R2 |
| TC-RP-012 | `ramp_pct_per_s=1` | setpoint 6000 | 60 W/s; p(10 s)=600 +/- 6 | R1 (R=60) |
| TC-RP-013 | `ramp_pct_per_s=100` | setpoint 6000 | arrives at 1 s | R2, R3 |
| TC-RP-014 | Runtime rate change 10->20 at t=2 s (if setter exists, OQ-6) | | 600 W/s then 1200 W/s; no jump | R1 per segment |
| TC-RP-015 | Arrival | setpoint 6000, dt=0.1, 200 steps | After arrival no oscillation | max abs(p-6000) for t>10.1 s <= 1e-6 |
| TC-RP-N01 | Constructor | `ramp_pct_per_s=0` | `ValueError` | raises |
| TC-RP-N02 | Constructor | `ramp_pct_per_s=-10` | `ValueError` | raises |
| TC-RP-N03 | Constructor | `ramp_pct_per_s=nan` | `ValueError` | raises |
| TC-RP-B01 | Boundary | `ramp_pct_per_s=0.001` | Accepted; p(10 s)=0.6 W | abs 0.01 |
| TC-RP-B02 | Boundary | `ramp_pct_per_s=1000` | Accepted or ValueError (OQ-6); never overshoots 6000 | R3 |

### 5.5 AC electrical outputs (TC-EL)
| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-EL-001 | RUNNING p=0, nominal grid | read currents | 0.0 A each | abs 0.01 |
| TC-EL-002 [CORE] | Settled 6000 W, nominal grid | read | `i_l1_a` = `i_l2_a` = 6000/240 = 25.0 A | abs 0.01 |
| TC-EL-003 | Settled 3000 W | read | 12.5 A each | abs 0.01 |
| TC-EL-004 | Settled 0 W | read | 0.0 A | abs 0.01 |
| TC-EL-005 [CORE] | Settled -6000 W | read | -25.0 A each (sign follows P_ac) | abs 0.01 |
| TC-EL-006 | Settled 6000 W | `i_n_a` | 0.0 A | abs 0.01 |
| TC-EL-007 | Mid-ramp p=2400 | read | 10.0 A each (follows instantaneous p_ac, not setpoint) | abs 0.01 |
| TC-EL-008 | Settled 6000 W, `grid.v_l1n_v = grid.v_l2n_v = 114` (L1-L2 = 228, derived) | read | 6000/228 = 26.316 A each (A-05, OQ-10) | abs 0.01 |
| TC-EL-009 | Grid 125/125 V, 60.2 Hz (in band) | `step()` | State not FAULT; currents use 250 V: 6000 W -> 24.0 A | abs 0.01 |
| TC-EL-010 | OFF / STANDBY / FAULT | read | 0.0 A | abs 0.01 |
| TC-EL-011 | Every sample of all ramp tests | `i_l1_a * grid.v_l1l2_v` vs `p_ac_w` | equal | abs 1 W |
| TC-EL-012 | RUNNING | `i_l1_a` vs `i_l2_a` at all samples | identical (balanced) | abs 1e-9 |
| TC-EL-013 | Unbalanced L-N (L1=110, L2=130), settled 6000 W | read | Uses derived L1-L2 = 240 V: 25.0 A each | abs 0.01 |

### 5.6 Battery side (TC-BT) (CONFIRMED sign and efficiency, A-02..A-04)
Worked values (V_dc = 200 V, eta = 0.97; positive current = discharge/feed-in):
- +6000 W: P_dc = 6000 / 0.97 = 6185.567 W; I_dc = +30.928 A.
- +3000 W: P_dc = 3092.784 W; I_dc = +15.464 A.
- -6000 W: P_dc = 6000 * 0.97 -> -5820 W; I_dc = -29.100 A.
- -3000 W: P_dc = -2910 W; I_dc = -14.550 A.
- 0 W: 0 W, 0 A.

| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-BT-001 [CORE] | Settled +6000 W | read `p_dc_w`, `i_dc_a` | 6185.57 W, +30.93 A | W abs 0.5; A abs 0.01 |
| TC-BT-002 | Settled +3000 W | read | 3092.78 W, +15.46 A | same |
| TC-BT-003 [CORE] | Settled -6000 W | read | -5820.0 W, -29.10 A | same |
| TC-BT-004 | Settled -3000 W | read | -2910.0 W, -14.55 A | same |
| TC-BT-005 | p=0 | read | 0 W, 0 A | abs 1e-9 |
| TC-BT-006 | Sweep {-6000,-3000,-600,0,600,3000,6000} | read | `i_dc_a * 200` matches branch formula | abs 0.5 W |
| TC-BT-007 | +P vs -P | | abs(P_dc(+P)) > P and abs(P_dc(-P)) < P for P != 0 | strict |
| TC-BT-008 | Loss accounting | | P>0: P_dc - P_ac = 0.03 * P_dc; P<0: abs(P_ac) - abs(P_dc) = 0.03 * abs(P_ac) | abs 0.5 W |
| TC-BT-009 | Reversal +6000 -> -6000 | sample 0.1 s | `i_dc_a` sign equals `p_ac_w` sign; 0 at p_ac = 0; no jump larger than the formula slope change | abs 0.01 A |
| TC-BT-010 | OFF, STANDBY, FAULT | read | `i_dc_a` = 0 | abs 1e-9 |
| TC-BT-011 | Mid-ramp p=2400 | read | 12.371 A | abs 0.01 |
| TC-BT-012 | Grid voltage changed (e.g. 125/125 V) | read at settled 6000 W | `i_dc_a` unchanged (+30.93 A; battery side independent of grid voltage, V_dc fixed 200 V) | abs 0.01 |

### 5.7 Fault / trip (TC-FT)
All via the grid object. Precondition unless stated: RUNNING, settled 3000 W; set grid value(s) then one `step(0.1)`. L1-L2 is derived, so it is never set directly.

| Quantity | Nominal | Lower 88 % | Upper 110 % |
|---|---|---|---|
| L1-N, L2-N | 120 V | 105.6 V | 132.0 V |
| L1-L2 (derived, safety-net check, A-16) | 240 V | 211.2 V | 264.0 V |
| Frequency | 60 Hz | 59.3 Hz | 60.5 Hz |

Margins: coarse = 0.1 V / 0.01 Hz; edge = 1e-6 V / 1e-6 Hz (A-15). No test uses the exact limit value as input.

| ID | Stimulus | Expected | Pass/fail |
|---|---|---|---|
| TC-FT-001 [CORE] | Nominal grid, 100 steps | RUNNING, no fault | state RUNNING |
| TC-FT-002 | L1-N = 105.7 V (0.1 inside) | healthy | RUNNING |
| TC-FT-003 [CORE] | L1-N = 105.6 + 1e-6 (edge, inside) | healthy (limit counts as healthy) | RUNNING |
| TC-FT-004 [CORE] | L1-N = 105.5 V (0.1 outside) | FAULT after step | FAULT, p_ac = 0 |
| TC-FT-005 | L1-N = 105.6 - 1e-6 (edge, outside) | FAULT | FAULT |
| TC-FT-006 | L1-N = 131.9 V | healthy | RUNNING |
| TC-FT-007 | L1-N = 132.0 - 1e-6 | healthy | RUNNING |
| TC-FT-008 [CORE] | L1-N = 132.1 V | FAULT | FAULT, p_ac = 0 |
| TC-FT-009 | L1-N = 132.0 + 1e-6 | FAULT | FAULT |
| TC-FT-010 | L2-N = 105.5 V (L1 nominal) | FAULT (L2 checked independently) | FAULT |
| TC-FT-011 | L2-N = 132.1 V | FAULT | FAULT |
| TC-FT-012 | L2-N = 105.6 + 1e-6 and 132.0 - 1e-6 (two runs) | healthy | RUNNING |
| TC-FT-013 | L1-N = L2-N = 105.5 (L1-L2 = 211.0 < 211.2) | FAULT (L-L check also violated; cannot be shown to be the sole cause, A-16) | FAULT |
| TC-FT-014 | L1-N = L2-N = 132.1 (L1-L2 = 264.2 > 264.0) | FAULT (same note) | FAULT |
| TC-FT-015 | L1-N = L2-N = 105.7 (L1-L2 = 211.4) | healthy | RUNNING |
| TC-FT-016 | L1-N = L2-N = 131.9 (L1-L2 = 263.8) | healthy | RUNNING |
| TC-FT-017 | f = 59.31 Hz | healthy | RUNNING |
| TC-FT-018 [CORE] | f = 59.29 Hz | FAULT | FAULT, p_ac = 0 |
| TC-FT-019 | f = 60.49 Hz | healthy | RUNNING |
| TC-FT-020 [CORE] | f = 60.51 Hz | FAULT | FAULT, p_ac = 0 |
| TC-FT-021 | f = 59.3 + 1e-6 and 60.5 - 1e-6 (two runs) | healthy | RUNNING |
| TC-FT-022 | f = 59.3 - 1e-6 and 60.5 + 1e-6 (two runs) | FAULT | FAULT |
| TC-FT-023 | Voltage and frequency both bad | FAULT | FAULT |
| TC-FT-024 | Extremes: L-N 0 V on both legs; f=0; L-N 500 V; f=100 | FAULT, no exception, no division by zero; currents finite and 0 | `i_l1_a` abs 1e-9 |
| TC-FT-025 | Grid bad, one `step(0.1)` | FAULT after exactly 1 step (A-07) | FAULT |
| TC-FT-026 | Grid bad then restored with no `step()` in between | No fault (sampling only in `step()`) | RUNNING |
| TC-FT-027 | Grid bad for one step, restored, step again | Still FAULT (latched) | FAULT |
| TC-FT-028 [CORE] | RUNNING at 6000 W, grid bad | `p_ac_w`, `i_l1_a`, `i_l2_a`, `i_dc_a` = 0 on the step that trips (instant, not ramped) | abs 1e-9 |
| TC-FT-029 | Trip mid-ramp (p=2400, target 6000) | p_ac = 0; stays 0 for 20 more steps | abs 1e-9 |
| TC-FT-030 | Trip from OFF and STANDBY | FAULT | FAULT |
| TC-FT-031 | In FAULT: setpoint 6000, healthy grid, 20 s | p_ac stays 0, state FAULT | all samples 0 |
| TC-FT-032 [CORE] | In FAULT, grid back to nominal, 10 s | Still FAULT (latched) | FAULT |
| TC-FT-033 | `step(0)` with bad grid | Behaviour documented (OQ-8) | document |
| TC-FT-034 | `grid.v_l1n_v = nan` | Not RUNNING with p > 0 after step (OQ-7) | state != RUNNING or exception |
| TC-FT-035 | Frequency bad / voltage bad separately | Each alone sufficient | FAULT x2 |

### 5.8 Reset (TC-RS) (CONFIRMED, A-11)
| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-RS-001 [CORE] | FAULT, grid restored | `reset()` | state OFF, p_ac = 0 | == OFF |
| TC-RS-002 [CORE] | After TC-RS-001 | `to_standby()`, `to_running()`, setpoint 3000, 5 s | Normal: p(5 s)=3000 +/- 6 | R1-R4 |
| TC-RS-003 [CORE] | FAULT, grid still bad | `reset()` | Stays FAULT; no exception; p_ac = 0 | == FAULT, no raise |
| TC-RS-004 | As TC-RS-003, then grid restored | `reset()` | Succeeds | == OFF |
| TC-RS-005 | Refused reset, grid then restored, only `step()` | Remains FAULT | == FAULT |
| TC-RS-006 [CORE] | RUNNING at settled 3000 W | `reset()` | No-op: no exception; state RUNNING, p_ac, setpoint unchanged | state, p abs 1e-9, setpoint abs 1e-9 |
| TC-RS-007 | OFF, STANDBY, and RUNNING mid-wind-down (parametrised) | `reset()` | No-op: no exception, state and p_ac unchanged, wind-down continues | unchanged |
| TC-RS-008 | FAULT, grid healthy | `reset()` twice | Second call is a no-op (state is OFF), no exception | OFF |
| TC-RS-009 | After reset -> RUNNING | 1 step | Ramp restarts from 0 | p <= 60 + 6 W at dt 0.1 |
| TC-RS-010 | After reset | Setpoint handling (OQ-4) | p stays 0 in OFF | p = 0 |
| TC-RS-011 | Fault/reset x3 | | Same behaviour each cycle | sequence matches |
| TC-RS-012 | FAULT, grid L1-N = 105.6 + 1e-6 | `reset()` | Succeeds (edge healthy) | == OFF |
| TC-RS-013 | FAULT, grid frequency 59.29 Hz only | `reset()` | Stays FAULT | == FAULT |

### 5.9 `step(dt)` and time (TC-TM)
| ID | Preconditions | Stimulus | Expected | Pass/fail |
|---|---|---|---|---|
| TC-TM-001 | RUNNING p=0, setpoint 6000 | `step(0)` | No change, no exception | abs 1e-9 |
| TC-TM-002 [CORE] | Same | `step(-0.1)` | `ValueError`; p/state unchanged | raises |
| TC-TM-003 | Same | `step(nan)`, `step(inf)` | `ValueError` | raises |
| TC-TM-004 [CORE] | Same | `step(1000)` | p = 6000, no overshoot | abs 1e-6; max <= 6000 |
| TC-TM-005 | Same | `step(10)` | p = 6000 | abs 1e-6 |
| TC-TM-006 | Same | `step(9.999)` | p = 5999.4 | abs 6 W |
| TC-TM-007 [CORE] | Step independence | A: 1000 x 0.01; B: 100 x 0.1; C: 1 x 10; D: 3,3,3,1 | At 10 s all p = 6000; at 5 s (A: 500 steps, B: 50 steps, E: one `step(5)`) all 3000 | pairwise <= 1e-6 W |
| TC-TM-008 | Direction change | Up for 4 s, setpoint -6000, 8 s more; dt in {0.01,0.1,0.5,1} | All final p = -2400 | pairwise <= 1e-6 W |
| TC-TM-009 | Bad grid before `step(100)` | | FAULT, p = 0 | FAULT |
| TC-TM-010 | 100000 x `step(0.001)` at settled 3000 | | No drift | max dev <= 1e-6 |
| TC-TM-011 | Time attribute, if exposed (OQ-9) | | Equals sum of dt | abs 1e-9 |
| TC-TM-012 | Monkeypatch `time.sleep`/`time.time` to raise, run TC-RP-002 | | Passes | no call |
| TC-TM-013 | Whole suite | | Runs in < 5 s | pytest duration |
| TC-TM-014 | `step(1e-9)` | | p changes 6e-7 W, no exception | abs 1e-9 |
| TC-TM-015 | Determinism | Two identical sims | Identical outputs | equal |

## 6. Traceability

| Requirement / decision | Test IDs |
|---|---|
| Separate grid object | TC-GR-001..009, all FT/EL tests via fixture |
| Rated 6000 W, clamp | TC-SP-004..010, 012 |
| States, power only in RUNNING | TC-ST-001..013, TC-SP-013, TC-FT-031 |
| RUNNING->STANDBY ramps down; setpoint stored during wind-down | TC-SB-001..014, TC-ST-013 |
| Default ramp 10 %/s, configurable | TC-RP-001..015, N01..N03, B01, B02 |
| Grid 120/120/240 V, 60 Hz; L1-L2 derived | TC-GR-001..005, 007, TC-EL-008, 009, 013 |
| P_ac, current per leg | TC-EL-001..013 |
| Battery 200 V, 97 %, sign positive = discharge | TC-BT-001..012, TC-SB-012 |
| Trip voltage 88..110 %, edges healthy | TC-FT-002..016, 023, 024, 035, TC-RS-012 |
| L-L safety-net check (redundant, A-16) | TC-FT-013..016 |
| Trip frequency 59.3..60.5 Hz | TC-FT-017..022, 035, TC-RS-013 |
| Instant trip, no delay | TC-FT-025, 026, 028, 029, TC-SB-008 |
| Power to 0 on fault | TC-FT-028, 029, 031 |
| Leave FAULT only via reset(); reset needs healthy grid, lands in OFF, no-op outside FAULT | TC-ST-010, TC-FT-027, 032, TC-RS-001..013 |
| `step(dt)` simulated time | TC-TM-001..015 |
| Invalid inputs | TC-SP-011, TC-RP-N01..N03, TC-TM-002, 003, TC-GR-006, TC-FT-034 |

## 7. CORE set (implement first) - 39 tests
- GridSim (2): TC-GR-001, TC-GR-003
- Setpoint/clamp (5): TC-SP-002, 004, 005, 006, 007
- State machine (5): TC-ST-001, 002, 003, 006, 008
- Wind-down (3): TC-SB-001, 002, 006
- Ramp (5): TC-RP-001, 002, 003, 004, 010
- AC currents (2): TC-EL-002, 005
- Battery (2): TC-BT-001, 003
- Trip (8): TC-FT-001, 003, 004, 008, 018, 020, 028, 032
- Reset (4): TC-RS-001, 002, 003, 006
- Time (3): TC-TM-002, 004, 007

Total: 2 + 5 + 5 + 3 + 5 + 2 + 2 + 8 + 4 + 3 = 39 CORE tests.

Suggested files: `tests/test_grid_sim.py`, `test_inverter_setpoint.py`, `_states.py`, `_standby_rampdown.py`, `_ramp.py`, `_electrical.py`, `_battery.py`, `_fault.py`, `_reset.py`, `_time.py`. Shared helpers in `tests/conftest.py`: fixtures `grid`, `inv`, `running_inv`, a ramp recorder returning `(t_s, p_ac_w)` and an R1-R4 checker. Boundary tests parametrised.

## 8. Out of scope for step 1
Modbus/RS485 or any communication; BMS and battery SoC/voltage dynamics; multiple modules; EMS; thermal derating; reactive power / Volt-VAr / frequency-watt; trip clearing times and ride-through per IEEE 1547 / UL 1741 SB (planned for a later step; step 1 trips instantly); anti-islanding; DC/current limits; standby losses; unbalanced loads and neutral current; real-time clock; phase angle in the grid object; EVSE.

## 9. Floating-point notes
- Ramp: `p += sign * min(R*dt, |target - p|)`; the model must snap to the target when the remaining distance <= R*dt (needed by TC-RP-015, TC-TM-004, TC-SB-011).
- Limits: `0.88 * 120.0 != 105.6` exactly; hence A-15. The model should compare against limits computed once.
- Always `pytest.approx(x, abs=...)`.

## 10. Open questions (remaining)
- OQ-3 Remaining transition rules: direct RUNNING->OFF and OFF->RUNNING rejected with an exception (assumed)?
- OQ-4 Setpoint handling: retained or cleared on FAULT/reset/OFF (assumed retained; a setpoint is accepted while not RUNNING). Does `to_running()` during wind-down cancel the wind-down and resume toward the stored setpoint (assumed, TC-SB-014)?
- OQ-5 Setpoint `inf`/`nan`: clamp inf, reject nan assumed.
- OQ-6 Can the ramp rate change at runtime? Maximum allowed value (is > 100 %/s valid)?
- OQ-7 NaN or negative grid values: should `GridSim` reject them, or should the inverter treat them as FAULT?
- OQ-8 Is the trip evaluated on `step(0)`?
- OQ-9 Expose a simulated-time attribute and a battery-voltage output?
- OQ-10 Per-leg current uses the actual (derived) L1-L2 voltage (assumed) rather than a fixed 240 V.

Resolved by Keyur (no longer open): grid object and read() API; derived L1-L2; inclusive edges with float-safe tests; RUNNING->STANDBY ramp-down; instantaneous trip for step 1; battery current sign and efficiency direction and fixed 200 V; reset() semantics (needs healthy grid, lands in OFF, no-op outside FAULT); setpoint written during wind-down is stored and applied on return to RUNNING; L-L trip check kept as redundant safety net.
