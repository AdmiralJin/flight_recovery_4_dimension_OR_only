# Phase 12 Closeout & Phase 13 Solver Integration / Recovered Result Plan

## 1. Phase 12 Review Conclusion

**Phase 12 可以收尾并合并。当前未发现阻断性问题。**

当前 `feature/phase-12` 已完成：

```text
Aircraft exact Branch-and-Price
+
Crew exact Branch-and-Price
+
Schedule Benders exact integer recourse
```

已核对的关键实现包括：

```text
backend/config/branch_and_price.py

backend/core/branch_restrictions.py
backend/core/aircraft_string_branch_and_price.py
backend/core/crew_pairing_branch_and_price.py
backend/core/benders_branch_and_price.py
```

Phase 12 已落实：

- Aircraft 优先使用 tail-option assignment branching，exact String branching 兜底；
- Crew 优先使用 typed follow-on branching，再使用 typed-leg / exact Pairing 兜底；
- 每个 branch node 都重新在 branch-restricted implicit universe 内完成 Column Generation；
- parent columns 只作为 child warm start，不能替代 child pricing；
- Schedule Benders 保留 Phase 11 pricing-certified LP cuts；
- 只有 Branch-and-Price 已证明的 exact integer recourse 才进入 exact schedule recourse cut；
- Passenger 继续使用 fixed explicit Itinerary exact PRM；
- 正式求解路径不依赖 Phase 5/6 full enumerators；
- v1 明确只支持 `scope=None`。

当前回归证据：

```text
toy_case_015:
Crew root LP = 195
Crew exact MIP = 200
Crew Branch-and-Price = 200
B&P nodes = 9
max depth = 4

toy_case_016:
Phase 11 = INTEGRALITY_REQUIRED
LB = 95195
UB = 95200

Phase 12 = OPTIMAL
Phase 12 objective = 95200
Full Explicit Integrated Oracle = 95200

phase1_benchmark_001:
Phase 12 objective = 18080
LB = UB
```

正式 Phase 12 benchmark 输入仍不携带预生成 Aircraft Strings / Crew Pairings。

因此 Phase 12 已真正闭合：

```text
LP recourse
→ integrality gap
→ Branch-and-Price
→ exact integer recourse
→ Schedule exact cut
```

---

# 2. Phase 12 Known Boundary

以下不是 Phase 12 bug，不阻塞合并：

```text
scope=None only

Passenger Itineraries remain fixed explicit columns

Flight Options remain existing/prepared candidates

Crew legality remains Phase 6 v1 single-duty profile

Aircraft 当前测试 universe 未构造出自然 integrality gap

Crew toy_case_015 提供真实 fractional LP → integer B&P 闭合证据

pricing / branching 当前以 correctness-first 为主，
不是生产规模高性能实现
```

尤其：

> 当前 Aircraft 没有自然 gap，不应为了“证明 branching 有用”而人为修改 ARM 数学模型制造 gap。

保留 branch-aware Aircraft pricing、assignment restriction、exact String fallback 和 Oracle tests 即可。

---

# 3. Phase 12 Closeout

在 `feature/phase-12` 上执行：

```bash
git status
pytest -q
python -m compileall -q backend
git diff --check
```

如果当前工程继续使用 Black：

```bash
python -m black --check <Phase12 Python files>
```

要求：

```text
working tree clean
0 failed
0 errors
```

确认至少已提交：

```text
backend/config/branch_and_price.py

backend/core/branch_restrictions.py
backend/core/aircraft_string_branch_and_price.py
backend/core/crew_pairing_branch_and_price.py
backend/core/benders_branch_and_price.py

data/config/phase12_test_branch_and_price_v1.json

Phase 12 unit / regression / benchmark tests
toy_case_015
toy_case_016

README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/codex_reports/<latest_phase12_report>.md
```

---

# 4. Merge Phase 12

```bash
git switch main
git pull
git merge --no-ff feature/phase-12
```

合并后再次运行：

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

通过后：

```bash
git push origin main
```

随后：

```bash
git switch -c feature/phase-13
```

确认远端 `main` 已包含 Phase 12 后，可删除 Phase 12 分支。

---

# 5. Phase 12 Freeze

Phase 13 是接口/结果/可视化阶段。

原则上**不要再修改核心数学算法**：

```text
Integrated Oracle
Fixed-column Benders
Aircraft CG
Crew CG
Benders + CG
Aircraft Branch-and-Price
Crew Branch-and-Price
Benders + Branch-and-Price
```

Phase 13 只能为了稳定 API 做非常小的向后兼容接口提取。

任何影响：

```text
feasible region
objective
pricing
branching
Benders cuts
```

的改动都不属于 Phase 13。

---

# 6. Phase 13 Position

Phase 13 对应当前仓库计划：

```text
Recovered Result Visualization
+
Stable Solve API
```

当前算法已经存在，但产品链路仍断在：

```text
Scenario / Workbench
    ↓
Validate
    ↓
[no public Solve workflow]
```

当前 `backend/main.py` 仍写：

```text
Solver API remains disabled
```

当前前端也只有：

```text
Data
Visualization
Costs
Constraints
```

没有正式：

```text
Solve
Recovery Result
```

因此 Phase 13 的目标是把已经验证的 Phase 12 solver 接到系统表面，而不是继续开发新优化算法。

---

# 7. Phase 13 Core Goal

形成：

```text
Workbench Input
        ↓
Validate / Precheck
        ↓
POST /api/solve
        ↓
Phase 12 exact solver
        ↓
Recovered Result Builder
        ↓
Stable Recovery Result JSON
        ↓
Original / Disrupted / Recovered / Difference UI
```

Phase 13 完成后，用户应能够：

1. 加载完整 benchmark solve bundle；
2. 检查 Scenario / Costs / Constraints；
3. 点击 `Solve`；
4. 获取明确 Solver 状态；
5. 查看恢复后的 Flight / Aircraft / Crew / Passenger；
6. 查看 objective、runtime、cuts、columns、bounds 等 diagnostics；
7. 对比 Original / Disrupted / Recovered。

---

# 8. Critical Input Boundary

**Phase 13 不实现新的 Flight Option Generator。**

当前 Phase 12 仍需要：

```text
existing Flight Options
```

因此：

```text
Scenario-only input
```

不能被静默转换成可求解问题。

正式 Solve Input 必须至少具备：

```text
Scenario
Flight Options
Passenger Itineraries or enough data to generate them
Passenger Capacity Profile
Cost Config / Overrides
algorithm config profiles
```

Phase 13 不得偷偷：

```text
自动假设 delay options
自动制造 cancel options
自动制造 capacity
自动生成业务 Flight Options
```

---

# 9. Recommended Solve Bundle

建议新增明确的 application-level 输入：

```python
SolveRequest
```

而不是让前端拼多个内部 Core request。

建议结构：

```text
schema_version

scenario

recovery_columns:
    flight_options
    passenger_itineraries
    aircraft_strings = []
    crew_pairings = []

capacity_profile

cost_profile_id
cost_overrides

algorithm = "benders_branch_and_price_v1"

profile_ids:
    flight_string_generation
    crew_pairing_generation
    aircraft_string_cg
    crew_pairing_cg
    benders_cg
    branch_and_price
```

要求：

```text
Aircraft Strings / Crew Pairings
不得作为 Phase 13 formal solver 输入
```

以保持 Phase 11/12 formal-enumerator-independence contract。

---

# 10. Scenario-only Solve Must Be Rejected

如果当前 Workbench 只有 Scenario，没有 compatible：

```text
Flight Options
Passenger Capacity Profile
```

则 Solve button/API 应明确返回：

```text
not_solve_ready
```

并给出缺失项：

```text
missing_flight_options
missing_capacity_profile
...
```

不得返回：

```text
fake optimized result
```

---

# 11. Result Schema

建议新增：

```text
backend/schemas/result.py
```

不要直接把：

```text
BendersBranchAndPriceResult
```

原样暴露给前端。

Core solver result 是算法结构；

Recovered Result 是稳定业务/展示契约。

---

# 12. Reuse Existing Result Semantics

当前：

```text
backend/schemas/expected.py
```

已经有：

```text
ResolvedFlight
RecoveryAction
PassengerOutcome
RecoveryMetrics
```

Phase 13 优先复用这些语义。

不要复制一套不同的：

```text
delay
cancel
reassignment
unserved
```

定义。

如需重构 shared models：

```text
必须保持 RecoveryExpected v1.0.0 向后兼容
```

---

# 13. Recommended RecoveredResult

建议：

```python
RecoveredResult
```

至少包含：

```text
schema_version
run_id
scenario_id

status
algorithm

objective

selected:
    flight_options
    aircraft_strings
    crew_pairings
    passenger_itineraries

resolved_flights
aircraft_outcomes
crew_outcomes
passenger_outcomes
recovery_actions

metrics
diagnostics
run_metadata
```

---

# 14. Result Status

建议独立定义 API status：

```text
optimal
infeasible
not_converged
aborted
invalid_input
```

不要把 HTTP status 当作 Solver status。

例如：

```text
HTTP 200
status = infeasible
```

可以表示：

> 请求本身合法，优化模型证明不可行。

而：

```text
HTTP 422
```

表示输入 contract / semantic validation 失败。

---

# 15. Objective Result

至少：

```text
total
schedule
aircraft
crew
passenger
```

必须从 final selected solution 独立复算。

不要只复制：

```text
solver objective
```

并要求：

```text
sum(components)
≈
total
```

---

# 16. Flight Result

每个原 Flight 至少输出：

```text
flight_id
selected_option_id

status:
    operated / cancelled

original:
    origin
    destination
    dep
    arr

recovered:
    origin
    destination
    dep
    arr

departure_delay_minutes
arrival_delay_minutes

change_types

aircraft_id
crew_id
```

继续复用现有 `ResolvedFlight` 语义。

---

# 17. Aircraft Result

新增例如：

```python
AircraftOutcome
```

至少：

```text
aircraft_id
selected_string_id
ordered_flight_option_ids
original_flight_ids
recovered_flight_ids
reassignment_count
ferry_legs
final_station
```

用于：

```text
Original Rotation
vs
Recovered Rotation
```

---

# 18. Crew Result

新增例如：

```python
CrewOutcome
```

至少：

```text
crew_id
selected_pairing_id

segments:
    segment_type
    flight_option_id

operated_flights
deadhead_flights
reassignment_count
final_station
```

必须保留：

```text
OPERATE
DEADHEAD
```

区别。

---

# 19. Passenger Result

继续使用：

```text
PassengerOutcome
```

至少显示：

```text
pax_group_id
count
selected_itinerary_id
status
original itinerary
recovered itinerary
arrival_time
arrival_delay_minutes
unserved_count
```

---

# 20. Metrics

Recovered Result metrics 至少：

```text
operated_flights
cancelled_flights
delayed_flights

mean_departure_delay_minutes
max_departure_delay_minutes
total_departure_delay_minutes

aircraft_reassignments
crew_reassignments

passenger_reaccommodated_groups
passenger_reaccommodated_count
passenger_delay_minutes_weighted
unserved_passengers
```

其中现有 `RecoveryMetrics` 已有多数指标。

新增 mean/max 时必须程序化复算，不能由 UI 自己推断。

---

# 21. Diagnostics

Recovered Result 的 diagnostics 至少提供：

```text
algorithm

runtime_seconds

objective
lower_bound
upper_bound
gap

Benders master iterations
visited schedules

LP cuts
exact integer cuts
feasibility cuts

Aircraft CG calls
Aircraft generated columns
Aircraft B&P nodes

Crew CG calls
Crew generated pairings
Crew B&P nodes

Passenger itinerary count

formal_full_enumerators_used

integrated_audit_pass
```

UI 不应读取 Core dataclass 的任意内部字段。

必须先转换为稳定 diagnostics contract。

---

# 22. Run Metadata

至少：

```text
run_id
scenario_id

git_commit if available
application_version

solver
solver_version

algorithm
algorithm_profile_ids

cost_profile_id
capacity_profile_id

started_at
finished_at
runtime_seconds
```

如果 Git commit 无法可靠读取：

```text
允许 null
```

不要伪造。

---

# 23. Result Builder

建议新增：

```text
backend/application/result_builder.py
```

或：

```text
backend/core/result_builder.py
```

但推荐 application layer，因为这是从优化解转换成展示/业务结果，不是数学模型本身。

公共入口：

```python
build_recovered_result(...)
```

输入：

```text
Scenario
formal input columns
Phase 12 result
Cost Config
Capacity Profile
run metadata
```

输出：

```text
RecoveredResult
```

---

# 24. Result Builder Must Be Independently Auditable

Builder 必须重新检查：

```text
selected Flight Option exactly one/base Flight

selected Aircraft String ownership

selected Crew Pairing ownership

Passenger selection ownership

Flight ↔ Aircraft assignment

Flight ↔ Crew OPERATE assignment

Passenger referenced Flight Options

objective components

RecoveryMetrics
```

不要因为 Phase 12 已有 Integrated audit 就完全跳过 result transformation validation。

---

# 25. Stable Solve Service

建议新增：

```text
backend/application/solve_service.py
```

职责：

```text
validate SolveRequest

load/version-check configs

apply cost overrides

prepare formal Phase 12 input

call solve_benders_with_branch_and_price(...)

convert Core result
→ RecoveredResult

return stable application result
```

不要把这些 orchestration 全塞进：

```text
backend/api/solve.py
```

---

# 26. Solve API

新增：

```text
backend/api/solve.py
```

并在：

```text
backend/main.py
```

正式 include router。

接口：

```text
POST /api/solve
```

输入：

```text
SolveRequest
```

输出：

```text
RecoveredResult
```

---

# 27. HTTP Contract

建议：

## `200`

合法 solve request 已完成：

```text
optimal
infeasible
not_converged
aborted
```

status 放在 JSON 内。

## `422`

```text
Schema error
Semantic validation error
Solve readiness error
Profile mismatch
Missing capacity / Flight Options
```

## `500`

仅：

```text
unexpected internal exception
```

不得把已知 solver terminal status 当作 500。

---

# 28. No Background Job in Phase 13 v1

Phase 13 v1 使用：

```text
synchronous POST /api/solve
```

因为当前 benchmark / toy 仍是 correctness-scale。

不要在同一阶段引入：

```text
Celery
Redis
job queue
WebSocket
background worker
```

如果未来真实规模 runtime 需要异步，再单独设计。

---

# 29. Solve Readiness Endpoint

建议新增：

```text
POST /api/solve/precheck
```

或扩展现有 Constraints precheck。

返回：

```text
solve_ready
missing_inputs
invalid_profiles
warnings
```

注意：

```text
Solve Readiness
!=
Optimization Feasibility
```

不要把它称作 solver feasibility。

---

# 30. Frontend Solve Button

当前 command bar 增加：

```text
Solve
```

规则：

```text
Validate failed:
    disabled

Solve bundle incomplete:
    disabled / explicit warning

ready:
    enabled
```

点击后：

```text
show solving state
disable repeated submit
POST /api/solve
render result
```

---

# 31. Add Recovery View

建议一级视图扩展为：

```text
Data
Visualization
Recovery
Costs
Constraints
```

或者：

```text
Visualization
```

内部增加 recovery modes。

为了代码清晰，推荐单独：

```text
Recovery
```

一级视图。

---

# 32. Recovery Summary

至少显示：

```text
Solver Status
Total Cost

Cancelled Flights
Delayed Flights
Mean Delay
Max Delay

Aircraft Reassignments
Crew Reassignments

Passenger Delay
Unserved Passengers

Runtime
Final Gap
```

---

# 33. Flight Recovery Table

列：

```text
Flight
Original OD
Recovered OD

Original Departure
Recovered Departure

Original Arrival
Recovered Arrival

Departure Delay
Arrival Delay

Status
Aircraft
Crew
```

支持：

```text
Cancelled highlight
Delay sort
Changed OD indicator
```

---

# 34. Aircraft Recovery View

显示：

```text
Aircraft
Original Rotation
Recovered Rotation
Ferry
Reassignment
Final Station
```

推荐复用现有 Time-Space Network 的时间轴组件。

---

# 35. Crew Recovery View

显示：

```text
Crew
Original Pairing
Recovered Pairing

OPERATE legs
DEADHEAD legs

Reassignments
Terminal
```

DEADHEAD 必须有明确视觉标识，不能与 OPERATE 混在一起。

---

# 36. Passenger Recovery View

显示：

```text
Passenger Group
Count

Original Itinerary
Recovered Itinerary

Status
Arrival Delay
Unserved
```

---

# 37. Original / Disrupted / Recovered / Difference

现有 Visualization 是：

```text
Original
+
Disruption
+
Risk
```

Phase 13 增加选择器：

```text
Original
Disrupted
Recovered
Difference
```

其中：

## Original

原计划。

## Disrupted

原计划 + disruption/capacity exposure。

## Recovered

Phase 13 `RecoveredResult`。

## Difference

只强调发生变化的：

```text
delay
cancel
route change
aircraft reassignment
crew reassignment
passenger reaccommodation
unserved
```

---

# 38. Do Not Mix Risk and Recovery

现有：

```text
Aircraft/Crew Downstream Risk
```

属于扰动传播分析。

Recovered View 是优化结果。

前端必须明确区分：

```text
Risk
≠
Recovered Decision
```

不要把 risk marker 当作 solver action。

---

# 39. Diagnostics Panel

新增算法诊断折叠面板：

```text
Algorithm
Status

LB
UB
Gap

Benders iterations
Cuts

Aircraft columns
Crew pairings

Aircraft B&P nodes
Crew B&P nodes

Runtime
Integrated audit
```

这是研究/调试工具，不需要默认占用主业务界面。

---

# 40. Export Recovered Result

增加：

```text
Export Recovered Result
```

导出：

```text
RecoveredResult JSON
```

必须包含：

```text
schema_version
run metadata
selected decisions
metrics
diagnostics
```

便于：

```text
科研复现
结果对比
后续论文表格
回归测试
```

---

# 41. Import Result Is Not Required in v1

Phase 13 第一版不强制：

```text
Import Recovered Result
```

如果实现成本很低可加入。

核心优先级：

```text
Solve
→ Result
→ Visualization
→ Export
```

---

# 42. Benchmark API Acceptance

使用：

```text
phase1_benchmark_001
```

完整 Solve API 必须返回：

```text
status = optimal
objective = 18080
```

并且：

```text
Flight metrics
Aircraft assignments
Crew assignments
Passenger outcomes
```

与当前 Phase 12 selected solution / Integrated audit 一致。

---

# 43. toy_case_016 API Acceptance

Phase 13 API 还必须覆盖：

```text
toy_case_016
```

要求：

```text
status = optimal
objective = 95200
```

确保 API 真正使用 Phase 12，而不是退回 Phase 11 或固定列 Oracle。

---

# 44. Result Builder Regression

必须验证：

```text
Core objective
=
RecoveredResult objective

Core selected IDs
=
RecoveredResult selected IDs

independent metrics
=
RecoveredResult metrics
```

不能只 snapshot JSON。

---

# 45. Infeasible API Case

增加至少一个：

```text
valid SolveRequest
but optimization infeasible
```

要求：

```text
HTTP = 200
status = infeasible
```

且不返回伪 recovered flights。

---

# 46. Invalid Solve Bundle Case

例如：

```text
Scenario present
Flight Options missing
```

要求：

```text
HTTP 422
```

并明确：

```text
missing_flight_options
```

---

# 47. Not-converged Case

用很小：

```text
max_iterations / max_nodes
```

配置强制：

```text
NOT_CONVERGED
```

API 应稳定映射：

```text
status = not_converged
```

不得返回：

```text
optimal
```

---

# 48. Determinism

相同 SolveRequest：

除：

```text
run_id
timestamps
runtime
```

外，RecoveredResult 应 deterministic：

```text
objective
selected decisions
metrics
actions
diagnostics structural fields
```

---

# 49. Frontend Tests

不要为了 Phase 13 临时引入大型 JS framework。

保持：

```text
HTML
Vanilla JS
```

建议：

- 后端 API integration tests；
- RecoveredResult builder unit tests；
- existing static/frontend smoke tests；
- 对关键 DOM IDs / view wiring 做轻量 contract test；
- 最终进行一次人工 browser acceptance。

如果仓库当前没有 JS test toolchain：

```text
不要仅为了 Phase 13 引入 React/Vue/Vitest
```

---

# 50. Recommended Files

新增：

```text
backend/schemas/result.py

backend/application/__init__.py
backend/application/result_builder.py
backend/application/solve_service.py

backend/api/solve.py

tests/unit/test_result_builder.py
tests/unit/test_solve_service.py

tests/api/test_solve_api.py
tests/regression/test_phase13_recovered_result.py
tests/regression/test_phase13_benchmark_api.py
```

前端建议新增：

```text
frontend/js/recovery.js
```

或按现有模块结构：

```text
frontend/static/js/recovery.js
```

实际路径以当前项目组织为准。

同时修改：

```text
backend/main.py
backend/schemas/__init__.py

frontend/index.html
frontend/static/js/app.js
frontend/static/css/...
```

实际静态路径以当前仓库为准。

---

# 51. Avoid Unnecessary Core Changes

原则上不修改：

```text
backend/core/integrated_oracle.py
backend/core/benders.py
backend/core/benders_column_generation.py
backend/core/benders_branch_and_price.py

backend/core/aircraft_string_column_generation.py
backend/core/crew_pairing_column_generation.py

backend/core/aircraft_string_branch_and_price.py
backend/core/crew_pairing_branch_and_price.py
```

Phase 13 应通过：

```text
application/service layer
```

包装它们。

---

# 52. API Version / App Version

当前 FastAPI app version 仍为：

```text
0.3.0
```

且 description 明确写 Solver disabled。

Phase 13 完成后：

- 更新 version；
- 删除 Solver disabled 描述；
- `/api/health` 增加 solver capability 信息；
- 但不要宣称 production-ready。

例如：

```text
solver_enabled = true
algorithm = benders_branch_and_price_v1
production_ready = false
```

---

# 53. Health Endpoint

建议：

```json
{
  "status": "ok",
  "solver_enabled": true,
  "algorithm": "benders_branch_and_price_v1",
  "scope_mode": "full_only",
  "flight_option_generation": false,
  "production_ready": false
}
```

不要让健康检查隐瞒已知限制。

---

# 54. Documentation

Phase 13 完成时同步：

```text
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
assumptions.md
reproduction_notes.md
```

README 状态：

```text
Phase 13 = COMPLETE
```

并明确：

```text
Core AIR reproduction / research workbench v1 complete
```

---

# 55. Phase 13 Report

生成：

```text
docs/codex_reports/
YYYYMMDD_HHMMSS_phase13_solver_integration_recovered_result_report.md
```

至少包括：

```text
1. Phase 12 closeout
2. Modified files
3. SolveRequest contract
4. Solve readiness rules
5. RecoveredResult schema
6. Result-builder mapping
7. Solve service
8. /api/solve contract
9. Frontend Recovery view
10. Original/Disrupted/Recovered/Difference
11. Diagnostics
12. Export result
13. benchmark API result
14. toy_case_016 API result
15. invalid/infeasible/not-converged cases
16. full regression
17. known limitations
18. project closure status
19. business-migration next steps
```

---

# 56. Phase 13 Acceptance Criteria

全部满足才可完成。

## A. Solve API

- [ ] `/api/solve` 已正式注册；
- [ ] 不再返回假/占位优化结果；
- [ ] input contract versioned；
- [ ] Scenario-only input明确拒绝；
- [ ] known terminal statuses稳定返回；
- [ ] unexpected exception才使用500。

## B. Result Schema

- [ ] RecoveredResult versioned；
- [ ] selected x/y/z/w decisions可追踪；
- [ ] resolved Flight完整；
- [ ] Aircraft/Crew/Passenger outcome完整；
- [ ] metrics独立复算；
- [ ] objective components独立复算；
- [ ] diagnostics contract稳定。

## C. Solver Integration

- [ ] formal path使用 Phase 12；
- [ ] Aircraft/Crew full enumerators不成为 API 正式依赖；
- [ ] `scope=None` limitation显式；
- [ ] existing Flight Options requirement显式；
- [ ] Integrated final audit PASS。

## D. Frontend

- [ ] Solve button；
- [ ] solving / success / infeasible / failure state；
- [ ] Recovery view；
- [ ] Summary；
- [ ] Flight；
- [ ] Aircraft；
- [ ] Crew；
- [ ] Passenger；
- [ ] Diagnostics；
- [ ] Original/Disrupted/Recovered/Difference；
- [ ] Export Recovered Result。

## E. Regression

```text
phase1_benchmark_001:
API objective = 18080
```

```text
toy_case_016:
API objective = 95200
```

- [ ] Phase 1–12 existing tests PASS；
- [ ] compileall PASS；
- [ ] git diff --check PASS。

---

# 57. Definition of Done

Phase 13 只有形成以下完整闭环才算完成：

```text
Scenario + Solve Bundle
        ↓
Validation / Solve Readiness
        ↓
Stable /api/solve
        ↓
Phase 12 Solver
        ↓
RecoveredResult Builder
        ↓
Independent Result Audit
        ↓
Recovered Result JSON
        ↓
Recovery UI
        ↓
Original / Disrupted / Recovered / Difference
        ↓
Export
        ↓
Full Regression PASS
```

---

# 58. Is Phase 13 the Last Phase?

## 对当前 AIR 复现项目

**可以。**

Phase 13 完成后，建议将：

```text
Phase 0–13
```

冻结为：

```text
AIR Reproduction / Recovery Workbench v1
```

因为当前核心路线已经完整覆盖：

```text
Data
→ Oracle
→ Integrated Model
→ Benders
→ Candidate Generation
→ Column Generation
→ Integrality / Branch-and-Price
→ Solve API
→ Recovered Result
→ Visualization
```

此后不建议为了“继续编号”再随意向 core 添加 Phase 14/15。

---

# 59. But Phase 13 Is Not the End of the Real Airline Project

仓库当前路线写的是：

```text
Phase 13+
```

而最终成功标准还有：

```text
Level 8 — Business Migration
```

也就是进入真实航空公司数据后仍需要：

```text
real airline data mapping

real cost calibration

real crew rules
reserve crew

tail swap
fleet substitution

ATFM / flow control
weather

curfew
maintenance

important-flight rules

transfer-passenger priority

international/domestic restrictions

ferry
diversion
cancellation hierarchy

runtime / scalability engineering

operational validation
```

这些不应再静默修改：

```text
backend/core/
```

而应进入：

```text
backend/application/airline_rules/
```

或独立的业务迁移路线。

---

# 60. Recommended Project Boundary After Phase 13

Phase 13 完成后建议：

```text
Core Research / Reproduction Roadmap:
    COMPLETE

Business Migration Roadmap:
    START SEPARATELY
```

例如后续另建：

```text
Business Migration M1 — Real Data Mapping
Business Migration M2 — Airline Rules
Business Migration M3 — Cost Calibration
Business Migration M4 — Large-scale Performance
Business Migration M5 — Operational Validation
```

这样比继续叫：

```text
Phase 14
Phase 15
Phase 16
```

更清晰，也能保持：

```text
Paper/Core Model
vs
Airline-specific Extension
```

边界。

---

# 61. Final Principle

Phase 13 不再回答：

> “算法还能不能更复杂？”

而回答：

> **已经验证正确的算法，能否通过稳定输入、稳定结果、稳定 API 和可解释 UI，形成一个真正可使用、可演示、可复现的研究软件闭环。**

优先级：

```text
Result correctness
>
API stability
>
traceability
>
visual explainability
>
diagnostics
>
UI polish
```

不要在 Phase 13 为了界面效果重新改变数学模型。
