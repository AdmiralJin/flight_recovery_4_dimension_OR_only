from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

from backend.application.result_builder import build_recovered_result
from backend.application.solve_service import PROFILE_FILES, _git_commit, _selected_solution_artifact
from backend.config import FixedColumnBendersConfig
from backend.core import (IntegratedRecoveryRequest, solve_integrated_fixed_column_oracle,
                          solve_fixed_column_benders, solve_benders_with_branch_and_price)
from backend.core.benders_column_generation import solve_benders_with_column_generation
from backend.schemas.result import RunMetadata, SolveProfileIds, RecoveredStatus
from backend.solver import HighsAdapter, GurobiAdapter
from backend.solver.runtime import SolveBudget, use_budget, SolveStopped

from .audit import audit, enumerate_paths, necessary_infeasibility_certificate
from .common import clean, digest, frozen_repository_state, solver_failure
from .model import PublicSolveRequest


def precheck(request):
    from backend.services.validator import validate_scenario
    from backend.services.column_validator import validate_recovery_columns
    _, scenario_issues = validate_scenario(request.scenario)
    _, column_issues = validate_recovery_columns(request.scenario, request.recovery_columns)
    return clean({"ready": not (request.precheck_issues or scenario_issues or column_issues),
                  "issues": list(request.precheck_issues)+list(scenario_issues)+list(column_issues),
                  "original_rules_eligible": False, "model_type": request.model_type,
                  "problem_sha256": request.problem_sha256, "rules": request.rule_mapping})


def execute(request, *, seconds=None, cancel_check=None, event_sink=None, checkpoint_sink=None,
            node_limit=None, iteration_limit=None, output_flag=False):
    if not isinstance(request, PublicSolveRequest):
        request = PublicSolveRequest.model_validate(request)
    if seconds is None:
        from backend.workbench.solve_policy import recommend_time_limit
        seconds = recommend_time_limit(len(request.scenario.flights), len(request.recovery_columns.flight_options),
            len(request.recovery_columns.flight_options)*len(request.scenario.aircraft))["time_limit_seconds"]
    ready = precheck(request)
    if not ready["ready"]:
        return {"status": "unsupported_input", "precheck": ready, "problem_sha256": request.problem_sha256}
    start = perf_counter()
    timings = dict(solver_construction_seconds=0., solver_call_seconds=0., independent_audit_seconds=0.,
                   enumeration_seconds=0.)
    if cancel_check and cancel_check():
        return dict(status="aborted", algorithm=request.algorithm, backend=request.backend,
                    problem_sha256=request.problem_sha256, certified_optimal=False, runtime_seconds=0,
                    objective=None, lower_bound=None, upper_bound=None, selected=None)
    # Direct baselines deliberately enter the solver even when the existing
    # temporal relaxation could prove infeasibility without running a MIP.
    if request.algorithm == "direct_mip":
        from .direct import execute_direct
        return execute_direct(request, seconds=seconds, cancel_check=cancel_check, event_sink=event_sink,
                              checkpoint_sink=checkpoint_sink, output_flag=output_flag)
    certificate = necessary_infeasibility_certificate(request)
    if certificate:
        return {"status": "infeasible", "algorithm": request.algorithm, "backend": request.backend,
                "problem_sha256": request.problem_sha256, "objective": None, "lower_bound": None,
                "upper_bound": None, "certified_optimal": False, "certified_infeasible": True,
                "infeasibility_certificate": certificate, "preprocessing_only": True,
                "runtime_seconds": perf_counter()-start, "original_rules": {"eligible": False}}
    factory_type = HighsAdapter if request.backend == "highs" else GurobiAdapter
    def factory():
        adapter = factory_type(output_flag=output_flag, cancel_check=cancel_check)
        def track(method, key):
            def measured(*args, **kwargs):
                before = perf_counter()
                try:
                    return method(*args, **kwargs)
                finally:
                    timings[key] += perf_counter()-before
            return measured
        for name in ("create_model", "add_variable", "add_linear_constraint", "set_objective"):
            setattr(adapter, name, track(getattr(adapter, name), "solver_construction_seconds"))
        adapter.solve = track(adapter.solve, "solver_call_seconds")
        return adapter
    # Loader types are explicit public interfaces, not runtime mutation of legacy profiles.
    from backend.config import (FlightStringGenerationConfig, CrewPairingGenerationConfig,
        AircraftStringColumnGenerationConfig, CrewPairingColumnGenerationConfig,
        BendersColumnGenerationConfig, BranchAndPriceConfig)
    types = dict(flight_string_generation=FlightStringGenerationConfig,
                 crew_pairing_generation=CrewPairingGenerationConfig,
                 aircraft_string_cg=AircraftStringColumnGenerationConfig,
                 crew_pairing_cg=CrewPairingColumnGenerationConfig,
                 benders_cg=BendersColumnGenerationConfig, branch_and_price=BranchAndPriceConfig)
    configs = {key: cls.model_validate(request.configs[key]) for key, cls in types.items()}
    if node_limit is not None:
        configs["branch_and_price"] = configs["branch_and_price"].model_copy(update={"max_nodes": node_limit})
    if iteration_limit is not None:
        configs["benders_cg"] = configs["benders_cg"].model_copy(update={"max_iterations": iteration_limit})
    columns = request.recovery_columns
    enumeration, core = None, None
    def checkpoint(partial):
        if checkpoint_sink and partial.solution_columns is not None:
            selected = {"flight_options": partial.selected_flight_options,
                        "aircraft_strings": partial.selected_aircraft_strings, "crew_pairings": (),
                        "passenger_itineraries": partial.selected_passenger_itineraries}
            before_audit = perf_counter()
            primal = audit(request, partial.solution_columns, selected, partial.objective_value)
            timings["independent_audit_seconds"] += perf_counter()-before_audit
            if primal["pass"]:
                checkpoint_sink(clean({"status": "not_converged", "problem_sha256": request.problem_sha256,
                    "objective": partial.objective_value, "lower_bound": partial.lower_bound,
                    "upper_bound": partial.upper_bound, "audit": primal, "selected": selected,
                    "columns": partial.solution_columns}))
    parameters = {"TimeLimit": seconds, "MIPGap": 0.0, "Threads": 1}
    with use_budget(SolveBudget(max(0, seconds-(perf_counter()-start)), cancel_check, checkpoint)):
        if request.algorithm.startswith("xma_"):
            from .xma import execute_xma
            return execute_xma(request, seconds=max(.001, seconds-(perf_counter()-start)), cancel_check=cancel_check,
                               event_sink=event_sink, checkpoint_sink=checkpoint_sink)
        if request.algorithm in ("integrated_oracle", "fixed_benders"):
            enumeration_start = perf_counter()
            paths, enumeration = enumerate_paths(request)
            timings["enumeration_seconds"] = perf_counter()-enumeration_start
            columns = columns.model_copy(update={"aircraft_strings": paths})
            missing = [a.tail_id for a in request.scenario.aircraft
                       if not any(p.aircraft_id == a.tail_id for p in paths)]
            if missing:
                return clean({"status": "infeasible", "algorithm": request.algorithm, "backend": request.backend,
                    "problem_sha256": request.problem_sha256, "objective": None, "lower_bound": None,
                    "upper_bound": None, "certified_optimal": False, "certified_infeasible": True,
                    "enumeration": enumeration, "infeasibility_certificate": {"tails_without_any_legal_path": missing},
                    "runtime_seconds": perf_counter()-start, "original_rules": {"eligible": False}})
        if request.algorithm == "integrated_oracle":
            with factory() as s:
                result = solve_integrated_fixed_column_oracle(request.scenario, columns,
                    IntegratedRecoveryRequest(request.scenario.scenario_id, request.costs.cost_profile_id,
                                              request.capacity_profile.capacity_profile_id),
                    request.capacity_profile, request.costs, s, solver_parameters=parameters)
            d = result.diagnostics
            core = SimpleNamespace(status=RecoveredStatus.OPTIMAL if result.status.value == "optimal" else
                    RecoveredStatus.INFEASIBLE if result.status.value == "infeasible" else RecoveredStatus.NOT_CONVERGED,
                objective_value=result.objective_value, lower_bound=result.best_bound, upper_bound=result.objective_value,
                selected_flight_options=tuple(d.get("selected_option_by_flight", {}).values()),
                selected_aircraft_strings=tuple(d.get("selected_string_by_aircraft", {}).values()), selected_crew_pairings=(),
                selected_passenger_itineraries=tuple(d.get("selected_itinerary_by_group", {}).values()), solution_columns=columns,
                diagnostics={"integrated_audit": d if result.objective_value is not None else None,
                             "terminal_reason": result.termination_reason, "formal_full_enumerators_used": True})
            raw_core = clean(result)
        elif request.algorithm == "fixed_benders":
            core = solve_fixed_column_benders(request.scenario, columns, request.capacity_profile, request.costs,
                FixedColumnBendersConfig.model_validate(request.configs["fixed_benders"]),
                solver_factory=factory, solver_parameters=parameters)
            raw_core = clean(core)
            core = SimpleNamespace(**{k: getattr(core, k) for k in (
                "status", "objective_value", "lower_bound", "upper_bound", "selected_flight_options",
                "selected_aircraft_strings", "selected_crew_pairings", "selected_passenger_itineraries", "diagnostics")},
                solution_columns=columns)
        else:
            args = [request.scenario, columns, request.capacity_profile, request.costs,
                configs["flight_string_generation"], configs["crew_pairing_generation"],
                configs["aircraft_string_cg"], configs["crew_pairing_cg"], configs["benders_cg"]]
            fn = solve_benders_with_branch_and_price if request.algorithm == "air_bp" else solve_benders_with_column_generation
            if request.algorithm == "air_bp":
                args.append(configs["branch_and_price"])
            core = fn(*args, solver_factory=factory, solver_parameters=parameters, event_sink=event_sink)
            raw_core = clean(core)
    failure = solver_failure({"core": raw_core})
    if failure:
        return dict(**failure, core=raw_core, problem_sha256=request.problem_sha256,
                    algorithm=request.algorithm, backend=request.backend, objective=None, lower_bound=None, upper_bound=None,
                    certified_optimal=False, runtime_seconds=perf_counter()-start, original_rules={"eligible": False})
    if core.solution_columns is not None:
        columns = core.solution_columns
    selected = {"flight_options": core.selected_flight_options, "aircraft_strings": core.selected_aircraft_strings,
                "crew_pairings": core.selected_crew_pairings, "passenger_itineraries": core.selected_passenger_itineraries}
    before_audit = perf_counter()
    primal = audit(request, columns, selected, core.objective_value) if core.objective_value is not None else None
    timings["independent_audit_seconds"] += perf_counter()-before_audit
    lb, ub = core.lower_bound, core.upper_bound
    closed = lb is not None and ub is not None and abs(ub-lb) <= 1e-5
    certified = bool(primal and primal["pass"] and closed and core.status.value == "optimal")
    if core.status.value == "optimal" and not certified:
        raise RuntimeError("optimal label rejected: primal audit or finite bound closure is missing")
    return clean({"status": core.status.value, "problem_sha256": request.problem_sha256,
        "algorithm": request.algorithm, "backend": request.backend, "objective": core.objective_value,
        "lower_bound": lb, "upper_bound": ub, "gap": max(0., ub-lb) if lb is not None and ub is not None else None,
        "certified_optimal": certified, "audit": primal, "selected": selected,
        "certified_infeasible": request.algorithm == "integrated_oracle" and core.status.value == "infeasible",
        "components": request.components,
        "solution_columns": columns, "enumeration": enumeration, "core": raw_core,
        "runtime_seconds": perf_counter()-start, "effective_configs": configs,
        "timings": timings,
        "original_rules": {"eligible": False, "historical_gap": None},
        "certificate_scope": "frozen_research_model; implicit aircraft paths; fixed passenger candidates"})


def solve_request(request, *, event_sink=None, cancel_check=None, run_id=None, runtime_controls=None,
                  solution_artifact_sink=None):
    """Workbench worker entry; use the same snapshot, solve and audit as batch runs."""
    request = request if isinstance(request, PublicSolveRequest) else PublicSolveRequest.model_validate(request)
    if request.algorithm not in ("air_bp", "direct_mip", "integrated_oracle"):
        raise ValueError("Workbench supports public direct MIP, small Oracle and AIR Benders CG/BP")
    controls = runtime_controls or {}
    started = datetime.now(timezone.utc)
    evidence = execute(request, seconds=controls.get("time_limit_seconds"), cancel_check=cancel_check,
                       event_sink=event_sink, checkpoint_sink=solution_artifact_sink,
                       node_limit=controls.get("max_branch_nodes"), iteration_limit=controls.get("max_benders_iterations"))
    if evidence["status"] == "unsupported_input":
        raise ValueError(str(evidence["precheck"]["issues"]))
    if evidence["status"] in ("license_limited", "solver_error"):
        raise ValueError(evidence["status"]+": "+evidence["reason"])
    from backend.schemas.columns import RecoveryColumns
    raw = evidence.get("core") or {"status": evidence["status"], "objective_value": None,
        "lower_bound": None, "upper_bound": None, "diagnostics": {
            "terminal_reason": "certified_preprocessing_infeasibility" if evidence.get("certified_infeasible") else evidence["status"],
            "infeasibility_certificate": evidence.get("infeasibility_certificate")}}
    if request.algorithm in ("direct_mip", "integrated_oracle"):
        raw = dict(status="not_converged" if evidence["status"] == "input_limit" else evidence["status"], objective_value=evidence.get("objective"),
                   lower_bound=evidence.get("lower_bound"), upper_bound=evidence.get("upper_bound"),
                   diagnostics={"terminal_reason": evidence.get("reason") or (evidence.get("core") or {}).get("termination_reason"),
                       "integrated_audit": {"all_constraints_satisfied": bool((evidence.get("audit") or {}).get("pass"))},
                       "model_size": evidence.get("model_size"), "timings": evidence.get("timings")})
    selections = evidence.get("selected") or {"flight_options": [], "aircraft_strings": [], "passenger_itineraries": []}
    core = SimpleNamespace(status=RecoveredStatus(raw["status"]), objective_value=raw["objective_value"],
        lower_bound=raw["lower_bound"], upper_bound=raw["upper_bound"], diagnostics=raw["diagnostics"],
        solution_columns=RecoveryColumns.model_validate(evidence["solution_columns"]) if evidence.get("solution_columns") else None,
        selected_flight_options=selections["flight_options"], selected_aircraft_strings=selections["aircraft_strings"],
        selected_crew_pairings=(), selected_passenger_itineraries=selections["passenger_itineraries"])
    metadata = RunMetadata(run_id=run_id or str(uuid4()), scenario_id=request.scenario.scenario_id,
        git_commit=(frozen_repository_state() or {}).get("git_commit") or _git_commit(),
        application_version="public-benchmark-1.0", solver=request.backend,
        solver_version=(HighsAdapter if request.backend == "highs" else GurobiAdapter)().solver_version,
        algorithm={"air_bp": "public_air_benders_cg_bp_v1", "direct_mip": "public_compact_direct_mip_v1",
                   "integrated_oracle": "public_integrated_oracle_v1"}[request.algorithm], algorithm_profile_ids=SolveProfileIds(**{
            k: request.configs[k]["profile_id"] for k in PROFILE_FILES}),
        cost_profile_id=request.costs.cost_profile_id, capacity_profile_id=request.capacity_profile.capacity_profile_id,
        started_at=started, finished_at=datetime.now(timezone.utc), runtime_seconds=evidence["runtime_seconds"])
    result = build_recovered_result(request.scenario, request.recovery_columns, core, request.costs, request.capacity_profile, metadata)
    if solution_artifact_sink and (evidence.get("audit") or {}).get("pass"):
        artifact = _selected_solution_artifact(core.solution_columns, result)
        artifact["public_evidence"] = {k: v for k, v in evidence.items() if k not in ("core", "solution_columns")}
        solution_artifact_sink(artifact)
    return result
