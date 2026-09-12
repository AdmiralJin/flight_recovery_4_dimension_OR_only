# Phase 2.4 Review Fix + Phase 2.5 Fixed-Column PRM Plan

> 用途：供 Codex 在当前 `main` 基础上继续开发。  
> 执行顺序：**先完成 Phase 2.4 收尾修补并留痕，再进入 Phase 2.5 Fixed-Column PRM。**  
> 本文件不包含 HTML / Frontend 修改，也不进入 Integrated Oracle / Benders / Column Generation。

---

# Part A — Phase 2.4 Review Fix

# 1. Phase 2.4 当前结论

Phase 2.4 Fixed-Column CRM 主体已经完成并通过审核：

- canonical SRM → downstream handoff 已实现；
- `CrewRecoveryRequest` 为外生 schedule input；
- fixed `CrewPairing` selection 已实现；
- OPERATE / DEADHEAD 已明确分离；
- required revenue Flight Option crew coverage 已实现；
- non-required OPERATE / DEADHEAD leakage 已禁止；
- fixed-column legality / terminal 已审计；
- crew reassignment / deadhead CRM-owned cost 已实现；
- objective 与约束均有独立复算；
- Gurobi integration 实际运行；
- 未修改 HTML；
- 未进入 PRM / Integrated Oracle。

因此 **不进行 CRM 模型级返工**。

---

# 2. Phase 2.4 必须修补：`reproduction_notes.md` 同步

当前明确遗漏：

```text
reproduction_notes.md
```

仍停留在：

```text
Fixed-column CRM 尚未实现
当前仅有 SRM + ARM
下一步 Phase 2.4 CRM
```

这已经与当前代码、README、Reproduction Plan 和 Phase 2.4 Codex Report 不一致。

---

## 2.1 修改要求

更新 `reproduction_notes.md` 中至少以下章节：

```text
Cost 当前状态
当前仍未实现
当前工程状态
下一工程步骤
```

应准确改为：

```text
Phase 2.4 Fixed-Column CRM 已完成

当前已建立：
SRM
+
ARM
+
CRM

三个相互独立、fixed-column、可审计的业务恢复子模型。
```

成本状态应表述为：

```text
SRM-owned:
delay / cancellation / route change
已实现 Phase 2 test cost

ARM-owned:
aircraft reassignment / ferry
已实现 Phase 2 test cost

CRM-owned:
crew reassignment / deadhead
已实现 Phase 2 test cost

PRM-owned:
passenger delay / unserved passenger
Cost Contract 已预留，但尚未正式进入 PRM Model
```

并继续明确：

```text
以上仍为 abstract_cost_units / implementation test profile，
不代表真实航空公司生产成本。
```

下一步应改为：

```text
Phase 2.5 Fixed-Column PRM
```

---

# 3. Phase 2.4 低优先级留痕：Crew Reassignment Mapping

当前实现：

```text
每个 selected Crew Pairing 的 OPERATE leg
若 base_flight.original_crew != pairing.crew_id
→ 计一次 crew reassignment
```

这已经由 assumption 明确登记，因此当前不是 bug。

但应在：

```text
reproduction_notes.md
```

或 Phase 2.4 review-fix report 中保留一句：

> 当前 crew reassignment 是“按 reassigned operating flight leg 计数”的 Phase 2 implementation mapping；未来真实业务成本标定时必须重新确认实际计费粒度是 crew / duty / pairing / flight-leg 中哪一种。

不得在本次修补中修改现有成本逻辑。

---

# 4. Phase 2.4 Review Fix 测试

本次原则上仅改文档，不应改变业务代码。

执行：

```bash
python -m pytest -q
```

要求：

```text
全部通过
0 skipped
```

Gurobi integration 继续实际执行。

如果文档修补过程中发现代码/报告状态与实际测试数量变化，仅更新真实结果，不硬编码旧数量。

---

# 5. Phase 2.4 留痕报告

在：

```text
docs/codex_reports/
```

新增：

```text
YYYYMMDD_HHMMSS_phase2_4_review_fix_report.md
```

报告简要包含：

```text
1. Review Finding
2. reproduction_notes Changes
3. Crew Reassignment Mapping Note
4. Test Result
5. Gurobi Integration Result
6. Phase 2.4 Final Status
```

最终明确：

```text
Phase 2.4 FINAL PASS
```

或：

```text
Phase 2.4 NOT PASS
```

---

# 6. Phase 2.4 Review Fix Acceptance

- [ ] `reproduction_notes.md` 不再写 CRM 未实现；
- [ ] 当前工程状态为 SRM + ARM + CRM；
- [ ] 下一步明确为 Phase 2.5 PRM；
- [ ] CRM cost 状态描述正确；
- [ ] crew reassignment 当前计数粒度已留痕；
- [ ] full pytest PASS；
- [ ] 0 skipped；
- [ ] Gurobi integration 实际运行；
- [ ] review-fix report 已新增。

完成后进入 Phase 2.5。

---

# Part B — Phase 2.5 Fixed-Column PRM

# 7. Phase 2.5 目标

实现：

```text
Fixed-Column PRM
Passenger Recovery Model
```

总计划要求对应论文：

```text
(3.16) - (3.18)
```

并正式处理：

```text
Seat Capacity
Passenger Reaccommodation
Unserved Passenger
Arrival Delay Cost
```

**正式编码前必须重新打开仓库论文原文，逐式核对 `(3.16)-(3.18)`。**

Codex 必须建立：

```text
Paper equation
→ Paper variable / coefficient
→ 当前项目 fixed-column mapping
→ 数据字段
→ assumption
→ test
```

不得仅根据本计划文字猜原公式。

---

# 8. Phase 2.5 核心边界

Phase 2.5 只回答：

> 给定已经确定实际执行的 revenue Flight Options，以及明确的座位容量输入，在现有 fixed Passenger Itineraries 中，为每个 Passenger Commodity 选择恢复方案，使旅客延误与未服务成本最小，同时不超过航班座位容量。

本阶段允许：

```text
Passenger itinerary selection
Passenger reaccommodation
Unserved itinerary
Flight seat capacity
Passenger arrival delay cost
Unserved passenger cost
Surface segment as fixed itinerary component
```

本阶段禁止：

```text
重新决定 flight delay / cancellation
重新决定 aircraft string
重新决定 crew pairing
动态生成 passenger itinerary
Integrated Oracle
Benders
Column Generation
HTML / Frontend
真实南航旅客保护政策推断
Cabin / fare class inventory（除非当前数据正式增加）
```

---

# 9. 当前已有 Passenger 数据资产

当前 Scenario 已有：

```text
PassengerCommodity:
pax_group_id
count
origin
destination
original_departure
scheduled_arrival
original_itinerary
```

当前 Recovery Columns 已有：

```text
PassengerItinerary:
itinerary_id
pax_group_id
status
segments
final_destination
arrival_time
arrival_delay_minutes
cost_components
```

`status`：

```text
transported
unserved
```

`PassengerSegment`：

```text
flight
surface
```

因此现有 schema 已能表达：

```text
保持原路径
延误后的原路径
改签其他航班
surface transfer
unserved
```

Phase 2.5 应优先复用，不要无必要修改 itinerary schema。

---

# 10. 当前明确 Blocker：Seat Capacity Contract

当前项目虽然已有：

```text
Flight.min_seats
Flight.original_equipment
Aircraft.equipment_type
```

但当前没有正式：

```text
aircraft seat capacity
equipment seat capacity
option seat capacity
remaining seat inventory
cabin/class seat inventory
```

同时之前已明确：

```text
min_seats != aircraft seat capacity
```

因此 Phase 2.5 **严禁**：

```text
seat_capacity = Flight.min_seats
```

也不得凭 equipment name 猜座位数。

---

# 11. Phase 2.5 先建立独立 Seat Capacity Contract

为了保持 PRM 单模型可测，同时不提前耦合 ARM，第一版建议建立显式：

```text
PassengerCapacityProfile
```

或等价 immutable schema。

建议字段：

```text
schema_version
capacity_profile_id
scenario_id
source
units
seat_capacity_by_option_id
notes
```

例如：

```json
{
  "schema_version": "1.0.0",
  "capacity_profile_id": "phase2_test_seat_capacity_v1",
  "scenario_id": "phase1_benchmark_001",
  "source": "implementation_assumption",
  "units": "seats",
  "seat_capacity_by_option_id": {
    "FO_F1_ORIG": 100,
    "FO_F2_D50": 100
  },
  "notes": [
    "Phase 2 test-only seat capacity profile; not airline production data."
  ]
}
```

这里的数字仅为结构示例，不得直接照抄。

---

## 11.1 为什么不直接修改 Scenario

当前 Phase 2.5 的目的首先是验证：

```text
Fixed Passenger Itinerary + Capacity + Cost
```

数学结构。

因此建议先将 seat capacity 作为独立、版本化、可替换的 Phase 2 test input。

后续 Integrated Oracle 再决定是否升级为：

```text
Aircraft / equipment seat capacity
+
selected ARM assignment
→ operated Flight Option capacity
```

这样可以避免 Phase 2.5 偷偷把 ARM 重新实现一遍。

---

## 11.2 Capacity Profile 来源分类

必须标记：

```text
implementation_assumption
test_fixture
```

不得标记：

```text
paper value
airline value
real aircraft capacity
```

除非未来真实数据支持。

建议文件：

```text
data/capacities/phase2_test_seat_capacity_v1.json
```

及对应 Python schema。

是否增加 JSON Schema 文件，按当前项目已有配置类管理方式统一决定。

---

# 12. Seat Capacity Profile 必须满足的校验

至少检查：

```text
scenario_id 一致
option_id 存在
只允许 revenue OPERATE option
不得给 CANCEL capacity
不得给 FERRY passenger capacity
capacity 为非负整数
不得 duplicate
```

对于当前 `required_operated_option_ids`：

若某 option 被 Passenger Itinerary 使用但缺 capacity：

```text
fail fast
```

不得默认：

```text
infinite capacity
```

---

# 13. Phase 2.5 输入合同

建议新增：

```text
PassengerRecoveryRequest
```

至少包含：

```text
scenario_id
required_operated_option_ids
capacity_profile_id / seat_capacity_by_option_id
```

其中：

```text
required_operated_option_ids
```

继续复用 canonical：

```text
extract_required_operated_option_ids(...)
```

不得由 PRM 自己重新解析 SRM diagnostics。

---

# 14. PRM 不应该强依赖 ARM Result

Phase 2.5 是独立 fixed-column 子模型。

因此第一版：

```text
PRM
← external schedule
← external test seat-capacity profile
```

而不是：

```text
PRM 内部调用 ARM
```

如果以后需要真实 equipment-specific seats：

```text
Integrated Oracle / downstream handoff
```

再负责：

```text
ARM assignment
→ Flight Option capacity
```

Phase 2.5 只冻结 PRM 数学和数据合同。

---

# 15. 决策变量

当前 `PassengerCommodity` 是 group，当前 fixed itinerary 也是：

```text
itinerary_id
pax_group_id
```

第一版建议对每个 itinerary：

```text
w_i ∈ {0,1}
```

并要求同一 Passenger Commodity：

```text
sum(w_i for i in itineraries(group)) = 1
```

含义：

> 当前 fixed-column PRM 将 passenger group 作为不可拆分 commodity，一整个 group 选择一条 itinerary 或 unserved。

---

## 15.1 Group splitting 必须明确

必须在实现前核对论文 `(3.16)-(3.18)` 是否允许 passenger commodity 分流。

如果论文允许：

```text
部分旅客 itinerary A
部分旅客 itinerary B
```

而当前项目仍使用 binary group itinerary selection，则必须：

```text
登记 Implementation Mapping Assumption
```

并明确 Phase 2.5 第一版不支持 group splitting。

不得默认为“论文就是 binary”。

---

# 16. 建议 Constraint IDs

在重新核对论文后冻结。

建议工程 ID：

```text
PRM-C01-PASSENGER-GROUP-SELECTION
PRM-C02-SCHEDULE-CONSISTENCY
PRM-C03-SEAT-CAPACITY
PRM-C04-ITINERARY-FEASIBILITY
```

但：

> 不得为了凑 4 个 ID 把论文 `(3.16)-(3.18)` 强行拆成 4 个 paper constraints。

Codex Report 必须明确区分：

```text
paper_constraint
implementation_guard
fixed-column validation
```

---

# 17. PRM-C01 Passenger Group Selection

对每个：

```text
pax_group_id = g
```

要求：

```text
sum(w_i for i belonging to g) = 1
```

允许候选包括：

```text
transported itinerary
unserved itinerary
```

如果某 passenger group：

```text
没有任何 itinerary
```

应 fail fast 或模型 infeasible，按当前输入 contract 明确处理。

建议：

```text
建模前 fail fast
```

因为这属于 candidate data 不完整，而不是业务优化产生的 infeasibility。

---

# 18. PRM-C02 Schedule Consistency

Transported itinerary 中的每个：

```text
FLIGHT segment
```

都必须引用：

```text
required_operated_option_ids
```

不得使用：

```text
CANCEL
FERRY
non-selected alternate Flight Option
```

如果 itinerary 使用：

```text
FO_F3_D30
```

而 schedule selected：

```text
FO_F3_ORIG
```

则该 itinerary：

```text
不得被选择
```

可以通过：

```text
w_i = 0
```

或预过滤。

优先采用便于 diagnostics 的 deterministic eligible flag。

---

## 18.1 Surface segment

`surface`：

```text
不消耗 aircraft seat capacity
```

但必须继续通过 fixed-column itinerary validator：

```text
OD continuity
time continuity
```

Phase 2.5 不额外设计 surface transport capacity。

若未来需要 bus/train capacity：

```text
airline-specific extension
```

后续再做。

---

# 19. PRM-C03 Seat Capacity

建立：

```text
A_PI[o,i]
```

表示 Passenger Itinerary `i` 是否使用 Flight Option `o`。

对每个实际 operated revenue option：

```text
sum(
    passenger_count[group(i)]
    * A_PI[o,i]
    * w_i
)
<= seat_capacity[o]
```

其中：

```text
passenger_count = Scenario.PassengerCommodity.count
```

---

## 19.1 Unserved

Unserved itinerary：

```text
segments = []
```

因此：

```text
不消耗任何 Flight Option seat capacity
```

但产生：

```text
unserved passenger cost
```

---

## 19.2 Capacity 是人数，不是 group 数

严禁写：

```text
sum(w_i) <= seat_capacity
```

必须使用：

```text
PassengerCommodity.count
```

例如：

```text
P4.count = 15
```

选择一个 itinerary 就消耗：

```text
15 seats
```

而不是 1 seat。

---

# 20. PRM-C04 Fixed Itinerary Feasibility

进入模型前或 selected audit 时必须确认现有 validator 提供的：

```text
pax_group ownership
OD continuity
time continuity
final_destination
arrival_time
arrival_delay_minutes
flight option validity
UNSERVED shape
```

如果当前 validator 对 connection feasibility 只是：

```text
arr_time <= next dep_time
```

而没有真实：

```text
MCT
```

不得在 Phase 2.5 静默声称已经实现真实 Minimum Connection Time。

继续记录：

```text
fixed-column itinerary feasibility assumption
```

未来 Phase 7 Passenger Itinerary Generator 再正式处理 MCT。

---

# 21. Passenger Reaccommodation 的定义

Phase 2.5 不需要新建单独 binary “reaccommodated”。

Reaccommodation 从 selected itinerary 与 original itinerary 比较派生。

建议定义 deterministic audit：

```text
selected transported itinerary
uses flight-option path different from original planned path
→ passenger group is reaccommodated
```

但必须注意：

```text
同一路径只是 Flight Option 延误
```

不一定应视为 reaccommodation。

建议第一版：

```text
base-flight sequence 改变
或引入 surface segment
→ reaccommodated
```

若只是：

```text
FO_F2_ORIG → FO_F2_D50
```

base flight 不变：

```text
不计 reaccommodation
```

该规则属于 implementation metric mapping，应登记 assumption。

---

# 22. PRM Objective

当前 Cost Contract 已预留：

```text
passenger_delay_per_pax_minute
unserved_passenger
```

并均由：

```text
CostOwner.PRM
```

拥有。

第一版 PRM objective：

```text
min
Σ transported itinerary passenger delay cost
+
Σ unserved passenger cost
```

---

# 23. Transported Itinerary Cost

对 transported itinerary `i`：

```text
delay_cost(i)
=
passenger_count[g]
*
arrival_delay_minutes[i]
*
passenger_delay_per_pax_minute
```

禁止：

```text
只乘 delay_minutes，不乘 passenger count
```

也禁止重复计入：

```text
flight delay cost
```

因为 Flight delay 已由 SRM owner 收取。

---

# 24. Unserved Cost

对 unserved itinerary：

```text
unserved_cost(i)
=
passenger_count[g]
*
unserved_passenger
```

不得再额外计算：

```text
arrival_delay_minutes
```

因为 unserved itinerary 当前无 arrival time / delay。

如果论文对 spill passenger 有其他成本结构：

```text
以论文核对结果为准
```

当前 cost mapping 必须在 assumption 中说明。

---

# 25. Passenger Itinerary Cost Pure Function

建议在：

```text
backend/config/costs.py
```

延续现有模式，新增：

```python
passenger_itinerary_cost(...)
```

以及 immutable：

```text
PassengerItineraryCostBreakdown
```

至少输出：

```text
total
passenger_count
status
arrival_delay_minutes
weighted_passenger_delay_minutes
delay_cost
unserved_passengers
unserved_cost
```

要求：

```text
side-effect free
deterministic
does not trust columns.cost_components as source of truth
```

---

# 26. Passenger Incidence

Phase 2.0 总计划已有：

```text
A_FI
Flight / Flight Option - Passenger Itinerary
```

Phase 2.5 应实现或扩展统一：

```text
PassengerRecoveryIncidence
```

至少包含：

```text
group_to_itineraries
option_to_itineraries
itinerary_to_flight_options
transported_itineraries
unserved_itineraries
```

要求：

```text
immutable
deterministic ordering
explicit unknown-reference errors
```

不要在 `prm.py` 多次临时扫描 itinerary。

---

# 27. 建议文件结构

建议：

```text
backend/core/prm.py
backend/core/passenger_incidence.py
backend/config/passenger_capacity.py
```

或按当前目录风格合并。

测试：

```text
tests/unit/test_passenger_capacity.py
tests/unit/test_passenger_incidence.py
tests/unit/test_prm.py
tests/regression/test_phase2_prm_benchmark_001.py
```

如果一个文件足够清楚，不要求形式化过度拆分。

---

# 28. PRM Build 顺序

建议固定：

```text
1. validate Scenario
2. validate RecoveryColumns
3. validate PassengerCapacityProfile
4. validate PassengerRecoveryRequest
5. build FlightOption index
6. build PassengerGroup index
7. build PassengerItinerary index
8. build passenger incidence
9. derive schedule-eligible itineraries
10. verify capacity coverage for referenced operated options
11. create w variables
12. PRM objective
13. passenger-group exactly-one
14. schedule consistency
15. seat-capacity constraints
16. optimize through SolverAdapter
17. normalize ModelSolveResult
18. independent passenger audit
```

---

# 29. ModelSolveResult

继续使用：

```text
ModelSolveResult
```

并设置：

```text
model = PRM
single_model_only = true
```

PRM OPTIMAL 只表示：

> 给定当前 schedule 和 test seat-capacity profile，在当前 fixed Passenger Itineraries 下找到 passenger recovery optimum。

不得声称：

```text
完整 AIR recovery optimal
真实 aircraft capacity feasible
真实 passenger protection plan feasible
```

---

# 30. PRM Diagnostics

至少输出：

```text
selected_itinerary_by_group
transported_passengers
unserved_passengers
reaccommodated_passengers
weighted_passenger_delay_minutes
flight_seat_load
flight_seat_capacity
flight_seat_slack
capacity_violations
unexpected_flight_options
objective_breakdown
```

建议同时输出 group-level：

```text
pax_group_id
selected_itinerary_id
status
count
arrival_delay_minutes
weighted_delay
reaccommodated
```

便于人工审核。

---

# 31. Independent Audit

Solver 结束后必须独立复算：

```text
每个 Passenger Group 是否恰选一个 itinerary
selected transported itinerary 是否 schedule-compatible
seat load 是否 <= capacity
unserved count
reaccommodated count
weighted passenger delay
delay cost
unserved cost
total PRM objective
```

禁止仅：

```text
solver_status == OPTIMAL
```

就声明 PASS。

---

# 32. Unit Tests — Group Selection

至少：

```text
1 group / 2 transported + 1 unserved
→ exactly one selected
```

以及：

```text
group has no itinerary
→ explicit failure
```

---

# 33. Unit Tests — Schedule Consistency

覆盖：

```text
selected schedule contains FO_F2_D50
itinerary uses FO_F2_D50
→ eligible
```

```text
itinerary uses FO_F2_ORIG
→ ineligible
```

另测：

```text
CANCEL cannot appear in transported itinerary
FERRY cannot appear in passenger itinerary
```

---

# 34. Unit Tests — Capacity

必须建立真正会 crossing threshold 的小案例。

例如：

```text
capacity = 20

P1 count = 12
P2 count = 10
```

若两个 group 都选择该 flight：

```text
load = 22
→ infeasible / solver chooses alternate itinerary or unserved
```

要求明确验证：

```text
seat load 按 passenger count 计算
```

而非 group count。

---

# 35. Unit Tests — Alternative Itinerary

构造：

```text
Direct flight capacity insufficient
Alternative connection available
```

验证：

```text
PRM 选择 alternative itinerary
而不是无条件 unserved
```

前提：

```text
alternative total cost < unserved cost
且各段均有 seat
```

---

# 36. Unit Tests — Unserved

构造：

```text
所有 transported itineraries capacity 均不足
+
存在 explicit UNSERVED itinerary
```

应得到：

```text
OPTIMAL
selected = UNSERVED
```

而不是：

```text
INFEASIBLE
```

如果没有 unserved itinerary：

```text
可返回 INFEASIBLE / candidate coverage error
```

必须在 input contract 中明确。

---

# 37. Unit Tests — Passenger Delay Cost

使用非零：

```text
passenger_delay_per_pax_minute
```

例如：

```text
count = 10
arrival_delay = 30
coefficient = 2
```

应：

```text
weighted passenger delay = 300 pax-min
delay cost = 600
```

必须独立断言。

---

# 38. Unit Tests — Unserved Cost

例如：

```text
count = 10
unserved coefficient = 100
```

应：

```text
unserved cost = 1000
```

不得按 group 数计成 100。

---

# 39. Unit Tests — Surface Segment

验证：

```text
surface segment 不消耗 flight seats
```

但仍参与：

```text
fixed itinerary continuity
final arrival
```

不额外加入 surface cost，除非 Cost Contract 以后正式扩展。

---

# 40. Negative / Fail-fast Tests

至少：

```text
unknown pax_group_id
duplicate itinerary_id
unknown flight option
CANCEL referenced by transported itinerary
FERRY referenced by passenger itinerary
capacity profile unknown option
negative capacity
missing capacity for selected/referenced operated option
scenario_id mismatch
duplicate passenger group itinerary contract
invalid unserved shape
transported itinerary missing arrival_delay
```

已有 Pydantic / Column Validator 覆盖的错误可以复用，不重复造第二套 validator，但 PRM entry point 应 fail fast。

---

# 41. Benchmark Regression

使用：

```text
phase1_benchmark_001
phase1_benchmark_001_columns
phase2_test_costs_v1
phase2_test_seat_capacity_v1
```

推荐至少建立两个 regression path。

---

## 41.1 SRM optimum schedule → PRM

流程：

```text
solve SRM
↓
extract_required_operated_option_ids
↓
PRM
```

结果可以：

```text
OPTIMAL
```

也可以因为 fixed itinerary / capacity coverage 不足：

```text
INFEASIBLE
```

如果 infeasible：

> 必须分析是 schedule mismatch、fixed itinerary shortage 还是 test capacity shortage，不得修改 SRM 来迁就 PRM。

---

## 41.2 Manual Reference schedule → PRM

使用 Phase 1 Manual Reference：

```text
F2 +50
F10 +20
F11 +10
...
```

以及现有人工 Passenger Itineraries。

目标：

```text
至少存在一个可人工解释的 PRM feasible / optimal baseline
```

当前 Manual Reference 已有：

```text
P4 reaccommodated 15 pax
weighted passenger delay = 1800 pax-min
unserved = 0
```

但 Phase 2.5 是否重现这些指标取决于：

```text
test seat-capacity profile
PRM cost
可用 fixed itineraries
```

因此：

> 只有当 capacity profile 和 fixed-column choice 确实支持时，才能把 1800 / 15 / 0 固定成 regression invariant。

不得为了匹配 Manual Reference 人为调 cost。

---

# 42. 必须新增 `toy_case_003`

总计划已经预留：

```text
toy_case_003
Passenger capacity / reaccommodation conflict case
```

Phase 2.5 是最合理的实现时机。

建议该 fixture 极小化：

```text
2-3 Passenger Groups
2-3 operated Flight Options
1 个容量瓶颈
1 条 alternative itinerary
1 个 explicit unserved option
```

必须能人工算出：

```text
seat load
alternative choice
unserved choice
objective
```

它将成为 PRM 最重要的独立 Oracle fixture。

---

# 43. Seat Capacity Test Profile 设计原则

至少支持三种状态：

```text
capacity enough
capacity forces reaccommodation
capacity forces unserved
```

不要把所有 capacity 设得极大，否则 Seat Capacity Constraint 虽存在却从不 active。

也不要全部过低导致 benchmark 永远只有 unserved。

---

# 44. PRM Cost Profile

当前：

```text
passenger_delay_per_pax_minute
unserved_passenger
```

已经存在于 Phase 2 Cost Config。

Phase 2.5 要做的是：

```text
真正调用这两个系数进入 PRM objective
+
增加 pure cost audit
```

不得新增：

```text
passenger_reaccommodation flat cost
surface transfer cost
missed connection cost
```

除非论文/现有 Cost Contract 有明确依据。

---

# 45. Reaccommodation 不是独立 Cost Owner

当前项目可先：

```text
reaccommodation = diagnostic / metric
```

成本通过：

```text
arrival delay
+
unserved
```

体现。

如果未来确认论文存在额外 itinerary/reaccommodation penalty：

```text
再升级 Cost Contract
```

不要本阶段凭经验添加。

---

# 46. 与 SRM Market-seat Proxy 的关系

Phase 2.2 当前：

```text
SRM-C06 MARKET_SEAT_PROXY
```

只保证：

```text
market_flag=true / min_seats>0
→ flight cannot cancel
```

它不证明真实 seats。

Phase 2.5 实现正式 Seat Capacity 后：

> 不要立即删除 SRM-C06。

原因：

```text
SRM 与 PRM 当前仍是独立模型
```

Phase 2.5 Report 应说明：

```text
SRM market-seat proxy remains a schedule-level provisional constraint;
PRM seat capacity is the first explicit passenger seat-load constraint.
```

到：

```text
Phase 3 Integrated Oracle
```

再重新审查：

```text
是否保留 SRM proxy
是否由 PRM capacity 完整取代
是否映射回论文真实 market-seat equation
```

---

# 47. 与 ARM Seat Capacity 的未来关系

当前 Phase 2.5 capacity 是：

```text
external test profile by Flight Option
```

未来真实结构应更可能是：

```text
selected Aircraft String
→ aircraft/equipment
→ seat capacity
→ Flight Option capacity
→ PRM
```

但这属于：

```text
Phase 3 Integrated Oracle / later real-data contract
```

Phase 2.5 不提前实现。

必须在 assumption 中留痕，避免未来把 test capacity 当作 aircraft truth。

---

# 48. Assumptions

执行前读取最新：

```text
assumptions.md
```

从下一个可用编号继续。

预计至少需要登记：

```text
PRM external schedule boundary
Test seat-capacity profile provenance
Passenger group indivisibility / splitting mapping
Fixed itinerary feasibility trust
Seat-load counted by passenger count
Passenger delay cost mapping
Unserved cost mapping
Reaccommodation diagnostic mapping
PRM single-model result boundary
```

如果重新核对 `(3.16)-(3.18)` 后某项是 paper-defined：

> 不要错误登记为 implementation assumption。

---

# 49. Schema / Docs 同步

如果新增：

```text
PassengerCapacityProfile
```

必须同步：

```text
Python schema / config
example test capacity file
README
Reproduction Plan
reproduction_notes
assumptions
必要的 schema documentation
tests
```

但默认：

```text
不修改 PassengerItinerary v1.0.0 schema
```

除非重新核对论文后发现现有结构无法表达必要变量。

---

# 50. Gurobi Integration

继续使用 Phase 2.3 / 2.4 已建立的：

```text
不可 skip integration gate
```

Phase 2.5 报告必须明确：

```text
total
passed
failed
skipped
Gurobi version
PRM integration executed = yes/no
```

如果核心 PRM Gurobi regression 被 skip：

```text
Phase 2.5 不得完整 PASS
```

---

# 51. Phase 2.5 Acceptance Criteria

Phase 2.5 只有以下全部满足才能 PASS：

- [ ] 已重新核对论文 `(3.16)-(3.18)`；
- [ ] Paper equation → fixed-column implementation mapping 已记录；
- [ ] 使用现有 fixed Passenger Itineraries；
- [ ] 不动态生成 itinerary；
- [ ] PRM 不重新决定 SRM schedule；
- [ ] canonical operated-option handoff 被复用；
- [ ] CANCEL 不进入 passenger flight segment；
- [ ] FERRY 不进入 passenger itinerary；
- [ ] Test Seat Capacity Contract 已建立；
- [ ] `min_seats` 未被误用为 aircraft seat capacity；
- [ ] capacity 按 passenger count 而非 group count 消耗；
- [ ] 每个 passenger group 恰选一个 itinerary / unserved；
- [ ] non-selected Flight Option itinerary 不得被选；
- [ ] Seat Capacity Constraint 真正 active 并有 threshold test；
- [ ] Alternative itinerary test PASS；
- [ ] Unserved test PASS；
- [ ] Surface segment 不消耗 flight seats；
- [ ] Passenger delay cost 使用 passenger-minutes；
- [ ] Unserved cost 使用 passenger count；
- [ ] PRM 只收取 PRM-owned cost；
- [ ] objective 可独立复算；
- [ ] Reaccommodation metric 可独立复算；
- [ ] 至少一个 PRM feasible regression；
- [ ] 至少一个 capacity shortage regression；
- [ ] `toy_case_003` 已建立；
- [ ] Normal / Negative / Infeasible tests 完整；
- [ ] full pytest PASS；
- [ ] 0 skipped；
- [ ] Gurobi integration 实际执行；
- [ ] assumptions 已同步；
- [ ] README / reproduction plan / reproduction_notes 同步；
- [ ] 未修改 HTML；
- [ ] 未进入 Integrated Oracle；
- [ ] 未进入 Benders / CG。

---

# 52. Phase 2.5 Codex Report

完成后新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase2_5_fixed_column_prm_report.md
```

至少包含：

```text
1. Modified Files
2. Paper (3.16)-(3.18) Mapping
3. PRM Input Contract
4. Seat Capacity Contract
5. Capacity Provenance / Assumptions
6. Passenger Itinerary Schema Reuse / Changes
7. Constraint Mapping Table
8. Passenger Group Splitting Policy
9. Cost Ownership
10. Passenger Cost Function
11. New Assumptions
12. Unit / Negative / Infeasible Tests
13. toy_case_003 Result
14. SRM → PRM Handoff Result
15. Manual Reference → PRM Result
16. Seat Capacity Audit
17. Reaccommodation / Unserved Audit
18. Passenger Delay Audit
19. Objective Audit
20. Full Pytest Result
21. Gurobi Result
22. Known Limitations
23. Acceptance Checklist
24. Next Recommended Step
```

最终必须明确：

```text
Phase 2.5 PASS
```

或：

```text
Phase 2.5 NOT PASS
```

不得只写：

```text
Done
```

---

# 53. Phase 2.5 明确禁止

不得：

```text
使用 Flight.min_seats 作为真实 seat capacity
凭 aircraft/equipment 名称猜座位数
修改 SRM 结果来让 PRM 可行
修改成本来强行匹配 Manual Reference
动态生成 Passenger Itinerary
实现真实 MCT 而不登记数据/规则来源
实现 cabin/fare class inventory
实现 loyalty / priority / fare compensation
修改 HTML
进入 Integrated Oracle
进入 Benders
进入 Column Generation
```

---

# 54. Phase 2.5 完成后的下一步

只有 Phase 2.5 PASS 后，Phase 2 四个子模型才全部独立完成：

```text
SRM
ARM
CRM
PRM
```

然后进入：

```text
Phase 3
Full Integrated Fixed-Column Oracle
```

Phase 3 才首次将：

```text
Schedule
+
Aircraft
+
Crew
+
Passenger
```

放进同一个 MIP，并统一：

```text
SRM Cost
+
ARM Cost
+
CRM Cost
+
PRM Cost
```

在进入 Phase 3 前，应先对 Phase 2 做一次总审查，重点冻结：

```text
cross-model coupling
seat-capacity source
market-seat proxy 去留
cost units / weights
tie-breaking policy
fixed-column coverage gaps
```

不要在 Phase 2.5 中提前实现这些联合逻辑。
