"""Independent small-universe checks for cuts, interruption and evidence."""
from itertools import product
from pathlib import Path
import runpy
from time import perf_counter, sleep

import pytest

from backend.business.xma.algorithms import Budget, direct
from backend.business.xma.recourse import GlobalRecourseLP
from backend.business.xma.rules import generate_options
from backend.business.xma import model as xma_model
from backend.solver.runtime import SolveBudget, SolveStopped, check_budget, use_budget

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("objective", ["tianchi_2017", "air_linear_v1"])
def test_global_lp_cuts_do_not_remove_any_feasible_integer_schedule(objective):
    request = runpy.run_path(str(ROOT / "tests/unit/test_xma_recovery.py"))["micro_request"](objective)
    options = generate_options(request)
    groups = [[o.option_id for o in options if o.flight_id == f.flight_id] for f in request.dataset.flights]
    schedules = [set(s) for s in product(*groups)]
    exact = [direct(request, options, Budget(30), schedule=s) for s in schedules]
    lp = GlobalRecourseLP(request, options)
    counts = {"feasibility": 0, "optimality": 0}
    try:
        for schedule in schedules:
            cert = lp.solve(schedule, Budget(30))
            assert cert is not None
            counts[cert["kind"]] += 1
            for other, outcome in zip(schedules, exact):
                if outcome.status != "optimal":
                    continue
                bound = cert["value"] + sum(c*(int(oid in other)-int(oid in schedule))
                                             for oid, c in cert["gradient"].items())
                assert bound <= (0 if cert["kind"] == "feasibility" else outcome.objective) + 1e-5
    finally:
        lp.close()
    assert all(counts.values())


def test_cancellation_during_build_cleans_models_and_returns_no_false_optimum(monkeypatch):
    request = runpy.run_path(str(ROOT / "tests/unit/test_xma_recovery.py"))["micro_request"]()
    created = []
    original = xma_model.new_model
    def capture(name):
        result = original(name)
        created.append(result[0])
        add = result[0].addVar
        result[0].created_vars = 0
        def counted(*args, **kwargs):
            var = add(*args, **kwargs)
            result[0].created_vars += 1
            return var
        result[0].addVar = counted
        return result
    monkeypatch.setattr(xma_model, "new_model", capture)
    def cancelled():
        return bool(created and created[-1].created_vars > 4)
    result = direct(request, generate_options(request), Budget(30, cancel_check=cancelled))
    assert result.status == "aborted" and result.upper is None
    assert created and all(m._disposed for m in created)


def test_single_monotonic_budget_is_shared_across_nested_work():
    budget = SolveBudget(.04)
    with use_budget(budget):
        check_budget()
        sleep(.06)
        with pytest.raises(SolveStopped, match="total_time_limit"):
            check_budget()


def test_air_short_total_budget_returns_without_external_kill():
    from backend.application.solve_service import example_solve_bundle, solve_request
    from backend.schemas.result import SolveRequest
    request = SolveRequest.model_validate(example_solve_bundle("phase1_benchmark_001"))
    started = perf_counter()
    result = solve_request(request, runtime_controls={"time_limit_seconds": .001})
    assert perf_counter()-started < 2
    assert result.status.value == "not_converged"
    assert result.diagnostics.upper_bound is None and not result.selected.flight_options


def test_cancel_after_audited_air_incumbent_keeps_decisions_and_checkpoint():
    from backend.application.solve_service import example_solve_bundle, solve_request
    from backend.schemas.result import SolveRequest
    request = SolveRequest.model_validate(example_solve_bundle("phase1_benchmark_001"))
    stopped = False
    artifacts = []
    def event(payload):
        nonlocal stopped
        if payload.get("type") == "incumbent_audited":
            stopped = True
    result = solve_request(request, event_sink=event, cancel_check=lambda: stopped,
                           solution_artifact_sink=lambda payload: artifacts.append(payload) or "checkpoint")
    assert stopped
    assert result.status.value in ("aborted", "optimal")
    assert result.objective is not None and result.diagnostics.integrated_audit_pass
    assert result.selected.flight_options and artifacts
    assert any(a.get("checkpoint", {}).get("independent_audit", {}).get("all_constraints_satisfied") for a in artifacts)
    from backend.schemas.workbench import CompilePreview, DraftDocument, SnapshotRecord
    from backend.workbench.comparison import build_comparison
    from backend.workbench.visualization import build_run_visualization
    snapshot = SnapshotRecord(snapshot_id="isolated", draft_id="d", revision_id="r", content_hash="a"*64,
                              created_at="2026-11-07T00:00:00Z", solve_request=request.model_dump(mode="json"),
                              compile_preview=CompilePreview(valid=True, draft_hash="a"*64, effective_scenario=request.scenario),
                              draft_document=DraftDocument(name="audit", scenario=request.scenario))
    payload = result.model_dump(mode="json")
    assert build_comparison(snapshot, payload)["recovered_available"]
    visualization = build_run_visualization(snapshot, payload, artifacts[-1], run_id=result.run_id,
                                           optimization_status=result.status.value)
    assert visualization.mode_availability["recovered"].available


def test_global_progress_excludes_auxiliary_models_and_records_first_audit(tmp_path):
    from scripts.validation_jobs import Evidence
    ev = Evidence(tmp_path)
    ev.top_algorithm = "joint_arc_flow"
    try:
        ev.event({"type": "mip_progress", "upper_bound": 0, "metrics": {"bound_scope": "necessary_conditions"}})
        assert ev.first_global_incumbent is None
        ev.event({"type": "mip_progress", "upper_bound": 110, "metrics": {"bound_scope": "global"}})
        first = ev.first_global_incumbent
        ev.event({"type": "incumbent_audited", "upper_bound": 110})
        assert first is not None and ev.first_audited_feasible >= first
    finally:
        ev.close()


def test_air_cancellation_from_inside_python_pricing_is_not_wrapped_as_failure(monkeypatch):
    from backend.application.solve_service import example_solve_bundle, solve_request
    from backend.schemas.result import SolveRequest
    from backend.core import aircraft_string_pricing
    calls = []
    def cancelled_in_pricing():
        calls.append(1)
        raise SolveStopped("cancelled")
    monkeypatch.setattr(aircraft_string_pricing, "check_budget", cancelled_in_pricing)
    result = solve_request(SolveRequest.model_validate(example_solve_bundle("phase1_benchmark_001")))
    assert calls and result.status.value == "aborted" and result.diagnostics.upper_bound is None


def test_dominated_expensive_rebooking_elimination_preserves_optimum():
    from datetime import timedelta
    from backend.business.xma.model import build_joint
    from scripts.validation_jobs import micro_request
    request = micro_request("split")
    for f in request.dataset.flights[2:]:
        f.sched_dep += timedelta(hours=49)
        f.sched_arr += timedelta(hours=49)
        f.date = f.sched_dep.date().isoformat()
    request.dataset.adjustment_end = request.dataset.flights[-1].sched_arr + timedelta(hours=1)
    options = generate_options(request)
    objectives = []
    for enabled in (False, True):
        joint = build_joint(request, options, eliminate_dominated_rebooking=enabled)
        try:
            assert Budget(30).optimize(joint.model, mip=True)
            assert joint.model.Status == 2
            objectives.append(joint.model.ObjVal)
            if enabled:
                assert any(v.UB == 0 for v in joint.sign.values())
                assert max(abs(v.Obj) for v in joint.model.getVars()) < 1e9
        finally:
            joint.close()
    assert objectives == pytest.approx([16, 16])
