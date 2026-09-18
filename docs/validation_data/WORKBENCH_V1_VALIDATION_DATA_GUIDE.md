# Workbench v1 Validation Data Guide

## 1. Document purpose

This document is the canonical explanation of the Workbench v1 validation dataset on branch:

```text
feature/workbench-v1-validation-data
```

It records:

- what was changed relative to `main`;
- why each validation Case was created;
- how each Case is structured;
- what was learned or corrected while building it;
- how to run automated validation;
- how to test the same behavior manually in Workbench;
- what result should be expected;
- what a failure usually means;
- what should be done before merging this branch into `main`.

The executable source of truth remains the JSON fixtures and regression tests. This document explains their intent and use.

---

## 2. Branch baseline and scope

The branch was created from the Workbench v1 completion point:

```text
main
f75e66fcf05c734d315ed7e90d6f7cfc4a2a8346
docs: record phase 13 final merge verification
```

At the time this documentation was consolidated, the validation branch was:

```text
20 commits ahead of main
0 commits behind main
```

The branch does **not** redesign the Phase 12/13 optimization mathematics. Its purpose is to create small, auditable system-level acceptance data around the existing formal Solve path.

The work added or changed four main areas:

1. validation JSON fixtures under `data/workbench_validation/`;
2. Case-specific regression tests under `tests/regression/`;
3. a batch acceptance runner under `scripts/`;
4. CI and documentation needed to make the validation suite repeatable.

---

## 3. Final data and test structure

```text
data/workbench_validation/
├── scenarios/
├── columns/
├── capacities/
├── bundles/
├── expected/
└── negative/

tests/regression/
├── test_workbench_v1_case001.py
├── test_workbench_v1_case002.py
├── test_workbench_v1_case003.py
├── test_workbench_v1_case004.py
├── test_workbench_v1_case005.py
├── test_workbench_v1_case006.py
├── test_workbench_v1_case007.py
└── test_workbench_v1_case008.py

scripts/
└── validate_workbench_v1_cases.py
```

The meanings are deliberately separated:

- **Scenario**: original schedule/resources/disruption/capacity state used by Data, Validate and Visualization.
- **Recovery Columns**: externally supplied Flight Options and, when required, Passenger Itineraries. Formal v1 does not generate new Flight Options.
- **Capacity Profile**: residual passenger-seat capacity, not physical aircraft capacity.
- **Bundle**: complete SolveRequest used by Precheck and Solve.
- **Expected**: human-readable Oracle plus strong assertions.
- **Negative fixtures**: intentionally invalid or incomplete inputs used to verify error handling.

For Aircraft Strings and Crew Pairings, the validation bundles intentionally leave the arrays empty so the formal v1 path exercises the current dynamic generators rather than injecting pre-generated full resource columns.

---

# 4. Step-by-step modification history

## Step 1 — Case 001: baseline control

### What was done

Created:

```text
wb_v1_001_baseline
```

with:

- 3 airports;
- 6 flights;
- 2 independent aircraft rotations;
- 2 independent crew pairings;
- no passengers;
- no disruption;
- slack airport capacity;
- Original and Cancel Flight Options.

The two rotations use different equipment/rating types so the canonical zero reassignment coefficients cannot create irrelevant zero-cost swaps.

### Purpose

This is the control Case. Before testing disruption recovery, the system must prove that an already feasible plan is preserved.

### Expected result

```text
status = optimal
objective.total = 0
all six original flight options selected
cancelled flights = 0
total departure delay = 0
aircraft reassignment = 0
crew reassignment = 0
ferry = 0
deadhead = 0
passenger outcomes = 0
recovery actions = 0
integrated_audit_pass = true
```

### What to test manually

1. Import the Scenario-only file.
2. Validate it.
3. Open Visualization and confirm no disruption overlay.
4. Import the full bundle.
5. Run Precheck and confirm `solve_ready=true`.
6. Run Solve.
7. In Recovery, confirm Recovered equals Original.

### Relevant commits

```text
03ff072c testdata: add Workbench v1 baseline validation case
4b1b5e3a test(case001): add baseline solve regression
```

---

## Step 2 — Case 002: single delay and downstream propagation

### What was done

Created a departure closure at A from 07:30 to 09:00.

The first E1 flight has a forced +60 minute recovery option. Because the same aircraft and crew continue to the next flight, the second flight must move +20 minutes. The third flight returns to original time.

### Purpose

Verify that:

- a direct disruption is visible;
- the formal solver respects the binding airport interval;
- aircraft/crew continuity propagates delay;
- the delay stops when continuity becomes feasible again.

### Expected result

```text
F101 +60
F102 +20
F103 original
control rotation original

objective.total = 80
schedule = 80
recovery actions = 2
aircraft reassignment = 0
crew reassignment = 0
```

### Manual focus

In Visualization, inspect direct exposure at A. In Recovery, compare Original / Disrupted / Recovered and verify that only F101 and F102 move.

### Relevant commits

```text
145f3d3e testdata(case002): add single-delay propagation validation case
a5bdf98e test(case002): add single-delay solve regression
```

---

## Step 3 — Case 003: delay versus cancellation and Cost Override

### What was done

Built two bundles with identical Scenario, Recovery Columns, Capacity and algorithm profiles.

Only one value changes in the second bundle:

```text
cost_overrides.flight_cancellation = 20
```

The affected E1 resource is a closed A-B-C-A rotation. Cancelling only its first leg would not be physically independent because aircraft/crew terminal continuity still applies. Therefore the actual comparison is:

- recover the affected rotation by delay; versus
- cancel the complete affected three-leg rotation.

### Purpose

Prove that Cost Override does not only change a UI number; it changes the actual optimization decision.

### Expected results

Default costs:

```text
F101 +60
F102 +20
F103 original
objective = 80
```

Low cancellation cost:

```text
F101 cancel
F102 cancel
F103 cancel
objective = 60
```

The unaffected control rotation remains original in both variants.

### Manual focus

Open Costs before Solve. Compare Baseline and Effective values. Solve each bundle separately and verify the recovery decision flips.

### Relevant commits

```text
e313045c testdata(case003): add delay-vs-cancel cost tradeoff validation case
ea41152e test(case003): add cost-override decision-flip regression
```

---

## Step 4 — Case 004: Aircraft Recovery

### What was done

Created:

- WB4_AC1: original E1 aircraft;
- WB4_AC2: compatible E1 spare aircraft already positioned at B.

A closure delays F101 by 60 minutes. AC1 therefore cannot reach B in time for F102. The spare AC2 covers F102/F103 and returns to B. AC1 later operates F104 back to A.

The all-original-aircraft fallback would require:

```text
F101 +60
F102 +30
F103 +20
F104 original
schedule cost = 110
```

Using the spare keeps only the forced 60-minute delay.

### Purpose

Isolate Aircraft Recovery while preserving valid initial and terminal positions.

### Important correction discovered during real Solve

The canonical profile has:

```text
crew_reassignment = 0
```

The first real Solve therefore found equivalent zero-cost crew swaps. That did not invalidate Aircraft Recovery, but it made the Case semantically noisy.

Case 004 was corrected with:

```text
cost_overrides.crew_reassignment = 100
```

This removes irrelevant crew degeneracy while leaving the intended aircraft decision unchanged.

### Expected result

```text
AC1: F101 +60 -> F104 original
AC2: F102 original -> F103 original

objective = 60
aircraft reassignments = 2
crew reassignments = 0
ferry = 0
deadhead = 0
recovery actions = 3
```

### Manual focus

In Recovery, inspect per-flight aircraft assignment and final stations:

```text
AC1 final station = A
AC2 final station = B
```

### Relevant commits

```text
fc697c34 testdata(case004): add spare-aircraft recovery validation case
5edbc22a test(case004): add spare-aircraft solve regression
0d171b10 fix(case004): isolate aircraft recovery from zero-cost crew swaps
```

---

## Step 5 — Case 005: Crew Recovery

### What was done

Aircraft rotations are intentionally independent:

```text
AC1: F101 + F104
AC2: F102 + F103
```

Original crew C1 is assigned across all four flights. A forced +60 delay on F101 makes C1 miss F102. Spare qualified crew C2 is already at B and can operate F102/F103, returning to B.

Both bundles override:

```text
aircraft_reassignment = 100
```

to prevent unrelated zero-cost aircraft swaps.

A second variant adds:

```text
crew_reassignment = 100
```

to verify that the optimization can reverse the crew-recovery decision.

### Purpose

Verify Crew Recovery independently of Aircraft Recovery.

### Expected results

Default crew cost:

```text
C1: F101 +60 -> F104 original
C2: F102 original -> F103 original

objective = 60
crew reassignments = 2
aircraft reassignments = 0
```

High crew-reassignment cost:

```text
C1 operates all flights
F101 +60
F102 +30
F103 +20
F104 original

objective = 110
crew reassignments = 0
```

### Manual focus

Check both crew IDs and final stations:

```text
C1 final station = A
C2 final station = B
```

### Relevant commits

```text
c1e66dc0 testdata(case005): add crew-recovery validation case
bdef7627 test(case005): add crew-recovery solve regression
```

---

## Step 6 — Case 006: Passenger Recovery

### What was done

Created one passenger group:

```text
PG1 = 20 passengers
A -> C
original itinerary = F101 -> F102
scheduled arrival = 10:30
```

F101 is forced +60 and reaches B at 10:00. F102 departed B at 09:30, so the original connection is missed. A later flight F103 departs B at 11:00 and arrives C at 12:00.

Three explicit Passenger Itinerary candidates are provided:

```text
1. ORIGINAL: F101_ORIG -> F102_ORIG
2. RECOVERY: F101_D60 -> F103_ORIG
3. UNSERVED
```

Two capacity profiles are tested:

- F103 residual capacity = 40;
- F103 residual capacity = 10.

### Purpose

Verify:

- schedule consistency of passenger itineraries;
- missed-connection recovery;
- passenger delay cost;
- residual seat capacity;
- UNSERVED fallback.

### Expected results

Default capacity 40:

```text
PG1 transported on F101_D60 -> F103_ORIG
arrival delay = 90 minutes
20 reaccommodated passengers
0 unserved

passenger cost = 20 * 90 * 10 = 18,000
schedule cost = 60
objective = 18,060
```

Low capacity 10:

```text
PG1 = UNSERVED
unserved passengers = 20

passenger cost = 20 * 2,500 = 50,000
schedule cost = 60
objective = 50,060
```

Current PRM selects the passenger group as an indivisible commodity; it does not split the 20-person group across a 10-seat residual capacity.

### Important correction discovered during CI

The first auxiliary comparison test treated descriptive `notes` as semantic content. The two capacity files naturally contain different explanatory text for 40 versus 10 seats. The regression was corrected to ignore descriptive notes while still strictly checking that the meaningful model difference is the F103 residual capacity.

### Relevant commits

```text
27a0f922 testdata(case006): add passenger missed-connection validation case
7b7e19af test(case006): add passenger-recovery solve regression
24b5ffde fix(case006): ignore descriptive capacity notes in variant comparison
```

---

## Step 7 — Case 007: Airport Capacity Bottleneck

### What was done

Created four independent flights leaving B in the same interval:

```text
F101 09:05
F102 09:15
F103 09:25
F104 09:35
```

Each has one delayed option at 10:05:

```text
F101 +60
F102 +50
F103 +40
F104 +30
```

Two Scenario variants are provided:

- baseline: B departure capacity = 4 in 09:00–10:00;
- bottleneck: B departure capacity = 2 in 09:00–10:00.

The bottleneck Scenario also includes a matching `departure_capacity_reduction` disruption for Workbench visualization.

### Purpose

Verify that the SRM departure-capacity constraint actually changes the recovered schedule.

The relevant interval semantics are:

```text
start_time <= departure < end_time
```

so 10:05 lies outside the constrained 09:00–10:00 interval.

### Expected results

Baseline:

```text
4 original departures
load = 4 / capacity 4
objective = 0
```

Bottleneck:

```text
F101 original
F102 original
F103 +40
F104 +30

09:00–10:00 load = 2 / capacity 2
objective = 70
```

The regression independently reconstructs selected departure load from the selected Flight Options rather than merely checking that two flights are delayed.

### Relevant commits

```text
db66712f testdata(case007): add airport-capacity bottleneck validation case
6315faaa test(case007): add airport-capacity solve regression
```

---

## Step 8 — Case 008: invalid, incomplete and infeasible inputs

### What was done

Case 008 is a negative-case group, not one successful Solve Case.

It contains:

```text
008A duplicate flight ID
008B sched_arr <= sched_dep
008C declared duration inconsistent with schedule
008D market_flag=false with min_seats>0
008E invalid disruption interval
008F valid Scenario but incomplete SolveRequest
008G complete and Solve-ready but optimization-infeasible
```

### Purpose

Verify that failures occur at the correct system layer:

```text
Schema / Semantic Validation
        !=
Solve Input Readiness
        !=
Optimization Feasibility
```

### Expected results

008A–008E:

```text
POST /api/validate -> HTTP 422
expected validation error is present
```

008F:

```text
Scenario validation = PASS
Precheck.solve_ready = false
missing:
  missing_flight_options
  missing_capacity_profile
  missing_algorithm_profiles

POST /api/solve -> HTTP 422
status = not_solve_ready
```

008G:

The only formal Flight Option is a legal origin-change option C->B, while the only aircraft and crew both start at A and no ferry/deadhead/repositioning candidate exists.

Expected:

```text
Validate = PASS
Precheck = READY
Solve = infeasible
objective = null
selected decisions = empty
resolved/resource/passenger/recovery outputs = empty
metrics = null
```

This is the explicit regression for:

```text
PRECHECK != OPTIMIZATION FEASIBILITY
```

### Relevant commits

```text
b833b026 testdata(case008): add invalid incomplete and infeasible validation cases
3a379c53 test(case008): add negative validation and infeasibility regression
```

---

## Step 9 — Unified batch acceptance runner

### What was done

Added:

```text
scripts/validate_workbench_v1_cases.py
```

The runner executes the same FastAPI application in-process with `TestClient`.

It covers normal Cases, Case variants, invalid inputs, incomplete Solve input and valid-but-infeasible input.

Current batch size:

```text
18 acceptance rows
```

Output columns:

```text
Case ID
Validate
Precheck
Solve Status
Expected Check
PASS/FAIL
```

Any failed expected behavior returns a non-zero process exit code.

### Purpose

Provide one command that answers:

> Is the complete Workbench v1 validation dataset still behaving as designed?

### Command

```bash
python scripts/validate_workbench_v1_cases.py
```

Filtered examples:

```bash
python scripts/validate_workbench_v1_cases.py --case 006
python scripts/validate_workbench_v1_cases.py --case 003/default
python scripts/validate_workbench_v1_cases.py --case 008
```

### Expected result

At the point this branch was documented:

```text
Summary: 18/18 PASS
```

Key row:

```text
008G | PASS | READY | infeasible | PASS | PASS
```

### Relevant commits

```text
33a2d343 feat(validation-suite): add case001-case008 batch acceptance runner
ff32ac01 docs(validation-suite): add case001-case008 batch acceptance report
```

---

# 5. CI integration

The GitHub Actions workflow now performs both layers:

```text
python -m pytest
python scripts/validate_workbench_v1_cases.py
```

The last completed acceptance-suite run before this documentation migration reported:

```text
pytest:
450 passed
0 failed
2 warnings

Workbench v1 batch acceptance:
18/18 PASS
```

The warnings were not validation-case failures.

The distinction between the two layers matters:

- pytest contains detailed case-specific assertions;
- the batch runner gives a readable system acceptance summary.

Both should remain green.

---

# 6. How to test from zero

## 6.1 Install and run the backend/frontend

From repository root:

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Do not double-click `frontend/index.html` directly.

---

## 6.2 Run the full automated regression

First run the complete repository tests:

```bash
python -m pytest
```

Then run the validation acceptance summary:

```bash
python scripts/validate_workbench_v1_cases.py
```

Expected high-level result:

```text
all pytest tests pass
18/18 validation rows PASS
```

If the total pytest count changes later because new tests are added, the requirement is **all tests pass**, not that the count must remain exactly 450.

---

## 6.3 Run one Case only

Detailed regression:

```bash
python -m pytest tests/regression/test_workbench_v1_case006.py
```

Batch-runner filter:

```bash
python scripts/validate_workbench_v1_cases.py --case 006
```

Use pytest when diagnosing a specific assertion. Use the batch runner when you want a quick acceptance overview.

---

# 7. Manual Workbench test procedure

The UI test is still important because automated API tests do not prove that every view is understandable or displays the correct state.

## 7.1 Scenario-only workflow

Use files under:

```text
data/workbench_validation/scenarios/
```

for:

- Data;
- Validate;
- Visualization;
- disruption overlay;
- risk inspection;
- airport capacity heatmap.

A Scenario-only import is intentionally not automatically Solve-ready because formal v1 Solve also requires Recovery Columns, Capacity Profile and algorithm profiles.

## 7.2 Full Solve workflow

Use files under:

```text
data/workbench_validation/bundles/
```

when testing:

- Precheck;
- Costs override embedded in a bundle;
- formal Solve;
- Recovery;
- result export.

Workbench Import Scenario supports a complete SolveRequest as well as Scenario-only JSON.

## 7.3 Expected files

Before testing manually, open the corresponding file under:

```text
data/workbench_validation/expected/
```

Treat it as the human Oracle for that Case.

---

# 8. Recommended manual smoke-test sequence

A complete UI pass does not need every variant on every screen. The following sequence gives broad coverage with low duplication.

| Order | Case | UI focus | Expected observation |
|---|---|---|---|
| 1 | 001 | Data / Validate / Recovery | no changes, objective 0 |
| 2 | 002 | Visualization / Recovery | direct A disruption, +60 then +20 propagation |
| 3 | 003 | Costs / Recovery | cost override flips Delay to Cancel |
| 4 | 004 | Recovery aircraft detail | F102/F103 move to spare AC2 |
| 5 | 005 | Recovery crew detail | F102/F103 move to spare C2 |
| 6 | 006 | Passenger Recovery | reaccommodation with 40 seats; UNSERVED with 10 |
| 7 | 007 | Capacity Heatmap / Constraints | B capacity 4->2 forces two departures out |
| 8 | 008F | Validate / Precheck | valid Scenario but NOT_READY |
| 9 | 008G | Precheck / Solve | READY then infeasible, no fake decisions |

For 008A–008E, importing or validating the corresponding files under `negative/` should produce the documented rejection instead of proceeding as a normal Case.

---

# 9. Per-Case acceptance summary

| Case | Main mechanism | Expected objective / terminal result | Core invariant |
|---|---|---:|---|
| 001 | Baseline | 0 | Original plan preserved |
| 002 | Delay propagation | 80 | F101 +60, F102 +20 |
| 003 default | Delay vs Cancel | 80 | Delay recovery |
| 003 low cancel | Cost Override | 60 | affected three-leg cycle cancelled |
| 004 | Aircraft Recovery | 60 | two aircraft reassignments |
| 005 default | Crew Recovery | 60 | two crew reassignments |
| 005 high crew cost | Crew cost tradeoff | 110 | no crew reassignment, downstream delay |
| 006 default | Passenger recovery | 18,060 | 20 pax reaccommodated, +90 min |
| 006 low capacity | Passenger capacity | 50,060 | 20 pax UNSERVED |
| 007 baseline | Airport capacity | 0 | 4 departures fit capacity 4 |
| 007 bottleneck | Airport capacity | 70 | F103/F104 delayed, load 2/2 |
| 008A-E | Invalid data | validation reject | correct validation layer |
| 008F | Incomplete SolveRequest | not_solve_ready | Scenario valid, Solve input incomplete |
| 008G | Optimization infeasible | infeasible | Precheck READY but no feasible integrated solution |

---

# 10. What to inspect when a test fails

## Baseline suddenly non-zero

Inspect:

- cost ownership;
- generated Aircraft Strings/Crew Pairings;
- linking constraints;
- zero-cost equivalent reassignment;
- result recomputation.

Do not weaken Case 001 Expected merely to make the test pass.

## Delay propagation differs

Inspect:

- airport interval boundaries;
- min-turn / crew connection profile;
- Flight Option timing;
- resource terminal requirements.

## Aircraft/Crew Case shows extra swaps

Check whether a canonical reassignment coefficient is zero. Cases 004 and 005 deliberately use cost isolation to remove unrelated equivalent optima.

## Passenger Case chooses a different itinerary

Inspect:

- selected schedule compatibility;
- itinerary arrival delay;
- passenger group count;
- residual seat capacity;
- UNSERVED cost.

## Capacity Case does not move two flights

Check the SRM half-open interval and the `dep_capacity` stored in the Scenario. The passenger residual capacity profile is not the airport capacity constraint.

## Precheck says READY but Solve fails

That is not automatically a bug. Case 008G exists specifically to prove that input readiness and optimization feasibility are different concepts.

---

# 11. What should not be changed casually

These validation Cases are intentionally small and deterministic. When extending them:

- do not add complexity unless it verifies a new mechanism;
- do not change Expected simply because another equal-cost solution appears—first remove irrelevant degeneracy if the Case needs a unique result;
- do not confuse residual passenger capacity with aircraft physical capacity;
- do not treat Precheck as a solver;
- do not add pre-generated Aircraft/Crew full enumerations to formal v1 bundles unless the formal contract itself changes;
- do not add new Flight Options implicitly in the solver; current formal v1 uses externally supplied Flight Options.

---

# 12. Branch-level modification summary

Relative to `main`, the validation branch added:

- complete Case 001–008 JSON fixtures;
- 12 complete Solve bundles across normal and variant cases;
- 8 expected/oracle files;
- Case 008 negative fixtures;
- 8 regression test modules;
- one batch acceptance runner;
- CI execution of the batch runner;
- root README discoverability;
- validation-data documentation and closeout reports.

The branch is intended as a verification layer on top of Workbench v1, not a new optimization phase.

---

# 13. Commit history for this branch

```text
03ff072c testdata: add Workbench v1 baseline validation case
4b1b5e3a test(case001): add baseline solve regression

145f3d3e testdata(case002): add single-delay propagation validation case
a5bdf98e test(case002): add single-delay solve regression

e313045c testdata(case003): add delay-vs-cancel cost tradeoff validation case
ea41152e test(case003): add cost-override decision-flip regression

fc697c34 testdata(case004): add spare-aircraft recovery validation case
5edbc22a test(case004): add spare-aircraft solve regression
0d171b10 fix(case004): isolate aircraft recovery from zero-cost crew swaps

c1e66dc0 testdata(case005): add crew-recovery validation case
bdef7627 test(case005): add crew-recovery solve regression

27a0f922 testdata(case006): add passenger missed-connection validation case
7b7e19af test(case006): add passenger-recovery solve regression
24b5ffde fix(case006): ignore descriptive capacity notes in variant comparison

db66712f testdata(case007): add airport-capacity bottleneck validation case
6315faaa test(case007): add airport-capacity solve regression

b833b026 testdata(case008): add invalid incomplete and infeasible validation cases
3a379c53 test(case008): add negative validation and infeasibility regression

33a2d343 feat(validation-suite): add case001-case008 batch acceptance runner
ff32ac01 docs(validation-suite): add case001-case008 batch acceptance report
```

The first Case 001 data commit predates the later naming convention; all subsequent Case-specific commits explicitly include the Case number.

---

# 14. Final acceptance checklist before merge

Before merging `feature/workbench-v1-validation-data` into `main`, complete all of the following:

- full `python -m pytest` passes;
- `python scripts/validate_workbench_v1_cases.py` reports all rows PASS;
- representative Workbench UI smoke test is completed;
- Case 001 baseline remains objective 0;
- Cases 003/005/006/007 variant decisions still flip for the intended reason;
- 008F remains NOT_READY;
- 008G remains READY then infeasible;
- no stale or duplicate validation fixtures remain;
- root README and this document point to the current commands/paths;
- no core solver change has been smuggled into the validation-data closeout.

If all items pass, the branch is ready for final review and merge preparation.

---

# 15. Recommended next action

The next task should be a **manual Workbench UI smoke test and final branch review**, not creation of more synthetic Cases.

The UI review should record, at minimum:

- whether Scenario-only imports render correctly;
- whether Disruption Overlay and Direct Exposure match Case design;
- whether Costs overrides display Baseline versus Effective values correctly;
- whether Constraints/Capacity Heatmap reflect Case 007;
- whether Recovery correctly shows aircraft, crew and passenger changes;
- whether invalid and infeasible Cases surface understandable messages;
- whether exported RecoveredResult matches the automated Oracle.

After that, produce a final freeze/merge report and merge the validation branch into `main`.
