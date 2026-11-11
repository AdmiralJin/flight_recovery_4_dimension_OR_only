# 算法修复完整复测报告

生成时间：2026-11-07T21:29:15+08:00。

最终续测批次：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261107_151057_repair`；包含跨批次去重后的 186 个任务。
修复基线：`D:\python_project\flight_recovery\.workbench\validation_campaigns\20261107_001154_continue`；全部原任务重新执行，未继承任何旧通过结果。

## 1. 完成情况与判定口径

任务执行状态：`{"passed": 140, "completed": 36, "license_limited": 1, "inconclusive": 7, "resource_limited": 1, "input_limit": 1}`。
pytest 文件任务 93 项；底层测试报告计数 `{"passed": 521}`，另有跳过 0 项。任务数与底层断言数分开统计。
`passed` 表示本测试断言通过；`completed` 只表示测量完成。最优性另外核查独立审计、目标、上下界及参考断言，不能将三次未收敛当作三次最优。
AIR 与厦航、Tianchi 与 AIR 目标、LP 与整数最优、固定候选与动态候选分别判断；相同最优目标允许不同资源串 ID。

| 科学或执行结论 | 任务数 |
|---|---:|
| LP 最优及定价终止审计通过 | 4 |
| 候选或输入规模门槛 | 1 |
| 变形关系断言通过，各问题最优性分别认证 | 1 |
| 审计、目标与上下界闭合的最优解 | 62 |
| 未得到确定结论 | 7 |
| 求解器认证不可行 | 9 |
| 测试断言通过 | 95 |
| 联合 Oracle 与 Benders/B&P 最优一致 | 2 |
| 许可证受限 | 1 |
| 资源受限 | 1 |
| 输入合同或预检完成，未运行优化 | 2 |
| 返回不可行，认证与边界见原始结果 | 1 |

## 2. 来源、配置和测试公平性

- 已核验本批 470 个冻结文件、不可变任务清单及 0 份继承结果 SHA256。
- 原批次中被替代的失败尝试继续保留；本报告按任务 ID 使用最近一次有效执行证据，不将旧失败与修复后的通过重复计数。
- 批次预算 24 小时，最大并发 2；性能任务独占、求解器单线程；当前资源等待策略 `False`。
- 重型单例最长 2 小时；轻/中/重进程树提交内存约 1.5/2.5/4GiB。原始预算以每项 manifest/job.json 为准。
- 厦航粗档步长/延误上限 60/120 分钟，细档 30/1440 分钟；随机种子 20261106、20261107。整条机尾选样的实际航班数可高于目标数。
- 性能加速比仅在同问题、三次均最优、审计通过且目标相等时计算。建模、候选、求解、审计和端到端时间见各记录，不把嵌套子问题界作为全局界。
- 显式路径 Oracle 只用于小例子。全量细档的预检是候选规模检查，不是一次大型优化成功。

## 3. 各路线覆盖和结果

| 路线 | 任务数 | 执行状态 |
|---|---:|---|
| 01 Regression - unit API regression | 93 | {'passed': 93} |
| 02 AIR - expected solutions | 17 | {'passed': 17} |
| 03 AIR - Aircraft column generation | 2 | {'passed': 2} |
| 04 AIR - Crew column generation | 2 | {'passed': 2} |
| 05 AIR - Benders BP vs integrated | 2 | {'passed': 2} |
| 06 Conflicts - cancellation and limits | 2 | {'passed': 2} |
| 07 XMA - four algorithms two objectives | 11 | {'passed': 11} |
| 08 XMA - joint arc flow | 18 | {'completed': 12, 'passed': 3, 'inconclusive': 1, 'resource_limited': 1, 'input_limit': 1} |
| 09 XMA - Benders joint | 17 | {'completed': 12, 'passed': 2, 'inconclusive': 3} |
| 10 XMA - Benders CG BP | 17 | {'completed': 12, 'passed': 2, 'inconclusive': 3} |
| 11 AIR - P1 P2 P3 P4 P5 stress | 5 | {'passed': 4, 'license_limited': 1} |

### 修复前后证据关联

逐项核验 182 份旧结果 SHA256 并关联本轮重跑；已认证最优目标不一致 0 项。
执行 completed 与优化未收敛仍分别记录；详细状态、目标冲突见本批 baseline_to_repair_comparisons.json。

## 4. 未通过、未收敛、受限及证据不足的项目

以下将执行失败与优化目标未实现分别列出；超时、许可证和内存限制不自动等价于算法数学错误。

| 任务 ID / 名称 | 执行状态 | 具体结论 | 原因 | 证据 |
|---|---|---|---|---|
| `11-air-stress-005` P5-hours | license_limited | 许可证受限 | Gurobi 10010 size limit; not an algorithm correctness failure; 停止原因=phase11_aborted | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/11-air-stress-005/result.json) |
| `08-xma-arc-014` Stress / joint_arc_flow / fixed target=500 / grid60 max120 | inconclusive | 未得到确定结论 | joint_arc_flow: not_converged; objective=None; 停止原因=11 | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-014/result.json) |
| `09-xma-benders-014` Stress / benders_joint / fixed target=500 / grid60 max120 | inconclusive | 未得到确定结论 | benders_joint: not_converged; objective=None; 停止原因=master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-014/result.json) |
| `10-xma-cg-bp-014` Stress / benders_cg_bp / fixed target=500 / grid60 max120 | inconclusive | 未得到确定结论 | benders_cg_bp: not_converged; objective=None; 停止原因=master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-014/result.json) |
| `09-xma-benders-016` Stress / benders_joint / fixed target=100 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_joint: not_converged; objective=42473.56481481481; 停止原因=master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-016/result.json) |
| `10-xma-cg-bp-016` Stress / benders_cg_bp / fixed target=100 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_cg_bp: not_converged; objective=42473.56481481481; 停止原因=master_not_optimal | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-016/result.json) |
| `08-xma-arc-017` Stress / joint_arc_flow / fixed target=500 / grid30 max1440 | resource_limited | 资源受限 | resource_limited: MemoryError: bad allocation; 进程树提交内存上限 4GiB；具体触发项见 reason/worker.log | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-017/result.json) |
| `09-xma-benders-017` Stress / benders_joint / fixed target=500 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-017/result.json) |
| `10-xma-cg-bp-017` Stress / benders_cg_bp / fixed target=500 / grid30 max1440 | inconclusive | 未得到确定结论 | benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-017/result.json) |
| `08-xma-arc-018` Full 2364 fine grid: candidate readiness and size gate | input_limit | 候选或输入规模门槛 | Candidate/assignment readiness only; optimization not run; 输入门槛=assignment network has 6055567 tail-option pairs, exceeds configured limit 100000; increase delay_step_minutes, lower maximum_delay_minutes, or explicitly raise max_assignment_options | [result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-018/result.json) |

## 5. 列生成、分解与耗时收益

### 5.1 AIR 全列 LP 与列生成

速度比定义为全列流程中位耗时 / CG 流程中位耗时；小于 1 表示本实例 CG 更慢。它与最优性审计是两项结论，不能用正确性通过替代性能提速。

| 任务 | 速度比 | 全列列数 | CG 列数 | 判定 |
|---|---:|---|---|---|
| aircraft: full LP vs CG / toy_case_011_aircraft_string_column_generation | 0.261778 | [4, 4, 4] | [4, 4, 4] | CG not faster on this instance |
| aircraft: full LP vs CG / phase1_benchmark_001 | 0.344656 | [77, 77, 77] | [15, 15, 15] | CG not faster on this instance |
| crew: full LP vs CG / toy_case_012_crew_pairing_column_generation | 0.191422 | [12, 12, 12] | [12, 12, 12] | CG not faster on this instance |
| crew: full LP vs CG / phase1_benchmark_001 | 0.321504 | [374, 374, 374] | [34, 34, 34] | CG not faster on this instance |

### 5.2 厦航真实样本逐组对照

每组比较键由固定输入、目标和候选空间生成；三种算法各有预热及三次正式测量。不同目标的费用不横向比较。

#### 问题键 `0506e3c5ac1d9c6cc494f1422b771b0954071167148eb343c6780463a468276a`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 31 | ['optimal', 'optimal', 'optimal'] | [5948.0, 5948.0, 5948.0] | 0.387568 | [0.33063069998752326, 0.3972483000252396] | 0.698789 |
| benders_cg_bp | 31 | ['optimal', 'optimal', 'optimal'] | [5948.0, 5948.0, 5948.0] | 0.477618 | [0.4731051999842748, 0.48484830011148006] | 0.56704 |
| joint_arc_flow | 31 | ['optimal', 'optimal', 'optimal'] | [5948.0, 5948.0, 5948.0] | 0.270828 | [0.26710450008977205, 0.27945170004386455] | 缺失 |
#### 问题键 `1a5cc92ed5cf676460b43f818a45116a24f9cb58a1a33578a1b9baeb6a87b79e`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 103 | ['optimal', 'optimal', 'optimal'] | [8437500.0, 8437500.0, 8437500.0] | 1.42057 | [1.3983431999804452, 1.4525517999427393] | 缺失 |
| benders_joint | 103 | ['optimal', 'optimal', 'optimal'] | [8437500.0, 8437500.0, 8437500.0] | 0.967788 | [0.9511781999608502, 0.9707597999367863] | 1.46785 |
| benders_cg_bp | 103 | ['optimal', 'optimal', 'optimal'] | [8437500.0, 8437500.0, 8437500.0] | 7.45988 | [7.415609200019389, 7.4838952999562025] | 0.190428 |
#### 问题键 `2473ec1f1dca3c4a8c9c13ef94ad4881c5c640cf67222d8e1d80a849767cc6cf`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 115 | ['optimal', 'optimal', 'optimal'] | [43465.68194444444, 43465.68194444444, 43465.68194444444] | 30.7041 | [30.493094700039364, 31.050245100050233] | 0.0449685 |
| joint_arc_flow | 115 | ['optimal', 'optimal', 'optimal'] | [43465.68194444444, 43465.68194444444, 43465.68194444444] | 1.38072 | [1.341179299983196, 1.3890557999256998] | 缺失 |
| benders_joint | 115 | ['optimal', 'optimal', 'optimal'] | [43465.68194444444, 43465.68194444444, 43465.68194444444] | 1.09371 | [1.0636256000725552, 1.110133400070481] | 1.26242 |
#### 问题键 `3557b8025195fa27cba5a64eea3cf5dc0ad6d4a7a19e1e34a01c808fc674289f`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 31 | ['optimal', 'optimal', 'optimal'] | [870000.0, 870000.0, 870000.0] | 0.2718 | [0.26326630008406937, 0.27350569993723184] | 1.0703 |
| joint_arc_flow | 31 | ['optimal', 'optimal', 'optimal'] | [870000.0, 870000.0, 870000.0] | 0.290907 | [0.2663602000102401, 0.3232332000043243] | 缺失 |
| benders_joint | 31 | ['optimal', 'optimal', 'optimal'] | [870000.0, 870000.0, 870000.0] | 0.268688 | [0.2558026999467984, 0.28884749999269843] | 1.08269 |
#### 问题键 `4008685379116815b876560fcd2b0ccf7fa873c7a246146d58b63bfe035b0a0a`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 30 | ['optimal', 'optimal', 'optimal'] | [1302500.0, 1302500.0, 1302500.0] | 0.313362 | [0.3094120000023395, 0.3403522999724373] | 0.932193 |
| benders_cg_bp | 30 | ['optimal', 'optimal', 'optimal'] | [1302500.0, 1302500.0, 1302500.0] | 0.359475 | [0.3545622000237927, 0.4093356999801472] | 0.812611 |
| joint_arc_flow | 30 | ['optimal', 'optimal', 'optimal'] | [1302500.0, 1302500.0, 1302500.0] | 0.292114 | [0.27914559992495924, 0.3412789999274537] | 缺失 |
#### 问题键 `73dc48c9e1063d30681a462e8a793621aa1c4189d775032ee52f82e4089fd896`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 115 | ['optimal', 'optimal', 'optimal'] | [6820000.0, 6820000.0, 6820000.0] | 1.10544 | [1.1045860999729484, 1.106312100077048] | 缺失 |
| benders_joint | 115 | ['optimal', 'optimal', 'optimal'] | [6820000.0, 6820000.0, 6820000.0] | 1.00933 | [1.00726109999232, 1.1180101999780163] | 1.09522 |
| benders_cg_bp | 115 | ['optimal', 'optimal', 'optimal'] | [6820000.0, 6820000.0, 6820000.0] | 3.79223 | [3.7556345000630245, 3.8768651999998838] | 0.291502 |
#### 问题键 `82165e69de8ad138eed6d22b3911bfae87786f83c198b5e815a3fa5533c1fa81`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 33 | ['optimal', 'optimal', 'optimal'] | [19745.61111111111, 19745.61111111111, 19745.61111111111] | 0.280689 | [0.266009800019674, 0.29801449994556606] | 缺失 |
| benders_joint | 33 | ['optimal', 'optimal', 'optimal'] | [19745.61111111111, 19745.61111111111, 19745.61111111111] | 0.297969 | [0.2956104000331834, 0.33247399993706495] | 0.942007 |
| benders_cg_bp | 33 | ['optimal', 'optimal', 'optimal'] | [19745.61111111111, 19745.61111111111, 19745.61111111111] | 0.671952 | [0.6643668999895453, 0.7115171999903396] | 0.417722 |
#### 问题键 `84aa1d955b851cf754a6c7c0a638dbee917596c7d23dee8d0d8e25743076f5d4`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 33 | ['optimal', 'optimal', 'optimal'] | [2925510.0, 2925510.0, 2925510.0] | 0.31876 | [0.3027453999966383, 0.32279030000790954] | 0.922117 |
| benders_cg_bp | 33 | ['optimal', 'optimal', 'optimal'] | [2925510.0, 2925510.0, 2925510.0] | 0.328186 | [0.32420109992381185, 0.34188439999707043] | 0.89563 |
| joint_arc_flow | 33 | ['optimal', 'optimal', 'optimal'] | [2925510.0, 2925510.0, 2925510.0] | 0.293933 | [0.2898345999419689, 0.29726759996265173] | 缺失 |
#### 问题键 `9ec12d6dca8170f462f46e83c9f42b8aa78d9d1b9fa21895431b35fa1000f340`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| joint_arc_flow | 30 | ['optimal', 'optimal', 'optimal'] | [11444.0, 11444.0, 11444.0] | 0.293155 | [0.27267750003375113, 0.3139905999414623] | 缺失 |
| benders_joint | 30 | ['optimal', 'optimal', 'optimal'] | [11444.0, 11444.0, 11444.0] | 0.312904 | [0.30097639991436154, 0.34580459992866963] | 0.936885 |
| benders_cg_bp | 30 | ['optimal', 'optimal', 'optimal'] | [11444.0, 11444.0, 11444.0] | 0.346357 | [0.33761279995087534, 0.3645301000215113] | 0.846396 |
#### 问题键 `b1a427124cc94bea5d403dcb2623b769ed989b9c596489ef943d507b008f1df8`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.372836 | [0.3652435999829322, 0.38399369991384447] | 缺失 |
| joint_arc_flow | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.344813 | [0.3425950000528246, 0.36323569994419813] | 缺失 |
| benders_joint | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.381564 | [0.3716658999910578, 0.3977975999005139] | 缺失 |
#### 问题键 `b1c11b70e239c7eb3285eb81e4b61df4a744cd1986a680baf4e1c6942d3ba159`

三算法均证明最优且目标一致：**是**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_cg_bp | 103 | ['optimal', 'optimal', 'optimal'] | [56897.62037037037, 56897.62037037037, 56897.62037037037] | 41.2552 | [41.21297749993391, 42.074691600049846] | 0.0385334 |
| joint_arc_flow | 103 | ['optimal', 'optimal', 'optimal'] | [56897.62037037037, 56897.62037037037, 56897.62037037037] | 1.58971 | [1.5587317000608891, 1.5953436000272632] | 缺失 |
| benders_joint | 103 | ['optimal', 'optimal', 'optimal'] | [56897.62037037037, 56897.62037037037, 56897.62037037037] | 1.62625 | [1.606971099972725, 1.6467188999522477] | 0.977531 |
#### 问题键 `e394648fb4daded9dadce4269318d92ea950660ff27a14b63de9f85aa6dc32d6`

三算法均证明最优且目标一致：**否**。

| 算法 | 实际航班 | 三次状态 | 三次目标 | 中位耗时/秒 | 范围/秒 | 合格加速比 |
|---|---:|---|---|---:|---|---:|
| benders_joint | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.38856 | [0.3737791000166908, 0.3893161000451073] | 缺失 |
| benders_cg_bp | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.38009 | [0.353975799982436, 0.3945950000779703] | 缺失 |
| joint_arc_flow | 106 | ['infeasible', 'infeasible', 'infeasible'] | [None, None, None] | 0.359771 | [0.3446676000021398, 0.3619982999516651] | 缺失 |

## 6. 全部任务逐项证据

以下每一项均保留名称、配置、预算、执行结论及原始证据。最优性表中的缺失值保持缺失，不按零处理。

### 01 Regression - unit API regression

#### `01-regression-001` · tests/api/test_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_api.py"]}`。
- 观测墙钟：5.516 秒；进程树提交内存峰值：0.104816GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-001/result.json)；SHA256 `fa533262b1b880186062f65b9069a4f6bc4b7155d59d852175eda5954ae3db1b`。

#### `01-regression-002` · tests/api/test_cases_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_cases_api.py"]}`。
- 观测墙钟：4.438 秒；进程树提交内存峰值：0.104153GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-002/result.json)；SHA256 `38b448d0792f820f609da62b2441fe1a62d32996aefe6b51009a6d665ac7648d`。

#### `01-regression-003` · tests/api/test_solve_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_solve_api.py"]}`。
- 观测墙钟：14.468 秒；进程树提交内存峰值：0.145725GiB。
- 结果与原因：pytest exit=0; {'passed': 8}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-003/result.json)；SHA256 `d749a2ed6eb58bd47544d95362dbe339bbc7d24e7b127ee69f3f18e90674d23e`。

#### `01-regression-004` · tests/api/test_workbench_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_workbench_api.py"]}`。
- 观测墙钟：4.422 秒；进程树提交内存峰值：0.103508GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-004/result.json)；SHA256 `39a944751f4bde7a91d8f71f1523543d2296fce08b3837f66cc2fda96390abb7`。

#### `01-regression-007` · tests/regression/test_aircraft_string_column_generation_regression.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_aircraft_string_column_generation_regression.py"]}`。
- 观测墙钟：2.234 秒；进程树提交内存峰值：0.0459862GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-007/result.json)；SHA256 `25aab3cb73b42592f60dc2e521d4d5f43726bd092e85e95328f1724dc07c8515`。

#### `01-regression-008` · tests/regression/test_phase10_crew_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase10_crew_column_generation.py"]}`。
- 观测墙钟：3.344 秒；进程树提交内存峰值：0.052021GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-008/result.json)；SHA256 `09f10cb8fd255b1d946409326a26ba6fa5875e1a9982edd362f159a3ed08a1f8`。

#### `01-regression-009` · tests/regression/test_phase11_benders_cg_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_benchmark.py"]}`。
- 观测墙钟：3.344 秒；进程树提交内存峰值：0.0567665GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-009/result.json)；SHA256 `cbb8c75d687bf5d53008e00276f7f4a9a10ac2f1ff4be6ffc08526cf7438d78d`。

#### `01-regression-010` · tests/regression/test_phase11_benders_cg_cut_validity.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_cut_validity.py"]}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0464363GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-010/result.json)；SHA256 `b62fd4a9e76f12f1d345dc523086f12383278563871ba377ffc3c023f6189d69`。

#### `01-regression-011` · tests/regression/test_phase11_benders_cg_integrality_boundary.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_integrality_boundary.py"]}`。
- 观测墙钟：2.218 秒；进程树提交内存峰值：0.046627GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-011/result.json)；SHA256 `6707bb11797ccc6fe70e7834ca98b29f809c138d2e5d5347b8dd6c8dce359636`。

#### `01-regression-012` · tests/regression/test_phase11_benders_cg_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase11_benders_cg_oracle.py"]}`。
- 观测墙钟：3.375 秒；进程树提交内存峰值：0.0472755GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-012/result.json)；SHA256 `89a0d97f372338e1fd89977b8cdf255271a174ed6c1a57bfbdfa7a833f5d0c92`。

#### `01-regression-013` · tests/regression/test_phase12_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_benchmark.py"]}`。
- 观测墙钟：2.218 秒；进程树提交内存峰值：0.0547981GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-013/result.json)；SHA256 `63c5e49a13608b1d42e432bf52f6c0969cd80cfff7a70d3d6d52ce559ca67e36`。

#### `01-regression-014` · tests/regression/test_phase12_benders_branch_and_price.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_benders_branch_and_price.py"]}`。
- 观测墙钟：8.828 秒；进程树提交内存峰值：0.0513954GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-014/result.json)；SHA256 `9ff034a9ec96fcc976a01458821b2778d99dd133b40e3d887ad57d53a2f1a645`。

#### `01-regression-015` · tests/regression/test_phase12_branching_oracles.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_branching_oracles.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.046833GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-015/result.json)；SHA256 `e185aba5017461b35947dc5c18dba7187d2d166efdf2eb923e301a0b8770692c`。

#### `01-regression-016` · tests/regression/test_phase12_crew_integrality.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase12_crew_integrality.py"]}`。
- 观测墙钟：3.235 秒；进程树提交内存峰值：0.0478859GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-016/result.json)；SHA256 `5efb22b12367571ccbf47af7465e5438d8db70b0e1d403dfffed3baac2732e7a`。

#### `01-regression-017` · tests/regression/test_phase1_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase1_benchmark_001.py"]}`。
- 观测墙钟：2.157 秒；进程树提交内存峰值：0.0419083GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-017/result.json)；SHA256 `00abd4b9b82211be5bec3caef5eed68499d16491e0c31f199b255a8d848973be`。

#### `01-regression-018` · tests/regression/test_phase1_validation_case.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase1_validation_case.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0409813GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-018/result.json)；SHA256 `ecd5f12bbec4df860635c8587cefaa022c7a74cfbf3bdadc88b84bd34e3e3ef2`。

#### `01-regression-019` · tests/regression/test_phase2_arm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_arm_benchmark_001.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0472755GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-019/result.json)；SHA256 `a1618477eb92ef1194c4047ca8b6feab295c8ed645b9fef90eee8f7128085e15`。

#### `01-regression-020` · tests/regression/test_phase2_crm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_crm_benchmark_001.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0475044GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-020/result.json)；SHA256 `14b340806640f7e74b22347b3f6f7deaf16dc46f20ccc0d0c53249e68b5b8ee6`。

#### `01-regression-021` · tests/regression/test_phase2_gurobi_integration_gate.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_gurobi_integration_gate.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0330658GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-021/result.json)；SHA256 `f23323cdaf8332eb82b3be92888ba5721c954956b066a549b51b5ccc1656fdae`。

#### `01-regression-022` · tests/regression/test_phase2_incidence_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_incidence_benchmark_001.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0446548GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-022/result.json)；SHA256 `6b2e01aa42bc29259dca6e4ecd03301861dff9724df3359824892d2b1f2c279e`。

#### `01-regression-023` · tests/regression/test_phase2_overall_manual_reference.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_overall_manual_reference.py"]}`。
- 观测墙钟：3.266 秒；进程树提交内存峰值：0.0477371GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-023/result.json)；SHA256 `d2c2699b858c8e40fa0467e1733db70ebbdb233595134901793ddeb864a0653c`。

#### `01-regression-024` · tests/regression/test_phase2_prm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_prm_benchmark_001.py"]}`。
- 观测墙钟：2.14 秒；进程树提交内存峰值：0.0474281GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-024/result.json)；SHA256 `0d93c74f68f0ab3b0583e8ecf75c2b25b24879d1f6bf6a76b5e64c8dd78595ef`。

#### `01-regression-025` · tests/regression/test_phase2_srm_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase2_srm_benchmark_001.py"]}`。
- 观测墙钟：2.157 秒；进程树提交内存峰值：0.0477066GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-025/result.json)；SHA256 `ef6d4658e8f2cfdfd844a231788c1c735be172f8f8b0adeac3afa94e633b5f86`。

#### `01-regression-026` · tests/regression/test_phase3_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase3_benchmark_001.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0472717GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-026/result.json)；SHA256 `7634e76323445c940f83d41a97db37c9b58f248f2dcca78c8dcb622e0ef01753`。

#### `01-regression-027` · tests/regression/test_phase3_toy_case_004.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase3_toy_case_004.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.046669GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-027/result.json)；SHA256 `7bbc0c2ec15421534ab9b15f7c180f8caeadb38d03611c2cc4366fe66b4cc6fa`。

#### `01-regression-028` · tests/regression/test_phase3_toy_case_005.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase3_toy_case_005.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.046505GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-028/result.json)；SHA256 `71500ac544017409dd76071e8f46bdd7f7971155790c19cb3c8a88e202266125`。

#### `01-regression-029` · tests/regression/test_phase4_scope_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase4_scope_benchmark_001.py"]}`。
- 观测墙钟：3.25 秒；进程树提交内存峰值：0.0487976GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-029/result.json)；SHA256 `9906e78919458f58e18caf1be4bf9a96501f5f272a01500a78094604b563b2b4`。

#### `01-regression-030` · tests/regression/test_phase5_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase5_benchmark_001.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0476036GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-030/result.json)；SHA256 `5a89269bedc06ed3c6197b8665e1877fc303c981935c6228958d56a40b46a62f`。

#### `01-regression-031` · tests/regression/test_phase5_string_generator_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase5_string_generator_oracle.py"]}`。
- 观测墙钟：3.25 秒；进程树提交内存峰值：0.04562GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-031/result.json)；SHA256 `a5ce23e99279665e9a94e61dd261ca2d304b712b1608220fd6aa96720db15e14`。

#### `01-regression-032` · tests/regression/test_phase6_benchmark_001.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase6_benchmark_001.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0629272GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-032/result.json)；SHA256 `f90e6fb5c33f9f4afcc1f8aa0213c80402e1098a8713e83a250d7859c725e15b`。

#### `01-regression-033` · tests/regression/test_phase6_pairing_generator_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase6_pairing_generator_oracle.py"]}`。
- 观测墙钟：2.219 秒；进程树提交内存峰值：0.0444832GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-033/result.json)；SHA256 `d1c0b9562cc16ec955ad994e4f1b21ee39162579690880f50feb5eac150ac599`。

#### `01-regression-034` · tests/regression/test_phase7_itinerary_generator_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase7_itinerary_generator_benchmark.py"]}`。
- 观测墙钟：3.281 秒；进程树提交内存峰值：0.0671806GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-034/result.json)；SHA256 `d6c132e2aa752847a89c4ee74a1028653f26435204fb2b83fce12903ad20e28a`。

#### `01-regression-035` · tests/regression/test_phase7_itinerary_generator_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase7_itinerary_generator_oracle.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0449181GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-035/result.json)；SHA256 `8d3fcb28cd608c27e345da3192b5fa0c2ebfd80563e3c247e364bb532f9247a6`。

#### `01-regression-036` · tests/regression/test_phase8_benders_benchmark.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase8_benders_benchmark.py"]}`。
- 观测墙钟：3.218 秒；进程树提交内存峰值：0.0569115GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-036/result.json)；SHA256 `8ecfa816d17f2470bacfdb2a8ad1e3eeddcde7e4cce1949811a4e19b2e04c72a`。

#### `01-regression-037` · tests/regression/test_phase8_benders_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase8_benders_oracle.py"]}`。
- 观测墙钟：3.265 秒；进程树提交内存峰值：0.0467796GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-037/result.json)；SHA256 `f9c47058d00a3b532c30ddf2686b325d9696a54b51af8ebc50c9b2eabdf29592`。

#### `01-regression-038` · tests/regression/test_phase8_benders_scope.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_phase8_benders_scope.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0483551GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-038/result.json)；SHA256 `74c79cbaefa7a80731384583e60dc50f427fcb7ca21c8b211ed246a779b86770`。

#### `01-regression-039` · tests/regression/test_toy_cases.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_toy_cases.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0410385GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-039/result.json)；SHA256 `285cefba6f95e481ed66edc64d24eacdfe873e49d9e99378a1ce19f544b7e51d`。

#### `01-regression-040` · tests/regression/test_validation_case_catalog.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/regression/test_validation_case_catalog.py"]}`。
- 观测墙钟：7.5 秒；进程树提交内存峰值：0.143494GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-040/result.json)；SHA256 `338355ed237089077284249b22a26e39129dbc8227a6d0b4370acefd26e24909`。

#### `01-regression-041` · tests/unit/test_aircraft_string_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_aircraft_string_column_generation.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0452881GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-041/result.json)；SHA256 `443f976266bd1033e9f9c08b58dd8841a37a24b1d29b35ee0b6f4506b3d28383`。

#### `01-regression-042` · tests/unit/test_aircraft_string_master.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_aircraft_string_master.py"]}`。
- 观测墙钟：2.422 秒；进程树提交内存峰值：0.0452423GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-042/result.json)；SHA256 `ac01f22bae33d239c945c39456c4f7913190e3b2f54b469c2b964589cbf047d5`。

#### `01-regression-043` · tests/unit/test_aircraft_string_pricing.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_aircraft_string_pricing.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0451546GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-043/result.json)；SHA256 `5bc8faf58b6611d57bb3923724c0d83d732a3b03172a138c2aa93d211dbeec9a`。

#### `01-regression-044` · tests/unit/test_arm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_arm.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0474701GiB。
- 结果与原因：pytest exit=0; {'passed': 17}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-044/result.json)；SHA256 `bbb06ff9e6a930924d3b0ec714de32afe6371cee85e1ed114e4ba34205b195ad`。

#### `01-regression-045` · tests/unit/test_benders.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_benders.py"]}`。
- 观测墙钟：3.25 秒；进程树提交内存峰值：0.0480232GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-045/result.json)；SHA256 `8b4e694dddd5a882eb59479591b3bae057728ed34f9ef10d4beb662acc0a1b5a`。

#### `01-regression-046` · tests/unit/test_benders_branch_and_price.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_benders_branch_and_price.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0448647GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-046/result.json)；SHA256 `4b858ff1ba9a9a8dc9d02f7d7ecded7f1fed101bba73f30911979afadea827d5`。

#### `01-regression-047` · tests/unit/test_benders_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_benders_column_generation.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0472488GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-047/result.json)；SHA256 `9436481cb533232c8a10bee272b6f8b9e83f096608ea7ff20ab6e7602daea035`。

#### `01-regression-048` · tests/unit/test_branch_and_price.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_branch_and_price.py"]}`。
- 观测墙钟：2.219 秒；进程树提交内存峰值：0.0465355GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-048/result.json)；SHA256 `70b079ded8d38f7dc695e508c6f7caac2989b3c69e182b7d295bb05b515f259e`。

#### `01-regression-049` · tests/unit/test_column_validator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_column_validator.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0410805GiB。
- 结果与原因：pytest exit=0; {'passed': 16}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-049/result.json)；SHA256 `20409b00d1401e09935d799139a848f70055f45644db7ba8cabd528442705460`。

#### `01-regression-050` · tests/unit/test_columns_schema.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_columns_schema.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0411835GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-050/result.json)；SHA256 `d29c793c3dc4dbfccce3aa42d9fe2f81bf7a3c4c83b3a21a01e54547f6184e83`。

#### `01-regression-051` · tests/unit/test_constraint_precheck.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_constraint_precheck.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0458603GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-051/result.json)；SHA256 `d8fd64b56bf614f1c98adce9c4b424a5793942383057641828d99a0c5da21b6c`。

#### `01-regression-052` · tests/unit/test_constraint_registry.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_constraint_registry.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0448685GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-052/result.json)；SHA256 `54ea57ab588b431303a5d572b9f601e7761fa582d9712d54de67ca9d1b7026c7`。

#### `01-regression-053` · tests/unit/test_cost_config.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_cost_config.py"]}`。
- 观测墙钟：2.157 秒；进程树提交内存峰值：0.0422821GiB。
- 结果与原因：pytest exit=0; {'passed': 16}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-053/result.json)；SHA256 `f2dd5687d288f0a2940d84d860c326ee88b34f06d4a93645389354abcfafc735`。

#### `01-regression-054` · tests/unit/test_crew_network.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_network.py"]}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0450134GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-054/result.json)；SHA256 `421459d38b13afee4a03c599913900470085c4dcf4f9130dcce4dce1751f9fcc`。

#### `01-regression-055` · tests/unit/test_crew_pairing_column_generation.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_pairing_column_generation.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0463028GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-055/result.json)；SHA256 `408fac2c5caac70eb89991d51a572bca0120d68583c13df79b9820f0f6c31c8a`。

#### `01-regression-056` · tests/unit/test_crew_pairing_master.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_pairing_master.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0452766GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-056/result.json)；SHA256 `28ca0c8f95b17ee3f05cbf8bfe70177815f64e7008ef9bef959247b83445fe64`。

#### `01-regression-057` · tests/unit/test_crew_pairing_pricing.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crew_pairing_pricing.py"]}`。
- 观测墙钟：2.157 秒；进程树提交内存峰值：0.0455856GiB。
- 结果与原因：pytest exit=0; {'passed': 3}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-057/result.json)；SHA256 `fb38a861632db48d56d0c92c2d994ada4d852aca8af413ab86c7ae7939bd5d4e`。

#### `01-regression-058` · tests/unit/test_crm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_crm.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0468369GiB。
- 结果与原因：pytest exit=0; {'passed': 20}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-058/result.json)；SHA256 `891f0aba90f6b29e3e205092270b854912024df3add1c4b08d84fd2985ba8450`。

#### `01-regression-059` · tests/unit/test_expected_schema.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_expected_schema.py"]}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0411987GiB。
- 结果与原因：pytest exit=0; {'passed': 4}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-059/result.json)；SHA256 `224c94df684210270875ff12051eceefc7ced42fb7850124fafb9ae5cdb256ce`。

#### `01-regression-060` · tests/unit/test_flight_network.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_flight_network.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0450935GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-060/result.json)；SHA256 `2e31dcea537b3e45eaed1abeadbfbc9d01fb6244a029a7078621175f54605ee6`。

#### `01-regression-061` · tests/unit/test_gate_inventory.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_gate_inventory.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0462112GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-061/result.json)；SHA256 `dbc0f7147d1e8c80d78fd49f1bb8e722e069d92dd5a9b655f637336a8029d288`。

#### `01-regression-062` · tests/unit/test_gurobi_adapter.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_gurobi_adapter.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0371208GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-062/result.json)；SHA256 `9ea65e33da9b635e5fe733dcaa1d4e3f1fda7203647a210d2f9b984a825ea92f`。

#### `01-regression-063` · tests/unit/test_incidence.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_incidence.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0460129GiB。
- 结果与原因：pytest exit=0; {'passed': 15}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-063/result.json)；SHA256 `ad0368ff6b2f823edc25402843b7b7b2383c4ec2c09be735e9ea5f778aa0b1b7`。

#### `01-regression-064` · tests/unit/test_indices.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_indices.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0444183GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-064/result.json)；SHA256 `c0f3e459ada735681a60744d02426258f05ea73756bbe7eda07392cf0a5752ca`。

#### `01-regression-065` · tests/unit/test_integrated_oracle.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_integrated_oracle.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0475044GiB。
- 结果与原因：pytest exit=0; {'passed': 8}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-065/result.json)；SHA256 `482a0575de4121ec2f11fbb399e8f5f77e48325553f33f628e195e7c5cf45609`。

#### `01-regression-066` · tests/unit/test_itinerary_generator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_itinerary_generator.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0459251GiB。
- 结果与原因：pytest exit=0; {'passed': 20}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-066/result.json)；SHA256 `4f96a19bb04cfa8fc80480224fd56f871806800c232f0b552772559d91e68af6`。

#### `01-regression-067` · tests/unit/test_json_schema_contract.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_json_schema_contract.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.044529GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-067/result.json)；SHA256 `9a376179cba7d41667e0bf22d950c7bcdcfa65f1c36449d4c97b7e6e112d913c`。

#### `01-regression-068` · tests/unit/test_model_result.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_model_result.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0411835GiB。
- 结果与原因：pytest exit=0; {'passed': 12}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-068/result.json)；SHA256 `308cbd0b9335217e3101794635b20e6f08d69c84ec913c3a1610d4d7b820d3fa`。

#### `01-regression-069` · tests/unit/test_oracle_validator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_oracle_validator.py"]}`。
- 观测墙钟：2.141 秒；进程树提交内存峰值：0.0414772GiB。
- 结果与原因：pytest exit=0; {'passed': 13}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-069/result.json)；SHA256 `6b69fea4e6bd72ec485c9e63b8440b815a1f534db5d5cb8b2c7a23fdc5302f41`。

#### `01-regression-070` · tests/unit/test_pairing_generator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_pairing_generator.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0448799GiB。
- 结果与原因：pytest exit=0; {'passed': 16}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-070/result.json)；SHA256 `83b7111cfb3980b05c3e910b38d02ef7c026e5f1a90484df142f97f0d865c66f`。

#### `01-regression-071` · tests/unit/test_passenger_capacity.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_passenger_capacity.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0426636GiB。
- 结果与原因：pytest exit=0; {'passed': 8}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-071/result.json)；SHA256 `542f00030891f21ffdabd9dd8c7927c968dea366b9a7dfc6a3107b1781e295d1`。

#### `01-regression-072` · tests/unit/test_passenger_incidence.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_passenger_incidence.py"]}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0450211GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-072/result.json)；SHA256 `e6521ee8e27c35260999bdc15278ffd51040cb1f4e3325666b2074a628b3d592`。

#### `01-regression-073` · tests/unit/test_passenger_network.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_passenger_network.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0446014GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-073/result.json)；SHA256 `454fad46047c5d55391ece80e82ed815a3e8d8e00118df64a1ca27aa3193cf90`。

#### `01-regression-074` · tests/unit/test_prm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_prm.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0469322GiB。
- 结果与原因：pytest exit=0; {'passed': 17}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-074/result.json)；SHA256 `3e0928ad9fb0a9084183fd7b55db6f1488bd8db8578c10a52625ea2092f836d1`。

#### `01-regression-075` · tests/unit/test_recovery_handoff.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_recovery_handoff.py"]}`。
- 观测墙钟：2.14 秒；进程树提交内存峰值：0.0448189GiB。
- 结果与原因：pytest exit=0; {'passed': 7}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-075/result.json)；SHA256 `83bfe0f72c3a063594f377df223bafd9cc5fea4d5900f4e3f135e85c66aab347`。

#### `01-regression-076` · tests/unit/test_recovery_metrics.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_recovery_metrics.py"]}`。
- 观测墙钟：2.14 秒；进程树提交内存峰值：0.0411873GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-076/result.json)；SHA256 `6b49228734c601e08571601ccc3c144663c260a3454b01d2196c3c83d72c9a16`。

#### `01-regression-077` · tests/unit/test_result_builder.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_result_builder.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0444603GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-077/result.json)；SHA256 `307ab2ef6274b26f6a81b0980ea251f424123a9513cd36fe8034b4989a251617`。

#### `01-regression-078` · tests/unit/test_schema.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_schema.py"]}`。
- 观测墙钟：2.171 秒；进程树提交内存峰值：0.0410538GiB。
- 结果与原因：pytest exit=0; {'passed': 9}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-078/result.json)；SHA256 `50e2ee9325f1c0d33c092381b4c44c5fc3894fd730e3a828b668fc4c672fb88d`。

#### `01-regression-079` · tests/unit/test_scope.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_scope.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0461082GiB。
- 结果与原因：pytest exit=0; {'passed': 17}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-079/result.json)；SHA256 `2e6e0e92dde86f86462c5d477bff2fe4e7abdc4f33fe34f8b303bd1a413d64a8`。

#### `01-regression-080` · tests/unit/test_solver_contract.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_solver_contract.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0329857GiB。
- 结果与原因：pytest exit=0; {'passed': 10}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-080/result.json)；SHA256 `300f5b7f1975ff8768cb0dc3687fedcfd0e89d8496f457cdadfb433a6fa45479`。

#### `01-regression-081` · tests/unit/test_srm.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_srm.py"]}`。
- 观测墙钟：3.25 秒；进程树提交内存峰值：0.0481873GiB。
- 结果与原因：pytest exit=0; {'passed': 11}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-081/result.json)；SHA256 `a1cf0c37d543c90165e00bf630dc5ad0004a626abd7ba42db86a082acb1f3179`。

#### `01-regression-082` · tests/unit/test_string_generator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_string_generator.py"]}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.0444489GiB。
- 结果与原因：pytest exit=0; {'passed': 6}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-082/result.json)；SHA256 `12c86faa2355d9d2a45b2d8f312488be481b8701d403fdc9c5726a038cc6e759`。

#### `01-regression-083` · tests/unit/test_validation_data_suite.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_validation_data_suite.py"]}`。
- 观测墙钟：3.25 秒；进程树提交内存峰值：0.0922241GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-083/result.json)；SHA256 `20fde1fa6719d97758317ef270412f7ed7560179864847bdccb1255fb55dde2c`。

#### `01-regression-084` · tests/unit/test_validator.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_validator.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0412064GiB。
- 结果与原因：pytest exit=0; {'passed': 14}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-084/result.json)；SHA256 `b41617a7417a692d33855dcae533801002f6663f782837d69fd7a141ae0e1294`。

#### `01-regression-085` · tests/unit/test_visualization_js.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_visualization_js.py"]}`。
- 观测墙钟：2.171 秒；进程树提交内存峰值：0.0839043GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-085/result.json)；SHA256 `b6b7271d818b1507b2afe6d98433fbacd1d49a970be25ee498d37455ebc7c599`。

#### `01-regression-086` · tests/unit/test_workbench_comparison.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_workbench_comparison.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0428391GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-086/result.json)；SHA256 `e3fbd365572749c360c355ae3fd0f90d63543e3528da8c950d089d4bcfc34018`。

#### `01-regression-087` · tests/unit/test_workbench_compiler.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_workbench_compiler.py"]}`。
- 观测墙钟：2.171 秒；进程树提交内存峰值：0.0463638GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-087/result.json)；SHA256 `9bcf4a81f7a47c2588a1211daf375b1702d33addc66e65835933e49d983effc2`。

#### `01-regression-088` · tests/unit/test_workbench_js.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_workbench_js.py"]}`。
- 观测墙钟：2.172 秒；进程树提交内存峰值：0.0834885GiB。
- 结果与原因：pytest exit=0; {'passed': 1}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-088/result.json)；SHA256 `8beac56922d059dabbffc90af0fc1cdacecc40f4d7d0a097f05e190e013ca0f4`。

#### `01-regression-089` · tests/unit/test_xma_recovery.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_xma_recovery.py"]}`。
- 观测墙钟：6.453 秒；进程树提交内存峰值：0.103222GiB。
- 结果与原因：pytest exit=0; {'passed': 27}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-089/result.json)；SHA256 `0aa32d34e1d9a8a8339e83c873298bf709df758b1d3a0d39caf92bc41e3d450d`。

#### `01-regression-005` · tests/api/test_workbench_v2_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_workbench_v2_api.py"]}`。
- 观测墙钟：7.828 秒；进程树提交内存峰值：0.146721GiB。
- 结果与原因：pytest exit=0; {'passed': 7}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-005/result.json)；SHA256 `16341cc394b403a61f9c7337f9116a24d848665f3329c684049c5a81f9cba434`。

#### `01-regression-006` · tests/api/test_xma_api.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/api/test_xma_api.py"]}`。
- 观测墙钟：14.359 秒；进程树提交内存峰值：0.275955GiB。
- 结果与原因：pytest exit=0; {'passed': 2}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-006/result.json)；SHA256 `9f2e44e31725cde820275a683878b57315b31fbb85be5e6e82b55225f0c2758d`。

#### `01-regression-repair-183` · tests/unit/test_algorithm_repair_certificates.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_algorithm_repair_certificates.py"]}`。
- 观测墙钟：4.328 秒；进程树提交内存峰值：0.124523GiB。
- 结果与原因：pytest exit=0; {'passed': 9}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-repair-183/result.json)；SHA256 `8138f9377fff379fae02bf0364f9276a81ea2c0a96d9ffff3f9198edc82564c0`。

#### `01-regression-repair-184` · tests/unit/test_validation_report.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_validation_report.py"]}`。
- 观测墙钟：2.156 秒；进程树提交内存峰值：0.0345955GiB。
- 结果与原因：pytest exit=0; {'passed': 13}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-repair-184/result.json)；SHA256 `3de00aad070b631106666ba0629b7b552f857947a3dbddff70690366d3221bdc`。

#### `01-regression-repair-185` · tests/unit/test_validation_watch.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_validation_watch.py"]}`。
- 观测墙钟：2.171 秒；进程树提交内存峰值：0.0344925GiB。
- 结果与原因：pytest exit=0; {'passed': 16}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-repair-185/result.json)；SHA256 `60a6e5e8ff958d815840c79973bd5c1baa092b84ce1d5d96740af5060ef99517`。

#### `01-regression-repair-186` · tests/unit/test_xma_solver_incremental.py

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`pytest`；阶段：`correctness`；单例墙钟/求解器预算：900/60 秒；提交内存上限：1.5GiB。
- 参数：`{"paths":["tests/unit/test_xma_solver_incremental.py"]}`。
- 观测墙钟：3.235 秒；进程树提交内存峰值：0.0753517GiB。
- 结果与原因：pytest exit=0; {'passed': 5}; skipped=0。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/01-regression-repair-186/result.json)；SHA256 `ab1514f187e5b8d2a176fe98b26c0356e5774f4e6d2b4adbb6e7f3e6dd1d8543`。

### 02 AIR - expected solutions

#### `02-air-cases-001` · benchmark-disruption-recovery

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"benchmark-disruption-recovery"}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0743103GiB。
- 结果与原因：optimal objective=18080.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-001/result.json)；SHA256 `f6684fe971cb6fade0f3a349d96722c0730b1be5200be2a0dfd0eff1c9ab1a76`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 18080.0, "required_flight_options": {"F2": "FO_F2_D50", "F10": "FO_F10_D20", "F11": "FO_F11_D10"}, "required_metrics": {"cancelled_flights": 0, "delayed_flights": 3, "aircraft_reassignments": 2, "passenger_reaccommodated_groups": 1, "unserved_passengers": 0}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 18080 | 18080 | 18080 | True | 缺失 | 0.226349 | 0.226349 |

#### `02-air-cases-002` · crew-recovery-integrality

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"crew-recovery-integrality","additional_expectations":[{"status":"optimal","objective_total":95200.0}]}`。
- 观测墙钟：3.312 秒；进程树提交内存峰值：0.0730286GiB。
- 结果与原因：optimal objective=95200.0; 停止原因=exact_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-002/result.json)；SHA256 `70c7e08e7ff726e5081a1057f1ef82007c5543e5bfe4819dd00b9036ca0c1e05`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 95200.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 95200 | 95200 | 95200 | True | 缺失 | 1.89716 | 1.89716 |

#### `02-air-cases-003` · passenger-capacity-constrained

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"passenger-capacity-constrained"}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0702171GiB。
- 结果与原因：optimal objective=1010.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-003/result.json)；SHA256 `ad2bfec6cb1db99cafd7414229e6089af298b9791f502d8a74006dd6fefa8b60`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 1010.0, "required_flight_options": {"T5_F1": "FO_T5_F1_D10"}, "required_metrics": {"delayed_flights": 1, "unserved_passengers": 0}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 1010 | 1010 | 1010 | True | 缺失 | 0.0685792 | 0.0685792 |

#### `02-air-cases-004` · passenger-capacity-relaxed

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"passenger-capacity-relaxed"}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0702782GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-004/result.json)；SHA256 `33e8b1f6dd6884e789f5d17d97b87381e28e138951bc06d7da59b53e45bf4291`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 0.0, "required_flight_options": {"T5_F1": "FO_T5_F1_ORIG"}, "required_metrics": {"delayed_flights": 0, "unserved_passengers": 0}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 | 0.0673058 | 0.0673058 |

#### `02-air-cases-005` · delay-cost-cancellation-tradeoff

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"delay-cost-cancellation-tradeoff"}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0701714GiB。
- 结果与原因：optimal objective=25000.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-005/result.json)；SHA256 `6aad8f443874c751a85cb6426fd5db344b335dd0eec9c1dbaee1c29bdf5007ef`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "optimal", "objective_total": 25000.0, "required_flight_options": {"T5_F1": "FO_T5_F1_ORIG"}, "required_metrics": {"delayed_flights": 0, "unserved_passengers": 10}}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 25000 | 25000 | 25000 | True | 缺失 | 0.0591119 | 0.0591119 |

#### `02-air-cases-006` · solve-ready-infeasible

- 执行状态：`passed`；结论：**返回不可行，认证与边界见原始结果**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"solve-ready-infeasible"}`。
- 观测墙钟：2.235 秒；进程树提交内存峰值：0.0714912GiB。
- 结果与原因：infeasible objective=None; 停止原因=phase11_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-006/result.json)；SHA256 `1ab3c34bcac12cf3812b34170e62ff1945af123399a3b202b5b87ff345d5da49`。
- 参考断言：`{"scenario_valid": true, "solve_ready": true, "optimization_status": "infeasible", "objective_total": null}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | infeasible | 缺失 | 0 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

#### `02-air-cases-007` · scenario-only-minimal

- 执行状态：`passed`；结论：**输入合同或预检完成，未运行优化**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"scenario-only-minimal"}`。
- 观测墙钟：1.094 秒；进程树提交内存峰值：0.0348969GiB。
- 结果与原因：Expected input rejection / Scenario-only verified。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-007/result.json)；SHA256 `c49db3bd251a1d91eb2265d9c343b6d08c7ce25227d4b494f465b8edb34fa126`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| air_case/ | not_run | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

#### `02-air-cases-008` · invalid-missing-airport

- 执行状态：`passed`；结论：**输入合同或预检完成，未运行优化**。
- 类型：`air_case`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"invalid-missing-airport"}`。
- 观测墙钟：1.094 秒；进程树提交内存峰值：0.0348892GiB。
- 结果与原因：Expected input rejection / Scenario-only verified。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-008/result.json)；SHA256 `2ece6574ff093702af7550cfa01d619a0b873e861c95094cf41dd3198588dbb1`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| air_case/ | not_run | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

#### `02-air-cases-009` · micro-aircraft-coupling

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-aircraft-coupling.json","expected":{"status":"optimal"}}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0699615GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-009/result.json)；SHA256 `178440346b9c6fcc844749388fababd7f4b28b729ec270e02131bd341501584c`。
- 参考断言：`{"status": "optimal"}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 | 0.0606964 | 0.0606964 |

#### `02-air-cases-010` · micro-scope-closure

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-scope-closure.json","expected":{"status":"optimal","objective_total":2040.0}}`。
- 观测墙钟：2.235 秒；进程树提交内存峰值：0.0701637GiB。
- 结果与原因：optimal objective=2040.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-010/result.json)；SHA256 `4954b9fd7d7ef34d84184116e60a9c352a217d6d80033ca65c8f7a8bde849aca`。
- 参考断言：`{"status": "optimal", "objective_total": 2040.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 2040 | 2040 | 2040 | True | 缺失 | 0.0796109 | 0.0796109 |

#### `02-air-cases-011` · micro-aircraft-string-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-aircraft-string-generation.json","expected":{"status":"optimal","objective_total":0.0}}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0709877GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-011/result.json)；SHA256 `47c3f86eae096b91268fdcd4c507ddc2746af6141cc8dea60982439719796ca7`。
- 参考断言：`{"status": "optimal", "objective_total": 0.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 | 0.0832183 | 0.0832183 |

#### `02-air-cases-012` · micro-passenger-itinerary-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-passenger-itinerary-generation.json","expected":{"status":"optimal","objective_total":0.0}}`。
- 观测墙钟：2.25 秒；进程树提交内存峰值：0.0707664GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-012/result.json)；SHA256 `86d5f98459f567bb7563268eae8b86a2b884f075eaa244545c57bce446c47660`。
- 参考断言：`{"status": "optimal", "objective_total": 0.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 | 0.142512 | 0.142512 |

#### `02-air-cases-013` · micro-fixed-column-benders

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-fixed-column-benders.json","expected":{"status":"optimal"}}`。
- 观测墙钟：1.125 秒；进程树提交内存峰值：0.0698509GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-013/result.json)；SHA256 `4354734bd00d5b380e652ede2818d39c48c98b97e6d588ea0eea68f140a72e73`。
- 参考断言：`{"status": "optimal"}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 | 0.0663631 | 0.0663631 |

#### `02-air-cases-014` · micro-aircraft-column-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-aircraft-column-generation.json","expected":{"status":"optimal","objective_total":0.0}}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0704193GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-014/result.json)；SHA256 `3926a3ed029063579b58d59eabf01cbd3cda1d012106a1cb49b04ef140ab5d8a`。
- 参考断言：`{"status": "optimal", "objective_total": 0.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 | 0.0742543 | 0.0742543 |

#### `02-air-cases-015` · micro-crew-column-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-crew-column-generation.json","expected":{"status":"optimal","objective_total":150.0}}`。
- 观测墙钟：2.219 秒；进程树提交内存峰值：0.0708694GiB。
- 结果与原因：optimal objective=150.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-015/result.json)；SHA256 `e7d27a743cfe1937bd09003a3e41b34a895b75d5bc66620702814a456f8d8aa5`。
- 参考断言：`{"status": "optimal", "objective_total": 150.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 150 | 150 | 150 | True | 缺失 | 0.0783538 | 0.0783538 |

#### `02-air-cases-016` · micro-benders-column-generation

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-benders-column-generation.json","expected":{"status":"optimal","objective_total":220.0}}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0700302GiB。
- 结果与原因：optimal objective=220.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-016/result.json)；SHA256 `9a6c2e80252eedb682c3f9291c281bdf065f3bdcd703f1ca7bf32688c2f73e37`。
- 参考断言：`{"status": "optimal", "objective_total": 220.0}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 220 | 220 | 220 | True | 缺失 | 0.0906187 | 0.0906187 |

#### `02-air-cases-017` · micro-crew-root-integrality

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/micro/micro-crew-root-integrality.json","expected":{"status":"optimal"}}`。
- 观测墙钟：2.234 秒；进程树提交内存峰值：0.0730629GiB。
- 结果与原因：optimal objective=0.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/02-air-cases-017/result.json)；SHA256 `506908d804b838b258a88a7686c51b34bc1fbeef3a979cff4688b906725e3234`。
- 参考断言：`{"status": "optimal"}`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 0 | 0 | 0 | True | 缺失 | 0.158415 | 0.158415 |

### 03 AIR - Aircraft column generation

#### `03-aircraft-cg-001` · aircraft: full LP vs CG / toy_case_011_aircraft_string_column_generation

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"aircraft","case":"toy_case_011_aircraft_string_column_generation","repeats":3,"warmups":1}`。
- 观测墙钟：2.157 秒；进程树提交内存峰值：0.0356293GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.262。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/03-aircraft-cg-001/result.json)；SHA256 `0febf54324f19f4c8e6f567161b8daca0fcbea0870c042f4034d916821862b4d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| full/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0091989 | 缺失 | 缺失 |
| cg/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0261893 | 缺失 | 缺失 |
| cg/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0169598 | 缺失 | 缺失 |
| full/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0044102 | 缺失 | 缺失 |
| full/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0044397 | 缺失 | 缺失 |
| cg/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0155885 | 缺失 | 缺失 |

#### `03-aircraft-cg-002` · aircraft: full LP vs CG / phase1_benchmark_001

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"aircraft","case":"phase1_benchmark_001","repeats":3,"warmups":1}`。
- 观测墙钟：2.203 秒；进程树提交内存峰值：0.0369568GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.345。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/03-aircraft-cg-002/result.json)；SHA256 `eb6eee6b6dfd920fb0b2f1edd3d18c9888791bf91caf91c65aede504fc0b2d8d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| full/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0171742 | 缺失 | 缺失 |
| cg/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0444971 | 缺失 | 缺失 |
| cg/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0491918 | 缺失 | 缺失 |
| full/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.015633 | 缺失 | 缺失 |
| full/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0158827 | 缺失 | 缺失 |
| cg/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0460828 | 缺失 | 缺失 |

### 04 AIR - Crew column generation

#### `04-crew-cg-001` · crew: full LP vs CG / toy_case_012_crew_pairing_column_generation

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"crew","case":"toy_case_012_crew_pairing_column_generation","repeats":3,"warmups":1}`。
- 观测墙钟：2.188 秒；进程树提交内存峰值：0.035923GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.191。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/04-crew-cg-001/result.json)；SHA256 `229286f0150e5a1974d6af59e2b9ba7eb5b1ba86d4e1eca94593727a3f459710`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| full/0 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0048895 | 缺失 | 缺失 |
| cg/0 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0257097 | 缺失 | 缺失 |
| cg/1 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0254394 | 缺失 | 缺失 |
| full/1 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0049214 | 缺失 | 缺失 |
| full/2 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0057218 | 缺失 | 缺失 |
| cg/2 | 见测试断言 | 150 | 缺失 | 缺失 | 缺失 | 0.0279661 | 缺失 | 缺失 |

#### `04-crew-cg-002` · crew: full LP vs CG / phase1_benchmark_001

- 执行状态：`passed`；结论：**LP 最优及定价终止审计通过**。
- 类型：`air_cg`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"owner":"crew","case":"phase1_benchmark_001","repeats":3,"warmups":1}`。
- 观测墙钟：3.265 秒；进程树提交内存峰值：0.0431976GiB。
- 结果与原因：LP objectives and pricing audit agree; observed full/CG median speedup=0.322。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/04-crew-cg-002/result.json)；SHA256 `eb572bf3d3b1e0f1ef0fcefaaeb2bfff3d9bbf8db65ee1118654e9503232a0bf`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| full/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0610191 | 缺失 | 缺失 |
| cg/0 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.184384 | 缺失 | 缺失 |
| cg/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.181646 | 缺失 | 缺失 |
| full/1 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0551777 | 缺失 | 缺失 |
| full/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.0584001 | 缺失 | 缺失 |
| cg/2 | 见测试断言 | 0 | 缺失 | 缺失 | 缺失 | 0.16516 | 缺失 | 缺失 |

### 05 AIR - Benders BP vs integrated

#### `05-air-oracle-001` · Integrated vs Benders BP / benchmark-disruption-recovery

- 执行状态：`passed`；结论：**联合 Oracle 与 Benders/B&P 最优一致**。
- 类型：`air_oracle`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"benchmark-disruption-recovery","repeats":3}`。
- 观测墙钟：3.281 秒；进程树提交内存峰值：0.0462952GiB。
- 结果与原因：Integrated oracle and exact Benders/BP agree in all repetitions。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/05-air-oracle-001/result.json)；SHA256 `46717850240fe36553cf976af48a98716eb40d925edfa3d62362718315da9ac1`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| integrated/0 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.0919982 | 缺失 | 缺失 |
| benders_bp/0 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.207598 | 缺失 | 缺失 |
| benders_bp/1 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.22209 | 缺失 | 缺失 |
| integrated/1 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.0883632 | 缺失 | 缺失 |
| integrated/2 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.0878043 | 缺失 | 缺失 |
| benders_bp/2 | 见测试断言 | 18080 | 缺失 | 缺失 | 缺失 | 0.242826 | 缺失 | 缺失 |

#### `05-air-oracle-002` · Integrated vs Benders BP / crew-recovery-integrality

- 执行状态：`passed`；结论：**联合 Oracle 与 Benders/B&P 最优一致**。
- 类型：`air_oracle`；阶段：`performance`；单例墙钟/求解器预算：600/60 秒；提交内存上限：1.5GiB。
- 参数：`{"case_id":"crew-recovery-integrality","repeats":3}`。
- 观测墙钟：10.813 秒；进程树提交内存峰值：0.0424423GiB。
- 结果与原因：Integrated oracle and exact Benders/BP agree in all repetitions。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/05-air-oracle-002/result.json)；SHA256 `246e70c315011230ed5a8589899c2c3a1a53fd9dcf0db70626c6c41331d7839d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| integrated/0 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 0.0350817 | 缺失 | 缺失 |
| benders_bp/0 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 2.16952 | 缺失 | 缺失 |
| benders_bp/1 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 2.39163 | 缺失 | 缺失 |
| integrated/1 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 0.0195257 | 缺失 | 缺失 |
| integrated/2 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 0.0186491 | 缺失 | 缺失 |
| benders_bp/2 | 见测试断言 | 95200 | 缺失 | 缺失 | 缺失 | 2.27368 | 缺失 | 缺失 |

### 06 Conflicts - cancellation and limits

#### `06-stop-conflict-001` · Capacity/candidates/order metamorphic properties

- 执行状态：`passed`；结论：**变形关系断言通过，各问题最优性分别认证**。
- 类型：`metamorphic`；阶段：`correctness`；单例墙钟/求解器预算：300/60 秒；提交内存上限：1.5GiB。
- 参数：`{}`。
- 观测墙钟：3.328 秒；进程树提交内存峰值：0.088295GiB。
- 结果与原因：Capacity relaxation, candidate expansion, order invariance verified; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/06-stop-conflict-001/result.json)；SHA256 `27aaf8dd2058e01b0cc675cc9c2d295ad468e536650a2c63f163c0f11c36b5eb`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 160 | 160 | 160 | True | 0.0203504 | 0.0131111 | 0.0131111 |
| joint_arc_flow/0 | optimal | 110 | 110 | 110 | True | 0.0301453 | 0.0227122 | 0.0227122 |

#### `06-stop-conflict-002` · Immediate cancellation and conflicting XMA instance

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`stop_controls`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{}`。
- 观测墙钟：3.297 秒；进程树提交内存峰值：0.121738GiB。
- 结果与原因：Certified infeasibility, cancellation and restricted nonoptimal output verified。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/06-stop-conflict-002/result.json)；SHA256 `fb69ac5925140c86d7a005df9cd88b3614f5ec5766af1676433409f8354580ca`。

### 07 XMA - four algorithms two objectives

#### `07-xma-oracle-001` · Four algorithms / tianchi_2017 / normal

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"normal"}`。
- 观测墙钟：3.297 秒；进程树提交内存峰值：0.0853729GiB。
- 结果与原因：Four architectures agree; objective=0.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-001/result.json)；SHA256 `6b800de0e4421bbd384b5399530e9935cdb3bbce12328f995ecf5fec0bbc6ca2`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 0 | 0 | 0 | True | 0.0322778 | 0.0250204 | 0.0250204 |
| joint_path_oracle/0 | optimal | 0 | 0 | 0 | True | 0.0176853 | 0.0106401 | 0.0106401 |
| benders_joint/0 | optimal | 0 | 0 | 0 | True | 0.0260862 | 0.0164774 | 0.0164774 |
| benders_cg_bp/0 | optimal | 0 | 0 | 0 | True | 0.0281165 | 0.0186888 | 0.0186888 |

#### `07-xma-oracle-002` · Four algorithms / tianchi_2017 / delay

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"delay"}`。
- 观测墙钟：3.297 秒；进程树提交内存峰值：0.0850945GiB。
- 结果与原因：Four architectures agree; objective=110.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-002/result.json)；SHA256 `0c4a35be6aab21ba86b6b1f5f045611be0c2cd5d6a671516e3a9d71ab3719573`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 110 | 110 | 110 | True | 0.019688 | 0.0129426 | 0.0129426 |
| joint_path_oracle/0 | optimal | 110 | 110 | 110 | True | 0.0182927 | 0.0111148 | 0.0111148 |
| benders_joint/0 | optimal | 110 | 110 | 110 | True | 0.0268187 | 0.0176311 | 0.0176311 |
| benders_cg_bp/0 | optimal | 110 | 110 | 110 | True | 0.0268404 | 0.0173185 | 0.0173185 |

#### `07-xma-oracle-003` · Four algorithms / tianchi_2017 / overflow

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"overflow"}`。
- 观测墙钟：3.312 秒；进程树提交内存峰值：0.0849876GiB。
- 结果与原因：Four architectures agree; objective=16.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-003/result.json)；SHA256 `dd24ca077a4d346ab2898b52681bf426b0e5767d1a76da81844fb4362cf05ef4`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 16 | 16 | 16 | True | 0.0224524 | 0.0151111 | 0.0151111 |
| joint_path_oracle/0 | optimal | 16 | 16 | 16 | True | 0.0176162 | 0.0104984 | 0.0104984 |
| benders_joint/0 | optimal | 16 | 16 | 16 | True | 0.0259224 | 0.0158324 | 0.0158324 |
| benders_cg_bp/0 | optimal | 16 | 16 | 16 | True | 0.0416008 | 0.0307836 | 0.0307836 |

#### `07-xma-oracle-004` · Four algorithms / tianchi_2017 / split

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"split"}`。
- 观测墙钟：3.375 秒；进程树提交内存峰值：0.0854301GiB。
- 结果与原因：Four architectures agree; objective=0.26666666666666666; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-004/result.json)；SHA256 `81c094d9879184fbb4eac14f3d94b7e15035347965e8d3646118afe98d38e3aa`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.0260006 | 0.0184563 | 0.0184563 |
| joint_path_oracle/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.0205972 | 0.0132352 | 0.0132352 |
| benders_joint/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.0362163 | 0.0234646 | 0.0234646 |
| benders_cg_bp/0 | optimal | 0.266667 | 0.266667 | 0.266667 | True | 0.134802 | 0.0328552 | 0.0328552 |

#### `07-xma-oracle-005` · Four algorithms / tianchi_2017 / branch

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"tianchi_2017","variant":"branch"}`。
- 观测墙钟：3.375 秒；进程树提交内存峰值：0.0850296GiB。
- 结果与原因：Four architectures agree; objective=0.2; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-005/result.json)；SHA256 `ca14c5ff88e32feb2ec8215eabdec151ab32f2cd1c9773976f9bdff1655d8a30`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.0341556 | 0.0265026 | 0.0265026 |
| joint_path_oracle/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.0207396 | 0.0132784 | 0.0132784 |
| benders_joint/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.032652 | 0.0211068 | 0.0211068 |
| benders_cg_bp/0 | optimal | 0.2 | 0.2 | 0.2 | True | 0.0837519 | 0.0577427 | 0.0577427 |

#### `07-xma-oracle-006` · Four algorithms / air_linear_v1 / normal

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"normal"}`。
- 观测墙钟：3.328 秒；进程树提交内存峰值：0.0842743GiB。
- 结果与原因：Four architectures agree; objective=0.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-006/result.json)；SHA256 `13a48bb9fbb87c35644fb509ca078f60d71801f366a2104defd25f6d21396722`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 0 | 0 | 0 | True | 0.0260063 | 0.0181885 | 0.0181885 |
| joint_path_oracle/0 | optimal | 0 | 0 | 0 | True | 0.0184709 | 0.011256 | 0.011256 |
| benders_joint/0 | optimal | 0 | 0 | 0 | True | 0.0260411 | 0.0169145 | 0.0169145 |
| benders_cg_bp/0 | optimal | 0 | 0 | 0 | True | 0.028433 | 0.0184391 | 0.0184391 |

#### `07-xma-oracle-007` · Four algorithms / air_linear_v1 / delay

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"delay"}`。
- 观测墙钟：3.344 秒；进程树提交内存峰值：0.0852203GiB。
- 结果与原因：Four architectures agree; objective=3060.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-007/result.json)；SHA256 `6604eff0ddea962bdfe195f0a80cd40a7d93aec8de6d75df4e3c4f265dd9a1d3`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 3060 | 3060 | 3060 | True | 0.0380416 | 0.0285854 | 0.0285854 |
| joint_path_oracle/0 | optimal | 3060 | 3060 | 3060 | True | 0.0211029 | 0.0132036 | 0.0132036 |
| benders_joint/0 | optimal | 3060 | 3060 | 3060 | True | 0.0303794 | 0.0186816 | 0.0186816 |
| benders_cg_bp/0 | optimal | 3060 | 3060 | 3060 | True | 0.0834447 | 0.0218418 | 0.0218418 |

#### `07-xma-oracle-008` · Four algorithms / air_linear_v1 / overflow

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"overflow"}`。
- 观测墙钟：3.359 秒；进程树提交内存峰值：0.0854683GiB。
- 结果与原因：Four architectures agree; objective=10000.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-008/result.json)；SHA256 `f3b489cc4af3cdcc5cd72edd60e88ca8125aba86ea5823c10874a3508cc4367d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 10000 | 10000 | 10000 | True | 0.032664 | 0.0254131 | 0.0254131 |
| joint_path_oracle/0 | optimal | 10000 | 10000 | 10000 | True | 0.0182752 | 0.010899 | 0.010899 |
| benders_joint/0 | optimal | 10000 | 10000 | 10000 | True | 0.0299411 | 0.0189299 | 0.0189299 |
| benders_cg_bp/0 | optimal | 10000 | 10000 | 10000 | True | 0.0983061 | 0.0363032 | 0.0363032 |

#### `07-xma-oracle-009` · Four algorithms / air_linear_v1 / split

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"split"}`。
- 观测墙钟：3.312 秒；进程树提交内存峰值：0.0848541GiB。
- 结果与原因：Four architectures agree; objective=0.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-009/result.json)；SHA256 `2a644a8c745c14c17573916d47af8f18b011f42b4f6f94738be7cb6ed3b4d6d2`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 0 | 0 | 0 | True | 0.033887 | 0.0262918 | 0.0262918 |
| joint_path_oracle/0 | optimal | 0 | 0 | 0 | True | 0.0194116 | 0.0121101 | 0.0121101 |
| benders_joint/0 | optimal | 0 | 0 | 0 | True | 0.0325917 | 0.0221248 | 0.0221248 |
| benders_cg_bp/0 | optimal | 0 | 0 | 0 | True | 0.0331373 | 0.0227727 | 0.0227727 |

#### `07-xma-oracle-010` · Four algorithms / air_linear_v1 / branch

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_micro`；阶段：`correctness`；单例墙钟/求解器预算：180/30 秒；提交内存上限：1.5GiB。
- 参数：`{"objective":"air_linear_v1","variant":"branch"}`。
- 观测墙钟：3.297 秒；进程树提交内存峰值：0.0855827GiB。
- 结果与原因：Four architectures agree; objective=40.0; 停止原因=2, integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-010/result.json)；SHA256 `de405ef17d339a993bf5a8406f109bde68cab77aecf45dd9a00d390324aa23b7`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 40 | 40 | 40 | True | 0.0371641 | 0.0287072 | 0.0287072 |
| joint_path_oracle/0 | optimal | 40 | 40 | 40 | True | 0.0239685 | 0.0163699 | 0.0163699 |
| benders_joint/0 | optimal | 40 | 40 | 40 | True | 0.0351425 | 0.0236487 | 0.0236487 |
| benders_cg_bp/0 | optimal | 40 | 40 | 40 | True | 0.0570532 | 0.0360564 | 0.0360564 |

#### `07-xma-oracle-011` · Official JAR fixture revalidation (existing runtime only)

- 执行状态：`passed`；结论：**测试断言通过**。
- 类型：`jar`；阶段：`correctness`；单例墙钟/求解器预算：180/60 秒；提交内存上限：1.5GiB。
- 参数：`{"java_executable":"D:\\Program Files\\MATLAB\\R2024b\\sys\\java\\jre\\win64\\jre\\bin\\java.exe"}`。
- 观测墙钟：2.234 秒；进程树提交内存峰值：0.538822GiB。
- 结果与原因：Official JAR and independent evaluator agree on the documented derived fixture。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/07-xma-oracle-011/result.json)；SHA256 `72eb9d8283d645d85e9ac7eccf0e731d7139ba888ead88a34873c2ebc7462273`。

### 08 XMA - joint arc flow

#### `08-xma-arc-001` · Timing / fixed target=20 seed=None / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.656 秒；进程树提交内存峰值：0.126209GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-001/result.json)；SHA256 `2318da20c859e8c256763d0fe6cea4d0b8b0774d09730378f72a9cbdc399c961`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 11444 | 11444 | 11444 | True | 0.313991 | 0.17468 | 0.17468 |
| joint_arc_flow/1 | optimal | 11444 | 11444 | 11444 | True | 0.293155 | 0.187026 | 0.187026 |
| joint_arc_flow/2 | optimal | 11444 | 11444 | 11444 | True | 0.272678 | 0.169048 | 0.169048 |

#### `08-xma-arc-002` · Timing / fixed target=20 seed=None / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.64 秒；进程树提交内存峰值：0.126152GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-002/result.json)；SHA256 `3842f885c67003d0d7e3e060de3c3704f94558baa25907eb21d14c68f4185a4c`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.341279 | 0.178311 | 0.178311 |
| joint_arc_flow/1 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.292114 | 0.168306 | 0.168306 |
| joint_arc_flow/2 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.279146 | 0.175297 | 0.175297 |

#### `08-xma-arc-003` · Timing / fixed target=100 seed=None / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：13.969 秒；进程树提交内存峰值：0.146824GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-003/result.json)；SHA256 `907412caff5842066e1c57414700442d220be96569ca8a1d79e6180d5845b5ed`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.58971 | 1.35676 | 1.44715 |
| joint_arc_flow/1 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.59534 | 1.36246 | 1.44842 |
| joint_arc_flow/2 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.55873 | 1.32865 | 1.41408 |

#### `08-xma-arc-004` · Timing / fixed target=100 seed=None / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：12.985 秒；进程树提交内存峰值：0.143337GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-004/result.json)；SHA256 `957a331aa0194a6bba67bb7271779afa18453b2010922fefbffb6ccf81096cf0`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 1.42057 | 1.19563 | 1.28164 |
| joint_arc_flow/1 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 1.45255 | 1.22811 | 1.31468 |
| joint_arc_flow/2 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 1.39834 | 1.17465 | 1.25744 |

#### `08-xma-arc-005` · Timing / random target=20 seed=20261106 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：7.547 秒；进程树提交内存峰值：0.12719GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-005/result.json)；SHA256 `6e7c604f6b2c40ddb0a5857798d08a672730aab7b183aeb6e2edc80653ca9b12`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 5948 | 5948 | 5948 | True | 0.279452 | 0.168519 | 0.168519 |
| joint_arc_flow/1 | optimal | 5948 | 5948 | 5948 | True | 0.270828 | 0.165223 | 0.165223 |
| joint_arc_flow/2 | optimal | 5948 | 5948 | 5948 | True | 0.267105 | 0.163165 | 0.163165 |

#### `08-xma-arc-006` · Timing / random target=20 seed=20261106 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.64 秒；进程树提交内存峰值：0.126408GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-006/result.json)；SHA256 `6bbf8591534039b0e8d4fb0c0d865076f4167f5429267b41ac849dfe455149a9`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 870000 | 870000 | 870000 | True | 0.323233 | 0.197021 | 0.197021 |
| joint_arc_flow/1 | optimal | 870000 | 870000 | 870000 | True | 0.290907 | 0.161857 | 0.161857 |
| joint_arc_flow/2 | optimal | 870000 | 870000 | 870000 | True | 0.26636 | 0.159044 | 0.159044 |

#### `08-xma-arc-007` · Timing / random target=20 seed=20261107 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：7.563 秒；进程树提交内存峰值：0.126499GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-007/result.json)；SHA256 `c043c551ad7e4ad15027648f37ce7803537e19415793badba3355a1d687ee15e`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.298014 | 0.16337 | 0.16337 |
| joint_arc_flow/1 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.26601 | 0.156398 | 0.156398 |
| joint_arc_flow/2 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.280689 | 0.162683 | 0.162683 |

#### `08-xma-arc-008` · Timing / random target=20 seed=20261107 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.641 秒；进程树提交内存峰值：0.126301GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-008/result.json)；SHA256 `9e0ac664803f84a0ff766dad1fe709c0d34566df822b1811d48b90099bc2e443`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.289835 | 0.157845 | 0.157845 |
| joint_arc_flow/1 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.297268 | 0.17894 | 0.17894 |
| joint_arc_flow/2 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.293933 | 0.188601 | 0.188601 |

#### `08-xma-arc-009` · Timing / random target=100 seed=20261106 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：12.985 秒；进程树提交内存峰值：0.133987GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-009/result.json)；SHA256 `604e57faf8552ff09124431c6a51cd8adaca3ea8b9995e36ce9b4a30fd365954`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.38072 | 1.00096 | 1.22752 |
| joint_arc_flow/1 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.38906 | 1.02546 | 1.24152 |
| joint_arc_flow/2 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.34118 | 0.982301 | 1.19458 |

#### `08-xma-arc-010` · Timing / random target=100 seed=20261106 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：11.891 秒；进程树提交内存峰值：0.136414GiB。
- 结果与原因：joint_arc_flow: optimal, optimal, optimal; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-010/result.json)；SHA256 `4441296bb4ea336c3edf21b64eb05a809705337e7ae8152dfa0c6a0e6af97a6a`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.10544 | 0.855861 | 0.952791 |
| joint_arc_flow/1 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.10631 | 0.865118 | 0.961557 |
| joint_arc_flow/2 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.10459 | 0.85582 | 0.953738 |

#### `08-xma-arc-011` · Timing / random target=100 seed=20261107 / tianchi_2017 / joint_arc_flow

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"joint_arc_flow","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.703 秒；进程树提交内存峰值：0.129974GiB。
- 结果与原因：joint_arc_flow: infeasible, infeasible, infeasible; 停止原因=3。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-011/result.json)；SHA256 `bb60a2844fbb0e70eb5d2fb2cb91ec87ea40f014e1c214b243fc43aaa8d82323`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.359771 | 缺失 | 缺失 |
| joint_arc_flow/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.344668 | 缺失 | 缺失 |
| joint_arc_flow/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.361998 | 缺失 | 缺失 |

#### `08-xma-arc-012` · Timing / random target=100 seed=20261107 / air_linear_v1 / joint_arc_flow

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"joint_arc_flow","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.625 秒；进程树提交内存峰值：0.129379GiB。
- 结果与原因：joint_arc_flow: infeasible, infeasible, infeasible; 停止原因=3。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-012/result.json)；SHA256 `cdf6df2843daf5050aeed53a77ba3ca852b00edcb8e9afb904e0fa012867bd1c`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.344813 | 缺失 | 缺失 |
| joint_arc_flow/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.342595 | 缺失 | 缺失 |
| joint_arc_flow/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.363236 | 缺失 | 缺失 |

#### `08-xma-arc-013` · Stress / joint_arc_flow / fixed target=100 / grid60 max120

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/270 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：6.485 秒；进程树提交内存峰值：0.139259GiB。
- 结果与原因：joint_arc_flow: optimal; objective=56897.62037037037; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-013/result.json)；SHA256 `00c75e6a0d80f734254b4c2f7db4e77fd5e6d6af81dc559cb46d9afc02e10455`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.65983 | 1.38324 | 1.52494 |

#### `08-xma-arc-014` · Stress / joint_arc_flow / fixed target=500 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：3600/3570 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：3576.14 秒；进程树提交内存峰值：2.10918GiB。
- 结果与原因：joint_arc_flow: not_converged; objective=None; 停止原因=11。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-014/result.json)；SHA256 `44bfbdfd8a65ab0b53b383920dda3cc8523657118920648c921eb82fd8ef04e4`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | not_converged | 缺失 | 197683 | 缺失 | 缺失 | 3570.69 | 缺失 | 缺失 |

#### `08-xma-arc-015` · Stress / joint_arc_flow / fixed target=2364 / grid60 max120

- 执行状态：`passed`；结论：**求解器认证不可行**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：14.922 秒；进程树提交内存峰值：0.139435GiB。
- 结果与原因：joint_arc_flow: infeasible; objective=None; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-015/result.json)；SHA256 `697d988357f469d45b12404687c9e72c72d9d8a46d48b9d299101a66de9f652d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 5.16493 | 缺失 | 缺失 |

#### `08-xma-arc-016` · Stress / joint_arc_flow / fixed target=100 / grid30 max1440

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：900/870 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：273.125 秒；进程树提交内存峰值：0.978588GiB。
- 结果与原因：joint_arc_flow: optimal; objective=42473.56481481481; 停止原因=2。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-016/result.json)；SHA256 `d6a67878cf437fb21b7fa72bea22229cb62b0bfda8ba91e7678a503c52e2d32b`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| joint_arc_flow/0 | optimal | 42473.6 | 42473.6 | 42473.6 | True | 267.66 | 238.732 | 267.398 |

#### `08-xma-arc-017` · Stress / joint_arc_flow / fixed target=500 / grid30 max1440

- 执行状态：`resource_limited`；结论：**资源受限**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow"}`。
- 观测墙钟：124.641 秒；进程树提交内存峰值：4.03561GiB。
- 结果与原因：resource_limited: MemoryError: bad allocation; 进程树提交内存上限 4GiB；具体触发项见 reason/worker.log。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-017/result.json)；SHA256 `d08bbb8f0b06f485f4b0857762268884e31222be9b0382428b7ac4adbee86df6`。

#### `08-xma-arc-018` · Full 2364 fine grid: candidate readiness and size gate

- 执行状态：`input_limit`；结论：**候选或输入规模门槛**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/60 秒；提交内存上限：2.5GiB。
- 参数：`{"size":2364,"mode":"fixed","step":30,"delay":1440,"algorithm":"joint_arc_flow","precheck_only":true,"max_assignments":100000}`。
- 观测墙钟：77.625 秒；进程树提交内存峰值：0.436764GiB。
- 结果与原因：Candidate/assignment readiness only; optimization not run; 输入门槛=assignment network has 6055567 tail-option pairs, exceeds configured limit 100000; increase delay_step_minutes, lower maximum_delay_minutes, or explicitly raise max_assignment_options。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/08-xma-arc-018/result.json)；SHA256 `2da607614153710a72df41e6439d820b1761cbf4a4df28b67377ffd0b3e75ae6`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| xma_scale/ | not_run | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

### 09 XMA - Benders joint

#### `09-xma-benders-001` · Timing / fixed target=20 seed=None / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.625 秒；进程树提交内存峰值：0.126106GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-001/result.json)；SHA256 `fab50a59b48703bcb7c85c3675f9f1852e9ac65feb5b8fc2554dd1cf06582279`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 11444 | 11444 | 11444 | True | 0.345805 | 0.215005 | 0.215005 |
| benders_joint/1 | optimal | 11444 | 11444 | 11444 | True | 0.300976 | 0.18261 | 0.18261 |
| benders_joint/2 | optimal | 11444 | 11444 | 11444 | True | 0.312904 | 0.194246 | 0.194246 |

#### `09-xma-benders-002` · Timing / fixed target=20 seed=None / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.672 秒；进程树提交内存峰值：0.126751GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-002/result.json)；SHA256 `39093fef2788f0767d78292bfaafae9d356f02426f7f5e126099cf9c1ef81be6`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.340352 | 0.213971 | 0.213971 |
| benders_joint/1 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.309412 | 0.18696 | 0.18696 |
| benders_joint/2 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.313362 | 0.19219 | 0.19219 |

#### `09-xma-benders-003` · Timing / fixed target=100 seed=None / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：14 秒；进程树提交内存峰值：0.134426GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-003/result.json)；SHA256 `9b96814b8c01f6acd10863651bc98a4e9d1e72af5a6d1956f2d641dae19ed2ed`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.64672 | 0.663148 | 0.663148 |
| benders_joint/1 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.60697 | 0.627758 | 0.627758 |
| benders_joint/2 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.62625 | 0.630426 | 0.630426 |

#### `09-xma-benders-004` · Timing / fixed target=100 seed=None / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：10.813 秒；进程树提交内存峰值：0.131165GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-004/result.json)；SHA256 `e5f5ed6c69fc1735e99e6a0cc74821685dae37a690f0d94c65f043f7c3dae919`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 0.967788 | 0.637847 | 0.637847 |
| benders_joint/1 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 0.951178 | 0.621186 | 0.621186 |
| benders_joint/2 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 0.97076 | 0.633894 | 0.633894 |

#### `09-xma-benders-005` · Timing / random target=20 seed=20261106 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.641 秒；进程树提交内存峰值：0.126888GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-005/result.json)；SHA256 `bcffcb045f601e1ba9a4ff744c4af5f3cdc904b3e018ffff4099bb1d0866b232`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 5948 | 5948 | 5948 | True | 0.397248 | 0.170157 | 0.170157 |
| benders_joint/1 | optimal | 5948 | 5948 | 5948 | True | 0.330631 | 0.148437 | 0.148437 |
| benders_joint/2 | optimal | 5948 | 5948 | 5948 | True | 0.387568 | 0.144691 | 0.144691 |

#### `09-xma-benders-006` · Timing / random target=20 seed=20261106 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：7.594 秒；进程树提交内存峰值：0.12608GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-006/result.json)；SHA256 `63fd67b9ec54f695f6b56013194cd75f92f0f9d85edcecded7cdc5b0b765f322`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 870000 | 870000 | 870000 | True | 0.288847 | 0.148181 | 0.148181 |
| benders_joint/1 | optimal | 870000 | 870000 | 870000 | True | 0.268688 | 0.143783 | 0.143783 |
| benders_joint/2 | optimal | 870000 | 870000 | 870000 | True | 0.255803 | 0.140357 | 0.140357 |

#### `09-xma-benders-007` · Timing / random target=20 seed=20261107 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.657 秒；进程树提交内存峰值：0.126652GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-007/result.json)；SHA256 `357685eb14649881680b595a4742761d9b062678172549fa02d12e591643f6e7`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.332474 | 0.206095 | 0.206095 |
| benders_joint/1 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.297969 | 0.182429 | 0.182429 |
| benders_joint/2 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.29561 | 0.180725 | 0.180725 |

#### `09-xma-benders-008` · Timing / random target=20 seed=20261107 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.657 秒；进程树提交内存峰值：0.126667GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-008/result.json)；SHA256 `02fb621de3c360704f4cfe78bbdc688456ffcbe601b22aec591e013aca26cbf4`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.32279 | 0.2052 | 0.2052 |
| benders_joint/1 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.31876 | 0.189988 | 0.189988 |
| benders_joint/2 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.302745 | 0.185679 | 0.185679 |

#### `09-xma-benders-009` · Timing / random target=100 seed=20261106 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：11.891 秒；进程树提交内存峰值：0.132034GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-009/result.json)；SHA256 `2ae4c31b0d6f38b05a0b8fad220f915f97f4cb9b19c7016fa7d5ea9b85d009ea`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.06363 | 0.663612 | 0.663612 |
| benders_joint/1 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.09371 | 0.693154 | 0.693154 |
| benders_joint/2 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 1.11013 | 0.698772 | 0.698772 |

#### `09-xma-benders-010` · Timing / random target=100 seed=20261106 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：10.797 秒；进程树提交内存峰值：0.13522GiB。
- 结果与原因：benders_joint: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-010/result.json)；SHA256 `23a1c37666b1412ebcbdc69d6449e5ff0099632df3f61be95a971a11d14161ed`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.00726 | 0.703342 | 0.703342 |
| benders_joint/1 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.00933 | 0.700241 | 0.700241 |
| benders_joint/2 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 1.11801 | 0.79141 | 0.79141 |

#### `09-xma-benders-011` · Timing / random target=100 seed=20261107 / tianchi_2017 / benders_joint

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_joint","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.64 秒；进程树提交内存峰值：0.129559GiB。
- 结果与原因：benders_joint: infeasible, infeasible, infeasible; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-011/result.json)；SHA256 `12a83d8c0a1b54fedcf02d96e5e9fb50001828aeb00d607e7f8dded59a980fc6`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.373779 | 缺失 | 缺失 |
| benders_joint/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.389316 | 缺失 | 缺失 |
| benders_joint/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.38856 | 缺失 | 缺失 |

#### `09-xma-benders-012` · Timing / random target=100 seed=20261107 / air_linear_v1 / benders_joint

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_joint","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.64 秒；进程树提交内存峰值：0.130131GiB。
- 结果与原因：benders_joint: infeasible, infeasible, infeasible; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-012/result.json)；SHA256 `afe6ea30ee949518ced508f7e6983266238a0f7fc4d9ba1ea315af928103eff3`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.381564 | 缺失 | 缺失 |
| benders_joint/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.371666 | 缺失 | 缺失 |
| benders_joint/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.397798 | 缺失 | 缺失 |

#### `09-xma-benders-013` · Stress / benders_joint / fixed target=100 / grid60 max120

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/270 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}`。
- 观测墙钟：6.5 秒；进程树提交内存峰值：0.133766GiB。
- 结果与原因：benders_joint: optimal; objective=56897.62037037037; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-013/result.json)；SHA256 `1e5e9a5188e497d1a21e763660fb37f7233156868112ee10ef2626db22c596fe`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 1.61905 | 0.648931 | 0.648931 |

#### `09-xma-benders-014` · Stress / benders_joint / fixed target=500 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：3600/3570 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}`。
- 观测墙钟：3592.44 秒；进程树提交内存峰值：0.669338GiB。
- 结果与原因：benders_joint: not_converged; objective=None; 停止原因=master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-014/result.json)；SHA256 `a16b0459d7b38b8750deeafc97a611265fd3c3013e917fccab383cf73c945ac2`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | not_converged | 缺失 | 197032 | 缺失 | 缺失 | 3585.53 | 缺失 | 缺失 |

#### `09-xma-benders-015` · Stress / benders_joint / fixed target=2364 / grid60 max120

- 执行状态：`passed`；结论：**求解器认证不可行**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_joint"}`。
- 观测墙钟：16.063 秒；进程树提交内存峰值：0.138573GiB。
- 结果与原因：benders_joint: infeasible; objective=None; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-015/result.json)；SHA256 `db7c1dd1342227d32f5c9fe8be4aa42086d73c64926aca0fb81bc7b016672e69`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 6.16915 | 缺失 | 缺失 |

#### `09-xma-benders-016` · Stress / benders_joint / fixed target=100 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：900/870 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_joint"}`。
- 观测墙钟：875.235 秒；进程树提交内存峰值：0.819092GiB。
- 结果与原因：benders_joint: not_converged; objective=42473.56481481481; 停止原因=master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-016/result.json)；SHA256 `1a49d597261b52132d0746d60e38af2576811d41c82c09ed924e98624ba4e011`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | not_converged | 42473.6 | 42460.6 | 42473.6 | True | 870.421 | 137.131 | 137.131 |

#### `09-xma-benders-017` · Stress / benders_joint / fixed target=500 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_joint"}`。
- 观测墙钟：1324.03 秒；进程树提交内存峰值：0.253166GiB。
- 结果与原因：benders_joint: not_converged; objective=None; 停止原因=benders_iteration_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/09-xma-benders-017/result.json)；SHA256 `61c685214cb1ef81ebf0f6d82db3804693cbc8f5ab8d749ec4c555e06ba76a30`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_joint/0 | not_converged | 缺失 | 91004.2 | 缺失 | 缺失 | 1313.61 | 缺失 | 缺失 |

### 10 XMA - Benders CG BP

#### `10-xma-cg-bp-001` · Timing / fixed target=20 seed=None / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.625 秒；进程树提交内存峰值：0.126793GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-001/result.json)；SHA256 `0d7c6809624b7f687fee1f01d12688e77e12f2366b45c06f43181739ccd29391`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 11444 | 11444 | 11444 | True | 0.36453 | 0.187964 | 0.187964 |
| benders_cg_bp/1 | optimal | 11444 | 11444 | 11444 | True | 0.346357 | 0.171247 | 0.171247 |
| benders_cg_bp/2 | optimal | 11444 | 11444 | 11444 | True | 0.337613 | 0.16645 | 0.16645 |

#### `10-xma-cg-bp-002` · Timing / fixed target=20 seed=None / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":20,"seed":null,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.703 秒；进程树提交内存峰值：0.12627GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-002/result.json)；SHA256 `7938d98a588104b79ec6f84832f27ac2610be74bd13a13447694bf04c582d359`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.409336 | 0.223063 | 0.223063 |
| benders_cg_bp/1 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.354562 | 0.166493 | 0.166493 |
| benders_cg_bp/2 | optimal | 1.3025e+06 | 1.3025e+06 | 1.3025e+06 | True | 0.359475 | 0.181235 | 0.181235 |

#### `10-xma-cg-bp-003` · Timing / fixed target=100 seed=None / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：171.672 秒；进程树提交内存峰值：0.161572GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-003/result.json)；SHA256 `803e1a943837bd350fc7f169cda97b2d426169ee994bd24005de38d0794e3057`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 42.0747 | 23.7637 | 23.7637 |
| benders_cg_bp/1 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 41.2552 | 22.6716 | 22.6716 |
| benders_cg_bp/2 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 41.213 | 22.7644 | 22.7644 |

#### `10-xma-cg-bp-005` · Timing / random target=20 seed=20261106 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.672 秒；进程树提交内存峰值：0.127861GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-005/result.json)；SHA256 `8f74c03525759273779914fc0b9a7c7168b6614ad8d0aa72d866ee713fd84301`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 5948 | 5948 | 5948 | True | 0.477618 | 0.145507 | 0.145507 |
| benders_cg_bp/1 | optimal | 5948 | 5948 | 5948 | True | 0.473105 | 0.144184 | 0.144184 |
| benders_cg_bp/2 | optimal | 5948 | 5948 | 5948 | True | 0.484848 | 0.147205 | 0.147205 |

#### `10-xma-cg-bp-006` · Timing / random target=20 seed=20261106 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261106,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.625 秒；进程树提交内存峰值：0.126595GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-006/result.json)；SHA256 `12df2b696e27bc3e80bd04c297e2f821fe52e2067bc7e34095d273d0918792b7`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 870000 | 870000 | 870000 | True | 0.273506 | 0.149919 | 0.149919 |
| benders_cg_bp/1 | optimal | 870000 | 870000 | 870000 | True | 0.2718 | 0.152025 | 0.152025 |
| benders_cg_bp/2 | optimal | 870000 | 870000 | 870000 | True | 0.263266 | 0.145176 | 0.145176 |

#### `10-xma-cg-bp-007` · Timing / random target=20 seed=20261107 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：9.735 秒；进程树提交内存峰值：0.128529GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-007/result.json)；SHA256 `fae0e24d153068f74dd545c1cf73c91ffffbf5e665d938223a008ab4b2fd06ab`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.671952 | 0.160186 | 0.160186 |
| benders_cg_bp/1 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.664367 | 0.153813 | 0.153813 |
| benders_cg_bp/2 | optimal | 19745.6 | 19745.6 | 19745.6 | True | 0.711517 | 0.151704 | 0.151704 |

#### `10-xma-cg-bp-008` · Timing / random target=20 seed=20261107 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":20,"seed":20261107,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.656 秒；进程树提交内存峰值：0.128147GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-008/result.json)；SHA256 `2e14d59c3d13e536787667f5b0870b883c8f2b7857439e8fa911e74a2cc625aa`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.341884 | 0.176841 | 0.176841 |
| benders_cg_bp/1 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.328186 | 0.153095 | 0.153095 |
| benders_cg_bp/2 | optimal | 2.92551e+06 | 2.92551e+06 | 2.92551e+06 | True | 0.324201 | 0.15591 | 0.15591 |

#### `10-xma-cg-bp-004` · Timing / fixed target=100 seed=None / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"fixed","size":100,"seed":null,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：36.609 秒；进程树提交内存峰值：0.139736GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-004/result.json)；SHA256 `db9539dce35200216966f0f1ee8742e5026c88bf02e56e47fce5ff449b2ce90b`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 7.4839 | 7.13631 | 7.13631 |
| benders_cg_bp/1 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 7.45988 | 7.12542 | 7.12542 |
| benders_cg_bp/2 | optimal | 8.4375e+06 | 8.4375e+06 | 8.4375e+06 | True | 7.41561 | 7.08807 | 7.08807 |

#### `10-xma-cg-bp-009` · Timing / random target=100 seed=20261106 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：131.016 秒；进程树提交内存峰值：0.145996GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-009/result.json)；SHA256 `7cb1fe6b1c53292615f8cfa52b4bbb77fbae6d4c08975a431b4b698e1940e440`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 30.7041 | 30.2938 | 30.2938 |
| benders_cg_bp/1 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 30.4931 | 30.0915 | 30.0915 |
| benders_cg_bp/2 | optimal | 43465.7 | 43465.7 | 43465.7 | True | 31.0502 | 30.6348 | 30.6348 |

#### `10-xma-cg-bp-010` · Timing / random target=100 seed=20261106 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261106,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：22.625 秒；进程树提交内存峰值：0.14267GiB。
- 结果与原因：benders_cg_bp: optimal, optimal, optimal; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-010/result.json)；SHA256 `910a7bc89b8e4bd5edfc83a5892ac413aa59ada00a412f7401add834783df646`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 3.87687 | 3.55473 | 3.55473 |
| benders_cg_bp/1 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 3.79223 | 3.46223 | 3.46223 |
| benders_cg_bp/2 | optimal | 6.82e+06 | 6.82e+06 | 6.82e+06 | True | 3.75563 | 3.4407 | 3.4407 |

#### `10-xma-cg-bp-011` · Timing / random target=100 seed=20261107 / tianchi_2017 / benders_cg_bp

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_cg_bp","objective":"tianchi_2017","step":60,"delay":120}`。
- 观测墙钟：8.688 秒；进程树提交内存峰值：0.129692GiB。
- 结果与原因：benders_cg_bp: infeasible, infeasible, infeasible; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-011/result.json)；SHA256 `f4c30deb17837137ea3348f3ab781dd60010490b5e0c4c6f6a585095fba20e77`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.38009 | 缺失 | 缺失 |
| benders_cg_bp/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.353976 | 缺失 | 缺失 |
| benders_cg_bp/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.394595 | 缺失 | 缺失 |

#### `10-xma-cg-bp-012` · Timing / random target=100 seed=20261107 / air_linear_v1 / benders_cg_bp

- 执行状态：`completed`；结论：**求解器认证不可行**。
- 类型：`xma_timing`；阶段：`performance`；单例墙钟/求解器预算：600/90 秒；提交内存上限：2.5GiB。
- 参数：`{"mode":"random","size":100,"seed":20261107,"algorithm":"benders_cg_bp","objective":"air_linear_v1","step":60,"delay":120}`。
- 观测墙钟：8.671 秒；进程树提交内存峰值：0.129189GiB。
- 结果与原因：benders_cg_bp: infeasible, infeasible, infeasible; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-012/result.json)；SHA256 `c0eb72cfa16840ff37a6695c3afe28423b1cae67d75dcf105b114f7e1e26b092`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.365244 | 缺失 | 缺失 |
| benders_cg_bp/1 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.372836 | 缺失 | 缺失 |
| benders_cg_bp/2 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 0.383994 | 缺失 | 缺失 |

#### `10-xma-cg-bp-013` · Stress / benders_cg_bp / fixed target=100 / grid60 max120

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：300/270 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：46.172 秒；进程树提交内存峰值：0.145149GiB。
- 结果与原因：benders_cg_bp: optimal; objective=56897.62037037037; 停止原因=integer_recourse_and_global_master_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-013/result.json)；SHA256 `c3008afa074be9b96d86cb566f44098598c510eab8f3f45e429a0cbf8a3f6d57`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | optimal | 56897.6 | 56897.6 | 56897.6 | True | 40.9401 | 22.3172 | 22.3172 |

#### `10-xma-cg-bp-014` · Stress / benders_cg_bp / fixed target=500 / grid60 max120

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：3600/3570 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：3577.97 秒；进程树提交内存峰值：0.7593GiB。
- 结果与原因：benders_cg_bp: not_converged; objective=None; 停止原因=master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-014/result.json)；SHA256 `7c3ffefb0c4b7e2f3a07ff1f4d184c6065b119e748fe1e9feae4702bd46613bb`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 197032 | 缺失 | 缺失 | 3570.37 | 缺失 | 缺失 |

#### `10-xma-cg-bp-015` · Stress / benders_cg_bp / fixed target=2364 / grid60 max120

- 执行状态：`passed`；结论：**求解器认证不可行**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":2364,"mode":"fixed","step":60,"delay":120,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：16 秒；进程树提交内存峰值：0.13821GiB。
- 结果与原因：benders_cg_bp: infeasible; objective=None; 停止原因=certified_master_infeasible。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-015/result.json)；SHA256 `b41ba49830a566a9b4ada1fc756156e7434cd29115444c7cf0259b4bb4a08e0d`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | infeasible | 缺失 | 缺失 | 缺失 | 缺失 | 6.0903 | 缺失 | 缺失 |

#### `10-xma-cg-bp-016` · Stress / benders_cg_bp / fixed target=100 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：900/870 秒；提交内存上限：2.5GiB。
- 参数：`{"size":100,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：875.469 秒；进程树提交内存峰值：0.893291GiB。
- 结果与原因：benders_cg_bp: not_converged; objective=42473.56481481481; 停止原因=master_not_optimal。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-016/result.json)；SHA256 `c7fd2439034625b51f00b04a65c4bb1978f7eb51338ec83bd6fc69276137dc34`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | not_converged | 42473.6 | 42457.6 | 42473.6 | True | 870.373 | 177.715 | 177.715 |

#### `10-xma-cg-bp-017` · Stress / benders_cg_bp / fixed target=500 / grid30 max1440

- 执行状态：`inconclusive`；结论：**未得到确定结论**。
- 类型：`xma_scale`；阶段：`stress`；单例墙钟/求解器预算：7200/7170 秒；提交内存上限：4GiB。
- 参数：`{"size":500,"mode":"fixed","step":30,"delay":1440,"algorithm":"benders_cg_bp"}`。
- 观测墙钟：7179.41 秒；进程树提交内存峰值：0.525799GiB。
- 结果与原因：benders_cg_bp: not_converged; objective=None; 停止原因=bp_budget_or_node_limit。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/10-xma-cg-bp-017/result.json)；SHA256 `08f70e09d130193502e3524e100eca2a270150370a03d54aac989d2de743070a`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_cg_bp/0 | not_converged | 缺失 | 91004.2 | 缺失 | 缺失 | 7170.27 | 缺失 | 缺失 |

### 11 AIR - P1 P2 P3 P4 P5 stress

#### `11-air-stress-001` · P1-seconds

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：60/50 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P1-seconds.json"}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0737953GiB。
- 结果与原因：optimal, LB=18080.0, UB=18080.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/11-air-stress-001/result.json)；SHA256 `e35b169c3add099e67940cc56122bc1fb0a1b18ff75a05443028f040014213d2`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 18080 | 18080 | 18080 | True | 缺失 | 0.247699 | 0.247699 |

#### `11-air-stress-002` · P2-tens-seconds

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：180/170 秒；提交内存上限：1.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P2-tens-seconds.json"}`。
- 观测墙钟：2.187 秒；进程树提交内存峰值：0.0761719GiB。
- 结果与原因：optimal, LB=600.0, UB=600.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/11-air-stress-002/result.json)；SHA256 `7473aa6ae2b677afec69e419abc388c461f43721ac13a0bfa802f6d7d46ecaf9`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 600 | 600 | 600 | True | 缺失 | 0.424892 | 0.424892 |

#### `11-air-stress-003` · P3-minutes

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：600/590 秒；提交内存上限：2.5GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P3-minutes.json"}`。
- 观测墙钟：3.234 秒；进程树提交内存峰值：0.0907822GiB。
- 结果与原因：optimal, LB=1980.0, UB=1980.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/11-air-stress-003/result.json)；SHA256 `0e4a4300449b8c3236e7af385be7b91416700df9ce97508b1b37d83bdaad42ff`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 1980 | 1980 | 1980 | True | 缺失 | 1.99359 | 1.99359 |

#### `11-air-stress-004` · P4-tens-minutes

- 执行状态：`passed`；结论：**审计、目标与上下界闭合的最优解**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：1800/1790 秒；提交内存上限：4GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P4-tens-minutes.json"}`。
- 观测墙钟：61.734 秒；进程树提交内存峰值：0.109783GiB。
- 结果与原因：optimal, LB=4440.0, UB=4440.0; 停止原因=phase11_lp_integer_bound_closed。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/11-air-stress-004/result.json)；SHA256 `f8236e7c7207dc3d6c9655f8c615ee6b51022371191241ba209d93f95b6c91e3`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | optimal | 4440 | 4440 | 4440 | True | 缺失 | 59.5957 | 59.5957 |

#### `11-air-stress-005` · P5-hours

- 执行状态：`license_limited`；结论：**许可证受限**。
- 类型：`air_stress`；阶段：`stress`；单例墙钟/求解器预算：7200/7190 秒；提交内存上限：4GiB。
- 参数：`{"path":"data/validation_suite/frozen/stress/P5-hours.json"}`。
- 观测墙钟：2.218 秒；进程树提交内存峰值：0.084301GiB。
- 结果与原因：Gurobi 10010 size limit; not an algorithm correctness failure; 停止原因=phase11_aborted。
- 原始证据：[result.json](../../.workbench/validation_campaigns/20261107_151057_repair/jobs/11-air-stress-005/result.json)；SHA256 `8cf1cb605f179049163cc60c810db3a746245a893830577c69569237f082fc67`。

| 算法/重复 | 优化状态 | 目标 | 全局 LB | 全局 UB | 审计 | 耗时/秒 | 首次全局候选/秒 | 首次审计可行/秒 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| benders_branch_and_price_v1/ | aborted | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |

## 7. 修复方向与复测要求

已观察到的真实样本问题优先由对应事件和停止原因定位，不按未收敛实例的 incumbent 大小判定单调性错误。
若 Benders 多次排除完整不可行计划却没有全局可行上界，应检查可行性割的泛化能力、资源松弛是否缺失，以及可行解初始化。该项是待验证的性能根因，不能凭日志将其认定为数学正确性错误。
AIR 压力任务也需检查完整计划条件割是否造成反复枚举，以及全局时限是否仅分配到单个子求解。保留硬停前的全局界，修复时争取在预算内正常返回可审计方案与未闭合状态。
修复须保留真正的列生成、整数分支与全局界证明，不将算法名称改为直接模型调用来获得表面通过。新增割应以小规模穷举或 Oracle 检查对所有可行计划有效。
修复后执行相关单元/API/回归、小例子四算法双目标对拍、原先未收敛的同输入同预算复测，以及递增压力；保留旧结果、新结果、修复内容和仍受限项目。
许可证、依赖和机器内存的外部限制需单列；不能通过取消审计、放宽业务约束或将预检当作求解来消除失败。
