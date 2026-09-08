# AIR Recovery Reproduction

Phase 0 of a staged reproduction of Petersen et al. (2010), *An Optimization Approach to Airline Integrated Recovery*.

This version provides a strict scenario schema, cross-entity validation, a stable toy case and a browser-based JSON editor. It intentionally contains no optimization model.

## Run

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Verify

```powershell
python -m pytest
```

## API

- `GET /api/health` - service and phase status
- `GET /api/examples/toy_case_001` - stable example payload
- `POST /api/validate` - structural and cross-entity validation
- `POST /api/solve` - Phase 0 safety gate; rejects invalid input and returns 501 for valid input

Validation failures use machine-readable locations such as `flights[0].origin`, together with a code and message. A successful response includes normalized JSON suitable for a deterministic export/import round trip.

Implementation choices not specified by the paper are tracked in [assumptions.md](assumptions.md). Paper-to-code scope notes are in [reproduction_notes.md](reproduction_notes.md).

