from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from backend.application.solve_service import (
    ALGORITHM,
    ROOT,
    SolveReadinessError,
    default_profile_ids,
    example_solve_bundle,
    solve_readiness,
    solve_request,
)
from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.schemas.columns import RecoveryColumns
from backend.schemas.result import RecoveredResult, SolveRequest
from backend.schemas.scenario import Scenario


router = APIRouter(prefix="/api/solve", tags=["solver"])
EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "examples"
COLUMNS_DIR = ROOT / "data" / "columns"
CAPACITIES_DIR = ROOT / "data" / "capacities"
VALIDATION_ROOT = ROOT / "data" / "workbench_validation"
VALIDATION_BUNDLES_DIR = VALIDATION_ROOT / "bundles"


def _label(case_id: str) -> str:
    labels = {
        "phase1_benchmark_001": "Phase 1 Benchmark",
        "toy_case_016_benders_branch_and_price": "Toy 016 — Integrality",
    }
    return labels.get(case_id, case_id.replace("_", " ").title())


def _validation_label(case_id: str) -> str:
    labels = {
        "wb_v1_001_baseline": "Validation 001 — Baseline",
        "wb_v1_002_single_delay": "Validation 002 — Single Delay",
        "wb_v1_003_delay_vs_cancel": "Validation 003 — Delay vs Cancellation",
        "wb_v1_003_delay_vs_cancel_low_cancel": "Validation 003 — Low Cancellation Cost",
        "wb_v1_004_aircraft_swap": "Validation 004 — Aircraft Recovery",
        "wb_v1_005_crew_recovery": "Validation 005 — Crew Recovery",
        "wb_v1_005_crew_recovery_high_crew_cost": "Validation 005 — High Crew Cost",
        "wb_v1_006_passenger_connection": "Validation 006 — Passenger Connection",
        "wb_v1_006_passenger_connection_low_capacity": "Validation 006 — Low Capacity",
        "wb_v1_007_capacity_baseline": "Validation 007 — Capacity Baseline",
        "wb_v1_007_capacity_bottleneck": "Validation 007 — Capacity Bottleneck",
        "wb_v1_008g_valid_but_infeasible": "Validation 008G — Expected Infeasible",
    }
    return labels.get(case_id, case_id.replace("_", " ").title())


def _validation_bundle_path(case_id: str) -> Path | None:
    path = VALIDATION_BUNDLES_DIR / f"{case_id}_bundle.json"
    return path if path.exists() else None


def _load_validation_bundle(case_id: str) -> dict[str, Any] | None:
    path = _validation_bundle_path(case_id)
    if path is None:
        return None
    request = SolveRequest.model_validate_json(path.read_text(encoding="utf-8"))
    bundle = request.model_dump(mode="json")
    readiness = solve_readiness(bundle)
    if not readiness["solve_ready"]:
        raise SolveReadinessError(
            readiness["missing_inputs"] + readiness["invalid_profiles"],
            readiness["warnings"],
        )
    return bundle


def _generic_bundle_paths(case_id: str) -> tuple[Path, Path] | None:
    columns = COLUMNS_DIR / f"{case_id}_columns.json"
    capacity = CAPACITIES_DIR / f"{case_id}_capacity.json"
    if not columns.exists() or not capacity.exists():
        return None
    return columns, capacity


def _build_example_bundle(case_id: str) -> dict[str, Any]:
    """Return a solve bundle when repository fixtures can satisfy the current solver contract."""
    try:
        return example_solve_bundle(case_id)
    except SolveReadinessError as exc:
        if "unknown_example_bundle" not in exc.codes:
            raise

    validation_bundle = _load_validation_bundle(case_id)
    if validation_bundle is not None:
        return validation_bundle

    paths = _generic_bundle_paths(case_id)
    scenario_path = EXAMPLES_DIR / f"{case_id}.json"
    if paths is None or not scenario_path.exists():
        raise SolveReadinessError(["unknown_example_bundle"])

    columns_path, capacity_path = paths
    scenario = Scenario.model_validate_json(scenario_path.read_text(encoding="utf-8"))
    columns = RecoveryColumns.model_validate_json(columns_path.read_text(encoding="utf-8"))
    # The current exact solve generates aircraft strings and crew pairings internally.
    # Historical fixture columns may contain pre-generated resource columns that the
    # current readiness contract intentionally rejects, so keep only the prepared
    # flight options and passenger itineraries here.
    columns = columns.model_copy(update={"aircraft_strings": [], "crew_pairings": []})
    capacity = load_passenger_capacity_profile(capacity_path)
    baseline = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    bundle = SolveRequest(
        schema_version="1.0.0",
        scenario=scenario.model_dump(mode="json"),
        recovery_columns=columns.model_dump(mode="json"),
        capacity_profile=capacity.model_dump(mode="json"),
        cost_profile_id=baseline.cost_profile_id,
        cost_overrides={},
        algorithm=ALGORITHM,
        profile_ids=default_profile_ids(),
    ).model_dump(mode="json")
    readiness = solve_readiness(bundle)
    if not readiness["solve_ready"]:
        raise SolveReadinessError(
            readiness["missing_inputs"] + readiness["invalid_profiles"],
            readiness["warnings"],
        )
    return bundle


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
    """List core examples and Workbench validation bundles for the UI catalog."""
    result: list[dict[str, Any]] = []
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        case_id = path.stem
        solve_ready = False
        description = "Scenario-only example for inspection and validation"
        try:
            _build_example_bundle(case_id)
            solve_ready = True
            description = "Scenario plus matching repository solve fixtures"
        except (SolveReadinessError, ValidationError, ValueError, OSError):
            pass
        result.append(
            {
                "case_id": case_id,
                "label": _label(case_id),
                "type": "solve_bundle" if solve_ready else "scenario",
                "solve_ready": solve_ready,
                "description": description,
                "source": "core_example",
                "group": "core" if solve_ready else "scenario",
                "expected_status": None,
            }
        )

    for path in sorted(VALIDATION_BUNDLES_DIR.glob("*_bundle.json")):
        case_id = path.name.removesuffix("_bundle.json")
        expected_status = "infeasible" if case_id == "wb_v1_008g_valid_but_infeasible" else "optimal"
        group = "boundary" if case_id.startswith("wb_v1_008") else "validation"
        try:
            _load_validation_bundle(case_id)
        except (SolveReadinessError, ValidationError, ValueError, OSError):
            continue
        result.append(
            {
                "case_id": case_id,
                "label": _validation_label(case_id),
                "type": "solve_bundle",
                "solve_ready": True,
                "description": (
                    "Validation boundary case; input-ready but expected optimization infeasible"
                    if expected_status == "infeasible"
                    else "Workbench v1 system validation Solve Bundle"
                ),
                "source": "workbench_validation",
                "group": group,
                "expected_status": expected_status,
            }
        )
    return result


@router.get("/example-bundle/{case_id}")
def example_bundle(case_id: str) -> dict[str, Any]:
    try:
        return _build_example_bundle(case_id)
    except SolveReadinessError as exc:
        raise HTTPException(status_code=404, detail=exc.codes) from exc
    except (ValidationError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
