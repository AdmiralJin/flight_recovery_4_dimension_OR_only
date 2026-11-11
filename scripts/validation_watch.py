"""Low-overhead durable monitoring and evidence collection for a running batch.

No solvers or scientific inputs are changed. Normal sampling is every 300s;
supervisor liveness is checked every 30s. A dead supervisor can be resumed at
most three times without extending the original batch deadline.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import validation_campaign as campaign

LOCAL = timezone(timedelta(hours=8))
START_MARKER = "<!-- validation-watch:start -->"
END_MARKER = "<!-- validation-watch:end -->"


def stamp():
    return datetime.now(LOCAL).isoformat(timespec="seconds")


def event(folder, kind, **values):
    with (folder / "watch_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": stamp(), "type": kind, **values}, ensure_ascii=False) + "\n")


def brief(state, manifest):
    index = {j["id"]: j for j in manifest["jobs"]}
    running = []
    for ident, row in state["jobs"].items():
        if row["status"] != "running":
            continue
        progress = campaign.read_json(Path(row["attempt_folder"]) / "progress.json", {})
        running.append({"id": ident, "pid": row.get("pid"), "stage": progress.get("stage"),
                        "elapsed_seconds": progress.get("elapsed_seconds"),
                        "wall_limit_seconds": index[ident]["wall_seconds"],
                        **{k: progress.get(k) for k in ("lower_bound", "upper_bound", "relative_gap")}})
    pending = [index[k]["wall_seconds"] for k, row in state["jobs"].items() if row["status"] == "pending"]
    worst = sum(pending) + sum(max(0, r["wall_limit_seconds"] - (r["elapsed_seconds"] or 0)) for r in running)
    return {"status": state["status"], "counts": dict(Counter(r["status"] for r in state["jobs"].values())),
            "active": running, "remaining_serial_hard_bound_hours": round(worst / 3600, 3),
            "deadline_epoch": state.get("deadline_epoch")}


def update_todo(folder, snapshot, report=None):
    path = ROOT / "tudulist.md"
    text = path.read_text(encoding="utf-8")
    status = "已结束，证据已汇总" if report else "后台续测与监控中"
    carried_count = len(campaign.read_json(folder / "manifest.json").get("carried_forward_results", []))
    block = [START_MARKER, f"## 算法验证当前状态：{status}", "",
             f"更新时间：{stamp()}；批次：`{folder.name}`。",
             f"本轮状态：`{json.dumps(snapshot['counts'], ensure_ascii=False)}`；已保留历史证据 {carried_count} 项。",
             "按用户要求跳过系统空闲内存等待和低内存停测；并发最多 2 项，正式计时独占，单例硬时限与进程树内存上限有效。",
             f"实时状态：[watch_state.json]({folder.relative_to(ROOT).as_posix()}/watch_state.json)。"]
    if report:
        block += [f"最终汇总：[{report.name}]({report.relative_to(ROOT).as_posix()})。",
                  "执行结束不等于全部证明最优；受限、未收敛与正确性失败分别列出。"]
    else:
        block += ["监控每 300 秒汇总，30 秒检查调度器存活；异常退出最多恢复 3 次，不延长批次原截止时间。"]
    block += [END_MARKER, ""]
    if START_MARKER in text:
        begin, rest = text.split(START_MARKER, 1)
        _old, end = rest.split(END_MARKER, 1)
        text = begin + "\n".join(block) + end.lstrip("\n")
    else:
        header, rest = text.split("\n", 1)
        text = header + "\n\n" + "\n".join(block) + "\n" + rest.lstrip("\n")
    text = text.replace("## 算法验证：已暂缓，不自动恢复", "## 算法验证：上轮停队记录（历史）")
    text = text.replace("当前阶段：**任务1与任务2均已完成；算法验证保持暂缓**。",
                        "当前阶段：**任务1与任务2均已完成；算法验证按用户要求恢复**。")
    text = text.replace("- [ ] 后续：用户安排恢复算法验证后再启动；完成后复核证据并形成分层结论。",
                        "- [x] 用户已安排恢复算法验证：启动剩余任务，最多 2 项并发，不等待系统空闲资源。\n"
                        "- [ ] 算法验证：完成全部执行并复核独立审计、上下界、Oracle 与规模限制。")
    if report:
        text = text.replace("- [ ] 算法验证：完成全部执行并复核独立审计、上下界、Oracle 与规模限制。",
                            "- [x] 算法验证：本轮调度结束并生成证据汇总；受限或未收敛问题见报告，不能视为全部通过。")
    campaign.atomic_text(path, text)


def closed_and_audited(record):
    diagnostics = record.get("diagnostics") or {}
    values = [record.get("objective"), diagnostics.get("lower_bound"), diagnostics.get("upper_bound")]
    if record.get("optimization_status") != "optimal" or record.get("audit_valid") is not True:
        return False
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in values):
        return False
    tolerance = max(1e-6, abs(values[0]) * 1e-8)
    return max(values) - min(values) <= tolerance


def timing_comparisons(items):
    groups = defaultdict(lambda: defaultdict(list))
    for item in items:
        if item["job"]["kind"] != "xma_timing" or item["result"].get("verdict") != "completed":
            continue
        for record in item["result"].get("records", []):
            if record.get("repetition", -1) >= 0:
                groups[record["comparison_key"]][record["method"]].append(record)
    rows = []
    for key, methods in sorted(groups.items()):
        eligible = {method: values for method, values in methods.items()
                    if sorted(r["repetition"] for r in values) == [0, 1, 2]
                    and all(closed_and_audited(r) for r in values)}
        objectives = [r["objective"] for values in eligible.values() for r in values]
        same = bool(objectives) and max(objectives) - min(objectives) <= max(1e-6, abs(objectives[0]) * 1e-8)
        medians = {method: statistics.median(r["seconds"] for r in values) for method, values in methods.items()}
        rows.append({"comparison_key": key, "certified_methods": sorted(eligible),
                     "three_methods_certified_and_equal": len(eligible) == 3 and same,
                     "methods": {method: {"statuses": [r["optimization_status"] for r in values],
                                          "median_seconds": medians[method],
                                          "range_seconds": [min(r["seconds"] for r in values), max(r["seconds"] for r in values)],
                                          "objectives": [r.get("objective") for r in values],
                                          "flights": values[0]["flights"]} for method, values in methods.items()},
                     "certified_speedups_vs_direct": {
                         method: medians["joint_arc_flow"] / medians[method]
                         for method in eligible if method != "joint_arc_flow" and "joint_arc_flow" in eligible
                         and same and medians[method] > 0}})
    return rows


def collect(folder, manifest, state):
    campaign.verify_source(folder, manifest)
    manifests = {str(folder): manifest}
    items = []
    entries = list(manifest.get("carried_forward_results", []))
    entries += [{"id": j["id"], "path": str(folder / "jobs" / j["id"] / "result.json")}
                for j in manifest["jobs"]]
    seen = set()
    for entry in entries:
        ident, path = entry["id"], Path(entry["path"])
        if ident in seen:
            raise ValueError(f"Duplicate scientific job: {ident}")
        seen.add(ident)
        owner = path.parents[2]
        if str(owner) not in manifests:
            manifests[str(owner)] = campaign.read_json(owner / "manifest.json")
        jobs = {j["id"]: j for j in manifests[str(owner)]["jobs"]}
        result = campaign.read_json(path)
        status = state["jobs"][ident]["status"] if owner == folder else entry["verdict"]
        if result is None and status not in ("cancelled", "not_run_budget", "blocked_by_correctness"):
            raise ValueError(f"Missing attempted-job evidence: {ident}")
        if result and result["verdict"] != status:
            raise ValueError(f"State/result disagreement: {ident}")
        items.append({"job": jobs[ident], "status": status, "result": result or {}, "result_path": str(path),
                      "result_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None})
    return items


def repair_comparisons(manifest, items):
    """Compare fresh results with preserved baseline evidence, never inherit it."""
    current={i["job"]["id"]:i for i in items}
    comparisons=[]
    for entry in manifest.get("baseline_results",[]):
        path=Path(entry["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry["sha256"]:
            raise ValueError("Baseline result changed: "+entry["id"])
        old=campaign.read_json(path)
        new=current[entry["id"]]["result"]
        def records(result):
            rows=[r for r in result.get("records",[]) if r.get("repetition",0)>=0]
            if not rows and result.get("optimization_status"):
                diag=result.get("diagnostics",{})
                rows=[{"optimization_status":result["optimization_status"],"diagnostics":diag,
                       "objective":diag.get("objective",diag.get("upper_bound")),"audit_valid":diag.get("integrated_audit_pass")}]
            return rows
        previous,latest=records(old),records(new)
        mismatches=[]
        for a in previous:
            for b in latest:
                if (a.get("comparison_key"),a.get("method"),a.get("repetition",0))!=(b.get("comparison_key"),b.get("method"),b.get("repetition",0)):
                    continue
                if closed_and_audited(a) and closed_and_audited(b) and not math.isclose(a["objective"],b["objective"],abs_tol=1e-6,rel_tol=1e-8):
                    mismatches.append({"baseline":a["objective"],"repair":b["objective"],"comparison_key":a.get("comparison_key")})
        comparisons.append({"id":entry["id"],"baseline_status":entry["status"],"repair_status":current[entry["id"]]["status"],
                            "baseline_optimization_statuses":[r.get("optimization_status") for r in previous],
                            "repair_optimization_statuses":[r.get("optimization_status") for r in latest],
                            "certified_objective_mismatches":mismatches})
    return comparisons


def finalize(folder, manifest, state, monitor):
    items = collect(folder, manifest, state)
    if manifest.get("repair_of"):
        campaign.atomic_json(folder/"baseline_to_repair_comparisons.json",repair_comparisons(manifest,items))
    comparisons = timing_comparisons(items)
    counts = dict(Counter(item["status"] for item in items))
    limitations = [x for x in items if x["status"] not in ("passed", "completed")]
    unfinished_optimization = [x for x in items if x["status"] in ("passed", "completed") and (
        x["result"].get("optimization_status") in ("not_converged", "feasible", "aborted") or any(
            r.get("optimization_status") in ("not_converged", "feasible", "aborted")
            for r in x["result"].get("records", []) if r.get("repetition", 0) >= 0))]
    incomplete = [x for x in items if x["status"] in ("cancelled", "not_run_budget", "interrupted", "blocked_by_correctness")]
    campaign.atomic_json(folder / "combined_evidence.json", {"generated_at": stamp(), "counts": counts,
                         "all_jobs_attempted": not incomplete, "items": items})
    campaign.atomic_json(folder / "combined_performance_comparisons.json", comparisons)
    report = ROOT / "docs/codex_reports" / (datetime.now(LOCAL).strftime("%Y%m%d_%H%M%S") + "_validation_campaign_finished.md")
    rows = ["# 算法验证续测与监控结果", "", f"完成时间：{stamp()}；批次：`{folder.name}`。", "",
            f"本轮 {len(manifest['jobs'])} 项，历史保留 {len(manifest.get('carried_forward_results', []))} 项；合并状态：`{json.dumps(counts, ensure_ascii=False)}`。",
            f"全部任务已尝试：**{'是' if not incomplete else '否'}**；未执行或中断 {len(incomplete)} 项。",
            "已取消系统空闲资源等待及低内存停测；最多两项并发，正式计时独占；单例硬时限和进程树内存限制有效。",
            f"监控记录的最大并发：{monitor.get('maximum_observed_active', 0)}；调度器异常恢复：{monitor.get('recoveries', 0)} 次。",
            "已核验冻结代码、数据、任务清单和继承结果 SHA256，检查本轮执行状态与结果一致。", "",
            "## 结果含义", "", "passed 表示相应测试断言通过，completed 表示采样完成。资源受限、未收敛和未执行不能当作证明最优或算法正确性失败。",
            f"其中已完成采样但包含未收敛、仅可行或中止结果的任务：{len(unfinished_optimization)} 项。",
            "本报告为自动证据汇总；没有合格证据的项目保留未定结论。", "",
            "## AIR 列生成对照", "", "| 测试 | 全列/CG 中位耗时比 | 结论 |", "|---|---:|---|"]
    for item in items:
        if item["job"]["kind"] == "air_cg":
            r = item["result"]
            ratio = r.get("observed_speedup")
            rows.append(f"| {item['job']['name']} | {ratio:.3f} | {'本实例 CG 较快' if ratio > 1 else '本实例 CG 未提速'}；{item['status']} |" if ratio is not None else
                        f"| {item['job']['name']} | 缺失 | {item['status']} |")
    certified = sum(c["three_methods_certified_and_equal"] for c in comparisons)
    rows += ["", "## 厦航真实数据计时", "", f"合并 {len(comparisons)} 组同输入、同目标比较；三算法均有三次审计通过、上下界闭合且目标一致的组数：{certified}。",
             "仅对满足同问题、三次证明最优且独立审计有效的算法计算加速比；未收敛或无合法 incumbent 的时间不参与加速比。", "",
             "## 受限、失败及未完成任务", "", "| 任务 | 状态 | 原因 |", "|---|---|---|"]
    for item in limitations:
        reason = str(item["result"].get("summary", item["result"].get("reason", "见状态文件"))).replace("|", "/").replace("\n", " ")[:240]
        rows.append(f"| {item['job']['id']} {item['job']['name']} | {item['status']} | {reason} |")
    if not limitations:
        rows.append("| 无 | — | — |")
    rows += ["", "## 已执行但优化未闭合", "", "| 任务 | 执行状态 | 优化结果 |", "|---|---|---|"]
    for item in unfinished_optimization:
        reason = str(item["result"].get("summary", "见结果 records 和 diagnostics")).replace("|", "/").replace("\n", " ")[:240]
        rows.append(f"| {item['job']['id']} {item['job']['name']} | {item['status']} | {reason} |")
    if not unfinished_optimization:
        rows.append("| 无 | — | — |")
    rows += ["", "## 证据位置", "", f"- 本轮执行汇总：`{folder / 'SUMMARY.md'}`。",
             f"- 跨批次证据及输入参数：`{folder / 'combined_evidence.json'}`。",
             f"- 跨批次性能比较：`{folder / 'combined_performance_comparisons.json'}`。",
             f"- 监控与恢复日志：`{folder / 'watch_events.jsonl'}`。", ""]
    campaign.atomic_text(report, "\n".join(rows))
    update_todo(folder, brief(state, manifest), report)
    return report


def alive(pid, script, folder):
    import psutil
    try:
        args = psutil.Process(pid).cmdline()
        return any(str(script).lower() == str(arg).lower() for arg in args) and str(folder) in args
    except psutil.AccessDenied:
        # An observation failure must not be mistaken for a dead supervisor.
        return True
    except (psutil.NoSuchProcess, TypeError):
        return False


def watch(folder):
    import win32api
    import win32event
    mutex = win32event.CreateMutex(None, False, "Local\\FlightValidationWatch_" + hashlib.sha256(str(folder).encode()).hexdigest()[:24])
    if win32api.GetLastError() == 183:
        win32api.CloseHandle(mutex)
        raise SystemExit("A watcher for this batch is already running")
    manifest = campaign.read_json(folder / "manifest.json")
    script = folder / "source/scripts/validation_campaign.py"
    monitor = campaign.read_json(folder / "watch_state.json", {})
    monitor.update(status="watching", watcher_pid=os.getpid(), started_at=monitor.get("started_at", stamp()),
                   maximum_observed_active=monitor.get("maximum_observed_active", 0),
                   recoveries=monitor.get("recoveries", 0), sample_interval_seconds=300,
                   liveness_interval_seconds=30, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    last_sample = 0
    try:
        campaign.verify_source(folder, manifest)
        while True:
            state = campaign.read_json(folder / "state.json")
            if not state:
                event(folder, "state_temporarily_unavailable")
                monitor.update(updated_at=stamp(), last_observation_error="Batch state temporarily unreadable; no restart requested")
                campaign.atomic_json(folder / "watch_state.json", monitor)
                time.sleep(1)
                continue
            snapshot = brief(state, manifest)
            running = [j for j in manifest["jobs"] if state["jobs"][j["id"]]["status"] == "running"]
            monitor["maximum_observed_active"] = max(monitor["maximum_observed_active"], len(running))
            if len(running) > 2 or (len(running) > 1 and any(j["exclusive"] for j in running)):
                (folder / "STOP").touch()
                event(folder, "concurrency_violation_stop", jobs=[j["id"] for j in running])
                raise ValueError("Concurrency/exclusive timing constraint violated; STOP requested")
            pid = state.get("supervisor_pid") or campaign.read_json(folder / "supervisor_pid.json", {}).get("pid")
            supervisor_alive = alive(pid, script, folder)
            if state["status"] == "finished" and not supervisor_alive:
                report = finalize(folder, manifest, state, monitor)
                monitor.update(status="finished", final_report=str(report), finished_at=stamp())
                event(folder, "finished", report=str(report), **snapshot)
                break
            if not supervisor_alive and state["status"] != "finished":
                if (folder / "STOP").exists() or monitor["recoveries"] >= 3 or time.time() >= (state.get("deadline_epoch") or float("inf")):
                    raise RuntimeError("Supervisor stopped; explicit STOP, expired deadline or recovery limit prevents auto-resume")
                campaign.verify_source(folder, manifest)
                event(folder, "supervisor_recovery", previous_pid=pid)
                restored = subprocess.run([sys.executable, str(script), "resume", "--folder", str(folder)],
                                          capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                monitor["recoveries"] += 1
                if restored.returncode:
                    raise RuntimeError(restored.stderr.decode("utf-8", errors="replace"))
            if time.monotonic() - last_sample >= 300:
                event(folder, "sample", **snapshot)
                update_todo(folder, snapshot)
                last_sample = time.monotonic()
            monitor.update(updated_at=stamp(), snapshot=snapshot, supervisor_alive=supervisor_alive)
            campaign.atomic_json(folder / "watch_state.json", monitor)
            time.sleep(30)
    except BaseException:
        monitor.update(status="error", error=traceback.format_exc(), updated_at=stamp())
        event(folder, "watch_error", error=monitor["error"])
        raise
    finally:
        campaign.atomic_json(folder / "watch_state.json", monitor)
        win32api.CloseHandle(mutex)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "watch", "report"))
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    folder = args.folder.resolve()
    if args.action == "watch":
        watch(folder)
    elif args.action == "report":
        state = campaign.read_json(folder / "state.json")
        if state.get("status") != "finished":
            raise SystemExit("Reports require a finished batch")
        print(finalize(folder, campaign.read_json(folder / "manifest.json"), state,
                       campaign.read_json(folder / "watch_state.json", {})))
    else:
        existing = campaign.read_json(folder / "watch_state.json", {})
        if alive(existing.get("watcher_pid"), Path(__file__).resolve(), folder):
            print(json.dumps({"status": "already_watching", "pid": existing["watcher_pid"]}))
            return
        log = (folder / "watcher.log").open("ab", buffering=0)
        child = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "watch", "--folder", str(folder)],
                                 cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        log.close()
        print(json.dumps({"status": "started", "pid": child.pid, "sample_seconds": 300, "folder": str(folder)}))


if __name__ == "__main__":
    main()
