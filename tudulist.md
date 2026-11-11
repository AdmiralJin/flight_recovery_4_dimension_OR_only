# 项目待办清单

<!-- validation-watch:start -->
## 算法验证当前状态：已结束，证据已汇总

更新时间：2026-11-07T21:28:59+08:00；批次：`20261107_151057_repair`。
本轮状态：`{"passed": 140, "completed": 36, "license_limited": 1, "inconclusive": 7, "resource_limited": 1, "input_limit": 1}`；已保留历史证据 0 项。
按用户要求跳过系统空闲内存等待和低内存停测；并发最多 2 项，正式计时独占，单例硬时限与进程树内存上限有效。
实时状态：[watch_state.json](.workbench/validation_campaigns/20261107_151057_repair/watch_state.json)。
最终汇总：[20261107_212859_validation_campaign_finished.md](docs/codex_reports/20261107_212859_validation_campaign_finished.md)。
执行结束不等于全部证明最优；受限、未收敛与正确性失败分别列出。
<!-- validation-watch:end -->
更新时间：2026-11-06T21:47:55+08:00

## 算法验证：上轮停队记录（历史）

批次：`20261106_152943_continue`；原批次：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261106_110703`。
停队状态：**finished**；当前运行任务 0；未执行 34 项；本续测批次已执行 32 项。
实际状态：`{"passed": 9, "completed": 22, "resource_limited": 1, "cancelled": 34}`。
原冻结代码、数据及截止时间未变。STOP 表示主动停队，cancelled 且无 attempt 的条目属于未执行，不表示算法失败。
原批次保留 116 份既有证据；本轮状态只陈述执行情况，尚未给出完整科学复核结论。

### 上轮未执行清单（已纳入当前续测）

每项沿用本批次的单线程、独占计时或正确性并行设置。参数列保存完整 config（含种子与候选粒度）；算法及规模见名称。

| 任务 ID | 名称 / 算法 / 规模 | 参数与种子 | 时限 / 求解时限 / 内存 |
|---|---|---|---|
| `08-xma-arc-008` | Timing / random target=20 seed=20261107 / air_linear_v1 / joint_arc_flow | `{"mode":"random","size":20,"seed":20261107,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `10-xma-cg-bp-009` | Timing / random target=100 seed=20261106 / tianchi_2017 / benders_cg_bp | `{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `08-xma-arc-009` | Timing / random target=100 seed=20261106 / tianchi_2017 / joint_arc_flow | `{"mode":"random","size":100,"seed":20261106,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `09-xma-benders-009` | Timing / random target=100 seed=20261106 / tianchi_2017 / benders_joint | `{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `08-xma-arc-010` | Timing / random target=100 seed=20261106 / air_linear_v1 / joint_arc_flow | `{"mode":"random","size":100,"seed":20261106,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `09-xma-benders-010` | Timing / random target=100 seed=20261106 / air_linear_v1 / benders_joint | `{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `10-xma-cg-bp-010` | Timing / random target=100 seed=20261106 / air_linear_v1 / benders_cg_bp | `{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `09-xma-benders-011` | Timing / random target=100 seed=20261107 / tianchi_2017 / benders_joint | `{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `10-xma-cg-bp-011` | Timing / random target=100 seed=20261107 / tianchi_2017 / benders_cg_bp | `{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `08-xma-arc-011` | Timing / random target=100 seed=20261107 / tianchi_2017 / joint_arc_flow | `{"mode":"random","size":100,"seed":20261107,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `10-xma-cg-bp-012` | Timing / random target=100 seed=20261107 / air_linear_v1 / benders_cg_bp | `{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `08-xma-arc-012` | Timing / random target=100 seed=20261107 / air_linear_v1 / joint_arc_flow | `{"mode":"random","size":100,"seed":20261107,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `09-xma-benders-012` | Timing / random target=100 seed=20261107 / air_linear_v1 / benders_joint | `{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}` | 600s / 90s / 2.5GiB |
| `11-air-stress-001` | P1-seconds | `{"path":"data/validation_suite/frozen/stress/P1-seconds.json"}` | 60s / 50s / 1.5GiB |
| `11-air-stress-002` | P2-tens-seconds | `{"path":"data/validation_suite/frozen/stress/P2-tens-seconds.json"}` | 180s / 170s / 1.5GiB |
| `11-air-stress-003` | P3-minutes | `{"path":"data/validation_suite/frozen/stress/P3-minutes.json"}` | 600s / 590s / 2.5GiB |
| `11-air-stress-004` | P4-tens-minutes | `{"path":"data/validation_suite/frozen/stress/P4-tens-minutes.json"}` | 1800s / 1790s / 4GiB |
| `11-air-stress-005` | P5-hours | `{"path":"data/validation_suite/frozen/stress/P5-hours.json"}` | 7200s / 7190s / 4GiB |
| `08-xma-arc-013` | Stress / joint_arc_flow / fixed target=100 / grid60 max120 | `{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}` | 300s / 270s / 2.5GiB |
| `09-xma-benders-013` | Stress / benders_joint / fixed target=100 / grid60 max120 | `{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}` | 300s / 270s / 2.5GiB |
| `10-xma-cg-bp-013` | Stress / benders_cg_bp / fixed target=100 / grid60 max120 | `{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}` | 300s / 270s / 2.5GiB |
| `08-xma-arc-014` | Stress / joint_arc_flow / fixed target=500 / grid60 max120 | `{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}` | 3600s / 3570s / 4GiB |
| `09-xma-benders-014` | Stress / benders_joint / fixed target=500 / grid60 max120 | `{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}` | 3600s / 3570s / 4GiB |
| `10-xma-cg-bp-014` | Stress / benders_cg_bp / fixed target=500 / grid60 max120 | `{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}` | 3600s / 3570s / 4GiB |
| `08-xma-arc-015` | Stress / joint_arc_flow / fixed target=2364 / grid60 max120 | `{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}` | 7200s / 7170s / 4GiB |
| `09-xma-benders-015` | Stress / benders_joint / fixed target=2364 / grid60 max120 | `{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}` | 7200s / 7170s / 4GiB |
| `10-xma-cg-bp-015` | Stress / benders_cg_bp / fixed target=2364 / grid60 max120 | `{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}` | 7200s / 7170s / 4GiB |
| `08-xma-arc-016` | Stress / joint_arc_flow / fixed target=100 / grid30 max1440 | `{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow"}` | 900s / 870s / 2.5GiB |
| `09-xma-benders-016` | Stress / benders_joint / fixed target=100 / grid30 max1440 | `{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_joint"}` | 900s / 870s / 2.5GiB |
| `10-xma-cg-bp-016` | Stress / benders_cg_bp / fixed target=100 / grid30 max1440 | `{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_cg_bp"}` | 900s / 870s / 2.5GiB |
| `08-xma-arc-017` | Stress / joint_arc_flow / fixed target=500 / grid30 max1440 | `{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow"}` | 7200s / 7170s / 4GiB |
| `09-xma-benders-017` | Stress / benders_joint / fixed target=500 / grid30 max1440 | `{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_joint"}` | 7200s / 7170s / 4GiB |
| `10-xma-cg-bp-017` | Stress / benders_cg_bp / fixed target=500 / grid30 max1440 | `{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_cg_bp"}` | 7200s / 7170s / 4GiB |
| `08-xma-arc-018` | Full 2364 fine grid: candidate readiness and size gate | `{"size":2364,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow","precheck_only":true,"max_assignments":100000}` | 300s / 60s / 2.5GiB |

上轮恢复入口（历史记录；当前续测已启动，无需重复执行）：

```powershell
& "C:\Users\28635\anaconda3\python.exe" scripts/validation_campaign.py launch --continue-from "D:\python_project\flight_recovery\.workbench\validation_campaigns\20261106_152943_continue" --profile long
```

续测机制创建新批次，仅选未完成或受限项目，复用原冻结算法、数据及已通过结果。原批次 resume 保留原截止时间；超过原截止时间时不要用 resume 重新计时。

### 已执行、待复核

completed 仅表示测量完成；passed 表示该测试自身断言通过；资源受限、未收敛不属于未执行。最终可靠性结论仍需核查独立审计、上下界及参考解。

| 任务 ID | 名称 | 执行状态 | 证据 |
|---|---|---|---|
| `01-regression-005` | tests/api/test_workbench_v2_api.py | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/01-regression-005/result.json) |
| `01-regression-006` | tests/api/test_xma_api.py | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/01-regression-006/result.json) |
| `03-aircraft-cg-001` | aircraft: full LP vs CG / toy_case_011_aircraft_string_column_generation | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/03-aircraft-cg-001/result.json) |
| `03-aircraft-cg-002` | aircraft: full LP vs CG / phase1_benchmark_001 | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/03-aircraft-cg-002/result.json) |
| `04-crew-cg-001` | crew: full LP vs CG / toy_case_012_crew_pairing_column_generation | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/04-crew-cg-001/result.json) |
| `04-crew-cg-002` | crew: full LP vs CG / phase1_benchmark_001 | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/04-crew-cg-002/result.json) |
| `05-air-oracle-001` | Integrated vs Benders BP / benchmark-disruption-recovery | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/05-air-oracle-001/result.json) |
| `05-air-oracle-002` | Integrated vs Benders BP / crew-recovery-integrality | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/05-air-oracle-002/result.json) |
| `07-xma-oracle-011` | Official JAR fixture revalidation (existing runtime only) | `passed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/07-xma-oracle-011/result.json) |
| `08-xma-arc-001` | Timing / fixed target=20 seed=None / tianchi_2017 / joint_arc_flow | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-001/result.json) |
| `09-xma-benders-001` | Timing / fixed target=20 seed=None / tianchi_2017 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-001/result.json) |
| `10-xma-cg-bp-001` | Timing / fixed target=20 seed=None / tianchi_2017 / benders_cg_bp | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-001/result.json) |
| `09-xma-benders-002` | Timing / fixed target=20 seed=None / air_linear_v1 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-002/result.json) |
| `10-xma-cg-bp-002` | Timing / fixed target=20 seed=None / air_linear_v1 / benders_cg_bp | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-002/result.json) |
| `08-xma-arc-002` | Timing / fixed target=20 seed=None / air_linear_v1 / joint_arc_flow | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-002/result.json) |
| `10-xma-cg-bp-003` | Timing / fixed target=100 seed=None / tianchi_2017 / benders_cg_bp | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-003/result.json) |
| `08-xma-arc-003` | Timing / fixed target=100 seed=None / tianchi_2017 / joint_arc_flow | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-003/result.json) |
| `09-xma-benders-003` | Timing / fixed target=100 seed=None / tianchi_2017 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-003/result.json) |
| `08-xma-arc-004` | Timing / fixed target=100 seed=None / air_linear_v1 / joint_arc_flow | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-004/result.json) |
| `09-xma-benders-004` | Timing / fixed target=100 seed=None / air_linear_v1 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-004/result.json) |
| `10-xma-cg-bp-004` | Timing / fixed target=100 seed=None / air_linear_v1 / benders_cg_bp | `resource_limited` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-004/result.json) |
| `09-xma-benders-005` | Timing / random target=20 seed=20261106 / tianchi_2017 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-005/result.json) |
| `10-xma-cg-bp-005` | Timing / random target=20 seed=20261106 / tianchi_2017 / benders_cg_bp | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-005/result.json) |
| `08-xma-arc-005` | Timing / random target=20 seed=20261106 / tianchi_2017 / joint_arc_flow | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-005/result.json) |
| `10-xma-cg-bp-006` | Timing / random target=20 seed=20261106 / air_linear_v1 / benders_cg_bp | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-006/result.json) |
| `08-xma-arc-006` | Timing / random target=20 seed=20261106 / air_linear_v1 / joint_arc_flow | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-006/result.json) |
| `09-xma-benders-006` | Timing / random target=20 seed=20261106 / air_linear_v1 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-006/result.json) |
| `08-xma-arc-007` | Timing / random target=20 seed=20261107 / tianchi_2017 / joint_arc_flow | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/08-xma-arc-007/result.json) |
| `09-xma-benders-007` | Timing / random target=20 seed=20261107 / tianchi_2017 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-007/result.json) |
| `10-xma-cg-bp-007` | Timing / random target=20 seed=20261107 / tianchi_2017 / benders_cg_bp | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-007/result.json) |
| `09-xma-benders-008` | Timing / random target=20 seed=20261107 / air_linear_v1 / benders_joint | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/09-xma-benders-008/result.json) |
| `10-xma-cg-bp-008` | Timing / random target=20 seed=20261107 / air_linear_v1 / benders_cg_bp | `completed` | [result.json](.workbench/validation_campaigns/20261106_152943_continue/jobs/10-xma-cg-bp-008/result.json) |

## 当前开发任务

当前阶段：**任务1与任务2均已完成；算法验证按用户要求恢复**。

- [x] 刷新长测状态；当前任务结束后停止派发；保存结果和未执行清单。
- [x] 任务1：新建独立 Workbench v3，保留 v2 与后端；完成三个工作区及保存、校验、运行、分析闭环。
- [x] 任务1验收：AIR/厦航、异常与并发、事件恢复、浅深色及 1440/1024/390、隔离和 v2 兼容。
- [x] 任务2：任务1验收后，核验并固定安装 UI/UX Pro Max，优化共享组件与设计变量。
- [x] 任务2验收：保留前后截图、改进记录并完成相关回归（20 项模拟浏览器、3 项真实接口浏览器场景）。
- [x] 用户已安排恢复算法验证：启动剩余任务，最多 2 项并发，不等待系统空闲资源。
- [x] 算法验证：本轮调度结束并生成证据汇总；受限或未收敛问题见报告，不能视为全部通过。

## 当前持续目标：全部测试 → 详细报告 → 修复算法 → 复测通过

- [ ] 跑完跨批次的全部 182 个去重测试任务；保持最多 2 项计算并行，正式性能计时独占，不等待系统空闲内存。
- [x] 补齐逐任务详细报告工具 `scripts/validation_report.py`，覆盖参数、时限、目标、全局界、审计、停止原因与证据链接。
- [x] 启动详细报告等待进程；本轮终止后自动生成 `docs/codex_reports/*_algorithm_validation_detailed_baseline.md`，路径保存于本批 `detailed_report.json`。
- [ ] 基线全部结束后，复核详细报告，区分断言失败、未收敛、资源/许可证限制和未执行。
- [ ] 基于完整基线修复算法；优先检查厦航 Benders/CG/B&P 的不可行计划排除、割强度和全局可行解获取。
- [ ] 同时核查和修复 AIR 压力收敛及整条算法的统一时限，保留硬停前的全局界与可审计方案。
- [ ] 核查 500 班 CG/B&P 的 LP 重复求解成本：基线约 3545 秒求解、339 次 CG 迭代、仅检查 3 个计划；验证持久 LP、列池及基复用，不替代有效的可行性割和整数证明。
- [ ] 修复厦航求解矩阵转换的中间内存开销：500 班细档在 solver.py::_problem 追加 ri/ci/values 时触及 4GiB；验证批量稀疏提取与原模型系数、边界、常数项一致。
- [x] 补充真实 103 班的候选扩充合理性核查：数据和成本相同，276 个粗档候选包含于 2844 个细档候选，两者均证明最优，目标由 56897.62037 降至 42473.56481；证据见本批 real_candidate_expansion_audit.json。
- [ ] 新割和分支逻辑通过小例子 Oracle/枚举有效性检查，完成相关 unit、API、regression 回归。
- [ ] 使用相同输入、目标、候选空间和预算复测原先未收敛或失败的实例，再做递增规模压力；记录改善及仍受限项目。
- [ ] 保存详细修复与最终复测报告；完整证据满足目标前不标记目标完成。


## 2026-11-07 Algorithm repair and full replay

- [x] Implement evidence, cumulative budget, audited checkpoints, sparse conversion, persistent LP and stronger decomposition masters.
- [x] Complete 541 unit/API/regression tests; all passed.
- [x] Launch full repair replay: `.workbench/validation_campaigns/20261107_151057_repair` (186 jobs, no inherited passes, max 2 parallel, exclusive performance).
- [ ] Review this repair batch after completion: all 12 real-data comparison groups; AIR P1-P5; XMA 508/2364 memory and termination; old/new objective certificates.
- [ ] Keep license/resource/input-size limits separate; do not resume the old frozen continuation as a repair test.

Report: [repairs and replay](docs/codex_reports/20261107_151248_algorithm_validation_repairs_and_replay.md).
