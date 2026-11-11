"""One monotonic budget shared by nested AIR solves and Python pricing loops."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields, replace
from functools import wraps
from time import perf_counter


class SolveStopped(RuntimeError):
    pass


class SolveBudget:
    def __init__(self, seconds=None, cancel_check=None, checkpoint_sink=None):
        self.started = perf_counter()
        self.deadline = self.started + seconds if seconds is not None else float("inf")
        self.reserve = min(5.0, seconds * .05) if seconds is not None else 0
        self.cancel_check = cancel_check or (lambda: False)
        self.checkpoint_sink = checkpoint_sink
        self.best = None
        self.lower = None
        self.auditing = 0
        self.resources = []

    def remaining(self):
        return max(0.0, self.deadline - self.reserve - perf_counter())

    def check(self):
        if not self.auditing:
            if self.cancel_check():
                raise SolveStopped("cancelled")
            if self.remaining() <= 0:
                raise SolveStopped("total_time_limit")


ACTIVE_BUDGET = ContextVar("air_solve_budget", default=None)


@contextmanager
def use_budget(budget):
    token = ACTIVE_BUDGET.set(budget)
    try:
        yield budget
    finally:
        ACTIVE_BUDGET.reset(token)


@contextmanager
def audit_budget():
    budget = ACTIVE_BUDGET.get()
    if budget:
        budget.auditing += 1
    try:
        yield
    finally:
        if budget:
            budget.auditing -= 1


def check_budget():
    budget = ACTIVE_BUDGET.get()
    if budget:
        budget.check()


def register_resource(close):
    budget = ACTIVE_BUDGET.get()
    if budget:
        budget.resources.append(close)


def retain_incumbent(result):
    budget = ACTIVE_BUDGET.get()
    if budget and result.diagnostics.get("integrated_audit", {}).get("all_constraints_satisfied"):
        if result.lower_bound is not None:
            budget.lower = max(budget.lower if budget.lower is not None else -float("inf"), result.lower_bound)
        if budget.best is None or result.objective_value < budget.best.objective_value:
            budget.best = result
            if budget.checkpoint_sink:
                budget.checkpoint_sink(result)


def bounded_core(result_type, status_type):
    """Preserve a fully audited incumbent if any nested build/solve/pricing stops."""
    def decorate(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            current = ACTIVE_BUDGET.get()
            parameters = kwargs.get("solver_parameters") or {}
            with use_budget(current or SolveBudget(parameters.get("TimeLimit"))) as budget:
                try:
                    check_budget()
                    result = fn(*args, **kwargs)
                    if result.status.value != "optimal":
                        best = budget.best
                        if best is not None and (result.upper_bound is None or best.objective_value < result.upper_bound):
                            names = ("objective_value", "upper_bound", "x_values", "y_values", "z_values", "w_values",
                                     "selected_flight_options", "selected_aircraft_strings", "selected_crew_pairings",
                                     "selected_passenger_itineraries", "solution_columns")
                            result = replace(result, **{name: getattr(best, name) for name in names},
                                             diagnostics={**dict(result.diagnostics),
                                                          "integrated_audit": best.diagnostics["integrated_audit"],
                                                          "incumbent_retained_from_checkpoint": True})
                        if budget.remaining() <= 0:
                            result = replace(result, status=status_type.NOT_CONVERGED,
                                             diagnostics={**dict(result.diagnostics), "terminal_reason": "total_time_limit",
                                                          "cumulative_budget": True})
                    return result
                except SolveStopped as exc:
                    best = budget.best
                    values = {}
                    for field in fields(result_type):
                        name = field.name
                        if name == "status":
                            values[name] = status_type.ABORTED if str(exc) == "cancelled" else status_type.NOT_CONVERGED
                        elif name == "diagnostics":
                            values[name] = {**(dict(best.diagnostics) if best else {}),
                                            "terminal_reason": str(exc), "cumulative_budget": True,
                                            "runtime_seconds": perf_counter() - budget.started}
                        elif name == "lower_bound":
                            values[name] = budget.lower
                        elif name in ("iterations", "cuts", "exact_cuts", "certificates"):
                            values[name] = ()
                        elif best is not None and hasattr(best, name):
                            values[name] = getattr(best, name)
                        elif name.endswith("_values"):
                            values[name] = {}
                        elif name.startswith("selected_"):
                            values[name] = ()
                        else:
                            values[name] = None
                    return result_type(**values)
        return run
    return decorate
