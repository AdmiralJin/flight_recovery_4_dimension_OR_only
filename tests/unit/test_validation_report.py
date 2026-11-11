from pathlib import Path

import pytest

from scripts import validation_campaign as campaign
from scripts import validation_report as report


def item(status="completed", result=None, kind="xma_timing"):
    return {"status": status, "job": {"kind": kind}, "result": result or {}}


def test_completed_unconverged_is_not_reported_as_correct_or_optimal():
    outcome = item(result={"records": [{"repetition": 0, "optimization_status": "not_converged",
                                       "objective": None, "audit_valid": None}]})
    assert "未收敛" in report.diagnosis(outcome)


def test_uncertified_optimal_label_is_flagged_for_review():
    outcome = item(result={"records": [{"repetition": 0, "optimization_status": "optimal",
                                       "objective": 4, "audit_valid": True,
                                       "diagnostics": {"lower_bound": 0, "upper_bound": 4}}]})
    assert "证据不足" in report.diagnosis(outcome)


def test_resource_failure_overrides_partial_optimal_records():
    outcome = item("resource_limited", {"records": [{"optimization_status": "optimal"}]})
    assert report.diagnosis(outcome) == "资源受限"


def test_certified_infeasibility_is_distinct_from_unconverged_or_missing_audit():
    records = [{"repetition": i, "optimization_status": "infeasible", "objective": None,
                "audit_valid": None, "diagnostics": {"terminal_reason": "3"}} for i in range(3)]
    assert report.diagnosis(item(result={"records": records})) == "求解器认证不可行"


def test_infeasibility_without_certificate_marker_is_flagged():
    assert "需复核" in report.diagnosis(item(result={"records": [
        {"optimization_status": "infeasible", "diagnostics": {}}]}))


def test_different_optimal_values_in_identical_repeats_are_flagged():
    records = [{"repetition": i, "optimization_status": "optimal", "objective": value,
                "audit_valid": True, "diagnostics": {"lower_bound": value, "upper_bound": value}}
               for i, value in enumerate((10, 11, 10))]
    assert "重复最优目标不一致" in report.diagnosis(item(result={"records": records}))


def test_feasible_and_infeasible_certificates_in_same_repeat_group_conflict():
    records = [{"optimization_status": "infeasible", "diagnostics": {"terminal_reason": "3"}},
               {"optimization_status": "optimal", "objective": 10, "audit_valid": True,
                "diagnostics": {"lower_bound": 10, "upper_bound": 10}}]
    assert "可行性结论冲突" in report.diagnosis(item(result={"records": records}))


def test_candidate_expansion_compares_repeats_only_within_problem_key():
    records = [{"comparison_key": key, "optimization_status": "optimal", "objective": cost,
                "audit_valid": True, "diagnostics": {"lower_bound": cost, "upper_bound": cost}}
               for key, cost in (("coarse", 160), ("fine", 110))]
    assert "变形关系断言通过" in report.diagnosis(item("passed", {"records": records}, "metamorphic"))
    records.append({**records[0], "objective": 161, "diagnostics": {"lower_bound": 161, "upper_bound": 161}})
    assert "重复最优目标不一致" in report.diagnosis(item("passed", {"records": records}, "metamorphic"))


def test_distinct_problem_keys_can_have_different_feasibility():
    records = [{"comparison_key": "restricted", "optimization_status": "infeasible",
                "diagnostics": {"terminal_reason": "3"}},
               {"comparison_key": "expanded", "optimization_status": "optimal", "objective": 10,
                "audit_valid": True, "diagnostics": {"lower_bound": 10, "upper_bound": 10}}]
    assert "冲突" not in report.diagnosis(item(result={"records": records}))


def test_report_requires_finished_evidence_and_never_overwrites(tmp_path):
    folder = tmp_path / "batch"
    campaign.atomic_json(folder / "state.json", {"status": "running", "jobs": {}})
    with pytest.raises(ValueError, match="terminal"):
        report.write(folder, tmp_path / "report.md")
    manifest = {"source_root": str(folder / "source"), "source_hashes": {}, "jobs": [], "lanes": [],
                "carried_forward_results": []}
    campaign.atomic_json(folder / "manifest.json", manifest)
    campaign.atomic_json(folder / "state.json", {"status": "finished", "jobs": {}})
    path = report.write(folder, tmp_path / "report.md")
    assert path.is_file() and "全部任务逐项证据" in path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        report.write(folder, path)


def test_report_includes_limits_params_reference_and_result_links(tmp_path):
    folder = tmp_path / "batch"
    job = {"id": "case", "lane": "cases", "name": "Expected case", "kind": "air_case", "phase": "correctness",
           "wall_seconds": 60, "solver_seconds": 50, "memory_gib": 1.5, "config": {"seed": 20261106}}
    campaign.atomic_json(folder / "manifest.json", {"source_root": str(folder / "source"), "source_hashes": {},
                        "jobs": [job], "lanes": [["cases", "Known solutions", "cases"]]})
    campaign.atomic_json(folder / "state.json", {"status": "finished", "jobs": {"case": {"status": "passed"}}})
    campaign.atomic_json(folder / "jobs/case/result.json", {"verdict": "passed", "optimization_status": "optimal",
                        "expected": {"objective_total": 18080}, "diagnostics": {"objective": 18080,
                        "lower_bound": 18080, "upper_bound": 18080, "integrated_audit_pass": True}})
    text = report.write(folder, tmp_path / "report.md").read_text(encoding="utf-8")
    for required in ("case", "18080", "20261106", "60/50", "1.5GiB", "result.json", "上下界闭合"):
        assert required in text


def test_timeout_report_shows_global_progress_separately_from_nested_metrics(tmp_path):
    folder = tmp_path / "batch"
    job = {"id": "limited", "lane": "stress", "name": "Timeout case", "kind": "air_stress", "phase": "stress",
           "wall_seconds": 180, "solver_seconds": 170, "memory_gib": 1.5, "config": {}}
    campaign.atomic_json(folder / "manifest.json", {"source_root": str(folder / "source"), "source_hashes": {},
                        "jobs": [job], "lanes": [["stress", "Stress", "stress"]]})
    campaign.atomic_json(folder / "state.json", {"status": "finished", "jobs": {"limited": {"status": "timed_out"}}})
    campaign.atomic_json(folder / "jobs/limited/result.json", {"verdict": "timed_out", "partial_progress": {
        "stage": "phase11", "lower_bound": 120, "upper_bound": 600, "relative_gap": .8,
        "metrics": {"candidate_upper_bound": 999}}})
    text = report.write(folder, tmp_path / "report.md").read_text(encoding="utf-8")
    assert "全局 LB=120，UB=600" in text and "硬时限终止" in text
    assert "candidate_upper_bound" not in text


def test_waiter_loads_the_latest_report_implementation_after_completion(tmp_path, monkeypatch):
    campaign.atomic_json(tmp_path / "state.json", {"status": "finished"})
    monkeypatch.setattr(report.sys, "argv", ["validation_report.py", "--folder", str(tmp_path), "--wait"])
    commands = []
    monkeypatch.setattr(report.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))
    report.main()
    assert len(commands) == 1 and "--wait" not in commands[0][0]
    assert commands[0][1]["check"] is True
