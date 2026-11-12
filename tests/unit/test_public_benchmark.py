from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from backend.benchmarks.common import digest
from backend.benchmarks.model import PublicSolveRequest, build
from backend.benchmarks.solve import execute
from backend.benchmarks.workbench import make_document
from backend.workbench.compiler import compile_draft
from backend.services.validator import validate_scenario


@pytest.fixture
def public_case():
    start = datetime(2006, 1, 7, 8, tzinfo=timezone.utc)
    def flight(fid, tail, origin, destination, offset, delay=0):
        return dict(id=fid, number=fid, tail=tail, origin=origin, destination=destination,
                    dep=start+timedelta(minutes=offset), arr=start+timedelta(minutes=offset+60),
                    delay=delay, source={"fixture": fid})
    raw = dict(source="analytical_unit_fixture", source_instance="swap-delay-40", start=start,
               end=start+timedelta(hours=6),
               flights=[flight("A1", "T1", "A", "B", 0, 40), flight("A2", "T1", "B", "A", 120),
                        flight("B1", "T2", "A", "B", 15), flight("B2", "T2", "B", "A", 135)],
               planes={tail: dict(type="TYPE", seats=[0, 0, 100], turn=30, initial="A", maintenance="NULL")
                       for tail in ("T1", "T2")}, unavailable=[], journeys=[], raw_tables={}, source_files=[],
               reference_kind="analytically_known_unit_test_not_public_experiment")
    return build(raw, target=4)


@pytest.mark.parametrize("algorithm", ["direct_mip", "integrated_oracle", "fixed_benders", "air_cg", "air_bp",
    "xma_joint_arc_flow", "xma_joint_path_oracle", "xma_benders_joint", "xma_benders_cg_bp"])
def test_all_routes_match_nonzero_analytical_optimum(public_case, algorithm):
    result = execute(public_case.model_copy(update={"algorithm": algorithm}), seconds=30)
    assert result["status"] == "optimal"
    assert result["objective"] == pytest.approx(40)
    assert result["certified_optimal"] and result["audit"]["pass"]
    assert not result["selected"]["crew_pairings"]
    assert result["lower_bound"] == pytest.approx(result["upper_bound"])


def test_legacy_crew_validation_and_public_no_dummy_crew(public_case):
    assert not validate_scenario(public_case.scenario)[1]
    legacy = public_case.scenario.model_dump(mode="json")
    legacy.pop("crew_enabled")
    assert any(issue.code == "unknown_crew" for issue in validate_scenario(legacy)[1])
    assert public_case.scenario.crew == []
    assert all(f.original_crew is None for f in public_case.scenario.flights)


def test_direct_mip_checkpoints_and_workbench_route(public_case):
    from backend.benchmarks.solve import solve_request
    checkpoints, events = [], []
    request = public_case.model_copy(update={"algorithm":"direct_mip"})
    assert compile_draft(make_document(request)).valid
    result = execute(request, seconds=30, checkpoint_sink=checkpoints.append, event_sink=events.append)
    assert result["certified_optimal"]
    assert checkpoints and all(c["audit"]["pass"] for c in checkpoints)
    assert any(e["type"] == "model_built" for e in events)
    displayed = solve_request(request, runtime_controls={"time_limit_seconds":30})
    assert displayed.status.value == "optimal"
    assert displayed.run_metadata.algorithm == "public_compact_direct_mip_v1"
    oracle_display = solve_request(public_case.model_copy(update={"algorithm":"integrated_oracle"}),
                                   runtime_controls={"time_limit_seconds":30})
    assert oracle_display.status.value == "optimal"
    assert oracle_display.objective.total == pytest.approx(displayed.objective.total)


def test_direct_mip_reports_true_infeasibility_without_preprocessor(public_case):
    data = public_case.model_dump(mode="json")
    data["scenario"]["aircraft"][0]["required_station_at_T_end"] = "B"
    data["scenario"]["aircraft"][1]["required_station_at_T_end"] = "B"
    data["problem_sha256"] = digest({k:v for k,v in data.items() if k not in ("problem_sha256", "algorithm", "backend")})
    request = PublicSolveRequest.model_validate(data).model_copy(update={"algorithm":"direct_mip"})
    # Fixed flight A1 must operate; all other legs may cancel, so force both
    # return legs as well and make both required B terminals impossible.
    data = request.model_dump(mode="json")
    for f in data["scenario"]["flights"]:
        f["strategic_flag"] = True
    data["problem_sha256"] = digest({k:v for k,v in data.items() if k not in ("problem_sha256", "algorithm", "backend")})
    request = PublicSolveRequest.model_validate(data)
    result = execute(request, seconds=30)
    assert result["status"] == "infeasible" and result["certified_infeasible"]
    assert not result.get("preprocessing_only")


def test_direct_model_limits_do_not_claim_infeasibility(public_case):
    from backend.benchmarks.direct import execute_direct
    result = execute_direct(public_case, seconds=30, max_variables=1)
    assert result["status"] == "input_limit"
    assert not result["certified_optimal"]


def test_runtime_policy_scales_with_candidates_and_assignments():
    from backend.workbench.solve_policy import recommend_time_limit
    assert [recommend_time_limit(n)["time_limit_seconds"] for n in (2, 20, 100, 500, 2000)] == [600,1800,3600,7200,14400]
    assert recommend_time_limit(5, assignment_pairs=1000001)["time_limit_seconds"] == 14400


def test_direct_passenger_capacity_matches_independent_oracle(public_case):
    from backend.schemas.passenger import PassengerCommodity
    from backend.config import PassengerItineraryGenerationConfig
    from backend.core import generate_passenger_itineraries
    first = public_case.scenario.flights[0]
    group = PassengerCommodity(pax_group_id="analytical-capacity", count=101, origin=first.origin,
        destination=first.destination, original_departure=first.sched_dep,
        scheduled_arrival=first.sched_arr, original_itinerary=[first.flight_id])
    scenario = public_case.scenario.model_copy(update={"passengers":[group]})
    itineraries = generate_passenger_itineraries(scenario, public_case.recovery_columns.flight_options, None,
        PassengerItineraryGenerationConfig.model_validate(public_case.configs["itinerary_generation"]))
    data = public_case.model_dump(mode="json")
    data.update(scenario=scenario.model_dump(mode="json"), model_type="aircraft_passenger",
                components=dict(aircraft=True, passenger=True, crew=False))
    data["recovery_columns"]["passenger_itineraries"] = [i.model_dump(mode="json") for i in itineraries]
    data["problem_sha256"] = digest({k:v for k,v in data.items() if k not in ("problem_sha256", "algorithm", "backend")})
    request = PublicSolveRequest.model_validate(data)
    direct = execute(request.model_copy(update={"algorithm":"direct_mip"}), seconds=30)
    oracle = execute(request.model_copy(update={"algorithm":"integrated_oracle"}), seconds=30)
    assert direct["certified_optimal"] and oracle["certified_optimal"]
    assert direct["objective"] == pytest.approx(oracle["objective"])
    assert direct["audit"]["breakdown"]["passenger"] == pytest.approx(101*request.costs.coefficients.unserved_passenger.value)


def test_baseline_waits_for_enter_before_any_solver_or_verification(tmp_path, monkeypatch):
    from backend.benchmarks import direct_campaign
    from backend.benchmarks.common import write_json, read_json
    write_json(tmp_path / "manifest.json", dict(jobs=[dict(id="H1", group="micro", seconds=600)]))
    write_json(tmp_path / "groups/micro.json", dict(status="prepared_not_started", jobs={}))
    def no_enter(prompt):
        raise EOFError("unit test does not press Enter")
    monkeypatch.setattr("builtins.input", no_enter)
    monkeypatch.setattr(direct_campaign, "verify", lambda *a: pytest.fail("verification started before Enter"))
    with pytest.raises(EOFError):
        direct_campaign.run_group(tmp_path, "micro")
    assert read_json(tmp_path / "groups/micro_window.json")["status"] == "waiting_for_enter"
    assert not (tmp_path / "jobs").exists()


def test_baseline_retained_checkpoint_cannot_claim_optimal(tmp_path):
    from backend.benchmarks.direct_campaign import _retained
    from backend.benchmarks.common import write_json
    write_json(tmp_path / "checkpoint.json", dict(objective=240, lower_bound=150, audit={"pass":True}))
    result = _retained(tmp_path, dict(status="timed_out", certified_optimal=True))
    assert result["upper_bound"] == 240 and result["lower_bound"] == 150
    assert result["audit_pass"] and not result["certified_optimal"]


def test_direct_cancel_after_incumbent_retains_plan_without_optimal_label(public_case):
    cancelled = [False]
    saved = []
    def checkpoint(value):
        saved.append(value)
        cancelled[0] = True
    result = execute(public_case.model_copy(update={"algorithm":"direct_mip"}), seconds=30,
                     cancel_check=lambda: cancelled[0], checkpoint_sink=checkpoint)
    assert saved and all(s["audit"]["pass"] for s in saved)
    assert result["status"] == "aborted" and not result["certified_optimal"]
    assert result["audit"]["pass"] and result["upper_bound"] is not None


def test_baseline_group_collects_worker_evidence_after_enter(tmp_path, monkeypatch):
    from backend.benchmarks import direct_campaign
    from backend.benchmarks.common import write_json, read_json
    job = dict(id="H1", group="micro", instance="analytical", source="unit_fixture", algorithm="direct_mip",
               backend="highs", seconds=600, memory_gib=6, watchdog_grace_seconds=120,
               scale=dict(flights=4, candidates=24, assignment_pairs=48))
    manifest = dict(jobs=[job], live_root=str(tmp_path), manifest_sha256="unit-fixture")
    write_json(tmp_path / "manifest.json", manifest)
    write_json(tmp_path / "groups/micro.json", dict(status="prepared_not_started", jobs={}))
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    monkeypatch.setattr(direct_campaign, "verify", lambda folder: manifest)
    class FinishedWorker:
        def __init__(self, command, **kwargs):
            write_json(Path(command[-1]) / "result.json", dict(status="optimal", objective=40,
                       lower_bound=40, upper_bound=40, certified_optimal=True, audit_pass=True))
        def poll(self): return 0
        def peak_commit(self): return 0
        def close(self): pass
    from pathlib import Path
    monkeypatch.setattr("scripts.validation_campaign.GuardedChild", FinishedWorker)
    state = direct_campaign.run_group(tmp_path, "micro")
    assert state["status"] == "completed"
    assert read_json(tmp_path / "jobs/H1/result.json")["certified_optimal"]
    assert read_json(tmp_path / "summary_micro.json")["counts"] == {"optimal":1}


def test_actual_boundary_may_differ_from_planned_rotation_only_when_explicit(public_case):
    raw = public_case.scenario.model_dump(mode="json")
    raw["aircraft"][0]["initial_station_at_t"] = "B"
    assert not validate_scenario(raw)[1]
    raw["aircraft"][0].pop("boundary_from_fixed_context")
    assert any(i.code == "initial_station_mismatch" for i in validate_scenario(raw)[1])


def test_snapshot_rejects_data_or_display_tampering(public_case):
    document = make_document(public_case)
    assert compile_draft(document).valid
    damaged = public_case.model_dump(mode="json")
    damaged["candidate_policy"]["max_delay_minutes"] += 1
    with pytest.raises(ValueError, match="fingerprint"):
        PublicSolveRequest.model_validate(damaged)
    document.scenario["flights"][0]["max_delay"] += 1
    assert not compile_draft(document).valid


def test_frozen_provenance_does_not_inherit_live_repository_head(tmp_path, monkeypatch):
    from backend.benchmarks.common import frozen_repository_state, write_json
    from backend.workbench import storage
    source = tmp_path / "source"
    source.mkdir()
    manifest = dict(schema_version="public-campaign-1.0", git_commit="frozen-commit", sources={"frozen.py": "hash"})
    manifest["manifest_sha256"] = digest(manifest)
    write_json(tmp_path / "manifest.json", manifest)
    monkeypatch.setattr(storage, "ROOT", source)
    assert frozen_repository_state(source)["git_commit"] == "frozen-commit"
    assert storage._repository_state()["source_manifest_sha256"] == manifest["manifest_sha256"]
    manifest["git_commit"] = "tampered"
    write_json(tmp_path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="fingerprint"):
        frozen_repository_state(source)


def test_cancel_and_tiny_time_budget_do_not_fake_optimality(public_case):
    result = execute(public_case, seconds=30, cancel_check=lambda: True)
    assert result["status"] == "aborted"
    assert not result["certified_optimal"]
    timed = execute(public_case, seconds=.0001)
    assert timed["status"] == "not_converged"
    assert not timed["certified_optimal"]


def test_component_lp_pricing_and_integer_certificates(public_case):
    from backend.benchmarks.components import execute as components
    solution = execute(public_case.model_copy(update={"algorithm": "integrated_oracle"}), seconds=30)
    proof = components(public_case, solution["selected"]["flight_options"], seconds=30)
    assert proof["status"] == "passed"
    assert proof["pricing_audit"]["passed"]


def test_roadef_time_offsets_and_comment_terminator(tmp_path):
    from backend.benchmarks.roadef import timestamp, rows
    assert timestamp("07/01/06", "01:30-1").day == 6
    assert timestamp("07/01/06", "23:59+1").day == 8
    p = tmp_path / "aircraft.csv"
    p.write_text("% comment\nA320#1 A320\n#\nnot read\n")
    assert rows(p) == [{"line": 2, "tokens": ["A320#1", "A320"]}]


def test_hdf_metadata_parser_never_unpickles_executable_data():
    from backend.benchmarks.delft import _column_names
    assert _column_names(b"(lp1\nS'ORIGIN'\np2\naS'DEST'\np3\na.") == ["ORIGIN", "DEST"]
    with pytest.raises(ValueError):
        _column_names(b"cos\nsystem\n(S'echo unsafe'\ntR.")


def test_hdf_categories_are_business_identifiers_across_chunks(tmp_path):
    import h5py
    import numpy as np
    from backend.benchmarks.delft import iter_records
    path = tmp_path / "publisher.h5"
    dtype = np.dtype([("index", "i8"), ("values_block_0", "i1", (1,))])
    with h5py.File(path, "w") as h:
        table = h.create_dataset("csv/table", data=np.array([(10, [1]), (11, [0])], dtype=dtype))
        table.attrs["values_block_0_kind"] = np.bytes_(b"(lp0\nS'TAIL_NUMBER'\np1\na.")
        table.attrs["values_block_0_dtype"] = np.bytes_(b"int8")
        table.attrs["values_block_0_meta"] = np.bytes_(b"category")
        h.create_dataset("csv/meta/values_block_0/meta/table", data=np.array(
            [(0, b"TAIL-A"), (1, b"TAIL-B")], dtype=[("index", "i8"), ("values", "S8")]))
    records = list(iter_records(path, chunk_size=1))
    assert [r["TAIL_NUMBER"] for r in records] == ["TAIL-B", "TAIL-A"]
    assert [r["_source_row"] for r in records] == [0, 1]
    assert [r["_source_index"] for r in records] == [10, 11]


def test_native_checker_exit_zero_cannot_override_violations(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from backend.benchmarks.external import CHECK_FILES, check, historical_comparison
    exe = tmp_path / "extracted/Checker-B-2/solutionChecker-win32.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"mock checker")
    target = tmp_path / "export"
    target.mkdir()
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        results = target / "results"
        results.mkdir()
        for name in CHECK_FILES:
            (results / name).write_text("invalid rotation" if name == "checkRotation.txt" else "")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    monkeypatch.setattr("backend.benchmarks.external.subprocess.run", run)
    evidence = check(tmp_path, target)
    assert not evidence["passed"] and not evidence["historical_comparison_eligible"]
    assert len(calls) == 1  # Cost cannot become a historical score for this solution.
    assert not historical_comparison(evidence, {"value": 1})["eligible"]
    with pytest.raises(ValueError, match="stale"):
        check(tmp_path, target)


def test_stage_gate_rejects_partial_micro_proofs_and_mismatched_optima():
    from backend.benchmarks.campaign import ALGORITHMS, correctness_gate
    jobs = [dict(id=str(i), kind="solve", phase="correctness", instance="micro-known", algorithm=a)
            for i, a in enumerate(ALGORITHMS)]
    state = {"jobs": {j["id"]: dict(certified_optimal=True, objective=40) for j in jobs}}
    manifest = {"jobs": jobs}
    assert correctness_gate(manifest, state)["passed"]
    state["jobs"]["1"] = dict(certified_optimal=False, objective=None)
    assert not correctness_gate(manifest, state)["passed"]
    state["jobs"]["1"] = dict(certified_optimal=True, objective=41)
    assert not correctness_gate(manifest, state)["passed"]


def test_resume_charges_unrecorded_active_work_once():
    from backend.benchmarks.campaign import recover_interrupted_budget
    state = dict(elapsed_seconds=10, phase_elapsed={"correctness": 10}, active_started_at="2026-11-11T00:00:00+00:00",
                 active=dict(id="J1", phase="correctness", kind="solve", seconds=120))
    now = datetime(2026, 11, 11, 1, tzinfo=timezone.utc)
    recover_interrupted_budget(state, now=now)
    assert state["elapsed_seconds"] == 175 and state["phase_elapsed"]["correctness"] == 175
    recover_interrupted_budget(state, now=now)
    assert state["elapsed_seconds"] == 175


def test_refreeze_preserves_samples_tasks_and_budget_and_rejects_tampering(tmp_path, monkeypatch):
    from backend.benchmarks import campaign
    from backend.benchmarks.common import write_json, read_json, file_hash, digest
    previous, target = tmp_path / "previous", tmp_path / "replacement"
    for name in ("inputs", "drafts", "reference-2019", "source"):
        (previous / name).mkdir(parents=True)
    for name in ("frontend/dist", "frontend/workbench-v3"):
        (tmp_path / name).mkdir(parents=True)
        (tmp_path / name / "index.html").write_text("unit fixture")
    write_json(previous / "inputs/I.json", {"unit_fixture": 1})
    entry = dict(id="I", path="inputs/I.json", sha256=file_hash(previous / "inputs/I.json"))
    write_json(previous / "registry.json", [entry])
    for name in ("conversion_failures.json", "source_connections.json", "source_references.json", "reference-2019/summary.json"):
        write_json(previous / name, [])
    (previous / "reference-2019/rows.jsonl").write_text("")
    jobs = [dict(id="J1", kind="solve", phase="correctness", instance="I", algorithm="air_bp", backend="highs", warmup=False)]
    manifest = dict(jobs=jobs, budget_hours=24, sources={"../inputs/I.json": entry["sha256"]},
                    registry_sha256=file_hash(previous / "registry.json"))
    manifest["manifest_sha256"] = digest(manifest)
    write_json(previous / "manifest.json", manifest)
    write_json(previous / "state.json", dict(status="completed", elapsed_seconds=30, phase_elapsed={"correctness": 25}))
    def snapshot(folder):
        (folder / "source").mkdir()
        path = folder / "source/frozen.py"
        path.write_text("# unit code fixture\n")
        return {"frozen.py": file_hash(path)}
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    monkeypatch.setattr(campaign, "snapshot_sources", snapshot)
    monkeypatch.setattr(campaign.subprocess, "check_output", lambda *args, **kwargs: "unit-commit\n")
    campaign.refreeze(previous, target, reason="unit environment repair")
    fresh = read_json(target / "manifest.json")
    assert fresh["jobs"] == jobs
    assert (target / "inputs/I.json").read_bytes() == (previous / "inputs/I.json").read_bytes()
    assert read_json(target / "state.json")["elapsed_seconds"] == 30
    assert fresh["prior_budget"]["phase_elapsed"]["correctness"] == 25
    campaign._verify(target, fresh)
    write_json(target / "inputs/I.json", {"unit_fixture": 2})
    with pytest.raises(ValueError, match="changed"):
        campaign._verify(target, fresh)


def test_public_snapshot_worker_api_and_visualization(public_case, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api import workbench_v2
    from backend.main import app
    from backend.workbench import worker
    from backend.workbench.storage import WorkbenchStore
    from backend.schemas.workbench import CompilePreview, JobStatus
    store = WorkbenchStore(tmp_path / "isolated-workbench")
    monkeypatch.setattr(workbench_v2, "get_workbench_store", lambda: store)
    monkeypatch.setattr(worker, "WorkbenchStore", lambda: store)
    client = TestClient(app)
    document = make_document(public_case).model_dump(mode="json")
    response = client.post("/api/v2/drafts", json={"document": document})
    assert response.status_code == 201
    draft = response.json()
    compiled = client.post(f"/api/v2/drafts/{draft['draft_id']}/compile")
    assert compiled.json()["valid"]
    snapshot = store.create_snapshot(draft["draft_id"], draft["working_hash"], CompilePreview.model_validate(compiled.json()))
    run = store.create_run(snapshot, "detailed")
    assert worker.execute_run(run.run_id) == 0
    done = store.get_run(run.run_id)
    assert done.job_status == JobStatus.COMPLETED and done.optimization_status == "optimal"
    assert done.result["objective"]["total"] == pytest.approx(40)
    artifact = store.get_run_solution_artifact(run.run_id)
    assert artifact["public_evidence"]["audit"]["pass"]
    assert artifact["public_evidence"]["problem_sha256"] == public_case.problem_sha256
    visual = client.get(f"/api/v2/runs/{run.run_id}/visualization")
    assert visual.status_code == 200
    assert visual.json()["mode_availability"]["recovered"]["available"]
    assert store.list_events(run.run_id)[-1].event_type == "run_completed"


def test_business_metrics_keep_boarding_exposure_separate_from_passenger_recovery(public_case):
    from backend.benchmarks.analysis import business_metrics
    evidence = execute(public_case.model_copy(update={"algorithm": "integrated_oracle"}), seconds=30)
    metrics = business_metrics(public_case.model_dump(mode="json"), evidence)
    assert metrics["cancelled_flights"] == 0 and metrics["delayed_flights"] == 1
    assert metrics["total_departure_delay_minutes"] == 40
    assert metrics["reassigned_flights"] == 2
    assert metrics["optimized_passengers"] == 0
    assert not business_metrics({}, {"audit": {"pass": False}})["eligible"]


def test_connection_evaluation_does_not_invent_missing_context_or_od_demand():
    from backend.benchmarks.analysis import connection_impact
    records = [dict(id="F1", number="1", dep="2006-01-07T08:00:00+00:00", arr="2006-01-07T09:00:00+00:00", origin="A", destination="B", delay=0),
               dict(id="F2", number="2", dep="2006-01-07T09:30:00+00:00", arr="2006-01-07T10:30:00+00:00", origin="B", destination="C", delay=0)]
    public = dict(source=dict(records=records), fixed_context=dict(flights=[]), recovery_columns=dict(flight_options=[
        dict(option_id="C1", base_flight_id="F1", operation_type="cancel")]))
    evidence = dict(selected=dict(flight_options=["C1"]))
    row = dict(first_flight_no="1", second_flight_no="2", planned_departure_time=records[0]["dep"],
        planned_conn_departure_time=records[1]["dep"], planned_origin="A", planned_connection="B", planned_destination="C",
        _source_row=42, num_passengers=7, first_in_window=True, second_in_window=False)
    impact = connection_impact(public, evidence, [row], {"B": 20})
    assert impact["counts"]["newly_broken_connection_boardings"] == 7
    assert impact["records"][0]["first_in_window"] and not impact["records"][0]["second_in_window"]
    public["fixed_context"]["flights"] = []
    public["source"]["records"] = records[:1]
    missing = connection_impact(public, evidence, [row], {"B": 20})
    assert missing["counts"]["unknown_records"] == 1
    assert "newly_broken_connection_boardings" not in missing["counts"]


def test_publisher_statistics_exclude_illegal_records_and_preserve_time_definitions(tmp_path):
    import json
    from backend.benchmarks.analysis import publisher_distributions
    base = dict(file="unit-fixture.xlsx", sheet="reference", kind="run_observation", publisher_status=101)
    records = [{**base, "eligible_reference": legal, "cells": {
        "Cost of Disruption": {"value": cost, "seconds": None},
        "Iterationtime": {"value": "00:01:00", "seconds": 60},
        "Iterationsetup": {"value": "00:00:05", "seconds": 5}}} for legal, cost in ((True, 10), (False, -1))]
    path = tmp_path / "rows.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    summary = publisher_distributions(path)[0]
    assert summary["observations"] == 2 and summary["eligible"] == 1
    assert summary["metrics"]["cost of disruption"]["median"] == 10
    assert summary["metrics"]["iterationtime_seconds"]["median"] == 60
    assert summary["metrics"]["iterationsetup_seconds"]["median"] == 5


def test_swallowed_license_error_is_not_algorithm_nonconvergence():
    from backend.benchmarks.common import solver_failure
    evidence = dict(status="not_converged", core=dict(status="error", termination_reason="solver_error",
        diagnostics=dict(solver=dict(error_code=10010, error_message="size-limited license"))))
    assert solver_failure(evidence)["status"] == "license_limited"
    assert evidence["status"] == "not_converged"  # Classification must preserve raw records.
    assert solver_failure(dict(core=dict(status="not_converged", diagnostics={}))) is None


def test_historical_references_include_qualification_page_and_ignore_inf(tmp_path):
    from backend.benchmarks.external import historical_references, historical_comparison
    (tmp_path / "verification").mkdir()
    (tmp_path / "documentation").mkdir()
    (tmp_path / "verification/official_results_table_2.csv").write_text('Equipe,B01,X01\nTeam,INF,-2\n', encoding="utf-8")
    (tmp_path / "documentation/resultat_qualif.php.html").write_text(
        '<table><tr><th>Team</th><th>A01</th></tr><tr><td>T1</td><td>10,5</td></tr><tr><td>T2</td><td>8,25</td></tr></table>', encoding="utf-8")
    refs = historical_references(tmp_path)
    assert refs["A01"]["value"] == 8.25 and refs["A01"]["team"] == "T2"
    assert refs["X01"]["value"] == -2 and not refs["X01"]["competition_scored"]
    assert "B01" not in refs
    assert not historical_comparison({"historical_comparison_eligible": False}, refs["A01"])["eligible"]


def test_report_keeps_backend_timings_separate_and_retains_unexecuted_denominator(tmp_path):
    from backend.benchmarks.campaign import report
    from backend.benchmarks.common import write_json, read_json
    jobs = [dict(id=str(i), kind="solve", phase="correctness", instance="micro-I",
                 algorithm="integrated_oracle", backend=backend, repeat=0, warmup=False)
            for i, backend in enumerate(("highs", "gurobi", "highs"))]
    write_json(tmp_path / "manifest.json", dict(jobs=jobs, budget_hours=24, manifest_sha256="fixture"))
    write_json(tmp_path / "registry.json", [dict(id="micro-I", actual_flights=2, block="fixture")])
    results = {str(i): dict(verdict="completed", optimization_status="optimal", certified_optimal=True,
                           objective=40, audit_pass=True, solver_runtime_seconds=seconds)
               for i, seconds in enumerate((1, 100))}
    results["2"] = dict(verdict="blocked_by_correctness")
    write_json(tmp_path / "state.json", dict(status="completed", jobs=results,
                                            elapsed_seconds=101, phase_elapsed={"correctness": 101}))
    report(tmp_path)
    summary = read_json(tmp_path / "summary.json")
    times = {r["backend"]: r for r in summary["performance"]}
    assert times["highs"]["n"] == 1 and times["highs"]["median_seconds"] == 1
    assert times["gurobi"]["n"] == 1 and times["gurobi"]["median_seconds"] == 100
    rates = {r["backend"]: r for r in summary["registered_task_rates"]}
    assert rates["highs"]["registered"] == 2 and rates["highs"]["executed"] == 1
    assert not summary["acceptance_passed"]
