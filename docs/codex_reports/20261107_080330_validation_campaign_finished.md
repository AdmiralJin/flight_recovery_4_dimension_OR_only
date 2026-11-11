# 算法验证续测与监控结果

完成时间：2026-11-07T08:03:30+08:00；批次：`20261107_001154_continue`。

本轮 35 项，历史保留 147 项；合并状态：`{"passed": 130, "completed": 36, "timed_out": 3, "license_limited": 1, "inconclusive": 9, "resource_limited": 2, "input_limit": 1}`。
全部任务已尝试：**是**；未执行或中断 0 项。
已取消系统空闲资源等待及低内存停测；最多两项并发，正式计时独占；单例硬时限和进程树内存限制有效。
监控记录的最大并发：1；调度器异常恢复：0 次。
已核验冻结代码、数据、任务清单和继承结果 SHA256，检查本轮执行状态与结果一致。

## 结果含义

passed 表示相应测试断言通过，completed 表示采样完成。资源受限、未收敛和未执行不能当作证明最优或算法正确性失败。
其中已完成采样但包含未收敛、仅可行或中止结果的任务：24 项。
本报告为自动证据汇总；没有合格证据的项目保留未定结论。

## AIR 列生成对照

| 测试 | 全列/CG 中位耗时比 | 结论 |
|---|---:|---|
| aircraft: full LP vs CG / toy_case_011_aircraft_string_column_generation | 0.223 | 本实例 CG 未提速；passed |
| aircraft: full LP vs CG / phase1_benchmark_001 | 0.349 | 本实例 CG 未提速；passed |
| crew: full LP vs CG / toy_case_012_crew_pairing_column_generation | 0.184 | 本实例 CG 未提速；passed |
| crew: full LP vs CG / phase1_benchmark_001 | 0.358 | 本实例 CG 未提速；passed |

## 厦航真实数据计时

合并 12 组同输入、同目标比较；三算法均有三次审计通过、上下界闭合且目标一致的组数：0。
仅对满足同问题、三次证明最优且独立审计有效的算法计算加速比；未收敛或无合法 incumbent 的时间不参与加速比。

## 受限、失败及未完成任务

| 任务 | 状态 | 原因 |
|---|---|---|
| 11-air-stress-002 P2-tens-seconds | timed_out | strict wall limit, including build and serialization |
| 11-air-stress-003 P3-minutes | timed_out | strict wall limit, including build and serialization |
| 11-air-stress-004 P4-tens-minutes | timed_out | strict wall limit, including build and serialization |
| 11-air-stress-005 P5-hours | license_limited | Gurobi 10010 size limit; not an algorithm correctness failure |
| 09-xma-benders-013 Stress / benders_joint / fixed target=100 / grid60 max120 | inconclusive | benders_joint: not_converged; objective=None |
| 10-xma-cg-bp-013 Stress / benders_cg_bp / fixed target=100 / grid60 max120 | inconclusive | benders_cg_bp: not_converged; objective=None |
| 08-xma-arc-014 Stress / joint_arc_flow / fixed target=500 / grid60 max120 | inconclusive | joint_arc_flow: not_converged; objective=None |
| 09-xma-benders-014 Stress / benders_joint / fixed target=500 / grid60 max120 | inconclusive | benders_joint: not_converged; objective=None |
| 10-xma-cg-bp-014 Stress / benders_cg_bp / fixed target=500 / grid60 max120 | inconclusive | benders_cg_bp: not_converged; objective=None |
| 08-xma-arc-015 Stress / joint_arc_flow / fixed target=2364 / grid60 max120 | resource_limited | worker exited without a complete result |
| 09-xma-benders-016 Stress / benders_joint / fixed target=100 / grid30 max1440 | inconclusive | benders_joint: not_converged; objective=None |
| 10-xma-cg-bp-016 Stress / benders_cg_bp / fixed target=100 / grid30 max1440 | inconclusive | benders_cg_bp: not_converged; objective=None |
| 08-xma-arc-017 Stress / joint_arc_flow / fixed target=500 / grid30 max1440 | resource_limited | resource_limited: MemoryError:  |
| 09-xma-benders-017 Stress / benders_joint / fixed target=500 / grid30 max1440 | inconclusive | benders_joint: not_converged; objective=None |
| 10-xma-cg-bp-017 Stress / benders_cg_bp / fixed target=500 / grid30 max1440 | inconclusive | benders_cg_bp: not_converged; objective=None |
| 08-xma-arc-018 Full 2364 fine grid: candidate readiness and size gate | input_limit | Candidate/assignment readiness only; optimization not run |

## 已执行但优化未闭合

| 任务 | 执行状态 | 优化结果 |
|---|---|---|
| 09-xma-benders-001 Timing / fixed target=20 seed=None / tianchi_2017 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-001 Timing / fixed target=20 seed=None / tianchi_2017 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 09-xma-benders-002 Timing / fixed target=20 seed=None / air_linear_v1 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-002 Timing / fixed target=20 seed=None / air_linear_v1 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-003 Timing / fixed target=100 seed=None / tianchi_2017 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 09-xma-benders-003 Timing / fixed target=100 seed=None / tianchi_2017 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 09-xma-benders-004 Timing / fixed target=100 seed=None / air_linear_v1 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 09-xma-benders-005 Timing / random target=20 seed=20261106 / tianchi_2017 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-005 Timing / random target=20 seed=20261106 / tianchi_2017 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-006 Timing / random target=20 seed=20261106 / air_linear_v1 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 09-xma-benders-006 Timing / random target=20 seed=20261106 / air_linear_v1 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 09-xma-benders-007 Timing / random target=20 seed=20261107 / tianchi_2017 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-007 Timing / random target=20 seed=20261107 / tianchi_2017 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 09-xma-benders-008 Timing / random target=20 seed=20261107 / air_linear_v1 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-008 Timing / random target=20 seed=20261107 / air_linear_v1 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-004 Timing / fixed target=100 seed=None / air_linear_v1 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-009 Timing / random target=100 seed=20261106 / tianchi_2017 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 09-xma-benders-009 Timing / random target=100 seed=20261106 / tianchi_2017 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 09-xma-benders-010 Timing / random target=100 seed=20261106 / air_linear_v1 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-010 Timing / random target=100 seed=20261106 / air_linear_v1 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 09-xma-benders-011 Timing / random target=100 seed=20261107 / tianchi_2017 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-011 Timing / random target=100 seed=20261107 / tianchi_2017 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 10-xma-cg-bp-012 Timing / random target=100 seed=20261107 / air_linear_v1 / benders_cg_bp | completed | benders_cg_bp: not_converged, not_converged, not_converged |
| 09-xma-benders-012 Timing / random target=100 seed=20261107 / air_linear_v1 / benders_joint | completed | benders_joint: not_converged, not_converged, not_converged |

## 证据位置

- 本轮执行汇总：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261107_001154_continue\SUMMARY.md`。
- 跨批次证据及输入参数：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261107_001154_continue\combined_evidence.json`。
- 跨批次性能比较：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261107_001154_continue\combined_performance_comparisons.json`。
- 监控与恢复日志：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261107_001154_continue\watch_events.jsonl`。
