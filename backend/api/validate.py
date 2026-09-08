from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from backend.services.validator import validation_payload

router = APIRouter(prefix="/api", tags=["validation"])


@router.post("/validate")
def validate(data: Any = Body(...)) -> JSONResponse:
    payload, status = validation_payload(data)
    return JSONResponse(payload, status_code=status)


@router.post("/solve")
def solve_guard(data: Any = Body(...)) -> JSONResponse:
    payload, status = validation_payload(data)
    if status != 200:
        payload["message"] = "Invalid scenario was blocked before optimization."
        return JSONResponse(payload, status_code=422)
    return JSONResponse(
        {
            "status": "not_implemented",
            "message": "Phase 0 validates data only; optimization starts after Phase 0 acceptance.",
        },
        status_code=501,
    )

