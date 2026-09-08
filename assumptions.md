# Implementation Assumptions

This register separates implementation choices from statements made by Petersen et al. (2010).

## A-001 Time representation

Source status: The paper defines one exogenous recovery window `T = [t, T_end]` but does not prescribe a JSON timestamp format.

Implementation: Phase 0 accepts timezone-aware ISO 8601 datetimes; `Z` or an explicit UTC offset is mandatory. The bundled example uses UTC (`Z`). Each scheduled flight and each capacity/disruption interval must be fully inside the recovery window.

Reason: An absolute timestamp avoids day-boundary ambiguity and makes JSON round trips deterministic.

Impact: Real airline ingestion will need an explicit airport-local-time and timezone conversion policy.

## A-002 Duration

Source status: The paper uses timed flight strings but does not define a standalone `duration` input field.

Implementation: `Flight.duration` is an integer number of minutes and must exactly equal `sched_arr - sched_dep`.

Reason: This detects inconsistent source data before network generation.

Impact: Block-time adjustments and time-zone changes must be normalized before validation.

## A-003 Crew rating

Source status: The paper solves crew recovery by equipment type corresponding to crew rating, while full legality is airline-specific.

Implementation: Phase 0 models one `rating` string per crew and requires an exact match with `Flight.original_equipment`.

Reason: This is the smallest auditable compatibility rule.

Impact: Multiple ratings, seat positions, qualifications, reserve crew and full duty legality are deferred.

## A-004 Original duties and pairing

Source status: The paper distinguishes duties and multi-duty pairings but does not prescribe an interchange schema.

Implementation: `original_duties` is a list of ordered flight-id lists; `original_pairing` must be the exact ordered flattening of those duties.

Reason: Keeping both fields makes the source structure explicit and catches inconsistent imports.

Impact: Duty boundaries are preserved but rest and maximum-duty rules are not yet evaluated in Phase 0.

## A-005 Airport capacity change

Source status: The paper models absolute arrival/departure capacities over station-time intervals.

Implementation: `AirportInterval` stores the post-scenario capacities; `Disruption.capacity_change` is a signed non-zero integer metadata value. Negative values are reductions.

Reason: This keeps baseline/realized capacity data distinct from the causal disruption record.

Impact: Phase 0 checks references and time ranges but does not derive one record from the other.

## A-006 Passenger commodities

Source status: The PRM describes homogeneous O-D passenger commodities with origin, departure time, destination and scheduled arrival.

Implementation: A passenger commodity has a positive `count` and an ordered original itinerary. Its endpoint airports and endpoint timestamps must agree with that itinerary.

Reason: Grouped demand is sufficient for the paper's aggregate passenger-flow model.

Impact: Fare class, loyalty status and individual reaccommodation priority are outside the reproduction core.
