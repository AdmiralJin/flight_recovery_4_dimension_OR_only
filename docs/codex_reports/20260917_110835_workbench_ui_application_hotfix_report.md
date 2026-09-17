# Workbench UI / Application Hotfix Report

Timestamp: 2026-09-17 11:08:35 Asia/Shanghai

## Scope

Implemented the application-layer work from `WORKBENCH_UI_APPLICATION_HOTFIX_AND_UX_ENHANCEMENT_PLAN.md`. The solver core, mathematical constraints, pricing, Benders, and Branch-and-Price code were not changed.

## Delivered

- Added `GET /api/solve/examples` with two solve-ready bundles (`phase1_benchmark_001`, `toy_case_016_benders_branch_and_price`) and one scenario-only example (`toy_case_001`).
- Added a server-driven case selector, URL case selection (`?case=...`), explicit Solve-input/Solver/Result status indicators, and a global toast surface.
- Added unified bundle application so Scenario, Recovery Columns, Passenger Capacity, and case-specific cost overrides always move together.
- Added case baseline capture, `Reset Changes`, and `Reload Example`. Reset now preserves the selected case's baseline overrides (including Toy 016).
- Added input revisions, pre-readiness Solve locking, duplicate-request protection, elapsed-time status, UI input locking, and stale-result discard protection.
- Bound the Constraints capacity summary to the current case; scenario-only cases explicitly report missing capacity instead of displaying benchmark fallback data.
- Reworked Import/Export around Scenario JSON, Solve Bundle JSON, and round-trippable `workbench_snapshot_v1` snapshots.
- Added robust HTTP text/JSON error parsing and visible user feedback.
- Updated README and reproduction notes; added API and frontend regression coverage.

## Verification

```text
python -m pytest
429 passed, 1 external-library deprecation warning

node --test tests/frontend/workbench.test.mjs tests/frontend/visualization.test.mjs
19 passed

node --check frontend/js/app.js
node --check frontend/js/api.js
git diff --check
all passed
```

## Notes

- The existing synchronous solver remains unchanged. The UI reports long-running solves but does not claim to cancel a Gurobi solve.
- The source plan is an existing untracked review artifact and was intentionally left untouched.
