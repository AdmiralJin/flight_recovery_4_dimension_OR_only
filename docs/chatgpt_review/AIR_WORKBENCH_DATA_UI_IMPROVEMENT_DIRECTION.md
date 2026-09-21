# AIR Recovery Workbench：数据与浏览器改进方向

## 1. 目标
基于当前 `main` 的 Phase 13 状态，在**不改动核心优化算法逻辑**的前提下推进两件事：
1. 建立一套系统化、可核验的验证数据；
2. 将当前偏 benchmark 的浏览器页面升级为通用 Case Workbench。
本任务以工程整合、验证和可用性提升为主，不重新设计 Phase 12/13 数学模型。

## 2. 数据生成方向
后续不要只生成 Scenario，而应围绕“一个可独立运行、可核验的 Case”组织。
每个正式验证 Case 原则上包含：
```text
Scenario
Recovery Columns
Passenger Capacity
Cost / Profile 配置
Expected / Oracle
```
应遵循当前正式 Solve contract：
- Flight Options 作为输入提前提供；
- 有旅客时提供必要的 Passenger Itineraries；
- Capacity Profile 完整；
- Cost/Profile IDs 与当前程序一致；
- 不把预生成 Aircraft Strings / Crew Pairings 作为正式 Solve 输入；
- 数据通过现有 Schema、Validator 和 Solve Precheck。

### 建议覆盖的 Case
```text
Baseline
单航班延误传播
延误 vs 取消
Aircraft Recovery / Swap
Crew Recovery
Passenger Connection / Reaccommodation
Airport Capacity
Cost Sensitivity
Capacity Sensitivity
Invalid / Incomplete Input
Valid + Solve Ready + Infeasible
```
案例数量和具体形式可根据现有模型能力调整。

### 数据设计原则
1. **小规模、可解释**：人工能理解主要恢复决策，方便定位错误。
2. **尽量单变量**：敏感性 Case 只改变一个关键因素，如取消成本、机组成本或剩余座位容量。
3. **Expected 可核验**：不只检查 `optimal`，还应核验关键 Flight Options、取消/延误、资源恢复、旅客结果和目标值。
4. **区分三类状态**：`Scenario Valid`、`Solve Input Ready`、`Optimization Feasible / Infeasible`。
5. **便于回归**：Case 可直接进入 pytest / batch acceptance，后续修改可快速发现行为变化。

### 数据组织原则
不强制具体目录，但建议按统一 Case ID 对应：
```text
Scenario / Columns / Capacity / Bundle / Expected / Negative-Boundary
```
核心要求：**一个 Case 的 Scenario、Columns、Capacity、Cost/Profile 和 Expected 必须保持一致。**

## 3. 浏览器改进方向
当前浏览器仍明显围绕 `phase1_benchmark_001` 工作，应升级为真正的多 Case Workbench。
核心目标：**所有页面始终围绕同一个 Current Case 工作。**
建议统一维护：
```text
Current Case
├── Scenario
├── Recovery Columns
├── Passenger Capacity
├── Cost Overrides
├── Algorithm Profiles
├── Solve Readiness
└── Recovered Result
```
具体状态结构由 Codex 根据现有代码决定。

## 4. Case 加载
浏览器应支持选择不同 Case，而不是固定加载 benchmark。
建议提供 Case selector，例如：
```text
Core Examples
Validation Cases
Boundary Cases
Scenario-only Cases
```
分类方式可以调整。
选择 Case 后，应同步加载 Scenario、Columns、Capacity、Cost Overrides 和 Profiles。
必须避免不同页面引用不同 Case 数据，例如：
```text
Scenario = Case B
Constraints = benchmark capacity
Recovery Columns = Case A
```

## 5. 浏览器工作流
现有 `Data / Visualization / Recovery / Costs / Constraints` 五个一级视图可以保留。
整体逻辑应更清楚地体现：
```text
Load Case
→ Validate Scenario
→ Check Solve Readiness / Constraints
→ Solve
→ Recovery / Audit
```
不要求做成严格向导，只需让用户明确当前阶段。

## 6. 状态显示
建议顶部长期显示：`Case / Scenario / Solve Input / Solver / Result`。
重点分开 `Scenario Validation`、`Solve Readiness`、`Optimization Result`。
不能把 `Precheck READY` 解释成 `Optimization Feasible`。

## 7. Result 生命周期
需要解决“输入变化后旧结果仍像当前结果”的问题。
建议引入 revision、dirty state 或等价机制：
```text
Solve → 得到 Result
修改 Scenario / Cost / Capacity / 其他 Solve 输入
→ 原 Result 失效或标记 STALE
重新 Solve → 产生新的有效 Result
```
具体实现方式不限制。

## 8. Reset / Import / Export
这些功能应围绕 Current Case 统一处理：
- Reset 恢复当前 Case 的加载基线；
- Case 自带 Cost Override 时不要错误清空为全局默认；
- Import Scenario 与 Import Solve Bundle 保持语义区别；
- Scenario-only 数据不要被静默补成另一个 Solve Bundle；
- Export 的内容层级清晰。
具体按钮和格式由 Codex 自行设计。

## 9. 各视图的数据一致性
`Costs / Constraints / Visualization / Recovery` 不需要大改功能边界，重点是统一数据来源。
要求全部读取 Current Case，不再依赖固定 benchmark 输入作为隐式 fallback。
保留现有语义：
```text
PRECHECK != OPTIMIZATION FEASIBILITY
Visualization = Original Plan + Disruption + Risk
Recovery = Solver Result
```

## 10. 测试方向
在现有测试基础上增加系统级回归，重点覆盖：
```text
Case catalog / Case loading
完整 Solve Bundle 加载
Cost sensitivity
Capacity sensitivity
Scenario-only
Invalid / incomplete input
Valid + Ready + Infeasible
输入变化后 Result 失效
Reset 恢复当前 Case baseline
```
测试形式由 Codex 根据现有项目结构决定。
建议保持三层验证：`Python/API tests`、`Validation Case acceptance`、`Frontend state/interaction tests`。

## 11. 实施边界
原则上不要修改 `backend/core/` 以及 Phase 12/13 已验证的核心数学逻辑，除非实际集成发现明确 bug 且有充分测试依据。
优先修改范围：
```text
Validation Data
API / Application glue
Frontend state
Case loading
UI workflow
Regression tests
Documentation
```

## 12. 最终目标
最终应达到：
> 每个正式 Case 都是一套完整、可复现、可核验的 Solve 输入与 Expected；浏览器可以稳定切换 Case，并保证 Scenario、Columns、Capacity、Costs、Constraints 和 Recovery 始终属于同一个 Current Case。
```text
数据层：零散 toy / benchmark fixtures → 系统验证 Case 集
浏览器：Benchmark-oriented page → Case-oriented Recovery Workbench
```
Codex 可根据仓库实际结构自行选择最合适的具体实现方案，不要求严格照搬某一种目录、类或前端状态结构。
