from __future__ import annotations

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


@router.get("/example-bundle/{case_id}")
def example_bundle(case_id: str) -> dict[str, Any]:
    try:
        return example_solve_bundle(case_id)
    except SolveReadinessError as exc:
        raise HTTPException(status_code=404, detail=exc.codes) from exc
