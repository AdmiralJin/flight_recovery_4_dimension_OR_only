"""Fixed-schedule, full-column LP/MIP versus CG/B&P evidence."""
from backend.config import (FlightStringGenerationConfig, AircraftStringColumnGenerationConfig,
                            BranchAndPriceConfig)
from backend.core.arm import AircraftRecoveryRequest, solve_fixed_column_arm
from backend.core.aircraft_string_master import solve_full_column_aircraft_string_lp
from backend.core.aircraft_string_column_generation import (solve_aircraft_string_column_generation,
    audit_aircraft_string_column_generation_termination)
from backend.core.aircraft_string_branch_and_price import solve_aircraft_string_branch_and_price
from backend.schemas.columns import FlightOperationType
from backend.solver import HighsAdapter, GurobiAdapter
from backend.solver.runtime import SolveBudget, use_budget

from .audit import enumerate_paths
from .common import clean


def execute(public, selected_options, seconds=120):
    factory = HighsAdapter if public.backend == "highs" else GurobiAdapter
    factory = (lambda cls=factory: cls(output_flag=False))
    required = tuple(o.option_id for o in public.recovery_columns.flight_options
                     if o.option_id in selected_options and o.operation_type == FlightOperationType.OPERATE)
    request = AircraftRecoveryRequest(public.scenario.scenario_id, required)
    string = FlightStringGenerationConfig.model_validate(public.configs["flight_string_generation"])
    cg_config = AircraftStringColumnGenerationConfig.model_validate(public.configs["aircraft_string_cg"])
    bp_config = BranchAndPriceConfig.model_validate(public.configs["branch_and_price"])
    with use_budget(SolveBudget(seconds)):
        paths, enumeration = enumerate_paths(public)
        cols = public.recovery_columns.model_copy(update={"aircraft_strings": paths})
        with factory() as solver:
            full_lp = solve_full_column_aircraft_string_lp(public.scenario, cols.flight_options, paths, request,
                                                          public.costs, string, solver)
        cg = solve_aircraft_string_column_generation(public.scenario, cols.flight_options, request,
                                                     public.costs, string, cg_config, factory)
        termination = audit_aircraft_string_column_generation_termination(public.scenario, cols.flight_options,
            paths, request, public.costs, string, cg_config, cg, factory)
        with factory() as solver:
            full_mip = solve_fixed_column_arm(public.scenario, cols, request, public.costs, solver)
        bp = solve_aircraft_string_branch_and_price(public.scenario, cols.flight_options, request,
                                                    public.costs, string, cg_config, bp_config, factory)
    passed = (cg.status.value == "optimal" and full_lp.outcome.status.value == "optimal"
              and abs(cg.objective_value-full_lp.objective_value) <= 1e-6 and termination.passed
              and bp.status.value == "optimal" and full_mip.status.value == "optimal"
              and abs(bp.objective_value-full_mip.objective_value) <= 1e-6)
    return clean(dict(status="passed" if passed else "failed", problem_sha256=public.problem_sha256,
        schedule=required, enumeration=enumeration, full_lp=full_lp, cg=cg, pricing_audit=termination,
        full_mip=full_mip, bp=bp, lp_is_not_integer_optimality=True))
