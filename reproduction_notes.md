# Reproduction Notes

## Phase 0 scope

Phase 0 implements a verifiable data boundary only. There are no flight strings, mathematical decision variables, solver calls, Benders cuts or column generation.

The schema is designed to retain the source information needed later by the four paper components:

- SRM: flights, equipment, strategic/market flags, seat requirements, airport-time capacities and disruptions.
- ARM: individual tails, equipment type, start/end stations, maintenance metadata and original rotations.
- CRM: individual cockpit crews, rating, start/end stations, duties and original pairings.
- PRM: homogeneous passenger commodities and original itineraries.

The `/api/solve` route is intentionally a guard. Invalid data receives HTTP 422 and never reaches an optimizer; valid data receives HTTP 501 until a later phase supplies an audited model.

## Paper-to-schema distinctions

The paper defines optimization sets and parameters, not a complete operational interchange format. Fields required by the project plan but not formally specified by the paper are treated as implementation assumptions and recorded in `assumptions.md`.

## Toy case

`toy_case_001` contains three airports, six flights, two aircraft, two cockpit crews, four passenger groups, an eight-hour recovery horizon and a two-hour departure-capacity reduction at airport B. It is a Phase 0 data fixture, not yet a claimed optimal recovery instance.

