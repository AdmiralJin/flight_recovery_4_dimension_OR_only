from __future__ import annotations

import hashlib
import itertools
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from types import MappingProxyType

from backend.config.itinerary_generation import PassengerItineraryGenerationConfig
from backend.schemas.columns import (
    FlightOperationType,
    FlightOption,
    PassengerItinerary,
    PassengerItineraryStatus,
    PassengerSegment,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.common import minutes_between
from backend.schemas.passenger import PassengerCommodity
from backend.schemas.scenario import Scenario

from .passenger_network import (
    PassengerFlightNetwork,
    build_passenger_flight_network,
    validate_flight_option_for_passenger,
)
from .scope import RecoveryScope, ScopeBuildError, resolve_original_flight_option_ids


class PassengerItineraryGenerationError(ValueError):
    """Phase 7 cannot produce an auditable passenger candidate set."""


@dataclass(frozen=True)
class ItineraryLegalityResult:
    valid: bool
    violations: tuple[str, ...]


@dataclass(frozen=True)
class ItineraryGenerationResult:
    itineraries: tuple[PassengerItinerary, ...]
    networks: Mapping[str, PassengerFlightNetwork]
    metrics: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "networks", MappingProxyType(dict(self.networks)))
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


def itinerary_semantic_key(
    itinerary: PassengerItinerary,
) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    if itinerary.status is PassengerItineraryStatus.UNSERVED:
        return itinerary.pax_group_id, itinerary.status.value, ()
    return (
        itinerary.pax_group_id,
        itinerary.status.value,
        tuple(
            (segment.segment_type.value, segment.flight_option_id or "")
            for segment in itinerary.segments
        ),
    )


def _itinerary_id(
    pax_group_id: str,
    status: PassengerItineraryStatus,
    option_ids: Sequence[str],
) -> str:
    payload = "\x00".join((pax_group_id, status.value, *option_ids)).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16].upper()
    safe_group = "".join(
        character if character.isalnum() else "_" for character in pax_group_id
    )
    return f"GEN_PI_{safe_group}_{digest}"


def _make_transported_itinerary(
    passenger: PassengerCommodity,
    option_ids: Sequence[str],
    options: Mapping[str, FlightOption],
) -> PassengerItinerary:
    last = options[option_ids[-1]]
    assert last.arr_time is not None
    delay = max(0, minutes_between(passenger.scheduled_arrival, last.arr_time))
    return PassengerItinerary(
        itinerary_id=_itinerary_id(
            passenger.pax_group_id,
            PassengerItineraryStatus.TRANSPORTED,
            option_ids,
        ),
        pax_group_id=passenger.pax_group_id,
        status=PassengerItineraryStatus.TRANSPORTED,
        segments=[
            PassengerSegment(
                segment_type=PassengerSegmentType.FLIGHT,
                flight_option_id=option_id,
                origin=None,
                destination=None,
                dep_time=None,
                arr_time=None,
            )
            for option_id in option_ids
        ],
        final_destination=passenger.destination,
        arrival_time=last.arr_time,
        arrival_delay_minutes=delay,
        cost_components={},
        notes=(
            "Phase 7 deterministic full explicit enumeration within the v1 "
            "generation profile."
        ),
    )


def _make_unserved_itinerary(
    passenger: PassengerCommodity,
) -> PassengerItinerary:
    return PassengerItinerary(
        itinerary_id=_itinerary_id(
            passenger.pax_group_id,
            PassengerItineraryStatus.UNSERVED,
            (),
        ),
        pax_group_id=passenger.pax_group_id,
        status=PassengerItineraryStatus.UNSERVED,
        segments=[],
        final_destination=None,
        arrival_time=None,
        arrival_delay_minutes=None,
        cost_components={},
        notes="Phase 7 explicit unserved candidate.",
    )


def validate_generated_passenger_itinerary(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    passenger: PassengerCommodity,
    candidate: PassengerItinerary,
    config: PassengerItineraryGenerationConfig,
) -> ItineraryLegalityResult:
    """Pure candidate validator, independent from smart path enumeration."""

    violations: list[str] = []
    options = {item.option_id: item for item in flight_options}
    if candidate.pax_group_id != passenger.pax_group_id:
        violations.append("passenger_ownership_mismatch")

    if candidate.status is PassengerItineraryStatus.UNSERVED:
        if not config.allow_unserved:
            violations.append("unserved_disabled")
        if candidate.segments or any(
            value is not None
            for value in (
                candidate.final_destination,
                candidate.arrival_time,
                candidate.arrival_delay_minutes,
            )
        ):
            violations.append("unserved_shape_violation")
        return ItineraryLegalityResult(
            valid=not violations,
            violations=tuple(dict.fromkeys(violations)),
        )

    if candidate.status is not PassengerItineraryStatus.TRANSPORTED:
        violations.append("unknown_itinerary_status")
    if not candidate.segments:
        violations.append("transported_without_segments")
    if any(
        value is None
        for value in (
            candidate.final_destination,
            candidate.arrival_time,
            candidate.arrival_delay_minutes,
        )
    ):
        violations.append("transported_shape_violation")
    if len(candidate.segments) > config.max_flight_legs:
        violations.append("max_flight_legs_exceeded")

    resolved: list[tuple[str, str, datetime, datetime, str | None]] = []
    option_ids: list[str] = []
    for segment in candidate.segments:
        if segment.segment_type is PassengerSegmentType.SURFACE:
            if not config.allow_surface:
                violations.append("surface_disabled")
                continue
            if None in (
                segment.origin,
                segment.destination,
                segment.dep_time,
                segment.arr_time,
            ):
                violations.append("invalid_surface_shape")
                continue
            assert segment.dep_time is not None and segment.arr_time is not None
            if segment.dep_time < scenario.recovery_window.start_time or (
                segment.arr_time > scenario.recovery_window.end_time
            ):
                violations.append("outside_recovery_horizon")
            resolved.append(
                (
                    segment.origin or "",
                    segment.destination or "",
                    segment.dep_time,
                    segment.arr_time,
                    None,
                )
            )
            continue
        if segment.segment_type is not PassengerSegmentType.FLIGHT:
            violations.append("unsupported_segment_type")
            continue
        option_id = segment.flight_option_id or ""
        option_ids.append(option_id)
        option = options.get(option_id)
        if option is None:
            violations.append(f"unknown_flight_option:{option_id}")
            continue
        eligibility = validate_flight_option_for_passenger(
            scenario, option, passenger, config
        )
        violations.extend(eligibility.reasons)
        if None not in (
            option.origin,
            option.destination,
            option.dep_time,
            option.arr_time,
        ):
            resolved.append(
                (
                    option.origin or "",
                    option.destination or "",
                    option.dep_time,
                    option.arr_time,
                    option.base_flight_id,
                )
            )

    if len(option_ids) != len(set(option_ids)):
        violations.append("duplicate_flight_option")
    base_ids = [item[4] for item in resolved if item[4] is not None]
    if len(base_ids) != len(set(base_ids)):
        violations.append("duplicate_base_flight")

    if resolved:
        first = resolved[0]
        last = resolved[-1]
        if first[0] != passenger.origin:
            violations.append("origin_mismatch")
        if first[2] < passenger.original_departure:
            violations.append("departure_before_passenger_ready")
        if last[1] != passenger.destination:
            violations.append("destination_mismatch")
        for left, right in zip(resolved, resolved[1:]):
            if left[1] != right[0]:
                violations.append("station_discontinuity")
            try:
                connection = minutes_between(left[3], right[2])
            except ValueError:
                violations.append("non_integral_connection_minutes")
            else:
                if connection < 0:
                    violations.append("time_overlap")
                elif connection < config.default_mct_minutes:
                    violations.append("mct_violation")

        actual_arrival = last[3]
        if candidate.final_destination != passenger.destination:
            violations.append("final_destination_mismatch")
        if candidate.arrival_time != actual_arrival:
            violations.append("arrival_time_mismatch")
        try:
            expected_delay = max(
                0,
                minutes_between(passenger.scheduled_arrival, actual_arrival),
            )
        except ValueError:
            violations.append("arrival_delay_mismatch")
        else:
            if candidate.arrival_delay_minutes != expected_delay:
                violations.append("arrival_delay_mismatch")

    return ItineraryLegalityResult(
        valid=not violations,
        violations=tuple(dict.fromkeys(violations)),
    )


def _original_paths_by_group(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
) -> Mapping[str, tuple[str, ...]]:
    try:
        originals = resolve_original_flight_option_ids(scenario, flight_options)
    except ScopeBuildError as exc:
        raise PassengerItineraryGenerationError(
            f"original flight-option resolution failed: {exc}"
        ) from exc
    paths: dict[str, tuple[str, ...]] = {}
    for passenger in scenario.passengers:
        missing = [
            flight_id
            for flight_id in passenger.original_itinerary
            if flight_id not in originals
        ]
        if missing:
            raise PassengerItineraryGenerationError(
                f"passenger group {passenger.pax_group_id!r} original itinerary "
                f"references unresolved flights: {missing}"
            )
        paths[passenger.pax_group_id] = tuple(
            originals[flight_id] for flight_id in passenger.original_itinerary
        )
    return MappingProxyType(paths)


def _enumerate_network_itineraries(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    passenger: PassengerCommodity,
    config: PassengerItineraryGenerationConfig,
    network: PassengerFlightNetwork,
) -> tuple[tuple[PassengerItinerary, ...], Counter[str]]:
    options = {item.option_id: item for item in flight_options}
    emitted: dict[tuple[str, str, tuple[tuple[str, str], ...]], PassengerItinerary] = {}
    pruned: Counter[str] = Counter()

    def emit(path: tuple[str, ...]) -> None:
        candidate = _make_transported_itinerary(passenger, path, options)
        audit = validate_generated_passenger_itinerary(
            scenario, flight_options, passenger, candidate, config
        )
        if not audit.valid:
            raise PassengerItineraryGenerationError(
                f"generator emitted illegal itinerary for {passenger.pax_group_id!r}: "
                f"path={path}, violations={audit.violations}"
            )
        emitted[itinerary_semantic_key(candidate)] = candidate

    if config.allow_unserved:
        unserved = _make_unserved_itinerary(passenger)
        audit = validate_generated_passenger_itinerary(
            scenario, flight_options, passenger, unserved, config
        )
        if not audit.valid:
            raise PassengerItineraryGenerationError(
                f"illegal unserved itinerary for {passenger.pax_group_id!r}: "
                f"{audit.violations}"
            )
        emitted[itinerary_semantic_key(unserved)] = unserved

    def dfs(
        path: tuple[str, ...],
        used_options: frozenset[str],
        used_base_flights: frozenset[str],
    ) -> None:
        last = options[path[-1]]
        if last.destination == passenger.destination:
            emit(path)
            return
        if len(path) >= config.max_flight_legs:
            pruned["max_flight_legs_exceeded"] += 1
            return
        for next_id in network.successor_option_ids[path[-1]]:
            if next_id in used_options:
                pruned["duplicate_flight_option"] += 1
                continue
            next_option = options[next_id]
            base_id = next_option.base_flight_id
            if base_id is not None and base_id in used_base_flights:
                pruned["duplicate_base_flight"] += 1
                continue
            dfs(
                (*path, next_id),
                used_options | {next_id},
                used_base_flights | ({base_id} if base_id else set()),
            )

    for option_id in network.start_option_ids:
        option = options[option_id]
        base_ids = (
            frozenset({option.base_flight_id})
            if option.base_flight_id is not None
            else frozenset()
        )
        dfs((option_id,), frozenset({option_id}), base_ids)
    return tuple(emitted[key] for key in sorted(emitted)), pruned


def generate_passenger_itineraries_with_metrics(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
    config: PassengerItineraryGenerationConfig,
) -> ItineraryGenerationResult:
    """Generate Phase 7 itinerary candidates from existing Flight Options."""

    started = perf_counter()
    option_ids = tuple(item.option_id for item in flight_options)
    if len(option_ids) != len(set(option_ids)):
        raise PassengerItineraryGenerationError("flight option IDs must be unique")
    passenger_ids = tuple(item.pax_group_id for item in scenario.passengers)
    scoped_ids = set(passenger_ids if scope is None else scope.passenger_group_ids)
    unknown_scope = sorted(scoped_ids - set(passenger_ids))
    if unknown_scope:
        raise PassengerItineraryGenerationError(
            f"scope contains unknown passenger group IDs: {unknown_scope}"
        )

    originals = _original_paths_by_group(scenario, flight_options)
    networks: dict[str, PassengerFlightNetwork] = {}
    all_itineraries: list[PassengerItinerary] = []
    count_by_group: dict[str, int] = {}
    original_status: dict[str, object] = {}
    rejected_candidates: Counter[str] = Counter()
    rejected_edges: Counter[str] = Counter()

    for passenger in scenario.passengers:
        network = build_passenger_flight_network(
            scenario, flight_options, passenger, config
        )
        networks[passenger.pax_group_id] = network
        for reasons in network.rejected_option_reasons.values():
            rejected_candidates.update(reasons)
        rejected_edges.update(network.rejected_edge_counts)

        original_candidate = _make_transported_itinerary(
            passenger,
            originals[passenger.pax_group_id],
            {item.option_id: item for item in flight_options},
        )
        original_audit = validate_generated_passenger_itinerary(
            scenario, flight_options, passenger, original_candidate, config
        )
        if passenger.pax_group_id in scoped_ids:
            generated, pruned = _enumerate_network_itineraries(
                scenario, flight_options, passenger, config, network
            )
            rejected_candidates.update(pruned)
            original_status[passenger.pax_group_id] = (
                "legal" if original_audit.valid else list(original_audit.violations)
            )
            generated_keys = {itinerary_semantic_key(item) for item in generated}
            if (
                original_audit.valid
                and itinerary_semantic_key(original_candidate) not in generated_keys
            ):
                raise PassengerItineraryGenerationError(
                    "legal original itinerary was not enumerated for "
                    f"{passenger.pax_group_id!r}"
                )
        else:
            if not original_audit.valid:
                raise PassengerItineraryGenerationError(
                    f"out-of-scope original itinerary is illegal for "
                    f"{passenger.pax_group_id!r}: {original_audit.violations}"
                )
            generated = (original_candidate,)
            original_status[passenger.pax_group_id] = "legal_out_of_scope_retained"

        if not generated:
            raise PassengerItineraryGenerationError(
                f"passenger group {passenger.pax_group_id!r} has no legal candidate"
            )
        count_by_group[passenger.pax_group_id] = len(generated)
        all_itineraries.extend(generated)

    keys = [itinerary_semantic_key(item) for item in all_itineraries]
    if len(keys) != len(set(keys)):
        raise PassengerItineraryGenerationError(
            "generated duplicate semantic itineraries"
        )
    transported_count = sum(
        item.status is PassengerItineraryStatus.TRANSPORTED for item in all_itineraries
    )
    metrics: dict[str, object] = {
        "passenger_group_count": len(scenario.passengers),
        "scoped_passenger_group_count": len(scoped_ids),
        "flight_option_count": len(flight_options),
        "network_node_count": sum(item.node_count for item in networks.values()),
        "network_edge_count": sum(item.edge_count for item in networks.values()),
        "generated_itinerary_count": len(all_itineraries),
        "generated_transported_count": transported_count,
        "generated_unserved_count": len(all_itineraries) - transported_count,
        "generated_itinerary_count_by_group": count_by_group,
        "rejected_candidate_count_by_reason": dict(sorted(rejected_candidates.items())),
        "rejected_edge_count_by_reason": dict(sorted(rejected_edges.items())),
        "original_itinerary_status_by_group": original_status,
        "generation_runtime_seconds": perf_counter() - started,
        "generation_mode": (
            "full_explicit_enumeration_within_phase7_v1_profile_without_pricing"
        ),
    }
    return ItineraryGenerationResult(
        itineraries=tuple(all_itineraries),
        networks=networks,
        metrics=metrics,
    )


def generate_passenger_itineraries(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
    config: PassengerItineraryGenerationConfig,
) -> tuple[PassengerItinerary, ...]:
    return generate_passenger_itineraries_with_metrics(
        scenario, flight_options, scope, config
    ).itineraries


def replace_passenger_itineraries(
    columns: RecoveryColumns,
    passenger_itineraries: Sequence[PassengerItinerary],
) -> RecoveryColumns:
    """Return validated columns with only the passenger universe replaced."""

    data = columns.model_dump(mode="json")
    data["passenger_itineraries"] = [
        item.model_dump(mode="json") for item in passenger_itineraries
    ]
    return RecoveryColumns.model_validate(data)


def brute_force_legal_passenger_itineraries(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    passenger: PassengerCommodity,
    config: PassengerItineraryGenerationConfig,
    *,
    max_options: int = 8,
) -> tuple[PassengerItinerary, ...]:
    """Independent tiny-case oracle using ordered option permutations."""

    eligible = tuple(
        sorted(
            (
                item
                for item in flight_options
                if validate_flight_option_for_passenger(
                    scenario, item, passenger, config
                ).eligible
            ),
            key=lambda item: (item.dep_time, item.arr_time, item.option_id),
        )
    )
    if len(eligible) > max_options:
        raise PassengerItineraryGenerationError(
            f"brute-force oracle limited to {max_options} eligible options; "
            f"got {len(eligible)} for {passenger.pax_group_id!r}"
        )
    options = {item.option_id: item for item in flight_options}
    legal: dict[tuple[str, str, tuple[tuple[str, str], ...]], PassengerItinerary] = {}
    if config.allow_unserved:
        unserved = _make_unserved_itinerary(passenger)
        if validate_generated_passenger_itinerary(
            scenario, flight_options, passenger, unserved, config
        ).valid:
            legal[itinerary_semantic_key(unserved)] = unserved
    for length in range(1, config.max_flight_legs + 1):
        for permutation in itertools.permutations(eligible, length):
            option_path = tuple(item.option_id for item in permutation)
            candidate = _make_transported_itinerary(passenger, option_path, options)
            if validate_generated_passenger_itinerary(
                scenario, flight_options, passenger, candidate, config
            ).valid:
                legal[itinerary_semantic_key(candidate)] = candidate
    return tuple(legal[key] for key in sorted(legal))
