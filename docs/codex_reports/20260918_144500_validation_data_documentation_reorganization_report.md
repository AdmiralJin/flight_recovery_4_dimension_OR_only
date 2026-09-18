# Validation Data Documentation Reorganization Report

- Date: 2026-09-18
- Branch: `feature/workbench-v1-validation-data`
- Purpose: consolidate all Workbench v1 validation-data documentation under `docs/`.

## Changes

Created:

```text
docs/validation_data/README.md
docs/validation_data/WORKBENCH_V1_VALIDATION_DATA_GUIDE.md
```

The detailed Case documentation previously living in:

```text
data/workbench_validation/README.md
```

has been migrated and expanded into the canonical guide under `docs/validation_data/`.

The data-directory README is now intentionally short and acts as an index to executable fixtures and the canonical documentation.

The root README is updated to point users to the canonical guide.

## Guide contents

The new guide records:

- branch baseline and scope;
- file/directory contracts;
- Case 001–008 construction history;
- purposes and design decisions;
- corrections discovered during actual Solve/CI;
- expected objectives and recovery decisions;
- automated test commands;
- manual Workbench smoke-test steps;
- failure interpretation;
- branch commit history;
- final merge acceptance checklist.

## Documentation ownership rule

Future changes to validation fixtures should update:

1. the relevant JSON fixture;
2. its detailed regression test;
3. the canonical guide under `docs/validation_data/`.

The short `data/workbench_validation/README.md` should remain an index rather than regrowing into a second competing long-form specification.
