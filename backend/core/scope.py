from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.schemas.columns import (
    CrewSegmentType,
    FlightChangeType,
    FlightOption,
    FlightOperationType,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.scenario import Scenario

from .crew_incidence import CrewRecoveryIncidence, build_crew_recovery_incidence
from .gate_inventory import GateInventoryData, build_gate_inventory_data
from .incidence import RecoveryIncidence, build_recovery_incidence
from .indices import RecoveryIndices, build_recovery_indices
from .passenger_incidence import (
    PassengerRecoveryIncidence,
    build_passenger_recovery_incidence,
)


SUPPORTED_SCOPE_RESTRICTION_TYPES = frozenset(
    {"departure_capacity_reduction"}
)


class ScopeBuildError(ValueError):
    """The validated fixed-column universe cannot produce a safe scope."""


@dataclass(frozen=True)
class RecoveryScope:
    """Immutable, deterministic closure of decisions exposed to recovery."""

    direct_flight_ids: tuple[str, ...]
    flight_ids: tuple[str, ...]
    aircraft_ids: tuple[str, ...]
    crew_ids: tuple[str, ...]
    passenger_group_ids: tuple[str, ...]
    flight_option_ids: tuple[str, ...]
    aircraft_string_ids: tuple[str, ...]
    crew_pairing_ids: tuple[str, ...]
    passenger_itinerary_ids: tuple[str, ...]
    propagation_reasons: Mapping[str, tuple[str, ...]]
    iteration_count: int

    def __post_init__(self) -> None:
        tuple_fields = (
            "direct_flight_ids",
            "flight_ids",
            "aircraft_ids",
            "crew_ids",
            "passenger_group_ids",
            "flight_option_ids",
            "aircraft_string_ids",
            "crew_pairing_ids",
            "passenger_itinerary_ids",
        )
        for name in tuple_fields:
            values = tuple(getattr(self, name))
            if len(values) != len(set(values)):
                raise ValueError(f"{name} cannot contain duplicate IDs")
            object.__setattr__(self, name, values)
        if self.iteration_count < 1:
            raise ValueError("iteration_count must be at least 1")
        frozen_reasons = {
            entity_id: tuple(sorted(set(reasons)))
            for entity_id, reasons in sorted(self.propagation_reasons.items())
        }
        object.__setattr__(
            self, "propagation_reasons", MappingProxyType(frozen_reasons)
        )


@dataclass(frozen=True)
class OriginalCandidates:
    """Semantically resolved original-plan candidate for every owner."""

    flight_option_by_flight: Mapping[str, str] = field(repr=False)
    aircraft_string_by_aircraft: Mapping[str, str] = field(repr=False)
    crew_pairing_by_crew: Mapping[str, str] = field(repr=False)
    passenger_itinerary_by_group: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        for name in (
            "flight_option_by_flight",
            "aircraft_string_by_aircraft",
            "crew_pairing_by_crew",
            "passenger_itinerary_by_group",
        ):
            object.__setattr__(
                self, name, MappingProxyType(dict(getattr(self, name)))
            )


@dataclass(frozen=True)
class _ScopeDependencies:
    indices: RecoveryIndices
    incidence: RecoveryIncidence
    crew_incidence: CrewRecoveryIncidence
    passenger_incidence: PassengerRecoveryIncidence
    gate_inventory: GateInventoryData


def _dependencies(
    scenario: Scenario, columns: RecoveryColumns
) -> _ScopeDependencies:
    try:
        indices = build_recovery_indices(scenario, columns)
        return _ScopeDependencies(
            indices=indices,
            incidence=build_recovery_incidence(scenario, columns, indices),
            crew_incidence=build_crew_recovery_incidence(
                scenario, columns, indices
            ),
            passenger_incidence=build_passenger_recovery_incidence(
                scenario, columns, indices
            ),
            gate_inventory=build_gate_inventory_data(scenario, columns),
        )
    except (KeyError, ValueError) as exc:
        raise ScopeBuildError(f"scope dependency build failed: {exc}") from exc


def direct_disrupted_flight_ids(scenario: Scenario) -> tuple[str, ...]:
    """Return direct departure exposures using half-open disruption windows."""

    unsupported = sorted(
        {
            item.restriction_type
            for item in scenario.disruptions
            if item.restriction_type not in SUPPORTED_SCOPE_RESTRICTION_TYPES
        }
    )
    if unsupported:
        raise ScopeBuildError(
            "unsupported scope restriction_type values: " + ", ".join(unsupported)
        )
    direct = {
        flight.flight_id
        for disruption in scenario.disruptions
        for flight in scenario.flights
        if disruption.restriction_type == "departure_capacity_reduction"
        and flight.origin == disruption.airport
        and disruption.start_time <= flight.sched_dep < disruption.end_time
    }
    return tuple(
        flight.flight_id for flight in scenario.flights if flight.flight_id in direct
    )


def _add_reason(
    reasons: dict[str, set[str]], entity_id: str, reason: str
) -> None:
    reasons.setdefault(entity_id, set()).add(reason)


def _base_flight_id(options: Mapping[str, object], option_id: str) -> str | None:
    option = options[option_id]
    if (
        option.operation_type is FlightOperationType.OPERATE
        and option.base_flight_id is not None
    ):
        return option.base_flight_id
    return None


def build_recovery_scope(
    scenario: Scenario, columns: RecoveryColumns
) -> RecoveryScope:
    """Build the monotone fixed-point scope for the current fixed columns.

    Algorithms 3-6 of Petersen et al. provide the resource/passenger propagation
    backbone. Candidate reassignment and shared MIP-row propagation are explicit
    Phase 4 safety extensions required by this repository's fixed-column oracle.
    """

    deps = _dependencies(scenario, columns)
    indices = deps.indices
    incidence = deps.incidence
    options = {item.option_id: item for item in columns.flight_options}
    strings = {item.string_id: item for item in columns.aircraft_strings}
    pairing_owner = {
        item.pairing_id: item.crew_id for item in columns.crew_pairings
    }
    itinerary_owner = {
        item.itinerary_id: item.pax_group_id
        for item in columns.passenger_itineraries
    }

    direct = direct_disrupted_flight_ids(scenario)
    flights = set(direct)
    aircraft: set[str] = set()
    crew: set[str] = set()
    passengers: set[str] = set()
    flight_options: set[str] = set()
    aircraft_strings: set[str] = set()
    crew_pairings: set[str] = set()
    passenger_itineraries: set[str] = set()
    reasons: dict[str, set[str]] = {}
    disruption_by_flight = {
        flight.flight_id: tuple(
            disruption
            for disruption in scenario.disruptions
            if disruption.restriction_type == "departure_capacity_reduction"
            and flight.origin == disruption.airport
            and disruption.start_time <= flight.sched_dep < disruption.end_time
        )
        for flight in scenario.flights
    }
    for flight_id in direct:
        for disruption in disruption_by_flight[flight_id]:
            _add_reason(
                reasons,
                flight_id,
                "DIRECT_DISRUPTION:"
                f"{disruption.airport}:{disruption.start_time.isoformat()}:"
                f"{disruption.end_time.isoformat()}",
            )

    iteration_count = 0
    while True:
        iteration_count += 1
        before = (frozenset(flights), frozenset(aircraft), frozenset(crew), frozenset(passengers))

        # Scoped base flights expose all schedule candidates and every candidate
        # resource/passenger owner that can use one of those options.
        for flight_id in indices.flights.ids:
            if flight_id not in flights:
                continue
            for option_id in incidence.base_flight_to_options.columns_for_row(flight_id):
                flight_options.add(option_id)
                _add_reason(reasons, option_id, f"BASE_FLIGHT_SCOPED:{flight_id}")
                for string_id in incidence.option_to_aircraft_strings.columns_for_row(option_id):
                    owner = strings[string_id].aircraft_id
                    aircraft.add(owner)
                    _add_reason(
                        reasons,
                        owner,
                        f"COVERS_SCOPED_FLIGHT:{flight_id}:{option_id}:{string_id}",
                    )
                pairing_ids = (
                    incidence.option_to_operating_pairings.columns_for_row(option_id)
                    + incidence.option_to_deadhead_pairings.columns_for_row(option_id)
                )
                for pairing_id in pairing_ids:
                    owner = pairing_owner[pairing_id]
                    crew.add(owner)
                    _add_reason(
                        reasons,
                        owner,
                        f"PAIRING_USES_SCOPED_FLIGHT:{flight_id}:{option_id}:{pairing_id}",
                    )
                for itinerary_id in incidence.option_to_passenger_itineraries.columns_for_row(option_id):
                    owner = itinerary_owner[itinerary_id]
                    passengers.add(owner)
                    _add_reason(
                        reasons,
                        owner,
                        f"ITINERARY_USES_SCOPED_FLIGHT:{flight_id}:{option_id}:{itinerary_id}",
                    )

        # Every candidate of a scoped owner is free; every referenced revenue
        # base flight must therefore join the closure.
        for aircraft_id in indices.aircraft.ids:
            if aircraft_id not in aircraft:
                continue
            for string_id in incidence.aircraft_to_strings.columns_for_row(aircraft_id):
                aircraft_strings.add(string_id)
                _add_reason(reasons, string_id, f"SCOPED_AIRCRAFT:{aircraft_id}")
                for option_id in strings[string_id].leg_option_ids:
                    flight_options.add(option_id)
                    _add_reason(reasons, option_id, f"CANDIDATE_STRING:{string_id}")
                    base_id = _base_flight_id(options, option_id)
                    if base_id is not None:
                        flights.add(base_id)
                        _add_reason(reasons, base_id, f"CANDIDATE_STRING:{string_id}:{option_id}")

        for crew_id in indices.crew.ids:
            if crew_id not in crew:
                continue
            for pairing_id in incidence.crew_to_pairings.columns_for_row(crew_id):
                crew_pairings.add(pairing_id)
                _add_reason(reasons, pairing_id, f"SCOPED_CREW:{crew_id}")
                option_ids = (
                    deps.crew_incidence.pairing_to_operated_options[pairing_id]
                    + deps.crew_incidence.pairing_to_deadhead_options[pairing_id]
                )
                for option_id in option_ids:
                    flight_options.add(option_id)
                    _add_reason(reasons, option_id, f"CANDIDATE_PAIRING:{pairing_id}")
                    base_id = _base_flight_id(options, option_id)
                    if base_id is not None:
                        flights.add(base_id)
                        _add_reason(reasons, base_id, f"CANDIDATE_PAIRING:{pairing_id}:{option_id}")

        for group_id in indices.passenger_groups.ids:
            if group_id not in passengers:
                continue
            for itinerary_id in deps.passenger_incidence.group_to_itineraries.columns_for_row(group_id):
                passenger_itineraries.add(itinerary_id)
                _add_reason(reasons, itinerary_id, f"SCOPED_PASSENGER:{group_id}")
                for option_id in deps.passenger_incidence.itinerary_to_flight_options[itinerary_id]:
                    flight_options.add(option_id)
                    _add_reason(reasons, option_id, f"CANDIDATE_ITINERARY:{itinerary_id}")
                    base_id = _base_flight_id(options, option_id)
                    if base_id is not None:
                        flights.add(base_id)
                        _add_reason(reasons, base_id, f"CANDIDATE_ITINERARY:{itinerary_id}:{option_id}")

        # Airport-capacity rows are shared x-variable constraints.
        for label, relation in (
            ("DEPARTURE", incidence.departure_capacity_to_options),
            ("ARRIVAL", incidence.arrival_capacity_to_options),
        ):
            for row in relation.rows:
                row_options = relation.columns_for_row(row)
                sources = tuple(item for item in row_options if item in flight_options)
                if not sources:
                    continue
                for option_id in row_options:
                    base_id = _base_flight_id(options, option_id)
                    if base_id is not None and base_id not in flights:
                        flights.add(base_id)
                        _add_reason(
                            reasons,
                            base_id,
                            f"SHARED_{label}_CAPACITY:{row.airport}:"
                            f"{row.start_time.isoformat()}:{sources[0]}",
                        )

        # Gate checkpoints are the exact cumulative rows used by the SRM block.
        for checkpoint in deps.gate_inventory.checkpoints:
            row_options = tuple(checkpoint.coefficient_by_option)
            sources = tuple(item for item in row_options if item in flight_options)
            if not sources:
                continue
            for option_id in row_options:
                base_id = _base_flight_id(options, option_id)
                if base_id is not None and base_id not in flights:
                    flights.add(base_id)
                    _add_reason(
                        reasons,
                        base_id,
                        f"SHARED_GATE_CHECKPOINT:{checkpoint.checkpoint_id}:{sources[0]}",
                    )

        # Seat-capacity competition is represented by itineraries sharing an
        # operated option. It can expose groups not found from original plans.
        for option_id in indices.revenue_operate_options.ids:
            if option_id not in flight_options:
                continue
            for itinerary_id in deps.passenger_incidence.option_to_itineraries.columns_for_row(option_id):
                owner = itinerary_owner[itinerary_id]
                passengers.add(owner)
                _add_reason(
                    reasons,
                    owner,
                    f"SHARED_SEAT_CAPACITY:{option_id}:{itinerary_id}",
                )

        after = (frozenset(flights), frozenset(aircraft), frozenset(crew), frozenset(passengers))
        if after == before:
            break

    def ordered(index_ids: tuple[str, ...], selected: set[str]) -> tuple[str, ...]:
        return tuple(item_id for item_id in index_ids if item_id in selected)

    scope = RecoveryScope(
        direct_flight_ids=direct,
        flight_ids=ordered(indices.flights.ids, flights),
        aircraft_ids=ordered(indices.aircraft.ids, aircraft),
        crew_ids=ordered(indices.crew.ids, crew),
        passenger_group_ids=ordered(indices.passenger_groups.ids, passengers),
        flight_option_ids=ordered(indices.flight_options.ids, flight_options),
        aircraft_string_ids=ordered(indices.aircraft_strings.ids, aircraft_strings),
        crew_pairing_ids=ordered(indices.crew_pairings.ids, crew_pairings),
        passenger_itinerary_ids=ordered(
            indices.passenger_itineraries.ids, passenger_itineraries
        ),
        propagation_reasons=reasons,
        iteration_count=iteration_count,
    )
    _assert_scope_invariants(scenario, columns, scope, deps)
    return scope


def _assert_subset(label: str, actual: tuple[str, ...], universe: tuple[str, ...]) -> None:
    unknown = sorted(set(actual) - set(universe))
    if unknown:
        raise ScopeBuildError(f"scope contains unknown {label} IDs: {unknown}")


def _assert_scope_invariants(
    scenario: Scenario,
    columns: RecoveryColumns,
    scope: RecoveryScope,
    deps: _ScopeDependencies,
) -> None:
    indices = deps.indices
    _assert_subset("flight", scope.flight_ids, indices.flights.ids)
    _assert_subset("aircraft", scope.aircraft_ids, indices.aircraft.ids)
    _assert_subset("crew", scope.crew_ids, indices.crew.ids)
    _assert_subset("passenger group", scope.passenger_group_ids, indices.passenger_groups.ids)
    _assert_subset("flight option", scope.flight_option_ids, indices.flight_options.ids)
    _assert_subset("aircraft string", scope.aircraft_string_ids, indices.aircraft_strings.ids)
    _assert_subset("crew pairing", scope.crew_pairing_ids, indices.crew_pairings.ids)
    _assert_subset("passenger itinerary", scope.passenger_itinerary_ids, indices.passenger_itineraries.ids)
    explained_ids = (
        set(scope.flight_ids)
        | set(scope.aircraft_ids)
        | set(scope.crew_ids)
        | set(scope.passenger_group_ids)
        | set(scope.flight_option_ids)
        | set(scope.aircraft_string_ids)
        | set(scope.crew_pairing_ids)
        | set(scope.passenger_itinerary_ids)
    )
    unexplained = sorted(
        item_id
        for item_id in explained_ids
        if not scope.propagation_reasons.get(item_id)
    )
    if unexplained:
        raise ScopeBuildError(
            f"scoped entities/candidates lack propagation reasons: {unexplained}"
        )
    missing_direct = sorted(set(direct_disrupted_flight_ids(scenario)) - set(scope.flight_ids))
    if missing_direct:
        raise ScopeBuildError(f"direct disrupted flights missing from scope: {missing_direct}")

    options = {item.option_id: item for item in columns.flight_options}
    missing: list[str] = []
    for aircraft_id in scope.aircraft_ids:
        for string_id in deps.incidence.aircraft_to_strings.columns_for_row(aircraft_id):
            for option_id in deps.incidence.option_to_aircraft_strings.rows_for_column(string_id):
                base_id = _base_flight_id(options, option_id)
                if base_id is not None and base_id not in scope.flight_ids:
                    missing.append(f"aircraft:{aircraft_id}:{string_id}:{base_id}")
    for crew_id in scope.crew_ids:
        for pairing_id in deps.incidence.crew_to_pairings.columns_for_row(crew_id):
            option_ids = (
                deps.crew_incidence.pairing_to_operated_options[pairing_id]
                + deps.crew_incidence.pairing_to_deadhead_options[pairing_id]
            )
            for option_id in option_ids:
                base_id = _base_flight_id(options, option_id)
                if base_id is not None and base_id not in scope.flight_ids:
                    missing.append(f"crew:{crew_id}:{pairing_id}:{base_id}")
    for group_id in scope.passenger_group_ids:
        for itinerary_id in deps.passenger_incidence.group_to_itineraries.columns_for_row(group_id):
            for option_id in deps.passenger_incidence.itinerary_to_flight_options[itinerary_id]:
                base_id = _base_flight_id(options, option_id)
                if base_id is not None and base_id not in scope.flight_ids:
                    missing.append(f"passenger:{group_id}:{itinerary_id}:{base_id}")
    if missing:
        raise ScopeBuildError("scope resource/passenger closure is broken: " + ", ".join(sorted(missing)))

def validate_recovery_scope(
    scenario: Scenario, columns: RecoveryColumns, scope: RecoveryScope
) -> None:
    """Reject an unknown, incomplete, or non-canonical caller-supplied scope."""

    deps = _dependencies(scenario, columns)
    _assert_scope_invariants(scenario, columns, scope, deps)
    canonical = build_recovery_scope(scenario, columns)
    labels_and_values = (
        ("direct flights", scope.direct_flight_ids, canonical.direct_flight_ids),
        ("flights", scope.flight_ids, canonical.flight_ids),
        ("aircraft", scope.aircraft_ids, canonical.aircraft_ids),
        ("crew", scope.crew_ids, canonical.crew_ids),
        ("passengers", scope.passenger_group_ids, canonical.passenger_group_ids),
        ("options", scope.flight_option_ids, canonical.flight_option_ids),
        ("strings", scope.aircraft_string_ids, canonical.aircraft_string_ids),
        ("pairings", scope.crew_pairing_ids, canonical.crew_pairing_ids),
        ("itineraries", scope.passenger_itinerary_ids, canonical.passenger_itinerary_ids),
    )
    details = [
        f"{label}:missing={sorted(set(expected) - set(actual))},"
        f"extra={sorted(set(actual) - set(expected))}"
        for label, actual, expected in labels_and_values
        if tuple(actual) != tuple(expected)
    ]
    if details:
        raise ScopeBuildError(
            "scope fixed-point closure differs: " + "; ".join(details)
        )


def _unique_candidate(
    label: str, owner_id: str, candidates: list[str]
) -> str:
    if len(candidates) != 1:
        raise ScopeBuildError(
            f"semantic original {label} for {owner_id!r} must be unique; "
            f"found {len(candidates)}: {sorted(candidates)}"
        )
    return candidates[0]


def resolve_original_candidates(
    scenario: Scenario, columns: RecoveryColumns
) -> OriginalCandidates:
    """Resolve original candidates only from business semantics, never IDs."""

    options = {item.option_id: item for item in columns.flight_options}
    original_option = dict(
        resolve_original_flight_option_ids(scenario, columns.flight_options)
    )

    original_string: dict[str, str] = {}
    for aircraft in scenario.aircraft:
        expected = tuple(original_option[item] for item in aircraft.original_rotation)
        matches = []
        for string in columns.aircraft_strings:
            if string.aircraft_id != aircraft.tail_id:
                continue
            revenue = tuple(
                option_id
                for option_id in string.leg_option_ids
                if options[option_id].operation_type is FlightOperationType.OPERATE
                and options[option_id].base_flight_id is not None
            )
            if revenue == expected and len(revenue) == len(string.leg_option_ids):
                matches.append(string.string_id)
        original_string[aircraft.tail_id] = _unique_candidate(
            "aircraft string", aircraft.tail_id, matches
        )

    original_pairing: dict[str, str] = {}
    for crew in scenario.crew:
        expected_options = tuple(original_option[item] for item in crew.original_pairing)
        matches = []
        for pairing in columns.crew_pairings:
            if pairing.crew_id != crew.crew_id:
                continue
            operated = tuple(
                segment.flight_option_id
                for duty in pairing.duties
                for segment in duty.segments
                if segment.segment_type is CrewSegmentType.OPERATE
            )
            all_segments = tuple(
                segment for duty in pairing.duties for segment in duty.segments
            )
            if operated == expected_options and len(operated) == len(all_segments):
                matches.append(pairing.pairing_id)
        original_pairing[crew.crew_id] = _unique_candidate(
            "crew pairing", crew.crew_id, matches
        )

    original_itinerary: dict[str, str] = {}
    for group in scenario.passengers:
        expected_options = tuple(original_option[item] for item in group.original_itinerary)
        matches = []
        for itinerary in columns.passenger_itineraries:
            if itinerary.pax_group_id != group.pax_group_id:
                continue
            segments = tuple(
                segment.flight_option_id
                for segment in itinerary.segments
                if segment.segment_type is PassengerSegmentType.FLIGHT
            )
            if segments == expected_options and len(segments) == len(itinerary.segments):
                matches.append(itinerary.itinerary_id)
        original_itinerary[group.pax_group_id] = _unique_candidate(
            "passenger itinerary", group.pax_group_id, matches
        )

    return OriginalCandidates(
        flight_option_by_flight=original_option,
        aircraft_string_by_aircraft=original_string,
        crew_pairing_by_crew=original_pairing,
        passenger_itinerary_by_group=original_itinerary,
    )


def resolve_original_flight_option_ids(
    scenario: Scenario, flight_options: Sequence[FlightOption]
) -> Mapping[str, str]:
    """Resolve each original schedule option without relying on its ID text."""

    original_option: dict[str, str] = {}
    for flight in scenario.flights:
        matches = [
            option.option_id
            for option in flight_options
            if option.base_flight_id == flight.flight_id
            and option.operation_type is FlightOperationType.OPERATE
            and option.change_types == [FlightChangeType.UNCHANGED]
            and option.origin == flight.origin
            and option.destination == flight.destination
            and option.dep_time == flight.sched_dep
            and option.arr_time == flight.sched_arr
            and option.block_minutes == flight.duration
            and option.departure_delay_minutes == 0
            and option.arrival_delay_minutes == 0
        ]
        original_option[flight.flight_id] = _unique_candidate(
            "flight option", flight.flight_id, matches
        )
    return MappingProxyType(original_option)


def scope_metrics(
    scenario: Scenario, columns: RecoveryColumns, scope: RecoveryScope
) -> dict[str, object]:
    schedule_options = tuple(
        item
        for item in columns.flight_options
        if item.operation_type in {FlightOperationType.OPERATE, FlightOperationType.CANCEL}
    )
    scoped_flights = set(scope.flight_ids)
    scoped_aircraft = set(scope.aircraft_ids)
    scoped_crew = set(scope.crew_ids)
    scoped_passengers = set(scope.passenger_group_ids)
    free_x = sum(item.base_flight_id in scoped_flights for item in schedule_options)
    free_y = sum(item.aircraft_id in scoped_aircraft for item in columns.aircraft_strings)
    free_z = sum(item.crew_id in scoped_crew for item in columns.crew_pairings)
    free_w = sum(item.pax_group_id in scoped_passengers for item in columns.passenger_itineraries)
    totals = {
        "x": len(schedule_options),
        "y": len(columns.aircraft_strings),
        "z": len(columns.crew_pairings),
        "w": len(columns.passenger_itineraries),
    }
    free = {"x": free_x, "y": free_y, "z": free_z, "w": free_w}
    total_binary = sum(totals.values())
    free_binary = sum(free.values())
    reason_counts = Counter(
        reason.split(":", 1)[0]
        for values in scope.propagation_reasons.values()
        for reason in values
    )
    return {
        "total_flights": len(scenario.flights),
        "scoped_flights": len(scope.flight_ids),
        "total_aircraft": len(scenario.aircraft),
        "scoped_aircraft": len(scope.aircraft_ids),
        "total_crew": len(scenario.crew),
        "scoped_crew": len(scope.crew_ids),
        "total_passenger_groups": len(scenario.passengers),
        "scoped_passenger_groups": len(scope.passenger_group_ids),
        "total_candidates": totals,
        "free_candidates": free,
        "fixed_candidates": {key: totals[key] - free[key] for key in totals},
        "total_binary_candidates": total_binary,
        "free_binary_candidates": free_binary,
        "fixed_binary_candidates": total_binary - free_binary,
        "free_binary_ratio": free_binary / total_binary if total_binary else 0.0,
        "scoped_flight_ratio": len(scope.flight_ids) / len(scenario.flights) if scenario.flights else 0.0,
        "scope_iteration_count": scope.iteration_count,
        "propagation_reason_counts": dict(sorted(reason_counts.items())),
    }
