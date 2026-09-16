from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from backend.services.validator import validation_payload

router = APIRouter(prefix="/api", tags=["validation"])


@router.post("/validate")
def validate(data: Any = Body(...)) -> JSONResponse:
    payload, status = validation_payload(data)
    return JSONResponse(payload, status_code=status)
