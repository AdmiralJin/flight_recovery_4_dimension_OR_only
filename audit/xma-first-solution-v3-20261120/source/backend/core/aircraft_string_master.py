from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from backend.config.costs import FixedColumnCostConfig, aircraft_string_cost
from backend.config.string_generation import FlightStringGenerationConfig
from backend.schemas.columns import AircraftString, FlightOperationType, FlightOption
from backend.schemas.scenario import Scenario
from backend.solver.base import (
    ConstraintHandle,
    ConstraintSense,
    ObjectiveSense,
    SolverAdapter,
    SolverOutcome,
    SolverStatus,
    VariableHandle,
    VariableType,
)

from .arm import AircraftRecoveryRequest
from .scope import RecoveryScope, resolve_original_flight_option_ids
from .string_generator import validate_generated_aircraft_string


AIRCRAFT_STRING_MASTER_MODEL_NAME = "aircraft_string_lp_master"


class AircraftStringMasterError(ValueError):
    """The fixed schedule or aircraft-string pool violates the LP contract."""


class AircraftStringMasterPhase(str, Enum):
    PHASE_I = "phase_i"
    PHASE_II = "phase_ii"


@dataclass(frozen=True)
class AircraftStringMasterDuals:
    phase: AircraftStringMasterPhase
    selection_by_aircraft: Mapping[str, float] = field(repr=False)
    required_coverage_by_option: Mapping[str, float] = field(repr=False)
    nonrequired_coverage_by_option: Mapping[str, float] = field(repr=False)
    terminal_by_aircraft: Mapping[str, float] = field(repr=False)
    maintenance_by_aircraft: Mapping[str, float] = field(repr=False)

    def __post_init__(self) -> None:
        for name in (
            "selection_by_aircraft",
            "required_coverage_by_option",
            "nonrequired_coverage_by_option",
            "terminal_by_aircraft",
            "maintenance_by_aircraft",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    @property
    def count(self) -> int:
        return sum(
            len(items)
            for items in (
                self.selection_by_aircraft,
                self.required_coverage_by_option,
                self.nonrequired_coverage_by_option,
                self.terminal_by_aircraft,
                self.maintenance_by_aircraft,
            )
        )


@dataclass(frozen=True)
class AircraftStringMasterModel:
    phase: AircraftStringMasterPhase
    strings: tuple[AircraftString, ...]
    variables: Mapping[str, VariableHandle] = field(repr=False)
    artificial_variables: Mapping[str, VariableHandle] = field(repr=False)
    constraints: Mapping[str, Mapping[str, ConstraintHandle]] = field(repr=False)
    objective_costs: Mapping[str, float] = field(repr=False)
    row_coefficients: Mapping[str, Mapping[str, Mapping[str, float]]] = field(
        repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "variables", MappingProxyType(dict(self.variables)))
        object.__setattr__(
            self,
            "artificial_variables",
            MappingProxyType(dict(self.artificial_variables)),
        )
        object.__setattr__(
            self,
            "constraints",
            MappingProxyType(
                {name: MappingProxyType(dict(rows)) for name, rows in self.constraints.items()}
            ),
        )
        object.__setattr__(self, "objective_costs", MappingProxyType(dict(self.objective_costs)))
        object.__setattr__(
            self,
            "row_coefficients",
            MappingProxyType(
                {
                    group: MappingProxyType(
                        {row: MappingProxyType(dict(values)) for row, values in rows.items()}
                    )
                    for group, rows in self.row_coefficients.items()
                }
            ),
        )


@dataclass(frozen=True)
class AircraftStringMasterResult:
    phase: AircraftStringMasterPhase
    outcome: SolverOutcome
    objective_value: float | None
    artificial_objective: float
    string_values: Mapping[str, float] = field(repr=False)
    artificial_values: Mapping[str, float] = field(repr=False)
    duals: AircraftStringMasterDuals | None = field(repr=False)
    reduced_costs: Mapping[str, float] = field(repr=False)
    manual_reduced_costs: Mapping[str, float] = field(repr=False)
    maximum_reduced_cost_error: float | None

    def __post_init__(self) -> None:
        for name in (
            "string_values",
            "artificial_values",
            "reduced_costs",
            "manual_reduced_costs",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


def validate_aircraft_string_master_inputs(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    strings: Sequence[AircraftString],
    request: AircraftRecoveryRequest,
    string_config: FlightStringGenerationConfig,
) -> None:
    if request.scenario_id != scenario.scenario_id:
        raise AircraftStringMasterError("request scenario_id differs from Scenario")
    option_ids = [item.option_id for item in flight_options]
    if len(option_ids) != len(set(option_ids)):
        raise AircraftStringMasterError("flight option IDs must be unique")
    options = {item.option_id: item for item in flight_options}
    required_base_ids: set[str] = set()
    for option_id in request.required_operated_option_ids:
        option = options.get(option_id)
        if option is None:
            raise AircraftStringMasterError(f"unknown required option: {option_id!r}")
        if option.operation_type is not FlightOperationType.OPERATE or option.base_flight_id is None:
            raise AircraftStringMasterError(
                f"required option is not a revenue operation: {option_id!r}"
            )
        if option.base_flight_id in required_base_ids:
            raise AircraftStringMasterError(
                f"multiple required options use base flight {option.base_flight_id!r}"
            )
        required_base_ids.add(option.base_flight_id)

    aircraft = {item.tail_id: item for item in scenario.aircraft}
    string_ids = [item.string_id for item in strings]
    if len(string_ids) != len(set(string_ids)):
        raise AircraftStringMasterError("aircraft string IDs must be unique")
    semantic_keys: set[tuple[str, tuple[str, ...]]] = set()
    for item in strings:
        owner = aircraft.get(item.aircraft_id)
        if owner is None:
            raise AircraftStringMasterError(
                f"string {item.string_id!r} has unknown aircraft {item.aircraft_id!r}"
            )
        key = item.aircraft_id, tuple(item.leg_option_ids)
        if key in semantic_keys:
            raise AircraftStringMasterError(f"duplicate aircraft-string path: {key!r}")
        semantic_keys.add(key)
        audit = validate_generated_aircraft_string(
            scenario, flight_options, owner, item, string_config
        )
        if not audit.valid:
            raise AircraftStringMasterError(
                f"illegal aircraft string {item.string_id!r}: {audit.violations}"
            )


def restrict_aircraft_string_pool(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    strings: Sequence[AircraftString],
    scope: RecoveryScope | None,
) -> tuple[AircraftString, ...]:
    if scope is None:
        return tuple(strings)
    aircraft_ids = {item.tail_id for item in scenario.aircraft}
    unknown = set(scope.aircraft_ids) - aircraft_ids
    if unknown:
        raise AircraftStringMasterError(f"scope contains unknown aircraft: {sorted(unknown)}")
    scoped = set(scope.aircraft_ids)
    originals = resolve_original_flight_option_ids(scenario, flight_options)
    original_paths = {
        item.tail_id: tuple(originals[flight_id] for flight_id in item.original_rotation)
        for item in scenario.aircraft
    }
    selected = tuple(
        item
        for item in strings
        if item.aircraft_id in scoped
        or tuple(item.leg_option_ids) == original_paths[item.aircraft_id]
    )
    for aircraft_id in sorted(aircraft_ids - scoped):
        matches = [
            item
            for item in selected
            if item.aircraft_id == aircraft_id
            and tuple(item.leg_option_ids) == original_paths[aircraft_id]
        ]
        if len(matches) != 1:
            raise AircraftStringMasterError(
                f"out-of-scope aircraft {aircraft_id!r} requires exactly one original string"
            )
    return selected


def _row_coefficients(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    strings: Sequence[AircraftString],
    request: AircraftRecoveryRequest,
) -> dict[str, dict[str, dict[str, float]]]:
    required = set(request.required_operated_option_ids)
    revenue = tuple(
        item.option_id
        for item in flight_options
        if item.operation_type is FlightOperationType.OPERATE
    )
    aircraft = {item.tail_id: item for item in scenario.aircraft}
    return {
        "selection": {
            aircraft_id: {
                item.string_id: 1.0 for item in strings if item.aircraft_id == aircraft_id
            }
            for aircraft_id in aircraft
        },
        "required": {
            option_id: {
                item.string_id: 1.0 for item in strings if option_id in item.leg_option_ids
            }
            for option_id in request.required_operated_option_ids
        },
        "nonrequired": {
            option_id: {
                item.string_id: 1.0 for item in strings if option_id in item.leg_option_ids
            }
            for option_id in revenue
            if option_id not in required
        },
        "terminal": {
            aircraft_id: {
                item.string_id: 1.0
                for item in strings
                if item.aircraft_id == aircraft_id
                and item.end_station == owner.required_station_at_T_end
            }
            for aircraft_id, owner in aircraft.items()
        },
        "maintenance": {
            aircraft_id: {
                item.string_id: 1.0
                for item in strings
                if item.aircraft_id == aircraft_id and item.maintenance_satisfied
            }
            for aircraft_id, owner in aircraft.items()
            if owner.maintenance_required
        },
    }


def build_aircraft_string_master(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    strings: Sequence[AircraftString],
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    solver: SolverAdapter,
    *,
    phase: AircraftStringMasterPhase,
) -> AircraftStringMasterModel:
    validate_aircraft_string_master_inputs(
        scenario, flight_options, strings, request, string_config
    )
    ordered = tuple(strings)
    options = {item.option_id: item for item in flight_options}
    true_costs = {
        item.string_id: aircraft_string_cost(scenario, options, item, costs).total
        for item in ordered
    }
    objective_costs = {
        string_id: (0.0 if phase is AircraftStringMasterPhase.PHASE_I else value)
        for string_id, value in true_costs.items()
    }
    rows = _row_coefficients(scenario, flight_options, ordered, request)

    solver.create_model(f"{AIRCRAFT_STRING_MASTER_MODEL_NAME}_{phase.value}")
    variables = {
        item.string_id: solver.add_variable(
            f"y[{item.string_id}]",
            lower_bound=0.0,
            upper_bound=1.0,
            variable_type=VariableType.CONTINUOUS,
        )
        for item in ordered
    }
    artificials: dict[str, VariableHandle] = {}
    handles: dict[str, dict[str, ConstraintHandle]] = {}
    objective = {variables[key]: value for key, value in objective_costs.items()}
    for group, group_rows in rows.items():
        handles[group] = {}
        rhs = 0.0 if group == "nonrequired" else 1.0
        for row_id, coefficients in group_rows.items():
            expression = {variables[key]: value for key, value in coefficients.items()}
            if phase is AircraftStringMasterPhase.PHASE_I and rhs == 1.0:
                artificial_key = f"{group}:{row_id}"
                artificial = solver.add_variable(
                    f"artificial[{artificial_key}]",
                    lower_bound=0.0,
                    upper_bound=1.0,
                    variable_type=VariableType.CONTINUOUS,
                )
                artificials[artificial_key] = artificial
                expression[artificial] = 1.0
                objective[artificial] = 1.0
            handles[group][row_id] = solver.add_linear_constraint(
                expression,
                ConstraintSense.EQUAL,
                rhs,
                name=f"{group}[{row_id}]",
            )
    solver.set_objective(objective, ObjectiveSense.MINIMIZE)
    return AircraftStringMasterModel(
        phase=phase,
        strings=ordered,
        variables=variables,
        artificial_variables=artificials,
        constraints=handles,
        objective_costs=objective_costs,
        row_coefficients=rows,
    )


def solve_aircraft_string_master(
    model: AircraftStringMasterModel,
    solver: SolverAdapter,
) -> AircraftStringMasterResult:
    outcome = solver.solve()
    if outcome.status is not SolverStatus.OPTIMAL:
        return AircraftStringMasterResult(
            phase=model.phase,
            outcome=outcome,
            objective_value=outcome.objective_value,
            artificial_objective=float("inf"),
            string_values={},
            artificial_values={},
            duals=None,
            reduced_costs={},
            manual_reduced_costs={},
            maximum_reduced_cost_error=None,
        )
    string_values = {
        key: solver.get_variable_value(handle) for key, handle in model.variables.items()
    }
    artificial_values = {
        key: solver.get_variable_value(handle)
        for key, handle in model.artificial_variables.items()
    }
    dual_groups = {
        group: {row: solver.get_constraint_dual(handle) for row, handle in rows.items()}
        for group, rows in model.constraints.items()
    }
    duals = AircraftStringMasterDuals(
        phase=model.phase,
        selection_by_aircraft=dual_groups["selection"],
        required_coverage_by_option=dual_groups["required"],
        nonrequired_coverage_by_option=dual_groups["nonrequired"],
        terminal_by_aircraft=dual_groups["terminal"],
        maintenance_by_aircraft=dual_groups["maintenance"],
    )
    reduced = {key: solver.get_reduced_cost(handle) for key, handle in model.variables.items()}
    manual: dict[str, float] = {}
    for string_id, cost in model.objective_costs.items():
        dual_contribution = 0.0
        for group, rows in model.row_coefficients.items():
            for row_id, coefficients in rows.items():
                if string_id in coefficients:
                    dual_contribution += dual_groups[group][row_id] * coefficients[string_id]
        manual[string_id] = cost - dual_contribution
    maximum_error = max(
        (abs(manual[key] - reduced[key]) for key in reduced), default=0.0
    )
    return AircraftStringMasterResult(
        phase=model.phase,
        outcome=outcome,
        objective_value=outcome.objective_value,
        artificial_objective=sum(artificial_values.values()),
        string_values=string_values,
        artificial_values=artificial_values,
        duals=duals,
        reduced_costs=reduced,
        manual_reduced_costs=manual,
        maximum_reduced_cost_error=maximum_error,
    )


def solve_full_column_aircraft_string_lp(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    strings: Sequence[AircraftString],
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    solver: SolverAdapter,
    *,
    scope: RecoveryScope | None = None,
) -> AircraftStringMasterResult:
    """Solve the independent full-column LP ground truth for a fixed schedule."""

    restricted = restrict_aircraft_string_pool(
        scenario, flight_options, strings, scope
    )
    model = build_aircraft_string_master(
        scenario,
        flight_options,
        restricted,
        request,
        costs,
        string_config,
        solver,
        phase=AircraftStringMasterPhase.PHASE_II,
    )
    return solve_aircraft_string_master(model, solver)
