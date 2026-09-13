# Costs + Constraints 可视化工作台实施计划

> 目标：在现有 AIR Recovery HTML Workbench 中新增 Costs 与 Constraints 两个可视化工作区，用于人工查看、编辑、校验和审计 Phase 2 已建立的模型成本与约束。
> 本任务只扩展数据与参数工作台，不接入正式 Solve，不修改 SRM、ARM、CRM、PRM 数学逻辑，不进入 Phase 3 Integrated Oracle。

## 1. 当前基线

当前前端仍以 Data Editor 与 Visualization 为两个一级视图，主要编辑 Scenario、Airports、Flights、Aircraft、Crew、Passengers、Airport Capacity 和 Disruptions。当前 `frontend/index.html` 仍含早期 Phase 0.5 文案，应更新为长期可用的 Workbench 表述。

当前 `frontend/js/app.js` 主要只有 Scenario `state` 与 `baseline`。本任务需要将 Scenario、Cost、Constraint Metadata 分开管理，禁止把 Cost Config 或 Constraint 定义塞进 Scenario Schema。

## 2. 本任务目标

新增两个一级视图：

```text
Data
Visualization
Costs
Constraints
```

Costs 用于查看 canonical cost profile、编辑实验 override、显示 baseline / effective value / unit / owner / source，并支持校验、重置和 Workbench Config 导出。

Constraints 用于查看 SRM、ARM、CRM、PRM 的约束、来源、公式摘要、依赖字段、assumption、当前数据参数和 deterministic precheck 状态。

## 3. 强制边界

不得：

```text
修改 SRM / ARM / CRM / PRM 公式
加入 Integrated Oracle
加入 Benders / Column Generation
动态生成 Recovery Columns
启用正式 /api/solve
展示伪优化结果
修改 Manual Reference 语义
```

约束公式必须以后端 metadata / registry 为单一真源，禁止在 JavaScript 中复制另一套数学定义。

## 4. 页面与状态

页面建议：

```text
AIR Recovery Workbench
Scenario · Costs · Constraints · Validation
```

删除硬编码 Phase 0.5 与当前版本不会运行任何优化等过时描述。

状态建议显示：

```text
Scenario       Valid / Modified / Not checked
Costs          Baseline / Modified / Invalid
Constraints    SRM / ARM / CRM / PRM
```

建议将前端状态重构为：

```javascript
workbenchState = {
  scenario,
  costBaseline,
  costOverrides,
  costEffective,
  constraintMetadata,
  capacityProfileSummary
}
```

不要求使用精确对象名，但必须职责分离。

## 5. Costs 单一真源

Canonical profile：

```text
data/costs/phase2_test_costs_v1.json
```

已有：

```text
schema_version
cost_profile_id
source
units
coefficients
notes
```

每项 coefficient 已包含：

```text
value
unit
owner
source
source_reference
notes
```

前端直接消费现有 contract，不重新定义成本语义。

## 6. Costs API 与 Override

建议新增：

```text
GET  /api/config/costs
POST /api/config/costs/validate-overrides
```

新增 `CostOverrideConfig`：

```text
base_cost_profile_id
overrides
```

规则：

```text
key 必须存在
value 必须 finite 且 >= 0
不得修改 owner / unit / canonical source / source_reference
```

建议 pure function：

```python
apply_cost_overrides(...)
```

不得 mutation baseline。

浏览器修改默认只保留在 Workbench State，不自动写回 `data/costs/*.json`。

## 7. Costs UI

按 Owner 分组：

```text
SRM
ARM
CRM
PRM
```

表格至少显示：

| Coefficient | Meaning | Baseline | Override | Effective | Unit | Source |
|---|---|---:|---:|---:|---|---|

每项可展开：

```text
owner
source
source_reference
notes
```

状态 Badge 至少：

```text
PAPER
IMPLEMENTATION ASSUMPTION
USER OVERRIDE
```

USER OVERRIDE 不能覆盖 canonical source，只表示当前实验值被改写。

操作至少：

```text
Validate Costs
Reset Cost Overrides
Export Workbench Config
```

建议将现有 Export / Reset 明确区分为：

```text
Export Scenario
Export Workbench Config
Reset Scenario
Reset Cost Overrides
Reset Workbench
```

## 8. Constraint Registry

建议新增后端统一 registry，例如：

```text
backend/core/constraint_registry.py
```

每条 metadata 至少：

```text
constraint_id
model
name
paper_equation
kind
provenance
implementation_status
formula_summary
input_dependencies
assumption_refs
notes
```

枚举建议：

```text
kind:
paper_constraint
implementation_guard
fixed_column_validation

provenance:
paper_defined
implementation_assumption
generated_provisional
airline_extension

implementation_status:
implemented
proxy
deferred
```

## 9. Constraints API

建议新增：

```text
GET  /api/model/constraints
POST /api/model/constraints/precheck
```

Precheck 返回：

```text
constraint_id
status
summary
issues
derived_values
```

必须明确：

```text
PRECHECK != MIP FEASIBILITY
```

页面统一使用：

```text
Precheck Passed
Precheck Warning
Precheck Failed
```

禁止写 Model Feasible 或 Optimal。

## 10. Constraint Inspector

按模型分组：

```text
SRM
ARM
CRM
PRM
```

每张卡至少展示：

```text
Constraint ID
Name
Paper equation
Type
Provenance
Implementation status
Formula summary
Related inputs
Assumption refs
Current-data summary
```

必须覆盖当前 Phase 2 已实现约束。

### SRM

```text
Flight Coverage
Strategic Flight
Arrival Capacity
Departure Capacity
Gate Inventory
Market-seat Proxy
```

### ARM

```text
Aircraft String selection
Required Flight Option coverage
Non-required revenue prohibition
Terminal
Maintenance
Fixed-column feasibility
```

### CRM

```text
Crew Pairing selection
Operating coverage
Non-required operating prohibition
Deadhead schedule consistency
Crew legality
Terminal / ownership guards
```

### PRM

```text
Passenger Group itinerary selection
Schedule consistency
Seat Capacity
Fixed itinerary feasibility
```

最终 Constraint ID 必须以实际代码为准，不重新创建冲突 ID。

## 11. Proxy 与 Assumption 展示

以下内容必须醒目标记：

```text
SRM Gate Inventory
SRM Market-seat
PRM test / residual seat capacity
```

例如：

```text
[PROXY]
[IMPLEMENTATION ASSUMPTION]
[TEST CAPACITY]
```

并说明：

```text
当前实现是什么
不等于什么
未来在哪个阶段重新处理
```

不能仅显示 Implemented。

## 12. Constraint 参数与编辑原则

Constraints 页面显示参数，但不建立第二份 editable 数据。

例如机场容量显示 arr_capacity / dep_capacity / gate_capacity，但修改跳转到 Data → Airport Capacity。

Strategic / Market 参数显示 strategic_flag / market_flag / min_seats，但修改跳转 Data → Flights。

同一字段只能有一个 canonical editable state。

PRM Passenger Capacity Profile 建议第一版只读展示：

```text
capacity_profile_id
source
units
option_id
seat_capacity
```

并明确：

```text
TEST / RESIDUAL CAPACITY
NOT AIRCRAFT PHYSICAL CAPACITY
```

Phase 3 会重新冻结 ARM → PRM capacity coupling，因此当前不建议在 HTML 建第二套 seat-capacity 编辑逻辑。

## 13. Constraint Precheck

允许 deterministic precheck：

```text
Flight 是否存在合法 options
Strategic Flight 是否存在 operate option
AirportInterval 是否覆盖所需 event
Gate inventory 输入是否可构造
Aircraft 是否存在候选 String
Crew 是否存在候选 Pairing
Passenger Group 是否存在 Itinerary
Seat Capacity Profile 是否覆盖相关 option
```

不运行 Solver。

## 14. Related Inputs 导航

Constraint card 提供：

```text
Go to Flights
Go to Aircraft
Go to Crew
Go to Passengers
Go to Airport Capacity
```

只切换到原有 Data View，不复制数据。

## 15. Assumption 与公式展示

Constraint card 显示 assumption refs，例如：

```text
A-005
A-029
A-030
```

可展示简短 summary，完整说明仍以 `assumptions.md` 为准。

公式只读展示简洁摘要，例如：

```text
Σ x_o = 1
Σ a_ko x_o ≤ ARR_CAP_k
Σ pax_g A_oi w_i ≤ SEAT_CAP_o
```

不在前端建立数学引擎。

## 16. 禁止直接开关核心约束

第一版禁止：

```text
Enable / Disable Flight Coverage
Enable / Disable Capacity
Enable / Disable Maintenance
Enable / Disable Passenger Capacity
```

如未来确需不同约束组合，应建立 versioned ModelProfile，而不是 checkbox。

## 17. Workbench Import / Export

保留纯：

```text
Export Scenario
```

新增：

```text
Export Workbench Config
```

建议：

```json
{
  "scenario": {},
  "cost_profile_id": "phase2_test_v1",
  "cost_overrides": {},
  "capacity_profile_id": "phase2_test_seat_capacity_v1",
  "model_profile": "phase2_fixed_column"
}
```

如实现 Import，必须明确区分 Scenario JSON 与 Workbench Config JSON，不能猜字段静默解析。

## 18. 前端文件职责

继续 Vanilla JS。

建议：

```text
frontend/js/app.js
    Workbench state / view routing

frontend/js/costs.js
    Cost rendering / override / validation

frontend/js/constraints.js
    Constraint inspector / precheck

frontend/js/api.js
    Costs / Constraints API

frontend/js/tables.js
    Scenario entity tables only

frontend/js/visualization.js
    Existing visualization only
```

CSS 可按现有结构扩展，不做整体 UI 重构。

## 19. Backend Tests

至少：

### Costs

```text
GET canonical profile
valid override
unknown key rejected
negative rejected
NaN / Infinity rejected
baseline immutable
effective value correct
```

### Constraint Registry

```text
constraint_id unique
model / kind / provenance enum valid
implemented constraints have metadata
paper equation field consistent when applicable
assumption refs format valid
```

### Precheck

```text
normal benchmark
broken flight-option coverage
broken capacity input
missing Passenger capacity input
```

## 20. Frontend / Contract Tests

至少：

```text
Costs view exists
Constraints view exists
canonical costs load
override changes effective value
reset restores baseline
Scenario state unaffected by cost editing
constraint metadata renders
PAPER / ASSUMPTION / PROXY distinguishable
related-input navigation works
Scenario export excludes cost override
Workbench export includes cost override
```

不要为了本任务引入重型前端框架。

## 21. Manual Browser Test

Codex 完成后人工检查：

```text
1. 启动 FastAPI
2. Load Example
3. Data 正常
4. Visualization 正常
5. Costs 可打开
6. SRM / ARM / CRM / PRM cost 正确分组
7. 修改 flight_delay_per_minute
8. Baseline 保持不变
9. Effective value 更新
10. Reset Cost Overrides 正常
11. Constraints 可打开
12. 四模型约束均可查看
13. Gate / Market-seat / test capacity provenance 清晰
14. Related Inputs 可跳转 Data
15. 修改 Scenario 后 current-data summary 同步
16. Export Scenario 正常
17. Export Workbench Config 正常
18. 页面无 console error
```

## 22. 文档同步

完成后更新：

```text
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
reproduction_notes.md
```

明确：

```text
Costs + Constraints Workbench 是人工审计与实验配置工具
不代表 Integrated Oracle 已完成
```

## 23. Codex Report

新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_costs_constraints_workbench_report.md
```

至少包含：

```text
1. Modified Files
2. Workbench Architecture
3. Costs UI
4. Cost Override Contract
5. Constraint Registry
6. Constraint Inspector
7. Precheck Semantics
8. APIs Added
9. Tests Added
10. Full Test Result
11. Manual Browser Test
12. Known Limitations
13. Acceptance Checklist
14. Next Recommended Step
```

最终明确：

```text
Costs + Constraints Workbench PASS
```

或：

```text
Costs + Constraints Workbench NOT PASS
```

## 24. Acceptance Criteria

- [ ] Costs 一级 View 已实现
- [ ] Constraints 一级 View 已实现
- [ ] 页面不再硬编码 Phase 0.5
- [ ] canonical Cost Config 是后端单一真源
- [ ] cost override 不修改 canonical provenance
- [ ] SRM / ARM / CRM / PRM 成本按 Owner 分组
- [ ] Constraint metadata 来自后端统一 registry
- [ ] Phase 2 implemented constraints 均有 metadata
- [ ] Paper / Assumption / Proxy / Deferred 可区分
- [ ] Constraint formula 只读
- [ ] 不允许任意关闭核心约束
- [ ] Related Inputs 与 Scenario 当前数据一致
- [ ] PRM test capacity 明确标记非真实 aircraft capacity
- [ ] Precheck 不冒充 Solver Feasibility
- [ ] Scenario Export 与 Workbench Export 分离
- [ ] Existing Data / Visualization 无回归
- [ ] 自动测试 PASS
- [ ] Manual Browser Test PASS
- [ ] 不接正式 Solve
- [ ] 不修改 Phase 2 数学模型
- [ ] 不进入 Phase 3 Integrated Oracle
