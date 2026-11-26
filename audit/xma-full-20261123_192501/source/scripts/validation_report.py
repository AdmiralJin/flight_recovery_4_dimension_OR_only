"""Detailed, evidence-based baseline report, including completed-but-unconverged jobs.

The optional --wait process only polls local state and never runs a solver.
Reports are immutable timestamped files; baseline results are never rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import validation_campaign as campaign
from scripts import validation_watch as watch


def cell(value):
    return str(value if value is not None else "缺失").replace("|", "/").replace("\n", " ")


def number(value):
    return f"{value:.6g}" if isinstance(value, (int, float)) and math.isfinite(value) else "缺失"


def measured(result):
    return [r for r in result.get("records", []) if r.get("repetition", 0) >= 0]


def diagnosis(item):
    status, result = item["status"], item["result"]
    if status not in ("passed", "completed"):
        return {"failed": "正确性断言失败", "error": "执行异常", "timed_out": "硬时限终止",
                "resource_limited": "资源受限", "license_limited": "许可证受限",
                "dependency_limited": "依赖受限", "input_limit": "候选或输入规模门槛",
                "inconclusive": "未得到确定结论", "cancelled": "主动停止或未执行",
                "not_run_budget": "批次预算内未执行", "interrupted": "运行中断",
                "blocked_by_correctness": "前置正确性失败阻塞"}.get(status, "尚未完成")
    rows = [r for r in measured(result) if r.get("optimization_status")]
    if rows:
        groups = defaultdict(list)
        for row in rows:
            groups[row.get("comparison_key")].append(row)
        for group in groups.values():
            statuses = {r["optimization_status"] for r in group}
            if "infeasible" in statuses and any(
                r["optimization_status"] == "optimal" or r.get("audit_valid") is True for r in group
            ):
                return "重复测量的可行性结论冲突，需复核"
            optimal = [r for r in group if watch.closed_and_audited(r)]
            if optimal:
                objectives = [r["objective"] for r in optimal]
                if max(objectives) - min(objectives) > max(1e-6, abs(objectives[0]) * 1e-8):
                    return "重复最优目标不一致，需复核"
        statuses = {r["optimization_status"] for r in rows}
        if statuses == {"infeasible"}:
            markers = {"3", "certified_master_infeasible", "certified_integer_infeasible"}
            if all(str((r.get("diagnostics") or {}).get("terminal_reason")) in markers for r in rows):
                return "求解器认证不可行"
            return "不可行状态缺少认证标记，需复核"
        if all(watch.closed_and_audited(r) for r in rows):
            if item["job"]["kind"] == "metamorphic":
                return "变形关系断言通过，各问题最优性分别认证"
            return "审计、目标与上下界闭合的最优解"
        if any(r.get("optimization_status") == "optimal" and not watch.closed_and_audited(r) for r in rows):
            return "标为最优但证据不足，需复核"
        if any(r.get("audit_valid") is True and r.get("objective") is not None for r in rows):
            return "有合法可行解，未全部证明最优"
        if any(r.get("optimization_status") in ("not_converged", "aborted") for r in rows):
            return "未收敛，缺少经审计的全局可行解"
    optimization = result.get("optimization_status")
    if optimization == "lp_optimal":
        return "LP 最优及定价终止审计通过"
    if optimization == "optimal":
        if item["job"]["kind"] == "air_oracle":
            return "联合 Oracle 与 Benders/B&P 最优一致"
        diag = result.get("diagnostics") or {}
        proof = {"optimization_status": optimization, "objective": diag.get("objective", diag.get("upper_bound")),
                 "audit_valid": diag.get("integrated_audit_pass"), "diagnostics": diag}
        return "审计、目标与上下界闭合的最优解" if watch.closed_and_audited(proof) else "标为最优但证据不足，需复核"
    if optimization == "infeasible":
        return "返回不可行，认证与边界见原始结果"
    if optimization == "not_run":
        return "输入合同或预检完成，未运行优化"
    if optimization in ("not_converged", "feasible", "aborted"):
        return "优化未闭合，未证明最优"
    return "测试断言通过" if status == "passed" else "测量完成，未直接证明最优"


def reason(item):
    result, job = item["result"], item["job"]
    parts = [result.get("summary") or result.get("reason") or item.get("stop_reason") or "见独立证据文件"]
    diagnostics = [r.get("diagnostics", {}) for r in measured(result)]
    if result.get("diagnostics"):
        diagnostics.append(result["diagnostics"])
    terminal = sorted({str(d["terminal_reason"]) for d in diagnostics if d.get("terminal_reason")})
    if terminal:
        parts.append("停止原因=" + ", ".join(terminal))
    errors = result.get("readiness", {}).get("errors", [])
    if errors:
        parts.append("输入门槛=" + "; ".join(str(e) for e in errors))
    if item["status"] == "timed_out":
        parts.append(f"进程树墙钟上限 {job['wall_seconds']}s，含构模和落盘")
    if item["status"] == "resource_limited":
        parts.append(f"进程树提交内存上限 {job['memory_gib']}GiB；具体触发项见 reason/worker.log")
    return "; ".join(parts)


def link(path, report):
    import os
    relative = os.path.relpath(str(path), str(report.parent)).replace("\\", "/")
    return f"[{Path(path).name}]({relative})"


def candidate_expansion_section(folder, items, report):
    path = folder / "real_candidate_expansion_audit.json"
    data = campaign.read_json(path)
    if data is None:
        return []
    index = {item["job"]["id"]: item for item in items}
    if len(data.get("inputs", [])) != 2:
        raise ValueError("Supplemental candidate audit requires both input witnesses")
    for entry, objective in zip(data["inputs"], (data["coarse_objective"], data["fine_objective"])):
        if hashlib.sha256(Path(entry["input_path"]).read_bytes()).hexdigest() != entry["input_sha256"]:
            raise ValueError("Supplemental candidate input changed")
        records = measured(index[entry["id"]]["result"])
        if not records or not watch.closed_and_audited(records[0]) or not math.isclose(
                records[0]["objective"], objective, rel_tol=1e-8, abs_tol=1e-6):
            raise ValueError("Supplemental candidate audit disagrees with certified results")
    passed = all(data.get(key) is True for key in (
        "same_dataset", "same_costs", "candidate_inclusion", "both_optimal_audited_and_bound_closed",
        "objective_nonworsening", "passed"))
    return ["", "### 补充：真实样本候选扩充的合理性核查", "",
            f"实际 {data['flights']} 班，输入和成本相同。原始输入 hash、两项最优结果及独立审计已再次核对；此补充检查不计入原任务数。",
            f"候选数 {data['coarse_candidates']} → {data['fine_candidates']}；最优目标 {number(data['coarse_objective'])} → {number(data['fine_objective'])}。",
            f"粗档候选包含于细档、扩充候选后目标不变差：**{'通过' if passed else '未通过'}**。证据：{link(path, report)}。"]


def write(folder, output=None, *, save_metadata=True):
    folder = Path(folder).resolve()
    manifest = campaign.read_json(folder / "manifest.json")
    state = campaign.read_json(folder / "state.json")
    if not state or state.get("status") != "finished":
        raise ValueError("Detailed baseline report requires every batch job to be terminal")
    if any(row["status"] not in campaign.TERMINAL for row in state["jobs"].values()):
        raise ValueError("Finished state contains unfinished jobs")
    items = watch.collect(folder, manifest, state)
    for item in items:
        item["diagnosis"] = diagnosis(item)
        item["stop_reason"] = state["jobs"].get(item["job"]["id"], {}).get("reason")
        item["reason"] = reason(item)
    comparisons = watch.timing_comparisons(items)
    baseline_comparisons = watch.repair_comparisons(manifest,items) if manifest.get("repair_of") else []
    report = Path(output) if output else ROOT / "docs/codex_reports" / (
        datetime.now(watch.LOCAL).strftime("%Y%m%d_%H%M%S") + "_algorithm_validation_detailed_baseline.md")
    if report.exists():
        raise FileExistsError(f"Refusing to replace an existing scientific report: {report}")
    counts = Counter(x["status"] for x in items)
    conclusions = Counter(x["diagnosis"] for x in items)
    groups = defaultdict(list)
    for item in items:
        groups[item["job"]["lane"]].append(item)
    cases = [x for x in items if x["job"]["kind"] == "pytest"]
    pytest_counts = Counter()
    skipped = 0
    for item in cases:
        pytest_counts.update(item["result"].get("counts", {}))
        skipped += len(item["result"].get("skipped_tests", []))
    title = "算法修复完整复测报告" if manifest.get("repair_of") else "算法验证详细基线报告"
    provenance = (f"修复基线：`{manifest['repair_of']}`；全部原任务重新执行，未继承任何旧通过结果。"
                  if manifest.get("repair_of") else
                  "本报告记录修复前冻结代码的实际测试结果。后续算法修复与复测须建立新证据目录，不覆盖本报告或基线输入。")
    rows = ["# "+title, "", f"生成时间：{watch.stamp()}。", "",
            f"最终续测批次：`{folder}`；包含跨批次去重后的 {len(items)} 个任务。",
            provenance, "",
            "## 1. 完成情况与判定口径", "", f"任务执行状态：`{json.dumps(dict(counts), ensure_ascii=False)}`。",
            f"pytest 文件任务 {len(cases)} 项；底层测试报告计数 `{json.dumps(dict(pytest_counts), ensure_ascii=False)}`，另有跳过 {skipped} 项。任务数与底层断言数分开统计。",
            "`passed` 表示本测试断言通过；`completed` 只表示测量完成。最优性另外核查独立审计、目标、上下界及参考断言，不能将三次未收敛当作三次最优。",
            "AIR 与厦航、Tianchi 与 AIR 目标、LP 与整数最优、固定候选与动态候选分别判断；相同最优目标允许不同资源串 ID。", "",
            "| 科学或执行结论 | 任务数 |", "|---|---:|"]
    for label, count in sorted(conclusions.items()):
        rows.append(f"| {label} | {count} |")
    rows += ["", "## 2. 来源、配置和测试公平性", "",
             f"- 已核验本批 {len(manifest.get('source_hashes', {}))} 个冻结文件、不可变任务清单及 {len(manifest.get('carried_forward_results', []))} 份继承结果 SHA256。",
             "- 原批次中被替代的失败尝试继续保留；本报告按任务 ID 使用最近一次有效执行证据，不将旧失败与修复后的通过重复计数。",
             f"- 批次预算 {manifest.get('campaign_hours')} 小时，最大并发 {manifest.get('max_parallel', 2)}；性能任务独占、求解器单线程；当前资源等待策略 `{manifest.get('resource_wait', True)}`。",
             "- 重型单例最长 2 小时；轻/中/重进程树提交内存约 1.5/2.5/4GiB。原始预算以每项 manifest/job.json 为准。",
             "- 厦航粗档步长/延误上限 60/120 分钟，细档 30/1440 分钟；随机种子 20261106、20261107。整条机尾选样的实际航班数可高于目标数。",
             "- 性能加速比仅在同问题、三次均最优、审计通过且目标相等时计算。建模、候选、求解、审计和端到端时间见各记录，不把嵌套子问题界作为全局界。",
             "- 显式路径 Oracle 只用于小例子。全量细档的预检是候选规模检查，不是一次大型优化成功。", "",
             "## 3. 各路线覆盖和结果", "", "| 路线 | 任务数 | 执行状态 |", "|---|---:|---|"]
    for lane, title, _label in manifest["lanes"]:
        group = groups[lane]
        rows.append(f"| {cell(title)} | {len(group)} | {cell(dict(Counter(x['status'] for x in group)))} |")
    rows += candidate_expansion_section(folder, items, report)
    if baseline_comparisons:
        mismatches=[x for x in baseline_comparisons if x["certified_objective_mismatches"]]
        rows += ["", "### 修复前后证据关联", "",
                 f"逐项核验 {len(baseline_comparisons)} 份旧结果 SHA256 并关联本轮重跑；已认证最优目标不一致 {len(mismatches)} 项。",
                 "执行 completed 与优化未收敛仍分别记录；详细状态、目标冲突见本批 baseline_to_repair_comparisons.json。"]
    rows += ["", "## 4. 未通过、未收敛、受限及证据不足的项目", "",
             "以下将执行失败与优化目标未实现分别列出；超时、许可证和内存限制不自动等价于算法数学错误。", "",
             "| 任务 ID / 名称 | 执行状态 | 具体结论 | 原因 | 证据 |", "|---|---|---|---|---|"]
    concerns = [x for x in items if x["status"] not in ("passed", "completed") or any(
        token in x["diagnosis"] for token in ("未收敛", "未闭合", "证据不足", "未直接证明", "未全部证明", "需复核"))]
    for item in concerns:
        job = item["job"]
        rows.append(f"| `{job['id']}` {cell(job['name'])} | {item['status']} | {item['diagnosis']} | {cell(item['reason'])} | {link(item['result_path'], report)} |")
    if not concerns:
        rows.append("| 无 | — | — | — | — |")
    rows += ["", "## 5. 列生成、分解与耗时收益", "", "### 5.1 AIR 全列 LP 与列生成", "",
             "速度比定义为全列流程中位耗时 / CG 流程中位耗时；小于 1 表示本实例 CG 更慢。它与最优性审计是两项结论，不能用正确性通过替代性能提速。", "",
             "| 任务 | 速度比 | 全列列数 | CG 列数 | 判定 |", "|---|---:|---|---|---|"]
    for item in items:
        if item["job"]["kind"] == "air_cg":
            r = item["result"]
            full = [v.get("columns") for v in measured(r) if v.get("method") == "full"]
            cg = [v.get("columns") for v in measured(r) if v.get("method") == "cg"]
            ratio = r.get("observed_speedup")
            rows.append(f"| {cell(item['job']['name'])} | {number(ratio)} | {full} | {cg} | {cell(r.get('speed_conclusion', item['status']))} |")
    rows += ["", "### 5.2 厦航真实样本逐组对照", "",
             "每组比较键由固定输入、目标和候选空间生成；三种算法各有预热及三次正式测量。不同目标的费用不横向比较。", ""]
    for comparison in comparisons:
        rows += [f"#### 问题键 `{comparison['comparison_key']}`", "",
                 f"三算法均证明最优且目标一致：**{'是' if comparison['three_methods_certified_and_equal'] else '否'}**。", "",
                 "| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |", "|---|---:|---|---|---:|---|---:|"]
        for method, data in comparison["methods"].items():
            ratio = comparison["certified_speedups_vs_direct"].get(method)
            rows.append(f"| {method} | {data['flights']} | {cell(data['statuses'])} | {cell(data['objectives'])} | {number(data['median_seconds'])} | {cell(data['range_seconds'])} | {number(ratio)} |")
    rows += ["", "## 6. 全部任务逐项证据", "",
             "以下每一项均保留名称、配置、预算、执行结论及原始证据。最优性表中的缺失值保持缺失，不按零处理。", ""]
    for lane, title, _label in manifest["lanes"]:
        rows += [f"### {title}", ""]
        for item in groups[lane]:
            job, result = item["job"], item["result"]
            rows += [f"#### `{job['id']}` · {job['name']}", "",
                     f"- 执行状态：`{item['status']}`；结论：**{item['diagnosis']}**。",
                     f"- 类型：`{job['kind']}`；阶段：`{job.get('phase')}`；单例墙钟/求解器预算：{job['wall_seconds']}/{job['solver_seconds']} 秒；提交内存上限：{job['memory_gib']}GiB。",
                     f"- 参数：`{json.dumps(job['config'], ensure_ascii=False, separators=(',', ':'))}`。",
                     f"- 观测墙钟：{number(result.get('supervisor_wall_seconds'))} 秒；进程树提交内存峰值：{number((result['process_tree_peak_commit_bytes'] / campaign.GIB) if result.get('process_tree_peak_commit_bytes') is not None else None)}GiB。",
                     f"- 结果与原因：{cell(item['reason'])}。",
                     f"- 原始证据：{link(item['result_path'], report)}；SHA256 `{item.get('result_sha256') or '无结果文件'}`。"]
            if result.get("expected"):
                rows.append(f"- 参考断言：`{json.dumps(result['expected'], ensure_ascii=False)}`。")
            partial = result.get("partial_progress")
            if partial:
                rows.append(f"- 硬停时进度：阶段 `{partial.get('stage', '缺失')}`，全局 LB={number(partial.get('lower_bound'))}，UB={number(partial.get('upper_bound'))}，相对 Gap={number(partial.get('relative_gap'))}。进度中的界须与保存方案及独立审计分开判断，不单凭上界认定已有可复用的合法方案。")
            records = measured(result)
            if not records and result.get("optimization_status"):
                diag = result.get("diagnostics") or {}
                records = [{"method": diag.get("algorithm", job['kind']), "optimization_status": result["optimization_status"],
                            "objective": diag.get("objective", diag.get("upper_bound")), "diagnostics": diag,
                            "audit_valid": diag.get("integrated_audit_pass")}]
            if records:
                rows += ["", "| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |", "|---|---|---:|---:|---:|---|---:|---:|---:|"]
                for rec in records:
                    d = rec.get("diagnostics") or {}
                    timing=rec.get("stage_timings",result.get("timings",{}))
                    rows.append(f"| {rec.get('method', '')}/{rec.get('repetition', '')} | {rec.get('optimization_status', '见测试断言')} | {number(rec.get('objective'))} | {number(d.get('lower_bound'))} | {number(d.get('upper_bound'))} | {cell(rec.get('audit_valid'))} | {number(rec.get('seconds'))} | {number(timing.get('first_global_incumbent_seconds'))} | {number(timing.get('first_audited_feasible_seconds'))} |")
            rows.append("")
    rows += ["## 7. 修复方向与复测要求", "",
             "已观察到的真实样本问题优先由对应事件和停止原因定位，不按未收敛实例的 incumbent 大小判定单调性错误。",
             "若 Benders 多次排除完整不可行计划却没有全局可行上界，应检查可行性割的泛化能力、资源松弛是否缺失，以及可行解初始化。该项是待验证的性能根因，不能凭日志将其认定为数学正确性错误。",
             "AIR 压力任务也需检查完整计划条件割是否造成反复枚举，以及全局时限是否仅分配到单个子求解。保留硬停前的全局界，修复时争取在预算内正常返回可审计方案与未闭合状态。",
             "修复须保留真正的列生成、整数分支与全局界证明，不将算法名称改为直接模型调用来获得表面通过。新增割应以小规模穷举或 Oracle 检查对所有可行计划有效。",
             "修复后执行相关单元/API/回归、小例子四算法双目标对拍、原先未收敛的同输入同预算复测，以及递增压力；保留旧结果、新结果、修复内容和仍受限项目。",
             "许可证、依赖和机器内存的外部限制需单列；不能通过取消审计、放宽业务约束或将预检当作求解来消除失败。", ""]
    campaign.atomic_text(report, "\n".join(rows))
    metadata = {"generated_at": watch.stamp(), "report": str(report), "batch": str(folder),
                "status_counts": dict(counts), "diagnoses": dict(conclusions), "concern_jobs": [x['job']['id'] for x in concerns],
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if save_metadata:
        campaign.atomic_json(folder / "detailed_report.json", metadata)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    folder = args.folder.resolve()
    if args.wait:
        while campaign.read_json(folder / "state.json", {}).get("status") != "finished":
            time.sleep(60)
        # Load the final report implementation after the long wait, so fixes to
        # evidence interpretation made during the campaign are not lost.
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--folder", str(folder)], check=True)
        return
    print(write(folder))


if __name__ == "__main__":
    main()
