import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from backend.config import load_passenger_capacity_profile
from backend.core.constraint_registry import list_constraint_metadata
from backend.schemas.common import SchemaModel
from backend.services.constraint_precheck import precheck_constraints


router = APIRouter(prefix="/api/model/constraints", tags=["model-metadata"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAPACITY_PROFILE_PATH = (
    PROJECT_ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
)
BENCHMARK_COLUMNS_PATH = (
    PROJECT_ROOT / "data" / "columns" / "phase1_benchmark_001_columns.json"
)


class ConstraintPrecheckRequest(SchemaModel):
    scenario: Any
    recovery_columns: Any | None = None
    capacity_profile: Any | None = None


@router.get("")
def get_constraints() -> dict:
    capacity = load_passenger_capacity_profile(CAPACITY_PROFILE_PATH)
    return {
        "model_profile": "phase2_fixed_column",
        "precheck_semantics": "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY",
        "constraints": [item.model_dump(mode="json") for item in list_constraint_metadata()],
        "capacity_profile_summary": {
            "capacity_profile_id": capacity.capacity_profile_id,
            "scenario_id": capacity.scenario_id,
            "source": capacity.source.value,
            "units": capacity.units,
            "seat_capacity_by_option_id": dict(
                capacity.seat_capacity_by_option_id
            ),
            "notes": list(capacity.notes),
            "display_label": "TEST / RESIDUAL CAPACITY",
            "not_physical_aircraft_capacity": True,
        },
    }


@router.get("/benchmark-inputs")
def get_benchmark_precheck_inputs() -> dict:
    capacity = load_passenger_capacity_profile(CAPACITY_PROFILE_PATH)
    columns = json.loads(BENCHMARK_COLUMNS_PATH.read_text(encoding="utf-8"))
    return {
        "scenario_id": columns["scenario_id"],
        "recovery_columns": columns,
        "passenger_capacity_profile": capacity.model_dump(mode="json"),
    }


@router.post("/precheck")
def constraint_precheck(request: ConstraintPrecheckRequest) -> dict:
    return precheck_constraints(
        request.scenario,
        request.recovery_columns,
        request.capacity_profile,
    )
