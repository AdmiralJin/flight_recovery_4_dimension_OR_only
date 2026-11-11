"""Evidence aggregation must not turn unfinished measurements into speedups."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts import validation_campaign as campaign
from scripts import validation_watch as watch


def record(method="joint_arc_flow", repetition=0, **changes):
    return {"method": method, "repetition": repetition, "comparison_key": "identical-input",
            "optimization_status": "optimal", "objective": 10, "audit_valid": True,
            "diagnostics": {"lower_bound": 10, "upper_bound": 10},
            "seconds": 4 if method == "joint_arc_flow" else 2, "flights": 20, **changes}


def timed_item(method, **changes):
    return {"job": {"kind": "xma_timing"}, "result": {"verdict": "completed", "records": [
        record(method, i, **changes) for i in range(-1, 3)]}}


def test_only_three_certified_audited_runs_allow_a_speedup():
    comparisons = watch.timing_comparisons([timed_item("joint_arc_flow"), timed_item("benders_joint"),
                                           timed_item("benders_cg_bp")])
    assert comparisons[0]["three_methods_certified_and_equal"]
    assert comparisons[0]["certified_speedups_vs_direct"] == {"benders_joint": 2, "benders_cg_bp": 2}


def test_repair_comparison_checks_old_hash_and_certified_objectives(tmp_path):
    path=tmp_path/"old.json"
    campaign.atomic_json(path,{"records":[record()]})
    manifest={"baseline_results":[{"id":"case","path":str(path),"status":"completed",
                                   "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}]}
    fresh=record(objective=11,diagnostics={"lower_bound":11,"upper_bound":11})
    items=[{"job":{"id":"case"},"status":"completed","result":{"records":[fresh]}}]
    assert watch.repair_comparisons(manifest,items)[0]["certified_objective_mismatches"]
    fresh["optimization_status"]="not_converged"
    assert not watch.repair_comparisons(manifest,items)[0]["certified_objective_mismatches"]
    path.write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError,match="Baseline result changed"):
        watch.repair_comparisons(manifest,items)


@pytest.mark.parametrize("changes", [
    {"optimization_status": "not_converged", "objective": None},
    {"audit_valid": None}, {"diagnostics": {"lower_bound": 0, "upper_bound": 10}},
    {"diagnostics": {"lower_bound": None, "upper_bound": 10}}, {"objective": float("nan")},
    {"objective": 20, "diagnostics": {"lower_bound": 20, "upper_bound": 20}},
])
def test_incomparable_or_uncertified_measurements_do_not_get_speedups(changes):
    comparisons = watch.timing_comparisons([timed_item("joint_arc_flow"), timed_item("benders_joint", **changes)])
    assert not comparisons[0]["three_methods_certified_and_equal"]
    assert comparisons[0]["certified_speedups_vs_direct"] == {}


def test_duplicate_measurements_do_not_count_as_three_repetitions():
    item = timed_item("benders_joint")
    item["result"]["records"][1]["repetition"] = 1
    assert watch.timing_comparisons([timed_item("joint_arc_flow"), item])[0]["certified_speedups_vs_direct"] == {}


def write_batch(folder, ident, status="passed", carried=()):
    manifest = {"source_root": str(folder / "source"), "source_hashes": {},
                "jobs": [{"id": ident, "name": ident, "kind": "selftest", "wall_seconds": 10}],
                "carried_forward_results": list(carried)}
    state = {"status": "finished", "jobs": {ident: {"status": status}}}
    campaign.atomic_json(folder / "manifest.json", manifest)
    campaign.atomic_json(folder / "state.json", state)
    if status != "cancelled":
        campaign.atomic_json(folder / "jobs" / ident / "result.json", {"verdict": status})
    return manifest, state


def test_collect_resolves_parent_metadata_and_rejects_changed_evidence(tmp_path):
    parent, child = tmp_path / "parent", tmp_path / "child"
    write_batch(parent, "old")
    result = parent / "jobs/old/result.json"
    entry = {"id": "old", "verdict": "passed", "path": str(result),
             "sha256": hashlib.sha256(result.read_bytes()).hexdigest()}
    manifest, state = write_batch(child, "new", carried=[entry])
    assert [x["job"]["id"] for x in watch.collect(child, manifest, state)] == ["old", "new"]
    result.write_text('{}')
    with pytest.raises(ValueError, match="Carried-forward result changed"):
        watch.collect(child, manifest, state)


def test_missing_attempt_evidence_is_not_silently_accepted(tmp_path):
    manifest, state = write_batch(tmp_path, "new")
    (tmp_path / "jobs/new/result.json").unlink()
    with pytest.raises(ValueError, match="Missing attempted-job evidence"):
        watch.collect(tmp_path, manifest, state)


def test_finalize_preserves_todo_and_lists_unstarted_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "ROOT", tmp_path)
    (tmp_path / "tudulist.md").write_text("# Todo\n\nExisting UI work stays here.\n", encoding="utf-8")
    folder = tmp_path / "batch"
    manifest, state = write_batch(folder, "unstarted", "cancelled")
    report = watch.finalize(folder, manifest, state, {})
    evidence = json.loads((folder / "combined_evidence.json").read_text(encoding="utf-8"))
    assert evidence["all_jobs_attempted"] is False
    assert "cancelled" in report.read_text(encoding="utf-8")
    assert "Existing UI work stays here." in (tmp_path / "tudulist.md").read_text(encoding="utf-8")
    watch.update_todo(folder, watch.brief(state, manifest), report)
    assert (tmp_path / "tudulist.md").read_text(encoding="utf-8").count(watch.START_MARKER) == 1


def test_watch_recovers_dead_supervisor_then_finalizes_without_extending_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "ROOT", tmp_path)
    monkeypatch.setattr(watch, "alive", lambda *args: False)
    monkeypatch.setattr(watch.time, "sleep", lambda seconds: None)
    (tmp_path / "tudulist.md").write_text("# Existing UI tasks\n", encoding="utf-8")
    folder = tmp_path / "batch"
    manifest, state = write_batch(folder, "new")
    state.update(status="interrupted", deadline_epoch=watch.time.time() + 3600)
    state["jobs"]["new"]["status"] = "pending"
    campaign.atomic_json(folder / "state.json", state)
    calls = []

    def recover(command, **kwargs):
        calls.append(command)
        state["status"] = "finished"
        state["jobs"]["new"]["status"] = "passed"
        campaign.atomic_json(folder / "state.json", state)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(watch.subprocess, "run", recover)
    watch.watch(folder)
    monitor = campaign.read_json(folder / "watch_state.json")
    assert monitor["status"] == "finished" and monitor["recoveries"] == 1
    assert len(calls) == 1 and "resume" in calls[0]
    assert campaign.read_json(folder / "state.json")["deadline_epoch"] == state["deadline_epoch"]
    assert campaign.read_json(folder / "combined_evidence.json")["all_jobs_attempted"]
    assert "Existing UI tasks" in (tmp_path / "tudulist.md").read_text(encoding="utf-8")


def test_explicit_stop_is_never_automatically_resumed(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "alive", lambda *args: False)
    _manifest, state = write_batch(tmp_path, "new")
    state["status"] = "interrupted"
    campaign.atomic_json(tmp_path / "state.json", state)
    (tmp_path / "STOP").touch()
    with pytest.raises(RuntimeError, match="explicit STOP"):
        watch.watch(tmp_path)
    assert campaign.read_json(tmp_path / "watch_state.json")["recoveries"] == 0


def test_transient_state_read_failure_waits_without_restarting(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "ROOT", tmp_path)
    monkeypatch.setattr(watch, "alive", lambda *args: False)
    monkeypatch.setattr(watch.time, "sleep", lambda seconds: None)
    (tmp_path / "tudulist.md").write_text("# Existing tasks\n", encoding="utf-8")
    folder = tmp_path / "batch"
    write_batch(folder, "new")
    original = campaign.read_json
    observations = []

    def temporarily_unreadable(path, default=None):
        if Path(path) == folder / "state.json":
            observations.append(path)
            if len(observations) == 1:
                return default
        return original(path, default)

    from pathlib import Path
    monkeypatch.setattr(campaign, "read_json", temporarily_unreadable)
    watch.watch(folder)
    monitor = original(folder / "watch_state.json")
    assert monitor["status"] == "finished" and monitor["recoveries"] == 0
    assert "state_temporarily_unavailable" in (folder / "watch_events.jsonl").read_text(encoding="utf-8")


def test_transient_process_access_failure_does_not_mean_dead(monkeypatch):
    import psutil

    def access_denied(_pid):
        raise psutil.AccessDenied(123)

    monkeypatch.setattr(psutil, "Process", access_denied)
    assert watch.alive(123, "script", "folder") is True
