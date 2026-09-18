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


## Case 005 — `wb_v1_005_crew_recovery`

Purpose: verify Crew Recovery while keeping aircraft assignments stable and easy to audit.

### Structure

- WB5_AC1 operates `F101 A-B` and `F104 B-A`
- WB5_AC2 independently operates `F102 B-C` and `F103 C-B`
- WB5_C1 is the original crew for all four flights
- WB5_C2 is an E1-qualified spare crew positioned at B and required to finish at B
- A departure closure forces F101 to +60 minutes
- no passengers
- no ferry or deadhead is required
- both bundles set `aircraft_reassignment = 100` only to remove unrelated zero-cost aircraft-swap degeneracy

### Default crew-cost recovery

After F101 +60, C1 reaches B at 10:00 and misses original F102 at 09:30.

The intended Crew Recovery is:

- C1: `F101 +60 -> F104 original`, A-B-A
- C2: `F102 original -> F103 original`, B-C-B

Only F101 is delayed, so schedule objective = 60. Canonical crew reassignment cost is 0, producing exactly two crew reassignments.

### High crew-reassignment-cost variant

The identical data are solved with:

`crew_reassignment = 100`

Now the alternative of keeping C1 is cheaper:

`F101 +60 -> F102 +30 -> F103 +20 -> F104 original`

Schedule objective = 110, with zero crew reassignment.

### Files

- `scenarios/wb_v1_005_crew_recovery.json`
- `columns/wb_v1_005_crew_recovery_columns.json`
- `capacities/wb_v1_005_crew_recovery_capacity.json`
- `bundles/wb_v1_005_crew_recovery_bundle.json`
- `bundles/wb_v1_005_crew_recovery_high_crew_cost_bundle.json`
- `expected/wb_v1_005_crew_recovery_expected.json`


## Case 006 — `wb_v1_006_passenger_connection`

Purpose: verify Passenger Recovery after a missed connection, including residual seat capacity.

### Structure

- PG1 = 20 passengers travelling A -> C
- original itinerary: F101 A-B -> F102 B-C
- scheduled arrival: 10:30
- A departure closure forces F101 from 08:00 to 09:00 (+60)
- delayed F101 arrives B at 10:00, after F102 has departed at 09:30
- later F103 departs B at 11:00 and arrives C at 12:00
- aircraft and crew use distinct E1/E2/E3 types/ratings, so no resource recovery is needed or possible

Custom Solve bundles explicitly include three passenger itinerary candidates:

1. original F101_ORIG + F102_ORIG
2. recovered F101_D60 + F103_ORIG
3. UNSERVED

### Default residual capacity

F103 residual capacity = 40.

Recovered passenger arrival delay = 90 minutes.

Passenger recovery cost:

`20 × 90 × 10 = 18,000`

UNSERVED cost:

`20 × 2,500 = 50,000`

Therefore the expected optimum reaccommodates all 20 passengers on F103.

Total objective = 60 schedule delay + 18,000 passenger delay = 18,060.

### Low-capacity variant

F103 residual capacity is reduced to 10 while the passenger group remains 20.

Current PRM treats the passenger group as an indivisible itinerary-selection commodity, so the 20-person recovery itinerary cannot use a 10-seat residual capacity. The expected selection becomes UNSERVED.

Total objective = 60 schedule delay + 50,000 unserved cost = 50,060.

### Files

- `scenarios/wb_v1_006_passenger_connection.json`
- `columns/wb_v1_006_passenger_connection_columns.json`
- `capacities/wb_v1_006_passenger_connection_capacity.json`
- `capacities/wb_v1_006_passenger_connection_low_capacity.json`
- `bundles/wb_v1_006_passenger_connection_bundle.json`
- `bundles/wb_v1_006_passenger_connection_low_capacity_bundle.json`
- `expected/wb_v1_006_passenger_connection_expected.json`


## Case 007 — `wb_v1_007_capacity_bottleneck`

Purpose: verify that airport departure-capacity constraints in the SRM actually force schedule recovery.

### Structure

Four independent one-leg flights leave hub B inside the same `09:00-10:00` interval:

- F101 09:05, delay alternative 10:05 (+60)
- F102 09:15, delay alternative 10:05 (+50)
- F103 09:25, delay alternative 10:05 (+40)
- F104 09:35, delay alternative 10:05 (+30)

Each flight has a unique equipment/rating type, so Aircraft/Crew Recovery cannot substitute for the airport-capacity decision. There are no passengers.

SRM interval membership is half-open: `start <= departure < end`.

### Baseline-capacity variant

B departure capacity in 09:00-10:00 = 4.

All four original departures fit, so expected objective = 0.

### Bottleneck variant

B departure capacity in 09:00-10:00 = 2 and a matching `departure_capacity_reduction` disruption with `capacity_change=-2` is included for Workbench visualization.

Exactly two flights must move to 10:05. The possible delay penalties are 60, 50, 40 and 30, so the unique minimum is:

- F101 original
- F102 original
- F103 +40
- F104 +30

Expected objective = 70.

### Files

- `scenarios/wb_v1_007_capacity_baseline.json`
- `scenarios/wb_v1_007_capacity_bottleneck.json`
- `columns/wb_v1_007_capacity_bottleneck_columns.json`
- `capacities/wb_v1_007_capacity_bottleneck_capacity.json`
- `bundles/wb_v1_007_capacity_baseline_bundle.json`
- `bundles/wb_v1_007_capacity_bottleneck_bundle.json`
- `expected/wb_v1_007_capacity_bottleneck_expected.json`
