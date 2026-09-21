from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_aircraft_string_column_generation_config,
    load_benders_column_generation_config,
    load_branch_and_price_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
    validate_passenger_capacity_profile,
)
from backend.core import (
    generate_passenger_itineraries,
    solve_benders_with_branch_and_price,
)
from backend.config import load_passenger_itinerary_generation_config
from backend.schemas.columns import RecoveryColumns
from backend.schemas.result import (
    RecoveredResult,
    RunMetadata,
    SolveProfileIds,
    SolveRequest,
)
from backend.schemas.scenario import Scenario
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario
from backend.solver import GurobiAdapter

from .result_builder import build_recovered_result


ROOT = Path(__file__).resolve().parents[2]
APP_VERSION = "0.4.0"
ALGORITHM = "benders_branch_and_price_v1"
PROFILE_FILES = {
    "flight_string_generation": (
        "phase5_test_string_generation_v1.json",
        load_flight_string_generation_config,
    ),
    "crew_pairing_generation": (
        "phase6_test_crew_pairing_generation_v1.json",
        load_crew_pairing_generation_config,
    ),
    "aircraft_string_cg": (
        "phase9_test_aircraft_string_cg_v1.json",
        load_aircraft_string_column_generation_config,
    ),
    "crew_pairing_cg": (
        "phase10_test_crew_pairing_cg_v1.json",
        load_crew_pairing_column_generation_config,
    ),
    "benders_cg": (
        "phase11_test_benders_cg_v1.json",
        load_benders_column_generation_config,
    ),
    "branch_and_price": (
        "phase12_test_branch_and_price_v1.json",
        load_branch_and_price_config,
    ),
}
LIMITED_BRANCH_FILE = "phase13_limited_branch_and_price_v1.json"


class SolveReadinessError(ValueError):
    def __init__(self, codes: list[str], details: list[str] | None = None):
        self.codes = codes
        self.details = details or []
        super().__init__(", ".join(codes + self.details))


def default_profile_ids() -> SolveProfileIds:
    return SolveProfileIds(
        **{
            key: loader(ROOT / "data" / "config" / filename).profile_id
            for key, (filename, loader) in PROFILE_FILES.items()
        }
    )


def solve_readiness(data: Any) -> dict[str, Any]:
    """Input readiness only; never claims optimization feasibility."""
    missing: list[str] = []
    invalid: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {
            "solve_ready": False,
            "missing_inputs": ["missing_scenario"],
            "invalid_profiles": [],
            "warnings": [],
            "semantics": "INPUT_READINESS_NOT_OPTIMIZATION_FEASIBILITY",
        }
    if data.get("schema_version") != "1.0.0":
        invalid.append("schema_version")
    if data.get("algorithm") != ALGORITHM:
        invalid.append("algorithm")
    if not data.get("scenario"):
        missing.append("missing_scenario")
    columns = data.get("recovery_columns")
    if not isinstance(columns, dict) or not columns.get("flight_options"):
        missing.append("missing_flight_options")
    if isinstance(columns, dict) and not columns.get("passenger_itineraries"):
        scenario_data = data.get("scenario")
        if isinstance(scenario_data, dict) and scenario_data.get("passengers"):
            missing.append("missing_passenger_itineraries")
    if data.get("capacity_profile") is None:
        missing.append("missing_capacity_profile")
    if not isinstance(data.get("profile_ids"), dict):
        missing.append("missing_algorithm_profiles")
    else:
        defaults = default_profile_ids().model_dump()
        limited_id = load_branch_and_price_config(
            ROOT / "data/config" / LIMITED_BRANCH_FILE
        ).profile_id
        for key, expected in defaults.items():
            allowed = (
                {expected, limited_id} if key == "branch_and_price" else {expected}
            )
            if data["profile_ids"].get(key) not in allowed:
                invalid.append(key)
    if (
        data.get("cost_profile_id")
        != load_cost_config(
            ROOT / "data/costs/phase2_test_costs_v1.json"
        ).cost_profile_id
    ):
        invalid.append("cost_profile_id")
    if not missing and not invalid:
        scenario, issues = validate_scenario(data["scenario"])
        if issues or scenario is None:
            invalid.append("scenario_semantics")
            warnings.extend(f"{item.code}@{item.location}" for item in issues)
        else:
            parsed, column_issues = validate_recovery_columns(scenario, columns)
            if column_issues or parsed is None:
                invalid.append("recovery_columns_semantics")
                warnings.extend(
                    f"{item.code}@{item.location}" for item in column_issues
                )
            elif parsed.aircraft_strings or parsed.crew_pairings:
                invalid.append("pre_generated_resource_columns")
            else:
                try:
                    from backend.config import PassengerCapacityProfile

                    capacity = PassengerCapacityProfile.model_validate(
                        data["capacity_profile"]
                    )
                    validate_passenger_capacity_profile(capacity, scenario, parsed)
                except (ValidationError, ValueError) as exc:
                    invalid.append("capacity_profile_semantics")
                    warnings.append(str(exc))
        try:
            override = CostOverrideConfig(
                base_cost_profile_id=data["cost_profile_id"],
                overrides=data.get("cost_overrides", {}),
            )
            apply_cost_overrides(
                load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json"),
                override,
            )
        except (ValidationError, ValueError) as exc:
            invalid.append("cost_overrides")
            warnings.append(str(exc))
    return {
        "solve_ready": not missing and not invalid,
        "missing_inputs": missing,
        "invalid_profiles": invalid,
        "warnings": warnings,
        "semantics": "INPUT_READINESS_NOT_OPTIMIZATION_FEASIBILITY",
    }


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if len(value) == 40 else None


def solve_request(
    request: SolveRequest,
    *,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    run_id: str | None = None,
    runtime_controls: dict[str, Any] | None = None,
) -> RecoveredResult:
    readiness = solve_readiness(request.model_dump(mode="json"))
    if not readiness["solve_ready"]:
        raise SolveReadinessError(
            readiness["missing_inputs"] + readiness["invalid_profiles"],
            readiness["warnings"],
        )
    started = datetime.now(timezone.utc)
    tick = perf_counter()
    if event_sink is not None:
        event_sink({"stage": "validation", "type": "stage_completed", "message": "Solve input validated."})
    scenario = Scenario.model_validate(request.scenario)
    columns = RecoveryColumns.model_validate(request.recovery_columns)
    from backend.config import PassengerCapacityProfile

    capacity = PassengerCapacityProfile.model_validate(request.capacity_profile)
    baseline = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        baseline,
        CostOverrideConfig(
            base_cost_profile_id=request.cost_profile_id,
            overrides=request.cost_overrides,
        ),
    )
    configs = {
        key: loader(ROOT / "data/config" / filename)
        for key, (filename, loader) in PROFILE_FILES.items()
    }
    if request.profile_ids.branch_and_price != configs["branch_and_price"].profile_id:
        configs["branch_and_price"] = load_branch_and_price_config(
            ROOT / "data/config" / LIMITED_BRANCH_FILE
        )
    runtime_controls = runtime_controls or {}
    benders_updates = {
        key: runtime_controls[key]
        for key in (
            "max_benders_iterations",
            "absolute_gap_tolerance",
            "relative_gap_tolerance",
        )
        if runtime_controls.get(key) is not None
    }
    if benders_updates:
        configs["benders_cg"] = configs["benders_cg"].model_copy(
            update=benders_updates
        )
    if runtime_controls.get("max_branch_nodes") is not None:
        configs["branch_and_price"] = configs["branch_and_price"].model_copy(
            update={"max_nodes": runtime_controls["max_branch_nodes"]}
        )
    solver_parameters: dict[str, bool | int | float | str] = {}
    if runtime_controls.get("time_limit_seconds") is not None:
        solver_parameters["TimeLimit"] = runtime_controls["time_limit_seconds"]
    if event_sink is not None:
        event_sink({"stage": "optimization", "type": "stage_started", "message": "Exact recovery optimization started."})
    core = solve_benders_with_branch_and_price(
        scenario,
        columns,
        capacity,
        costs,
        configs["flight_string_generation"],
        configs["crew_pairing_generation"],
        configs["aircraft_string_cg"],
        configs["crew_pairing_cg"],
        configs["benders_cg"],
        configs["branch_and_price"],
        solver_factory=lambda: GurobiAdapter(
            output_flag=False, cancel_check=cancel_check
        ),
        solver_parameters=solver_parameters,
        event_sink=event_sink,
    )
    integrated_audit = core.diagnostics.get("integrated_audit")
    if integrated_audit is None:
        phase11_diagnostics = core.diagnostics.get("phase11_diagnostics", {})
        if hasattr(phase11_diagnostics, "get"):
            integrated_audit = phase11_diagnostics.get("integrated_audit")
    if event_sink is not None and integrated_audit is not None:
        event_sink(
            {
                "stage": "audit",
                "type": "audit_completed",
                "message": "Independent integrated constraint audit completed.",
                "metrics": {"integrated_audit": integrated_audit},
            }
        )
    with GurobiAdapter(output_flag=False) as adapter:
        solver_version = adapter.solver_version
    metadata = RunMetadata(
        run_id=run_id or str(uuid4()),
        scenario_id=scenario.scenario_id,
        git_commit=_git_commit(),
        application_version=APP_VERSION,
        solver="gurobi",
        solver_version=solver_version,
        algorithm=ALGORITHM,
        algorithm_profile_ids=request.profile_ids,
        cost_profile_id=costs.cost_profile_id,
        capacity_profile_id=capacity.capacity_profile_id,
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        runtime_seconds=perf_counter() - tick,
    )
    result = build_recovered_result(scenario, columns, core, costs, capacity, metadata)
    result = result.model_copy(
        update={
            "run_metadata": result.run_metadata.model_copy(
                update={
                    "finished_at": datetime.now(timezone.utc),
                    "runtime_seconds": perf_counter() - tick,
                }
            )
        }
    )
    if event_sink is not None:
        event_sink(
            {
                "stage": "result",
                "type": "stage_completed",
                "message": f"Optimization finished with status {result.status.value}.",
                "lower_bound": result.diagnostics.lower_bound,
                "upper_bound": result.diagnostics.upper_bound,
            }
        )
    return result


def example_solve_bundle(case_id: str) -> dict[str, Any]:
    """Explicit demo bundle; does not generate Aircraft/Crew or Flight Options."""
    from backend.application.case_service import CaseCatalogError, load_case

    try:
        case = load_case(case_id)
    except CaseCatalogError:
        case = None
    if case is not None:
        if case["solve_bundle"] is None:
            raise SolveReadinessError(["scenario_only_case"])
        return case["solve_bundle"]

    if case_id == "phase1_benchmark_001":
        columns_file = "phase1_benchmark_001_columns.json"
        capacity_file = "phase2_test_seat_capacity_v1.json"
    elif case_id == "toy_case_016_benders_branch_and_price":
        columns_file = "toy_case_016_benders_branch_and_price_columns.json"
        capacity_file = "toy_case_016_benders_branch_and_price_capacity.json"
    else:
        raise SolveReadinessError(["unknown_example_bundle"])
    scenario = Scenario.model_validate_json(
        (ROOT / "data/examples" / f"{case_id}.json").read_text(encoding="utf-8")
    )
    columns = RecoveryColumns.model_validate_json(
        (ROOT / "data/columns" / columns_file).read_text(encoding="utf-8")
    )
    if case_id == "phase1_benchmark_001":
        itinerary_config = load_passenger_itinerary_generation_config(
            ROOT / "data/config/phase7_test_itinerary_generation_v1.json"
        )
        itineraries = generate_passenger_itineraries(
            scenario, columns.flight_options, None, itinerary_config
        )
        columns = columns.model_copy(
            update={
                "passenger_itineraries": list(itineraries),
            }
        )
    columns = columns.model_copy(update={"aircraft_strings": [], "crew_pairings": []})
    capacity = load_passenger_capacity_profile(ROOT / "data/capacities" / capacity_file)
    baseline = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    return SolveRequest(
        schema_version="1.0.0",
        scenario=scenario.model_dump(mode="json"),
        recovery_columns=columns.model_dump(mode="json"),
        capacity_profile=capacity.model_dump(mode="json"),
        cost_profile_id=baseline.cost_profile_id,
        cost_overrides=(
            {"crew_reassignment": 100.0, "deadhead_per_minute": 1.0}
            if case_id == "toy_case_016_benders_branch_and_price"
            else {}
        ),
        algorithm=ALGORITHM,
        profile_ids=default_profile_ids(),
    ).model_dump(mode="json")
