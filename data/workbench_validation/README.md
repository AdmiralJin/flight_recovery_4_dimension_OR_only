# Workbench v1 Validation Data

This directory stores the executable data fixtures for Workbench v1 system acceptance.

The canonical documentation has been moved to:

```text
docs/validation_data/WORKBENCH_V1_VALIDATION_DATA_GUIDE.md
```

Documentation index:

```text
docs/validation_data/README.md
```

## Data layout

```text
data/workbench_validation/
├── scenarios/    # Scenario-only inputs for Data / Validate / Visualization
├── columns/      # Recovery Columns: Flight Options and explicit Passenger Itineraries
├── capacities/   # Residual passenger-seat capacity profiles
├── bundles/      # Complete SolveRequest payloads for Precheck / Solve / Recovery
├── expected/     # Human Oracle / regression expectations
└── negative/     # Intentionally invalid or incomplete Case 008 fixtures
```

## Fast verification

From the repository root:

```bash
python scripts/validate_workbench_v1_cases.py
```

Detailed regression tests:

```bash
python -m pytest tests/regression/test_workbench_v1_case001.py
python -m pytest tests/regression/test_workbench_v1_case002.py
python -m pytest tests/regression/test_workbench_v1_case003.py
python -m pytest tests/regression/test_workbench_v1_case004.py
python -m pytest tests/regression/test_workbench_v1_case005.py
python -m pytest tests/regression/test_workbench_v1_case006.py
python -m pytest tests/regression/test_workbench_v1_case007.py
python -m pytest tests/regression/test_workbench_v1_case008.py
```

Do not treat this short README as the full acceptance specification. Use the canonical guide under `docs/validation_data/`.
