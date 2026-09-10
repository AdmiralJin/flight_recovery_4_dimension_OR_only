# AIR 论文复现与业务迁移开发计划
## HTML 前端数据编辑 + Python 后端优化计算

> 目标：以 Petersen et al. (2010) AIR（Airline Integrated Recovery）模型为基础，建立一个可持续扩展、可人工核验、可与真实航空公司业务逐步对接的复现工程。  
> 前端使用 HTML/JavaScript 负责数据编辑、场景配置和结果展示；后端 Python 负责校验、候选网络/列构造、数学建模、求解与诊断。  
> 核心原则：**任何复杂算法都必须先有一个更简单、可人工核验或可整体求解的 Oracle。**

---

# 0. 当前项目状态（2026-09）

| Phase | 状态 | 当前事实 |
|---|---|---|
| Phase 0 | ✅ 完成 | Scenario 数据层、Pydantic Schema、跨实体 Validator、HTML Data Editor、toy case |
| Phase 0.5 | ✅ 完成 | 原计划、扰动、风险传播、容量热力图等确定性可视化 |
| Phase 1 | ✅ 完成 | 人工数据资产、Python/JSON Schema、Semantic Validator、指标复算、Regression/Negative Tests |
| Phase 2+ | ⏳ 未开始 | Fixed-column 四模型、Integrated Oracle、Benders、CG 等 |

因此当前准确表述是：

> **Phase 1 已完成数据、候选列和人工 Oracle 的程序化语义闭环；这不等于已证明 AIR 恢复目标的数学全局最优性。**

---

# 1. 总体系统目标

最终形成：

```text
HTML / Vanilla JavaScript
│
├── Scenario / Airport / Flight 编辑
├── Aircraft / Crew 编辑
├── Passenger 编辑
├── Airport Capacity / Disruption 编辑
├── Original / Disruption / Recovery Visualization
│
├── Validate
└── Solve
        ↓ HTTP / JSON
FastAPI / Python
│
├── Scenario Schema & Validation
├── Recovery Columns / Expected Validation
├── Scope Limiting
│
├── Flight Option / String Generator
├── Crew Pairing Generator
├── Passenger Itinerary Generator
│
├── SRM
├── ARM
├── CRM
├── PRM
│
├── Full Integrated Oracle
├── Benders
├── Column Generation
└── Diagnostics
        ↓
Gurobi / CPLEX / Pyomo 等
```

---

# 2. 总体开发原则

## 2.1 论文复现、实现假设与业务扩展必须分离

始终区分：

```text
Paper-defined
vs
Implementation assumption
vs
Airline-specific extension
```

推荐边界：

```text
backend/core/
    论文复现核心

backend/application/
    真实航空公司扩展规则

assumptions.md
    论文缺口与本项目实现选择
```

禁止把真实业务规则静默写入论文模型核心。

---

## 2.2 每增加一层复杂度，都保留上一级 Oracle

```text
人工 Reference
    ↓
Fixed-column SRM / ARM / CRM / PRM
    ↓
Full Integrated Fixed-column Oracle
    ↓
Fixed-column Benders
    ↓
Full-column / Brute-force Enumeration
    ↓
Column Generation
    ↓
Benders + Column Generation
```

复杂版本只有在小实例上与简单版本一致后才能进入下一阶段。

---

## 2.3 测试案例分层

不再要求一个 toy case 承担所有职责。

### `toy_case_001`

定位：

```text
Phase 0 / Phase 0.5 smoke fixture
```

用于：

- Schema；
- Validator；
- Frontend round-trip；
- Visualization；
- 简单风险传播。

### `phase1_benchmark_001`

定位：

```text
Phase 1 main integration benchmark
```

用于：

- Manual Flight Options；
- Manual Aircraft Strings；
- Manual Crew Pairings；
- Manual Passenger Itineraries；
- Manual Reference Recovery；
- Fixed-column model oracle input。

规模：

```text
4 airports
12 flights
4 aircraft
5 crew
8 passenger groups
8h recovery horizon
1 departure-capacity disruption
```

后续还应继续维护：

```text
toy_case_002
    必须取消案例

toy_case_003
    Passenger capacity / reaccommodation 冲突案例
```

---

## 2.4 每个 Phase 必须有验收门槛

每个 Phase 必须明确：

```text
Input
Output
Unit Tests
Negative Tests
Benchmark
Acceptance Criteria
```

禁止只用：

```text
程序运行成功
solver status = OPTIMAL
```

作为完成标准。

---

# 3. 技术栈

## 前端

当前：

- HTML；
- CSS；
- Vanilla JavaScript；
- 原生 SVG / DOM Visualization。

当前不引入 React / Vue。

原因：

- 核心难点仍是 OR 正确性；
- 当前规模足够；
- 减少构建链和状态同步复杂度。

---

## 后端

- Python 3.11+；
- FastAPI；
- Pydantic；
- 后续 Pandas / NetworkX；
- Gurobi 优先。

没有 Gurobi 时可替换为其他可审计 MIP/LP Solver。

---

## 数据交换

统一使用：

```text
JSON
```

数据分为三层：

```text
Scenario Input
Recovery Columns
Expected / Solver Result
```

三者必须明确分离。

---

# 4. 推荐目录

```text
flight_recovery_4_dimension_OR_only/
│
├── README.md
├── assumptions.md
├── reproduction_notes.md
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   ├── styles.css
│   │   └── visualization.css
│   └── js/
│       ├── app.js
│       ├── api.js
│       ├── tables.js
│       ├── results.js
│       └── visualization.js
│
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── validate.py
│   │   ├── solve.py
│   │   └── examples.py
│   ├── schemas/
│   │   ├── airport.py
│   │   ├── flight.py
│   │   ├── aircraft.py
│   │   ├── crew.py
│   │   ├── passenger.py
│   │   ├── capacity.py
│   │   ├── disruption.py
│   │   ├── scenario.py
│   │   ├── columns.py          # Phase 1B
│   │   └── expected.py         # Phase 1B
│   ├── services/
│   │   ├── validator.py
│   │   ├── column_validator.py # Phase 1B
│   │   ├── oracle_validator.py # Phase 1B
│   │   ├── recovery_metrics.py # Phase 1B
│   │   ├── validation_common.py
│   │   ├── solver_service.py
│   │   └── result_formatter.py
│   ├── core/
│   │   ├── incidence.py
│   │   ├── scope.py
│   │   ├── flight_network.py
│   │   ├── string_generator.py
│   │   ├── crew_network.py
│   │   ├── pairing_generator.py
│   │   ├── itinerary_generator.py
│   │   ├── srm.py
│   │   ├── arm.py
│   │   ├── crm.py
│   │   ├── prm.py
│   │   ├── integrated_oracle.py
│   │   ├── benders.py
│   │   ├── pricing.py
│   │   └── integrality.py
│   └── application/
│       └── airline_rules/
│
├── data/
│   ├── examples/
│   │   ├── toy_case_001.json
│   │   └── phase1_benchmark_001.json
│   ├── columns/
│   │   └── phase1_benchmark_001_columns.json
│   └── expected/
│       └── phase1_benchmark_001_expected.json
│
├── schemas/
│   ├── recovery_columns_v1.schema.json
│   └── recovery_expected_v1.schema.json
│
├── docs/
│   ├── AIR_HTML_Python_Reproduction_Plan.md
│   ├── RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md
│   └── benchmarks/
│       └── PHASE1_BENCHMARK_001_DESIGN.md
│
└── tests/
    ├── unit/
    ├── regression/
    ├── oracle/
    └── manual/
```

> 标准目录是 `data/columns/`。若当前仓库仍为 `data/colums/`，应重命名，后续禁止继续沿用误拼写。

---

# 5. Phase 0：可验证 Scenario 数据层

## 目标

回答：

> 系统到底在优化什么原始数据？

Phase 0 不实现优化。

---

## 5.1 Scenario 实体

### Airport

```text
airport_id
name
```

### Flight

```text
flight_id
origin
destination
sched_dep
sched_arr
duration
original_aircraft
original_equipment
original_crew
strategic_flag
market_flag
min_seats
max_delay
```

### Aircraft

```text
tail_id
equipment_type
initial_station_at_t
required_station_at_T_end
maintenance_required
maintenance_stations
original_rotation
```

### Crew

```text
crew_id
rating
start_station_at_t
required_station_at_T_end
original_duties
original_pairing
```

### PassengerCommodity

```text
pax_group_id
count
origin
destination
original_departure
scheduled_arrival
original_itinerary
```

### AirportInterval

```text
airport
start_time
end_time
arr_capacity
dep_capacity
gate_capacity
curfew_flag
weather_restrictions
```

### Disruption

```text
airport
start_time
end_time
capacity_change
restriction_type
```

---

## 5.2 Data Editor

当前 HTML Data Editor 已支持：

- Load Example；
- Add / Edit / Duplicate / Delete；
- Import JSON；
- Export JSON；
- Reset；
- Validate。

人工修改保留在同页面内存 State。

---

## 5.3 `/api/validate`

Scenario Validator 至少检查：

- ID 唯一性；
- 外键引用；
- dep < arr；
- duration；
- Recovery Window；
- Aircraft Rotation 连续；
- Crew Pairing 连续；
- Passenger Itinerary 连续；
- Capacity Interval 不重叠；
- Disruption 引用合法。

---

## Phase 0 验收

- [x] HTML 可编辑 Scenario；
- [x] JSON Import / Export；
- [x] `/api/validate` 返回机器可读错误；
- [x] 错误数据不进入 Solver；
- [x] `toy_case_001` 稳定存在；
- [x] Frontend / Backend 数据往返。

**Phase 0：Completed。**

---

# 6. Phase 0.5：确定性场景可视化

## 目标

在尚无 Solver 时，让人直观看到：

```text
原计划
+
扰动
+
资源传播风险
+
机场容量压力
```

---

## 核心组件

1. Time-Space Network；
2. Disruption Overlay；
3. Resource Detail；
4. Airport Capacity Heatmap。

Visualization 与 Data Editor 共享 Scenario State。

---

## 语义边界

当前：

```text
Direct Exposure
Downstream Risk
```

不是：

```text
Actual Delay
Cancellation
Recovered Solution
```

禁止在没有优化结果时伪造恢复计划。

---

## Phase 0.5 验收

- [x] Data / Visualization 同页切换；
- [x] Scenario State 不丢；
- [x] Visualization 前先 Validate；
- [x] Time-Space Network；
- [x] Disruption / Risk；
- [x] Capacity View；
- [x] Resource Detail。

**Phase 0.5：Completed。**

---

# 7. Phase 1：人工建立 Recovery Columns + Manual Reference

## 目标

建立后续数学模型最重要的第一套人工 Oracle 数据资产。

Phase 1 分为：

```text
Phase 1A
人工数据与 Reference

Phase 1B
程序化语义验证与回归
```

---

## 7.1 主 Benchmark

使用：

```text
phase1_benchmark_001
```

而不是继续把全部集成任务压在 `toy_case_001` 上。

规模：

```text
4 Airports
12 Flights
4 Aircraft
5 Crew
8 Passenger Groups
```

核心扰动：

```text
B airport
[09:30,10:30)
departure capacity = 2
```

原计划出港：

```text
F2
F5
F8

3 / 2
```

---

## 7.2 Recovery Columns Schema v1.0.0

Columns 顶层：

```text
flight_options
aircraft_strings
crew_pairings
passenger_itineraries
```

标准文件：

```text
data/columns/phase1_benchmark_001_columns.json
schemas/recovery_columns_v1.schema.json
```

详细设计：

```text
docs/RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md
```

---

## 7.3 Flight Option Identity

原 Flight ID 不随恢复动作变化。

例如：

```text
F2
    ├── FO_F2_ORIG
    ├── FO_F2_D50
    └── FO_F2_CANCEL
```

而不是：

```text
F2_DELAY50
```

---

## 7.4 Phase 1 人工列

当前人工候选包括约：

```text
22 Flight Options
11 Aircraft Strings
10 Crew Pairings
17 Passenger Itineraries
```

列集合需要覆盖：

- 原计划；
- Reference Recovery；
- 主要替代方案；
- Schema 能力验证所需 Cancellation；
- Destination Change；
- Ferry；
- Reassignment；
- Passenger Reaccommodation；
- Unserved。

Phase 1 不要求穷举全部合法列。

---

## 7.5 Expected Schema v1.0.0

Expected 不再使用旧的简单结构：

```text
expected_selected_strings
expected_objective
...
```

而统一为：

```text
reference_solution
oracle_invariants
comparison_policy
objective
```

标准文件：

```text
data/expected/phase1_benchmark_001_expected.json
schemas/recovery_expected_v1.schema.json
```

---

## 7.6 当前人工 Reference

核心恢复：

```text
F2 +50
F10 +20
F11 +10
```

Aircraft：

```text
AC1:
F1 → F2 → F10

AC4:
F3 → F11 → F12
```

P4：

```text
F2→F3
→
F8
```

核心指标：

```text
total flight delay = 80 min
aircraft reassignments = 2
crew reassignments = 0
passenger reaccommodated = 15 pax
weighted passenger delay = 1800 passenger-min
cancellations = 0
unserved = 0
```

---

## 7.7 Reference 不等于 Optimal

当前：

```text
reference_type = manual_reference
solution_status = feasible
```

因为 SRM/ARM/CRM/PRM 的正式 Cost Coefficients 尚未全部定义。

不能声称：

```text
80 min reference
=
global optimum
```

例如 Aircraft Swap Cost 足够高时，旧的 110 min 纯延误方案可能在完整成本目标下更优。

---

## 7.8 Phase 1A 验收

- [x] 主 Benchmark 已建立；
- [x] Flight Options 人工建立；
- [x] Aircraft Strings 人工建立；
- [x] Crew Pairings 人工建立；
- [x] Passenger Itineraries 人工建立；
- [x] Columns JSON Schema v1.0.0；
- [x] Expected JSON Schema v1.0.0；
- [x] Manual Reference；
- [x] Oracle Invariants；
- [x] Comparison Policy；
- [x] 主要恢复逻辑可人工解释。

**Phase 1A：Completed。**

---

## 7.9 Phase 1B：Completed

已实现：

```text
backend/schemas/columns.py
backend/schemas/expected.py

backend/services/column_validator.py
backend/services/oracle_validator.py
backend/services/recovery_metrics.py
```

Semantic Validator 至少检查：

1. 所有 ID 唯一；
2. `base_flight_id` 合法；
3. Cancel Option 字段规则；
4. Aircraft String Station/Time 连续；
5. Crew Pairing Station/Time 连续；
6. Passenger Itinerary OD/Time 连续；
7. Expected 引用 Columns 中存在的 ID；
8. 每个原航班选择一个 Flight Option；
9. 每个执行 Flight Option 被 Aircraft 覆盖一次；
10. 每个执行 Flight Option 被 Crew 覆盖一次；
11. Passenger 不使用 Cancelled Flight；
12. Aircraft Terminal / Maintenance；
13. Airport Capacity；
14. Expected Metrics 可重新计算一致。

---

## 7.10 Phase 1B 测试

已建立：

```text
tests/regression/test_phase1_benchmark_001.py
tests/unit/test_column_validator.py
tests/unit/test_oracle_validator.py
```

必须包含正常和故意破坏案例。

---

## Phase 1 总验收

只有以下全部满足后，才将 README 改为：

```text
Phase 1 Completed
```

- [x] 人工数据与 Reference；
- [x] Python Columns / Expected Schema；
- [x] Semantic Validation；
- [x] Regression Test；
- [x] Negative Tests；
- [x] Reference Metrics 程序化复算；
- [x] 所有 Phase 0/0.5 Tests 无回归。

---

# 8. Phase 2：Fixed-Column SRM / ARM / CRM / PRM

Phase 1 工程验收完成后再进入。

目标：

> 先验证四个数学模型，不做 Benders，不做动态 Column Generation。

---

## 8.1 先做 Incidence Matrix Builder

这是 Phase 2 的第一开发任务，不应直接跳到 Solver。

必须构建并独立测试：

```text
A_FS : Flight / Flight Option - Aircraft String
A_MS : Maintenance - Aircraft String
A_FP : Flight / Flight Option - Crew Pairing
A_FI : Flight / Flight Option - Passenger Itinerary
```

建议使用可审计的稀疏结构，并保留 ID mapping。

---

## 8.2 SRM

实现论文：

```text
(3.1) objective
(3.2) flight coverage
(3.3) strategic flights
(3.4) arrival capacity
(3.5) departure capacity
(3.6) gate constraint
(3.7) market seat
```

Phase 1 `flight_options` / `aircraft_strings` 是第一套 fixed columns。

---

## 8.3 ARM

实现论文：

```text
(3.8)-(3.12)
```

必须检查：

- Tail assignment；
- String feasibility；
- Terminal；
- Maintenance；
- Reassignment。

---

## 8.4 CRM

实现：

```text
(3.13)-(3.15)
```

第一版只使用已经人工定义的 Pairings。

---

## 8.5 PRM

实现：

```text
(3.16)-(3.18)
```

必须正式解决 Phase 1 暂未程序化证明的：

- Seat Capacity；
- Passenger Reaccommodation；
- Unserved；
- Arrival Delay Cost。

---

## 8.6 Phase 2 测试

每个模型：

```text
Normal Case
+
Broken / Infeasible Case
```

### SRM

- 每个 Flight 执行或取消；
- Strategic Flight 无合法执行选项时应 Infeasible；
- 改 Airport Capacity 时 Selection 应响应。

### ARM

- 可执行 String → Feasible；
- 资源冲突 → Infeasible；
- Maintenance 无 compatible string → Infeasible。

### CRM

- 正常 Pairing → Feasible；
- 删除全部 Coverage → Infeasible。

### PRM

- Capacity 足够；
- Capacity 不足；
- Alternative Itinerary；
- Unserved。

---

## Phase 2 验收

- [ ] 四模型分别可运行；
- [ ] Incidence Matrices 独立测试；
- [ ] 正常结果符合人工预期；
- [ ] 破坏案例得到预期变化；
- [ ] Solver OPTIMAL 不是唯一判断。

---

# 9. Phase 3：Full Integrated Fixed-Column Oracle

这是后续所有高级算法的 Ground Truth。

暂时不做 Benders。

直接将：

```text
SRM
+
ARM
+
CRM
+
PRM
```

放入一个整体 MIP。

统一 Objective：

```text
SRM Cost
+
ARM Cost
+
CRM Cost
+
PRM Cost
```

此阶段必须正式冻结：

- 各成本项；
- 单位；
- 权重；
- Tie-breaking Policy。

---

## 9.1 与 Manual Reference 比较

对 `phase1_benchmark_001`：

不要求：

```text
Integrated Oracle
==
完整人工 Assignment Vector
```

而要求首先比较：

```text
Feasibility
Objective
Flight recovery decisions
Cancellation
Capacity
Terminal / Maintenance
Passenger service
```

如果 Integrated Oracle 找到比 Manual Reference 更低目标的方案：

> 不应认为 Solver 错，而应检查人工 Reference 是否本来就不是 Optimal。

---

## Phase 3 验收

- [ ] Integrated MIP 可运行；
- [ ] Objective 各成本来源可解释；
- [ ] 所有约束通过独立检查；
- [ ] Benchmark 与 Manual Oracle Invariants 对齐；
- [ ] 若结果优于 Manual Reference，有可人工解释原因。

---

# 10. Phase 4：Scope Limiting

实现论文 Appendix Algorithms 3–6。

输入：

```text
direct disruption
```

自动获得：

```text
disruptable flights
disruptable aircraft
disrupted crew
disrupted passengers
```

传播链：

```text
airport disruption
→ flight
→ aircraft
→ crew
→ additional flights
→ passenger connection
→ additional candidates
```

Oracle：

```text
OBJ_scope == OBJ_full
```

同时期望 Scope 明显减小。

---

# 11. Phase 5：Flight String Generator

第一版：

> 只生成合法列，不做 Pricing。

至少处理：

- Station continuity；
- Flight timing；
- Turn Time；
- Max Delay；
- Airport restrictions；
- Recovery Horizon；
- Maintenance；
- Terminal Station。

验证：

```text
smart generator
vs
brute-force / full-enumeration oracle
```

要求：

- 不生成非法列；
- 不遗漏 Oracle Optimal 所需关键列。

---

# 12. Phase 6：Crew Pairing Generator

建立 Crew Duty Network：

```text
G_k
```

Source-to-Sink Path：

```text
=
candidate repaired pairing
```

最小 Crew Legality 以后必须明确：

- Airport continuity；
- Timing；
- Maximum Duty；
- Minimum Rest；
- Fleet Qualification；
- Start / End Station。

所有规则先写入 `assumptions.md`。

---

# 13. Phase 7：Passenger Itinerary Generator

论文没有完整给出 Itinerary Generation Algorithm，因此明确标记：

```text
Implementation Assumption / Extension
```

第一版考虑：

- O-D continuity；
- MCT；
- Recovery Horizon；
- Available flights；
- Seat Capacity 在 PRM 内处理。

---

# 14. Phase 8：Fixed-Column Benders

固定：

```text
S
P
Gamma
```

不动态加列。

流程：

```text
SRM Master
    ↓
ARM / CRM / PRM
    ↓
Feasibility / Optimality Cuts
    ↓
Master
```

第一验收：

```text
OBJ_Benders
==
OBJ_Integrated_Oracle
```

同一 Fixed Columns、同一 Objective 下必须成立。

---

# 15. Phase 9：Flight String Column Generation

目标：

> 不再预枚举全部 Flight Strings。

Pricing 输入：

```text
LP duals
flight network
current columns
```

输出：

```text
negative reduced-cost strings
```

Toy/Benchmark 上必须存在：

```text
Full-column LP Oracle
```

最终：

```text
OBJ_CG == OBJ_full_columns
```

终止时暴力检查未加入列：

```text
reduced_cost >= -epsilon
```

---

# 16. Phase 10：Crew Pairing Column Generation

实现 Crew Pairing Reduced Cost。

Toy/Benchmark：

```text
all-pairings LP
vs
crew column-generation LP
```

必须一致。

---

# 17. Phase 11：Benders + Column Generation

只有：

- Fixed-column Benders；
- Flight CG；
- Crew CG；

都独立通过后才组合。

特别注意：

> 新列加入后旧 Benders Cut 的有效性不能想当然。

必须严格实现 Cut Invalidation / Validity Policy。

---

# 18. Phase 12：Integrality / Branching

最后再实现：

- ARM Integrality；
- CRM Follow-on Branching；
- PRM Branching。

此前 LP / Decomposition 必须完成 Oracle 验证。

---

# 19. Phase 13：Recovered Result Visualization

Phase 0.5 已经有 Original/Disruption Visualization。

Solver 接入后扩展为：

```text
Original
Disrupted
Recovered
Difference
```

至少显示：

## Summary

```text
Total Cost
Cancelled Flights
Mean / Max Flight Delay
Passenger Delay
Unserved Passengers
Aircraft Reassignments
Crew Reassignments
Runtime
```

## Flight Recovery

```text
Flight
Original OD / Times
Recovered OD / Times
Delay
Cancelled
Aircraft
Crew
```

## Aircraft

Original vs Recovered Rotation。

## Crew

Original vs Recovered Pairing / Deadhead。

## Passenger

Original vs Recovered Itinerary / Delay / Unserved。

## Diagnostics

```text
iterations
columns
cuts
bounds
subproblem status
runtime
```

---

# 20. 接真实航空公司数据前的门槛

至少满足：

```text
Manual Benchmark
    ↕
Integrated Oracle
    ↕
Fixed-column Benders
```

以及：

```text
Full-column LP
=
Column Generation LP
```

最终：

```text
Integrated Oracle
=
Benders + Column Generation
```

在多个标准案例中稳定成立。

---

# 21. Regression Test 体系

长期至少维护：

## `toy_case_001`

基础 Schema / Visualization / simple propagation。

## `phase1_benchmark_001`

综合 Flight / Aircraft / Crew / Passenger / Capacity 人工 Reference。

## `toy_case_002`

必须 Cancellation。

## `toy_case_003`

Passenger Seat Capacity / Multiple Reaccommodation。

每次修改：

```bash
python -m pytest
```

全部通过。

---

# 22. Solver 日志

每次正式求解至少记录：

```text
run_id
scenario_id
git_commit
solver
solver_version
parameters
```

算法日志：

```text
objective
bound
MIP gap
iterations
number of strings
number of pairings
number of itineraries
cuts
pricing iterations
subproblem status
runtime
```

业务结果：

```text
flight delays
cancellations
aircraft reassignments
crew reassignments
passenger delay
unserved passengers
total cost
```

---

# 23. Assumptions 管理

根目录长期维护：

```text
assumptions.md
```

任何影响：

- 可行域；
- Objective；
- Candidate Generation；
- Recovery Semantics；
- Business Rules；

的实现决定都必须先登记。

当前已经登记 Phase 0/1 的关键数据与 Recovery Column 假设。

Phase 2+ 还需持续加入：

- Cost Model；
- MCT；
- Turn Time；
- Crew Legality；
- Seat Capacity；
- Gate Inventory；
- Diversion；
- Reduced Cost；
- Benders Cut Validity 等。

---

# 24. 业务迁移原则

论文复现基本通过后再建立：

```text
backend/application/airline_rules/
```

逐步加入：

- 南航 Crew Rules；
- Reserve Crew；
- Tail Swap；
- Fleet Substitution；
- Flow Control；
- Weather；
- Curfew；
- Maintenance；
- Important Flight；
- Transfer Passenger Priority；
- International/Domestic Restrictions；
- Ferry；
- Diversion；
- Cancellation Hierarchy；
- Business Cost Model。

禁止静默修改 Core AIR Model。

---

# 25. 推荐 Codex 执行顺序（更新版）

## 已完成 Task 1

```text
Scenario Schema
FastAPI
HTML Data Editor
Validator
toy_case_001
```

## 已完成 Task 2

```text
Phase 0.5 Visualization
```

## 已完成 Task 3A

```text
phase1_benchmark_001
Manual Columns
Columns/Expected JSON Schema
Manual Reference
Documentation
```

## 已完成 Task：Phase 1B

```text
实现 Recovery Columns / Expected 的 Python Schema 和 Semantic Validation；
增加 benchmark001 Regression / Negative Tests；
不要实现 Solver。
```

Phase 1B 工程验收已通过。

## 然后 Task：Phase 2.0

```text
Incidence Matrix Builder
```

## 再依次：

```text
Fixed SRM
→ Fixed ARM
→ Fixed CRM
→ Fixed PRM
→ Integrated Oracle
→ Scope
→ String Generator
→ Pairing Generator
→ Itinerary Generator
→ Fixed Benders
→ Flight CG
→ Crew CG
→ Benders + CG
→ Integrality
```

每步独立任务和 Commit。

---

# 26. 每个 Codex Task 的统一输出

Codex 每个任务必须报告：

```text
1. Modified Files
2. Implemented Features
3. Tests Added
4. Test Results
5. Known Assumptions
6. Known Limitations
7. Comparison With Oracle
8. Next Recommended Step
```

禁止只回复：

```text
Done
```

---

# 27. 禁止事项

不得：

- 未说明修改论文数学模型；
- 把业务规则混进 Core；
- 跳过小规模 Oracle；
- 用真实大规模数据替代正确性测试；
- 只依赖 OPTIMAL；
- 在 Fixed-column Benders 未对齐 Integrated Oracle 前加入 CG；
- 在 Pricing 未经 Full Enumeration 验证前扩大规模；
- 将实现假设称作论文原算法；
- 在 Objective 未定义时把 Manual Reference 称为 Optimal；
- 为性能提前牺牲可审计性。

---

# 28. 最终成功标准

## Level 1：数据正确

Frontend / Backend / Scenario 一致。

## Level 2：候选列正确

Manual / Generated Columns 均经过 Semantic Validation。

## Level 3：单模型正确

SRM / ARM / CRM / PRM 每个关键约束有测试。

## Level 4：整体模型正确

```text
Integrated Oracle
```

在小实例上可人工解释，并与 Benchmark Invariants 对齐。

## Level 5：分解正确

```text
Fixed-column Benders
=
Integrated Oracle
```

## Level 6：列生成正确

```text
Column Generation
=
Full-column LP
```

## Level 7：完整算法正确

```text
Benders + CG
=
Small-scale Oracle
```

## Level 8：业务迁移成功

真实航空公司数据下：

- 方案业务可行；
- 结果可解释；
- Runtime 可接受；
- Recovery Quality 优于基线；
- 所有业务扩展都有独立规则和测试。

---

# 29. 当前立即执行的下一任务

Phase 1 已完成。当前不要直接开始 SRM Solver，而应先开始：

```text
Phase 2.0 Incidence Matrix Builder
```

再进入四个 Fixed-Column Models。

---

# 30. 核心原则总结

```text
先数据
→ 后模型

先人工列
→ 后自动列

先固定列
→ 后列生成

先整体 Oracle
→ 后分解

先小规模 Reference
→ 后真实规模

先证明正确
→ 再追求性能
```

最终每增加一种高级算法，都必须回答：

> **它是否在已知、可审计的小规模实例上，与更简单的 Oracle 得到一致的数学结论？**

如果不能回答，就不得进入下一阶段。
