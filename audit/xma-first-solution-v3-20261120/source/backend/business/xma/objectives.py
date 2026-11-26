"""Costs are sourced from Configuration.java, never blended with AIR weights."""
from __future__ import annotations

from .schema import XmaFlight, XmaSolveRequest


def normal_delay_cost(hours: float) -> float:
    if hours<=0:
        return 0
    if hours<=2:
        return 1
    if hours<=4:
        return 1.5
    if hours<=8:
        return 2
    if hours<=36:
        return 3
    return 1e9


def rebook_delay_cost(hours: float) -> float:
    hours=max(0,hours)  # ResultEvaluator clamps negative delay before scoring.
    if 0<=hours<6:
        return hours/30
    if hours<24:
        return hours/24
    if hours<36:
        return hours/18
    if hours<=48:
        return hours/16
    return 1e9


def schedule_cost(request: XmaSolveRequest, flight: XmaFlight, option) -> float:
    if request.objective_profile=="tianchi_2017":
        return flight.importance*(1200 if option.cancelled else option.delay*100/60)
    c=request.air_objective
    return c.flight_cancellation if option.cancelled else option.delay*c.flight_delay_per_minute


def assignment_cost(request: XmaSolveRequest, flight: XmaFlight, tail: str) -> float:
    if tail==flight.original_aircraft:
        return 0
    if request.objective_profile=="air_linear_v1":
        return request.air_objective.aircraft_reassignment
    boundary=request.dataset.adjustment_start.replace(hour=16,minute=0,second=0,microsecond=0)
    return flight.importance*(15 if flight.sched_dep<=boundary else 5)


def resident_cost(request: XmaSolveRequest, option) -> float:
    if request.objective_profile=="tianchi_2017":
        return normal_delay_cost(option.delay/60)
    return option.delay*request.air_objective.passenger_delay_per_pax_minute


def sign_cost(request: XmaSolveRequest, delay: float) -> float:
    if request.objective_profile=="tianchi_2017":
        return rebook_delay_cost(delay/60)
    return delay*request.air_objective.passenger_delay_per_pax_minute


def unserved_cost(request: XmaSolveRequest) -> float:
    return 4 if request.objective_profile=="tianchi_2017" else request.air_objective.unserved_passenger
