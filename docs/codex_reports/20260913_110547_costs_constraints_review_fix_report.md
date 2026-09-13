# Costs + Constraints Review Fix Report

## 修补内容

- Workbench 默认加载 `phase1_benchmark_001`。
- 新增 `GET /api/model/constraints/benchmark-inputs`，从 canonical JSON 提供 Recovery Columns 与 Passenger Capacity Profile。
- 前端 Constraints Precheck 现在同时发送 Scenario、Recovery Columns、Passenger Capacity Profile。
- 导入非 benchmark Scenario 时清空不匹配的 Columns/Capacity，自动进入 Scenario-only 降级模式。
- 无 Columns 时不再对 20 条约束统一 Warning 后提前结束；Scenario 可检查项继续执行，其余依赖项分别 Warning。
- README 的一级视图说明已改为 Data / Visualization / Costs / Constraints。

## 验证结果

- Constraint metadata：20 条，SRM/ARM/CRM/PRM 均存在。
- 完整 benchmark precheck：16 Passed / 4 Warning / 0 Failed。
- Scenario-only precheck：3 Passed / 17 Warning / 0 Failed。
- `PRECHECK != MIP FEASIBILITY` 语义保持不变。
- Costs contract、override immutable 和 owner metadata 测试继续通过。
- HTTP 实测 benchmark inputs 与完整 precheck 正常。

## 浏览器检查

computer-use 环境返回 `apps: []`、`browsers: []`，Chrome 与 Edge 均为 unavailable，因此无法完成真实浏览器 console 检查。JS syntax、Node contract tests、HTTP static/API smoke 均通过，但不能替代真实浏览器验收。

## 结论

Workbench review fix 的代码与自动化验收通过；真实浏览器 console 验收受当前环境限制待补。
