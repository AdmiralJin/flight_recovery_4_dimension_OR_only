from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from backend.application.solve_service import (
    SolveReadinessError,
    example_solve_bundle,
    solve_readiness,
    solve_request,
)
from backend.schemas.result import RecoveredResult, SolveRequest


router = APIRouter(prefix="/api/solve", tags=["solver"])
EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "examples"
SOLVE_READY_EXAMPLES = {
    "phase1_benchmark_001": {
        "label": "Phase 1 Benchmark",
        "description": "Main 4D recovery benchmark",
    },
    "toy_case_016_benders_branch_and_price": {
        "label": "Toy 016 — Integrality",
        "description": "Phase 12 Branch-and-Price integrality case",
    },
}


@router.post("", response_model=RecoveredResult)
def solve(data: Any = Body(...)) -> RecoveredResult:
    try:
        readiness = solve_readiness(data)
        if not readiness["solve_ready"]:
            raise SolveReadinessError(
                readiness["missing_inputs"] + readiness["invalid_profiles"],
                readiness["warnings"],
            )
        request = SolveRequest.model_validate(data)
        return solve_request(request)
    except SolveReadinessError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "not_solve_ready",
                "codes": exc.codes,
                "details": exc.details,
            },
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_input",
                "errors": exc.errors(include_context=False),
            },
        ) from exc


@router.post("/precheck")
def precheck(data: Any = Body(...)) -> dict[str, Any]:
    return solve_readiness(data)


@router.get("/examples")
def solve_examples() -> list[dict[str, Any]]:
    """List supported demo inputs so the UI does not own this catalog."""
    result = [
        {
            "case_id": case_id,
            "type": "solve_bundle",
            "solve_ready": True,
            **metadata,
        }
        for case_id, metadata in SOLVE_READY_EXAMPLES.items()
    ]
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        case_id = path.stem
        if case_id in SOLVE_READY_EXAMPLES:
            continue
        result.append(
            {
                "case_id": case_id,
                "label": case_id.replace("_", " ").title(),
                "type": "scenario",
                "solve_ready": False,
                "description": "Scenario-only example for inspection and validation",
            }
        )
    return result


@router.get("/example-bundle/{case_id}")
def example_bundle(case_id: str) -> dict[str, Any]:
    try:
        return example_solve_bundle(case_id)
    except SolveReadinessError as exc:
        raise HTTPException(status_code=404, detail=exc.codes) from exc
