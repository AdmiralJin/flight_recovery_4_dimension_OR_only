from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import workbench_v2
from backend.main import app
from backend.application.solve_service import solve_request
from backend.schemas.result import SolveRequest
from backend.workbench.run_manager import RunManager
from backend.workbench.storage import WorkbenchStore


@pytest.fixture()
def v2_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = WorkbenchStore(tmp_path / ".workbench")
    manager = RunManager(store)
    monkeypatch.setattr(workbench_v2, "get_workbench_store", lambda: store)
    monkeypatch.setattr(workbench_v2, "get_run_manager", lambda: manager)
    yield TestClient(app), store, manager
    manager.stop()


def test_clone_compile_snapshot_and_hash_conflict(v2_client):
    client, store, _manager = v2_client
    created = client.post(
        "/api/v2/drafts",
        json={"source_case_id": "benchmark-disruption-recovery"},
    )
    assert created.status_code == 201
    draft = created.json()

    preview = client.post(f"/api/v2/drafts/{draft['draft_id']}/compile")
    assert preview.status_code == 200
    assert preview.json()["valid"] is True
    assert preview.json()["candidate_counts"]["flight_options"] > 0

    snapshot = client.post(
        f"/api/v2/drafts/{draft['draft_id']}/snapshots",
        json={"base_hash": draft["working_hash"], "note": "test"},
    )
    assert snapshot.status_code == 201
    assert snapshot.json()["content_hash"] == preview.json()["compiled_hash"]
    assert store.get_snapshot(snapshot.json()["snapshot_id"]).draft_id == draft["draft_id"]

    conflict = client.put(
        f"/api/v2/drafts/{draft['draft_id']}/working-copy",
        json={"base_hash": "0" * 64, "document": draft["document"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "draft_hash_conflict"


def test_precheck_rejects_wrong_outer_contract():
    client = TestClient(app)
    bundle = client.get(
        "/api/solve/example-bundle/phase1_benchmark_001"
    ).json()
    bundle["algorithm"] = "wrong"
    response = client.post("/api/solve/precheck", json=bundle)
    assert response.status_code == 200
    assert response.json()["solve_ready"] is False
    assert "algorithm" in response.json()["invalid_profiles"]


def test_runtime_profiles_are_clone_only_and_schema_whitelisted(v2_client):
    client, _store, _manager = v2_client
    profiles = client.get("/api/v2/profiles")
    assert profiles.status_code == 200
    assert profiles.json()["items"][0]["profile_id"] == "default-exact"
    read_only = client.put(
        "/api/v2/profiles/default-exact",
        json={"name": "mutated", "parameters": {"time_limit_seconds": 30}},
    )
    assert read_only.status_code == 409
    cloned = client.post(
        "/api/v2/profiles/default-exact/clone",
        json={"profile_id": "fast-local", "name": "Fast local"},
    )
    assert cloned.status_code == 201
    updated = client.put(
        "/api/v2/profiles/fast-local",
        json={
            "name": "Fast local",
            "parameters": {
                "time_limit_seconds": 30,
                "max_benders_iterations": 20,
                "max_branch_nodes": 100,
                "absolute_gap_tolerance": 0.001,
                "relative_gap_tolerance": 0.0001,
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["parameters"]["max_branch_nodes"] == 100


def test_sse_resume_serializes_monotonic_event_ids(v2_client):
    _client, store, _manager = v2_client
    created = workbench_v2.create_draft(
        workbench_v2.DraftCreateRequest(
            source_case_id="benchmark-disruption-recovery"
        )
    )
    preview = workbench_v2.compile_preview(created.draft_id)
    snapshot = store.create_snapshot(created.draft_id, created.working_hash, preview)
    run = store.create_run(snapshot, "detailed")
    store.append_event(workbench_v2._queued_event(run.run_id))
    from backend.schemas.workbench import RunEvent, utc_now

    store.append_event(
        RunEvent(
            run_id=run.run_id,
            seq=2,
            emitted_at=utc_now(),
            elapsed_seconds=0.2,
            stage="phase11",
            event_type="benders_iteration",
            lower_bound=10,
            upper_bound=20,
            absolute_gap=10,
            relative_gap=0.5,
        )
    )
    store.update_run_status(run.run_id, workbench_v2.JobStatus.COMPLETED)

    client = TestClient(app)
    with client.stream(
        "GET", f"/api/v2/runs/{run.run_id}/events", headers={"Last-Event-ID": "1"}
    ) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "id: 2" in body
    assert "id: 1" not in body
    payload = json.loads(next(line[6:] for line in body.splitlines() if line.startswith("data: ")))
    assert payload["relative_gap"] == 0.5


def test_real_solver_emits_monotonic_phase11_bounds():
    client = TestClient(app)
    bundle = client.get(
        "/api/solve/example-bundle/phase1_benchmark_001"
    ).json()
    events = []
    result = solve_request(SolveRequest.model_validate(bundle), event_sink=events.append)
    iterations = [item for item in events if item.get("type") == "benders_iteration"]
    assert result.status.value == "optimal"
    assert iterations
    phase11_lower_bounds = [
        item["lower_bound"]
        for item in iterations
        if item["stage"] == "phase11" and item["lower_bound"] is not None
    ]
    assert phase11_lower_bounds == sorted(phase11_lower_bounds)
    assert events[-1]["type"] == "stage_completed"
    assert events[-1]["upper_bound"] == result.diagnostics.upper_bound
