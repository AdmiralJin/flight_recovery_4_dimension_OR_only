from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from backend.config.costs import (
    CrewPairingCostBreakdown,
    FixedColumnCostConfig,
    crew_pairing_cost,
)
from backend.schemas.columns import (
    CrewSegmentType,
    FlightOperationType,
    RecoveryColumns,
)
from backend.schemas.model_result import ModelSolveResult
from backend.schemas.scenario import Scenario
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario
from backend.solver.base import (
    ConstraintSense,
    SolverAdapter,
    VariableHandle,
    VariableType,
)

from .crew_incidence import CrewRecoveryIncidence, build_crew_recovery_incidence
from .indices import RecoveryIndices, build_recovery_indices


CRM_C01_PAIRING_SELECTION = "CRM-C01-CREW-PAIRING-SELECTION"
CRM_C02_OPTION_COVERAGE = "CRM-C02-FLIGHT-OPTION-COVERAGE"
CRM_C03_NONREQUIRED_PROHIBITION = "CRM-C03-NONREQUIRED-REVENUE-PROHIBITION"
CRM_C04_CREW_FEASIBILITY = "CRM-C04-CREW-FEASIBILITY"
CRM_C05_TERMINAL_OWNERSHIP = "CRM-C05-TERMINAL-OR-OWNERSHIP"

CRM_MODEL_NAME = "fixed_column_crm"
CRM_FEASIBILITY_TOLERANCE = 1e-6

CONSTRAINT_PROVENANCE = MappingProxyType(
    {
        CRM_C01_PAIRING_SELECTION: (
            "paper_constraint:(3.15)+fixed_pairing_mapping_assumption:A-041"
        ),
        CRM_C02_OPTION_COVERAGE: (
            "paper_constraint:(3.14)+single_crew_unit_mapping_assumption:A-042"
        ),
        CRM_C03_NONREQUIRED_PROHIBITION: ("implementation_guard:A-043"),
        CRM_C04_CREW_FEASIBILITY: ("fixed-column_validation:A-044"),
        CRM_C05_TERMINAL_OWNERSHIP: (
            "fixed-column_validation+implementation_guard:A-044"
        ),
    }
)


class CrmBuildError(ValueError):
    """Validated inputs cannot be mapped to the Fixed-Column CRM contract."""


@dataclass(frozen=True)
class CrewRecoveryRequest:
    scenario_id: str
    required_operated_option_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id must not be empty")
        if isinstance(self.required_operated_option_ids, str):
            raise TypeError("required_operated_option_ids must be an iterable of IDs")
        option_ids = tuple(self.required_operated_option_ids)
        if any(not option_id for option_id in option_ids):
            raise ValueError("required operated option IDs must not be empty")
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("required_operated_option_ids must be unique")
        object.__setattr__(self, "required_operated_option_ids", option_ids)

    @classmethod
    def from_option_ids(
        cls,
        scenario_id: str,
        option_ids: Iterable[str],
    ) -> CrewRecoveryRequest:
        return cls(scenario_id, tuple(option_ids))


@dataclass(frozen=True)
class FixedColumnCrmModel:
    scenario: Scenario
    columns: RecoveryColumns
    request: CrewRecoveryRequest
    indices: RecoveryIndices
    incidence: CrewRecoveryIncidence
    variables: Mapping[str, VariableHandle]
    pairing_costs: Mapping[str, CrewPairingCostBreakdown]


def _validation_message(scope: str, issues) -> str:
    details = "; ".join(
        f"{item.code}@{item.location}: {item.message}" for item in issues
    )
    return f"{scope} validation failed: {details}"


def _validated_inputs(
    scenario_data: Any,
    columns_data: Any,
) -> tuple[Scenario, RecoveryColumns]:
    scenario, scenario_issues = validate_scenario(scenario_data)
    if scenario is None or scenario_issues:
        raise CrmBuildError(_validation_message("scenario", scenario_issues))
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    if columns is None or column_issues:
        raise CrmBuildError(_validation_message("columns", column_issues))
    return scenario, columns


def _validate_request(
    scenario: Scenario,
    columns: RecoveryColumns,
    request: CrewRecoveryRequest,
) -> None:
    if request.scenario_id != scenario.scenario_id:
        raise CrmBuildError(
            "CRM request scenario_id differs from validated Scenario: "
            f"{request.scenario_id!r} != {scenario.scenario_id!r}"
        )

    options = {option.option_id: option for option in columns.flight_options}
    base_flights: dict[str, str] = {}
    for option_id in request.required_operated_option_ids:
        option = options.get(option_id)
        if option is None:
            raise CrmBuildError(f"unknown required operated option: {option_id!r}")
        if (
            option.operation_type is not FlightOperationType.OPERATE
            or option.base_flight_id is None
        ):
            raise CrmBuildError(
                f"required option {option_id!r} is not a revenue operate option"
            )
        previous = base_flights.get(option.base_flight_id)
        if previous is not None:
            raise CrmBuildError(
                "CRM request contains conflicting schedule options for base flight "
                f"{option.base_flight_id!r}: {previous!r}, {option_id!r}"
            )
        base_flights[option.base_flight_id] = option_id


def _validate_pairing_flight_segments(columns: RecoveryColumns) -> None:
    options = {option.option_id: option for option in columns.flight_options}
    for pairing in columns.crew_pairings:
        for duty in pairing.duties:
            for segment in duty.segments:
                if segment.segment_type not in {
                    CrewSegmentType.OPERATE,
                    CrewSegmentType.DEADHEAD,
                }:
                    continue
                option = options[segment.flight_option_id or ""]
                if option.operation_type is not FlightOperationType.OPERATE:
                    raise CrmBuildError(
                        f"{CRM_C04_CREW_FEASIBILITY}: pairing "
                        f"{pairing.pairing_id!r} {segment.segment_type.value} "
                        "segment must reference a revenue operate option, got "
                        f"{option.option_id!r}"
                    )


def _constraint_name(constraint_id: str, instance: str) -> str:
    return f"{constraint_id}[{instance}]"


def build_fixed_column_crm(
    scenario: Scenario,
    columns: RecoveryColumns,
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
) -> FixedColumnCrmModel:
    """Build, but do not solve, the Phase 2.4 Fixed-Column CRM."""

    _validate_request(scenario, columns, request)
    _validate_pairing_flight_segments(columns)
    try:
        indices = build_recovery_indices(scenario, columns)
        incidence = build_crew_recovery_incidence(scenario, columns, indices)
    except (KeyError, ValueError) as exc:
        raise CrmBuildError(f"CRM incidence build failed: {exc}") from exc

    crews_by_id = {crew.crew_id: crew for crew in scenario.crew}
    pairings_by_id = {pairing.pairing_id: pairing for pairing in columns.crew_pairings}
    options_by_id = {option.option_id: option for option in columns.flight_options}

    for crew_id in indices.crew.ids:
        candidate_ids = incidence.crew_to_pairings.columns_for_row(crew_id)
        if not candidate_ids:
            raise CrmBuildError(
                f"{CRM_C01_PAIRING_SELECTION}: crew {crew_id!r} has no "
                "explicit candidate pairing"
            )

    try:
        pairing_costs = {
            pairing_id: crew_pairing_cost(
                scenario,
                options_by_id,
                pairings_by_id[pairing_id],
                costs,
            )
            for pairing_id in indices.crew_pairings.ids
        }
    except ValueError as exc:
        raise CrmBuildError(f"CRM pairing cost build failed: {exc}") from exc

    solver.create_model(CRM_MODEL_NAME)
    variables = {
        pairing_id: solver.add_variable(
            f"z[{pairing_id}]", variable_type=VariableType.BINARY
        )
        for pairing_id in indices.crew_pairings.ids
    }
    solver.set_objective(
        {
            variables[pairing_id]: breakdown.total
            for pairing_id, breakdown in pairing_costs.items()
        }
    )

    for crew_id in indices.crew.ids:
        candidate_ids = incidence.crew_to_pairings.columns_for_row(crew_id)
        solver.add_linear_constraint(
            {variables[pairing_id]: 1.0 for pairing_id in candidate_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(CRM_C01_PAIRING_SELECTION, crew_id),
        )

    required = set(request.required_operated_option_ids)
    for option_id in request.required_operated_option_ids:
        covering_pairings = incidence.operated_option_to_pairings.columns_for_row(
            option_id
        )
        solver.add_linear_constraint(
            {variables[pairing_id]: 1.0 for pairing_id in covering_pairings},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(CRM_C02_OPTION_COVERAGE, option_id),
        )

    for option_id in indices.revenue_operate_options.ids:
        if option_id in required:
            continue
        operating_pairings = incidence.operated_option_to_pairings.columns_for_row(
            option_id
        )
        solver.add_linear_constraint(
            {variables[pairing_id]: 1.0 for pairing_id in operating_pairings},
            ConstraintSense.EQUAL,
            0.0,
            name=_constraint_name(
                CRM_C03_NONREQUIRED_PROHIBITION,
                f"operate:{option_id}",
            ),
        )
        deadhead_pairings = incidence.deadhead_option_to_pairings.columns_for_row(
            option_id
        )
        solver.add_linear_constraint(
            {variables[pairing_id]: 1.0 for pairing_id in deadhead_pairings},
            ConstraintSense.EQUAL,
            0.0,
            name=_constraint_name(
                CRM_C03_NONREQUIRED_PROHIBITION,
                f"deadhead:{option_id}",
            ),
        )

    for crew_id in indices.crew.ids:
        crew = crews_by_id[crew_id]
        terminal_compatible = tuple(
            pairing_id
            for pairing_id in incidence.crew_to_pairings.columns_for_row(crew_id)
            if pairings_by_id[pairing_id].end_station == crew.required_station_at_T_end
        )
        solver.add_linear_constraint(
            {variables[pairing_id]: 1.0 for pairing_id in terminal_compatible},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(CRM_C05_TERMINAL_OWNERSHIP, crew_id),
        )

    return FixedColumnCrmModel(
        scenario=scenario,
        columns=columns,
        request=request,
        indices=indices,
        incidence=incidence,
        variables=MappingProxyType(variables),
        pairing_costs=MappingProxyType(pairing_costs),
    )


def _check(
    constraint_id: str,
    instance: str,
    lhs: float,
    rhs: float,
) -> dict[str, Any]:
    satisfied = abs(lhs - rhs) <= CRM_FEASIBILITY_TOLERANCE
    return {
        "constraint_id": constraint_id,
        "instance": instance,
        "lhs": lhs,
        "sense": "==",
        "rhs": rhs,
        "slack": -abs(lhs - rhs),
        "satisfied": satisfied,
        "provenance": CONSTRAINT_PROVENANCE[constraint_id],
    }


def analyze_crm_fixed_columns(model: FixedColumnCrmModel) -> dict[str, Any]:
    """Report schedule-compatible fixed pairing availability before solving."""

    required = set(model.request.required_operated_option_ids)
    crews_by_id = {crew.crew_id: crew for crew in model.scenario.crew}
    pairings_by_id = {
        pairing.pairing_id: pairing for pairing in model.columns.crew_pairings
    }
    eligible_by_crew: dict[str, list[str]] = {}
    eligible_pairing_ids: set[str] = set()
    rejected_operating: dict[str, list[str]] = {}
    rejected_deadhead: dict[str, list[str]] = {}

    for crew_id in model.indices.crew.ids:
        crew = crews_by_id[crew_id]
        eligible_by_crew[crew_id] = []
        for pairing_id in model.incidence.crew_to_pairings.columns_for_row(crew_id):
            unexpected_operating = [
                option_id
                for option_id in model.incidence.pairing_to_operated_options[pairing_id]
                if option_id not in required
            ]
            unexpected_deadhead = [
                option_id
                for option_id in model.incidence.pairing_to_deadhead_options[pairing_id]
                if option_id not in required
            ]
            if unexpected_operating:
                rejected_operating[pairing_id] = unexpected_operating
            if unexpected_deadhead:
                rejected_deadhead[pairing_id] = unexpected_deadhead
            if unexpected_operating or unexpected_deadhead:
                continue
            if pairings_by_id[pairing_id].end_station != crew.required_station_at_T_end:
                continue
            eligible_by_crew[crew_id].append(pairing_id)
            eligible_pairing_ids.add(pairing_id)

    required_covering = {
        option_id: [
            pairing_id
            for pairing_id in model.incidence.operated_option_to_pairings.columns_for_row(
                option_id
            )
            if pairing_id in eligible_pairing_ids
        ]
        for option_id in model.request.required_operated_option_ids
    }
    return {
        "eligible_pairing_ids_by_crew": eligible_by_crew,
        "crew_without_schedule_compatible_pairing": [
            crew_id
            for crew_id, pairing_ids in eligible_by_crew.items()
            if not pairing_ids
        ],
        "required_option_covering_eligible_pairings": required_covering,
        "required_options_without_eligible_operating_pairing": [
            option_id
            for option_id, pairing_ids in required_covering.items()
            if not pairing_ids
        ],
        "pairings_rejected_for_operating_leakage": rejected_operating,
        "pairings_rejected_for_deadhead_leakage": rejected_deadhead,
    }


def recompute_crm_diagnostics(
    model: FixedColumnCrmModel,
    pairing_values: Mapping[str, float],
    costs: FixedColumnCostConfig,
) -> dict[str, Any]:
    """Independently recalculate every Phase 2.4 CRM constraint and cost."""

    expected_pairing_ids = set(model.variables)
    actual_pairing_ids = set(pairing_values)
    if actual_pairing_ids != expected_pairing_ids:
        unknown = sorted(actual_pairing_ids - expected_pairing_ids)
        missing = sorted(expected_pairing_ids - actual_pairing_ids)
        raise CrmBuildError(
            "CRM audit pairing IDs differ from model; "
            f"unknown={unknown}, missing={missing}"
        )

    scenario = model.scenario
    columns = model.columns
    incidence = model.incidence
    crews_by_id = {crew.crew_id: crew for crew in scenario.crew}
    pairings_by_id = {pairing.pairing_id: pairing for pairing in columns.crew_pairings}
    options_by_id = {option.option_id: option for option in columns.flight_options}
    selected_pairing_ids = {
        pairing_id for pairing_id, value in pairing_values.items() if value > 0.5
    }

    selected_pairing_by_crew: dict[str, str] = {}
    selection_checks = []
    terminal_checks = []
    for crew_id in model.indices.crew.ids:
        candidate_ids = incidence.crew_to_pairings.columns_for_row(crew_id)
        lhs = sum(pairing_values[pairing_id] for pairing_id in candidate_ids)
        selection_checks.append(_check(CRM_C01_PAIRING_SELECTION, crew_id, lhs, 1.0))
        selected = [
            pairing_id
            for pairing_id in candidate_ids
            if pairing_id in selected_pairing_ids
        ]
        if len(selected) == 1:
            selected_pairing_by_crew[crew_id] = selected[0]

        crew = crews_by_id[crew_id]
        terminal_lhs = sum(
            pairing_values[pairing_id]
            for pairing_id in candidate_ids
            if pairings_by_id[pairing_id].end_station == crew.required_station_at_T_end
        )
        terminal = _check(
            CRM_C05_TERMINAL_OWNERSHIP,
            crew_id,
            terminal_lhs,
            1.0,
        )
        terminal["required_station"] = crew.required_station_at_T_end
        terminal["selected_pairing_id"] = selected[0] if len(selected) == 1 else None
        terminal["selected_end_station"] = (
            pairings_by_id[selected[0]].end_station if len(selected) == 1 else None
        )
        terminal_checks.append(terminal)

    operating_coverage = {
        option_id: sum(
            pairing_values[pairing_id]
            for pairing_id in incidence.operated_option_to_pairings.columns_for_row(
                option_id
            )
        )
        for option_id in model.indices.revenue_operate_options.ids
    }
    deadhead_presence = {
        option_id: sum(
            pairing_values[pairing_id]
            for pairing_id in incidence.deadhead_option_to_pairings.columns_for_row(
                option_id
            )
        )
        for option_id in model.indices.revenue_operate_options.ids
    }
    required = set(model.request.required_operated_option_ids)
    required_checks = [
        _check(
            CRM_C02_OPTION_COVERAGE,
            option_id,
            operating_coverage[option_id],
            1.0,
        )
        for option_id in model.request.required_operated_option_ids
    ]
    operating_leakage_checks = [
        _check(
            CRM_C03_NONREQUIRED_PROHIBITION,
            f"operate:{option_id}",
            operating_coverage[option_id],
            0.0,
        )
        for option_id in model.indices.revenue_operate_options.ids
        if option_id not in required
    ]
    deadhead_leakage_checks = [
        _check(
            CRM_C03_NONREQUIRED_PROHIBITION,
            f"deadhead:{option_id}",
            deadhead_presence[option_id],
            0.0,
        )
        for option_id in model.indices.revenue_operate_options.ids
        if option_id not in required
    ]

    selected_breakdowns = {
        pairing_id: crew_pairing_cost(
            scenario,
            options_by_id,
            pairings_by_id[pairing_id],
            costs,
        )
        for pairing_id in selected_pairing_ids
    }
    deadhead_legs = []
    for pairing_id in model.indices.crew_pairings.ids:
        if pairing_id not in selected_pairing_ids:
            continue
        pairing = pairings_by_id[pairing_id]
        for option_id in incidence.pairing_to_deadhead_options[pairing_id]:
            option = options_by_id[option_id]
            deadhead_legs.append(
                {
                    "crew_id": pairing.crew_id,
                    "pairing_id": pairing_id,
                    "option_id": option_id,
                    "minutes": option.block_minutes,
                    "cost": float(option.block_minutes or 0)
                    * float(costs.coefficients.deadhead_per_minute.value),
                }
            )

    objective_breakdown = {
        "crew_reassignment": sum(
            item.crew_reassignment_cost for item in selected_breakdowns.values()
        ),
        "deadhead": sum(item.deadhead_cost for item in selected_breakdowns.values()),
    }
    objective_breakdown["total"] = sum(objective_breakdown.values())
    all_checks = (
        selection_checks
        + required_checks
        + operating_leakage_checks
        + deadhead_leakage_checks
        + terminal_checks
    )
    return {
        "model": "CRM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "paper_objective": "(3.13):fixed-column mapping",
        "paper_variable_domain": "binary fixed-pairing selection",
        "fixed_column_analysis": analyze_crm_fixed_columns(model),
        "required_operated_option_ids": list(
            model.request.required_operated_option_ids
        ),
        "selected_pairing_by_crew": selected_pairing_by_crew,
        "covered_required_options": [
            option_id
            for option_id in model.request.required_operated_option_ids
            if abs(operating_coverage[option_id] - 1.0) <= CRM_FEASIBILITY_TOLERANCE
        ],
        "uncovered_required_options": [
            option_id
            for option_id in model.request.required_operated_option_ids
            if operating_coverage[option_id] < 1.0 - CRM_FEASIBILITY_TOLERANCE
        ],
        "duplicate_operating_coverage": [
            option_id
            for option_id in model.request.required_operated_option_ids
            if operating_coverage[option_id] > 1.0 + CRM_FEASIBILITY_TOLERANCE
        ],
        "unexpected_operating_options": [
            option_id
            for option_id in model.indices.revenue_operate_options.ids
            if option_id not in required
            and operating_coverage[option_id] > CRM_FEASIBILITY_TOLERANCE
        ],
        "unexpected_deadhead_options": [
            option_id
            for option_id in model.indices.revenue_operate_options.ids
            if option_id not in required
            and deadhead_presence[option_id] > CRM_FEASIBILITY_TOLERANCE
        ],
        "operating_coverage": operating_coverage,
        "deadhead_presence": deadhead_presence,
        "pairing_selection_constraints": selection_checks,
        "required_option_constraints": required_checks,
        "operating_leakage_constraints": operating_leakage_checks,
        "deadhead_leakage_constraints": deadhead_leakage_checks,
        "crew_legality_status": {
            "constraint_id": CRM_C04_CREW_FEASIBILITY,
            "validated_before_model_build": True,
            "selected_pairing_ids": sorted(selected_pairing_ids),
            "provenance": CONSTRAINT_PROVENANCE[CRM_C04_CREW_FEASIBILITY],
        },
        "terminal_status": terminal_checks,
        "deadhead_legs": deadhead_legs,
        "deadhead_minutes": sum(
            item.deadhead_minutes for item in selected_breakdowns.values()
        ),
        "crew_reassignment_count": sum(
            item.crew_reassignment_count for item in selected_breakdowns.values()
        ),
        "objective_breakdown": objective_breakdown,
        "all_constraints_satisfied": all(item["satisfied"] for item in all_checks),
        "constraint_violation_count": sum(not item["satisfied"] for item in all_checks),
    }


def solve_fixed_column_crm(
    scenario_data: Any,
    columns_data: Any,
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
    *,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
) -> ModelSolveResult:
    """Validate, build, solve, and independently audit the Fixed-Column CRM."""

    scenario, columns = _validated_inputs(scenario_data, columns_data)
    model = build_fixed_column_crm(scenario, columns, request, costs, solver)
    outcome = solver.solve(solver_parameters)
    selected_variables: dict[str, float] = {}
    diagnostics: dict[str, Any] = {
        "model": "CRM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "paper_objective": "(3.13):fixed-column mapping",
        "paper_variable_domain": "binary fixed-pairing selection",
        "required_operated_option_ids": list(request.required_operated_option_ids),
        "fixed_column_analysis": analyze_crm_fixed_columns(model),
        "solver": dict(outcome.diagnostics),
    }

    if outcome.has_solution:
        pairing_values = {
            pairing_id: solver.get_variable_value(variable)
            for pairing_id, variable in model.variables.items()
        }
        selected_variables = {
            model.variables[pairing_id].name: value
            for pairing_id, value in pairing_values.items()
            if value > 0.5
        }
        diagnostics = recompute_crm_diagnostics(model, pairing_values, costs)
        diagnostics["solver"] = dict(outcome.diagnostics)
        recomputed_objective = diagnostics["objective_breakdown"]["total"]
        if outcome.objective_value is None or not math.isclose(
            recomputed_objective,
            outcome.objective_value,
            rel_tol=CRM_FEASIBILITY_TOLERANCE,
            abs_tol=CRM_FEASIBILITY_TOLERANCE,
        ):
            raise RuntimeError(
                "CRM objective audit differs from Solver outcome: "
                f"audit={recomputed_objective}, solver={outcome.objective_value}"
            )
        if not diagnostics["all_constraints_satisfied"]:
            raise RuntimeError("CRM independent constraint audit found a violation")

    return ModelSolveResult(
        model_name=outcome.model_name,
        scenario_id=scenario.scenario_id,
        status=outcome.status,
        objective_value=outcome.objective_value,
        best_bound=outcome.best_bound,
        mip_gap=outcome.mip_gap,
        runtime_seconds=outcome.runtime_seconds,
        selected_variables=selected_variables,
        continuous_variables={},
        solver_name=solver.solver_name,
        solver_version=solver.solver_version,
        raw_status=outcome.raw_status,
        termination_reason=outcome.termination_reason,
        diagnostics=diagnostics,
    )
