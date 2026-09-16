from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.schemas.columns import AircraftString, CrewPairing

from .crew_network import CrewLegKey
from .pairing_generator import pairing_semantic_key
from .string_generator import aircraft_string_semantic_key


AircraftStringKey = tuple[str, tuple[str, ...]]
CrewTypedLeg = tuple[str, str]
CrewFollowOn = tuple[CrewTypedLeg, CrewTypedLeg]
CrewPairingKey = tuple[str, tuple[CrewTypedLeg, ...]]


class BranchRestrictionError(ValueError):
    """A branch restriction is contradictory or malformed."""


def _frozen_string_sets(
    values: Mapping[str, Sequence[str]],
) -> Mapping[str, frozenset[str]]:
    return MappingProxyType(
        {owner: frozenset(items) for owner, items in sorted(values.items()) if items}
    )


def _frozen_follow_on_sets(
    values: Mapping[str, Sequence[CrewFollowOn]],
) -> Mapping[str, frozenset[CrewFollowOn]]:
    return MappingProxyType(
        {owner: frozenset(items) for owner, items in sorted(values.items()) if items}
    )


def _frozen_typed_leg_sets(
    values: Mapping[str, Sequence[CrewTypedLeg]],
) -> Mapping[str, frozenset[CrewTypedLeg]]:
    return MappingProxyType(
        {owner: frozenset(items) for owner, items in sorted(values.items()) if items}
    )


@dataclass(frozen=True)
class AircraftBranchRestrictions:
    required_options_by_aircraft: Mapping[str, Sequence[str]] = field(
        default_factory=dict
    )
    forbidden_options_by_aircraft: Mapping[str, Sequence[str]] = field(
        default_factory=dict
    )
    forced_string_key_by_aircraft: Mapping[str, AircraftStringKey] = field(
        default_factory=dict
    )
    forbidden_string_keys: frozenset[AircraftStringKey] = frozenset()

    def __post_init__(self) -> None:
        required = _frozen_string_sets(self.required_options_by_aircraft)
        forbidden = _frozen_string_sets(self.forbidden_options_by_aircraft)
        forced = MappingProxyType(
            dict(sorted(self.forced_string_key_by_aircraft.items()))
        )
        forbidden_keys = frozenset(self.forbidden_string_keys)
        for owner in set(required) | set(forbidden):
            overlap = required.get(owner, frozenset()) & forbidden.get(
                owner, frozenset()
            )
            if overlap:
                raise BranchRestrictionError(
                    f"aircraft {owner!r} options are both required and forbidden: "
                    f"{sorted(overlap)}"
                )
        for owner, key in forced.items():
            if key[0] != owner:
                raise BranchRestrictionError(
                    f"forced string owner mismatch: {owner!r} != {key[0]!r}"
                )
            if key in forbidden_keys:
                raise BranchRestrictionError(
                    f"forced string is also forbidden for aircraft {owner!r}"
                )
            path = set(key[1])
            if not required.get(owner, frozenset()).issubset(path):
                raise BranchRestrictionError(
                    f"forced string omits a required option for aircraft {owner!r}"
                )
            if forbidden.get(owner, frozenset()) & path:
                raise BranchRestrictionError(
                    f"forced string contains a forbidden option for aircraft {owner!r}"
                )
        object.__setattr__(self, "required_options_by_aircraft", required)
        object.__setattr__(self, "forbidden_options_by_aircraft", forbidden)
        object.__setattr__(self, "forced_string_key_by_aircraft", forced)
        object.__setattr__(self, "forbidden_string_keys", forbidden_keys)

    def allows_key(self, key: AircraftStringKey) -> bool:
        owner, path = key
        path_set = set(path)
        if not self.required_options_by_aircraft.get(owner, frozenset()).issubset(
            path_set
        ):
            return False
        if self.forbidden_options_by_aircraft.get(owner, frozenset()) & path_set:
            return False
        forced = self.forced_string_key_by_aircraft.get(owner)
        return (
            forced is None or forced == key
        ) and key not in self.forbidden_string_keys

    def allows(self, item: AircraftString) -> bool:
        return self.allows_key(
            aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
        )


@dataclass(frozen=True)
class CrewBranchRestrictions:
    required_follow_ons_by_crew: Mapping[str, Sequence[CrewFollowOn]] = field(
        default_factory=dict
    )
    forbidden_follow_ons_by_crew: Mapping[str, Sequence[CrewFollowOn]] = field(
        default_factory=dict
    )
    required_typed_legs_by_crew: Mapping[str, Sequence[CrewTypedLeg]] = field(
        default_factory=dict
    )
    forbidden_typed_legs_by_crew: Mapping[str, Sequence[CrewTypedLeg]] = field(
        default_factory=dict
    )
    forced_pairing_key_by_crew: Mapping[str, CrewPairingKey] = field(
        default_factory=dict
    )
    forbidden_pairing_keys: frozenset[CrewPairingKey] = frozenset()

    def __post_init__(self) -> None:
        required_follow = _frozen_follow_on_sets(self.required_follow_ons_by_crew)
        forbidden_follow = _frozen_follow_on_sets(self.forbidden_follow_ons_by_crew)
        required_legs = _frozen_typed_leg_sets(self.required_typed_legs_by_crew)
        forbidden_legs = _frozen_typed_leg_sets(self.forbidden_typed_legs_by_crew)
        forced = MappingProxyType(dict(sorted(self.forced_pairing_key_by_crew.items())))
        forbidden_keys = frozenset(self.forbidden_pairing_keys)
        for owner in set(required_follow) | set(forbidden_follow):
            overlap = required_follow.get(owner, frozenset()) & forbidden_follow.get(
                owner, frozenset()
            )
            if overlap:
                raise BranchRestrictionError(
                    f"crew {owner!r} follow-ons are both required and forbidden"
                )
        for owner in set(required_legs) | set(forbidden_legs):
            overlap = required_legs.get(owner, frozenset()) & forbidden_legs.get(
                owner, frozenset()
            )
            if overlap:
                raise BranchRestrictionError(
                    f"crew {owner!r} typed legs are both required and forbidden"
                )
        for owner, key in forced.items():
            if key[0] != owner:
                raise BranchRestrictionError(
                    f"forced pairing owner mismatch: {owner!r} != {key[0]!r}"
                )
            legs = set(key[1])
            follow_ons = set(zip(key[1], key[1][1:]))
            violates = (
                key in forbidden_keys
                or not required_legs.get(owner, frozenset()).issubset(legs)
                or bool(forbidden_legs.get(owner, frozenset()) & legs)
                or not required_follow.get(owner, frozenset()).issubset(follow_ons)
                or bool(forbidden_follow.get(owner, frozenset()) & follow_ons)
            )
            if violates:
                raise BranchRestrictionError(
                    f"forced pairing violates another restriction for crew {owner!r}"
                )
        object.__setattr__(self, "required_follow_ons_by_crew", required_follow)
        object.__setattr__(self, "forbidden_follow_ons_by_crew", forbidden_follow)
        object.__setattr__(self, "required_typed_legs_by_crew", required_legs)
        object.__setattr__(self, "forbidden_typed_legs_by_crew", forbidden_legs)
        object.__setattr__(self, "forced_pairing_key_by_crew", forced)
        object.__setattr__(self, "forbidden_pairing_keys", forbidden_keys)

    def allows_key_without_force(self, key: CrewPairingKey) -> bool:
        owner, path = key
        legs = set(path)
        follow_ons = set(zip(path, path[1:]))
        if not self.required_typed_legs_by_crew.get(owner, frozenset()).issubset(legs):
            return False
        if self.forbidden_typed_legs_by_crew.get(owner, frozenset()) & legs:
            return False
        if not self.required_follow_ons_by_crew.get(owner, frozenset()).issubset(
            follow_ons
        ):
            return False
        if self.forbidden_follow_ons_by_crew.get(owner, frozenset()) & follow_ons:
            return False
        return key not in self.forbidden_pairing_keys

    def allows_key(self, key: CrewPairingKey) -> bool:
        if not self.allows_key_without_force(key):
            return False
        forced = self.forced_pairing_key_by_crew.get(key[0])
        return forced is None or forced == key

    def allows(self, item: CrewPairing) -> bool:
        return self.allows_key(pairing_semantic_key(item))


def crew_leg_semantic_key(item: CrewLegKey) -> CrewTypedLeg:
    return item.segment_type.value, item.flight_option_id


def crew_path_semantic_key(crew_id: str, path: Sequence[CrewLegKey]) -> CrewPairingKey:
    return crew_id, tuple(crew_leg_semantic_key(item) for item in path)


def branch_restriction_fingerprint(
    restrictions: AircraftBranchRestrictions | CrewBranchRestrictions | None,
) -> str:
    if restrictions is None:
        payload: dict[str, object] = {"kind": "root"}
    elif isinstance(restrictions, AircraftBranchRestrictions):
        payload = {
            "kind": "aircraft",
            "required": {
                key: sorted(value)
                for key, value in restrictions.required_options_by_aircraft.items()
            },
            "forbidden": {
                key: sorted(value)
                for key, value in restrictions.forbidden_options_by_aircraft.items()
            },
            "forced": dict(restrictions.forced_string_key_by_aircraft),
            "forbidden_keys": sorted(restrictions.forbidden_string_keys),
        }
    else:
        payload = {
            "kind": "crew",
            "required_follow_ons": {
                key: sorted(value)
                for key, value in restrictions.required_follow_ons_by_crew.items()
            },
            "forbidden_follow_ons": {
                key: sorted(value)
                for key, value in restrictions.forbidden_follow_ons_by_crew.items()
            },
            "required_typed_legs": {
                key: sorted(value)
                for key, value in restrictions.required_typed_legs_by_crew.items()
            },
            "forbidden_typed_legs": {
                key: sorted(value)
                for key, value in restrictions.forbidden_typed_legs_by_crew.items()
            },
            "forced": dict(restrictions.forced_pairing_key_by_crew),
            "forbidden_keys": sorted(restrictions.forbidden_pairing_keys),
        }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
