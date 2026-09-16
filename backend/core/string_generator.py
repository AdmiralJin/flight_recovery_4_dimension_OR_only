from __future__ import annotations

import hashlib
import itertools
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from time import perf_counter
from types import MappingProxyType

from backend.config.string_generation import FlightStringGenerationConfig
from backend.schemas.aircraft import Aircraft
from backend.schemas.columns import AircraftString, FlightOperationType, FlightOption
from backend.schemas.scenario import Scenario

from .flight_network import (
    AircraftFlightNetwork,
    build_aircraft_flight_network,
    validate_flight_option_for_aircraft,
)
from .scope import (
    RecoveryScope,
    ScopeBuildError,
    resolve_original_flight_option_ids,
)


class FlightStringGenerationError(ValueError):
    """Phase 5 cannot produce an auditable candidate set."""


@dataclass(frozen=True)
class StringLegalityResult:
    valid: bool
    violations: tuple[str, ...]


@dataclass(frozen=True)
class StringGenerationResult:
    strings: tuple[AircraftString, ...]
    networks: Mapping[str, AircraftFlightNetwork]
    metrics: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "networks", MappingProxyType(dict(self.networks)))
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


def aircraft_string_semantic_key(
    aircraft_id: str, option_ids: Sequence[str]
) -> tuple[str, tuple[str, ...]]:
    """Return the stable Phase 5/9 identity of an aircraft path."""

    return aircraft_id, tuple(option_ids)


def aircraft_string_id(aircraft_id: str, option_ids: Sequence[str]) -> str:
    """Return the deterministic ID shared by full enumeration and pricing."""

    payload = "\x00".join((aircraft_id, *option_ids)).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16].upper()
    safe_aircraft = "".join(
        character if character.isalnum() else "_" for character in aircraft_id
    )
    return f"GEN_AS_{safe_aircraft}_{digest}"


def make_generated_aircraft_string(
    aircraft: Aircraft, option_ids: Sequence[str]
) -> AircraftString:
    """Build a generated column without changing the Phase 5 ID contract."""

    return AircraftString(
        string_id=aircraft_string_id(aircraft.tail_id, option_ids),
        aircraft_id=aircraft.tail_id,
        leg_option_ids=list(option_ids),
        start_station=aircraft.initial_station_at_t,
        end_station=aircraft.required_station_at_T_end,
        maintenance_satisfied=True,
        cost_components={},
        notes="Phase 5 deterministic explicit/full-enumeration candidate.",
    )


# Backward-local aliases keep the Phase 5 implementation readable while exposing
# the exact same identity contract to the Phase 9 pricer.
_canonical_key = aircraft_string_semantic_key
_string_id = aircraft_string_id
_make_string = make_generated_aircraft_string


def validate_generated_aircraft_string(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    aircraft: Aircraft,
    candidate: AircraftString,
    config: FlightStringGenerationConfig,
) -> StringLegalityResult:
    """Pure independent validator for one generated Aircraft String."""

    violations: list[str] = []
    options = {item.option_id: item for item in flight_options}
    if candidate.aircraft_id != aircraft.tail_id:
        violations.append("aircraft_ownership_mismatch")
    if candidate.start_station != aircraft.initial_station_at_t:
        violations.append("start_station_mismatch")
    if candidate.end_station != aircraft.required_station_at_T_end:
        violations.append("terminal_station_mismatch")
    if len(candidate.leg_option_ids) != len(set(candidate.leg_option_ids)):
        violations.append("duplicate_flight_option")

    resolved: list[FlightOption] = []
    for option_id in candidate.leg_option_ids:
        option = options.get(option_id)
        if option is None:
            violations.append(f"unknown_flight_option:{option_id}")
            continue
        eligibility = validate_flight_option_for_aircraft(
            scenario, option, aircraft
        )
        violations.extend(eligibility.reasons)
        resolved.append(option)

    revenue_base_ids = tuple(
        item.base_flight_id
        for item in resolved
        if item.operation_type is FlightOperationType.OPERATE
        and item.base_flight_id is not None
    )
    if len(revenue_base_ids) != len(set(revenue_base_ids)):
        violations.append("duplicate_base_flight")

    if resolved:
        first = resolved[0]
        last = resolved[-1]
        if first.origin != aircraft.initial_station_at_t:
            violations.append("first_leg_origin_mismatch")
        if last.destination != aircraft.required_station_at_T_end:
            violations.append("last_leg_terminal_mismatch")
        min_turn = config.min_turn_minutes(aircraft.equipment_type)
        for left, right in zip(resolved, resolved[1:]):
            if left.destination != right.origin:
                violations.append("station_discontinuity")
            if left.arr_time is not None and right.dep_time is not None:
                if left.arr_time + timedelta(minutes=min_turn) > right.dep_time:
                    violations.append("turn_time_violation")
    elif aircraft.initial_station_at_t != aircraft.required_station_at_T_end:
        violations.append("idle_terminal_mismatch")

    if aircraft.maintenance_required:
        if not candidate.maintenance_satisfied:
            violations.append("maintenance_not_satisfied")
        if aircraft.required_station_at_T_end not in aircraft.maintenance_stations:
            violations.append("maintenance_station_mismatch")

    return StringLegalityResult(
        valid=not violations,
        violations=tuple(dict.fromkeys(violations)),
    )


def _original_path_by_aircraft(
    scenario: Scenario, flight_options: Sequence[FlightOption]
) -> Mapping[str, tuple[str, ...]]:
    try:
        originals = resolve_original_flight_option_ids(scenario, flight_options)
    except ScopeBuildError as exc:
        raise FlightStringGenerationError(
            f"original flight-option resolution failed: {exc}"
        ) from exc
    return MappingProxyType(
        {
            aircraft.tail_id: tuple(
                originals[flight_id] for flight_id in aircraft.original_rotation
            )
            for aircraft in scenario.aircraft
        }
    )


def _enumerate_network_strings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    aircraft: Aircraft,
    config: FlightStringGenerationConfig,
    network: AircraftFlightNetwork,
) -> tuple[AircraftString, ...]:
    options = {item.option_id: item for item in flight_options}
    emitted: dict[tuple[str, tuple[str, ...]], AircraftString] = {}

    def emit(path: tuple[str, ...]) -> None:
        candidate = _make_string(aircraft, path)
        audit = validate_generated_aircraft_string(
            scenario, flight_options, aircraft, candidate, config
        )
        if not audit.valid:
            raise FlightStringGenerationError(
                f"generator emitted illegal string for {aircraft.tail_id!r}: "
                f"path={path}, violations={audit.violations}"
            )
        emitted[_canonical_key(aircraft.tail_id, path)] = candidate

    idle = _make_string(aircraft, ())
    if validate_generated_aircraft_string(
        scenario, flight_options, aircraft, idle, config
    ).valid:
        emit(())

    def dfs(
        path: tuple[str, ...],
        used_options: frozenset[str],
        used_base_flights: frozenset[str],
    ) -> None:
        last_id = path[-1]
        last = options[last_id]
        if last.destination == aircraft.required_station_at_T_end:
            emit(path)
        for next_id in network.successor_option_ids[last_id]:
            if next_id in used_options:
                continue
            next_option = options[next_id]
            base_id = next_option.base_flight_id
            if base_id is not None and base_id in used_base_flights:
                continue
            dfs(
                (*path, next_id),
                used_options | {next_id},
                used_base_flights | ({base_id} if base_id is not None else set()),
            )

    for option_id in network.start_option_ids:
        option = options[option_id]
        base_ids = (
            frozenset({option.base_flight_id})
            if option.base_flight_id is not None
            else frozenset()
        )
        dfs((option_id,), frozenset({option_id}), base_ids)

    return tuple(emitted.values())


def generate_aircraft_strings_with_metrics(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
    config: FlightStringGenerationConfig,
) -> StringGenerationResult:
    """Generate deterministic explicit Aircraft Strings from existing options."""

    started = perf_counter()
    option_ids = tuple(item.option_id for item in flight_options)
    if len(option_ids) != len(set(option_ids)):
        raise FlightStringGenerationError("flight option IDs must be unique")
    aircraft_ids = tuple(item.tail_id for item in scenario.aircraft)
    scoped_ids = set(aircraft_ids if scope is None else scope.aircraft_ids)
    unknown_scope = sorted(scoped_ids - set(aircraft_ids))
    if unknown_scope:
        raise FlightStringGenerationError(
            f"scope contains unknown aircraft IDs: {unknown_scope}"
        )

    original_paths = _original_path_by_aircraft(scenario, flight_options)
    networks: dict[str, AircraftFlightNetwork] = {}
    all_strings: list[AircraftString] = []
    count_by_aircraft: dict[str, int] = {}
    rejected_counts: Counter[str] = Counter()

    for aircraft in scenario.aircraft:
        network = build_aircraft_flight_network(
            scenario, flight_options, aircraft, config
        )
        networks[aircraft.tail_id] = network
        for reasons in network.rejected_option_reasons.values():
            rejected_counts.update(reasons)
        rejected_counts.update(network.rejected_edge_counts)

        if aircraft.tail_id in scoped_ids:
            generated = _enumerate_network_strings(
                scenario, flight_options, aircraft, config, network
            )
            original_path = original_paths[aircraft.tail_id]
            original_key = _canonical_key(aircraft.tail_id, original_path)
            generated_keys = {
                _canonical_key(item.aircraft_id, item.leg_option_ids)
                for item in generated
            }
            original_candidate = _make_string(aircraft, original_path)
            original_audit = validate_generated_aircraft_string(
                scenario,
                flight_options,
                aircraft,
                original_candidate,
                config,
            )
            if original_audit.valid and original_key not in generated_keys:
                raise FlightStringGenerationError(
                    f"legal original string was not enumerated for {aircraft.tail_id!r}"
                )
        else:
            original_candidate = _make_string(
                aircraft, original_paths[aircraft.tail_id]
            )
            audit = validate_generated_aircraft_string(
                scenario, flight_options, aircraft, original_candidate, config
            )
            if not audit.valid:
                raise FlightStringGenerationError(
                    f"out-of-scope original string is illegal for {aircraft.tail_id!r}: "
                    f"{audit.violations}"
                )
            generated = (original_candidate,)

        if not generated:
            raise FlightStringGenerationError(
                f"aircraft {aircraft.tail_id!r} has no legal generated string"
            )
        count_by_aircraft[aircraft.tail_id] = len(generated)
        all_strings.extend(generated)

    keys = [
        _canonical_key(item.aircraft_id, item.leg_option_ids)
        for item in all_strings
    ]
    if len(keys) != len(set(keys)):
        raise FlightStringGenerationError("generated duplicate semantic strings")
    runtime = perf_counter() - started
    metrics: dict[str, object] = {
        "aircraft_count": len(scenario.aircraft),
        "scoped_aircraft_count": len(scoped_ids),
        "flight_option_count": len(flight_options),
        "network_node_count": sum(item.node_count for item in networks.values()),
        "network_edge_count": sum(item.edge_count for item in networks.values()),
        "generated_string_count": len(all_strings),
        "generated_string_count_by_aircraft": count_by_aircraft,
        "rejected_candidate_count_by_reason": dict(sorted(rejected_counts.items())),
        "generation_runtime_seconds": runtime,
        "generation_mode": "explicit_full_enumeration_without_pricing",
    }
    return StringGenerationResult(
        strings=tuple(all_strings),
        networks=networks,
        metrics=metrics,
    )


def generate_aircraft_strings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
    config: FlightStringGenerationConfig,
) -> tuple[AircraftString, ...]:
    return generate_aircraft_strings_with_metrics(
        scenario, flight_options, scope, config
    ).strings


def brute_force_legal_aircraft_strings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    aircraft: Aircraft,
    config: FlightStringGenerationConfig,
    *,
    max_options: int = 8,
) -> tuple[AircraftString, ...]:
    """Independent tiny-case oracle using exhaustive ordered permutations."""

    eligible = tuple(
        item
        for item in flight_options
        if validate_flight_option_for_aircraft(scenario, item, aircraft).eligible
    )
    if len(eligible) > max_options:
        raise FlightStringGenerationError(
            f"brute-force oracle limited to {max_options} eligible options; "
            f"got {len(eligible)}"
        )
    legal: dict[tuple[str, tuple[str, ...]], AircraftString] = {}
    for length in range(len(eligible) + 1):
        for permutation in itertools.permutations(eligible, length):
            candidate = _make_string(
                aircraft, tuple(item.option_id for item in permutation)
            )
            if validate_generated_aircraft_string(
                scenario, flight_options, aircraft, candidate, config
            ).valid:
                legal[
                    _canonical_key(aircraft.tail_id, candidate.leg_option_ids)
                ] = candidate
    return tuple(legal[key] for key in sorted(legal))
