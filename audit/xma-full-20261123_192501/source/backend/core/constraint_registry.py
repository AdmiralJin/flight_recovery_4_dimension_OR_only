from __future__ import annotations

from enum import Enum
from types import MappingProxyType

from pydantic import ConfigDict, Field

from backend.schemas.common import SchemaModel

from . import arm, crm, prm, srm


class ConstraintKind(str, Enum):
    PAPER_CONSTRAINT = "paper_constraint"
    IMPLEMENTATION_GUARD = "implementation_guard"
    FIXED_COLUMN_VALIDATION = "fixed_column_validation"


class ConstraintProvenance(str, Enum):
    PAPER_DEFINED = "paper_defined"
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    GENERATED_PROVISIONAL = "generated_provisional"
    AIRLINE_EXTENSION = "airline_extension"


class ConstraintImplementationStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PROXY = "proxy"
    DEFERRED = "deferred"


class ConstraintMetadata(SchemaModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(min_length=1)
    model: str = Field(pattern=r"^(SRM|ARM|CRM|PRM)$")
    name: str = Field(min_length=1)
    paper_equation: str | None = None
    kind: ConstraintKind
    provenance: ConstraintProvenance
    implementation_status: ConstraintImplementationStatus
    formula_summary: str = Field(min_length=1)
    input_dependencies: tuple[str, ...]
    related_sections: tuple[str, ...]
    assumption_refs: tuple[str, ...]
    provenance_detail: str = Field(min_length=1)
    notes: str = Field(min_length=1)


def _item(
    constraint_id: str,
    model: str,
    name: str,
    formula: str,
    dependencies: tuple[str, ...],
    sections: tuple[str, ...],
    assumptions: tuple[str, ...],
    notes: str,
    *,
    paper_equation: str | None = None,
    kind: ConstraintKind = ConstraintKind.PAPER_CONSTRAINT,
    provenance: ConstraintProvenance = ConstraintProvenance.PAPER_DEFINED,
    status: ConstraintImplementationStatus = ConstraintImplementationStatus.IMPLEMENTED,
    provenance_detail: str,
) -> ConstraintMetadata:
    return ConstraintMetadata(
        constraint_id=constraint_id,
        model=model,
        name=name,
        paper_equation=paper_equation,
        kind=kind,
        provenance=provenance,
        implementation_status=status,
        formula_summary=formula,
        input_dependencies=dependencies,
        related_sections=sections,
        assumption_refs=assumptions,
        provenance_detail=provenance_detail,
        notes=notes,
    )


_CONSTRAINTS = (
    _item(
        srm.SRM_C01_FLIGHT_COVERAGE, "SRM", "Flight coverage",
        "sum(x[o] for option o of flight f) = 1",
        ("scenario.flights", "recovery_columns.flight_options"), ("flights",), (),
        "Each base flight selects one explicit operate or cancel option.",
        paper_equation="(3.2)", provenance_detail=srm.CONSTRAINT_PROVENANCE[srm.SRM_C01_FLIGHT_COVERAGE],
    ),
    _item(
        srm.SRM_C02_STRATEGIC_FLIGHT, "SRM", "Strategic flight preservation",
        "sum(x[o] for operate option o of strategic flight f) = 1",
        ("scenario.flights.strategic_flag", "recovery_columns.flight_options"), ("flights",), ("A-028",),
        "Strategic is an implementation mapping of the paper constraint.",
        paper_equation="(3.3)", provenance_detail=srm.CONSTRAINT_PROVENANCE[srm.SRM_C02_STRATEGIC_FLIGHT],
    ),
    _item(
        srm.SRM_C03_ARRIVAL_CAPACITY, "SRM", "Arrival capacity",
        "sum(arrival_incidence[k,o] * x[o]) <= ARR_CAP[k]",
        ("scenario.airport_intervals.arr_capacity", "recovery_columns.flight_options.arr_time"), ("airport_intervals", "flights"), ("A-005",),
        "Uses half-open airport time buckets.", paper_equation="(3.4)",
        provenance_detail=srm.CONSTRAINT_PROVENANCE[srm.SRM_C03_ARRIVAL_CAPACITY],
    ),
    _item(
        srm.SRM_C04_DEPARTURE_CAPACITY, "SRM", "Departure capacity",
        "sum(departure_incidence[k,o] * x[o]) <= DEP_CAP[k]",
        ("scenario.airport_intervals.dep_capacity", "recovery_columns.flight_options.dep_time"), ("airport_intervals", "flights"), ("A-005",),
        "Uses half-open airport time buckets.", paper_equation="(3.5)",
        provenance_detail=srm.CONSTRAINT_PROVENANCE[srm.SRM_C04_DEPARTURE_CAPACITY],
    ),
    _item(
        srm.SRM_C05_GATE_INVENTORY, "SRM", "Gate inventory proxy",
        "initial_ground[a] + arrivals[a,t] - departures[a,t] >= 0 and <= GATE_CAP[a,t]",
        ("scenario.aircraft", "scenario.airport_intervals.gate_capacity", "recovery_columns.flight_options"), ("aircraft", "airport_intervals", "flights"), ("A-029", "A-030"),
        "PROXY: aggregate ground inventory, not tail-level gate occupancy; revisit in Phase 3.",
        kind=ConstraintKind.IMPLEMENTATION_GUARD, provenance=ConstraintProvenance.GENERATED_PROVISIONAL,
        status=ConstraintImplementationStatus.PROXY,
        provenance_detail=srm.CONSTRAINT_PROVENANCE[srm.SRM_C05_GATE_INVENTORY],
    ),
    _item(
        srm.SRM_C06_MARKET_SEAT, "SRM", "Market-seat preservation proxy",
        "market_flag[f] and min_seats[f] > 0 implies cancel[f] = 0",
        ("scenario.flights.market_flag", "scenario.flights.min_seats", "recovery_columns.flight_options"), ("flights",), ("A-031",),
        "PROXY: preserves market service; min_seats is not aircraft seat capacity. Revisit in Phase 3.",
        kind=ConstraintKind.IMPLEMENTATION_GUARD, provenance=ConstraintProvenance.GENERATED_PROVISIONAL,
        status=ConstraintImplementationStatus.PROXY,
        provenance_detail=srm.CONSTRAINT_PROVENANCE[srm.SRM_C06_MARKET_SEAT],
    ),
    _item(
        arm.ARM_C01_STRING_SELECTION, "ARM", "Aircraft string selection",
        "sum(y[string] for string owned by aircraft a) = 1",
        ("scenario.aircraft", "recovery_columns.aircraft_strings"), ("aircraft",), ("A-034",),
        "One explicit tail-owned fixed string is selected.", paper_equation="(3.10)",
        provenance_detail=arm.CONSTRAINT_PROVENANCE[arm.ARM_C01_STRING_SELECTION],
    ),
    _item(
        arm.ARM_C02_OPTION_COVERAGE, "ARM", "Required option coverage",
        "required option coverage = 1; non-required revenue option coverage = 0",
        ("aircraft_recovery_request.required_operated_option_ids", "recovery_columns.aircraft_strings"), ("aircraft", "flights"), ("A-035",),
        "The actual code ID combines required coverage and non-required prohibition.", paper_equation="(3.9)",
        provenance_detail=arm.CONSTRAINT_PROVENANCE[arm.ARM_C02_OPTION_COVERAGE],
    ),
    _item(
        arm.ARM_C03_TERMINAL_STATION, "ARM", "Aircraft terminal station",
        "selected string end_station = aircraft required_station_at_T_end",
        ("scenario.aircraft.required_station_at_T_end", "recovery_columns.aircraft_strings.end_station"), ("aircraft",), ("A-036",),
        "Paper prose plus fixed-column terminal mapping.", kind=ConstraintKind.IMPLEMENTATION_GUARD,
        provenance=ConstraintProvenance.IMPLEMENTATION_ASSUMPTION,
        provenance_detail=arm.CONSTRAINT_PROVENANCE[arm.ARM_C03_TERMINAL_STATION],
    ),
    _item(
        arm.ARM_C04_MAINTENANCE, "ARM", "Maintenance satisfaction",
        "maintenance_required[a] implies selected string maintenance_satisfied",
        ("scenario.aircraft.maintenance_required", "recovery_columns.aircraft_strings.maintenance_satisfied"), ("aircraft",), ("A-037",),
        "Uses validated fixed-column maintenance flags.", paper_equation="(3.11)",
        provenance_detail=arm.CONSTRAINT_PROVENANCE[arm.ARM_C04_MAINTENANCE],
    ),
    _item(
        arm.ARM_C05_STRING_FEASIBILITY, "ARM", "Fixed aircraft-string feasibility",
        "selected strings must pass ownership, equipment, continuity and terminal validation",
        ("scenario.aircraft", "recovery_columns.aircraft_strings", "recovery_columns.flight_options"), ("aircraft", "flights"), ("A-036",),
        "Validated before model build; not a separate paper constraint.",
        kind=ConstraintKind.FIXED_COLUMN_VALIDATION, provenance=ConstraintProvenance.IMPLEMENTATION_ASSUMPTION,
        provenance_detail=arm.CONSTRAINT_PROVENANCE[arm.ARM_C05_STRING_FEASIBILITY],
    ),
    _item(
        crm.CRM_C01_PAIRING_SELECTION, "CRM", "Crew pairing selection",
        "sum(z[pairing] for pairing owned by crew k) = 1",
        ("scenario.crew", "recovery_columns.crew_pairings"), ("crew",), ("A-041",),
        "One explicit crew-owned fixed pairing is selected.", paper_equation="(3.15)",
        provenance_detail=crm.CONSTRAINT_PROVENANCE[crm.CRM_C01_PAIRING_SELECTION],
    ),
    _item(
        crm.CRM_C02_OPTION_COVERAGE, "CRM", "Operating option coverage",
        "sum(z[p] for pairing p operating required option o) = 1",
        ("crew_recovery_request.required_operated_option_ids", "recovery_columns.crew_pairings"), ("crew", "flights"), ("A-042",),
        "Uses aggregate single crew-unit coverage.", paper_equation="(3.14)",
        provenance_detail=crm.CONSTRAINT_PROVENANCE[crm.CRM_C02_OPTION_COVERAGE],
    ),
    _item(
        crm.CRM_C03_NONREQUIRED_PROHIBITION, "CRM", "Non-required operating/deadhead prohibition",
        "non-required OPERATE coverage = 0 and non-required DEADHEAD presence = 0",
        ("crew_recovery_request.required_operated_option_ids", "recovery_columns.crew_pairings.duties"), ("crew", "flights"), ("A-043",),
        "The actual code ID combines operating leakage and deadhead schedule consistency.",
        kind=ConstraintKind.IMPLEMENTATION_GUARD, provenance=ConstraintProvenance.IMPLEMENTATION_ASSUMPTION,
        provenance_detail=crm.CONSTRAINT_PROVENANCE[crm.CRM_C03_NONREQUIRED_PROHIBITION],
    ),
    _item(
        crm.CRM_C04_CREW_FEASIBILITY, "CRM", "Fixed crew-pairing feasibility",
        "selected pairings must pass ownership, rating, station and time validation",
        ("scenario.crew", "recovery_columns.crew_pairings", "recovery_columns.flight_options"), ("crew", "flights"), ("A-044",),
        "Does not claim complete airline duty/rest legality.",
        kind=ConstraintKind.FIXED_COLUMN_VALIDATION, provenance=ConstraintProvenance.IMPLEMENTATION_ASSUMPTION,
        provenance_detail=crm.CONSTRAINT_PROVENANCE[crm.CRM_C04_CREW_FEASIBILITY],
    ),
    _item(
        crm.CRM_C05_TERMINAL_OWNERSHIP, "CRM", "Crew terminal and ownership",
        "selected pairing belongs to crew and ends at required_station_at_T_end",
        ("scenario.crew.required_station_at_T_end", "recovery_columns.crew_pairings"), ("crew",), ("A-044",),
        "Fixed-column terminal guard, not a distinct numbered paper equation.",
        kind=ConstraintKind.FIXED_COLUMN_VALIDATION, provenance=ConstraintProvenance.IMPLEMENTATION_ASSUMPTION,
        provenance_detail=crm.CONSTRAINT_PROVENANCE[crm.CRM_C05_TERMINAL_OWNERSHIP],
    ),
    _item(
        prm.PRM_C01_GROUP_SELECTION, "PRM", "Passenger group itinerary selection",
        "sum(w[itinerary] for itinerary of group g) = 1",
        ("scenario.passengers", "recovery_columns.passenger_itineraries"), ("passengers",), ("A-049",),
        "Paper integer passenger flow is mapped to indivisible binary group selection.", paper_equation="(3.18)",
        provenance_detail=prm.CONSTRAINT_PROVENANCE[prm.PRM_C01_GROUP_SELECTION],
    ),
    _item(
        prm.PRM_C02_SCHEDULE_CONSISTENCY, "PRM", "Passenger schedule consistency",
        "itinerary using a non-required flight option has w[itinerary] = 0",
        ("passenger_recovery_request.required_operated_option_ids", "recovery_columns.passenger_itineraries"), ("passengers", "flights"), ("A-047",),
        "External schedule guard; PRM does not reselect flight options.",
        kind=ConstraintKind.IMPLEMENTATION_GUARD, provenance=ConstraintProvenance.IMPLEMENTATION_ASSUMPTION,
        provenance_detail=prm.CONSTRAINT_PROVENANCE[prm.PRM_C02_SCHEDULE_CONSISTENCY],
    ),
    _item(
        prm.PRM_C03_SEAT_CAPACITY, "PRM", "Passenger seat capacity",
        "sum(passenger_count[g] * A[o,i] * w[i]) <= SEAT_CAP[o]",
        ("scenario.passengers.count", "recovery_columns.passenger_itineraries", "passenger_capacity_profile"), ("passengers", "flights"), ("A-048", "A-051"),
        "TEST CAPACITY: residual test inventory, not physical aircraft capacity; revisit ARM-to-PRM coupling in Phase 3.",
        paper_equation="(3.17)", provenance_detail=prm.CONSTRAINT_PROVENANCE[prm.PRM_C03_SEAT_CAPACITY],
    ),
    _item(
        prm.PRM_C04_ITINERARY_FEASIBILITY, "PRM", "Fixed passenger-itinerary feasibility",
        "selected itineraries must pass ownership, OD, time, arrival and UNSERVED validation",
        ("scenario.passengers", "recovery_columns.passenger_itineraries", "recovery_columns.flight_options"), ("passengers", "flights"), ("A-050",),
        "Current time continuity is not a real airline MCT implementation.",
        kind=ConstraintKind.FIXED_COLUMN_VALIDATION, provenance=ConstraintProvenance.IMPLEMENTATION_ASSUMPTION,
        provenance_detail=prm.CONSTRAINT_PROVENANCE[prm.PRM_C04_ITINERARY_FEASIBILITY],
    ),
)

CONSTRAINT_REGISTRY = MappingProxyType(
    {item.constraint_id: item for item in _CONSTRAINTS}
)

if len(CONSTRAINT_REGISTRY) != len(_CONSTRAINTS):
    raise RuntimeError("constraint registry contains duplicate constraint IDs")


def list_constraint_metadata() -> tuple[ConstraintMetadata, ...]:
    return _CONSTRAINTS
