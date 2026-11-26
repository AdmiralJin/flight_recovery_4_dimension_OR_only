"""Isolated experiment workers. Outputs are evidence, never production state."""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
import gzip
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validation_campaign import atomic_json, atomic_text, read_json


def clean(value):
    if hasattr(value, "model_dump"):
        return clean(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return clean({field: getattr(value, field) for field in value.__dataclass_fields__})
    if isinstance(value, Mapping):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def save_gzip(path, value):
    path = Path(path)
    payload = json.dumps(clean(value), ensure_ascii=False, allow_nan=False).encode("utf-8")
    path.write_bytes(gzip.compress(payload, mtime=0))


def digest(value):
    payload = json.dumps(clean(value), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def close_number(left, right):
    return left is not None and right is not None and math.isclose(
        float(left), float(right), abs_tol=1e-6, rel_tol=1e-8)


def memory_failure(value):
    message = str(value).lower()
    return any(text in message for text in ("out of memory", "out-of-memory", "memoryerror", "bad_alloc",
                                             "cannot allocate memory", "not enough memory"))


class Evidence:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.started = time.perf_counter()
        self.events = self.folder.joinpath("events.jsonl").open("a", encoding="utf-8", buffering=1)
        self.latest = {}
        self.last_write = 0.0
        self.first_global_incumbent = None
        self.first_audited_feasible = None
        self.top_algorithm = None
        self.seq = 0
        self.truncated = False
        self.lock = threading.RLock()
        self.observation_origin = 0.0
        self.license_limited = False
        self.resource_limited = False

    def progress(self, **values):
        with self.lock:
            self.latest.update(clean(values))
            self.latest["elapsed_seconds"] = round(time.perf_counter() - self.started, 3)
            self.latest["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
            atomic_json(self.folder / "progress.json", self.latest)

    def event(self, payload):
        with self.lock:
            self._event(payload)

    def _event(self, payload):
        self.seq += 1
        entry = clean({"seq": self.seq, "observed_seconds": time.perf_counter() - self.started, **payload})
        # Preserve a bounded trace; final solver results and truncation metadata survive.
        if self.events.tell() < 64 * 1024 ** 2:
            self.events.write(json.dumps(entry, ensure_ascii=False) + "\n")
        else:
            self.truncated = True
        kind = entry.get("type", "")
        stage = entry.get("stage", "")
        global_event = kind in ("benders_iteration", "solve_bounds", "run_completed", "incumbent_audited")
        if self.top_algorithm in ("joint_arc_flow", "joint_path_oracle") and kind == "mip_progress":
            global_event = entry.get("metrics", {}).get("bound_scope", "global") == "global"
        # branch_node and nested model MIP bounds are deliberately not global bounds.
        values = {"stage": stage, "event_type": kind, "message": entry.get("message", ""),
                  "metrics": entry.get("metrics", {}), "events": self.seq}
        if global_event:
            values.update({k: entry.get(k) for k in (
                "lower_bound", "upper_bound", "absolute_gap", "relative_gap")})
            if entry.get("upper_bound") is not None and self.first_global_incumbent is None:
                self.first_global_incumbent = entry["observed_seconds"] - self.observation_origin
        if kind == "incumbent_audited" and self.first_audited_feasible is None:
            self.first_audited_feasible = entry["observed_seconds"] - self.observation_origin
            values["first_audited_feasible_seconds"] = self.first_audited_feasible
        if time.perf_counter() - self.last_write >= 2 or global_event:
            self.progress(**values)
            self.last_write = time.perf_counter()

    def close(self):
        self.events.close()


class StageTimer:
    """Observational wrappers; same-category nested calls are counted once."""
    def __init__(self):
        self.times = Counter()
        self.active = Counter()
        self.originals = []
        self.extra = Counter()

    def wrap(self, target, attribute, category):
        original = getattr(target, attribute)
        if not callable(original):
            return
        @wraps(original)
        def measured(*args, **kwargs):
            outer = self.active[category] == 0
            started = time.perf_counter()
            self.active[category] += 1
            try:
                return original(*args, **kwargs)
            finally:
                self.active[category] -= 1
                if outer:
                    self.times[category] += time.perf_counter() - started
        self.originals.append((target, attribute, original))
        setattr(target, attribute, measured)

    def air(self):
        import backend.core
        from backend.solver import GurobiAdapter
        self.wrap(GurobiAdapter, "solve", "solver_seconds")
        for name, module in list(sys.modules.items()):
            if not name.startswith("backend.core") or module is None:
                continue
            for key, value in list(vars(module).items()):
                if inspect.isfunction(value) and (key.startswith("build_") or key.startswith("_build_")):
                    if "network" in key:
                        self.wrap(module, key, "network_build_seconds")
                    self.wrap(module, key, "model_build_seconds")
                elif inspect.isfunction(value) and key.startswith("price_"):
                    self.wrap(module, key, "pricing_seconds")
                elif inspect.isfunction(value) and key.startswith("generate_"):
                    self.wrap(module, key, "candidate_generation_seconds")
                elif inspect.isfunction(value) and key in ("audit_integrated_candidate", "recompute_benders_cg_audit"):
                    self.wrap(module, key, "independent_audit_seconds")

    def xma(self):
        from backend.business.xma import algorithms, evaluator, model, rules, service
        from backend.business.xma.solver import ScalableModel
        self.wrap(algorithms.Budget, "optimize", "solver_seconds")
        self.wrap(ScalableModel, "_problem", "matrix_extraction_seconds")
        self.wrap(ScalableModel, "_pass_highs_model", "native_model_build_seconds")
        self.wrap(ScalableModel, "_run_highs", "native_optimization_seconds")
        self.wrap(algorithms, "price", "pricing_seconds")
        self.wrap(model, "build_networks", "network_build_seconds")
        original_dispose=ScalableModel.dispose
        @wraps(original_dispose)
        def dispose(instance):
            if not instance._disposed:
                self.extra.update(instance.reuse_statistics)
                self.times["solver_model_update_seconds"]+=instance.timings.get("solver_model_update_seconds",0)
            return original_dispose(instance)
        self.originals.append((ScalableModel,"dispose",original_dispose))
        ScalableModel.dispose=dispose
        for module in (algorithms, model):
            self.wrap(module, "build_joint", "model_build_seconds")
        for module in (rules, service):
            self.wrap(module, "generate_options", "candidate_generation_seconds")
        for module in (algorithms, evaluator, service):
            self.wrap(module, "evaluate", "independent_audit_seconds")

    def close(self):
        for target, attribute, original in reversed(self.originals):
            setattr(target, attribute, original)


def single_thread_air():
    from backend.solver import GurobiAdapter
    original = GurobiAdapter.create_model
    @wraps(original)
    def create_model(adapter, *args, **kwargs):
        result = original(adapter, *args, **kwargs)
        adapter._require_model().setParam("Threads", 1)
        adapter._require_model().setParam("Seed", 0)
        return result
    GurobiAdapter.create_model = create_model
    original_solve = GurobiAdapter.solve
    @wraps(original_solve)
    def solve(adapter, *args, **kwargs):
        outcome = original_solve(adapter, *args, **kwargs)
        if outcome.diagnostics.get("error_code") == 10010:
            Evidence.current.license_limited = True
        if outcome.diagnostics.get("error_code") == 10001 or memory_failure(outcome.diagnostics.get("error_message", "")):
            Evidence.current.resource_limited = True
        return outcome
    GurobiAdapter.solve = solve


def air_inputs(bundle):
    from backend.application.solve_service import PROFILE_FILES, ROOT as BACKEND_ROOT
    from backend.config import CostOverrideConfig, PassengerCapacityProfile, apply_cost_overrides, load_cost_config
    from backend.schemas.columns import RecoveryColumns
    from backend.schemas.scenario import Scenario
    configs = {key: loader(BACKEND_ROOT / "data/config" / file)
               for key, (file, loader) in PROFILE_FILES.items()}
    base = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(base, CostOverrideConfig(
        base_cost_profile_id=bundle["cost_profile_id"], overrides=bundle.get("cost_overrides", {})))
    return (Scenario.model_validate(bundle["scenario"]),
            RecoveryColumns.model_validate(bundle["recovery_columns"]),
            PassengerCapacityProfile.model_validate(bundle["capacity_profile"]), costs, configs)


def validate_bounds(result):
    diag = result.get("diagnostics") or {}
    lower, upper = diag.get("lower_bound"), diag.get("upper_bound")
    if lower is not None and upper is not None:
        assert lower <= upper + max(1e-6, abs(upper) * 1e-8), (lower, upper)
    objective = (result.get("objective") or {}).get("total")
    if result["status"] == "optimal":
        assert close_number(lower, upper), (lower, upper)
        assert close_number(objective, upper), (objective, upper)
        assert diag.get("integrated_audit_pass") is True
    return lower, upper, objective


def air_solve(bundle, job, ev, tag="solve"):
    from backend.application.solve_service import solve_request
    from backend.schemas.result import SolveRequest
    save_gzip(ev.folder / (tag + "_input.json.gz"), bundle)
    timer = StageTimer()
    timer.air()
    started = time.perf_counter()
    ev.top_algorithm = "air_benders_bp"
    ev.first_global_incumbent = None
    ev.first_audited_feasible = None
    ev.observation_origin = started - ev.started
    try:
        result = solve_request(
            SolveRequest.model_validate(bundle), event_sink=ev.event,
            runtime_controls={"time_limit_seconds": job["solver_seconds"]},
            solution_artifact_sink=lambda payload: save_gzip(ev.folder / (tag + "_selected.json.gz"), payload),
        ).model_dump(mode="json")
    finally:
        timer.close()
    save_gzip(ev.folder / (tag + "_result.json.gz"), result)
    validate_bounds(result)
    return result, {"end_to_end_seconds": time.perf_counter() - started, **timer.times,
                    "first_global_incumbent_seconds": ev.first_global_incumbent,
                    "first_audited_feasible_seconds": ev.first_audited_feasible}


def check_expected(result, expected):
    required_status = expected.get("optimization_status", expected.get("status"))
    assert result["status"] == required_status, (required_status, result["status"])
    if expected.get("objective_total") is not None:
        assert close_number(result["objective"]["total"], expected["objective_total"])
    selected = {row["resolved"]["flight_id"]: row["resolved"]["selected_option_id"]
                for row in result.get("resolved_flights", [])}
    for flight, option in expected.get("required_flight_options", {}).items():
        assert selected[flight] == option
    metrics = (result.get("metrics") or {}).get("recovery", {})
    for key, value in expected.get("required_metrics", {}).items():
        assert metrics[key] == value, (key, metrics.get(key), value)


def run_air_case(job, ev):
    from backend.application.case_service import load_case
    from backend.application.solve_service import solve_readiness
    from backend.services.validator import validate_scenario
    config = job["config"]
    if job["kind"] == "air_case":
        payload = load_case(config["case_id"])
        expected, bundle = payload["case"]["expected"], payload["solve_bundle"]
        parsed, issues = validate_scenario(payload["scenario"])
        assert (parsed is not None and not issues) == expected["scenario_valid"]
        readiness = solve_readiness(bundle or {"scenario": payload["scenario"]})
        assert readiness["solve_ready"] == expected["solve_ready"]
        if not expected["solve_ready"]:
            return {"verdict": "passed", "summary": "Expected input rejection / Scenario-only verified",
                    "readiness": readiness, "optimization_status": "not_run"}
    else:
        bundle = read_json(ROOT / config["path"])
        expected = config.get("expected", {})
        assert solve_readiness(bundle)["solve_ready"]
    result, timings = air_solve(bundle, job, ev)
    check_expected(result, expected)
    for alias_expected in config.get("additional_expectations", []):
        check_expected(result, alias_expected)
    return {"verdict": "passed", "summary": f"{result['status']} objective={(result.get('objective') or {}).get('total')}",
            "optimization_status": result["status"], "expected": expected, "timings": timings,
            "diagnostics": result["diagnostics"], "input_hash": digest(bundle)}


def run_air_stress(job, ev):
    bundle = read_json(ROOT / job["config"]["path"])
    result, timings = air_solve(bundle, job, ev)
    return {"verdict": "passed" if result["status"] == "optimal" else "inconclusive",
            "summary": f"{result['status']}, LB={result['diagnostics']['lower_bound']}, UB={result['diagnostics']['upper_bound']}",
            "optimization_status": result["status"], "diagnostics": result["diagnostics"],
            "timings": timings, "input_hash": digest(bundle)}


def run_air_cg(job, ev):
    import backend.core as core
    from backend.config import CostOverrideConfig, apply_cost_overrides, load_cost_config
    from backend.config import load_flight_string_generation_config, load_crew_pairing_generation_config
    from backend.config import load_aircraft_string_column_generation_config, load_crew_pairing_column_generation_config
    from backend.schemas.columns import RecoveryColumns
    from backend.schemas.scenario import Scenario
    from backend.solver import GurobiAdapter
    config = job["config"]
    name, owner = config["case"], config["owner"]
    scenario = Scenario.model_validate(read_json(ROOT / f"data/examples/{name}.json"))
    columns = RecoveryColumns.model_validate(read_json(ROOT / f"data/columns/{name}_columns.json"))
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    aircraft = owner == "aircraft"
    if aircraft:
        generation = load_flight_string_generation_config(ROOT / "data/config/phase5_test_string_generation_v1.json")
        cg_config = load_aircraft_string_column_generation_config(ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json")
        generate, full_lp, cg_solve, audit = (core.generate_aircraft_strings, core.solve_full_column_aircraft_string_lp,
            core.solve_aircraft_string_column_generation, core.audit_aircraft_string_column_generation_termination)
        required = ("S11_REQ1", "S11_REQ2") if name.startswith("toy_") else tuple(
            core.resolve_original_flight_option_ids(scenario, columns.flight_options).values())
        request = core.AircraftRecoveryRequest.from_option_ids(scenario.scenario_id, required)
    else:
        generation = load_crew_pairing_generation_config(ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json")
        cg_config = load_crew_pairing_column_generation_config(ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json")
        generate, full_lp, cg_solve, audit = (core.generate_crew_pairings, core.solve_full_column_crew_pairing_lp,
            core.solve_crew_pairing_column_generation, core.audit_crew_pairing_column_generation_termination)
        required = ("S12_A_LONG", "S12_Z_SHORT") if name.startswith("toy_") else tuple(
            core.resolve_original_flight_option_ids(scenario, columns.flight_options).values())
        if name.startswith("toy_"):
            costs = apply_cost_overrides(costs, CostOverrideConfig(
                base_cost_profile_id=costs.cost_profile_id, overrides={"crew_reassignment": 100.0}))
        request = core.CrewRecoveryRequest.from_option_ids(scenario.scenario_id, required)
    records = []
    audit_seconds = []
    save_gzip(ev.folder / "input.json.gz", {"scenario": scenario, "initial_columns": columns,
        "costs": costs, "generation_config": generation, "cg_config": cg_config, "request": request})
    for repetition in range(-1, config.get("repeats", 3)):
        outcomes = {}
        for method in (("full", "cg") if repetition % 2 == 0 else ("cg", "full")):
            ev.progress(stage="performance", repetition=repetition, method=method, dataset=name)
            timer = StageTimer()
            timer.air()
            started = time.perf_counter()
            enumeration_seconds = 0.0
            try:
                if method == "full":
                    before = time.perf_counter()
                    pool = generate(scenario, columns.flight_options, None, generation)
                    enumeration_seconds = time.perf_counter() - before
                    with GurobiAdapter(output_flag=False) as solver:
                        outcome = full_lp(scenario, columns.flight_options, pool, request, costs, generation, solver)
                    status = outcome.outcome.status.value
                    count = len(pool)
                else:
                    outcome = cg_solve(scenario, columns.flight_options, request, costs, generation, cg_config,
                                       lambda: GurobiAdapter(output_flag=False))
                    status = outcome.status.value
                    count = len(outcome.columns)
                elapsed = time.perf_counter() - started
            finally:
                timer.close()
            assert status == "optimal", status
            outcomes[method] = outcome
            save_gzip(ev.folder / f"{method}_{repetition}.json.gz", outcome)
            if repetition >= 0:
                records.append({"method": method, "repetition": repetition, "seconds": elapsed,
                    "objective": outcome.objective_value, "columns": count,
                    "stage_timings": {"candidate_generation_seconds": enumeration_seconds if method == "full" else None,
                                      **timer.times}})
        assert close_number(outcomes["full"].objective_value, outcomes["cg"].objective_value)
        # Oracle audit is deliberately outside measured optimization time.
        audit_started = time.perf_counter()
        pool = generate(scenario, columns.flight_options, None, generation)
        checked = audit(scenario, columns.flight_options, pool, request, costs, generation, cg_config,
                        outcomes["cg"], lambda: GurobiAdapter(output_flag=False))
        assert checked.passed
        assert checked.minimum_omitted_reduced_cost is None or checked.minimum_omitted_reduced_cost >= -cg_config.pricing_epsilon
        audit_seconds.append({"repetition": repetition, "seconds": time.perf_counter() - audit_started})
        save_gzip(ev.folder / f"audit_{repetition}.json.gz", checked)
    full_times = [r["seconds"] for r in records if r["method"] == "full"]
    cg_times = [r["seconds"] for r in records if r["method"] == "cg"]
    speedup = statistics.median(full_times) / statistics.median(cg_times)
    return {"verdict": "passed", "summary": f"LP objectives and pricing audit agree; observed full/CG median speedup={speedup:.3f}",
            "optimization_status": "lp_optimal",
            "records": records, "oracle_audit_times": audit_seconds, "observed_speedup": speedup,
            "speed_conclusion": "CG faster on this instance" if speedup > 1 else "CG not faster on this instance",
            "timing_note": "Full-universe validation audit timed separately from the algorithm pipeline. CG generation is interleaved with pricing (null, not zero). Stage categories may overlap."}


def run_air_oracle(job, ev):
    from backend.application.case_service import load_case
    from backend.core import generate_aircraft_strings, generate_crew_pairings
    from backend.core import IntegratedRecoveryRequest, solve_integrated_fixed_column_oracle, solve_benders_with_branch_and_price
    from backend.solver import GurobiAdapter
    bundle = load_case(job["config"]["case_id"])["solve_bundle"]
    save_gzip(ev.folder / "input.json.gz", bundle)
    scenario, columns, capacity, costs, configs = air_inputs(bundle)
    records = []
    for repetition in range(-1, job["config"].get("repeats", 3)):
        pair = {}
        for method in (("integrated", "benders_bp") if repetition % 2 == 0 else ("benders_bp", "integrated")):
            ev.progress(stage="oracle_comparison", method=method, repetition=repetition)
            timer = StageTimer()
            timer.air()
            started = time.perf_counter()
            try:
                if method == "integrated":
                    strings = generate_aircraft_strings(scenario, columns.flight_options, None, configs["flight_string_generation"])
                    pairings = generate_crew_pairings(scenario, columns.flight_options, None, configs["crew_pairing_generation"])
                    full = columns.model_copy(update={"aircraft_strings": list(strings), "crew_pairings": list(pairings)})
                    request = IntegratedRecoveryRequest(scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id)
                    with GurobiAdapter(output_flag=False) as solver:
                        outcome = solve_integrated_fixed_column_oracle(
                            scenario, full, request, capacity, costs, solver)
                    objective, status = outcome.objective_value, outcome.status.value
                    if status == "optimal":
                        assert outcome.diagnostics["all_constraints_satisfied"]
                        assert close_number(objective, outcome.best_bound)
                else:
                    outcome = solve_benders_with_branch_and_price(
                        scenario, columns, capacity, costs, configs["flight_string_generation"],
                        configs["crew_pairing_generation"], configs["aircraft_string_cg"],
                        configs["crew_pairing_cg"], configs["benders_cg"], configs["branch_and_price"],
                        solver_factory=lambda: GurobiAdapter(output_flag=False), event_sink=ev.event)
                    objective, status = outcome.objective_value, outcome.status.value
                    if status == "optimal":
                        diagnostics = outcome.diagnostics
                        audit = diagnostics.get("integrated_audit") or diagnostics.get("phase11_diagnostics", {}).get("integrated_audit")
                        assert audit and audit["all_constraints_satisfied"]
                        assert close_number(outcome.lower_bound, outcome.upper_bound)
                        assert close_number(objective, outcome.upper_bound)
                elapsed = time.perf_counter() - started
            finally:
                timer.close()
            assert status == "optimal", status
            pair[method] = objective
            save_gzip(ev.folder / f"{method}_{repetition}.json.gz",
                      outcome.to_dict() if hasattr(outcome, "to_dict") else outcome)
            if repetition >= 0:
                records.append({"method": method, "repetition": repetition, "objective": objective,
                                "seconds": elapsed, "stage_timings": dict(timer.times)})
        assert close_number(pair["integrated"], pair["benders_bp"])
        expected = load_case(job["config"]["case_id"])["case"]["expected"]
        assert close_number(pair["integrated"], expected["objective_total"])
    return {"verdict": "passed", "summary": "Integrated oracle and exact Benders/BP agree in all repetitions",
            "optimization_status": "optimal",
            "records": records, "timing_note": "Independent diagnostics are retained; stage times may overlap."}


def micro_request(variant="normal", objective="tianchi_2017"):
    import runpy
    from backend.business.xma.schema import Scene, SourceRef, XmaAircraft
    request = runpy.run_path(str(ROOT / "tests/unit/test_xma_recovery.py"))["micro_request"](objective)
    a, b = request.dataset.flights
    source = SourceRef(sheet="台风场景", row=2)
    if variant in ("delay", "conflict"):
        request.dataset.scenes = [Scene(
            airport="B", kind="arrival", start=a.sched_arr - timedelta(minutes=30),
            end=a.sched_arr + timedelta(minutes=30), source=source)]
        if variant == "conflict":
            request.maximum_delay_minutes = 0
    elif variant == "overflow":
        a.passengers = 12
    elif variant in ("split", "branch"):
        a.passengers = 12 if variant == "split" else 11
        for index, flight in ((3, a), (4, b)):
            request.dataset.flights.append(flight.model_copy(update={
                "flight_id": str(index), "flight_no": str(index), "original_aircraft": "U",
                "seats": 12, "passengers": 0,
                "sched_dep": flight.sched_dep + timedelta(hours=2),
                "sched_arr": flight.sched_arr + timedelta(hours=2)}))
        request.dataset.aircraft.append(XmaAircraft(
            tail_id="U", equipment="E", seats=12, initial_station="A",
            original_terminal="A", original_rotation=["3", "4"]))
        request.dataset.original_turn_minutes["3#4"] = 30
        request.maximum_delay_minutes = 0
        if variant == "branch":
            request.air_objective.aircraft_reassignment = 10
    return request


def xma_request(config, seconds):
    from backend.business.xma.importer import load_workbook, select_subset
    from backend.business.xma.schema import XmaSolveRequest
    data = select_subset(load_workbook(), config["size"], mode=config.get("mode", "fixed"),
                         seed=config.get("seed"))
    return XmaSolveRequest(
        dataset=data, algorithm=config.get("algorithm", "joint_arc_flow"),
        objective_profile=config.get("objective", "tianchi_2017"),
        delay_step_minutes=config.get("step", 60), maximum_delay_minutes=config.get("delay", 120),
        time_limit_seconds=seconds, max_assignment_options=config.get("max_assignments", 10_000_000))


def xma_solve(request, ev, tag):
    from backend.business.xma.service import solve
    ev.top_algorithm = request.algorithm
    ev.first_global_incumbent = None
    ev.first_audited_feasible = None
    ev.observation_origin = time.perf_counter() - ev.started
    ev.progress(stage="preparing", algorithm=request.algorithm, flights=len(request.dataset.flights),
                step=request.delay_step_minutes, maximum_delay=request.maximum_delay_minutes,
                objective=request.objective_profile, lower_bound=None, upper_bound=None,
                absolute_gap=None, relative_gap=None)
    save_gzip(ev.folder / (tag + "_input.json.gz"), request)
    timer = StageTimer()
    timer.xma()
    started = time.perf_counter()
    ev.observation_origin = started - ev.started
    try:
        result = solve(request, event_sink=ev.event,
                       solution_artifact_sink=lambda payload: save_gzip(ev.folder / (tag + "_selected.json.gz"), payload))
    finally:
        timer.close()
    elapsed = time.perf_counter() - started
    save_gzip(ev.folder / (tag + "_result.json.gz"), result)
    if result.get("tianchi_csv"):
        atomic_text(ev.folder / (tag + ".csv"), result["tianchi_csv"])
    validate_bounds(result)
    if result.get("business_decisions"):
        assert result["independent_audit"]["valid"]
        from backend.business.xma.evaluator import evaluate
        from backend.business.xma.schema import Decision
        audit = evaluate(request, [Decision.model_validate(x) for x in result["business_decisions"]])
        assert audit["valid"] and close_number(audit["objective"], result["objective"]["total"])
    return result, {"end_to_end_seconds": elapsed, **timer.times,
                    "first_global_incumbent_seconds": ev.first_global_incumbent,
                    "first_audited_feasible_seconds": ev.first_audited_feasible,
                    "lp_reuse_statistics": dict(timer.extra),
                    "timing_semantics": "Nested: model build includes networks; solver_seconds includes matrix extraction, native update and optimization. Do not sum nested categories."}


def xma_record(request, result, timings, repetition):
    scope = request.model_dump(mode="json")
    for key in ("algorithm", "time_limit_seconds", "max_benders_iterations", "max_bp_nodes",
                "max_cg_iterations", "oracle_path_limit", "mip_gap", "max_assignment_options"):
        scope.pop(key, None)
    return {"method": request.algorithm, "repetition": repetition, "comparison_key": digest(scope),
            "optimization_status": result["status"], "objective": (result.get("objective") or {}).get("total"),
            "diagnostics": result["diagnostics"], "seconds": timings["end_to_end_seconds"],
            "stage_timings": timings, "audit_valid": (result.get("independent_audit") or {}).get("valid"),
            "first_global_incumbent_seconds": timings.get("first_global_incumbent_seconds"),
            "first_audited_feasible_seconds": timings.get("first_audited_feasible_seconds"),
            "flights": len(request.dataset.flights), "tails": len(request.dataset.aircraft),
            "selection": clean(request.dataset.subset_selection)}


def run_xma_micro(job, ev):
    config = job["config"]
    request = micro_request(config["variant"], config["objective"])
    records = []
    methods = ("joint_arc_flow", "joint_path_oracle", "benders_joint", "benders_cg_bp")
    for algorithm in methods:
        changed = request.model_copy(update={"algorithm": algorithm, "time_limit_seconds": job["solver_seconds"]})
        result, timings = xma_solve(changed, ev, algorithm)
        assert result["status"] == "optimal", result["diagnostics"]
        records.append(xma_record(changed, result, timings, 0))
    assert all(close_number(records[0]["objective"], r["objective"]) for r in records)
    analytic = {("normal", "tianchi_2017"): 0, ("normal", "air_linear_v1"): 0,
                ("overflow", "tianchi_2017"): 16, ("overflow", "air_linear_v1"): 10000,
                ("delay", "tianchi_2017"): 110}
    if (config["variant"], config["objective"]) in analytic:
        assert close_number(records[0]["objective"], analytic[config["variant"], config["objective"]])
    return {"verdict": "passed", "summary": f"Four architectures agree; objective={records[0]['objective']}",
            "records": records, "fixture_source": "existing tests/unit/test_xma_recovery.py + documented variants"}


def run_xma_scale(job, ev):
    from backend.business.xma.service import precheck
    request = xma_request(job["config"], job["solver_seconds"])
    save_gzip(ev.folder / "input.json.gz", request)
    ev.progress(stage="readiness", algorithm=request.algorithm, flights=len(request.dataset.flights))
    readiness = precheck(request)
    atomic_json(ev.folder / "readiness.json", readiness)
    if job["config"].get("precheck_only") or not readiness["solve_ready"]:
        return {"verdict": "input_limit" if not readiness["solve_ready"] else "completed",
                "summary": "Candidate/assignment readiness only; optimization not run",
                "readiness": readiness, "optimization_status": "not_run",
                "flights": len(request.dataset.flights), "selection": clean(request.dataset.subset_selection)}
    result, timings = xma_solve(request, ev, "solve")
    record = xma_record(request, result, timings, 0)
    return {"verdict": "passed" if result["status"] in ("optimal", "infeasible") else "inconclusive",
            "summary": f"{request.algorithm}: {result['status']}; objective={record['objective']}",
            "records": [record], "optimization_status": result["status"], "readiness": readiness}


def run_xma_timing(job, ev):
    config = job["config"]
    request = xma_request(config, job["solver_seconds"])
    records = []
    for repetition in range(-1, 3):
        ev.progress(stage="timing_repetition", repetition=repetition)
        result, timings = xma_solve(request, ev, f"repetition_{repetition}")
        record = xma_record(request, result, timings, repetition)
        record["first_global_incumbent_observed_seconds"] = ev.first_global_incumbent
        record["first_incumbent_note"] = "Observed from this solve's entry; only global feasible upper-bound events count. Missing telemetry remains null."
        records.append(record)
    return {"verdict": "completed", "summary": f"{request.algorithm}: " + ", ".join(
                r["optimization_status"] for r in records if r["repetition"] >= 0),
            "records": records, "timing_note": "One warmup (-1), 3 measurements. Compare only identical comparison_key and certified quality."}


def run_stop_controls(job, ev):
    from backend.business.xma import service
    from backend.application.case_service import load_case
    from backend.application.solve_service import solve_request
    from backend.schemas.result import SolveRequest
    outcomes = []
    for algorithm in ("joint_arc_flow", "joint_path_oracle", "benders_joint", "benders_cg_bp"):
        conflict = micro_request("conflict").model_copy(update={"algorithm": algorithm})
        assert service.precheck(conflict)["solve_ready"]
        result, timings = xma_solve(conflict, ev, "conflict_" + algorithm)
        assert result["status"] == "infeasible", result["diagnostics"]
        outcomes.append({"algorithm": algorithm, "case": "valid_but_infeasible", "status": result["status"]})
        request = micro_request().model_copy(update={"algorithm": algorithm})
        before = time.perf_counter()
        stopped = service.solve(request, cancel_check=lambda: True, event_sink=ev.event)
        assert stopped["status"] == "aborted" and not stopped.get("business_decisions")
        assert time.perf_counter() - before < 10
        outcomes.append({"algorithm": algorithm, "case": "immediate_cancel", "status": stopped["status"]})
    bundle = load_case("benchmark-disruption-recovery")["solve_bundle"]
    before = time.perf_counter()
    stopped_air = solve_request(SolveRequest.model_validate(bundle), cancel_check=lambda: True,
                                runtime_controls={"time_limit_seconds": 10}, event_sink=ev.event)
    assert stopped_air.status.value == "aborted"
    assert stopped_air.objective is None and not stopped_air.resolved_flights
    assert time.perf_counter() - before < 10
    outcomes.append({"algorithm": "AIR_benders_bp", "case": "immediate_cancel", "status": stopped_air.status.value})
    bundle = load_case("crew-recovery-integrality")["solve_bundle"]
    limited = solve_request(SolveRequest.model_validate(bundle),
        runtime_controls={"max_benders_iterations": 1, "max_branch_nodes": 1, "time_limit_seconds": 20})
    assert limited.status.value != "optimal"
    if limited.objective is None:
        assert not limited.resolved_flights
    else:
        assert limited.diagnostics.integrated_audit_pass is True
        assert len(limited.resolved_flights)==len(bundle["scenario"]["flights"])
        validate_bounds(limited.model_dump(mode="json"))
    outcomes.append({"case": "AIR_iteration_node_limit", "status": limited.status.value,
                     "diagnostics": clean(limited.diagnostics)})
    return {"verdict": "passed", "summary": "Certified infeasibility, cancellation and restricted nonoptimal output verified",
            "outcomes": outcomes}


def run_metamorphic(job, ev):
    from copy import deepcopy
    from backend.application.case_service import load_case
    from backend.business.xma.rules import generate_options
    records = []
    objectives = {}
    for case in ("passenger-capacity-constrained", "passenger-capacity-relaxed"):
        bundle = load_case(case)["solve_bundle"]
        result, _ = air_solve(bundle, job, ev, case)
        assert result["status"] == "optimal"
        objectives[case] = result["objective"]["total"]
    assert objectives["passenger-capacity-relaxed"] <= objectives["passenger-capacity-constrained"] + 1e-6
    base = load_case("passenger-capacity-constrained")["solve_bundle"]
    reordered = deepcopy(base)
    for key in ("airports", "flights", "aircraft", "crew", "passengers", "airport_intervals"):
        reordered["scenario"][key].reverse()
    for key in ("flight_options", "passenger_itineraries"):
        reordered["recovery_columns"][key].reverse()
    repeated, _ = air_solve(reordered, job, ev, "reordered")
    assert close_number(repeated["objective"]["total"], objectives["passenger-capacity-constrained"])
    original_ids = {x["option_id"] for x in base["recovery_columns"]["flight_options"]
                    if x["departure_delay_minutes"] == 0}
    restricted = deepcopy(base)
    restricted["recovery_columns"]["flight_options"] = [
        x for x in restricted["recovery_columns"]["flight_options"] if x["option_id"] in original_ids]
    restricted["recovery_columns"]["passenger_itineraries"] = [
        x for x in restricted["recovery_columns"]["passenger_itineraries"]
        if all(s.get("flight_option_id") in original_ids for s in x["segments"])]
    restricted["capacity_profile"]["seat_capacity_by_option_id"] = {
        k: v for k, v in restricted["capacity_profile"]["seat_capacity_by_option_id"].items() if k in original_ids}
    smaller, _ = air_solve(restricted, job, ev, "restricted_candidates")
    assert smaller["status"] == "optimal"
    assert objectives["passenger-capacity-constrained"] <= smaller["objective"]["total"] + 1e-6
    previous = None
    previous_ids = set()
    for step in (60, 30):
        request = micro_request("delay").model_copy(update={"delay_step_minutes": step, "maximum_delay_minutes": 120})
        ids = {x.option_id for x in generate_options(request)}
        if previous_ids:
            assert previous_ids <= ids
        result, timing = xma_solve(request, ev, f"xma_step_{step}")
        assert result["status"] == "optimal"
        if previous is not None:
            assert result["objective"]["total"] <= previous + 1e-6
        previous, previous_ids = result["objective"]["total"], ids
        records.append(xma_record(request, result, timing, 0))
    return {"verdict": "passed", "summary": "Capacity relaxation, candidate expansion, order invariance verified",
            "air_objectives": objectives, "restricted_objective": smaller["objective"]["total"], "records": records}


def run_jar(job, ev):
    import re
    from backend.business.xma.evaluator import evaluate, export_csv
    from backend.business.xma.schema import Decision, XmaSolveRequest
    fixture = ROOT / "docs/codex_reports/xma_jar_validation_20261008"
    request = XmaSolveRequest.model_validate(read_json(fixture / "request.json"))
    result = read_json(fixture / "result.json")
    decisions = [Decision.model_validate(x) for x in result["business_decisions"]]
    audit = evaluate(request, decisions)
    assert audit["valid"]
    atomic_json(ev.folder / "independent_rescore.json", audit)
    java = job.get("config", {}).get("java_executable") or shutil.which("java")
    if not java and os.environ.get("JAVA_HOME"):
        candidate = Path(os.environ["JAVA_HOME"]) / "bin/java.exe"
        java = str(candidate) if candidate.is_file() else None
    if not java:
        return {"verdict": "dependency_limited", "summary": "Java unavailable; independent rescore passed, official JAR NOT rerun"}
    version = subprocess.run([java, "-version"], capture_output=True, timeout=15)
    atomic_json(ev.folder / "java_runtime.json", {
        "executable": java, "version": (version.stdout + version.stderr).decode("utf-8", errors="replace"),
        "executable_sha256": hashlib.sha256(Path(java).read_bytes()).hexdigest(),
        "installed_by_campaign": False})
    csv = ev.folder / "result.csv"
    atomic_text(csv, export_csv(request, decisions))
    jar = next((ROOT / "data").rglob("XMAEvaluation.jar"))
    command = [java, "-Xmx512m", "-Duser.timezone=Asia/Shanghai", "-jar", str(jar),
               str(fixture / "subset_fixture.xlsx"), str(csv)]
    completed = subprocess.run(command, cwd=ev.folder, capture_output=True, timeout=90)
    (ev.folder / "jar_stdout.txt").write_bytes(completed.stdout)
    (ev.folder / "jar_stderr.txt").write_bytes(completed.stderr)
    matches = re.findall(r"(-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)\s*$",
                         completed.stdout.decode("utf-8", errors="replace"))
    score = float(matches[-1]) if matches else None
    assert completed.returncode == 0 and close_number(score, audit["score"])
    return {"verdict": "passed", "summary": "Official JAR and independent evaluator agree on the documented derived fixture",
            "official_score": score, "independent_score": audit["score"], "fixture_is_synthetic_derivative": True}


def pytest_workspace(folder):
    """Keep nested test artifacts below MAX_PATH without changing Windows settings."""
    configured = os.environ.get("FLIGHT_VALIDATION_TEMP_ROOT")
    root = Path(configured).resolve() if configured else None
    if root is not None and len(str(root)) <= 80:
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = None
    workspace = Path(tempfile.mkdtemp(prefix="frv_", dir=root)).resolve()
    atomic_json(Path(folder) / "pytest_workspace.json", {
        "path": str(workspace), "path_length": len(str(workspace)),
        "reason": "Short isolated workspace for nested Windows artifact paths",
        "retained_for_review": True})
    return workspace


def run_pytest(job, ev):
    import pytest
    counts = Counter()
    failed_causes = []
    class Telemetry:
        def pytest_runtest_logstart(self, nodeid, location):
            ev.license_limited = ev.resource_limited = False
        def pytest_runtest_logreport(self, report):
            if report.failed:
                detail = str(report.longrepr)
                failed_causes.append("resource_limited" if ev.resource_limited or memory_failure(detail) else
                                     "license_limited" if ev.license_limited or "10010" in detail else "failed")
            if report.when == "call" or report.failed:
                counts[report.outcome] += 1
                ev.progress(stage="pytest", test=report.nodeid, counts=dict(counts))
    xml = ev.folder / "junit.xml"
    workspace = pytest_workspace(ev.folder)
    args = [*job["config"]["paths"], "-q", "--tb=short", "--junitxml", str(xml),
            "--basetemp", str(workspace / "t"), "-o", "cache_dir=" + str(workspace / "cache")]
    code = int(pytest.main(args, plugins=[Telemetry()]))
    failures, skipped = [], []
    if xml.exists():
        for case in ET.parse(xml).iter("testcase"):
            for node in list(case):
                if node.tag in ("failure", "error"):
                    failures.append({"test": case.attrib.get("name"), "detail": node.text or node.attrib.get("message", "")})
                if node.tag == "skipped":
                    skipped.append(case.attrib.get("name"))
    if code == 0:
        verdict = "passed"
    elif failed_causes and all(cause in ("resource_limited", "license_limited") for cause in failed_causes):
        verdict = "resource_limited" if "resource_limited" in failed_causes else "license_limited"
    elif failures and all("10010" in x["detail"] or "size-limited" in x["detail"] for x in failures):
        verdict = "license_limited"
    elif code in (2, 4, 5):
        verdict = "error"
    else:
        verdict = "failed"
    return {"verdict": verdict, "summary": f"pytest exit={code}; {dict(counts)}; skipped={len(skipped)}",
            "counts": dict(counts), "skipped_tests": skipped, "failures": failures, "pytest_exit": code,
            "pytest_workspace": str(workspace),
            "blocked_scopes": job.get("blocks", []) if verdict == "failed" else []}


def run_selftest(job, ev):
    config = job["config"]
    mode = config.get("mode", "normal")
    if config.get("grandchild"):
        process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(600)"],
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        atomic_json(ev.folder / "grandchild.json", {"pid": process.pid})
    if mode == "crash":
        os._exit(7)
    if mode == "memory":
        ev.progress(stage="selftest_memory")
        chunks = []
        while True:
            chunks.append(bytearray(8 * 1024 ** 2))
            time.sleep(0.01)
    if mode == "wait":
        ev.progress(stage="selftest_wait")
        time.sleep(config.get("seconds", 1))
    return {"verdict": "passed", "summary": "Harness infrastructure fixture; not a solver benchmark."}


HANDLERS = {
    "pytest": run_pytest, "air_case": run_air_case, "air_micro": run_air_case,
    "air_cg": run_air_cg, "air_oracle": run_air_oracle, "air_stress": run_air_stress,
    "xma_micro": run_xma_micro, "xma_scale": run_xma_scale, "xma_timing": run_xma_timing,
    "stop_controls": run_stop_controls, "metamorphic": run_metamorphic, "jar": run_jar,
    "selftest": run_selftest,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    job = read_json(args.job)
    ev = Evidence(args.output)
    ev.license_limited = False
    Evidence.current = ev
    ev.progress(stage="worker_start", name=job["name"], pid=os.getpid())
    stop_heartbeat = threading.Event()
    def heartbeat():
        while not stop_heartbeat.wait(15):
            try:
                ev.progress()
            except Exception:
                pass
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        if job["kind"] != "selftest":
            single_thread_air()
        result = HANDLERS[job["kind"]](job, ev)
        if job["kind"] != "pytest":
            if ev.resource_limited:
                result.update(verdict="resource_limited", summary="Native solver allocation failed; not an algorithm correctness failure")
            elif ev.license_limited:
                result.update(verdict="license_limited", summary="Gurobi 10010 size limit; not an algorithm correctness failure")
    except BaseException as exc:
        detail = traceback.format_exc()
        atomic_text(args.output / "error.txt", detail)
        if ev.resource_limited or isinstance(exc, MemoryError) or memory_failure(exc) or getattr(exc, "errno", None) == 10001:
            verdict = "resource_limited"
        elif ev.license_limited or "10010" in str(exc):
            verdict = "license_limited"
        elif isinstance(exc, AssertionError):
            verdict = "failed"
        else:
            verdict = "error"
        result = {"verdict": verdict, "reason": f"{type(exc).__name__}: {exc}",
                  "summary": f"{verdict}: {type(exc).__name__}: {exc}",
                  "blocked_scopes": job.get("blocks", []) if verdict == "failed" else []}
    finally:
        stop_heartbeat.set()
        thread.join(timeout=1)
        ev.close()
    result.update(worker_wall_seconds=time.perf_counter() - ev.started, event_count=ev.seq,
                  events_truncated=ev.truncated, source_root=str(ROOT), test_kind=job["kind"],
                  memory_limit_gib=job["memory_gib"], algorithm_scopes=job.get("requires", []))
    claims = []
    statuses = [result["optimization_status"]] if result.get("optimization_status") else []
    statuses += [r["optimization_status"] for r in result.get("records", []) if r.get("optimization_status")]
    for status in sorted(set(statuses)):
        claims.append({"optimization_status": status, "conclusion": {
            "optimal": "proved_optimal_with_audit", "infeasible": "certified_infeasible",
            "lp_optimal": "proved_LP_optimal_with_pricing_certificate",
            "feasible": "legal_feasible_only", "not_converged": "not_converged",
            "aborted": "stopped_without_optimality", "not_run": "not_solved",
        }.get(status, "no_optimality_claim")})
    if result["verdict"] in ("failed", "error", "license_limited", "resource_limited"):
        claims = [{"conclusion": "no_success_claim", "reason": result["verdict"]}]
    result["conclusions"] = claims
    atomic_json(args.output / "result.json", clean(result))
    print(json.dumps(clean({"verdict": result["verdict"], "summary": result.get("summary", result.get("reason", ""))}),
                     ensure_ascii=False), flush=True)
    return 1 if result["verdict"] in ("failed", "error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
