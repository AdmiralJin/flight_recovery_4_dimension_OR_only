from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_cost_config,
)


router = APIRouter(prefix="/api/config", tags=["configuration"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COST_PROFILE_PATH = PROJECT_ROOT / "data" / "costs" / "phase2_test_costs_v1.json"


def _canonical_costs():
    return load_cost_config(COST_PROFILE_PATH)


@router.get("/costs")
def get_costs() -> dict:
    return _canonical_costs().model_dump(mode="json")


@router.post("/costs/validate-overrides")
def validate_cost_overrides(config: CostOverrideConfig) -> dict:
    baseline = _canonical_costs()
    try:
        effective = apply_cost_overrides(baseline, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "valid": True,
        "base_cost_profile_id": baseline.cost_profile_id,
        "overrides": config.overrides,
        "effective_profile": effective.model_dump(mode="json"),
    }
