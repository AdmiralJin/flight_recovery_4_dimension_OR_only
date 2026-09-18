# Workbench v1 Validation Data

This directory contains small, auditable system-level acceptance cases for the AIR Recovery Research Workbench v1.

## Case 001 — `wb_v1_001_baseline`

Purpose: verify that an undisrupted, resource-feasible plan is preserved end to end.

### Structure

- 3 airports: A, B, C
- 6 flights
- 2 aircraft rotations
- 2 crew pairings
- no passengers
- no disruptions
- slack airport capacity
- each flight has exactly two external schedule candidates: Original and Cancel
- Aircraft Strings and Crew Pairings are intentionally empty in the input because the formal v1 solve path generates them dynamically

The two rotations use different equipment/rating types so that the canonical zero reassignment coefficients do not create equivalent zero-cost resource swaps.

### Expected result

The unique intended baseline behavior is:

- all six original flight options selected
- no cancellations
- zero departure delay
- zero aircraft reassignment/ferry
- zero crew reassignment/deadhead
- no passenger outcomes
- no recovery actions
- objective = 0
- integrated audit passes

### Files

- `scenarios/wb_v1_001_baseline.json`: Scenario-only input for Data / Validate / Visualization
- `columns/wb_v1_001_baseline_columns.json`: external Flight Options; no pre-generated Aircraft/Crew columns
- `capacities/wb_v1_001_baseline_capacity.json`: non-binding residual seat capacities
- `bundles/wb_v1_001_baseline_bundle.json`: full SolveRequest for Precheck / Solve
- `expected/wb_v1_001_baseline_expected.json`: human oracle and regression assertions

Use the full bundle when testing the formal Solve path. The Scenario-only file is intentionally not solve-ready by itself.


## Case 002 — `wb_v1_002_single_delay`

Purpose: verify one direct departure disruption and the minimum downstream delay required by aircraft/crew continuity.

### Structure

- same 3-airport / 6-flight / 2-rotation skeleton as Case 001
- A airport departure closure and departure capacity 0 from 07:30 to 09:00
- matching `departure_capacity_reduction` disruption for direct-exposure visualization
- WB2_F101: Original, +40, +60, Cancel
- WB2_F102: Original, +20, +40, Cancel
- WB2_F103: Original, +20, Cancel
- unaffected E2 rotation: Original + Cancel only
- no passengers
- no pre-generated Aircraft Strings or Crew Pairings

### Intended propagation

`WB2_F101` cannot depart before 09:00, so the first feasible option is +60. It reaches B at 10:00. The same E1 aircraft and C1 crew cannot operate `WB2_F102` at its original 09:40 departure, so the minimum feasible downstream option is +20 at 10:00. That flight reaches C at 11:00, leaving the original 11:20 `WB2_F103` feasible.

Expected schedule:

`F101 +60 -> F102 +20 -> F103 original`

The E2 control rotation remains unchanged.

Expected objective: 80 under `phase2_test_v1` (60 + 20 minutes of flight-delay cost, with no aircraft/crew/passenger cost).
