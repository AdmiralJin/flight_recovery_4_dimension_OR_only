"""Frozen public research models. Raw inputs are retained outside AIR schemas."""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import timedelta
from typing import Any, Literal

from pydantic import Field, model_validator

from backend.application.solve_service import PROFILE_FILES
from backend.config import FixedColumnCostConfig, PassengerCapacityProfile
from backend.schemas.common import SchemaModel
from backend.schemas.columns import FlightOption, RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.services.validator import validate_scenario

from .common import BASELINE, CONVERTER, ROOT, clean, digest, read_json


class PublicSolveRequest(SchemaModel):
    schema_version: Literal["public-benchmark-1.0"] = "public-benchmark-1.0"
    instance_id: str
    model_type: Literal["aircraft", "aircraft_passenger"]
    components: dict[str, bool]
    source: dict[str, Any]
    scenario: Scenario
    recovery_columns: RecoveryColumns
    capacity_profile: PassengerCapacityProfile
    costs: FixedColumnCostConfig
    configs: dict[str, dict[str, Any]]
    candidate_policy: dict[str, Any]
    fixed_context: dict[str, Any]
    rule_mapping: list[dict[str, Any]]
    precheck_issues: list[dict[str, Any]] = Field(default_factory=list)
    algorithm: Literal["air_bp", "air_cg", "fixed_benders", "integrated_oracle",
                       "xma_joint_arc_flow", "xma_joint_path_oracle", "xma_benders_joint",
                       "xma_benders_cg_bp"] = "air_bp"
    backend: Literal["highs", "gurobi"] = "highs"
    problem_sha256: str

    def problem_payload(self):
        return self.model_dump(mode="json", exclude={"problem_sha256", "algorithm", "backend"})

    @model_validator(mode="after")
    def enforce_contract(self):
        if self.components != dict(aircraft=True, passenger=self.model_type == "aircraft_passenger", crew=False):
            raise ValueError("enabled components must match the explicit public research model")
        if self.scenario.crew_enabled or self.scenario.crew or self.recovery_columns.crew_pairings:
            raise ValueError("public models explicitly disable CRM and contain no crew")
        if self.model_type == "aircraft" and self.scenario.passengers:
            raise ValueError("aircraft profile cannot silently include passenger optimization")
        if digest(self.problem_payload()) != self.problem_sha256:
            raise ValueError("public problem fingerprint mismatch; regenerate the instance")
        return self


def algorithm_configs(turns):
    result = {}
    for key, (filename, loader) in PROFILE_FILES.items():
        config = loader(ROOT / "data/config" / filename).model_dump(mode="json")
        config["profile_id"] = f"public_v3_{key}_v1"
        config["source"] = "implementation_assumption"
        result[key] = config
    result["flight_string_generation"].update(default_min_turn_minutes=0, equipment_overrides=turns)
    for key, filename in [("fixed_benders", "phase8_test_benders_v1.json"),
                          ("itinerary_generation", "phase7_test_itinerary_generation_v1.json")]:
        matches = list((ROOT / "data/config").glob(filename))
        if not matches:
            matches = list((ROOT / "data/config").glob("phase8*" if key == "fixed_benders" else "phase7*"))
        value = read_json(matches[0])
        value["profile_id"] = f"public_v3_{key}_v1"
        value["source"] = "implementation_assumption"
        result[key] = value
    result["fixed_benders"]["enable_crm"] = True  # Explicitly empty CRM has zero recourse.
    return result


def build(raw, *, target=12, seed=0, step=30, max_delay=120, model_type="aircraft", tails=None, capability_filter=False):
    if step not in (15, 30, 60) or max_delay < 0:
        raise ValueError("supported grids: 15, 30, 60 minutes; max_delay must be nonnegative")
    start, end = raw["start"], raw["end"]
    within = [f for f in raw["flights"] if start <= f["dep"] < f["arr"] <= end
              and f["tail"] in raw["planes"] and not f["tail"].startswith("TranspCom")]
    by_tail = defaultdict(list)
    for f in within:
        by_tail[f["tail"]].append(f)
    eligible_tails = sorted(by_tail)
    excluded_tails = []
    if capability_filter:
        excluded_tails = [t for t in eligible_tails if raw["planes"][t]["maintenance"] != "NULL" or any(
            u["tail"] == t and u["event"]["SCHEDULED_DEPARTURE_DATETIME_UTC"] < end
            for u in raw.get("unsupported", []))]
        eligible_tails = [t for t in eligible_tails if t not in excluded_tails]
    # Selection is deterministic and independent of solver outcomes. Micro cases
    # include a complete tail rotation within the 12h window, never random legs.
    random.Random(seed).shuffle(eligible_tails)
    eligible_tails.sort(key=lambda t: not any(f["delay"] != 0 or f.get("cancel_required") for f in by_tail[t]))
    if tails is None:
        tails, size = [], 0
        for tail in eligible_tails:
            if size >= target:
                break
            if target <= 12 and (len(by_tail[tail]) > 12 or size + len(by_tail[tail]) > 12):
                continue
            tails.append(tail)
            size += len(by_tail[tail])
    unknown = set(tails) - set(by_tail)
    if unknown:
        raise ValueError(f"selected tails absent in window: {sorted(unknown)}")
    selected = sorted((f for tail in tails for f in by_tail[tail]), key=lambda f: (f["dep"], f["id"]))
    selected_ids = {f["id"] for f in selected}
    if not selected:
        raise ValueError("no adjustable flights in requested window")
    issues = []
    aircraft, flights, options, seats, turns = [], [], [], {}, {}
    # Equipment identity includes published seat configuration and turn time, so
    # every allowed swap has the same physical capacity and turn-time boundary.
    for tail in sorted(tails):
        spec = raw["planes"][tail]
        rotation = sorted(by_tail[tail], key=lambda f: (f["dep"], f["id"]))
        equipment = spec["type"] + ":" + "/".join(map(str, spec["seats"])) + f":T{spec['turn']}"
        turns[equipment] = spec["turn"]
        prefix = [f for f in raw["flights"] if f["tail"] == tail and f["dep"] < start]
        suffix = [f for f in raw["flights"] if f["tail"] == tail and f["id"] not in selected_ids and f["dep"] >= start]
        ready = max([start] + [f["arr"]+timedelta(minutes=spec["turn"]+f.get("context_arrival_delay", max(0, f["delay"])))
                              for f in prefix if not f.get("cancel_required")])
        limit = min([end] + [f["dep"]-timedelta(minutes=spec["turn"]) for f in suffix if f["dep"] >= rotation[-1]["arr"]])
        active_prefix = sorted((f for f in prefix if not f.get("cancel_required")), key=lambda f: f["dep"])
        next_suffix = min(suffix, key=lambda f: f["dep"]) if suffix else None
        aircraft.append({"tail_id": tail, "equipment_type": equipment,
                         "initial_station_at_t": active_prefix[-1]["destination"] if active_prefix else spec.get("initial", rotation[0]["origin"]),
                         "required_station_at_T_end": next_suffix["origin"] if next_suffix else rotation[-1]["destination"],
                         "original_rotation": [f["id"] for f in rotation],
                         "ready_at": ready, "available_until": limit,
                         "unavailable": [{"start": u["start"], "end": u["end"]}
                                         for u in raw["unavailable"] if u["tail"] == tail]})
        if spec["maintenance"] != "NULL":
            issues.append({"code": "unsupported_maintenance", "tail": tail, "raw": spec["maintenance"]})
        for event in raw.get("unsupported", []):
            ev = event["event"]
            if event["tail"] == tail and ev["SCHEDULED_DEPARTURE_DATETIME_UTC"] < end:
                issues.append({"code": event["reason"], "source": event})
        for f in rotation:
            duration = (f["arr"]-f["dep"]).total_seconds()/60
            if duration <= 0 or not duration.is_integer():
                issues.append({"code": "non_positive_or_fractional_block_time", "flight": f["id"]})
                continue
            flights.append({"flight_id": f["id"], "origin": f["origin"], "destination": f["destination"],
                            "sched_dep": f["dep"], "sched_arr": f["arr"], "duration": int(duration),
                            "original_aircraft": tail, "original_equipment": equipment,
                            "original_crew": None, "max_delay": max_delay,
                            "strategic_flag": f.get("fixed_delay") is not None,
                            "fixed_delay": f.get("fixed_delay"), "cancel_required": f.get("cancel_required", False),
                            "earliest_departure": f["dep"]+timedelta(minutes=max(0, f["delay"]))})
            if f.get("fixed_delay") is not None and f["delay"] > max_delay:
                issues.append({"code": "source_disruption_exceeds_frozen_delay_domain", "flight": f["id"], "delay": f["delay"]})
            delays = set(range(0, max_delay+1, step)) | {max_delay}
            if 0 <= f["delay"] <= max_delay:
                delays.add(f["delay"])
            # Add source disruption boundaries to every nested grid.
            for u in raw["unavailable"]:
                if u["tail"] in tails:
                    for at in (u["start"]-timedelta(minutes=int(duration)), u["end"]):
                        d = (at-f["dep"]).total_seconds()/60
                        if d.is_integer() and 0 <= d <= max_delay:
                            delays.add(int(d))
            for delay in sorted(delays):
                if f["arr"]+timedelta(minutes=delay) > end:
                    continue
                oid = f"{f['id']}:D{delay}"
                options.append(dict(option_id=oid, base_flight_id=f["id"], operation_type="operate",
                                    change_types=["unchanged" if delay == 0 else "delay"], origin=f["origin"],
                                    destination=f["destination"], dep_time=f["dep"]+timedelta(minutes=delay),
                                    arr_time=f["arr"]+timedelta(minutes=delay), block_minutes=int(duration),
                                    departure_delay_minutes=delay, arrival_delay_minutes=delay))
                seats[oid] = sum(spec["seats"])
            options.append(dict(option_id=f"{f['id']}:C", base_flight_id=f["id"], operation_type="cancel",
                                change_types=["cancel"], origin=None, destination=None, dep_time=None,
                                arr_time=None, block_minutes=None, departure_delay_minutes=None, arrival_delay_minutes=None))
    passengers, excluded_journeys = [], []
    lookup = {f["id"]: f for f in selected}
    for journey in raw["journeys"]:
        if model_type != "aircraft_passenger" or journey["missing"] or not set(journey["legs"]).issubset(selected_ids):
            excluded_journeys.append(journey)
            continue
        if not journey["legs"] or journey["count"] <= 0:
            excluded_journeys.append(journey)
            continue
        first, last = lookup[journey["legs"][0]], lookup[journey["legs"][-1]]
        passengers.append(dict(pax_group_id=journey["id"], count=journey["count"], origin=first["origin"],
                               destination=last["destination"], original_departure=first["dep"],
                               scheduled_arrival=last["arr"], original_itinerary=journey["legs"]))
    if model_type == "aircraft_passenger" and raw["source"] != "roadef2009":
        raise ValueError("Delft marginal connection statistics do not identify full itineraries")
    instance_id = f"{raw['source']}-{str(raw['source_instance']).replace(':','').replace('+','_')}-n{target}-s{seed}-g{step}-{model_type}"
    scenario, validation = validate_scenario(clean(dict(scenario_id=instance_id,
        recovery_window=dict(start_time=start, end_time=end), crew_enabled=False,
        airports=[dict(airport_id=a, name=a) for a in sorted({f[k] for f in raw["flights"] for k in ("origin", "destination")})],
        flights=flights, aircraft=aircraft, crew=[], passengers=passengers,
        airport_intervals=[dict(airport=a, start_time=start, end_time=end,
                               arr_capacity=len(flights), dep_capacity=len(flights), gate_capacity=len(aircraft))
                           for a in sorted({f[k] for f in raw["flights"] for k in ("origin", "destination")})])))
    if validation:
        raise ValueError("public scenario validation: " + str(validation))
    configs = algorithm_configs(turns)
    costs = read_json(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs["cost_profile_id"] = "public_air_linear_v1"
    columns = RecoveryColumns(schema_version="1.0.0", scenario_id=instance_id, time_unit="minute", flight_options=options,
                              aircraft_strings=[], crew_pairings=[], passenger_itineraries=[])
    if passengers:
        from backend.config import PassengerItineraryGenerationConfig
        from backend.core import generate_passenger_itineraries
        columns = columns.model_copy(update={"passenger_itineraries": list(generate_passenger_itineraries(
            scenario, columns.flight_options, None,
            PassengerItineraryGenerationConfig.model_validate(configs["itinerary_generation"])))})
    mappings = [
        {"rule": "crew", "research": "disabled; no synthetic data", "original": "not_applicable"},
        {"rule": "terminal", "research": "hard per-tail fixed-prefix position and fixed-suffix origin, otherwise last in-window destination", "original": "different_from_ROADEF_type_position_soft_penalty"},
        {"rule": "fleet_scope", "research": "selected active tails only; no inactive spare tails", "original": "raw full fleet retained; not the unrestricted original fleet model"},
        {"rule": "capacity", "research": "single cabin; swaps restricted to identical published seat configuration", "original": "no_cabin_split_or_downgrade"},
        {"rule": "airport_capacity", "research": "not_enforced_in_aircraft_submodel_v1", "original": "retained_raw; external_gate_required"},
        {"rule": "ground_transport_and_linked_flights", "research": "retained_raw_not_modeled", "original": "external_gate_required"},
        {"rule": "objective", "research": "public_air_linear_v1_abstract_units", "original": "not_comparable_to_ROADEF_cost"},
        {"rule": "passenger_scope", "research": "whole source groups fully inside selected flights only", "original": "outside_groups_retained_in_fixed_context"},
    ]
    data = dict(schema_version="public-benchmark-1.0", instance_id=instance_id, model_type=model_type,
                components=dict(aircraft=True, passenger=model_type == "aircraft_passenger", crew=False),
                source={"dataset": raw["source"], "source_instance": raw["source_instance"],
                        "converter": CONVERTER, "baseline": BASELINE, "files": raw["source_files"],
                        "reference_kind": raw["reference_kind"], "original_rules_eligible": False,
                        "delay_semantics": raw.get("delay_semantics", "source_alt_flight_fixed_delay_tail_or_required_cancellation"),
                        "records": selected, "raw_tables": raw["raw_tables"]},
                scenario=scenario, recovery_columns=columns,
                capacity_profile=dict(schema_version="1.0.0", capacity_profile_id=f"{instance_id}:seats",
                                      scenario_id=instance_id, source="implementation_assumption", units="seats",
                                      seat_capacity_by_option_id=seats,
                                      notes=["Published physical seats under identical-capacity swap restriction."]),
                costs=costs, configs=configs,
                candidate_policy=dict(step_minutes=step, max_delay_minutes=max_delay, selection_seed=seed,
                                      target_flights=target, actual_flights=len(flights), selected_tails=sorted(tails),
                                      capability_filter=capability_filter, excluded_unsupported_tails=excluded_tails,
                                      closure="complete selected-tail in-window rotations", implicit_paths=True),
                fixed_context={"flights": [f for f in raw["flights"] if f["id"] not in selected_ids],
                               "excluded_journeys": excluded_journeys, "window_hours": (end-start).total_seconds()/3600},
                rule_mapping=mappings, precheck_issues=issues)
    data = clean(data)
    # Materialize defaults before hashing; Pydantic's normalized object is the
    # authoritative input snapshot (not the original Python argument syntax).
    fields = {k: v for k, v in data.items()}
    for key, cls in [("scenario", Scenario), ("recovery_columns", RecoveryColumns),
                     ("capacity_profile", PassengerCapacityProfile), ("costs", FixedColumnCostConfig)]:
        fields[key] = cls.model_validate(fields[key]).model_dump(mode="json")
    fields.update(algorithm="air_bp", backend="highs", problem_sha256="")
    payload = {k: v for k, v in fields.items() if k not in ("algorithm", "backend", "problem_sha256")}
    fields["problem_sha256"] = digest(payload)
    return PublicSolveRequest.model_validate(fields)
