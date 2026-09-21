# AIR Workbench 数据与 UI 改进工作报告

- 时间：2026-09-20 12:41:34（Asia/Shanghai）
- 分支：`feature/air-workbench-data-ui-improvements`
- 基线：`air-workbench-v1` / `f75e66fcf05c734d315ed7e90d6f7cfc4a2a8346`
- 参考说明：`docs/chatgpt_review/AIR_WORKBENCH_DATA_UI_IMPROVEMENT_DIRECTION.md`

## 本次完成内容

1. 新增统一验证 Case catalog：
   - `benchmark-disruption-recovery`
   - `crew-recovery-integrality`
   - `passenger-capacity-constrained`
   - `passenger-capacity-relaxed`
   - `delay-cost-cancellation-tradeoff`
   - `solve-ready-infeasible`
   - `scenario-only-minimal`
   - `invalid-missing-airport`
2. 每个 catalog 条目显式声明 Case 分类、输入模式、数据来源与 Expected；完整 Case 统一组装 Scenario、Recovery Columns、Passenger Capacity、Cost Overrides、Algorithm Profiles 和 Expected。
3. 正式 Solve Bundle 在装载时清空 Aircraft Strings / Crew Pairings，不把预生成资源列作为正式求解输入；保留显式 Flight Options 与 Passenger Itineraries。
4. 新增 `GET /api/cases` 与 `GET /api/cases/{case_id}`，并保持原 `/api/solve/example-bundle/{case_id}` 兼容入口。
5. 前端从 benchmark-oriented 页面升级为 Current Case Workbench：
   - Case selector 按 Core / Validation / Boundary / Scenario-only 分类；
   - Data、Visualization、Recovery、Costs、Constraints 始终读取同一 Current Case；
   - 顶部持续显示 Case、Scenario、Solve Input、Solver、Result 五类状态；
   - 展示 Load → Validate → Readiness → Solve → Audit 工作流；
   - 区分 Scenario Validation、Solve Readiness 与 Optimization Result。
6. 新增结果 revision 生命周期：输入改变后旧结果标为 `STALE`，禁止结果导出，重新求解后才成为 current result。
7. `Reset Current Case` 会恢复 Scenario、Columns、Capacity 与 Case 自带 Cost Overrides；不再错误清空为全局默认。
8. 将 `Import Scenario` 与 `Import Solve Bundle` 拆分为两个语义明确的入口；Scenario-only 不会静默补成 Solve Bundle。
9. `Export Current Case` 按 `current_case / scenario / solve_input / result` 分层输出，并记录 input/result revision。
10. README 已更新为 Case Workbench 的使用方式、API、数据边界和结果生命周期说明。

## 验证数据与 Expected 校准

所有 solve-ready Case 均通过实际 Phase 12 exact solver 对拍：

- Benchmark disruption recovery：`optimal`，objective `18080.0`；
- Crew recovery integrality：`optimal`，objective `95200.0`；
- Passenger capacity constrained：`optimal`，objective `1010.0`；
- Passenger capacity relaxed：`optimal`，objective `0.0`；
- Delay cost trade-off：`optimal`，objective `25000.0`；
- Solve-ready but infeasible：输入预检查 READY，优化结果 `infeasible`。

Scenario-only 与 invalid fixture 分别验证“场景有效但不具备 Solve 输入”和“场景验证失败”两类边界。

## 测试与检查

- `git diff --check`：通过；
- `node --check frontend/js/app.js`：通过；
- Case/API/acceptance/frontend 定向测试：通过；
- `python -m pytest -q`：完整测试集通过（100%）；
- 核心算法边界检查：`backend/core/` 无改动。

测试覆盖新增：

- Case catalog 与所有 Case loading；
- 完整 Solve Bundle 的一致性；
- Cost sensitivity 与 Capacity sensitivity 单变量差异；
- Scenario-only 与 invalid input；
- Valid + Ready + Infeasible；
- Expected objective、关键 Flight Options 与 metrics；
- 前端 result stale、revision、reset baseline 与 Scenario-only 状态。

## 版本控制状态

工作保留在新分支 `feature/air-workbench-data-ui-improvements`，未创建提交、未推送，也未修改原 `main` 或 `air-workbench-v1` 标签。参考任务说明文件仍保持为未跟踪输入文件，未覆盖其内容。

## 已知边界

- 优化求解仍为同步 exact solver，保持研究工作台定位；
- `PRECHECK READY` 仅表示输入就绪，不代表优化可行；
- 未改变 Phase 12/13 数学模型、核心求解算法或 Gurobi 适配逻辑；
- 旧 benchmark constraints API 继续保留用于兼容，但新前端不再将其作为隐式数据 fallback。
