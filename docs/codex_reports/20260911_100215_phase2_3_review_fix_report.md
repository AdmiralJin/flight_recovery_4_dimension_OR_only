# Phase 2.3 Review Fix Report

时间：2026-09-11 10:02:15（Asia/Shanghai）

## 1. Review Finding

原 SRM → ARM benchmark 直接复制 `selected_option_by_flight.values()`。该写法会把合法的 CANCEL option 误传为需要 aircraft/crew 执行的航班，模型间 schedule handoff 合同不完整。

## 2. Handoff Contract

新增 pure `extract_required_operated_option_ids(srm_result, columns)`：

- 仅输出有 `base_flight_id` 的 revenue OPERATE option；
- 合法 CANCEL option 正常过滤；
- unknown option、ferry、base-flight mapping 不一致、重复或缺失 selection 均 fail fast；
- 输出按 Columns 的 base-flight 首次出现顺序保持确定性；
- ARM benchmark 改为复用该 canonical schedule → resource recovery handoff。

合同与失败语义已登记到 `assumptions.md` A-033。

## 3. Cancellation Regression

新增三航班回归合同：F1 原始运营、F2 取消、F3 延误运营。提取结果严格为 F1/F3，且 `AircraftRecoveryRequest` 可接受该结果。另覆盖 unknown、ferry、base mismatch、missing、duplicate 与 unsolved SRM result。

## 4. Documentation Changes

更新 `README.md` 与 `docs/AIR_HTML_Python_Reproduction_Plan.md`：SRM/ARM 已实现 Phase 2 fixed-column test cost contract；当前系数仍为 `abstract_cost_units`，不代表生产成本；CRM/PRM owned costs 与完整联合目标尚未全部进入正式模型。

## 5. Tests

- `tests/unit/test_recovery_handoff.py`
- `tests/regression/test_phase2_arm_benchmark_001.py`

聚焦结果：9 passed，0 failed，0 skipped。

## 6. Full Pytest

命令：`pytest -q`

结果：188 passed，0 failed，0 skipped；仅有 1 条既有 Starlette/httpx deprecation warning。

## 7. Gurobi Integration

命令：`pytest -q tests/regression/test_phase2_gurobi_integration_gate.py`

结果：1 passed，0 failed，0 skipped。Gurobi version：13.0.3。Integration executed：yes。

## 8. Phase 2.3 Final Status

验收项全部满足：canonical extractor、取消过滤、fail-fast、ARM regression 复用、文档同步、完整测试与真实 Gurobi gate 均通过。

**Phase 2.3 FINAL PASS**
