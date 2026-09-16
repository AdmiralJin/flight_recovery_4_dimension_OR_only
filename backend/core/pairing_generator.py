from __future__ import annotations

import hashlib
import itertools
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType

from backend.config.pairing_generation import CrewPairingGenerationConfig
from backend.schemas.columns import (
    CrewDuty,
    CrewPairing,
    CrewSegment,
    CrewSegmentType,
    FlightOperationType,
    FlightOption,
)
from backend.schemas.crew import Crew
from backend.schemas.scenario import Scenario

from .crew_network import (
    CrewFlightNetwork,
    CrewLegKey,
    build_crew_flight_network,
    validate_flight_option_for_crew,
)
from .scope import RecoveryScope, ScopeBuildError, resolve_original_flight_option_ids


class CrewPairingGenerationError(ValueError):
    """Phase 6 cannot produce an auditable crew candidate set."""


@dataclass(frozen=True)
class PairingLegalityResult:
    valid: bool
    violations: tuple[str, ...]


@dataclass(frozen=True)
class PairingGenerationResult:
    pairings: tuple[CrewPairing, ...]
    networks: Mapping[str, CrewFlightNetwork]
    metrics: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "networks", MappingProxyType(dict(self.networks)))
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


def pairing_semantic_key(
    pairing: CrewPairing,
) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (
        pairing.crew_id,
        tuple(
            (segment.segment_type.value, segment.flight_option_id or "")
            for duty in pairing.duties
            for segment in duty.segments
        ),
    )


def crew_pairing_id(crew_id: str, legs: Sequence[CrewLegKey]) -> str:
    """Return the stable Phase 6/10 identifier for a typed crew path."""

    payload = "\x00".join(
        (crew_id, *(f"{leg.segment_type.value}:{leg.flight_option_id}" for leg in legs))
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16].upper()
    safe_crew = "".join(
        character if character.isalnum() else "_" for character in crew_id
    )
    return f"GEN_CP_{safe_crew}_{digest}"


def make_generated_crew_pairing(
    crew: Crew, legs: Sequence[CrewLegKey]
) -> CrewPairing:
    """Build a pairing while preserving the Phase 6 identity contract."""

    pairing_id = crew_pairing_id(crew.crew_id, legs)
    segments = [
        CrewSegment(
            segment_type=leg.segment_type,
            flight_option_id=leg.flight_option_id,
            origin=None,
            destination=None,
            start_time=None,
            end_time=None,
            notes="",
        )
        for leg in legs
    ]
    return CrewPairing(
        pairing_id=pairing_id,
        crew_id=crew.crew_id,
        duties=[CrewDuty(duty_id=f"{pairing_id}_D1", segments=segments)],
        start_station=crew.start_station_at_t,
        end_station=crew.required_station_at_T_end,
        cost_components={},
        notes=(
            "Phase 6 deterministic full explicit enumeration within the v1 "
            "generation profile."
        ),
    )


_pairing_id = crew_pairing_id
_make_pairing = make_generated_crew_pairing


def validate_generated_crew_pairing(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    crew: Crew,
    candidate: CrewPairing,
    config: CrewPairingGenerationConfig,
) -> PairingLegalityResult:
    """Pure full-pairing validator, independent from network path enumeration."""

    violations: list[str] = []
    options = {item.option_id: item for item in flight_options}
    if candidate.crew_id != crew.crew_id:
        violations.append("crew_ownership_mismatch")
    if candidate.start_station != crew.start_station_at_t:
        violations.append("start_station_mismatch")
    if candidate.end_station != crew.required_station_at_T_end:
        violations.append("terminal_station_mismatch")
    if len(candidate.duties) != 1:
        violations.append("unsupported_duty_count")

    segments = tuple(segment for duty in candidate.duties for segment in duty.segments)
    resolved: list[tuple[CrewSegmentType, FlightOption]] = []
    option_ids: list[str] = []
    for segment in segments:
        if segment.segment_type not in {
            CrewSegmentType.OPERATE,
            CrewSegmentType.DEADHEAD,
        }:
            violations.append("unsupported_segment_type")
            continue
        option_id = segment.flight_option_id or ""
        option_ids.append(option_id)
        option = options.get(option_id)
        if option is None:
            violations.append(f"unknown_flight_option:{option_id}")
            continue
        eligibility = validate_flight_option_for_crew(
            scenario, option, crew, segment.segment_type, config
        )
        violations.extend(eligibility.reasons)
        if None not in (
            option.origin,
            option.destination,
            option.dep_time,
            option.arr_time,
        ):
            resolved.append((segment.segment_type, option))

    if len(option_ids) != len(set(option_ids)):
        violations.append("duplicate_flight_option")
    base_ids = [
        option.base_flight_id
        for _, option in resolved
        if option.base_flight_id is not None
    ]
    if len(base_ids) != len(set(base_ids)):
        violations.append("duplicate_base_flight")
    deadhead_count = sum(
        segment.segment_type is CrewSegmentType.DEADHEAD for segment in segments
    )
    if (
        config.max_deadhead_legs is not None
        and deadhead_count > config.max_deadhead_legs
    ):
        violations.append("deadhead_limit_violation")

    if resolved:
        first = resolved[0][1]
        last = resolved[-1][1]
        if first.origin != crew.start_station_at_t:
            violations.append("first_leg_origin_mismatch")
        if last.destination != crew.required_station_at_T_end:
            violations.append("last_leg_terminal_mismatch")
        for (_, left), (_, right) in zip(resolved, resolved[1:]):
            if left.destination != right.origin:
                violations.append("station_discontinuity")
            assert left.arr_time is not None and right.dep_time is not None
            gap = (right.dep_time - left.arr_time).total_seconds() / 60
            if gap < 0:
                violations.append("time_overlap")
            elif gap < config.default_min_connection_minutes:
                violations.append("min_connection_violation")
        assert first.dep_time is not None and last.arr_time is not None
        duty_minutes = (last.arr_time - first.dep_time).total_seconds() / 60
        if duty_minutes > config.max_duty_minutes:
            violations.append("duty_time_violation")
    elif not config.allow_idle:
        violations.append("idle_disabled")
    elif crew.start_station_at_t != crew.required_station_at_T_end:
        violations.append("idle_terminal_mismatch")

    return PairingLegalityResult(
        valid=not violations,
        violations=tuple(dict.fromkeys(violations)),
    )


def _original_legs_by_crew(
    scenario: Scenario, flight_options: Sequence[FlightOption]
) -> Mapping[str, tuple[CrewLegKey, ...]]:
    try:
        originals = resolve_original_flight_option_ids(scenario, flight_options)
    except ScopeBuildError as exc:
        raise CrewPairingGenerationError(
            f"original flight-option resolution failed: {exc}"
        ) from exc
    return MappingProxyType(
        {
            crew.crew_id: tuple(
                CrewLegKey(CrewSegmentType.OPERATE, originals[flight_id])
                for flight_id in crew.original_pairing
            )
            for crew in scenario.crew
        }
    )


def _enumerate_network_pairings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    crew: Crew,
    config: CrewPairingGenerationConfig,
    network: CrewFlightNetwork,
) -> tuple[tuple[CrewPairing, ...], Counter[str]]:
    options = {item.option_id: item for item in flight_options}
    emitted: dict[tuple[str, tuple[tuple[str, str], ...]], CrewPairing] = {}
    pruned: Counter[str] = Counter()

    def emit(path: tuple[CrewLegKey, ...]) -> None:
        candidate = _make_pairing(crew, path)
        audit = validate_generated_crew_pairing(
            scenario, flight_options, crew, candidate, config
        )
        if not audit.valid:
            raise CrewPairingGenerationError(
                f"generator emitted illegal pairing for {crew.crew_id!r}: "
                f"path={path}, violations={audit.violations}"
            )
        emitted[pairing_semantic_key(candidate)] = candidate

    idle = _make_pairing(crew, ())
    if validate_generated_crew_pairing(
        scenario, flight_options, crew, idle, config
    ).valid:
        emit(())

    def dfs(
        path: tuple[CrewLegKey, ...],
        used_options: frozenset[str],
        used_base_flights: frozenset[str],
    ) -> None:
        last_key = path[-1]
        last = options[last_key.flight_option_id]
        if last.destination == crew.required_station_at_T_end:
            emit(path)
        first = options[path[0].flight_option_id]
        assert first.dep_time is not None
        for next_key in network.successor_leg_keys[last_key]:
            if next_key.flight_option_id in used_options:
                pruned["duplicate_flight_option"] += 1
                continue
            next_option = options[next_key.flight_option_id]
            base_id = next_option.base_flight_id
            if base_id is not None and base_id in used_base_flights:
                pruned["duplicate_base_flight"] += 1
                continue
            if (
                config.max_deadhead_legs is not None
                and sum(leg.segment_type is CrewSegmentType.DEADHEAD for leg in path)
                + (next_key.segment_type is CrewSegmentType.DEADHEAD)
                > config.max_deadhead_legs
            ):
                pruned["deadhead_limit_violation"] += 1
                continue
            assert next_option.arr_time is not None
            duty_minutes = (next_option.arr_time - first.dep_time).total_seconds() / 60
            if duty_minutes > config.max_duty_minutes:
                pruned["duty_time_violation"] += 1
                continue
            dfs(
                (*path, next_key),
                used_options | {next_key.flight_option_id},
                used_base_flights | ({base_id} if base_id is not None else set()),
            )

    for key in network.start_leg_keys:
        if (
            config.max_deadhead_legs is not None
            and key.segment_type is CrewSegmentType.DEADHEAD
            and config.max_deadhead_legs == 0
        ):
            pruned["deadhead_limit_violation"] += 1
            continue
        option = options[key.flight_option_id]
        base_ids = (
            frozenset({option.base_flight_id}) if option.base_flight_id else frozenset()
        )
        dfs((key,), frozenset({key.flight_option_id}), base_ids)
    return tuple(emitted[key] for key in sorted(emitted)), pruned


def generate_crew_pairings_with_metrics(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
    config: CrewPairingGenerationConfig,
) -> PairingGenerationResult:
    """Generate deterministic explicit Crew Pairings from existing options."""

    started = perf_counter()
    option_ids = tuple(item.option_id for item in flight_options)
    if len(option_ids) != len(set(option_ids)):
        raise CrewPairingGenerationError("flight option IDs must be unique")
    crew_ids = tuple(item.crew_id for item in scenario.crew)
    scoped_ids = set(crew_ids if scope is None else scope.crew_ids)
    unknown_scope = sorted(scoped_ids - set(crew_ids))
    if unknown_scope:
        raise CrewPairingGenerationError(
            f"scope contains unknown crew IDs: {unknown_scope}"
        )

    originals = _original_legs_by_crew(scenario, flight_options)
    networks: dict[str, CrewFlightNetwork] = {}
    all_pairings: list[CrewPairing] = []
    count_by_crew: dict[str, int] = {}
    rejected_counts: Counter[str] = Counter()
    operate_count = 0
    deadhead_count = 0
    original_status: dict[str, object] = {}

    for crew in scenario.crew:
        network = build_crew_flight_network(scenario, flight_options, crew, config)
        networks[crew.crew_id] = network
        for reasons in network.rejected_leg_reasons.values():
            rejected_counts.update(reasons)
        rejected_counts.update(network.rejected_edge_counts)

        if crew.crew_id in scoped_ids:
            generated, pruned = _enumerate_network_pairings(
                scenario, flight_options, crew, config, network
            )
            rejected_counts.update(pruned)
            original_candidate = _make_pairing(crew, originals[crew.crew_id])
            original_audit = validate_generated_crew_pairing(
                scenario, flight_options, crew, original_candidate, config
            )
            generated_keys = {pairing_semantic_key(item) for item in generated}
            original_status[crew.crew_id] = (
                "legal" if original_audit.valid else list(original_audit.violations)
            )
            if (
                original_audit.valid
                and pairing_semantic_key(original_candidate) not in generated_keys
            ):
                raise CrewPairingGenerationError(
                    f"legal original pairing was not enumerated for {crew.crew_id!r}"
                )
        else:
            original_candidate = _make_pairing(crew, originals[crew.crew_id])
            audit = validate_generated_crew_pairing(
                scenario, flight_options, crew, original_candidate, config
            )
            if not audit.valid:
                raise CrewPairingGenerationError(
                    f"out-of-scope original pairing is illegal for {crew.crew_id!r}: "
                    f"{audit.violations}"
                )
            generated = (original_candidate,)
            original_status[crew.crew_id] = "legal_out_of_scope_retained"

        if not generated:
            raise CrewPairingGenerationError(
                f"crew {crew.crew_id!r} has no legal generated pairing"
            )
        count_by_crew[crew.crew_id] = len(generated)
        for pairing in generated:
            for duty in pairing.duties:
                for segment in duty.segments:
                    if segment.segment_type is CrewSegmentType.OPERATE:
                        operate_count += 1
                    elif segment.segment_type is CrewSegmentType.DEADHEAD:
                        deadhead_count += 1
        all_pairings.extend(generated)

    keys = [pairing_semantic_key(item) for item in all_pairings]
    if len(keys) != len(set(keys)):
        raise CrewPairingGenerationError("generated duplicate semantic pairings")
    metrics: dict[str, object] = {
        "crew_count": len(scenario.crew),
        "scoped_crew_count": len(scoped_ids),
        "flight_option_count": len(flight_options),
        "network_node_count": sum(item.node_count for item in networks.values()),
        "network_edge_count": sum(item.edge_count for item in networks.values()),
        "generated_pairing_count": len(all_pairings),
        "generated_pairing_count_by_crew": count_by_crew,
        "operate_leg_count": operate_count,
        "deadhead_leg_count": deadhead_count,
        "rejected_candidate_count_by_reason": dict(sorted(rejected_counts.items())),
        "original_pairing_status_by_crew": original_status,
        "generation_runtime_seconds": perf_counter() - started,
        "generation_mode": (
            "full_explicit_enumeration_within_phase6_v1_profile_without_pricing"
        ),
    }
    return PairingGenerationResult(
        pairings=tuple(all_pairings), networks=networks, metrics=metrics
    )


def generate_crew_pairings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
    config: CrewPairingGenerationConfig,
) -> tuple[CrewPairing, ...]:
    return generate_crew_pairings_with_metrics(
        scenario, flight_options, scope, config
    ).pairings


def brute_force_legal_crew_pairings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    crew: Crew,
    config: CrewPairingGenerationConfig,
    *,
    max_options: int = 6,
) -> tuple[CrewPairing, ...]:
    """Independent tiny-case oracle over option permutations and leg roles."""

    eligible_options = tuple(
        item
        for item in flight_options
        if item.operation_type is FlightOperationType.OPERATE
        and any(
            validate_flight_option_for_crew(
                scenario, item, crew, segment_type, config
            ).eligible
            for segment_type in (CrewSegmentType.OPERATE, CrewSegmentType.DEADHEAD)
        )
    )
    if len(eligible_options) > max_options:
        raise CrewPairingGenerationError(
            f"brute-force oracle limited to {max_options} eligible options; "
            f"got {len(eligible_options)}"
        )
    legal: dict[tuple[str, tuple[tuple[str, str], ...]], CrewPairing] = {}
    roles = (CrewSegmentType.OPERATE, CrewSegmentType.DEADHEAD)
    for length in range(len(eligible_options) + 1):
        for permutation in itertools.permutations(eligible_options, length):
            for role_assignment in itertools.product(roles, repeat=length):
                legs = tuple(
                    CrewLegKey(role, option.option_id)
                    for role, option in zip(role_assignment, permutation)
                )
                candidate = _make_pairing(crew, legs)
                if validate_generated_crew_pairing(
                    scenario, flight_options, crew, candidate, config
                ).valid:
                    legal[pairing_semantic_key(candidate)] = candidate
    return tuple(legal[key] for key in sorted(legal))
