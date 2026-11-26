"""Export one evidence-backed Chinese CSV row per registered or supplementary task.

Read-only with respect to campaign inputs/results. Uses the standard-library CSV
fallback because the spreadsheet skill's artifact runtime is unavailable here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "任务与结论": "任务编号|任务范围|实验阶段|任务类型|算法代码|算法名称|配置求解器|清单默认后端|清单覆盖后端|求解器版本|是否预热|重复编号|是否实际执行|任务状态|原始任务状态|优化状态|原始优化状态|结论|问题原因|原因证据等级|后续处理建议",
    "来源与规模": "来源数据包|来源包性质|包内公开实例数|包内计划总记录数|包内扰动总记录数|包内连接总记录数|包内飞机字典记录数|包内机场字典记录数|派生实例编号|原实例或日期窗口|模型类型|相关样本块|源实例或上下文计划记录数|源实例航班定义数|源实例飞机清单数|源实例机场数|源实例旅客组数|源实例旅客需求人数|任务目标航班数|任务实际航班数|任务实际飞机数|任务涉及机场数|场景声明机场数|任务机型配置数|任务飞机座位合计_座|任务飞机最小座位_座|任务飞机最大座位_座|任务最短过站_分钟|任务最长过站_分钟|任务优化旅客组数|任务优化旅客人数|关联原始旅客组数|关联原始旅客需求人数|完整落入任务的原始旅客组数|完整落入任务的原始旅客需求人数|原始航段登机人数合计|任务机组数|固定上下文航班数|排除的原始旅客组数|时间窗口开始_源时间|时间窗口结束_源时间|窗口小时数",
    "扰动与资源边界": "源实例航班扰动记录数|源实例飞机不可用记录数|源实例机场容量扰动记录数|源上下文事件记录数|任务正延误航班数|任务源正延误合计_分钟|任务源最大正延误_分钟|任务固定执行航班数|任务强制取消航班数|任务匹配事件数|任务负起飞延误事件数|任务飞机不可用区间数|资源就绪晚于首班计划的飞机数|任务维护缺口飞机数|不可用语义未明预检项数|任务扰动类型分布|任务扰动原因分布|扰动摘要|固定资源边界摘要",
    "答案与结果": "公开数据答案值_原规则|公开答案性质与适用范围|公开答案来源|公开答案团队|公开答案是否竞赛计分|公开答案能否直接比较|不可直接比较原因|研究模型已认证最优参考值|研究参考证据任务|研究参考值适用范围|本次结果目标值|本次LB|本次UB|本次Gap_比例|是否认证模型最优|是否认证研究问题不可行|是否仅预处理|是否实际调用优化器|独立方案审计通过|独立复算目标值|审计违规数|原规则检查通过|原规则违规文件|原规则违规条数|官方评分结果|相对历史成绩差距_比例|终止原因|不可行证书摘要",
    "时间与资源": "任务名义时限_秒|本次求解入口时限_秒|进程监护墙钟上限_秒|阶段预算上限_秒|本批总预算上限_小时|求解入口总耗时_秒|求解器调用累计_秒|构模接口累计_秒|独立枚举耗时_秒|独立审计耗时_秒|工作进程内部耗时_秒|任务实际进程墙钟_秒|原始elapsed_seconds_秒|规范化及候选生成耗时_秒|时间统计说明|开始时间_北京时间|结束时间_北京时间|内存硬上限_GiB|峰值进程树RSS_MiB|峰值进程树提交内存_MiB|求解线程数|最大任务并发数|求解器错误码|求解器模型变量数|求解器模型约束数",
    "候选与限制": "候选时间步长_分钟|最大允许延误_分钟|抽样种子|是否按能力预筛机尾|预筛排除机尾数|航班候选数|执行候选数|取消候选数|旅客行程候选数|候选与飞机配对规模|规模预检上限_候选飞机对|任务停止实验类型|Benders迭代上限|CG迭代上限|分支节点上限|分支深度上限|枚举航班上限|枚举路径上限|枚举访问节点上限|能力预检就绪|能力预检缺口代码|能力预检缺口明细|航班及换机限制|终端与固定上下文限制|机场容量规则|旅客及机组限制|成本口径|模型与原规则差异|实际配置摘要",
    "算法过程与业务结果": "完整枚举路径数|完整枚举访问节点数|枚举是否完整|Benders实际迭代数|飞机CG调用数|飞机生成列数|分支定价节点数|分支定价最大深度|全列LP目标|CG目标|全列整数目标|分支定价目标|定价终止审计通过|组件对拍结论|取消航班数|延误航班数|航班起飞延误合计_分钟|换机航班数|未服务优化旅客人数|优化旅客延误_人分钟|停止后是否保留合法方案|原始取消航段登机人数暴露|原始延误航段登机人数暴露",
    "追溯与附加资料": "源文件及SHA256|冻结输入文件|本次执行输入文件|原始结果证据文件|检查点文件|问题指纹SHA256|冻结输入SHA256|本次执行输入SHA256|结果证据SHA256|配置指纹SHA256|候选指纹SHA256|成本指纹SHA256|正式清单SHA256|运行代码提交|基线提交|参考结果工作簿数|参考结果工作表数|发布者运行记录数|可用发布者参考记录数|非零CV记录数|公式错误单元格数|汇总辅助记录数|补充说明",
}
FIELDS = [f for names in GROUPS.values() for f in names.split("|")]
ALGORITHMS = {
    "integrated_oracle": "AIR完整列联合整数Oracle",
    "fixed_benders": "AIR固定全列Benders",
    "air_cg": "AIR Benders＋列生成",
    "air_bp": "AIR Benders＋列生成＋分支定价",
    "xma_joint_arc_flow": "厦航直接联合弧流模型",
    "xma_joint_path_oracle": "厦航完整路径Oracle",
    "xma_benders_joint": "厦航Benders联合追索",
    "xma_benders_cg_bp": "厦航Benders＋CG/B&P",
}
PHASES = dict(correctness="正确性", comparison="规模与算法对照", stability="稳定性及停止", stress="整例及压力")
KINDS = dict(solve="算法求解", stop="停止合同实验", components="固定计划组件对拍",
             external="ROADEF原规则检查", workbench="v3运行及页面接口复核", pytest="既有后端回归")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def flag(value):
    return None if value is None else "是" if value else "否"


def relative(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def bj(value):
    if not value:
        return None
    from zoneinfo import ZoneInfo
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Shanghai")).isoformat()


def sample(values, maximum=8):
    values = list(values)
    return "；".join(map(text, values[:maximum])) + (f"；另有{len(values)-maximum}项，见输入证据" if len(values) > maximum else "")


def negative(value):
    try:
        return float(value) < 0
    except (ValueError, TypeError):
        return False


def empty():
    return {f: None for f in FIELDS}


def metadata(public, entry, package_info):
    source, scenario = public["source"], public["scenario"]
    policy, context = public["candidate_policy"], public["fixed_context"]
    records, fixed = source["records"], context["flights"]
    all_records = records + fixed
    flights, planes, pax = scenario["flights"], scenario["aircraft"], scenario["passengers"]
    tables = source["raw_tables"]
    roadef = source["dataset"] == "roadef2009"
    selected_ids = {f["id"] for f in records}
    airports = {f[k] for f in records for k in ("origin", "destination")}
    journeys = [*context["excluded_journeys"], *[
        dict(id=p["pax_group_id"], count=p["count"], legs=p["original_itinerary"], missing=[]) for p in pax]]
    related = [j for j in journeys if selected_ids.intersection(j["legs"])]
    inside = [j for j in journeys if j["legs"] and not j["missing"] and set(j["legs"]) <= selected_ids]
    events = {str(e["_source_row"]): e for f in records for e in f.get("events", [])}
    issues = entry["precheck"]["issues"]
    positive = [f for f in records if f["delay"] > 0]
    raw_aircraft = tables.get("aircraft.csv", [])
    raw_journeys = tables.get("itineraries.csv", [])
    boardings = (sum(j["count"]*sum(fid in selected_ids for fid in j["legs"]) for j in journeys) if roadef
                 else sum(int(f["raw"].get("PAX_ECONOMY", 0))+int(f["raw"].get("PAX_BUSINESS", 0)) for f in records))
    first = {a["tail_id"]: min(f["sched_dep"] for f in flights if f["original_aircraft"] == a["tail_id"]) for a in planes}
    late_ready = sum(bool(a.get("ready_at")) and datetime.fromisoformat(a["ready_at"].replace("Z", "+00:00")) >
                     datetime.fromisoformat(first[a["tail_id"]].replace("Z", "+00:00")) for a in planes)
    config = public["configs"]
    seat_counts = [sum(map(int, a["equipment_type"].rsplit(":", 2)[-2].split("/"))) for a in planes]
    turn_times = [int(a["equipment_type"].rsplit(":", 1)[-1].removeprefix("T")) for a in planes]
    row = dict(package_info)
    row.update({
        "派生实例编号": entry["id"], "原实例或日期窗口": source["source_instance"],
        "模型类型": "飞机＋旅客恢复" if public["model_type"] == "aircraft_passenger" else "飞机恢复",
        "相关样本块": entry["block"], "源实例或上下文计划记录数": len(all_records),
        "源实例航班定义数": len(tables["flights.csv"]) if roadef else None,
        "源实例飞机清单数": len(raw_aircraft) if roadef else len({f["tail"] for f in all_records}),
        "源实例机场数": len(scenario["airports"]),
        "源实例旅客组数": len(raw_journeys) if roadef else None,
        "源实例旅客需求人数": sum(int(j["tokens"][3]) for j in raw_journeys) if roadef else None,
        "任务目标航班数": policy["target_flights"] if policy["target_flights"] < 10**9 else None,
        "任务实际航班数": len(flights), "任务实际飞机数": len(planes),
        "任务涉及机场数": len(airports), "场景声明机场数": len(scenario["airports"]),
        "任务机型配置数": len({a["equipment_type"] for a in planes}),
        "任务飞机座位合计_座": sum(seat_counts), "任务飞机最小座位_座": min(seat_counts),
        "任务飞机最大座位_座": max(seat_counts), "任务最短过站_分钟": min(turn_times), "任务最长过站_分钟": max(turn_times),
        "任务优化旅客组数": len(pax), "任务优化旅客人数": sum(p["count"] for p in pax),
        "关联原始旅客组数": len(related) if roadef else None,
        "关联原始旅客需求人数": sum(j["count"] for j in related) if roadef else None,
        "完整落入任务的原始旅客组数": len(inside) if roadef else None,
        "完整落入任务的原始旅客需求人数": sum(j["count"] for j in inside) if roadef else None,
        "原始航段登机人数合计": boardings, "任务机组数": len(scenario["crew"]),
        "固定上下文航班数": len(fixed), "排除的原始旅客组数": len(context["excluded_journeys"]) if roadef else None,
        "时间窗口开始_源时间": scenario["recovery_window"]["start_time"],
        "时间窗口结束_源时间": scenario["recovery_window"]["end_time"], "窗口小时数": context["window_hours"],
        "源实例航班扰动记录数": len(tables["alt_flights.csv"]) if roadef else None,
        "源实例飞机不可用记录数": len(tables["alt_aircraft.csv"]) if roadef else None,
        "源实例机场容量扰动记录数": len(tables["alt_airports.csv"]) if roadef else None,
        "源上下文事件记录数": len(tables["events"]) if not roadef else None,
        "任务正延误航班数": len(positive), "任务源正延误合计_分钟": sum(f["delay"] for f in positive),
        "任务源最大正延误_分钟": max((f["delay"] for f in positive), default=0),
        "任务固定执行航班数": sum(f.get("fixed_delay") is not None for f in records),
        "任务强制取消航班数": sum(bool(f.get("cancel_required")) for f in records),
        "任务匹配事件数": len(events) if not roadef else None,
        "任务负起飞延误事件数": sum(negative(e.get("DEPARTURE_DELAY")) for e in events.values()) if not roadef else None,
        "任务飞机不可用区间数": sum(len(a.get("unavailable", [])) for a in planes),
        "资源就绪晚于首班计划的飞机数": late_ready,
        "任务维护缺口飞机数": len({i["tail"] for i in issues if i["code"] == "unsupported_maintenance"}),
        "不可用语义未明预检项数": sum(i["code"] == "AC_Unavailable_interval_semantics_not_documented" for i in issues),
        "任务扰动类型分布": dict(Counter(e["DISRUPTION_TYPE"] for e in events.values())) if events else None,
        "任务扰动原因分布": dict(Counter(e.get("CAUSE", "未提供") for e in events.values())) if events else None,
        "扰动摘要": (f"原实例航班扰动{len(tables.get('alt_flights.csv', []))}条、飞机不可用{len(tables.get('alt_aircraft.csv', []))}条、机场容量扰动{len(tables.get('alt_airports.csv', []))}条。" if roadef else
                  f"本任务组合键匹配{len(events)}条事件。正起飞延误作静态下界，负值原样保留但不生成提前候选，AC Unavailable语义不明时预检拒绝。") +
                 f"任务自身正延误{len(positive)}班；{late_ready}架飞机的就绪时刻晚于首班原计划。固定上下文也可能迫使任务航班延误。",
        "固定资源边界摘要": sample(f"{a['tail_id']}:{a['initial_station_at_t']}→{a['required_station_at_T_end']}，ready={a.get('ready_at')}，until={a.get('available_until')}" for a in planes),
        "规范化及候选生成耗时_秒": entry.get("normalization_and_candidates_seconds"),
        "候选时间步长_分钟": policy["step_minutes"], "最大允许延误_分钟": policy["max_delay_minutes"],
        "抽样种子": policy["selection_seed"], "是否按能力预筛机尾": flag(policy["capability_filter"]),
        "预筛排除机尾数": len(policy["excluded_unsupported_tails"]),
        "航班候选数": len(public["recovery_columns"]["flight_options"]),
        "执行候选数": sum(o["operation_type"] == "operate" for o in public["recovery_columns"]["flight_options"]),
        "取消候选数": sum(o["operation_type"] == "cancel" for o in public["recovery_columns"]["flight_options"]),
        "旅客行程候选数": len(public["recovery_columns"]["passenger_itineraries"]),
        "候选与飞机配对规模": len(public["recovery_columns"]["flight_options"])*len(planes),
        "规模预检上限_候选飞机对": 1000000,
        "CG迭代上限": config["aircraft_string_cg"]["max_iterations"],
        "分支深度上限": config["branch_and_price"]["max_depth"],
        "能力预检就绪": flag(entry["precheck"]["ready"]),
        "能力预检缺口代码": "；".join(sorted({i["code"] for i in issues})) or "无",
        "能力预检缺口明细": sample(issues),
        "航班及换机限制": "完整选中机尾窗口内轮转；仅活跃机尾；换机须同机型/座位配置/过站时间；不补备用机；固定执行项禁止取消并保持原机尾和时间",
        "终端与固定上下文限制": "固定前缀确定位置和最早就绪，后缀限制回接；每架飞机硬终端；窗口外航班固定",
        "机场容量规则": "原容量记录保留；研究模型不施加原容量约束",
        "旅客及机组限制": "关闭CRM，不造机组；仅ROADEF完整内部原始旅客组可参与整组单舱优化；Delft航段人数不重建OD",
        "成本口径": "public_air_linear_v1抽象非负成本；非ROADEF原评分。"+text({k:v["value"] for k,v in public["costs"]["coefficients"].items()}),
        "模型与原规则差异": "无维护、原机场容量、航班串和地面交通约束；无舱等拆分/降舱与原成本；限制活跃机尾和相同配置换机，改用硬终端；见输入rule_mapping",
        "实际配置摘要": {k:{a:b for a,b in v.items() if a in ("max_iterations", "max_benders_iterations", "max_nodes", "max_depth", "absolute_gap_tolerance", "relative_gap_tolerance")} for k,v in config.items()},
        "源文件及SHA256": source["files"], "问题指纹SHA256": public["problem_sha256"],
        "冻结输入SHA256": entry["sha256"], "配置指纹SHA256": entry["fingerprints"]["configs"],
        "候选指纹SHA256": entry["fingerprints"]["candidates"], "成本指纹SHA256": entry["fingerprints"]["costs"],
        "补充说明": "旅客需求人数按行程组人数求和；航段登机人数不是独立人数。" +
                    ("源实例计划按日期展开，与航班定义行数区分。" if roadef else "源实例规模是12小时窗口外扩前后各一天的已载入上下文，不是全季度。未复现原370组。") +
                    ("本例目标为整窗口全部航班，输入中的10亿为选择全部的哨兵值，不是实际航班数。" if policy["target_flights"] >= 10**9 else ""),
    })
    return row


def error_info(evidence):
    pending = [(evidence.get("core") or {}).get("diagnostics") or {}]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("error_code") is not None:
                return value
            pending.extend(v for v in value.values() if isinstance(v, (dict, list)))
        elif isinstance(value, list):
            pending.extend(value)
    return {}


def apply_evidence(row, evidence, state, metrics=None):
    core = evidence.get("core") or {}
    diag = core.get("diagnostics") or evidence.get("diagnostics") or {}
    statistics = core.get("statistics") or {}
    timing = evidence.get("timings") or {}
    audit = evidence.get("audit") or {}
    objective = evidence.get("objective")
    if isinstance(objective, dict):
        objective = objective.get("total")
    row.update({
        "本次结果目标值": objective, "本次LB": evidence.get("lower_bound", diag.get("lower_bound")),
        "本次UB": evidence.get("upper_bound", diag.get("upper_bound")),
        "本次Gap_比例": evidence.get("gap", diag.get("gap")),
        "是否认证模型最优": flag(evidence.get("certified_optimal")),
        "是否认证研究问题不可行": flag(evidence.get("certified_infeasible")),
        "是否仅预处理": flag(evidence.get("preprocessing_only", False)),
        "独立方案审计通过": flag(audit.get("pass", diag.get("integrated_audit_pass"))),
        "独立复算目标值": audit.get("objective"),
        "审计违规数": len(audit["violations"]) if "violations" in audit else None,
        "求解入口总耗时_秒": evidence.get("runtime_seconds", diag.get("runtime_seconds")),
        "求解器调用累计_秒": timing.get("solver_call_seconds"),
        "构模接口累计_秒": timing.get("solver_construction_seconds"),
        "独立枚举耗时_秒": timing.get("enumeration_seconds"),
        "独立审计耗时_秒": timing.get("independent_audit_seconds"),
        "终止原因": diag.get("terminal_reason") or core.get("termination_reason") or core.get("reason") or evidence.get("termination_reason"),
        "不可行证书摘要": evidence.get("infeasibility_certificate"),
        "完整枚举路径数": (evidence.get("enumeration") or {}).get("paths"),
        "完整枚举访问节点数": (evidence.get("enumeration") or {}).get("nodes"),
        "枚举是否完整": flag((evidence.get("enumeration") or {}).get("complete")),
        "Benders实际迭代数": statistics.get("benders_iterations", diag.get("benders_master_iterations", len(core["iterations"]) if isinstance(core.get("iterations"), list) else diag.get("iteration"))),
        "飞机CG调用数": diag.get("aircraft_cg_calls"), "飞机生成列数": statistics.get("aircraft_columns", diag.get("aircraft_generated_columns")),
        "分支定价节点数": statistics.get("bp_nodes", diag.get("aircraft_bp_nodes")),
        "停止后是否保留合法方案": flag(state.get("retained_incumbent")),
    })
    row["是否实际调用优化器"] = "否" if evidence.get("preprocessing_only") else "是" if core else None
    err = error_info(evidence)
    if err:
        row.update({"求解器错误码": err.get("error_code"), "求解器模型变量数": err.get("variables"),
                    "求解器模型约束数": err.get("constraints")})
    if "full_lp" in evidence:
        row.update({"全列LP目标": evidence["full_lp"].get("objective_value"), "CG目标": evidence["cg"].get("objective_value"),
                    "全列整数目标": evidence["full_mip"].get("objective_value"), "分支定价目标": evidence["bp"].get("objective_value"),
                    "定价终止审计通过": flag(evidence["pricing_audit"].get("passed")),
                    "组件对拍结论": evidence["status"], "分支定价节点数": evidence["bp"].get("nodes_solved"),
                    "分支定价最大深度": evidence["bp"].get("max_depth"), "是否实际调用优化器": "是",
                    "是否认证模型最优": None, "本次Gap_比例": None})
    if metrics and metrics.get("eligible"):
        for out, key in [("取消航班数", "cancelled_flights"), ("延误航班数", "delayed_flights"),
                         ("航班起飞延误合计_分钟", "total_departure_delay_minutes"), ("换机航班数", "reassigned_flights"),
                         ("未服务优化旅客人数", "unserved_optimized_passengers"), ("优化旅客延误_人分钟", "optimized_passenger_delay_minutes"),
                         ("原始取消航段登机人数暴露", "original_boardings_on_cancelled_legs"), ("原始延误航段登机人数暴露", "original_boardings_on_delayed_legs")]:
            row[out] = metrics.get(key)


def conclusions(row, evidence, state, kind):
    verdict, status = row["任务状态"], row["优化状态"]
    row["原因证据等级"] = "逐次记录及冻结输入"
    if verdict == "blocked_by_correctness":
        row.update({"结论": "未执行，不能评价本任务解质量或性能", "问题原因": "前置正确性门槛未通过：A03及旅客耦合的部分AIR路线缺少最优证据，5个不可行组件例无可行固定计划用于对拍。", "后续处理建议": "先修正并通过微例门槛，再新建冻结批次；保留本条未执行记录"})
        if row["能力预检就绪"] == "否":
            row["问题原因"] += "另有独立能力缺口："+row["能力预检缺口代码"]+"。"
    elif verdict == "license_limited":
        row.update({"结论": "许可证受限，不能视为算法未收敛", "问题原因": "Gurobi规模许可证错误10010，内核原始状态曾包装为not_converged；新表按结构化错误恢复原因。", "后续处理建议": "显式使用HiGHS，或取得满足模型规模的Gurobi许可证"})
    elif kind == "external":
        row.update({"结论": "检查器互操作通过，但原规则方案不可行，禁止与历史成绩比较", "问题原因": "检查器返回0仍存在行程最短连接时间和飞机过站时间违规；成本评分未执行。", "后续处理建议": "补足原规则能力和完整上下文，再通过全部11项检查及成本复算"})
    elif kind == "pytest":
        row.update({"结论": "正式冻结代码572项后端单元/API/回归测试通过", "问题原因": "未观察到回归失败；不构成公开业务模型最优性或规模证据", "后续处理建议": "保留既有机组等回归范围"})
    elif kind == "workbench":
        row.update({"结论": "v3草稿、快照、实际worker及离线目标一致；四种视图接口可用", "问题原因": "未观察到接口一致性缺陷；仅覆盖代表案例", "后续处理建议": "算法修正后继续用同一指纹复核"})
    elif kind == "components" and verdict == "passed":
        row.update({"结论": "固定计划全列LP/CG、定价及全列整数/B&P一致；根节点已整数", "问题原因": "组件对拍通过，但未覆盖存在整数间隙或深分支的困难情况", "后续处理建议": "预登记有可审计LP/IP间隙的公开微例"})
    elif kind == "components":
        row.update({"结论": "组件对拍无结论，未得到可行固定计划", "问题原因": state.get("reason") or "预处理已证明原研究问题不可行；没有可行固定计划用于LP/CG/IP/B&P对拍", "后续处理建议": "保留不可行证书；另外预登记可行分层样本，不删改本例"})
    elif evidence.get("preprocessing_only"):
        row.update({"结论": "必要时间可达性预处理证明当前研究问题不可行；未运行优化算法", "问题原因": "固定上下文、硬终端和冻结候选域下，至少一架飞机无法到达要求终点。不是原业务不可行证明。", "后续处理建议": "单列不可行研究实例；进一步解释源上下文和候选限制，不纳入求解性能"})
    elif evidence.get("certified_optimal"):
        row.update({"结论": "研究模型内认证最优，审计通过且上下界闭合", "问题原因": "未观察到认证目标冲突；只适用于冻结模型、资源边界和候选空间", "后续处理建议": "保留证据；门槛通过后再做重复、网格和规模实验"})
    elif status in ("not_converged", "aborted"):
        row.update({"结论": "时限内未取得最优证据；本路线没有经审计UB", "问题原因": "约115秒停止，保留原始终止原因。独立Oracle已给出参考最优值，外层分解收敛/可行计划构造需定位。", "原因证据等级": "停止状态与界为直接证据；具体算法根因尚未证实", "后续处理建议": "优先检查AIR外层必要域、有效割及旅客耦合可行解构造；不能直接归因于定价错误"})
    else:
        row.update({"结论": f"见原始状态：{verdict}/{status}", "问题原因": state.get("error") or state.get("reason")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=ROOT/".public_benchmarks/formal-v3-20261111-r4")
    parser.add_argument("--output", type=Path, default=ROOT/"docs/benchmarks/public_v3_tasks_detailed_20261112.csv")
    args = parser.parse_args()
    folder, output = args.campaign.resolve(), args.output.resolve()
    frozen = ROOT/"docs/benchmarks/public_v3_first_batch"
    manifest, state, registry = (read(folder/n) for n in ("manifest.json", "state.json", "registry.json"))
    analysis, summary = (read(frozen/n) for n in ("analysis.json", "summary.json"))
    inventory = read(ROOT/"docs/benchmarks/public_v3_source_inventory.json")
    for name in ("manifest.json", "state.json", "registry.json"):
        assert sha(folder/name) == sha(frozen/name), f"frozen evidence mismatch: {name}"
    with (frozen/"runs.csv").open(encoding="utf-8-sig", newline="") as stream:
        normalized = {r["id"]: r for r in csv.DictReader(stream)}
    observations = {r["job"]:r["metrics"] for r in analysis["observations"]}
    references = analysis["historical_references"]
    certified = {r["instance"]:r["min_objective"] for r in summary["comparisons"] if r["consistent"]}
    infeasible = {j["instance"] for j in manifest["jobs"] if state["jobs"][j["id"]].get("certified_infeasible")}
    ref_jobs = {name: "；".join(j["id"] for j in manifest["jobs"] if j["instance"] == name and
                j["algorithm"] == "integrated_oracle" and state["jobs"][j["id"]].get("certified_optimal")) for name in certified}
    delft_root = Path(manifest["source_roots"]["TU_Delft_370_Disruptions"])/"extracted/data"
    def csv_count(name):
        with (delft_root/name).open(encoding="utf-8-sig", newline="") as stream:
            return sum(1 for _ in csv.DictReader(stream, delimiter=";"))
    delft_tables = inventory["datasets"]["TU_Delft_370_Disruptions"]["table_rows"]
    packages = {
        "roadef2009": {"来源数据包":"ROADEF_2009", "来源包性质":"原输入＋官方检查器＋历史参考上界，非已证明最优答案", "包内公开实例数":32},
        "delft2020-derived": {"来源数据包":"TU_Delft_370_Disruptions（TU Delft 2020）", "来源包性质":"原输入；原370组划分及逐例答案未核实",
            "包内计划总记录数":delft_tables["Schedule_Q1_2015_def.h5"], "包内扰动总记录数":delft_tables["Disruptions_Q1_2015_def.h5"],
            "包内连接总记录数":delft_tables["Connections_Q1_2015_def.h5"], "包内飞机字典记录数":csv_count("ACType.csv"), "包内机场字典记录数":csv_count("Airports.csv")},
    }
    metas, entries = {}, {e["id"]:e for e in registry}
    for entry in registry:
        path = folder/entry["path"]
        assert sha(path) == entry["sha256"], entry["id"]
        public = read(path)
        metas[entry["id"]] = metadata(public, entry, packages[public["source"]["dataset"]])
    rows = []
    for job in manifest["jobs"]:
        row = empty()
        entry, saved = entries.get(job["instance"]), state["jobs"][job["id"]]
        old = normalized[job["id"]]
        executed = (folder/"jobs"/job["id"]/"started.json").exists()
        backend = job.get("backend_override") or job["backend"]
        if entry:
            row.update(metas[entry["id"]])
        else:
            row.update({"来源数据包":"项目既有回归集", "来源包性质":"包含既有机组案例；非新增公开数据输入"})
        directory = folder/"jobs"/job["id"]
        evidence_path = directory/"evidence.json"
        evidence = read(evidence_path) if evidence_path.exists() else {}
        config = read(directory/"input.json")["configs"] if executed and (directory/"input.json").exists() else {}
        algorithm = job["algorithm"]
        row.update({
            "任务编号":job["id"], "任务范围":"正式冻结清单498项", "实验阶段":PHASES[job["phase"]],
            "任务类型":KINDS[job["kind"]], "算法代码":algorithm,
            "算法名称":ALGORITHMS.get(algorithm) or {"components":"全列LP/CG＋全列整数/B&P", "external":"AIR B&P前置求解＋官方原生检查", "pytest":"pytest回归"}.get(job["kind"]),
            "配置求解器":backend, "清单默认后端":job["backend"], "清单覆盖后端":job.get("backend_override"),
            "求解器版本":manifest["environment"]["versions"]["highspy" if backend == "highs" else "gurobipy"],
            "是否预热":flag(job["warmup"]), "重复编号":job["repeat"], "是否实际执行":flag(executed),
            "任务状态":old["verdict"], "原始任务状态":saved["verdict"],
            "优化状态":old["optimization_status"] or evidence.get("status"), "原始优化状态":saved.get("optimization_status") or evidence.get("status"),
            "任务名义时限_秒":job["seconds"], "本次求解入口时限_秒":.02 if job.get("stop_kind") == "time" else job["seconds"],
            "进程监护墙钟上限_秒":600 if job["kind"] == "pytest" else job["seconds"]+45,
            "阶段预算上限_秒":manifest["phase_budgets_seconds"][job["phase"]], "本批总预算上限_小时":manifest["budget_hours"],
            "工作进程内部耗时_秒":saved.get("elapsed_seconds") if executed else None,
            "任务实际进程墙钟_秒":saved.get("wall_seconds") if executed else None,
            "原始elapsed_seconds_秒":saved.get("elapsed_seconds"),
            "时间统计说明":"求解入口含枚举/构模/审计等；进程内部含读取和任务逻辑；进程墙钟另含启动监护。未执行项实际耗时为空，原始状态elapsed=0另列。构模等分项可能缺测。",
            "开始时间_北京时间":bj(read(directory/"started.json")["at"]) if executed else None,
            "结束时间_北京时间":bj(saved.get("finished_at")), "内存硬上限_GiB":job["memory_gib"],
            "峰值进程树RSS_MiB":saved["peak_rss_bytes"]/1024**2 if saved.get("peak_rss_bytes") is not None else None,
            "峰值进程树提交内存_MiB":saved["peak_process_tree_commit_bytes"]/1024**2 if saved.get("peak_process_tree_commit_bytes") is not None else None,
            "求解线程数":1, "最大任务并发数":1, "任务停止实验类型":job.get("stop_kind"),
            "Benders迭代上限":(config.get("fixed_benders", {}).get("max_iterations") if algorithm == "fixed_benders" else
                              config.get("benders_cg", {}).get("max_benders_iterations")) if config else (500 if entry and algorithm in ("fixed_benders","air_cg","air_bp") else None),
            "分支节点上限":1 if job.get("stop_kind") == "nodes" else 1000 if entry else None,
            "冻结输入文件":relative(folder/entry["path"]) if entry else None,
            "本次执行输入文件":relative(directory/"input.json") if (directory/"input.json").exists() else None,
            "本次执行输入SHA256":sha(directory/"input.json") if (directory/"input.json").exists() else None,
            "原始结果证据文件":relative(evidence_path) if evidence_path.exists() else relative(directory/"result.json") if executed else None,
            "检查点文件":relative(directory/"checkpoint.json") if (directory/"checkpoint.json").exists() else None,
            "结果证据SHA256":sha(evidence_path) if evidence_path.exists() else None,
            "正式清单SHA256":manifest["manifest_sha256"], "运行代码提交":manifest["git_commit"], "基线提交":manifest["baseline"],
        })
        if algorithm in ("integrated_oracle","fixed_benders") or job["kind"] == "components":
            row.update({"枚举航班上限":12, "枚举路径上限":200000, "枚举访问节点上限":1000000})
        if (algorithm or "").startswith("xma_"):
            row.update({"CG迭代上限":1000 if algorithm == "xma_benders_cg_bp" else None,
                        "分支深度上限":None, "分支节点上限":1000 if algorithm == "xma_benders_cg_bp" else None,
                        "Benders迭代上限":500 if algorithm.startswith("xma_benders_") else None})
            row["实际配置摘要"] = "厦航v3默认强化开启；Benders迭代上限500，BP节点上限1000，CG迭代上限1000，完整路径Oracle上限100000；各项仅对相应路线适用，详见冻结source/backend/business/xma/schema.py及benchmarks/xma.py"
        if algorithm == "xma_joint_path_oracle":
            row.update({"枚举航班上限":12, "枚举路径上限":100000})
        if algorithm in ("integrated_oracle", "fixed_benders"):
            row.update({"CG迭代上限":None, "分支节点上限":None, "分支深度上限":None})
        if algorithm == "integrated_oracle":
            row["Benders迭代上限"] = None
        if algorithm == "air_cg":
            row.update({"分支节点上限":None, "分支深度上限":None})
        if job["kind"] == "external":
            row["Benders迭代上限"] = 500  # The preceding solve uses public AIR B&P.
        if job.get("stop_kind") == "iterations":
            row["实际配置摘要"] = text(row["实际配置摘要"])+"；清单请求停止迭代限制1，未执行，未验证其生效"
        if entry:
            ref = references.get(entry["source_instance"])
            row.update({"公开数据答案值_原规则":ref["value"] if ref else None,
                "公开答案性质与适用范围":"完整原实例的历史参考上界，非全局最优证明；不是当前冻结研究问题的已知最优值" if ref else "没有已核实的逐例公开答案",
                "公开答案来源":f"{ref['file']}；table={ref.get('table')}；row={ref['row']}；sha256={ref['sha256']}" if ref else None,
                "公开答案团队":ref["team"] if ref else None, "公开答案是否竞赛计分":flag(ref["competition_scored"]) if ref else None,
                "公开答案能否直接比较":"否", "不可直接比较原因":"研究模型/候选/范围/成本与原规则不同，且未通过完整原规则及成本检查" if ref else "Delft无本任务配对答案；2019结果不能与2020输入逐例配对",
                "研究模型已认证最优参考值":certified.get(entry["id"]), "研究参考证据任务":ref_jobs.get(entry["id"]),
                "研究参考值适用范围":"同一冻结问题指纹的整体最优值；组件任务为固定计划追索子目标，二者不可直接比较" if entry["id"] in certified else "有必要可达性预处理不可行证书，不存在有限最优目标" if entry["id"] in infeasible else "尚无同指纹认证最优参考",
            })
        if evidence:
            apply_evidence(row, evidence, saved, observations.get(job["id"]))
        if job["kind"] == "external" and evidence:
            violations = evidence.get("violations", {})
            row.update({"原规则检查通过":flag(evidence.get("passed")), "原规则违规文件":"；".join(violations),
                        "原规则违规条数":sum(len(v.splitlines()) for v in violations.values()),
                        "公开答案能否直接比较":flag(evidence.get("historical_comparison_eligible")),
                        "是否实际调用优化器":"是（前置求解）；官方检查器另行执行"})
        if job["kind"] == "workbench" and evidence:
            review = read(frozen/"workbench_review.json")
            row["是否认证模型最优"] = flag(review["independent_audit_pass"] and evidence["status"] == "optimal" and row["本次LB"] == row["本次UB"])
            row["是否实际调用优化器"] = "是"
        if job["kind"] in ("components", "external", "pytest"):
            row["优化状态"] = "前置Oracle:"+evidence["status"] if evidence.get("preprocessing_only") else None
        if executed and job["kind"] in ("solve", "stop"):
            assert evidence.get("backend") == backend, (job["id"], "backend mismatch")
        conclusions(row, evidence, saved, job["kind"])
        if job["kind"] not in ("solve", "stop"):
            row["补充说明"] = (row["补充说明"] or "")+"本行是复核/组件/回归任务，不计入报告59次正式求解认证运行。"
        rows.append(row)

    # The three supplementary activities are reported in the Markdown but are
    # not registered campaign jobs. Keep their identifiers and scope separate.
    pub = read(frozen/"publisher_2019_summary.json")
    row = empty()
    row.update({"任务编号":"SUP-2019", "任务范围":"报告补充活动，不计入498项", "实验阶段":"外部结果整理", "任务类型":"发布者结果解析",
        "算法名称":"工作簿原公式/缓存/CV/状态提取及按表统计", "是否实际执行":"是", "任务状态":"completed_reference_analysis",
        "来源数据包":"TU_Delft_2019_Results", "来源包性质":"结果资料，无完整配套输入",
        "公开答案性质与适用范围":"仅发布者成本/KPI/运行时间/求解状态；不存在与本项目输入配对的单一答案值",
        "公开答案能否直接比较":"否", "不可直接比较原因":"缺少配对输入；工作表可能重叠；时间字段定义不同；发布者101不是我方最优证明",
        "结论":"已整理7077条运行观察；7044条可作发布者参考、33条非零CV；不重跑我方算法",
        "问题原因":"数据包只有结果，不能构造虚构输入或与2020输入强行配对", "原因证据等级":"原工作簿及逐行提取证据",
        "后续处理建议":"分别按文件和工作表比较发布者分布，保留CV/公式错误，不用于我方逐例最优判定",
        "参考结果工作簿数":6, "参考结果工作表数":32, "发布者运行记录数":pub["counts"]["run_observation"],
        "可用发布者参考记录数":pub["counts"]["eligible_reference"], "非零CV记录数":pub["counts"]["nonzero_cv"],
        "公式错误单元格数":pub["counts"]["formula_errors"], "汇总辅助记录数":pub["counts"]["summary_or_auxiliary"],
        "原始结果证据文件":relative(folder/"reference-2019/rows.jsonl"), "结果证据SHA256":sha(folder/"reference-2019/rows.jsonl"),
        "源文件及SHA256":pub["source_files"],
        "时间统计说明":"未记录本次提取墙钟时间，故为空；发布者时间是原研究结果，不填入我方求解耗时",
        "补充说明":"2个公式错误是单元格数，不应在33条非零CV之外再次推断为新增失败运行；不将32个工作表当32个独立实例",
    })
    rows.append(row)
    stop_dir = ROOT/".public_benchmarks/dev/native-highs-stop-after-incumbent"
    stop, check = read(stop_dir/"evidence.json"), read(ROOT/"docs/benchmarks/public_v3_reliability_check.json")
    row = empty(); row.update(metas["micro-roadef-A01"])
    for field in FIELDS:
        if field.startswith(("公开", "研究参考", "研究模型已认证", "不可直接比较")):
            row[field] = next(r for r in rows if r["任务编号"] == "J0002")[field]
    row.update({"任务编号":"SUP-STOP", "任务范围":"开发合同补充检查，不计入498项", "实验阶段":"可靠性补充检查", "任务类型":"审计后取消保留方案",
        "算法代码":"air_bp", "算法名称":ALGORITHMS["air_bp"], "配置求解器":"highs", "求解器版本":"1.15.1",
        "是否实际执行":"是", "任务状态":"passed_stop_contract", "优化状态":stop["status"], "任务停止实验类型":"incumbent_audited后触发取消",
        "结论":"取消后保留目标240的合法方案与检查点，返回aborted，不标为最优",
        "问题原因":"主动取消，非算法故障；即使保留解目标等于Oracle也不能改变停止状态", "原因证据等级":"实际公开输入运行及独立方案/检查点审计",
        "后续处理建议":"仍需正式节点/时间/内存及重复实验", "本次求解入口时限_秒":120,
        "原始结果证据文件":relative(stop_dir/"evidence.json"), "检查点文件":relative(stop_dir/"checkpoint.json"),
        "本次执行输入文件":relative(stop_dir/"input.json"), "结果证据SHA256":check["evidence_sha256"],
        "冻结输入文件":relative(folder/"inputs/micro-roadef-A01.json"), "本次执行输入SHA256":sha(stop_dir/"input.json"),
        "研究参考值适用范围":"同一冻结输入的研究模型最优参考；本行主动取消，不凭目标与参考相等改变停止状态",
        "时间统计说明":"仅有求解入口耗时；没有独立记录进程墙钟/资源硬限制；排除正式性能统计",
    })
    apply_evidence(row, stop, {"retained_incumbent":check["checkpoint_audit_pass"]})
    rows.append(row)
    review = read(frozen/"workbench_review.json")["delft_infeasible_review"]
    result = review["run"]["result"]
    row = empty(); row.update(metas["micro-delft-2015-01-01"])
    row.update({"任务编号":"SUP-WB-DELFT", "任务范围":"开发页面补充复核，不计入498项", "实验阶段":"v3补充复核", "任务类型":"不可行状态页面链路复核",
        "算法代码":"air_bp", "算法名称":ALGORITHMS["air_bp"], "配置求解器":"highs", "求解器版本":"1.15.1",
        "是否实际执行":"是", "任务状态":"passed_infeasible_workbench_contract", "优化状态":result["status"],
        "结论":"worker正常完成，优化状态infeasible且目标为空；没有将任务完成标为方案可行",
        "问题原因":"当前固定上下文/候选域的必要可达性证书证明不可行；不是原业务不可行证明", "原因证据等级":"实际worker及结果记录",
        "后续处理建议":"保留任务完成与优化状态的区分", "原始结果证据文件":relative(frozen/"workbench_review.json"),
        "结果证据SHA256":sha(frozen/"workbench_review.json"), "是否仅预处理":"是", "是否认证研究问题不可行":"是",
        "运行代码提交":result["run_metadata"]["git_commit"], "研究参考值适用范围":"有预处理不可行证书，不存在有限最优目标",
        "时间统计说明":"仅有worker结果里的求解入口耗时；没有监护进程墙钟记录",
    })
    apply_evidence(row, result, {})
    row.update({"是否仅预处理":"是", "是否实际调用优化器":"否", "是否认证研究问题不可行":"是"})
    rows.append(row)

    assert len(rows) == 501 and len({r["任务编号"] for r in rows}) == 501
    assert Counter(r["任务状态"] for r in rows[:498]) == Counter(summary["verdicts"])
    assert sum(r["是否认证模型最优"] == "是" for r in rows[:498] if r["任务类型"] == "算法求解") == 59
    assert all(r["任务实际进程墙钟_秒"] is None and r["本次结果目标值"] is None for r in rows if r["是否实际执行"] == "否")
    assert all(r["配置求解器"] == "gurobi" for r in rows[:498] if r["清单覆盖后端"] == "gurobi")
    assert all(not (set(r)-set(FIELDS)) for r in rows), {k for r in rows for k in set(r)-set(FIELDS)}
    assert len(FIELDS) == len(set(FIELDS)), "duplicate column names"
    by_id = {r["任务编号"]:r for r in rows}
    for jid in ("J0023", "J0024", "J0025"):
        assert by_id[jid]["本次LB"] == 150 and by_id[jid]["本次UB"] is None
        assert by_id[jid]["研究模型已认证最优参考值"] == 240
    assert by_id["J0122"]["本次结果目标值"] == 93750 and by_id["J0122"]["任务优化旅客人数"] == 469
    assert by_id["J0125"]["原规则检查通过"] == "否" and by_id["J0125"]["官方评分结果"] is None
    assert sum(r["求解器错误码"] == 10010 for r in rows[:498]) == 2
    assert by_id["SUP-STOP"]["是否认证模型最优"] == "否" and by_id["SUP-STOP"]["停止后是否保留合法方案"] == "是"
    output.parent.mkdir(parents=True, exist_ok=True)
    def cell(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return format(v, ".12g")
        s = text(v).replace("\r", " ").replace("\n", " ")
        return "'"+s if s.startswith(("=", "+", "@", "\t")) else s
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k:cell(v) for k,v in r.items()} for r in rows)
    with output.open(encoding="utf-8-sig", newline="") as stream:
        saved_rows = list(csv.DictReader(stream))
    assert len(saved_rows) == 501 and all(None not in r for r in saved_rows)
    print(json.dumps(dict(output=relative(output), rows=len(rows), columns=len(FIELDS),
        formal_statuses=dict(Counter(r["任务状态"] for r in rows[:498])),
        formal_backends=dict(Counter(r["配置求解器"] for r in rows[:498] if r["任务类型"] == "算法求解")),
        sha256=sha(output)), ensure_ascii=False))


if __name__ == "__main__":
    main()
