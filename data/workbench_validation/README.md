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


## Case 003 — `wb_v1_003_delay_vs_cancel`

Purpose: verify that a Cost Override changes the actual recovery optimum.

### Why this case is rotation-level

The affected E1 resource is a closed `A -> B -> C -> A` rotation. Aircraft WB3_AC1 and crew WB3_C1 both start at A and are required to finish at A. If the first disrupted A-B leg is cancelled, the later B-C and C-A legs are not independently reachable by those resources. Therefore Case 003 compares two physically consistent integrated alternatives rather than treating one cancellation as an isolated schedule choice.

### Variant A — canonical costs

Uses `phase2_test_v1` unchanged.

- delay cost = 1 per flight-minute
- cancellation cost = 25,000 per flight
- intended E1 recovery: `F101 +60 -> F102 +20 -> F103 original`
- intended schedule objective = 80

### Variant B — low cancellation override

Uses the identical Scenario / Columns / Capacity / algorithm profiles, with only:

`flight_cancellation = 20`

Now the affected three-leg E1 cycle costs 60 to cancel, which is lower than the 80-minute delay recovery.

Expected E1 decision:

`F101 cancel -> F102 cancel -> F103 cancel`

The E2 control rotation stays original in both variants.

### Files

- `scenarios/wb_v1_003_delay_vs_cancel.json`
- `columns/wb_v1_003_delay_vs_cancel_columns.json`
- `capacities/wb_v1_003_delay_vs_cancel_capacity.json`
- `bundles/wb_v1_003_delay_vs_cancel_bundle.json`: canonical costs
- `bundles/wb_v1_003_delay_vs_cancel_low_cancel_bundle.json`: low cancellation-cost override
- `expected/wb_v1_003_delay_vs_cancel_expected.json`


## Case 004 — `wb_v1_004_aircraft_swap`

Purpose: verify Aircraft Recovery with a compatible spare aircraft, while keeping crew and passenger logic simple.

### Structure

- one disrupted E1 aircraft WB4_AC1 with original closed rotation `A-B-C-B-A`
- one compatible E1 spare WB4_AC2 positioned at B, with required terminal B
- three deliberately simple crew pairings so crew availability does not force the aircraft decision
- no passengers
- no ferry required
- A departure closure forces WB4_F101 to depart +60 minutes

### Intended aircraft recovery

If WB4_AC1 alone keeps its original downstream flying, the minimum feasible recovery is:

`F101 +60 -> F102 +30 -> F103 +20 -> F104 original`

Schedule cost = 110.

The spare-aircraft recovery is:

- WB4_AC1: `F101 +60 -> F104 original`, A -> B -> A
- WB4_AC2: `F102 original -> F103 original`, B -> C -> B

Schedule cost = 60.

Aircraft reassignment cost remains 0, so the intended optimum uses the spare and creates exactly two aircraft reassignments (F102 and F103) without ferry. Case 004 additionally overrides `crew_reassignment = 100` to remove unrelated zero-cost crew-swap degeneracy while leaving the intended original crew pairings feasible at zero crew cost.

### Files

- `scenarios/wb_v1_004_aircraft_swap.json`
- `columns/wb_v1_004_aircraft_swap_columns.json`
- `capacities/wb_v1_004_aircraft_swap_capacity.json`
- `bundles/wb_v1_004_aircraft_swap_bundle.json`
- `expected/wb_v1_004_aircraft_swap_expected.json`
