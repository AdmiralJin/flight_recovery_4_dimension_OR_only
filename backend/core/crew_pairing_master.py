from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from backend.config.costs import FixedColumnCostConfig, crew_pairing_cost
from backend.config.pairing_generation import CrewPairingGenerationConfig
from backend.schemas.columns import (
    CrewPairing,
    CrewSegmentType,
    FlightOperationType,
    FlightOption,
)
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

from .crm import CrewRecoveryRequest
from .crew_network import CrewLegKey
from .pairing_generator import (
    make_generated_crew_pairing,
    pairing_semantic_key,
    validate_generated_crew_pairing,
)
from .scope import RecoveryScope, resolve_original_flight_option_ids


CREW_PAIRING_MASTER_MODEL_NAME = "crew_pairing_lp_master"


class CrewPairingMasterError(ValueError):
    """The fixed schedule or crew-pairing pool violates the LP contract."""


class CrewPairingMasterPhase(str, Enum):
    PHASE_I = "phase_i"
    PHASE_II = "phase_ii"


@dataclass(frozen=True)
class CrewPairingMasterDuals:
    phase: CrewPairingMasterPhase
    selection_by_crew: Mapping[str, float] = field(repr=False)
    required_operate_coverage_by_option: Mapping[str, float] = field(repr=False)
    nonrequired_operate_by_option: Mapping[str, float] = field(repr=False)
    nonrequired_deadhead_by_option: Mapping[str, float] = field(repr=False)
    terminal_by_crew: Mapping[str, float] = field(repr=False)

    def __post_init__(self) -> None:
        for name in (
            "selection_by_crew",
            "required_operate_coverage_by_option",
            "nonrequired_operate_by_option",
            "nonrequired_deadhead_by_option",
            "terminal_by_crew",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    @property
    def count(self) -> int:
        return sum(
            len(values)
            for values in (
                self.selection_by_crew,
                self.required_operate_coverage_by_option,
                self.nonrequired_operate_by_option,
                self.nonrequired_deadhead_by_option,
                self.terminal_by_crew,
            )
        )


@dataclass(frozen=True)
class CrewPairingMasterModel:
    phase: CrewPairingMasterPhase
    pairings: tuple[CrewPairing, ...]
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
                {
                    group: MappingProxyType(dict(rows))
                    for group, rows in self.constraints.items()
                }
            ),
        )
        object.__setattr__(
            self, "objective_costs", MappingProxyType(dict(self.objective_costs))
        )
        object.__setattr__(
            self,
            "row_coefficients",
            MappingProxyType(
                {
                    group: MappingProxyType(
                        {
                            row: MappingProxyType(dict(values))
                            for row, values in rows.items()
                        }
                    )
                    for group, rows in self.row_coefficients.items()
                }
            ),
        )


@dataclass(frozen=True)
class CrewPairingMasterResult:
    phase: CrewPairingMasterPhase
    outcome: SolverOutcome
    objective_value: float | None
    artificial_objective: float
    pairing_values: Mapping[str, float] = field(repr=False)
    artificial_values: Mapping[str, float] = field(repr=False)
    duals: CrewPairingMasterDuals | None = field(repr=False)
    reduced_costs: Mapping[str, float] = field(repr=False)
    manual_reduced_costs: Mapping[str, float] = field(repr=False)
    maximum_reduced_cost_error: float | None

    def __post_init__(self) -> None:
        for name in (
            "pairing_values",
            "artificial_values",
            "reduced_costs",
            "manual_reduced_costs",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


def _segments(pairing: CrewPairing):
    return tuple(segment for duty in pairing.duties for segment in duty.segments)


def validate_crew_pairing_master_inputs(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    pairings: Sequence[CrewPairing],
    request: CrewRecoveryRequest,
    pairing_config: CrewPairingGenerationConfig,
) -> None:
    if request.scenario_id != scenario.scenario_id:
        raise CrewPairingMasterError("request scenario_id differs from Scenario")
    option_ids = [item.option_id for item in flight_options]
    if len(option_ids) != len(set(option_ids)):
        raise CrewPairingMasterError("flight option IDs must be unique")
    options = {item.option_id: item for item in flight_options}
    required_base_ids: set[str] = set()
    for option_id in request.required_operated_option_ids:
        option = options.get(option_id)
        if option is None:
            raise CrewPairingMasterError(f"unknown required option: {option_id!r}")
        if (
            option.operation_type is not FlightOperationType.OPERATE
            or option.base_flight_id is None
        ):
            raise CrewPairingMasterError(
                f"required option is not a revenue operation: {option_id!r}"
            )
        if option.base_flight_id in required_base_ids:
            raise CrewPairingMasterError(
                f"multiple required options use base flight {option.base_flight_id!r}"
            )
        required_base_ids.add(option.base_flight_id)

    crew_by_id = {item.crew_id: item for item in scenario.crew}
    pairing_ids = [item.pairing_id for item in pairings]
    if len(pairing_ids) != len(set(pairing_ids)):
        raise CrewPairingMasterError("crew pairing IDs must be unique")
    keys: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for item in pairings:
        crew = crew_by_id.get(item.crew_id)
        if crew is None:
            raise CrewPairingMasterError(
                f"pairing {item.pairing_id!r} has unknown crew {item.crew_id!r}"
            )
        key = pairing_semantic_key(item)
        if key in keys:
            raise CrewPairingMasterError(f"duplicate crew-pairing path: {key!r}")
        keys.add(key)
        audit = validate_generated_crew_pairing(
            scenario, flight_options, crew, item, pairing_config
        )
        if not audit.valid:
            raise CrewPairingMasterError(
                f"illegal crew pairing {item.pairing_id!r}: {audit.violations}"
            )


def original_pairing_by_crew(
    scenario: Scenario, flight_options: Sequence[FlightOption]
) -> Mapping[str, CrewPairing]:
    originals = resolve_original_flight_option_ids(scenario, flight_options)
    return MappingProxyType(
        {
            crew.crew_id: make_generated_crew_pairing(
                crew,
                tuple(
                    CrewLegKey(CrewSegmentType.OPERATE, originals[flight_id])
                    for flight_id in crew.original_pairing
                ),
            )
            for crew in scenario.crew
        }
    )


def restrict_crew_pairing_pool(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    pairings: Sequence[CrewPairing],
    scope: RecoveryScope | None,
) -> tuple[CrewPairing, ...]:
    if scope is None:
        return tuple(pairings)
    crew_ids = {item.crew_id for item in scenario.crew}
    unknown = set(scope.crew_ids) - crew_ids
    if unknown:
        raise CrewPairingMasterError(f"scope contains unknown crew: {sorted(unknown)}")
    scoped = set(scope.crew_ids)
    originals = original_pairing_by_crew(scenario, flight_options)
    original_keys = {
        key: pairing_semantic_key(value) for key, value in originals.items()
    }
    selected = tuple(
        item
        for item in pairings
        if item.crew_id in scoped
        or pairing_semantic_key(item) == original_keys[item.crew_id]
    )
    for crew_id in sorted(crew_ids - scoped):
        matches = [
            item
            for item in selected
            if item.crew_id == crew_id
            and pairing_semantic_key(item) == original_keys[crew_id]
        ]
        if len(matches) != 1:
            raise CrewPairingMasterError(
                f"out-of-scope crew {crew_id!r} requires exactly one original pairing"
            )
    return selected


def _row_coefficients(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    pairings: Sequence[CrewPairing],
    request: CrewRecoveryRequest,
) -> dict[str, dict[str, dict[str, float]]]:
    required = set(request.required_operated_option_ids)
    revenue = tuple(
        item.option_id
        for item in flight_options
        if item.operation_type is FlightOperationType.OPERATE
    )
    crew_by_id = {item.crew_id: item for item in scenario.crew}
    typed = {
        item.pairing_id: {
            (segment.segment_type, segment.flight_option_id or "")
            for segment in _segments(item)
        }
        for item in pairings
    }
    return {
        "selection": {
            crew_id: {
                item.pairing_id: 1.0 for item in pairings if item.crew_id == crew_id
            }
            for crew_id in crew_by_id
        },
        "required_operate": {
            option_id: {
                item.pairing_id: 1.0
                for item in pairings
                if (CrewSegmentType.OPERATE, option_id) in typed[item.pairing_id]
            }
            for option_id in request.required_operated_option_ids
        },
        "nonrequired_operate": {
            option_id: {
                item.pairing_id: 1.0
                for item in pairings
                if (CrewSegmentType.OPERATE, option_id) in typed[item.pairing_id]
            }
            for option_id in revenue
            if option_id not in required
        },
        "nonrequired_deadhead": {
            option_id: {
                item.pairing_id: 1.0
                for item in pairings
                if (CrewSegmentType.DEADHEAD, option_id) in typed[item.pairing_id]
            }
            for option_id in revenue
            if option_id not in required
        },
        "terminal": {
            crew_id: {
                item.pairing_id: 1.0
                for item in pairings
                if item.crew_id == crew_id
                and item.end_station == crew.required_station_at_T_end
            }
            for crew_id, crew in crew_by_id.items()
        },
    }


def build_crew_pairing_master(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    pairings: Sequence[CrewPairing],
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    solver: SolverAdapter,
    *,
    phase: CrewPairingMasterPhase,
) -> CrewPairingMasterModel:
    validate_crew_pairing_master_inputs(
        scenario, flight_options, pairings, request, pairing_config
    )
    ordered = tuple(pairings)
    options = {item.option_id: item for item in flight_options}
    true_costs = {
        item.pairing_id: crew_pairing_cost(scenario, options, item, costs).total
        for item in ordered
    }
    objective_costs = {
        pairing_id: (0.0 if phase is CrewPairingMasterPhase.PHASE_I else value)
        for pairing_id, value in true_costs.items()
    }
    rows = _row_coefficients(scenario, flight_options, ordered, request)
    solver.create_model(f"{CREW_PAIRING_MASTER_MODEL_NAME}_{phase.value}")
    variables = {
        item.pairing_id: solver.add_variable(
            f"z[{item.pairing_id}]",
            lower_bound=0.0,
            upper_bound=1.0,
            variable_type=VariableType.CONTINUOUS,
        )
        for item in ordered
    }
    artificials: dict[str, VariableHandle] = {}
    handles: dict[str, dict[str, ConstraintHandle]] = {}
    objective = {variables[key]: value for key, value in objective_costs.items()}
    zero_rhs_groups = {"nonrequired_operate", "nonrequired_deadhead"}
    for group, group_rows in rows.items():
        handles[group] = {}
        rhs = 0.0 if group in zero_rhs_groups else 1.0
        for row_id, coefficients in group_rows.items():
            expression = {variables[key]: value for key, value in coefficients.items()}
            if phase is CrewPairingMasterPhase.PHASE_I and rhs == 1.0:
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
    return CrewPairingMasterModel(
        phase=phase,
        pairings=ordered,
        variables=variables,
        artificial_variables=artificials,
        constraints=handles,
        objective_costs=objective_costs,
        row_coefficients=rows,
    )


def solve_crew_pairing_master(
    model: CrewPairingMasterModel, solver: SolverAdapter
) -> CrewPairingMasterResult:
    outcome = solver.solve()
    if outcome.status is not SolverStatus.OPTIMAL:
        return CrewPairingMasterResult(
            phase=model.phase,
            outcome=outcome,
            objective_value=outcome.objective_value,
            artificial_objective=float("inf"),
            pairing_values={},
            artificial_values={},
            duals=None,
            reduced_costs={},
            manual_reduced_costs={},
            maximum_reduced_cost_error=None,
        )
    pairing_values = {
        key: solver.get_variable_value(handle)
        for key, handle in model.variables.items()
    }
    artificial_values = {
        key: solver.get_variable_value(handle)
        for key, handle in model.artificial_variables.items()
    }
    dual_groups = {
        group: {row: solver.get_constraint_dual(handle) for row, handle in rows.items()}
        for group, rows in model.constraints.items()
    }
    duals = CrewPairingMasterDuals(
        phase=model.phase,
        selection_by_crew=dual_groups["selection"],
        required_operate_coverage_by_option=dual_groups["required_operate"],
        nonrequired_operate_by_option=dual_groups["nonrequired_operate"],
        nonrequired_deadhead_by_option=dual_groups["nonrequired_deadhead"],
        terminal_by_crew=dual_groups["terminal"],
    )
    reduced = {
        key: solver.get_reduced_cost(handle) for key, handle in model.variables.items()
    }
    manual: dict[str, float] = {}
    for pairing_id, cost in model.objective_costs.items():
        contribution = 0.0
        for group, rows in model.row_coefficients.items():
            for row_id, coefficients in rows.items():
                if pairing_id in coefficients:
                    contribution += (
                        dual_groups[group][row_id] * coefficients[pairing_id]
                    )
        manual[pairing_id] = cost - contribution
    maximum_error = max(
        (abs(manual[key] - reduced[key]) for key in reduced), default=0.0
    )
    return CrewPairingMasterResult(
        phase=model.phase,
        outcome=outcome,
        objective_value=outcome.objective_value,
        artificial_objective=sum(artificial_values.values()),
        pairing_values=pairing_values,
        artificial_values=artificial_values,
        duals=duals,
        reduced_costs=reduced,
        manual_reduced_costs=manual,
        maximum_reduced_cost_error=maximum_error,
    )


def solve_full_column_crew_pairing_lp(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    pairings: Sequence[CrewPairing],
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    solver: SolverAdapter,
    *,
    scope: RecoveryScope | None = None,
) -> CrewPairingMasterResult:
    """Solve the independent all-pairings LP ground truth for a fixed schedule."""

    restricted = restrict_crew_pairing_pool(scenario, flight_options, pairings, scope)
    model = build_crew_pairing_master(
        scenario,
        flight_options,
        restricted,
        request,
        costs,
        pairing_config,
        solver,
        phase=CrewPairingMasterPhase.PHASE_II,
    )
    return solve_crew_pairing_master(model, solver)
