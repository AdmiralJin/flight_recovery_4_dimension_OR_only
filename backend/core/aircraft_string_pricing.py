from __future__ import annotations

from collections.abc import Mapping, Set, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.config.costs import FixedColumnCostConfig, aircraft_string_cost
from backend.config.string_generation import FlightStringGenerationConfig
from backend.schemas.aircraft import Aircraft
from backend.schemas.columns import AircraftString, FlightOperationType, FlightOption
from backend.schemas.scenario import Scenario

from .aircraft_string_master import (
    AircraftStringMasterDuals,
    AircraftStringMasterPhase,
)
from .arm import AircraftRecoveryRequest
from .flight_network import build_aircraft_flight_network
from .string_generator import (
    aircraft_string_semantic_key,
    make_generated_aircraft_string,
    validate_generated_aircraft_string,
)


class AircraftStringPricingError(ValueError):
    """The aircraft-local pricing problem cannot be constructed safely."""


@dataclass(frozen=True)
class AircraftStringPricedColumn:
    aircraft_string: AircraftString
    primal_cost: float
    dual_contribution: float
    reduced_cost: float
    row_coefficients: Mapping[str, float] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "row_coefficients", MappingProxyType(dict(self.row_coefficients))
        )


@dataclass(frozen=True)
class AircraftStringPricingResult:
    aircraft_id: str
    columns: tuple[AircraftStringPricedColumn, ...]
    minimum_reduced_cost: float | None
    paths_evaluated: int
    omitted_paths_evaluated: int
    duplicate_paths_skipped: int


def evaluate_aircraft_string_reduced_cost(
    scenario: Scenario,
    flight_options: Mapping[str, FlightOption],
    candidate: AircraftString,
    costs: FixedColumnCostConfig,
    duals: AircraftStringMasterDuals,
) -> AircraftStringPricedColumn:
    """Evaluate c - pi*a from the same rows used by the LP master."""

    required_coefficients = {
        option_id: 1.0
        for option_id in candidate.leg_option_ids
        if option_id in duals.required_coverage_by_option
    }
    nonrequired_coefficients = {
        option_id: 1.0
        for option_id in candidate.leg_option_ids
        if option_id in duals.nonrequired_coverage_by_option
    }
    row_coefficients: dict[str, float] = {
        f"selection:{candidate.aircraft_id}": 1.0,
        f"terminal:{candidate.aircraft_id}": 1.0,
        **{f"required:{key}": value for key, value in required_coefficients.items()},
        **{
            f"nonrequired:{key}": value
            for key, value in nonrequired_coefficients.items()
        },
    }
    contribution = duals.selection_by_aircraft[candidate.aircraft_id]
    contribution += duals.terminal_by_aircraft[candidate.aircraft_id]
    contribution += sum(
        duals.required_coverage_by_option[key] for key in required_coefficients
    )
    contribution += sum(
        duals.nonrequired_coverage_by_option[key] for key in nonrequired_coefficients
    )
    if candidate.aircraft_id in duals.maintenance_by_aircraft:
        coefficient = 1.0 if candidate.maintenance_satisfied else 0.0
        row_coefficients[f"maintenance:{candidate.aircraft_id}"] = coefficient
        contribution += duals.maintenance_by_aircraft[candidate.aircraft_id] * coefficient
    true_cost = aircraft_string_cost(
        scenario, flight_options, candidate, costs
    ).total
    primal_cost = 0.0 if duals.phase is AircraftStringMasterPhase.PHASE_I else true_cost
    return AircraftStringPricedColumn(
        aircraft_string=candidate,
        primal_cost=primal_cost,
        dual_contribution=contribution,
        reduced_cost=primal_cost - contribution,
        row_coefficients=row_coefficients,
    )


def price_aircraft_strings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    aircraft: Aircraft,
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    duals: AircraftStringMasterDuals,
    existing_keys: Set[tuple[str, tuple[str, ...]]],
    *,
    pricing_epsilon: float,
    max_columns: int = 1,
) -> AircraftStringPricingResult:
    """Solve one aircraft's deterministic DAG pricing problem.

    This label/DFS routine is intentionally independent of the Phase 5 full-pool
    enumerator. It only traverses fixed-schedule revenue legs and ferry legs.
    """

    if aircraft.tail_id not in duals.selection_by_aircraft:
        raise AircraftStringPricingError(
            f"missing selection dual for aircraft {aircraft.tail_id!r}"
        )
    required = set(request.required_operated_option_ids)
    allowed = tuple(
        item
        for item in flight_options
        if item.operation_type is FlightOperationType.FERRY
        or (
            item.operation_type is FlightOperationType.OPERATE
            and item.option_id in required
        )
    )
    option_by_id = {item.option_id: item for item in allowed}
    all_options = {item.option_id: item for item in flight_options}
    network = build_aircraft_flight_network(
        scenario, allowed, aircraft, string_config
    )
    evaluated: list[AircraftStringPricedColumn] = []
    paths_evaluated = 0
    omitted_paths_evaluated = 0
    duplicates = 0

    def emit(path: tuple[str, ...]) -> None:
        nonlocal paths_evaluated, omitted_paths_evaluated, duplicates
        candidate = make_generated_aircraft_string(aircraft, path)
        audit = validate_generated_aircraft_string(
            scenario, flight_options, aircraft, candidate, string_config
        )
        if not audit.valid:
            raise AircraftStringPricingError(
                f"pricing emitted illegal path {path!r}: {audit.violations}"
            )
        paths_evaluated += 1
        key = aircraft_string_semantic_key(aircraft.tail_id, path)
        if key in existing_keys:
            duplicates += 1
            return
        omitted_paths_evaluated += 1
        evaluated.append(
            evaluate_aircraft_string_reduced_cost(
                scenario, all_options, candidate, costs, duals
            )
        )

    idle = make_generated_aircraft_string(aircraft, ())
    if validate_generated_aircraft_string(
        scenario, flight_options, aircraft, idle, string_config
    ).valid:
        emit(())

    def visit(
        path: tuple[str, ...],
        used_options: frozenset[str],
        used_base_flights: frozenset[str],
    ) -> None:
        last = option_by_id[path[-1]]
        if last.destination == aircraft.required_station_at_T_end:
            emit(path)
        for next_id in network.successor_option_ids[path[-1]]:
            if next_id in used_options:
                continue
            next_option = option_by_id[next_id]
            base_id = next_option.base_flight_id
            if base_id is not None and base_id in used_base_flights:
                continue
            visit(
                (*path, next_id),
                used_options | {next_id},
                used_base_flights
                | (frozenset({base_id}) if base_id is not None else frozenset()),
            )

    for option_id in network.start_option_ids:
        option = option_by_id[option_id]
        bases = (
            frozenset({option.base_flight_id})
            if option.base_flight_id is not None
            else frozenset()
        )
        visit((option_id,), frozenset({option_id}), bases)

    ordered = tuple(
        sorted(
            evaluated,
            key=lambda item: (
                item.reduced_cost,
                item.aircraft_string.aircraft_id,
                tuple(item.aircraft_string.leg_option_ids),
            ),
        )
    )
    negative = tuple(
        item for item in ordered if item.reduced_cost < -pricing_epsilon
    )[:max_columns]
    return AircraftStringPricingResult(
        aircraft_id=aircraft.tail_id,
        columns=negative,
        minimum_reduced_cost=ordered[0].reduced_cost if ordered else None,
        paths_evaluated=paths_evaluated,
        omitted_paths_evaluated=omitted_paths_evaluated,
        duplicate_paths_skipped=duplicates,
    )
