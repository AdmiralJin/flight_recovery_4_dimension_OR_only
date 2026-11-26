"""Acceptance of the unattended harness, including actual Windows job boundaries."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from scripts import validation_campaign as campaign
from scripts.validation_jobs import Evidence, pytest_workspace


def job(name, *, phase="correctness", exclusive=False, lane=None, **config):
    return {"id": name, "name": name, "lane": lane or name, "kind": "selftest",
            "phase": phase, "exclusive": exclusive, "priority": 10 if phase == "correctness" else 20,
            "memory_gib": 0.125, "wall_seconds": 15, "solver_seconds": 1,
            "requires": [], "blocks": [], "config": config}


def states_for(jobs):
    return {j["id"]: {"status": "pending", "name": j["name"], "lane": j["lane"]} for j in jobs}


def test_repair_replays_every_unique_baseline_job_without_mutating_old_evidence():
    items=[{"job":job("done"),"status":"completed"}, {"job":job("passed"),"status":"passed"},
           {"job":job("limited"),"status":"resource_limited"}]
    replay=campaign.full_replay_jobs(items)
    assert [j["id"] for j in replay]==["done","passed","limited"]
    assert replay[0]["baseline_status"]=="completed"
    replay[0]["config"]["changed"]=True
    assert "changed" not in items[0]["job"]["config"]
    with pytest.raises(ValueError,match="Duplicate"):
        campaign.full_replay_jobs([items[0],items[0]])


def test_admission_is_exclusive_and_drains_correctness():
    jobs = [job("a"), job("b"), job("perf", phase="performance", exclusive=True)]
    states = states_for(jobs)
    active = {"a": {"rss": 0}}
    states["a"]["status"] = "running"
    assert campaign.choose_job(jobs, states, active, 8 * campaign.GIB, 1.5)["id"] == "b"
    states["b"]["status"] = "passed"
    assert campaign.choose_job(jobs, states, active, 8 * campaign.GIB, 1.5) is None
    states["a"]["status"] = "passed"
    assert campaign.choose_job(jobs, states, {}, 8 * campaign.GIB, 1.5)["id"] == "perf"
    states["perf"]["status"] = "running"
    assert campaign.choose_job(jobs, states, {"perf": {"rss": 0}}, 8 * campaign.GIB, 1.5) is None


def test_admission_reserves_whole_process_tree_limits():
    jobs = [job("a"), job("b")]
    states = states_for(jobs)
    states["a"]["status"] = "running"
    active = {"a": {"rss": 0}}
    assert campaign.choose_job(jobs, states, active, 0.24 * campaign.GIB, 0) is None
    assert campaign.choose_job(jobs, states, active, 0.26 * campaign.GIB, 0)["id"] == "b"
    assert campaign.choose_job(jobs, states, {**active, "b": {"rss": 0}}, 8 * campaign.GIB, 0) is None


def test_no_resource_wait_retains_parallel_and_exclusive_limits():
    policy = campaign.resource_policy(no_resource_wait=True)
    assert policy == {"resource_wait": False, "startup_memory_gib": 0,
                      "reserve_memory_gib": 0, "emergency_available_gib": 0}
    jobs = [job("a"), job("b"), job("perf", phase="performance", exclusive=True)]
    states = states_for(jobs)
    states["a"]["status"] = "running"
    active = {"a": {"rss": 0}}
    assert campaign.choose_job(jobs, states, active, 0, 100, resource_wait=False)["id"] == "b"
    assert campaign.choose_job(jobs, states, {**active, "b": {"rss": 0}}, 0, 0,
                               resource_wait=False) is None
    states["b"]["status"] = "passed"
    assert campaign.choose_job(jobs, states, active, 0, 0, resource_wait=False) is None
    states["a"]["status"] = "passed"
    assert campaign.choose_job(jobs, states, {}, 0, 100, resource_wait=False)["id"] == "perf"


def test_nested_progress_cannot_become_global_bounds(tmp_path):
    evidence = Evidence(tmp_path)
    evidence.top_algorithm = "benders_cg_bp"
    evidence.event({"type": "mip_progress", "lower_bound": 999, "upper_bound": 1000})
    assert "upper_bound" not in evidence.latest
    assert evidence.first_global_incumbent is None
    evidence.event({"type": "branch_node", "lower_bound": 999, "upper_bound": 1000})
    evidence.event({"type": "benders_iteration", "lower_bound": 5, "upper_bound": 6})
    assert evidence.latest["lower_bound"] == 5
    assert evidence.first_global_incumbent is not None
    evidence.close()


def test_frozen_source_inventory_rejects_changes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    file = source / "sample.txt"
    file.write_text("original")
    manifest = {"source_root": str(source), "source_hashes": {"sample.txt": hashlib.sha256(file.read_bytes()).hexdigest()}}
    campaign.verify_source(tmp_path, manifest)
    file.write_text("changed")
    with pytest.raises(ValueError, match="Frozen source changed"):
        campaign.verify_source(tmp_path, manifest)


def test_monitors_are_passive_and_refresh_every_300_seconds(tmp_path):
    campaign.write_monitors(tmp_path, {})
    paths = list((tmp_path / "monitors").glob("*.cmd"))
    assert len(paths) == 12
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "timeout /t 300 /nobreak" in text
        assert "type " in text
        assert "validation_jobs" not in text and "taskkill" not in text
        assert f"[{tmp_path.name}]" in text


def test_pytest_workspace_keeps_nested_artifacts_below_windows_limit(tmp_path, monkeypatch):
    output = tmp_path / ("output" * 10)
    output.mkdir()
    monkeypatch.delenv("FLIGHT_VALIDATION_TEMP_ROOT", raising=False)
    workspace = pytest_workspace(output)
    try:
        artifact = workspace / "t" / ("test_" + "x" * 26) / ".workbench/artifacts/ab" / ("." + "f" * 64 + ".abcdefgh.tmp")
        assert len(str(artifact)) < 260
        assert not workspace.is_relative_to(output)
        assert campaign.read_json(output / "pytest_workspace.json")["path"] == str(workspace)
    finally:
        workspace.rmdir()


def test_continuation_selects_only_unfinished_evidence():
    jobs = [job(name) for name in ("passed", "completed", "failed", "blocked", "dependency")]
    state = {"status": "finished", "jobs": {name: {"status": status} for name, status in (
        ("passed", "passed"), ("completed", "completed"), ("failed", "failed"),
        ("blocked", "blocked_by_correctness"), ("dependency", "dependency_limited"))}}
    selected, carried = campaign.continuation_jobs({"jobs": jobs}, state)
    assert [j["id"] for j in selected] == ["failed", "blocked", "dependency"]
    assert carried == ["passed", "completed"]
    selected[0]["config"]["new"] = True
    assert "new" not in jobs[2]["config"]
    with pytest.raises(ValueError, match="finished parent"):
        campaign.continuation_jobs({"jobs": jobs}, {**state, "status": "running"})


def test_continuation_snapshot_preserves_algorithm_and_data(tmp_path):
    original, destination = tmp_path / "parent/source", tmp_path / "child/source"
    hashes = {}
    for relative, data in (("backend/solver.py", b"original algorithm"), ("data/sample.json", b"original input"),
                           ("scripts/validation_jobs.py", b"old harness")):
        path = original / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hashes[relative] = hashlib.sha256(data).hexdigest()
    manifest = {"source_root": str(original), "source_hashes": hashes}
    copied = campaign.snapshot_continuation(original.parent, manifest, destination)
    for relative in ("backend/solver.py", "data/sample.json"):
        assert copied[relative] == hashes[relative]
    assert copied["scripts/validation_jobs.py"] != hashes["scripts/validation_jobs.py"]
    assert (destination / "scripts/validation_defer.py").is_file()
    assert original.joinpath("scripts/validation_jobs.py").read_bytes() == b"old harness"


def test_changed_carried_evidence_is_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    result = tmp_path / "previous_result.json"
    result.write_text('{"verdict":"passed"}')
    manifest = {"source_root": str(source), "source_hashes": {}, "carried_forward_results": [
        {"id": "passed", "path": str(result), "sha256": hashlib.sha256(result.read_bytes()).hexdigest()}]}
    campaign.verify_source(tmp_path, manifest)
    result.write_text('{"verdict":"failed"}')
    with pytest.raises(ValueError, match="Carried-forward result changed"):
        campaign.verify_source(tmp_path, manifest)


def test_repeated_defer_preserves_final_evidence(tmp_path):
    from scripts.validation_defer import start
    campaign.atomic_json(tmp_path / "state.json", {"status": "finished"})
    original = {"status": "finished", "original_deadline": 123, "queued_at_defer": ["saved"]}
    campaign.atomic_json(tmp_path / "defer.json", original)
    assert start(tmp_path) == 0
    assert campaign.read_json(tmp_path / "defer.json") == original


@pytest.fixture
def harness(tmp_path):
    if sys.platform != "win32":
        pytest.skip("actual Windows process job acceptance")
    pytest.importorskip("win32job")
    pytest.importorskip("psutil")
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    for name in ("validation_campaign.py", "validation_jobs.py"):
        shutil.copy2(campaign.ROOT / "scripts" / name, source / "scripts" / name)
    children = []

    def create(jobs, **settings):
        # Tiny harness-only jobs run under test limits; formal defaults remain 6/1.5 GiB.
        manifest = {"source_root": str(source), "source_hashes": {}, "live_repository": str(tmp_path),
                    "campaign_hours": 1, "startup_memory_gib": 0, "reserve_memory_gib": 0,
                    "emergency_available_gib": 0, "lanes": [(j["lane"], j["lane"], "test") for j in jobs],
                    "jobs": jobs, **settings}
        campaign.atomic_json(tmp_path / "manifest.json", manifest)
        campaign.atomic_json(tmp_path / "state.json", {"status": "prepared", "jobs": states_for(jobs)})
        log = (tmp_path / "supervisor_test.log").open("ab", buffering=0)
        command = [sys.executable, str(source / "scripts/validation_campaign.py"), "supervise", "--folder", str(tmp_path)]
        child = subprocess.Popen(command, cwd=source, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        log.close()
        children.append(child)
        return child

    yield tmp_path, source, create, children
    (tmp_path / "STOP").touch()
    for child in children:
        if child.poll() is None:
            try:
                child.wait(5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(5)


def until(folder, predicate, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = campaign.read_json(folder / "state.json", {})
        if predicate(state):
            return state
        time.sleep(0.1)
    error = (folder / "supervisor_test.log").read_text(encoding="utf-8", errors="replace")
    pytest.fail(f"Harness did not reach expected state: {state}\n{error}")


def test_real_job_exit_crash_timeout_tree_and_memory(harness):
    import psutil
    folder, source, create, _children = harness
    jobs = [job("normal"), job("crash", mode="crash"),
            job("timeout", mode="wait", seconds=600, grandchild=True),
            job("memory", mode="memory"), job("exclusive", phase="performance", exclusive=True, mode="wait", seconds=1)]
    jobs[2]["wall_seconds"] = 3
    child = create(jobs)
    history = []
    while child.poll() is None:
        current = campaign.read_json(folder / "state.json", {})
        running = [key for key, value in current.get("jobs", {}).items() if value["status"] == "running"]
        history.append(running)
        assert len(running) <= 2
        if "exclusive" in running:
            assert running == ["exclusive"]
        if len(history) > 400:
            pytest.fail("Acceptance supervisor did not terminate")
        time.sleep(0.1)
    assert child.returncode == 0, (folder / "supervisor_test.log").read_text(errors="replace")
    state = campaign.read_json(folder / "state.json")
    assert {key: row["status"] for key, row in state["jobs"].items()} == {
        "normal": "passed", "crash": "error", "timeout": "timed_out", "memory": "resource_limited", "exclusive": "passed"}
    grandchild = campaign.read_json(folder / "jobs/timeout/attempt_001/grandchild.json")["pid"]
    assert not psutil.pid_exists(grandchild)
    for item in jobs:
        result = campaign.read_json(folder / "jobs" / item["id"] / "result.json")
        # Windows' reported historical peak may include the rejected allocation.
        # The fixture allocates in 8 MiB chunks; the next allocation must fail.
        assert result["process_tree_peak_commit_bytes"] <= item["memory_gib"] * campaign.GIB + 8 * 1024 ** 2
        assert result["supervisor_wall_seconds"] > 0
    assert "MemoryError" in (folder / "jobs/memory/attempt_001/error.txt").read_text()
    assert (folder / "summary.csv").is_file() and (folder / "SUMMARY.md").is_file()


def test_startup_memory_does_not_consume_budget_and_stop_is_persisted(harness):
    folder, _source, create, _children = harness
    child = create([job("waiting")], startup_memory_gib=999)
    state = until(folder, lambda s: s.get("status") == "waiting_for_memory")
    assert state["started_epoch"] is None and state["deadline_epoch"] is None
    assert state["jobs"]["waiting"]["status"] == "pending"
    (folder / "STOP").touch()
    state = until(folder, lambda s: s.get("status") == "finished")
    child.wait(5)
    assert state["jobs"]["waiting"]["status"] == "cancelled"
    assert state["started_epoch"] is None


def test_no_resource_wait_starts_despite_unreachable_memory_thresholds(harness):
    folder, _source, create, _children = harness
    child = create([job("immediate")], resource_wait=False, startup_memory_gib=99999,
                   reserve_memory_gib=99999, emergency_available_gib=99999)
    state = until(folder, lambda s: s.get("status") == "finished")
    child.wait(5)
    assert state["started_epoch"] is not None
    assert state["jobs"]["immediate"]["status"] == "passed"


def test_interrupt_and_explicit_resume_keep_completed_jobs_and_deadline(harness):
    import psutil
    folder, source, create, children = harness
    child = create([job("done"), job("running", mode="wait", seconds=4, grandchild=True)])
    state = until(folder, lambda s: s.get("jobs", {}).get("done", {}).get("status") == "passed")
    deadline = state["deadline_epoch"]
    running_pid = state["jobs"]["running"]["pid"]
    command = [sys.executable, str(source / "scripts/validation_campaign.py"), "resume", "--folder", str(folder)]
    rejected = subprocess.run(command, capture_output=True, timeout=8)
    assert rejected.returncode != 0
    assert campaign.read_json(folder / "state.json")["jobs"]["done"]["attempt"] == 1
    child.kill()
    child.wait(5)
    for _ in range(30):
        if not psutil.pid_exists(running_pid):
            break
        time.sleep(0.1)
    assert not psutil.pid_exists(running_pid)
    restarted = subprocess.run(command, capture_output=True, timeout=10)
    assert restarted.returncode == 0, restarted.stderr.decode(errors="replace")
    new_pid = campaign.read_json(folder / "supervisor_pid.json")["pid"]
    state = until(folder, lambda s: s.get("status") == "finished")
    assert state["deadline_epoch"] == deadline
    assert state["jobs"]["done"]["attempt"] == 1
    assert state["jobs"]["running"]["attempt"] == 2
    assert state["jobs"]["running"]["status"] == "passed"
    assert (folder / "jobs/running/attempt_001/job.json").exists()
    assert campaign.read_json(folder / "jobs/running/attempt_001/result.json")["verdict"] == "interrupted"
    assert (folder / "jobs/running/attempt_002/result.json").exists()


@pytest.mark.parametrize("limited", [False, True])
def test_defer_drains_current_job_without_dispatch_or_deadline_reset(harness, limited):
    from scripts.validation_defer import start
    folder, _source, create, _children = harness
    current = job("current", phase="performance", exclusive=True, mode="wait", seconds=20 if limited else 3, grandchild=True)
    current["wall_seconds"] = 3 if limited else 15
    child = create([current, job("next", phase="performance", exclusive=True)])
    before = until(folder, lambda s: s.get("jobs", {}).get("current", {}).get("status") == "running")
    controller_pid = start(folder)
    assert controller_pid > 0
    after = until(folder, lambda s: s.get("status") == "finished")
    child.wait(5)
    assert after["deadline_epoch"] == before["deadline_epoch"]
    assert after["jobs"]["current"]["status"] == ("timed_out" if limited else "passed")
    assert after["jobs"]["next"]["status"] == "cancelled"
    assert "attempt" not in after["jobs"]["next"]
    assert campaign.read_json(folder / "defer.json")["original_deadline"] == before["deadline_epoch"]


def test_defer_handles_worker_crash_without_dispatching_next(harness):
    import psutil
    from scripts.validation_defer import start
    folder, _source, create, _children = harness
    child = create([job("current", phase="performance", exclusive=True, mode="wait", seconds=600, grandchild=True),
                    job("next", phase="performance", exclusive=True)])
    before = until(folder, lambda s: s.get("jobs", {}).get("current", {}).get("status") == "running")
    start(folder)
    for _ in range(100):
        if campaign.read_json(folder / "defer.json", {}).get("status") == "draining":
            break
        time.sleep(.1)
    else:
        pytest.fail("Defer controller did not suspend dispatch")
    # RUNNING means the worker was dispatched; Python startup can still be in
    # progress. Wait for the actual descendant before testing tree cleanup.
    until(folder,lambda _s: campaign.read_json(folder/"jobs/current/attempt_001/grandchild.json") is not None,timeout=10)
    psutil.Process(before["jobs"]["current"]["pid"]).kill()
    after = until(folder, lambda s: s.get("status") == "finished")
    child.wait(5)
    assert after["jobs"]["current"]["status"] == "error"
    assert after["jobs"]["next"]["status"] == "cancelled"
    assert "attempt" not in after["jobs"]["next"]
    grandchild = campaign.read_json(folder / "jobs/current/attempt_001/grandchild.json")["pid"]
    assert not psutil.pid_exists(grandchild)


def test_defer_controller_hard_kill_is_fail_closed(harness):
    import psutil
    from scripts.validation_defer import start
    folder, _source, create, _children = harness
    child = create([job("current", phase="performance", exclusive=True, mode="wait", seconds=600, grandchild=True)])
    before = until(folder, lambda s: s.get("jobs", {}).get("current", {}).get("status") == "running")
    pid = start(folder)
    for _ in range(100):
        evidence = campaign.read_json(folder / "defer.json", {})
        if evidence.get("status") == "draining":
            break
        time.sleep(.1)
    else:
        pytest.fail("Defer controller did not persist its guard evidence")
    psutil.Process(pid).kill()
    child.wait(8)
    for _ in range(50):
        if not psutil.pid_exists(before["jobs"]["current"]["pid"]):
            break
        time.sleep(.1)
    assert not psutil.pid_exists(before["jobs"]["current"]["pid"])
    assert evidence["original_deadline"] == before["deadline_epoch"]
    assert evidence["controller_pid"] == pid  # interrupted guard evidence remains recoverable
