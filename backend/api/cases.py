from fastapi import APIRouter, HTTPException

from backend.application.case_service import CaseCatalogError, list_cases, load_case


router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def catalog() -> dict:
    return list_cases()


@router.get("/{case_id}")
def case(case_id: str) -> dict:
    try:
        return load_case(case_id)
    except CaseCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
