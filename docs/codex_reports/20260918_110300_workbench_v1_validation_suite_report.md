# Workbench v1 Validation Suite Batch Acceptance Report

- Date: 2026-09-18
- Branch: `feature/workbench-v1-validation-data`
- Validation feature commit: `33a2d3434ea1180d935a87c91b1d8f264a0ccaf3`
- Scope: Case 001–008 validation-data closeout step
- Core solver mathematics changed: **No**

## 1. Completed Work

This step converts the individually verified Workbench v1 validation cases into a repeatable system-level acceptance suite.

Added:

- `scripts/validate_workbench_v1_cases.py`
- CI execution of the batch acceptance runner after the normal pytest suite
- validation-suite Quick Start and case matrix in `data/workbench_validation/README.md`
- validation-suite entry point in the repository root `README.md`

The runner uses the same FastAPI application in-process through `TestClient`; it does not bypass the formal Solve API.

## 2. Batch Coverage

The runner covers:

- Case 001 baseline
- Case 002 single-delay propagation
- Case 003 default-cost and low-cancellation-cost variants
- Case 004 aircraft recovery
- Case 005 default and high-crew-reassignment-cost variants
- Case 006 default and low-residual-capacity variants
- Case 007 baseline and bottleneck-capacity variants
- Case 008A–008E invalid Scenario inputs
- Case 008F valid Scenario but incomplete Solve input
- Case 008G Solve-ready but optimization-infeasible input

Total batch rows: **18**.

Each row reports:

```text
Case ID
Validate
Precheck
Solve Status
Expected Check
PASS/FAIL
```

The command returns a non-zero exit code if any row fails.

## 3. Commands

Full acceptance suite:

```bash
python scripts/validate_workbench_v1_cases.py
```

Filtered examples:

```bash
python scripts/validate_workbench_v1_cases.py --case 006
python scripts/validate_workbench_v1_cases.py --case 003/default
python scripts/validate_workbench_v1_cases.py --case 008
```

The detailed regression tests remain authoritative for case-specific assertions:

```text
tests/regression/test_workbench_v1_case001.py
...
tests/regression/test_workbench_v1_case008.py
```

The batch runner is an acceptance summary and does not replace those stronger tests.

## 4. CI Verification

GitHub Actions run for feature commit:

```text
35301604695
```

Results:

```text
pytest:
450 passed
0 failed
2 warnings

Workbench v1 batch acceptance:
18/18 PASS
```

Key negative boundary confirmed:

```text
008G
Validate       = PASS
Precheck       = READY
Solve Status   = infeasible
Expected Check = PASS
```

This directly confirms:

```text
INPUT READINESS != OPTIMIZATION FEASIBILITY
```

and preserves the non-optimal result contract: no fake recovered decisions are emitted.

## 5. Documentation / Workbench Usage

`data/workbench_validation/README.md` now explains:

- how to start Workbench;
- which files are Scenario-only versus complete Solve Bundles;
- how to run the batch acceptance suite;
- how to filter by Case;
- what each Case 001–008 primarily validates;
- where Expected / Oracle files are stored.

The root README now exposes the validation suite so it is discoverable without browsing the data directory first.

## 6. Current Validation Status

At this point:

- Case 001–007 normal acceptance data exist and have formal Solve regression coverage;
- Case 008 invalid/incomplete/infeasible coverage exists;
- each Case has Expected data or equivalent negative expected behavior;
- detailed pytest regressions pass;
- unified batch acceptance passes;
- CI runs both detailed tests and the system-level batch runner.

## 7. Recommended Next Step

Do not add more synthetic business cases before closeout.

Next recommended task:

1. perform a focused manual Workbench UI smoke test using representative Cases;
2. verify Data / Visualization / Costs / Constraints / Precheck / Recovery display behavior;
3. perform a final branch review for naming, stale files and documentation consistency;
4. if all checks pass, prepare merge of `feature/workbench-v1-validation-data` into `main`.

