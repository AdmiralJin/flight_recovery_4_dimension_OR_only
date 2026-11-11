# 算法验证详细基线报告

生成时间：2026-11-07T08:03:51+08:00。

最终续测批次：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261107_001154_continue`；包含跨批次去重后的 182 个任务。
本报告记录修复前冻结代码的实际测试结果。后续算法修复与复测须建立新证据目录，不覆盖本报告或基线输入。

## 1. 完成情况与判定口径

任务执行状态：`{"passed": 130, "completed": 36, "timed_out": 3, "license_limited": 1, "inconclusive": 9, "resource_limited": 2, "input_limit": 1}`。
pytest 文件任务 89 项；底层测试报告计数 `{"passed": 476}`，另有跳过 0 项。任务数与底层断言数分开统计。
`passed` 表示本测试断言通过；`completed` 只表示测量完成。最优性另外核查独立审计、目标、上下界及参考断言，不能将三次未收敛当作三次最优。
AIR 与厦航、Tianchi 与 AIR 目标、LP 与整数最优、固定候选与动态候选分别判断；相同最优目标允许不同资源串 ID。

| 科学或执行结论 | 任务数 |
|---|---:|
| LP 最优及定价终止审计通过 | 4 |
| 候选或输入规模门槛 | 1 |
| 审计、目标与上下界闭合的最优解 | 37 |
| 未得到确定结论 | 9 |
| 未收敛，缺少经审计的全局可行解 | 24 |
| 求解器认证不可行 | 4 |
| 测试断言通过 | 91 |
| 硬时限终止 | 3 |
| 联合 Oracle 与 Benders/B&P 最优一致 | 2 |
| 许可证受限 | 1 |
| 资源受限 | 2 |
| 输入合同或预检完成，未运行优化 | 2 |
| 返回不可行，认证与边界见原始结果 | 1 |
| 重复最优目标不一致，需复核 | 1 |

## 2. 来源、配置和测试公平性

- 已核验本批 415 个冻结文件、不可变任务清单及 147 份继承结果 SHA256。
- 原批次中被替代的失败尝试继续保留；本报告按任务 ID 使用最近一次有效执行证据，不将旧失败与修复后的通过重复计数。
- 批次预算 24 小时，最大并发 2；性能任务独占、求解器单线程；当前资源等待策略 `False`。
- 重型单例最长 2 小时；轻/中/重进程树提交内存约 1.5/2.5/4GiB。原始预算以每项 manifest/job.json 为准。
- 厦航粗档步长/延误上限 60/120 分钟，细档 30/1440 分钟；随机种子 20261106、20261107。整条机尾选样的实际航班数可高于目标数。
- 性能加速比仅在同问题、三次均最优、审计通过且目标相等时计算。建模、候选、求解、审计和端到端时间见各记录，不把嵌套子问题界作为全局界。
- 显式路径 Oracle 只用于小例子。全量细档的预检是候选规模检查，不是一次大型优化成功。

## 3. 各路线覆盖和结果

| 路线 | 任务数 | 执行状态 |
|---|---:|---|
| 01 Regression - unit API regression | 89 | {'passed': 89} |
| 02 AIR - expected solutions | 17 | {'passed': 17} |
| 03 AIR - Aircraft column generation | 2 | {'passed': 2} |
| 04 AIR - Crew column generation | 2 | {'passed': 2} |
| 05 AIR - Benders BP vs integrated | 2 | {'passed': 2} |
| 06 Conflicts - cancellation and limits | 2 | {'passed': 2} |
| 07 XMA - four algorithms two objectives | 11 | {'passed': 11} |
| 08 XMA - joint arc flow | 18 | {'completed': 12, 'passed': 2, 'inconclusive': 1, 'resource_limited': 2, 'input_limit': 1} |
| 09 XMA - Benders joint | 17 | {'completed': 12, 'inconclusive': 4, 'passed': 1} |
| 10 XMA - Benders CG BP | 17 | {'completed': 12, 'inconclusive': 4, 'passed': 1} |
| 11 AIR - P1 P2 P3 P4 P5 stress | 5 | {'passed': 1, 'timed_out': 3, 'license_limited': 1} |

### 补充：真实样本候选扩充的合理性核查

实际 103 班，输入和成本相同。原始输入 hash、两项最优结果及独立审计已再次核对；此补充检查不计入原任务数。
候选数 276 → 2844；最优目标 56897.6 → 42473.6。
粗档候选包含于细档、扩充候选后目标不变差：**通过**。证据：[real_candidate_expansion_audit.json](../../.workbench/validation_campaigns/20261107_001154_continue/real_candidate_expansion_audit.json)。

## 4. 未通过、未收敛、受限及证据不足的项目

以下将执行失败与优化目标未实现分别列出；超时、许可证和内存限制不自动等价于算法数学错误。

| 任务 ID / 名称 | 执行状态 | 具体结论 | 原因 | 证据 |
|---|---|---|---|---|
| `06-stop-conflict-001` Capacity/candidates/order metamorphic properties | passed | 重复最优目标不一致，需复核 | Capacity relaxation, candidate expansion, order invariance verified; 停止原因=2 | [result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/06-stop-conflict-001/result.json) |
| `09-xma-benders-001` Timing / fixed target=20 seed=None / tianchi_2017 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-001/result.json) |
| `10-xma-cg-bp-001` Timing / fixed target=20 seed=None / tianchi_2017 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-001/result.json) |
| `09-xma-benders-002` Timing / fixed target=20 seed=None / air_linear_v1 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-002/result.json) |
| `10-xma-cg-bp-002` Timing / fixed target=20 seed=None / air_linear_v1 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-002/result.json) |
| `10-xma-cg-bp-003` Timing / fixed target=100 seed=None / tianchi_2017 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-003/result.json) |
| `09-xma-benders-003` Timing / fixed target=100 seed=None / tianchi_2017 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-003/result.json) |
| `09-xma-benders-004` Timing / fixed target=100 seed=None / air_linear_v1 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal, time_limit_or_cancel | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-004/result.json) |
| `09-xma-benders-005` Timing / random target=20 seed=20261106 / tianchi_2017 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-005/result.json) |
| `10-xma-cg-bp-005` Timing / random target=20 seed=20261106 / tianchi_2017 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-005/result.json) |
| `10-xma-cg-bp-006` Timing / random target=20 seed=20261106 / air_linear_v1 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-006/result.json) |
| `09-xma-benders-006` Timing / random target=20 seed=20261106 / air_linear_v1 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-006/result.json) |
| `09-xma-benders-007` Timing / random target=20 seed=20261107 / tianchi_2017 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal, time_limit_or_cancel | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-007/result.json) |
| `10-xma-cg-bp-007` Timing / random target=20 seed=20261107 / tianchi_2017 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-007/result.json) |
| `09-xma-benders-008` Timing / random target=20 seed=20261107 / air_linear_v1 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-008/result.json) |
| `10-xma-cg-bp-008` Timing / random target=20 seed=20261107 / air_linear_v1 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-008/result.json) |
| `10-xma-cg-bp-004` Timing / fixed target=100 seed=None / air_linear_v1 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-004/result.json) |
| `10-xma-cg-bp-009` Timing / random target=100 seed=20261106 / tianchi_2017 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-009/result.json) |
| `09-xma-benders-009` Timing / random target=100 seed=20261106 / tianchi_2017 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-009/result.json) |
| `09-xma-benders-010` Timing / random target=100 seed=20261106 / air_linear_v1 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal, time_limit_or_cancel | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-010/result.json) |
| `10-xma-cg-bp-010` Timing / random target=100 seed=20261106 / air_linear_v1 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, time_limit_or_cancel | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-010/result.json) |
| `09-xma-benders-011` Timing / random target=100 seed=20261107 / tianchi_2017 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal, time_limit_or_cancel | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-011/result.json) |
| `10-xma-cg-bp-011` Timing / random target=100 seed=20261107 / tianchi_2017 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-011/result.json) |
| `10-xma-cg-bp-012` Timing / random target=100 seed=20261107 / air_linear_v1 / benders_cg_bp | completed | 未收敛，缺少经审计的全局可行解 | benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-012/result.json) |
| `09-xma-benders-012` Timing / random target=100 seed=20261107 / air_linear_v1 / benders_joint | completed | 未收敛，缺少经审计的全局可行解 | benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, time_limit_or_cancel | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-012/result.json) |
| `11-air-stress-002` P2-tens-seconds | timed_out | 硬时限终止 | strict wall limit, including build and serialization; 进程树墙钟上限 180s，含构模和落盘 | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-002/result.json) |
| `11-air-stress-003` P3-minutes | timed_out | 硬时限终止 | strict wall limit, including build and serialization; 进程树墙钟上限 600s，含构模和落盘 | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-003/result.json) |
| `11-air-stress-004` P4-tens-minutes | timed_out | 硬时限终止 | strict wall limit, including build and serialization; 进程树墙钟上限 1800s，含构模和落盘 | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-004/result.json) |
| `11-air-stress-005` P5-hours | license_limited | 许可证受限 | Gurobi 10010 size limit; not an algorithm correctness failure; 停止原因=phase11_aborted | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-005/result.json) |
| `09-xma-benders-013` Stress / benders_joint / fixed target=100 / grid60 max120 | inconclusive | 未得到确定结论 | benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-013/result.json) |
| `10-xma-cg-bp-013` Stress / benders_cg_bp / fixed target=100 / grid60 max120 | inconclusive | 未得到确定结论 | benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-013/result.json) |
| `08-xma-arc-014` Stress / joint_arc_flow / fixed target=500 / grid60 max120 | inconclusive | 未得到确定结论 | joint_arc_flow: not_converged; objective=None; 停止原因=9 | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-014/result.json) |
| `09-xma-benders-014` Stress / benders_joint / fixed target=500 / grid60 max120 | inconclusive | 未得到确定结论 | benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-014/result.json) |
| `10-xma-cg-bp-014` Stress / benders_cg_bp / fixed target=500 / grid60 max120 | inconclusive | 未得到确定结论 | benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-014/result.json) |
| `08-xma-arc-015` Stress / joint_arc_flow / fixed target=2364 / grid60 max120 | resource_limited | 资源受限 | worker exited without a complete result; 进程树提交内存上限 4GiB；具体触发项见 reason/worker.log | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-015/result.json) |
| `09-xma-benders-016` Stress / benders_joint / fixed target=100 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-016/result.json) |
| `10-xma-cg-bp-016` Stress / benders_cg_bp / fixed target=100 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-016/result.json) |
| `08-xma-arc-017` Stress / joint_arc_flow / fixed target=500 / grid30 max1440 | resource_limited | 资源受限 | resource_limited: MemoryError: ; 进程树提交内存上限 4GiB；具体触发项见 reason/worker.log | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-017/result.json) |
| `09-xma-benders-017` Stress / benders_joint / fixed target=500 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-017/result.json) |
| `10-xma-cg-bp-017` Stress / benders_cg_bp / fixed target=500 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-017/result.json) |
| `08-xma-arc-018` Full 2364 fine grid: candidate readiness and size gate | input_limit | 候选或输入规模门槛 | Candidate/assignment readiness only; optimization not run; 输入门槛=assignment network has 6055567 tail-option pairs, exceeds configured limit 100000; increase delay_step_minutes, lower maximum_delay_minutes, or explicitly raise max_assignment_options | [result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-018/result.json) |

## 5. 列生成、分解与耗时收益

### 5.1 AIR 全列 LP 与列生成

速度比定义为全列流程中位耗时 / CG 流程中位耗时；小于 1 表示本实例 CG 更慢。它与最优性审计是两项结论，不能用正确性通过替代性能提速。

| 任务 | 速度比 | 全列列数 | CG 列数 | 判定 |
|---|---:|---|---|---|
| aircraft: full LP vs CG / toy_case_011_aircraft_string_column_generation | 0.223412 | [4, 4, 4] | [4, 4, 4] | CG not faster on this instance |
| aircraft: full LP vs CG / phase1_benchmark_001 | 0.348848 | [77, 77, 77] | [15, 15, 15] | CG not faster on this instance |
| crew: full LP vs CG / toy_case_012_crew_pairing_column_generation | 0.183731 | [12, 12, 12] | [12, 12, 12] | CG not faster on this instance |
| crew: full LP vs CG / phase1_benchmark_001 | 0.357948 | [374, 374, 374] | [34, 34, 34] | CG not faster on this instance |

### 5.2 厦航真实样本逐组对照

每组比较键由固定输入、目标和候选空间生成；三种算法各有预热及三次正式测量。不同目标的费用不横向比较。

#### 问题键 `0506e3c5ac1d9c6cc494f1422b771b0954071167148eb343c6780463a468276a`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 31 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5358 | [90.52597090008203, 90.54176259995438] | 缺失 |
| benders_cg_bp | 31 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.4863 | [90.46198499994352, 90.5202098999871] | 缺失 |
| joint_arc_flow | 31 | ['optimal', 'optimal', 'optimal'] | [5948.0, 5948.0, 5948.0] | 0.747742 | [0.745183699997142, 0.7510365000925958] | 缺失 |
#### 问题键 `1a5cc92ed5cf676460b43f818a45116a24f9cb58a1a33578a1b9baeb6a87b79e`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 103 | ['optimal', 'optimal', 'optimal'] | [8437500.0, 8437500.0, 8437500.0] | 5.76559 | [5.742682099924423, 5.782863299944438] | 缺失 |
| benders_joint | 103 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.6071 | [90.5698582000332, 90.92585170001257] | 缺失 |
| benders_cg_bp | 103 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.3105 | [90.22093900002073, 90.32207630004268] | 缺失 |
#### 问题键 `2473ec1f1dca3c4a8c9c13ef94ad4881c5c640cf67222d8e1d80a849767cc6cf`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 115 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.3151 | [90.31292980001308, 90.46498520008754] | 缺失 |
| joint_arc_flow | 115 | ['optimal', 'optimal', 'optimal'] | [43465.68194444444, 43465.68194444444, 43465.68194444444] | 1.57373 | [1.5593450999585912, 1.7134575999807566] | 缺失 |
| benders_joint | 115 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.2087 | [90.20389790006448, 90.24071340006776] | 缺失 |
#### 问题键 `3557b8025195fa27cba5a64eea3cf5dc0ad6d4a7a19e1e34a01c808fc674289f`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 31 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5117 | [90.50881459994707, 90.53172860003542] | 缺失 |
| joint_arc_flow | 31 | ['optimal', 'optimal', 'optimal'] | [870000.0, 870000.0, 870000.0] | 0.796371 | [0.7527330000884831, 0.8663054000353441] | 缺失 |
| benders_joint | 31 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5524 | [90.54492559994105, 90.57271229999606] | 缺失 |
#### 问题键 `4008685379116815b876560fcd2b0ccf7fa873c7a246146d58b63bfe035b0a0a`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 30 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.6217 | [90.5625066999346, 90.72108839999419] | 缺失 |
| benders_cg_bp | 30 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5497 | [90.54697939998005, 90.57070909999311] | 缺失 |
| joint_arc_flow | 30 | ['optimal', 'optimal', 'optimal'] | [1302500.0, 1302500.0, 1302500.0] | 0.903985 | [0.8904665000736713, 0.9294160000281408] | 缺失 |
#### 问题键 `73dc48c9e1063d30681a462e8a793621aa1c4189d775032ee52f82e4089fd896`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 115 | ['optimal', 'optimal', 'optimal'] | [6820000.0, 6820000.0, 6820000.0] | 1.34992 | [1.3461409999290481, 1.4183228999609128] | 缺失 |
| benders_joint | 115 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.272 | [90.23542050004471, 90.27559969993308] | 缺失 |
| benders_cg_bp | 115 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.2313 | [90.22124090010766, 90.27396260004025] | 缺失 |
#### 问题键 `82165e69de8ad138eed6d22b3911bfae87786f83c198b5e815a3fa5533c1fa81`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 33 | ['optimal', 'optimal', 'optimal'] | [19745.61111111111, 19745.61111111111, 19745.61111111111] | 0.730909 | [0.7167784000048414, 0.8227688999613747] | 缺失 |
| benders_joint | 33 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.494 | [90.47955219994765, 90.54734309995547] | 缺失 |
| benders_cg_bp | 33 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5138 | [90.50890589994378, 90.67593530006707] | 缺失 |
#### 问题键 `84aa1d955b851cf754a6c7c0a638dbee917596c7d23dee8d0d8e25743076f5d4`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 33 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5628 | [90.54687489999924, 90.58208650001325] | 缺失 |
| benders_cg_bp | 33 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5772 | [90.53260859998409, 90.75496329995804] | 缺失 |
| joint_arc_flow | 33 | ['optimal', 'optimal', 'optimal'] | [2925510.0, 2925510.0, 2925510.0] | 0.264885 | [0.25315170001704246, 0.30382919998373836] | 缺失 |
#### 问题键 `9ec12d6dca8170f462f46e83c9f42b8aa78d9d1b9fa21895431b35fa1000f340`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 30 | ['optimal', 'optimal', 'optimal'] | [11444.0, 11444.0, 11444.0] | 0.754055 | [0.7030935999937356, 0.7566196999978274] | 缺失 |
| benders_joint | 30 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5009 | [90.47986960003618, 90.56957799999509] | 缺失 |
| benders_cg_bp | 30 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.5602 | [90.50125400000252, 90.60084500000812] | 缺失 |
#### 问题键 `b1a427124cc94bea5d403dcb2623b769ed989b9c596489ef943d507b008f1df8`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 106 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.2934 | [90.27522199996747, 90.29801599995699] | 缺失 |
| joint_arc_flow | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.407658 | [0.4014240000396967, 0.46590159996412694] | 缺失 |
| benders_joint | 106 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.2398 | [90.23710599995684, 90.30800179997459] | 缺失 |
#### 问题键 `b1c11b70e239c7eb3285eb81e4b61df4a744cd1986a680baf4e1c6942d3ba159`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 103 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.825 | [90.7110282999929, 90.98720790003426] | 缺失 |
| joint_arc_flow | 103 | ['optimal', 'optimal', 'optimal'] | [56897.62037037037, 56897.62037037037, 56897.62037037037] | 5.97191 | [5.882501699961722, 6.06776040000841] | 缺失 |
| benders_joint | 103 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.6915 | [90.62575170001946, 90.98244330007583] | 缺失 |
#### 问题键 `e394648fb4daded9dadce4269318d92ea950660ff27a14b63de9f85aa6dc32d6`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 106 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.2552 | [90.21069360000547, 90.25873090000823] | 缺失 |
| benders_cg_bp | 106 | ['not_converged', 'not_converged', 'not_converged'] | [None, None, None] | 90.3178 | [90.25261969992425, 90.3298701000167] | 缺失 |
| joint_arc_flow | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.405416 | [0.38050420000217855, 0.40681009995751083] | 缺失 |

## 6. 全部任务逐项证据

以下每一项均保留名称、配置、预算、执行结论及原始证据。最优性表中的缺失值保持缺失，不按零处理。

### 01 Regression - unit API regression

#### `01-regression-001` · tests/api/test_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_api.py"]}`。
- 观测墙钟：8.343 秒；进程树提交内存峰值：0.104256GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-001/result.json)；SHA256 `69f5b9765686f24dc7d70750c0b4e84c85cc07359f759d433a830943df9319e8`。

#### `01-regression-002` · tests/api/test_cases_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_cases_api.py"]}`。
- 观测墙钟：5.906 秒；进程树提交内存峰值：0.103779GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-002/result.json)；SHA256 `935117928c676fb9568c558ac0ba4f742e887c9e90f619e5277050b3342db9a0`。

#### `01-regression-003` · tests/api/test_solve_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_solve_api.py"]}`。
- 观测墙钟：31.032 秒；进程树提交内存峰值：0.147694GiB。
- 结果与原因：pytest exit=0; {'passed': 8}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-003/result.json)；SHA256 `b490dcdfef9aee57dc005495afe1acf4ce5c05a6855def1f516999a98878eeba`。

#### `01-regression-004` · tests/api/test_workbench_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_workbench_api.py"]}`。
- 观测墙钟：5.953 秒；进程树提交内存峰值：0.103443GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-004/result.json)；SHA256 `4223a5edaf8fe038c081484584e3fde9d5dd7c4da263e540e79ca204b2b4f496`。

#### `01-regression-007` · tests/regression/test_aircraft_string_column_generation_regression.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_aircraft_string_column_generation_regression.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0462151GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-007/result.json)；SHA256 `3e17a133d3da81602929d8d6fcc8acd77b3d4556699cacdea5fb14b1b6fb1462`。

#### `01-regression-008` · tests/regression/test_phase10_crew_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase10_crew_column_generation.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0503883GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-008/result.json)；SHA256 `88c345a3a229ad3408f790eaa11b6077d4d36c76f911b6cf9e3c1ee53156e78e`。

#### `01-regression-009` · tests/regression/test_phase11_benders_cg_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_benchmark.py"]}`。
- 观测墙钟：5.75 秒；进程树提交内存峰值：0.0566711GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-009/result.json)；SHA256 `7d0f21954507522ea7b12d66c995e42159943f460383884917839994bf2f026a`。

#### `01-regression-010` · tests/regression/test_phase11_benders_cg_cut_validity.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_cut_validity.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0465469GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-010/result.json)；SHA256 `e7453152e61eee34c4f5a71998a0cb920791a7458187dd9b23708999d5b2a8ba`。

#### `01-regression-011` · tests/regression/test_phase11_benders_cg_integrality_boundary.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_integrality_boundary.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0460701GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-011/result.json)；SHA256 `9cf45bdbdcb789ee4f2b58977f08f4e296d6ac9b4d794482b813a839ac107cc8`。

#### `01-regression-012` · tests/regression/test_phase11_benders_cg_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_oracle.py"]}`。
- 观测墙钟：2.296 秒；进程树提交内存峰值：0.0471077GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-012/result.json)；SHA256 `65bbab5c18e1aeb9ebecda2878fed9de24841364ccdb1f8b4ddb46bd411d1d2b`。

#### `01-regression-013` · tests/regression/test_phase12_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_benchmark.py"]}`。
- 观测墙钟：4.609 秒；进程树提交内存峰值：0.0570526GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-013/result.json)；SHA256 `1e11334c982989c311cdbf3610476202c52127c58a5bc891b617bc06be41ad38`。

#### `01-regression-014` · tests/regression/test_phase12_benders_branch_and_price.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_benders_branch_and_price.py"]}`。
- 观测墙钟：17.25 秒；进程树提交内存峰值：0.050499GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-014/result.json)；SHA256 `4583da5055a4fcda13798866735a99bac7926e04b836f76296e5f5c4353ebedc`。

#### `01-regression-015` · tests/regression/test_phase12_branching_oracles.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_branching_oracles.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0460854GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-015/result.json)；SHA256 `3cf3a7045007d036aa82e58e23b81919bcd63469c068569d603eb0018dbce094`。

#### `01-regression-016` · tests/regression/test_phase12_crew_integrality.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_crew_integrality.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0475922GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-016/result.json)；SHA256 `0dcc6708b6a486a16d243f7f153e79c7bf6ce81b4e11b90925c086d4727382cd`。

#### `01-regression-017` · tests/regression/test_phase1_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase1_benchmark_001.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0418777GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-017/result.json)；SHA256 `86240637b0bf884b4e1008257fc29f5b9221791c9e2911f98dee88d11d909b62`。

#### `01-regression-018` · tests/regression/test_phase1_validation_case.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase1_validation_case.py"]}`。
- 观测墙钟：2.282 秒；进程树提交内存峰值：0.0410805GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-018/result.json)；SHA256 `ff0de4e58297992cfbfb2e7c07b12df72f4588a8825d09daa5d4489e77bf42dc`。

#### `01-regression-019` · tests/regression/test_phase2_arm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_arm_benchmark_001.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0472794GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-019/result.json)；SHA256 `2b2a9bd7ac8ce3e4923447dab80d97a6765fd8de38f2069d12be6b3130eb1c00`。

#### `01-regression-020` · tests/regression/test_phase2_crm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_crm_benchmark_001.py"]}`。
- 观测墙钟：2.296 秒；进程树提交内存峰值：0.0475502GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-020/result.json)；SHA256 `e15b604f642f7f6f8bfafe779b975f99b017cb9495e1bdaefe2cb16e4a5f993f`。

#### `01-regression-021` · tests/regression/test_phase2_gurobi_integration_gate.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_gurobi_integration_gate.py"]}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.0329208GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-021/result.json)；SHA256 `5f4cf83d30acffd69ec4e6480bcdb3c52dc83b6acfde4fbc09a07b5212f91224`。

#### `01-regression-022` · tests/regression/test_phase2_incidence_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_incidence_benchmark_001.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0446243GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-022/result.json)；SHA256 `1c69100f0ac7aa0374d2bf29bbc89e6a084b12e5396d6199f705b981da9d692f`。

#### `01-regression-023` · tests/regression/test_phase2_overall_manual_reference.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_overall_manual_reference.py"]}`。
- 观测墙钟：2.281 秒；进程树提交内存峰值：0.0474281GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-023/result.json)；SHA256 `9d656572fa279446636174b89498cf5a6c990e0071d4126badca7afe7b91dbc5`。

#### `01-regression-024` · tests/regression/test_phase2_prm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_prm_benchmark_001.py"]}`。
- 观测墙钟：2.359 秒；进程树提交内存峰值：0.0479774GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-024/result.json)；SHA256 `12aec6bd1372fc6c852b535bc19f78fc87a2161dbfd1c34efc6abbc6b7e63a92`。

#### `01-regression-025` · tests/regression/test_phase2_srm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_srm_benchmark_001.py"]}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.0472069GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-025/result.json)；SHA256 `97e4c27b157c74f4c5b31cbf53a958bce84955310ddba3cd2e447a5198f31d2f`。

#### `01-regression-026` · tests/regression/test_phase3_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase3_benchmark_001.py"]}`。
- 观测墙钟：2.281 秒；进程树提交内存峰值：0.0477371GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-026/result.json)；SHA256 `71f85ac25354f0c0c46d444fdcf6d6f0a871beda46aea614e03041e104a3e932`。

#### `01-regression-027` · tests/regression/test_phase3_toy_case_004.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase3_toy_case_004.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0465775GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-027/result.json)；SHA256 `3e4a9959eb156d11f3f871dda1e32305e3639d38e86a137e211a53102267f585`。

#### `01-regression-028` · tests/regression/test_phase3_toy_case_005.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase3_toy_case_005.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0460358GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-028/result.json)；SHA256 `df80bf0da8d05ef361e2d234dbbf3fe0dbed7c07279dcc36df74e7a19027f213`。

#### `01-regression-029` · tests/regression/test_phase4_scope_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase4_scope_benchmark_001.py"]}`。
- 观测墙钟：2.282 秒；进程树提交内存峰值：0.0488701GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-029/result.json)；SHA256 `1e533792c07d4e8fdcdf545ba3342a17fca0752354780ffa7fd22886b296998a`。

#### `01-regression-030` · tests/regression/test_phase5_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase5_benchmark_001.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0473175GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-030/result.json)；SHA256 `dd33e21c489829de724faa65bedad74c8b71a6bdf9180d93588938cdaaa25abf`。

#### `01-regression-031` · tests/regression/test_phase5_string_generator_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase5_string_generator_oracle.py"]}`。
- 观测墙钟：3.39 秒；进程树提交内存峰值：0.0453262GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-031/result.json)；SHA256 `fbc2cd373859cbe1f1753b8ccea809d654039710a8fc925741d9910cc8eda350`。

#### `01-regression-032` · tests/regression/test_phase6_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase6_benchmark_001.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0627403GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-032/result.json)；SHA256 `2876e4ca380257b4cd36b7d5b259814cb1952a353aefd250e485ae5c091acef4`。

#### `01-regression-033` · tests/regression/test_phase6_pairing_generator_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase6_pairing_generator_oracle.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0446167GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-033/result.json)；SHA256 `dc35f7714be841d31f96fed11b542523e3953bb3b43bad7a4982caf57c5cc593`。

#### `01-regression-034` · tests/regression/test_phase7_itinerary_generator_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase7_itinerary_generator_benchmark.py"]}`。
- 观测墙钟：3.453 秒；进程树提交内存峰值：0.0669365GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-034/result.json)；SHA256 `13dc75584fde49c4a8890e273a9bab0a558f01fa37ef6f676d0d27709bd7f1e2`。

#### `01-regression-035` · tests/regression/test_phase7_itinerary_generator_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase7_itinerary_generator_oracle.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0443802GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-035/result.json)；SHA256 `a86830b74c907fa8b7c203efeae3ad8122872100d0c6791573a852dd38caf021`。

#### `01-regression-036` · tests/regression/test_phase8_benders_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase8_benders_benchmark.py"]}`。
- 观测墙钟：3.469 秒；进程树提交内存峰值：0.056881GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-036/result.json)；SHA256 `e1e197d18c3f6192419a3c38fea15c99b3b5c1392879c765165661da2b60c5b7`。

#### `01-regression-037` · tests/regression/test_phase8_benders_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase8_benders_oracle.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0467758GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-037/result.json)；SHA256 `dbd583b42a2521d1331beb6d76e24ccfd5e669f5e0d40bea530a589f1d1634fb`。

#### `01-regression-038` · tests/regression/test_phase8_benders_scope.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase8_benders_scope.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0472412GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-038/result.json)；SHA256 `be9f37d5b30a50d5fb22a7dd0b4316eacf118428e1db6c8c388284622332d50a`。

#### `01-regression-039` · tests/regression/test_toy_cases.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_toy_cases.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0410118GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-039/result.json)；SHA256 `cf33ce190a94f7379344754f1a4ef9079fb2f0d6ce8e5bf4e192ab1dd2f73cdc`。

#### `01-regression-040` · tests/regression/test_validation_case_catalog.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_validation_case_catalog.py"]}`。
- 观测墙钟：17.265 秒；进程树提交内存峰值：0.146606GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-040/result.json)；SHA256 `a0b8980e4ad9ad2325991af2a0ecc36ca852aa065059e23f22a7353c071381e3`。

#### `01-regression-041` · tests/unit/test_aircraft_string_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_aircraft_string_column_generation.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0453491GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-041/result.json)；SHA256 `6bf8e9f7df12485add293605349371335e2f38ee84b4ebe6ab29864122236a94`。

#### `01-regression-042` · tests/unit/test_aircraft_string_master.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_aircraft_string_master.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0450211GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-042/result.json)；SHA256 `b025ea9371972ebe7f8cd4ea0d81237c8f16eba2f04c9f2706c312ab0fc68560`。

#### `01-regression-043` · tests/unit/test_aircraft_string_pricing.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_aircraft_string_pricing.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0449982GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-043/result.json)；SHA256 `8ef78b494c82d34fabde2f28623d2075e9a283a511ce1c0f94e565a980e3578b`。

#### `01-regression-044` · tests/unit/test_arm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_arm.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0461273GiB。
- 结果与原因：pytest exit=0; {'passed': 17}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-044/result.json)；SHA256 `8a53d57c6e28ea304ed2ea9225049979b70394d32d8ea78446754da16a880fb3`。

#### `01-regression-045` · tests/unit/test_benders.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_benders.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0469322GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-045/result.json)；SHA256 `0eb1a8912786580ae520b327ddff1020d2bb19b1decf5541a9cfdf93de175464`。

#### `01-regression-046` · tests/unit/test_benders_branch_and_price.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_benders_branch_and_price.py"]}`。
- 观测墙钟：2.266 秒；进程树提交内存峰值：0.0444336GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-046/result.json)；SHA256 `3cef04c03a94738f4395935f941f2ff03fc7a231b9572cb94989a1f711331cf9`。

#### `01-regression-047` · tests/unit/test_benders_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_benders_column_generation.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0463676GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-047/result.json)；SHA256 `59cb4199f6576222ff7950996c2bec38456cf3021c43c28fa5e2c9cab83e48cc`。

#### `01-regression-048` · tests/unit/test_branch_and_price.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_branch_and_price.py"]}`。
- 观测墙钟：2.296 秒；进程树提交内存峰值：0.0464897GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-048/result.json)；SHA256 `3e16bd8bf621ce3cf0ba47d9f1275955e14fcc272874d79c181b1afb8fa2b2a2`。

#### `01-regression-049` · tests/unit/test_column_validator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_column_validator.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0409775GiB。
- 结果与原因：pytest exit=0; {'passed': 16}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-049/result.json)；SHA256 `ca0324520ec1d20da31750097d401b73d5ca68dcd68963ea89ca3d78782cebdd`。

#### `01-regression-050` · tests/unit/test_columns_schema.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_columns_schema.py"]}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.041069GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-050/result.json)；SHA256 `1a93add4c5b239d08fba2609d782f1be6c95d78f96d3f56ac0b209b79a094723`。

#### `01-regression-051` · tests/unit/test_constraint_precheck.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_constraint_precheck.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0453758GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-051/result.json)；SHA256 `74a57c041a388eba33698d73b21b2fc50d99fbfb4cd71b0d97c1a82871287fc2`。

#### `01-regression-052` · tests/unit/test_constraint_registry.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_constraint_registry.py"]}`。
- 观测墙钟：2.296 秒；进程树提交内存峰值：0.0446587GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-052/result.json)；SHA256 `f8bde38ced6b1dc1bab5d3863a4cf95929427b1f772e92ca73e34472a7ef56f6`。

#### `01-regression-053` · tests/unit/test_cost_config.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_cost_config.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0424995GiB。
- 结果与原因：pytest exit=0; {'passed': 16}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-053/result.json)；SHA256 `1fcdc8b3a49aea01d08db1898ed5da02345a253ffdca98047cfac5a795fc4ca4`。

#### `01-regression-054` · tests/unit/test_crew_network.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_network.py"]}`。
- 观测墙钟：2.329 秒；进程树提交内存峰值：0.0445518GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-054/result.json)；SHA256 `99b6c8b4ff7d2f857686ed4c16be3707e885d38ed9583b33500433edd066e1dd`。

#### `01-regression-055` · tests/unit/test_crew_pairing_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_pairing_column_generation.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0456429GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-055/result.json)；SHA256 `40b3f6c365662f8c245ba5ceb4a1908f6867bc5567e1a7f7c7c2f17cf13b45d7`。

#### `01-regression-056` · tests/unit/test_crew_pairing_master.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_pairing_master.py"]}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.0451584GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-056/result.json)；SHA256 `a2da90c5e1f12e9102d67d39ca1a677495478df0711ba774c438163bae882388`。

#### `01-regression-057` · tests/unit/test_crew_pairing_pricing.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_pairing_pricing.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0453758GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-057/result.json)；SHA256 `457293ae41e727baf7b077fe40dbeae9d08bdaa412bc4682740fe466fdf2edaa`。

#### `01-regression-058` · tests/unit/test_crm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crm.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.0463715GiB。
- 结果与原因：pytest exit=0; {'passed': 20}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-058/result.json)；SHA256 `443c83e0b2089ebfda25e5e2ce007de01d6bfc4794440062ff4a9442c6e0bfd3`。

#### `01-regression-059` · tests/unit/test_expected_schema.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_expected_schema.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0410271GiB。
- 结果与原因：pytest exit=0; {'passed': 4}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-059/result.json)；SHA256 `6cf320a21a70636e4efdb1894ae860090f82b0adae8f2c2c084c41f4ffadbfb3`。

#### `01-regression-060` · tests/unit/test_flight_network.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_flight_network.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0448189GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-060/result.json)；SHA256 `56c14287fce0d734641ec0082192cff5d3269fffc3a6ca2f786e573c766b9496`。

#### `01-regression-061` · tests/unit/test_gate_inventory.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_gate_inventory.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0454788GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-061/result.json)；SHA256 `f1da0fd3e8848bc9b614b6a16cdf16b2a20745a3ae018941774dcad2639ab5f9`。

#### `01-regression-062` · tests/unit/test_gurobi_adapter.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_gurobi_adapter.py"]}`。
- 观测墙钟：2.329 秒；进程树提交内存峰值：0.0345497GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-062/result.json)；SHA256 `639a77bc8719c6bb53a054659006b9b8cd55b3de27c06570c1dc3458528987ee`。

#### `01-regression-063` · tests/unit/test_incidence.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_incidence.py"]}`。
- 观测墙钟：2.281 秒；进程树提交内存峰值：0.0457458GiB。
- 结果与原因：pytest exit=0; {'passed': 15}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-063/result.json)；SHA256 `fe899b126ebe341c83306cb001b4a61c69087422f3c726fef7cb33dccdb032fe`。

#### `01-regression-064` · tests/unit/test_indices.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_indices.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0444374GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-064/result.json)；SHA256 `d5e5bcea9c3524bb15bcd3c8f0d2f52211f1ed3fcab9656bfb0e975a2bfef026`。

#### `01-regression-065` · tests/unit/test_integrated_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_integrated_oracle.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0475197GiB。
- 结果与原因：pytest exit=0; {'passed': 8}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-065/result.json)；SHA256 `744b04d2907a34551460f25824f69823212af31d6ae260dd046a190bba731c3e`。

#### `01-regression-066` · tests/unit/test_itinerary_generator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_itinerary_generator.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0458794GiB。
- 结果与原因：pytest exit=0; {'passed': 20}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-066/result.json)；SHA256 `842eb4bc5273e59bdd2525e7aa89111d6bfb89650d5ef2413b2318857939f257`。

#### `01-regression-067` · tests/unit/test_json_schema_contract.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_json_schema_contract.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0447617GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-067/result.json)；SHA256 `6c463c5153bc92545a85df05916f60f346070c2e18a1be1a5fac9aea57ed48d4`。

#### `01-regression-068` · tests/unit/test_model_result.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_model_result.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.040905GiB。
- 结果与原因：pytest exit=0; {'passed': 12}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-068/result.json)；SHA256 `d03ecf5be4dd3ec1c34b37f40ce49734300da1f453ec1286168060722132e00d`。

#### `01-regression-069` · tests/unit/test_oracle_validator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_oracle_validator.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0409851GiB。
- 结果与原因：pytest exit=0; {'passed': 13}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-069/result.json)；SHA256 `b22c3d50317d37076aafe15c3f55ce37388006abbcbe582a94aafa101cad0fcd`。

#### `01-regression-070` · tests/unit/test_pairing_generator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_pairing_generator.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.0445023GiB。
- 结果与原因：pytest exit=0; {'passed': 16}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-070/result.json)；SHA256 `adde2fddb429f6d1192aaf947c010ceb93505f27d2cfe15420ab2e1a06a7d3b6`。

#### `01-regression-071` · tests/unit/test_passenger_capacity.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_passenger_capacity.py"]}`。
- 观测墙钟：2.281 秒；进程树提交内存峰值：0.0425682GiB。
- 结果与原因：pytest exit=0; {'passed': 8}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-071/result.json)；SHA256 `5ec1cb02094f3f1746f50510c0494e78b89cb3d7935aec074601b090131ca0cf`。

#### `01-regression-072` · tests/unit/test_passenger_incidence.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_passenger_incidence.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0448265GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-072/result.json)；SHA256 `1ec26684e8c9430fb7369e7b6376e2820771b7c4bfd159f3419d763cc98f8d99`。

#### `01-regression-073` · tests/unit/test_passenger_network.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_passenger_network.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0447769GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-073/result.json)；SHA256 `cb3d84e176392d98091ae7b4a744b5a2a5090789fe4bf75db66b862c92b5c5a6`。

#### `01-regression-074` · tests/unit/test_prm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_prm.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0472679GiB。
- 结果与原因：pytest exit=0; {'passed': 17}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-074/result.json)；SHA256 `be50911c5609646663ef7cabbdf40cc362f5c11cca56f1ea5bb286ece0dbc473`。

#### `01-regression-075` · tests/unit/test_recovery_handoff.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_recovery_handoff.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0442581GiB。
- 结果与原因：pytest exit=0; {'passed': 7}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-075/result.json)；SHA256 `71ea40e6f88f6dab158da84f172fb2b504d89b2e0117da1ecd68ba851a6d5249`。

#### `01-regression-076` · tests/unit/test_recovery_metrics.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_recovery_metrics.py"]}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.0409698GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-076/result.json)；SHA256 `c706e47ed1702cb399e2f1276c6d629bf14a49516b0330ff7e72c9a6e7d46ead`。

#### `01-regression-077` · tests/unit/test_result_builder.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_result_builder.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0448036GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-077/result.json)；SHA256 `9f0184b3deeae6ad421207c81ca75b39dc6da1d812c04e877718868c224438b6`。

#### `01-regression-078` · tests/unit/test_schema.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_schema.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0412292GiB。
- 结果与原因：pytest exit=0; {'passed': 9}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-078/result.json)；SHA256 `e375a80c4e9b1ea7ac6b5c37edeba90171188bdf528c68923ff6f4cec667d913`。

#### `01-regression-079` · tests/unit/test_scope.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_scope.py"]}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.0456581GiB。
- 结果与原因：pytest exit=0; {'passed': 17}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-079/result.json)；SHA256 `25c3c132b2e9cef0542681b4db4c8c4e36ee6b869dec921f8b98d30b170210e0`。

#### `01-regression-080` · tests/unit/test_solver_contract.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_solver_contract.py"]}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0326042GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-080/result.json)；SHA256 `f8083a191106133277f8b8f3f2d0331e5d0c1ba40b59f1b0f97868663cb6652f`。

#### `01-regression-081` · tests/unit/test_srm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_srm.py"]}`。
- 观测墙钟：2.297 秒；进程树提交内存峰值：0.047596GiB。
- 结果与原因：pytest exit=0; {'passed': 11}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-081/result.json)；SHA256 `79695fec24bd922eaf71a17ac7e09b759c83991b47d7ff476513eb7606d4eb33`。

#### `01-regression-082` · tests/unit/test_string_generator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_string_generator.py"]}`。
- 观测墙钟：2.375 秒；进程树提交内存峰值：0.0447998GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-082/result.json)；SHA256 `6878d112999cd315dd40d1f7ae41e344e373ecf0c00968b7ba40f8aaf067e2eb`。

#### `01-regression-083` · tests/unit/test_validation_data_suite.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_validation_data_suite.py"]}`。
- 观测墙钟：5.812 秒；进程树提交内存峰值：0.0919876GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-083/result.json)；SHA256 `78bb51208457642fde51b463e81b1a3ad255e5363c672e88673b5a9903e9c22d`。

#### `01-regression-084` · tests/unit/test_validator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_validator.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0410271GiB。
- 结果与原因：pytest exit=0; {'passed': 14}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-084/result.json)；SHA256 `d7534b8970778be99cd4900af9f4d1aecdc561140826b542fd597baf36adfea0`。

#### `01-regression-085` · tests/unit/test_visualization_js.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_visualization_js.py"]}`。
- 观测墙钟：2.312 秒；进程树提交内存峰值：0.085434GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-085/result.json)；SHA256 `6c1ed3b681037d57da1581a4513e245e9bada7ac08536d63e24c84f6aec8f6d9`。

#### `01-regression-086` · tests/unit/test_workbench_comparison.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_workbench_comparison.py"]}`。
- 观测墙钟：2.281 秒；进程树提交内存峰值：0.0415649GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-086/result.json)；SHA256 `1f388ae452ed0da75a54321e398c335737f0f21d875a4fed8979f05b59811fee`。

#### `01-regression-087` · tests/unit/test_workbench_compiler.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_workbench_compiler.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0466118GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-087/result.json)；SHA256 `7bbd46b8ad922ff3e21286876045a876fb5992959e72a4253518c6a8456c328d`。

#### `01-regression-088` · tests/unit/test_workbench_js.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_workbench_js.py"]}`。
- 观测墙钟：2.328 秒；进程树提交内存峰值：0.0834579GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-088/result.json)；SHA256 `c59931df641538d2ab04916ac7c9f3ed0cf72d65373184a2e9cd2b2c344b404c`。

#### `01-regression-089` · tests/unit/test_xma_recovery.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_xma_recovery.py"]}`。
- 观测墙钟：12.719 秒；进程树提交内存峰值：0.108528GiB。
- 结果与原因：pytest exit=0; {'passed': 27}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/01-regression-089/result.json)；SHA256 `05bb2a111b7e3f501400b5208c6e7fb336e72440b24bcfc82709107437c8a38d`。

#### `01-regression-005` · tests/api/test_workbench_v2_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_workbench_v2_api.py"]}`。
- 观测墙钟：10.672 秒；进程树提交内存峰值：0.147228GiB。
- 结果与原因：pytest exit=0; {'passed': 7}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/01-regression-005/result.json)；SHA256 `9bbe9296505fe49f92415842d6805c713846693cdd93e8971f624d76c08212d8`。

#### `01-regression-006` · tests/api/test_xma_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_xma_api.py"]}`。
- 观测墙钟：15.922 秒；进程树提交内存峰值：0.275803GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/01-regression-006/result.json)；SHA256 `fa78a45d3be43c1af97cfe2bef9c0fd95e23bc9eb7cd49ecb5294dbbc2ea1f13`。

### 02 AIR - expected solutions

#### `02-air-cases-001` · benchmark-disruption-recovery

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"benchmark-disruption-recovery"}`。
- 观测墙钟：3.547 秒；进程树提交内存峰值：0.0757942GiB。
- 结果与原因：optimal objective=18080.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-001/result.json)；SHA256 `a7ab7d753e38fa672405fea2a1a71d89ec1789aeddb70e1c9dfbaf7e601d07b7`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 18080.0, "required_flight_options": {"F2": "FO_F2_D50", "F10": "FO_F10_D20", "F11": "FO_F11_D10"}, "required_metrics": {"cancelled_flights": 0, "delayed_flights": 3, "aircraft_reassignments": 2, "passenger_reaccommodated_groups": 1, "unserved_passengers": 0}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 18080 | 18080 | 18080 | True | 缺失 |

#### `02-air-cases-002` · crew-recovery-integrality

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"crew-recovery-integrality","additional_expectations":[{"status":"optimal","objective_total":95200.0}]}`。
- 观测墙钟：4.766 秒；进程树提交内存峰值：0.073101GiB。
- 结果与原因：optimal objective=95200.0; 停止原因=exact_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-002/result.json)；SHA256 `dc755a072544c59e266c7a6d7d3bf03e74d525accb7f9d0774ffd53db182b65d`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 95200.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 95200 | 95200 | 95200 | True | 缺失 |

#### `02-air-cases-003` · passenger-capacity-constrained

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"passenger-capacity-constrained"}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.07024GiB。
- 结果与原因：optimal objective=1010.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-003/result.json)；SHA256 `5fce37b3f9bc86336e98f6db20a20069f93677bbf866c38d9187761b40756dbe`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 1010.0, "required_flight_options": {"T5_F1": "FO_T5_F1_D10"}, "required_metrics": {"delayed_flights": 1, "unserved_passengers": 0}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 1010 | 1010 | 1010 | True | 缺失 |

#### `02-air-cases-004` · passenger-capacity-relaxed

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"passenger-capacity-relaxed"}`。
- 观测墙钟：2.313 秒；进程树提交内存峰值：0.0701714GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-004/result.json)；SHA256 `a927a0ab1332566162b624bcc22ba03cadb3ceedff6a3dfb90bd62a9ce672cd7`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 0.0, "required_flight_options": {"T5_F1": "FO_T5_F1_ORIG"}, "required_metrics": {"delayed_flights": 0, "unserved_passengers": 0}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 |

#### `02-air-cases-005` · delay-cost-cancellation-tradeoff

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"delay-cost-cancellation-tradeoff"}`。
- 观测墙钟：2.391 秒；进程树提交内存峰值：0.0710793GiB。
- 结果与原因：optimal objective=25000.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-005/result.json)；SHA256 `dd7bf8c9c7341b410adce691f75dad5e89af291f9fc51487d14d8980b14a79ca`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 25000.0, "required_flight_options": {"T5_F1": "FO_T5_F1_ORIG"}, "required_metrics": {"delayed_flights": 0, "unserved_passengers": 10}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 25000 | 25000 | 25000 | True | 缺失 |

#### `02-air-cases-006` · solve-ready-infeasible

- 执行状态：`passed`；结论：**返回不可行，认证与边界见原始结果**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"solve-ready-infeasible"}`。
- 观测墙钟：2.329 秒；进程树提交内存峰值：0.0714531GiB。
- 结果与原因：infeasible objective=None; 停止原因=phase11_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-006/result.json)；SHA256 `59f2509b83dcea75b6f502c29e864681782306880451a4ac9d26f9a21674c2d1`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "infeasible", "objective_total": null}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | infeasible | 缺失 | 0 | 缺失 | 缺失 | 缺失 |

#### `02-air-cases-007` · scenario-only-minimal

- 执行状态：`passed`；结论：**输入合同或预检完成，未运行优化**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"scenario-only-minimal"}`。
- 观测墙钟：1.203 秒；进程树提交内存峰值：0.0348625GiB。
- 结果与原因：Expected input rejection / Scenario-only verified。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-007/result.json)；SHA256 `eadf7b91e3ce60d8dfcd6e9b22404573f50c304cd11fb4815c8437a9caa47e74`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| air_case/ | not_run | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

#### `02-air-cases-008` · invalid-missing-airport

- 执行状态：`passed`；结论：**输入合同或预检完成，未运行优化**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"invalid-missing-airport"}`。
- 观测墙钟：1.187 秒；进程树提交内存峰值：0.0347595GiB。
- 结果与原因：Expected input rejection / Scenario-only verified。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-008/result.json)；SHA256 `050c052afe62da87fd075a6126e7899bd9b1cd0d314b8107bd791ac5f634aab9`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| air_case/ | not_run | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

#### `02-air-cases-009` · micro-aircraft-coupling

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-aircraft-coupling.json","expected":{"status":"optimal"}}`。
- 观测墙钟：2.343 秒；进程树提交内存峰值：0.0700607GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-009/result.json)；SHA256 `7b1636853af13147d6f51a64ef2c12dd91e11b211fe868a21dcc11ef51aca706`。
- 参考断言：`{"status": "optimal"}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 |

#### `02-air-cases-010` · micro-scope-closure

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-scope-closure.json","expected":{"status":"optimal","objective_total":2040.0}}`。
- 观测墙钟：2.375 秒；进程树提交内存峰值：0.0701141GiB。
- 结果与原因：optimal objective=2040.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-010/result.json)；SHA256 `e918ff3331e00eeaf1ab58a76e6f9bd3d587faa43f4960ffd93b2dcf277fa155`。
- 参考断言：`{"status": "optimal", "objective_total": 2040.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 2040 | 2040 | 2040 | True | 缺失 |

#### `02-air-cases-011` · micro-aircraft-string-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-aircraft-string-generation.json","expected":{"status":"optimal","objective_total":0.0}}`。
- 观测墙钟：2.359 秒；进程树提交内存峰值：0.0704727GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-011/result.json)；SHA256 `e026168c8a5fada35047aec8376d2e45a1a6924b316f1f7cc628ec238fea6904`。
- 参考断言：`{"status": "optimal", "objective_total": 0.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 |

#### `02-air-cases-012` · micro-passenger-itinerary-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-passenger-itinerary-generation.json","expected":{"status":"optimal","objective_total":0.0}}`。
- 观测墙钟：2.343 秒；进程树提交内存峰值：0.0707359GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-012/result.json)；SHA256 `c7a7732e5318168ab0a8e5611101237b19b5ece4eefb074e40141f11233201b0`。
- 参考断言：`{"status": "optimal", "objective_total": 0.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 |

#### `02-air-cases-013` · micro-fixed-column-benders

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-fixed-column-benders.json","expected":{"status":"optimal"}}`。
- 观测墙钟：2.406 秒；进程树提交内存峰值：0.070118GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-013/result.json)；SHA256 `9d04a6f56be5fc371d3fc6f6322557d2c8b474d74abd3e5a404b015562e0deb7`。
- 参考断言：`{"status": "optimal"}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 |

#### `02-air-cases-014` · micro-aircraft-column-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-aircraft-column-generation.json","expected":{"status":"optimal","objective_total":0.0}}`。
- 观测墙钟：2.375 秒；进程树提交内存峰值：0.0695839GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-014/result.json)；SHA256 `67fb5eb0202381f8e19463adfaf5d947eba96b08f976f2c9fcff7ddc7c9c7b9e`。
- 参考断言：`{"status": "optimal", "objective_total": 0.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 |

#### `02-air-cases-015` · micro-crew-column-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-crew-column-generation.json","expected":{"status":"optimal","objective_total":150.0}}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.0702553GiB。
- 结果与原因：optimal objective=150.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-015/result.json)；SHA256 `9c56c969a0ecea15b70f3407c376b02b5729f4d3558357f542c01f44caf50ec2`。
- 参考断言：`{"status": "optimal", "objective_total": 150.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 150 | 150 | 150 | True | 缺失 |

#### `02-air-cases-016` · micro-benders-column-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-benders-column-generation.json","expected":{"status":"optimal","objective_total":220.0}}`。
- 观测墙钟：2.375 秒；进程树提交内存峰值：0.0700874GiB。
- 结果与原因：optimal objective=220.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-016/result.json)；SHA256 `97f0dd0b504a9e773740ed7c618606d784032987153cf77ac7928b780fb75277`。
- 参考断言：`{"status": "optimal", "objective_total": 220.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 220 | 220 | 220 | True | 缺失 |

#### `02-air-cases-017` · micro-crew-root-integrality

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-crew-root-integrality.json","expected":{"status":"optimal"}}`。
- 观测墙钟：2.359 秒；进程树提交内存峰值：0.0719223GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/02-air-cases-017/result.json)；SHA256 `b0c665e74ff593259fed576ed72c24ac3326788e4161b0e01b14270ed830629f`。
- 参考断言：`{"status": "optimal"}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 |

### 03 AIR - Aircraft column generation

#### `03-aircraft-cg-001` · aircraft: full LP vs CG / toy_case_011_aircraft_string_column_generation

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"aircraft","case":"toy_case_011_aircraft_string_column_generation","repeats":3,"warmups":1}`。
- 观测墙钟：2.344 秒；进程树提交内存峰值：0.0355186GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.223。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/03-aircraft-cg-001/result.json)；SHA256 `ecc885a8f180f1e4891b3c60f80898e7a079928dc10022c6f9e11d534045b0a1`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| full/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0052742 |
| cg/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0210517 |
| cg/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0162342 |
| full/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0040268 |
| full/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0040016 |
| cg/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0180241 |

#### `03-aircraft-cg-002` · aircraft: full LP vs CG / phase1_benchmark_001

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"aircraft","case":"phase1_benchmark_001","repeats":3,"warmups":1}`。
- 观测墙钟：2.265 秒；进程树提交内存峰值：0.0371513GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.349。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/03-aircraft-cg-002/result.json)；SHA256 `0484d28d03cf74b234bb8a2b9fd6dab3b67f923eb7b81aed2b97dd935f7d399c`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| full/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0170152 |
| cg/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0531607 |
| cg/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0562653 |
| full/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0187622 |
| full/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.018545 |
| cg/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0531098 |

### 04 AIR - Crew column generation

#### `04-crew-cg-001` · crew: full LP vs CG / toy_case_012_crew_pairing_column_generation

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"crew","case":"toy_case_012_crew_pairing_column_generation","repeats":3,"warmups":1}`。
- 观测墙钟：1.125 秒；进程树提交内存峰值：0.0360222GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.184。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/04-crew-cg-001/result.json)；SHA256 `c077c9caab604e6789825a25587083529e6a7f23f6be5230c005d601b209e83b`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| full/0 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0044043 |
| cg/0 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0249033 |
| cg/1 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0229774 |
| full/1 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0043524 |
| full/2 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0039729 |
| cg/2 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.023689 |

#### `04-crew-cg-002` · crew: full LP vs CG / phase1_benchmark_001

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"crew","case":"phase1_benchmark_001","repeats":3,"warmups":1}`。
- 观测墙钟：3.219 秒；进程树提交内存峰值：0.0430031GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.358。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/04-crew-cg-002/result.json)；SHA256 `5153dcb9eeeccce55ffa58864834c8671fc6bd6fd624ac1558d11239c1892157`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| full/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0603964 |
| cg/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.17412 |
| cg/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.208478 |
| full/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0956332 |
| full/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0746243 |
| cg/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.239263 |

### 05 AIR - Benders BP vs integrated

#### `05-air-oracle-001` · Integrated vs Benders BP / benchmark-disruption-recovery

- 执行状态：`passed`；结论：**联合 Oracle 与 Benders/B&P 最优一致**。
- 类型：`air_oracle`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"benchmark-disruption-recovery","repeats":3}`。
- 观测墙钟：16.781 秒；进程树提交内存峰值：0.0475655GiB。
- 结果与原因：Integrated oracle and exact Benders/BP agree in all repetitions。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/05-air-oracle-001/result.json)；SHA256 `a08a4bf9eb398d21670a435963aa515a0411ddc9b62edc073797a9f273013b0a`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| integrated/0 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.300795 |
| benders_bp/0 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 3.96246 |
| benders_bp/1 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 3.88443 |
| integrated/1 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.142322 |
| integrated/2 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.14749 |
| benders_bp/2 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 2.44243 |

#### `05-air-oracle-002` · Integrated vs Benders BP / crew-recovery-integrality

- 执行状态：`passed`；结论：**联合 Oracle 与 Benders/B&P 最优一致**。
- 类型：`air_oracle`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"crew-recovery-integrality","repeats":3}`。
- 观测墙钟：21.297 秒；进程树提交内存峰值：0.0417862GiB。
- 结果与原因：Integrated oracle and exact Benders/BP agree in all repetitions。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/05-air-oracle-002/result.json)；SHA256 `4ad176c8603b675371ea2edd7594d8fbeb716db6a4a2bc766f4f937fed93c463`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| integrated/0 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 0.0755641 |
| benders_bp/0 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 4.44837 |
| benders_bp/1 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 5.25336 |
| integrated/1 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 0.0444723 |
| integrated/2 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 0.0401639 |
| benders_bp/2 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 4.14059 |

### 06 Conflicts - cancellation and limits

#### `06-stop-conflict-001` · Capacity/candidates/order metamorphic properties

- 执行状态：`passed`；结论：**重复最优目标不一致，需复核**。
- 类型：`metamorphic`；阶段：`correctness`；单例墙钟/求解器预算：300/60 秒；提交内存上限：1.5GiB。
- 参数：`{}`。
- 观测墙钟：3.593 秒；进程树提交内存峰值：0.0882149GiB。
- 结果与原因：Capacity relaxation, candidate expansion, order invariance verified; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/06-stop-conflict-001/result.json)；SHA256 `81883358767016f49f0689a232564a517482413929e7506866c367f3fec591f7`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 160 | 160 | 160 | True | 0.0197922 |
| joint_arc_flow/0 | optimal | 110 | 110 | 110 | True | 0.0160129 |

#### `06-stop-conflict-002` · Immediate cancellation and conflicting XMA instance

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`stop_controls`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{}`。
- 观测墙钟：3.516 秒；进程树提交内存峰值：0.122082GiB。
- 结果与原因：Certified infeasibility, cancellation and restricted nonoptimal output verified。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/06-stop-conflict-002/result.json)；SHA256 `c570b5a1f579615df1d079b330f980e1958a13edeb37e5ac4e9063628d691ff1`。

### 07 XMA - four algorithms two objectives

#### `07-xma-oracle-001` · Four algorithms / tianchi_2017 / normal

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"normal"}`。
- 观测墙钟：3.594 秒；进程树提交内存峰值：0.0835953GiB。
- 结果与原因：Four architectures agree; objective=0.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-001/result.json)；SHA256 `0f4fe50ac6149e5701b8af25126ee870c611f1d116d3828f80818bf797d91018`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 0 | 0 | 0 | True | 0.0283069 |
| joint_path_oracle/0 | optimal | 0 | 0 | 0 | True | 0.0128505 |
| benders_joint/0 | optimal | 0 | 0 | 0 | True | 0.0208093 |
| benders_cg_bp/0 | optimal | 0 | 0 | 0 | True | 0.0213594 |

#### `07-xma-oracle-002` · Four algorithms / tianchi_2017 / delay

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"delay"}`。
- 观测墙钟：2.343 秒；进程树提交内存峰值：0.0844498GiB。
- 结果与原因：Four architectures agree; objective=110.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-002/result.json)；SHA256 `3f9c022bb69ff8e961c5a46bc833f352c700dedc63b7547eff9c8c3a863a030f`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 110 | 110 | 110 | True | 0.0177221 |
| joint_path_oracle/0 | optimal | 110 | 110 | 110 | True | 0.0137101 |
| benders_joint/0 | optimal | 110 | 110 | 110 | True | 0.0280081 |
| benders_cg_bp/0 | optimal | 110 | 110 | 110 | True | 0.0295537 |

#### `07-xma-oracle-003` · Four algorithms / tianchi_2017 / overflow

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"overflow"}`。
- 观测墙钟：2.391 秒；进程树提交内存峰值：0.0844498GiB。
- 结果与原因：Four architectures agree; objective=16.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-003/result.json)；SHA256 `24546912adac6a30687f6345b5b7b233a090c90e564caff0f9f78aa3eeecb048`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 16 | 16 | 16 | True | 0.0152536 |
| joint_path_oracle/0 | optimal | 16 | 16 | 16 | True | 0.0134325 |
| benders_joint/0 | optimal | 16 | 16 | 16 | True | 0.0182468 |
| benders_cg_bp/0 | optimal | 16 | 16 | 16 | True | 0.0359654 |

#### `07-xma-oracle-004` · Four algorithms / tianchi_2017 / split

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"split"}`。
- 观测墙钟：3.562 秒；进程树提交内存峰值：0.0851326GiB。
- 结果与原因：Four architectures agree; objective=0.26666666666666666; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-004/result.json)；SHA256 `6de861daf9ac0c1987575ab96878d07621d9109fae5fad91f5837a9818910e90`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.0316499 |
| joint_path_oracle/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.0157723 |
| benders_joint/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.0235548 |
| benders_cg_bp/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.0705495 |

#### `07-xma-oracle-005` · Four algorithms / tianchi_2017 / branch

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"branch"}`。
- 观测墙钟：3.578 秒；进程树提交内存峰值：0.0848961GiB。
- 结果与原因：Four architectures agree; objective=0.2; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-005/result.json)；SHA256 `081d46bc542ce7e8542e868ab5718bf329f1f51ff86304188a17e5a53f938ac5`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.0309474 |
| joint_path_oracle/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.0149904 |
| benders_joint/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.0249425 |
| benders_cg_bp/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.0712729 |

#### `07-xma-oracle-006` · Four algorithms / air_linear_v1 / normal

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"normal"}`。
- 观测墙钟：3.563 秒；进程树提交内存峰值：0.0843964GiB。
- 结果与原因：Four architectures agree; objective=0.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-006/result.json)；SHA256 `9fe14877bfb88c10ca1aea78d773cd479bdfa448894f7abeb8462139faa24c28`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 0 | 0 | 0 | True | 0.0272272 |
| joint_path_oracle/0 | optimal | 0 | 0 | 0 | True | 0.0145226 |
| benders_joint/0 | optimal | 0 | 0 | 0 | True | 0.0183608 |
| benders_cg_bp/0 | optimal | 0 | 0 | 0 | True | 0.0216554 |

#### `07-xma-oracle-007` · Four algorithms / air_linear_v1 / delay

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"delay"}`。
- 观测墙钟：3.562 秒；进程树提交内存峰值：0.0842781GiB。
- 结果与原因：Four architectures agree; objective=3060.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-007/result.json)；SHA256 `aea4a39364c08cab92977f4ce9252bd8ccf91110acd858a193a1850e927d05df`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 3060 | 3060 | 3060 | True | 0.027651 |
| joint_path_oracle/0 | optimal | 3060 | 3060 | 3060 | True | 0.0137232 |
| benders_joint/0 | optimal | 3060 | 3060 | 3060 | True | 0.0276241 |
| benders_cg_bp/0 | optimal | 3060 | 3060 | 3060 | True | 0.0325182 |

#### `07-xma-oracle-008` · Four algorithms / air_linear_v1 / overflow

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"overflow"}`。
- 观测墙钟：3.547 秒；进程树提交内存峰值：0.0844574GiB。
- 结果与原因：Four architectures agree; objective=10000.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-008/result.json)；SHA256 `2e36cb27bebd88e43e9403e1a6ad5f3f4d3a1b8fa9aad6792522d58d3a8cdb70`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 10000 | 10000 | 10000 | True | 0.0267852 |
| joint_path_oracle/0 | optimal | 10000 | 10000 | 10000 | True | 0.0140639 |
| benders_joint/0 | optimal | 10000 | 10000 | 10000 | True | 0.0575342 |
| benders_cg_bp/0 | optimal | 10000 | 10000 | 10000 | True | 0.09554 |

#### `07-xma-oracle-009` · Four algorithms / air_linear_v1 / split

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"split"}`。
- 观测墙钟：3.515 秒；进程树提交内存峰值：0.0841331GiB。
- 结果与原因：Four architectures agree; objective=0.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-009/result.json)；SHA256 `f0cd546e5026d942201b1180b3aea04f39fecd43b76b31b669ffeccd5a9bd988`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 0 | 0 | 0 | True | 0.0178636 |
| joint_path_oracle/0 | optimal | 0 | 0 | 0 | True | 0.0154723 |
| benders_joint/0 | optimal | 0 | 0 | 0 | True | 0.0219986 |
| benders_cg_bp/0 | optimal | 0 | 0 | 0 | True | 0.035588 |

#### `07-xma-oracle-010` · Four algorithms / air_linear_v1 / branch

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"branch"}`。
- 观测墙钟：3.579 秒；进程树提交内存峰值：0.0853195GiB。
- 结果与原因：Four architectures agree; objective=40.0; 停止原因=2, unknown。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_110703/jobs/07-xma-oracle-010/result.json)；SHA256 `f693d335bd7b4520a1ac6829a059ed2c8f842c175cb99a4731be74a6e5ea1573`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 40 | 40 | 40 | True | 0.0191725 |
| joint_path_oracle/0 | optimal | 40 | 40 | 40 | True | 0.0142051 |
| benders_joint/0 | optimal | 40 | 40 | 40 | True | 0.0223471 |
| benders_cg_bp/0 | optimal | 40 | 40 | 40 | True | 0.0478581 |

#### `07-xma-oracle-011` · Official JAR fixture revalidation (existing runtime only)

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`jar`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"java_executable":"D:\\Program Files\\MATLAB\\R2024b\\sys\\java\\jre\\win64\\jre\\bin\\java.exe"}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.530277GiB。
- 结果与原因：Official JAR and independent evaluator agree on the documented derived fixture。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/07-xma-oracle-011/result.json)；SHA256 `53539520abc38c9ef6a6161bf98e5fa18370b7fbc4c5584c0640f0008c4800f3`。

### 08 XMA - joint arc flow

#### `08-xma-arc-001` · Timing / fixed target=20 seed=None / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：16.985 秒；进程树提交内存峰值：0.126232GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-001/result.json)；SHA256 `13e2850d76616e10854162b504acda9cf271a6e7025b58381869a1e3ba49c2fb`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 11444 | 11444 | 11444 | True | 0.754055 |
| joint_arc_flow/1 | optimal | 11444 | 11444 | 11444 | True | 0.75662 |
| joint_arc_flow/2 | optimal | 11444 | 11444 | 11444 | True | 0.703094 |

#### `08-xma-arc-002` · Timing / fixed target=20 seed=None / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：17.234 秒；进程树提交内存峰值：0.126236GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-002/result.json)；SHA256 `8d628201b5612c410f28505bf0346610547d72fe42e967093daf64eae9c7996b`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.929416 |
| joint_arc_flow/1 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.890467 |
| joint_arc_flow/2 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.903985 |

#### `08-xma-arc-003` · Timing / fixed target=100 seed=None / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：38.844 秒；进程树提交内存峰值：0.14669GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-003/result.json)；SHA256 `087a62251e3321ad58204552a1544e62e2ade93ebf066cfc1faa0754e2644262`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 5.8825 |
| joint_arc_flow/1 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 6.06776 |
| joint_arc_flow/2 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 5.97191 |

#### `08-xma-arc-004` · Timing / fixed target=100 seed=None / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：37.688 秒；进程树提交内存峰值：0.146027GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-004/result.json)；SHA256 `b8cd211ba56dfd86a9f40e015bbd83220b42fe4a435fe495243413d43c509a33`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 5.74268 |
| joint_arc_flow/1 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 5.78286 |
| joint_arc_flow/2 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 5.76559 |

#### `08-xma-arc-005` · Timing / random target=20 seed=20261106 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：17.094 秒；进程树提交内存峰值：0.126087GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-005/result.json)；SHA256 `677523ac7278b2e8e53e1b35d051cf565f403358b53b459a597deebb9f11316e`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 5948 | 5948 | 5948 | True | 0.747742 |
| joint_arc_flow/1 | optimal | 5948 | 5948 | 5948 | True | 0.751037 |
| joint_arc_flow/2 | optimal | 5948 | 5948 | 5948 | True | 0.745184 |

#### `08-xma-arc-006` · Timing / random target=20 seed=20261106 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：17.125 秒；进程树提交内存峰值：0.125854GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-006/result.json)；SHA256 `d67e84c38f39329c0b88263a1503e0990d45e0f6001692b56b73aa422f6ee241`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 870000 | 870000 | 870000 | True | 0.866305 |
| joint_arc_flow/1 | optimal | 870000 | 870000 | 870000 | True | 0.796371 |
| joint_arc_flow/2 | optimal | 870000 | 870000 | 870000 | True | 0.752733 |

#### `08-xma-arc-007` · Timing / random target=20 seed=20261107 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：15.921 秒；进程树提交内存峰值：0.125484GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-007/result.json)；SHA256 `5bdd9af2584b5312984b90b7f8d399c68eb1cbc250b7a087870a2f8dd483b4f2`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.822769 |
| joint_arc_flow/1 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.730909 |
| joint_arc_flow/2 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.716778 |

#### `08-xma-arc-008` · Timing / random target=20 seed=20261107 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.578 秒；进程树提交内存峰值：0.125431GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-008/result.json)；SHA256 `0245bb0f340ed01f94127cd352dfde77ad4ba9b0eef09cb39c93ad29329fbdc4`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.303829 |
| joint_arc_flow/1 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.264885 |
| joint_arc_flow/2 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.253152 |

#### `08-xma-arc-009` · Timing / random target=100 seed=20261106 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：15.016 秒；进程树提交内存峰值：0.136189GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-009/result.json)；SHA256 `d6a9aa195836f1aab25f1d5e7648441bb0cdc39b507831ce073257900b5fb068`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.55935 |
| joint_arc_flow/1 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.71346 |
| joint_arc_flow/2 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.57373 |

#### `08-xma-arc-010` · Timing / random target=100 seed=20261106 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：12.844 秒；进程树提交内存峰值：0.13438GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-010/result.json)；SHA256 `ff3d905da5212189b2b3501d2c505461270f09f74aab32272426873f300b550e`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.34992 |
| joint_arc_flow/1 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.34614 |
| joint_arc_flow/2 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.41832 |

#### `08-xma-arc-011` · Timing / random target=100 seed=20261107 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.594 秒；进程树提交内存峰值：0.129429GiB。
- 结果与原因：joint_arc_flow: infeasible, infeasible, infeasible; 停止原因=3。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-011/result.json)；SHA256 `20b52580959bdffbe75cbc8d3403af44f9bc74ca9daecbbae81d4c85c03fefd5`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.40681 |
| joint_arc_flow/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.405416 |
| joint_arc_flow/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.380504 |

#### `08-xma-arc-012` · Timing / random target=100 seed=20261107 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.578 秒；进程树提交内存峰值：0.129105GiB。
- 结果与原因：joint_arc_flow: infeasible, infeasible, infeasible; 停止原因=3。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-012/result.json)；SHA256 `f9d6fc8f1c165286b45050c3e11a66167140069f2814d7e5550391928d6d7d0e`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.407658 |
| joint_arc_flow/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.401424 |
| joint_arc_flow/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.465902 |

#### `08-xma-arc-013` · Stress / joint_arc_flow / fixed target=100 / grid60 max120

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/270 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：7.485 秒；进程树提交内存峰值：0.13987GiB。
- 结果与原因：joint_arc_flow: optimal; objective=56897.62037037037; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-013/result.json)；SHA256 `acf4ec3ad483acca1ea1c5f3fad24cb00d8c432366175f037eb0a8a944ec5c90`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.77147 |

#### `08-xma-arc-014` · Stress / joint_arc_flow / fixed target=500 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：3600/3570 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：3580.33 秒；进程树提交内存峰值：2.28376GiB。
- 结果与原因：joint_arc_flow: not_converged; objective=None; 停止原因=9。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-014/result.json)；SHA256 `c4ad5e3479729cba2219fdfd0c7c09dc5ae2f42eff0fe7805a55d6098eb8be7f`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | not_converged | 缺失 | 197641 | 缺失 | 缺失 | 3573.91 |

#### `08-xma-arc-015` · Stress / joint_arc_flow / fixed target=2364 / grid60 max120

- 执行状态：`resource_limited`；结论：**资源受限**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：123.188 秒；进程树提交内存峰值：4.00337GiB。
- 结果与原因：worker exited without a complete result; 进程树提交内存上限 4GiB；具体触发项见 reason/worker.log。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-015/result.json)；SHA256 `7fcff0b1a7079595e7480f6c08611e52e0b056dfdeef5c69f1fc71bcabb39693`。

#### `08-xma-arc-016` · Stress / joint_arc_flow / fixed target=100 / grid30 max1440

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：900/870 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：265.75 秒；进程树提交内存峰值：0.896774GiB。
- 结果与原因：joint_arc_flow: optimal; objective=42473.56481481481; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-016/result.json)；SHA256 `1037c701f7d55b214cae5bf0feef141985001bd48d8354b5f66adacd59f51562`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| joint_arc_flow/0 | optimal | 42473.6 | 42473.6 | 42473.6 | True | 259.515 |

#### `08-xma-arc-017` · Stress / joint_arc_flow / fixed target=500 / grid30 max1440

- 执行状态：`resource_limited`；结论：**资源受限**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：104.828 秒；进程树提交内存峰值：4.01888GiB。
- 结果与原因：resource_limited: MemoryError: ; 进程树提交内存上限 4GiB；具体触发项见 reason/worker.log。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-017/result.json)；SHA256 `eff27f1b9aa12ec6cd11efb4ee5046486ed744cbf1d7052f5377525952556942`。

#### `08-xma-arc-018` · Full 2364 fine grid: candidate readiness and size gate

- 执行状态：`input_limit`；结论：**候选或输入规模门槛**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/60 秒；提交内存上限：2.5GiB。
- 参数：`{"size":2364,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow","precheck_only":true,"max_assignments":100000}`。
- 观测墙钟：75.062 秒；进程树提交内存峰值：0.438389GiB。
- 结果与原因：Candidate/assignment readiness only; optimization not run; 输入门槛=assignment network has 6055567 tail-option pairs, exceeds configured limit 100000; increase delay_step_minutes, lower maximum_delay_minutes, or explicitly raise max_assignment_options。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/08-xma-arc-018/result.json)；SHA256 `457f0ac80c14ac7646f4cbba3cb6ba2aeb856560d34643553cd379384e8f8cc6`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| xma_scale/ | not_run | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

### 09 XMA - Benders joint

#### `09-xma-benders-001` · Timing / fixed target=20 seed=None / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：375.344 秒；进程树提交内存峰值：0.128727GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-001/result.json)；SHA256 `517df0aa9a974b4c3db2887a088bf51b4aa735462334568a38390b424a7eef87`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 6900 | 缺失 | 缺失 | 90.5696 |
| benders_joint/1 | not_converged | 缺失 | 6900 | 缺失 | 缺失 | 90.4799 |
| benders_joint/2 | not_converged | 缺失 | 6900 | 缺失 | 缺失 | 90.5009 |

#### `09-xma-benders-002` · Timing / fixed target=20 seed=None / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：377.625 秒；进程树提交内存峰值：0.129894GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-002/result.json)；SHA256 `d13a863cc319f0f1da6586f02175481cd0c5ae5b432e1e41b9e559c866f2162f`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 100180 | 缺失 | 缺失 | 90.5625 |
| benders_joint/1 | not_converged | 缺失 | 100180 | 缺失 | 缺失 | 90.7211 |
| benders_joint/2 | not_converged | 缺失 | 100180 | 缺失 | 缺失 | 90.6217 |

#### `09-xma-benders-003` · Timing / fixed target=100 seed=None / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：377.094 秒；进程树提交内存峰值：0.132675GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-003/result.json)；SHA256 `2d18c6c077d163df09c6286053403d95415d7330ad0687a5e433366285e8a569`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 24800 | 缺失 | 缺失 | 90.9824 |
| benders_joint/1 | not_converged | 缺失 | 24800 | 缺失 | 缺失 | 90.6915 |
| benders_joint/2 | not_converged | 缺失 | 24800 | 缺失 | 缺失 | 90.6258 |

#### `09-xma-benders-004` · Timing / fixed target=100 seed=None / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：376.75 秒；进程树提交内存峰值：0.132591GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal, time_limit_or_cancel。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-004/result.json)；SHA256 `4da4f98798fed7e22b316907d9663e83521596161fe9afa3885de2fe6fcda78c`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 450110 | 缺失 | 缺失 | 90.9259 |
| benders_joint/1 | not_converged | 缺失 | 450110 | 缺失 | 缺失 | 90.5699 |
| benders_joint/2 | not_converged | 缺失 | 450110 | 缺失 | 缺失 | 90.6071 |

#### `09-xma-benders-005` · Timing / random target=20 seed=20261106 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：378.14 秒；进程树提交内存峰值：0.128998GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-005/result.json)；SHA256 `8e794a397c24ee5eed5da5c1b368e4b32b13eb930ae1b18e673fff3c52e88ab0`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 4091.67 | 缺失 | 缺失 | 90.5358 |
| benders_joint/1 | not_converged | 缺失 | 4091.67 | 缺失 | 缺失 | 90.526 |
| benders_joint/2 | not_converged | 缺失 | 4091.67 | 缺失 | 缺失 | 90.5418 |

#### `09-xma-benders-006` · Timing / random target=20 seed=20261106 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：375.281 秒；进程树提交内存峰值：0.128666GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-006/result.json)；SHA256 `52d63739a2c8effcf30a2b827867770943f78cbcb53cd73f6d81d7c4e30cd4d7`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 75295 | 缺失 | 缺失 | 90.5727 |
| benders_joint/1 | not_converged | 缺失 | 75295 | 缺失 | 缺失 | 90.5524 |
| benders_joint/2 | not_converged | 缺失 | 75295 | 缺失 | 缺失 | 90.5449 |

#### `09-xma-benders-007` · Timing / random target=20 seed=20261107 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：375.031 秒；进程树提交内存峰值：0.128838GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal, time_limit_or_cancel。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-007/result.json)；SHA256 `2ac0c75ab44fe95407837fd7903a84ec3f6b7e57f5a173bad251240a1df7c110`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 11266.7 | 缺失 | 缺失 | 90.5473 |
| benders_joint/1 | not_converged | 缺失 | 11266.7 | 缺失 | 缺失 | 90.494 |
| benders_joint/2 | not_converged | 缺失 | 11266.7 | 缺失 | 缺失 | 90.4796 |

#### `09-xma-benders-008` · Timing / random target=20 seed=20261107 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：375.516 秒；进程树提交内存峰值：0.128361GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-008/result.json)；SHA256 `c971780d9a4f75b357e78b4c76fb554ea97f9bd2b9d7a901f28486e5d89dc2cc`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 200265 | 缺失 | 缺失 | 90.5628 |
| benders_joint/1 | not_converged | 缺失 | 200265 | 缺失 | 缺失 | 90.5469 |
| benders_joint/2 | not_converged | 缺失 | 200265 | 缺失 | 缺失 | 90.5821 |

#### `09-xma-benders-009` · Timing / random target=100 seed=20261106 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：368.187 秒；进程树提交内存峰值：0.133209GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-009/result.json)；SHA256 `3dc81fe2935a7dfac4428ebb937aedc6fb1f498a0febe932883fa8460c03da75`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 22600 | 缺失 | 缺失 | 90.2407 |
| benders_joint/1 | not_converged | 缺失 | 22600 | 缺失 | 缺失 | 90.2087 |
| benders_joint/2 | not_converged | 缺失 | 22600 | 缺失 | 缺失 | 90.2039 |

#### `09-xma-benders-010` · Timing / random target=100 seed=20261106 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：368.296 秒；进程树提交内存峰值：0.135975GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, master_not_optimal, time_limit_or_cancel。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-010/result.json)；SHA256 `d9fdda1f9d6b6378097b541cc65afa56d5a55c703184dadecf0a49cab1e9a16d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 400540 | 缺失 | 缺失 | 90.2354 |
| benders_joint/1 | not_converged | 缺失 | 400540 | 缺失 | 缺失 | 90.272 |
| benders_joint/2 | not_converged | 缺失 | 400540 | 缺失 | 缺失 | 90.2756 |

#### `09-xma-benders-011` · Timing / random target=100 seed=20261107 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：368.547 秒；进程树提交内存峰值：0.135124GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=master_not_optimal, time_limit_or_cancel。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-011/result.json)；SHA256 `265cbc3b7d7852ab774923ce693ebc7397237e113c8bb0c5a9fb395ac62ace00`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 28858.3 | 缺失 | 缺失 | 90.2552 |
| benders_joint/1 | not_converged | 缺失 | 28858.3 | 缺失 | 缺失 | 90.2587 |
| benders_joint/2 | not_converged | 缺失 | 28858.3 | 缺失 | 缺失 | 90.2107 |

#### `09-xma-benders-012` · Timing / random target=100 seed=20261107 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：368.328 秒；进程树提交内存峰值：0.132935GiB。
- 结果与原因：benders_joint: not_converged, not_converged, not_converged; 停止原因=budget_exhausted_during_build, time_limit_or_cancel。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-012/result.json)；SHA256 `ff30fe4d4a7775573a18960efb3e4bc55348a2dc8911ad1a842e429f1fcef532`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 500390 | 缺失 | 缺失 | 90.2398 |
| benders_joint/1 | not_converged | 缺失 | 500390 | 缺失 | 缺失 | 90.308 |
| benders_joint/2 | not_converged | 缺失 | 500390 | 缺失 | 缺失 | 90.2371 |

#### `09-xma-benders-013` · Stress / benders_joint / fixed target=100 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/270 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}`。
- 观测墙钟：105.218 秒；进程树提交内存峰值：0.129047GiB。
- 结果与原因：benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-013/result.json)；SHA256 `adc075cfbd0e45222daeb20b2e23653c02dcc516ab7ccecea3796c5bc5bc309d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 24800 | 缺失 | 缺失 | 100.101 |

#### `09-xma-benders-014` · Stress / benders_joint / fixed target=500 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：3600/3570 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}`。
- 观测墙钟：1225.27 秒；进程树提交内存峰值：0.215576GiB。
- 结果与原因：benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-014/result.json)；SHA256 `08a225910ae3fc46e70ac10a2d5622811d792256a196996b474bf95942a9fa38`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 121629 | 缺失 | 缺失 | 1220.13 |

#### `09-xma-benders-015` · Stress / benders_joint / fixed target=2364 / grid60 max120

- 执行状态：`passed`；结论：**求解器认证不可行**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}`。
- 观测墙钟：14.89 秒；进程树提交内存峰值：0.141026GiB。
- 结果与原因：benders_joint: infeasible; objective=None; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-015/result.json)；SHA256 `e88d5adcf1f5cfbac5531f3fcf54d15b1d598fe31a64136ee5be35a1a7395207`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 5.23426 |

#### `09-xma-benders-016` · Stress / benders_joint / fixed target=100 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：900/870 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_joint"}`。
- 观测墙钟：655.453 秒；进程树提交内存峰值：0.193146GiB。
- 结果与原因：benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-016/result.json)；SHA256 `99b2e977a82045f8216259aa3da3dd48b4ae95e16c1154f1247b05582d6ef720`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 18862.5 | 缺失 | 缺失 | 648.666 |

#### `09-xma-benders-017` · Stress / benders_joint / fixed target=500 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_joint"}`。
- 观测墙钟：1717.27 秒；进程树提交内存峰值：0.265678GiB。
- 结果与原因：benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/09-xma-benders-017/result.json)；SHA256 `0323647887a117f8bcaa4279a76ba1a59274c0a3e34fcd7967e9e4ca7e752a75`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_joint/0 | not_converged | 缺失 | 91004.2 | 缺失 | 缺失 | 1707.79 |

### 10 XMA - Benders CG BP

#### `10-xma-cg-bp-001` · Timing / fixed target=20 seed=None / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：376.922 秒；进程树提交内存峰值：0.129532GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-001/result.json)；SHA256 `971a1f438d7f544e5a3bb58a39a6720d10a672d3b98172399e60a02ba676c54f`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 6900 | 缺失 | 缺失 | 90.6008 |
| benders_cg_bp/1 | not_converged | 缺失 | 6900 | 缺失 | 缺失 | 90.5602 |
| benders_cg_bp/2 | not_converged | 缺失 | 6900 | 缺失 | 缺失 | 90.5013 |

#### `10-xma-cg-bp-002` · Timing / fixed target=20 seed=None / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：375.891 秒；进程树提交内存峰值：0.129917GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-002/result.json)；SHA256 `3aec9caa0436e827bfc541ebab8875d17936786dd786d9ce56460a2dbeb95065`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 100180 | 缺失 | 缺失 | 90.5707 |
| benders_cg_bp/1 | not_converged | 缺失 | 100180 | 缺失 | 缺失 | 90.5497 |
| benders_cg_bp/2 | not_converged | 缺失 | 100180 | 缺失 | 缺失 | 90.547 |

#### `10-xma-cg-bp-003` · Timing / fixed target=100 seed=None / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：377.219 秒；进程树提交内存峰值：0.1376GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-003/result.json)；SHA256 `87c347d59ec5f0f1e931d60943933653f42baed78e1a98b371ccfd02f24a692f`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 24700 | 缺失 | 缺失 | 90.711 |
| benders_cg_bp/1 | not_converged | 缺失 | 24700 | 缺失 | 缺失 | 90.825 |
| benders_cg_bp/2 | not_converged | 缺失 | 24700 | 缺失 | 缺失 | 90.9872 |

#### `10-xma-cg-bp-005` · Timing / random target=20 seed=20261106 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：374.969 秒；进程树提交内存峰值：0.129406GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-005/result.json)；SHA256 `b77d87ead2594f2fae926936cca42de8a34b231d07120b121b4f52ca30e55987`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 4091.67 | 缺失 | 缺失 | 90.4863 |
| benders_cg_bp/1 | not_converged | 缺失 | 4091.67 | 缺失 | 缺失 | 90.5202 |
| benders_cg_bp/2 | not_converged | 缺失 | 4091.67 | 缺失 | 缺失 | 90.462 |

#### `10-xma-cg-bp-006` · Timing / random target=20 seed=20261106 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：375.86 秒；进程树提交内存峰值：0.129547GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-006/result.json)；SHA256 `8b5f0d375dd4c049f8542632544c08283d604548818ba3ae1a36068a43471f16`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 75295 | 缺失 | 缺失 | 90.5317 |
| benders_cg_bp/1 | not_converged | 缺失 | 75295 | 缺失 | 缺失 | 90.5088 |
| benders_cg_bp/2 | not_converged | 缺失 | 75295 | 缺失 | 缺失 | 90.5117 |

#### `10-xma-cg-bp-007` · Timing / random target=20 seed=20261107 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：375.828 秒；进程树提交内存峰值：0.128868GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-007/result.json)；SHA256 `81250f3513a435a20b695c52332c4f0cce70a7a9d180219467f5c7aff8587271`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 11266.7 | 缺失 | 缺失 | 90.6759 |
| benders_cg_bp/1 | not_converged | 缺失 | 11266.7 | 缺失 | 缺失 | 90.5138 |
| benders_cg_bp/2 | not_converged | 缺失 | 11266.7 | 缺失 | 缺失 | 90.5089 |

#### `10-xma-cg-bp-008` · Timing / random target=20 seed=20261107 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：376.422 秒；进程树提交内存峰值：0.12846GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-008/result.json)；SHA256 `009a3095e5ba6c595720e63e8874a5e84cc895ef819a4ac7892fc4eaf7802f70`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 200250 | 缺失 | 缺失 | 90.755 |
| benders_cg_bp/1 | not_converged | 缺失 | 200250 | 缺失 | 缺失 | 90.5772 |
| benders_cg_bp/2 | not_converged | 缺失 | 200250 | 缺失 | 缺失 | 90.5326 |

#### `10-xma-cg-bp-004` · Timing / fixed target=100 seed=None / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：368.937 秒；进程树提交内存峰值：0.138325GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-004/result.json)；SHA256 `22cc9ce8d727e6dd0061343c2261577eab0be9289db4e1e1ea1844e17b827508`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 450060 | 缺失 | 缺失 | 90.3221 |
| benders_cg_bp/1 | not_converged | 缺失 | 450060 | 缺失 | 缺失 | 90.3105 |
| benders_cg_bp/2 | not_converged | 缺失 | 450060 | 缺失 | 缺失 | 90.2209 |

#### `10-xma-cg-bp-009` · Timing / random target=100 seed=20261106 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：368.656 秒；进程树提交内存峰值：0.139175GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-009/result.json)；SHA256 `c78ce2f8feb970133d53bb915c2db28a89eaced89c2b3931419fa181a352f83c`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 22500 | 缺失 | 缺失 | 90.465 |
| benders_cg_bp/1 | not_converged | 缺失 | 22500 | 缺失 | 缺失 | 90.3129 |
| benders_cg_bp/2 | not_converged | 缺失 | 22500 | 缺失 | 缺失 | 90.3151 |

#### `10-xma-cg-bp-010` · Timing / random target=100 seed=20261106 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：368.484 秒；进程树提交内存峰值：0.143772GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit, time_limit_or_cancel。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-010/result.json)；SHA256 `48f44fd805cee5579bd3ca2861b9831aae80ec06be044a47a8a9bdf277f7af86`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 400480 | 缺失 | 缺失 | 90.2212 |
| benders_cg_bp/1 | not_converged | 缺失 | 400480 | 缺失 | 缺失 | 90.274 |
| benders_cg_bp/2 | not_converged | 缺失 | 400480 | 缺失 | 缺失 | 90.2313 |

#### `10-xma-cg-bp-011` · Timing / random target=100 seed=20261107 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：368.546 秒；进程树提交内存峰值：0.137905GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-011/result.json)；SHA256 `9e6d7bd0f612105bcb9b6e73a9f75dcdd85f246b70a698b4af507fbb3a184aad`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 28766.7 | 缺失 | 缺失 | 90.3178 |
| benders_cg_bp/1 | not_converged | 缺失 | 28766.7 | 缺失 | 缺失 | 90.3299 |
| benders_cg_bp/2 | not_converged | 缺失 | 28775 | 缺失 | 缺失 | 90.2526 |

#### `10-xma-cg-bp-012` · Timing / random target=100 seed=20261107 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**未收敛，缺少经审计的全局可行解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：367.844 秒；进程树提交内存峰值：0.137936GiB。
- 结果与原因：benders_cg_bp: not_converged, not_converged, not_converged; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-012/result.json)；SHA256 `2638897ea523987d7be3ce5ff14bfe142946da186ec2c8adad9dbb8e4e444af0`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 500330 | 缺失 | 缺失 | 90.2934 |
| benders_cg_bp/1 | not_converged | 缺失 | 500330 | 缺失 | 缺失 | 90.2752 |
| benders_cg_bp/2 | not_converged | 缺失 | 500330 | 缺失 | 缺失 | 90.298 |

#### `10-xma-cg-bp-013` · Stress / benders_cg_bp / fixed target=100 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/270 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：276.016 秒；进程树提交内存峰值：0.136925GiB。
- 结果与原因：benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-013/result.json)；SHA256 `3e979f6396f33149855fc024f8e4d270f9d01b7976ec1916d7f9ff27ff50a004`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 24783.3 | 缺失 | 缺失 | 270.308 |

#### `10-xma-cg-bp-014` · Stress / benders_cg_bp / fixed target=500 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：3600/3570 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：3576.34 秒；进程树提交内存峰值：0.267113GiB。
- 结果与原因：benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-014/result.json)；SHA256 `0e21022058fb0d6dd01dbae2919399a78841e4c6452f3047046c84d32f809d10`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 121533 | 缺失 | 缺失 | 3571.38 |

#### `10-xma-cg-bp-015` · Stress / benders_cg_bp / fixed target=2364 / grid60 max120

- 执行状态：`passed`；结论：**求解器认证不可行**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：14.86 秒；进程树提交内存峰值：0.142525GiB。
- 结果与原因：benders_cg_bp: infeasible; objective=None; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-015/result.json)；SHA256 `45092abf15ef52ce3964cacd9f77d3c92eb7f405f6d6a65b0e958bdc3e0759ef`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 5.03627 |

#### `10-xma-cg-bp-016` · Stress / benders_cg_bp / fixed target=100 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：900/870 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：875.688 秒；进程树提交内存峰值：0.176941GiB。
- 结果与原因：benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-016/result.json)；SHA256 `d59da82c7cd3f1eddceacf7c90ea431c58724abc861072a6d324c1291f693eb6`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 18854.2 | 缺失 | 缺失 | 870.485 |

#### `10-xma-cg-bp-017` · Stress / benders_cg_bp / fixed target=500 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：7184.98 秒；进程树提交内存峰值：0.297344GiB。
- 结果与原因：benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/10-xma-cg-bp-017/result.json)；SHA256 `4777e4cffafae4422f57c1d8db9185169b9e121fba655dbc9a5c0acc8881e84b`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 91004.2 | 缺失 | 缺失 | 7175.66 |

### 11 AIR - P1 P2 P3 P4 P5 stress

#### `11-air-stress-001` · P1-seconds

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：60/50 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P1-seconds.json"}`。
- 观测墙钟：3.25 秒；进程树提交内存峰值：0.0756226GiB。
- 结果与原因：optimal, LB=18080.0, UB=18080.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-001/result.json)；SHA256 `3bc7eafb4784fecaefdb37f04827e4beb235b3207a8648b20d05536fd3a82992`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | optimal | 18080 | 18080 | 18080 | True | 缺失 |

#### `11-air-stress-002` · P2-tens-seconds

- 执行状态：`timed_out`；结论：**硬时限终止**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：180/170 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P2-tens-seconds.json"}`。
- 观测墙钟：180.438 秒；进程树提交内存峰值：0.0561562GiB。
- 结果与原因：strict wall limit, including build and serialization; 进程树墙钟上限 180s，含构模和落盘。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-002/result.json)；SHA256 `d9aaa2725bd289cdb48e4d1c64cb0daa1695ab9481e996922d3ffd2bc82d0032`。
- 硬停时进度：阶段 `phase11`，全局 LB=120，UB=600，相对 Gap=0.8。进度中的界须与保存方案及独立审计分开判断，不单凭上界认定已有可复用的合法方案。

#### `11-air-stress-003` · P3-minutes

- 执行状态：`timed_out`；结论：**硬时限终止**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：600/590 秒；提交内存上限：2.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P3-minutes.json"}`。
- 观测墙钟：600.688 秒；进程树提交内存峰值：0.067276GiB。
- 结果与原因：strict wall limit, including build and serialization; 进程树墙钟上限 600s，含构模和落盘。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-003/result.json)；SHA256 `1c0d64a91e70fe08cfd02f2df67142e13ea4484207a987456492be671a951262`。
- 硬停时进度：阶段 `phase11`，全局 LB=120，UB=23790，相对 Gap=0.994956。进度中的界须与保存方案及独立审计分开判断，不单凭上界认定已有可复用的合法方案。

#### `11-air-stress-004` · P4-tens-minutes

- 执行状态：`timed_out`；结论：**硬时限终止**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：1800/1790 秒；提交内存上限：4GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P4-tens-minutes.json"}`。
- 观测墙钟：1800.72 秒；进程树提交内存峰值：0.0892982GiB。
- 结果与原因：strict wall limit, including build and serialization; 进程树墙钟上限 1800s，含构模和落盘。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-004/result.json)；SHA256 `4f6b0f26b3175c061311e3553d716ab553ff6bf9f9a3561e4f7ae69198256e7c`。
- 硬停时进度：阶段 `phase11`，全局 LB=120，UB=66860，相对 Gap=0.998205。进度中的界须与保存方案及独立审计分开判断，不单凭上界认定已有可复用的合法方案。

#### `11-air-stress-005` · P5-hours

- 执行状态：`license_limited`；结论：**许可证受限**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：7200/7190 秒；提交内存上限：4GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P5-hours.json"}`。
- 观测墙钟：2494.58 秒；进程树提交内存峰值：0.164551GiB。
- 结果与原因：Gurobi 10010 size limit; not an algorithm correctness failure; 停止原因=phase11_aborted。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_001154_continue/jobs/11-air-stress-005/result.json)；SHA256 `c9c427ed8c4c1c70d5a7ba33b0367ff05d4aea856b5d34b16a802eb7e28a5772`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 |
|---|---|---:|---:|---:|---|---:|
| benders_branch_and_price_v1/ | aborted | 缺失 | 270 | 缺失 | 缺失 | 缺失 |

## 7. 修复方向与复测要求

已观察到的真实样本问题优先由对应事件和停止原因定位，不按未收敛实例的 incumbent 大小判定单调性错误。
若 Benders 多次排除完整不可行计划却没有全局可行上界，应检查可行性割的泛化能力、资源松弛是否缺失，以及可行解初始化。该项是待验证的性能根因，不能凭日志将其认定为数学正确性错误。
AIR 压力任务也需检查完整计划条件割是否造成反复枚举，以及全局时限是否仅分配到单个子求解。保留硬停前的全局界，修复时争取在预算内正常返回可审计方案与未闭合状态。
修复须保留真正的列生成、整数分支与全局界证明，不将算法名称改为直接模型调用来获得表面通过。新增割应以小规模穷举或 Oracle 检查对所有可行计划有效。
修复后执行相关单元/API/回归、小例子四算法双目标对拍、原先未收敛的同输入同预算复测，以及递增压力；保留旧结果、新结果、修复内容和仍受限项目。
许可证、依赖和机器内存的外部限制需单列；不能通过取消审计、放宽业务约束或将预检当作求解来消除失败。
