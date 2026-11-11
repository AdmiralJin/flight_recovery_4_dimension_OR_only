"""Exact fixed-itinerary passenger projection for the schedule master.

Whole passenger groups remain binary. This strengthens the master without
changing the AIR candidate universe, capacity semantics or recourse audit.
"""
from backend.config.costs import passenger_itinerary_cost
from backend.solver import ConstraintSense, VariableType
from backend.solver.runtime import check_budget

from .passenger_incidence import build_passenger_recovery_incidence


def passenger_master_data(scenario, columns, capacity, costs):
    incidence = build_passenger_recovery_incidence(scenario, columns)
    passengers = {p.pax_group_id: p for p in scenario.passengers}
    itineraries = {p.itinerary_id: p for p in columns.passenger_itineraries}
    return {
        "groups": {g: incidence.group_to_itineraries.columns_for_row(g) for g in passengers},
        "loads": {oid: {iid: passengers[itineraries[iid].pax_group_id].count
                         for iid in incidence.option_to_itineraries.columns_for_row(oid)}
                  for oid in incidence.option_to_itineraries.rows},
        "links": incidence.itinerary_to_flight_options,
        "costs": {iid: passenger_itinerary_cost(passengers[it.pax_group_id].count, it, costs).total
                  for iid, it in itineraries.items()},
        "capacity": capacity.seat_capacity_by_option_id,
    }


def add_passenger_master(solver, x, theta, data):
    w = {iid: solver.add_variable("master_w["+iid+"]", variable_type=VariableType.BINARY)
         for iid in data["costs"]}
    for group, ids in data["groups"].items():
        check_budget()
        solver.add_linear_constraint({w[iid]: 1.0 for iid in ids}, ConstraintSense.EQUAL, 1.0,
                                     name="master_passenger_group["+group+"]")
    for iid, ids in data["links"].items():
        for oid in ids:
            solver.add_linear_constraint({w[iid]: 1.0, x[oid]: -1.0}, ConstraintSense.LESS_EQUAL, 0.0,
                                         name="master_itinerary_available["+iid+","+oid+"]")
    for oid, loads in data["loads"].items():
        coeff = {w[iid]: float(n) for iid, n in loads.items()}
        coeff[x[oid]] = -float(data["capacity"][oid])
        solver.add_linear_constraint(coeff, ConstraintSense.LESS_EQUAL, 0.0,
                                     name="master_passenger_capacity["+oid+"]")
    coeff = {w[iid]: -float(cost) for iid, cost in data["costs"].items()}
    coeff[theta] = 1.0
    solver.add_linear_constraint(coeff, ConstraintSense.EQUAL, 0.0, name="master_exact_passenger_cost")
