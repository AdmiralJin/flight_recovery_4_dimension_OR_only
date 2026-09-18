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
