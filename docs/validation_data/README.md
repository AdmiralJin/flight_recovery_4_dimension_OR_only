# Validation Data Documentation

This directory is the canonical home for documentation about validation, benchmark and acceptance data that are intended to verify Workbench behavior.

## Current document

- `WORKBENCH_V1_VALIDATION_DATA_GUIDE.md` — complete Case 001–008 design history, purpose, data layout, expected results, automated testing, manual Workbench testing and final acceptance checklist.

## Related executable assets

- `data/workbench_validation/` — JSON fixtures.
- `tests/regression/test_workbench_v1_case001.py` through `test_workbench_v1_case008.py` — detailed regression assertions.
- `scripts/validate_workbench_v1_cases.py` — batch acceptance runner.
- `.github/workflows/tests.yml` — CI entry point.
- `docs/codex_reports/` — timestamped implementation/closeout reports required by repository policy.

When validation data change, update the canonical guide in this directory together with the fixture and regression test so that design intent, expected behavior and executable assertions remain synchronized.
