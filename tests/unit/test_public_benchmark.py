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


@pytest.mark.parametrize("algorithm", ["integrated_oracle", "fixed_benders", "air_cg", "air_bp",
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


def test_snapshot_rejects_data_or_display_tampering(public_case):
    document = make_document(public_case)
    assert compile_draft(document).valid
    damaged = public_case.model_dump(mode="json")
    damaged["candidate_policy"]["max_delay_minutes"] += 1
    with pytest.raises(ValueError, match="fingerprint"):
        PublicSolveRequest.model_validate(damaged)
    document.scenario["flights"][0]["max_delay"] += 1
    assert not compile_draft(document).valid


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
