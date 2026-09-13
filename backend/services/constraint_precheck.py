from __future__ import annotations

from collections import Counter
from enum import Enum
from typing import Any

from pydantic import ValidationError

from backend.config import PassengerCapacityProfile, validate_passenger_capacity_profile
from backend.core import arm, crm, prm, srm
from backend.core.constraint_registry import list_constraint_metadata
from backend.core.gate_inventory import build_gate_inventory_data
from backend.schemas.columns import (
    FlightOperationType,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


class PrecheckStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


def _result(
    constraint_id: str,
    status: PrecheckStatus,
    summary: str,
    *,
    issues: list[str] | None = None,
    derived_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "constraint_id": constraint_id,
        "status": status.value,
        "summary": summary,
        "issues": issues or [],
        "derived_values": derived_values or {},
    }


def _no_columns(constraint_id: str, scenario_summary: dict[str, Any]):
    return _result(
        constraint_id,
        PrecheckStatus.WARNING,
        "Recovery Columns were not supplied; structural precheck is incomplete.",
        derived_values=scenario_summary,
    )


def precheck_constraints(
    scenario_data: Any,
    columns_data: Any | None = None,
    capacity_data: Any | None = None,
) -> dict[str, Any]:
    """Run deterministic input checks only; never build or solve a MIP."""

    metadata = list_constraint_metadata()
    scenario, scenario_issues = validate_scenario(scenario_data)
    if scenario is None or scenario_issues:
        messages = [
            f"{issue.code}@{issue.location}: {issue.message}"
            for issue in scenario_issues
        ]
        results = [
            _result(
                item.constraint_id,
                PrecheckStatus.FAILED,
                "Scenario validation failed before constraint precheck.",
                issues=messages,
            )
            for item in metadata
        ]
        return {
            "precheck_semantics": "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY",
            "overall_status": PrecheckStatus.FAILED.value,
            "results": results,
        }

    scenario_summary = {
        "scenario_id": scenario.scenario_id,
        "flights": len(scenario.flights),
        "strategic_flights": sum(item.strategic_flag for item in scenario.flights),
        "market_flights": sum(item.market_flag for item in scenario.flights),
        "aircraft": len(scenario.aircraft),
        "crew": len(scenario.crew),
        "passenger_groups": len(scenario.passengers),
        "airport_intervals": len(scenario.airport_intervals),
    }
    if columns_data is None:
        results = [
            _no_columns(item.constraint_id, scenario_summary) for item in metadata
        ]
        return {
            "precheck_semantics": "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY",
            "overall_status": PrecheckStatus.WARNING.value,
            "results": results,
        }

    try:
        parsed_columns = RecoveryColumns.model_validate(columns_data)
    except ValidationError as exc:
        messages = [
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors(include_url=False, include_input=False)
        ]
        results = [
            _result(
                item.constraint_id,
                PrecheckStatus.FAILED,
                "Recovery Columns schema validation failed.",
                issues=messages,
                derived_values=scenario_summary,
            )
            for item in metadata
        ]
        return {
            "precheck_semantics": "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY",
            "overall_status": PrecheckStatus.FAILED.value,
            "results": results,
        }

    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    assert columns is not None
    column_issue_messages = [
        f"{issue.code}@{issue.location}: {issue.message}" for issue in column_issues
    ]
    options_by_flight: dict[str, list[Any]] = {
        flight.flight_id: [] for flight in scenario.flights
    }
    for option in parsed_columns.flight_options:
        if option.base_flight_id in options_by_flight:
            options_by_flight[option.base_flight_id].append(option)

    missing_options = [
        flight_id for flight_id, options in options_by_flight.items() if not options
    ]
    results_by_id: dict[str, dict[str, Any]] = {}
    results_by_id[srm.SRM_C01_FLIGHT_COVERAGE] = _result(
        srm.SRM_C01_FLIGHT_COVERAGE,
        PrecheckStatus.FAILED if missing_options else PrecheckStatus.PASSED,
        (
            "Every flight has at least one explicit option."
            if not missing_options
            else "Some flights have no explicit operate/cancel option."
        ),
        issues=[f"missing options for {item}" for item in missing_options],
        derived_values={
            "flight_count": len(scenario.flights),
            "option_count": len(parsed_columns.flight_options),
            "missing_flight_option_count": len(missing_options),
        },
    )

    strategic_missing = [
        flight.flight_id
        for flight in scenario.flights
        if flight.strategic_flag
        and not any(
            option.operation_type is FlightOperationType.OPERATE
            for option in options_by_flight[flight.flight_id]
        )
    ]
    results_by_id[srm.SRM_C02_STRATEGIC_FLIGHT] = _result(
        srm.SRM_C02_STRATEGIC_FLIGHT,
        PrecheckStatus.FAILED if strategic_missing else PrecheckStatus.PASSED,
        "Strategic flights have operate candidates." if not strategic_missing else "Strategic flights are missing operate candidates.",
        issues=[f"no operate candidate for {item}" for item in strategic_missing],
        derived_values={
            "strategic_flight_count": scenario_summary["strategic_flights"],
            "missing_operate_candidate_count": len(strategic_missing),
        },
    )

    operated = [
        item
        for item in parsed_columns.flight_options
        if item.operation_type is FlightOperationType.OPERATE
    ]
    arrival_memberships = sum(
        interval.start_time <= option.arr_time < interval.end_time
        and interval.airport == option.destination
        for interval in scenario.airport_intervals
        for option in operated
        if option.arr_time is not None
    )
    departure_memberships = sum(
        interval.start_time <= option.dep_time < interval.end_time
        and interval.airport == option.origin
        for interval in scenario.airport_intervals
        for option in operated
        if option.dep_time is not None
    )
    results_by_id[srm.SRM_C03_ARRIVAL_CAPACITY] = _result(
        srm.SRM_C03_ARRIVAL_CAPACITY,
        PrecheckStatus.PASSED,
        "Arrival-capacity buckets and option memberships were derived.",
        derived_values={
            "airport_interval_count": len(scenario.airport_intervals),
            "arrival_option_memberships": arrival_memberships,
        },
    )
    results_by_id[srm.SRM_C04_DEPARTURE_CAPACITY] = _result(
        srm.SRM_C04_DEPARTURE_CAPACITY,
        PrecheckStatus.PASSED,
        "Departure-capacity buckets and option memberships were derived.",
        derived_values={
            "airport_interval_count": len(scenario.airport_intervals),
            "departure_option_memberships": departure_memberships,
        },
    )

    try:
        gate = build_gate_inventory_data(scenario, parsed_columns)
    except ValueError as exc:
        results_by_id[srm.SRM_C05_GATE_INVENTORY] = _result(
            srm.SRM_C05_GATE_INVENTORY,
            PrecheckStatus.WARNING,
            "Provisional gate inventory could not be constructed.",
            issues=[str(exc)],
            derived_values={"mode": srm.GATE_INVENTORY_MODE},
        )
    else:
        results_by_id[srm.SRM_C05_GATE_INVENTORY] = _result(
            srm.SRM_C05_GATE_INVENTORY,
            PrecheckStatus.PASSED,
            "Provisional aggregate gate inventory can be constructed.",
            derived_values={
                "mode": srm.GATE_INVENTORY_MODE,
                "checkpoint_count": len(gate.checkpoints),
            },
        )
    results_by_id[srm.SRM_C06_MARKET_SEAT] = _result(
        srm.SRM_C06_MARKET_SEAT,
        PrecheckStatus.PASSED,
        "Market-service proxy inputs were counted; this is not physical seat capacity.",
        derived_values={
            "mode": srm.MARKET_SEAT_MODE,
            "market_flight_count": scenario_summary["market_flights"],
            "market_min_seats_total": sum(
                item.min_seats for item in scenario.flights if item.market_flag
            ),
        },
    )

    string_counts = Counter(item.aircraft_id for item in parsed_columns.aircraft_strings)
    aircraft_without_strings = [
        item.tail_id for item in scenario.aircraft if not string_counts[item.tail_id]
    ]
    results_by_id[arm.ARM_C01_STRING_SELECTION] = _result(
        arm.ARM_C01_STRING_SELECTION,
        PrecheckStatus.FAILED if aircraft_without_strings else PrecheckStatus.PASSED,
        "Each aircraft has a fixed string candidate." if not aircraft_without_strings else "Some aircraft have no fixed string candidate.",
        issues=[f"no string for {item}" for item in aircraft_without_strings],
        derived_values={
            "aircraft_count": len(scenario.aircraft),
            "aircraft_string_count": len(parsed_columns.aircraft_strings),
        },
    )
    string_option_coverage = Counter(
        option_id
        for string in parsed_columns.aircraft_strings
        for option_id in string.leg_option_ids
    )
    results_by_id[arm.ARM_C02_OPTION_COVERAGE] = _result(
        arm.ARM_C02_OPTION_COVERAGE,
        PrecheckStatus.WARNING,
        "Potential string coverage was counted; exact coverage needs an external schedule request.",
        derived_values={
            "covered_option_count": len(string_option_coverage),
            "max_candidate_string_coverage": max(string_option_coverage.values(), default=0),
        },
    )

    columns_valid = not column_issues
    validation_status = PrecheckStatus.PASSED if columns_valid else PrecheckStatus.FAILED
    validation_summary = (
        "Recovery Columns semantic validation passed."
        if columns_valid
        else "Recovery Columns semantic validation found issues."
    )
    for constraint_id in (
        arm.ARM_C03_TERMINAL_STATION,
        arm.ARM_C04_MAINTENANCE,
        arm.ARM_C05_STRING_FEASIBILITY,
    ):
        results_by_id[constraint_id] = _result(
            constraint_id,
            validation_status,
            validation_summary,
            issues=column_issue_messages,
            derived_values={"semantic_issue_count": len(column_issues)},
        )

    pairing_counts = Counter(item.crew_id for item in parsed_columns.crew_pairings)
    crew_without_pairings = [
        item.crew_id for item in scenario.crew if not pairing_counts[item.crew_id]
    ]
    results_by_id[crm.CRM_C01_PAIRING_SELECTION] = _result(
        crm.CRM_C01_PAIRING_SELECTION,
        PrecheckStatus.FAILED if crew_without_pairings else PrecheckStatus.PASSED,
        "Each crew has a fixed pairing candidate." if not crew_without_pairings else "Some crew have no fixed pairing candidate.",
        issues=[f"no pairing for {item}" for item in crew_without_pairings],
        derived_values={
            "crew_count": len(scenario.crew),
            "crew_pairing_count": len(parsed_columns.crew_pairings),
        },
    )
    operating_coverage = Counter()
    deadhead_coverage = Counter()
    for pairing in parsed_columns.crew_pairings:
        for duty in pairing.duties:
            for segment in duty.segments:
                if segment.flight_option_id is None:
                    continue
                target = (
                    deadhead_coverage
                    if segment.segment_type.value == "deadhead"
                    else operating_coverage
                )
                target[segment.flight_option_id] += 1
    results_by_id[crm.CRM_C02_OPTION_COVERAGE] = _result(
        crm.CRM_C02_OPTION_COVERAGE,
        PrecheckStatus.WARNING,
        "Potential operating coverage was counted; exact coverage needs an external schedule request.",
        derived_values={"covered_operating_option_count": len(operating_coverage)},
    )
    results_by_id[crm.CRM_C03_NONREQUIRED_PROHIBITION] = _result(
        crm.CRM_C03_NONREQUIRED_PROHIBITION,
        PrecheckStatus.WARNING,
        "OPERATE/DEADHEAD incidence is available; schedule leakage needs an external request.",
        derived_values={
            "operating_reference_count": sum(operating_coverage.values()),
            "deadhead_reference_count": sum(deadhead_coverage.values()),
        },
    )
    for constraint_id in (
        crm.CRM_C04_CREW_FEASIBILITY,
        crm.CRM_C05_TERMINAL_OWNERSHIP,
    ):
        results_by_id[constraint_id] = _result(
            constraint_id,
            validation_status,
            validation_summary,
            issues=column_issue_messages,
            derived_values={"semantic_issue_count": len(column_issues)},
        )

    itinerary_counts = Counter(
        item.pax_group_id for item in parsed_columns.passenger_itineraries
    )
    groups_without_itineraries = [
        item.pax_group_id
        for item in scenario.passengers
        if not itinerary_counts[item.pax_group_id]
    ]
    results_by_id[prm.PRM_C01_GROUP_SELECTION] = _result(
        prm.PRM_C01_GROUP_SELECTION,
        PrecheckStatus.FAILED if groups_without_itineraries else PrecheckStatus.PASSED,
        "Each passenger group has a fixed itinerary candidate." if not groups_without_itineraries else "Some passenger groups have no fixed itinerary candidate.",
        issues=[f"no itinerary for {item}" for item in groups_without_itineraries],
        derived_values={
            "passenger_group_count": len(scenario.passengers),
            "passenger_itinerary_count": len(parsed_columns.passenger_itineraries),
        },
    )
    results_by_id[prm.PRM_C02_SCHEDULE_CONSISTENCY] = _result(
        prm.PRM_C02_SCHEDULE_CONSISTENCY,
        PrecheckStatus.WARNING,
        "Itinerary flight references were indexed; eligibility needs an external schedule request.",
        derived_values={
            "transported_itinerary_count": sum(
                item.status.value == "transported"
                for item in parsed_columns.passenger_itineraries
            )
        },
    )

    if capacity_data is None:
        results_by_id[prm.PRM_C03_SEAT_CAPACITY] = _result(
            prm.PRM_C03_SEAT_CAPACITY,
            PrecheckStatus.WARNING,
            "Passenger capacity profile was not supplied.",
            issues=["No seat-capacity input; no infinite capacity was assumed."],
            derived_values={"capacity_profile_present": False},
        )
    else:
        try:
            capacity = PassengerCapacityProfile.model_validate(capacity_data)
            validate_passenger_capacity_profile(capacity, scenario, parsed_columns)
            referenced_options = {
                segment.flight_option_id
                for itinerary in parsed_columns.passenger_itineraries
                for segment in itinerary.segments
                if segment.segment_type is PassengerSegmentType.FLIGHT
            }
            missing_capacity = sorted(
                option_id
                for option_id in referenced_options
                if option_id not in capacity.seat_capacity_by_option_id
            )
        except (ValidationError, ValueError) as exc:
            results_by_id[prm.PRM_C03_SEAT_CAPACITY] = _result(
                prm.PRM_C03_SEAT_CAPACITY,
                PrecheckStatus.FAILED,
                "Passenger capacity profile is invalid for current data.",
                issues=[str(exc)],
                derived_values={"capacity_profile_present": True},
            )
        else:
            results_by_id[prm.PRM_C03_SEAT_CAPACITY] = _result(
                prm.PRM_C03_SEAT_CAPACITY,
                PrecheckStatus.FAILED if missing_capacity else PrecheckStatus.PASSED,
                "Test residual capacity covers referenced passenger options." if not missing_capacity else "Referenced passenger options are missing test residual capacity.",
                issues=[f"missing capacity for {item}" for item in missing_capacity],
                derived_values={
                    "capacity_profile_present": True,
                    "capacity_profile_id": capacity.capacity_profile_id,
                    "capacity_option_count": len(capacity.seat_capacity_by_option_id),
                    "referenced_option_count": len(referenced_options),
                },
            )
    results_by_id[prm.PRM_C04_ITINERARY_FEASIBILITY] = _result(
        prm.PRM_C04_ITINERARY_FEASIBILITY,
        validation_status,
        validation_summary,
        issues=column_issue_messages,
        derived_values={"semantic_issue_count": len(column_issues)},
    )

    results = [results_by_id[item.constraint_id] for item in metadata]
    statuses = {item["status"] for item in results}
    overall = (
        PrecheckStatus.FAILED
        if PrecheckStatus.FAILED.value in statuses
        else PrecheckStatus.WARNING
        if PrecheckStatus.WARNING.value in statuses
        else PrecheckStatus.PASSED
    )
    return {
        "precheck_semantics": "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY",
        "overall_status": overall.value,
        "results": results,
    }
