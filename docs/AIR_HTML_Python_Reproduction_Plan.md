# AIR 论文复现与业务迁移开发计划
## HTML 前端数据编辑 + Python 后端优化计算

> 目标：以 Petersen et al. (2010) AIR（Airline Integrated Recovery）模型为基础，搭建一个可持续扩展的复现与业务迁移工程。  
> 前端使用 HTML/JavaScript 负责数据编辑、场景配置与结果展示；后端使用 Python 负责数据校验、网络构造、优化建模、求解与结果分析。  
> 核心原则：**任何复杂算法都必须先有一个简单、可人工核验或可整体求解的基准版本（oracle）作为正确性参照。**
>
> 本计划的第一目标不是性能，而是避免复杂 OR 项目中最常见的问题：
>
> **“代码能跑、求解器显示 OPTIMAL，但不知道模型、数据、分解或列生成到底有没有写错。”**

---

# 1. 总体目标

最终形成如下系统：

```text
HTML / JavaScript 前端
│
├── Airports 编辑
├── Flights 编辑
├── Aircraft 编辑
├── Crew 编辑
├── Passenger / Demand 编辑
├── Airport Capacity 编辑
├── Disruption Scenario 编辑
├── Recovery Horizon 编辑
│
├── 点击 Validate
├── 点击 Solve
│
└── 查看优化结果
      ↓ HTTP / JSON
FastAPI 后端
│
├── schema / 数据校验
├── preprocessing / scope limiting
├── network generators
├── flight string generator
├── crew pairing generator
├── passenger itinerary generator
│
├── SRM
├── ARM
├── CRM
├── PRM
│
├── full integrated oracle
├── Benders
├── column generation
└── result diagnostics
      ↓
Gurobi / CPLEX / Pyomo / NetworkX / Pandas
```

---

# 2. 总体开发原则

## 2.1 论文复现层与业务扩展层必须分离

项目必须明确区分：

```text
论文明确给出的内容
vs
论文未完全给出、代码必须补全的假设
vs
南航/实际业务新增规则
```

禁止直接把业务扩展规则写进论文模型核心代码而不做区分。

推荐：

```text
core/
    尽可能忠实于 Petersen 2010

application/
    实际航空公司业务规则

assumptions/
    论文缺口与实现者补全
```

---

## 2.2 每增加一层复杂度，都必须有上一级作为 oracle

例如：

```text
人工答案
    ↓
Fixed-column 四模型
    ↓
Full Integrated MIP
    ↓
Benders
    ↓
Column Generation
    ↓
Benders + Column Generation
```

复杂版本只有在小实例上与简单版本一致后才能进入下一阶段。

---

## 2.3 所有算法先在 toy case 上验证

第一版禁止直接接真实大规模航空数据。

建议第一标准实例：

```yaml
airports: 3
flights: 6
aircraft: 2
equipment_types: 1
crew: 2-3
passenger_groups: 3-5
recovery_horizon: 8h
disruption:
  type: airport_capacity_reduction
max_delay: 60min
```

必须保证：

- 可以人工理解；
- 可以人工列举 flight strings；
- 可以人工列举 crew pairings；
- 可以人工判断主要恢复选择；
- 可以使用整体 MIP 得到 ground truth。

---

## 2.4 每一步必须有明确验收门槛

每一个 Phase 必须包含：

```text
输入
输出
单元测试
反例测试
基准测试
验收标准
```

禁止仅用：

```text
程序运行成功
solver status = OPTIMAL
```

作为完成标准。

---

# 3. 技术栈

## 前端

第一版：

- HTML
- CSS
- Vanilla JavaScript

暂时不要引入 React / Vue。

原因：

- 第一阶段重点是 OR 模型；
- 原生 HTML table 足够进行 toy case 编辑；
- 减少额外工程复杂度。

后续数据量和交互复杂后，再考虑 Vue / React。

---

## 后端

推荐：

- Python 3.11+
- FastAPI
- Pydantic
- Pandas
- NetworkX
- Gurobi (`gurobipy`) 优先

如无 Gurobi，可使用：

- CPLEX / docplex
- Pyomo + 商业求解器

---

## 数据交换

统一使用：

```text
JSON
```

前端编辑后发送：

```http
POST /api/validate
POST /api/solve
```

后端返回 JSON。

---

# 4. 推荐项目目录

```text
air_recovery/
│
├── README.md
├── requirements.txt
├── assumptions.md
├── reproduction_notes.md
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── app.js
│       ├── tables.js
│       ├── api.js
│       └── results.js
│
├── backend/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── validate.py
│   │   ├── solve.py
│   │   └── examples.py
│   │
│   ├── schemas/
│   │   ├── airport.py
│   │   ├── flight.py
│   │   ├── aircraft.py
│   │   ├── crew.py
│   │   ├── passenger.py
│   │   ├── capacity.py
│   │   ├── disruption.py
│   │   └── scenario.py
│   │
│   ├── core/
│   │   ├── scope.py
│   │   ├── flight_network.py
│   │   ├── string_generator.py
│   │   ├── crew_network.py
│   │   ├── pairing_generator.py
│   │   ├── itinerary_generator.py
│   │   │
│   │   ├── srm.py
│   │   ├── arm.py
│   │   ├── crm.py
│   │   ├── prm.py
│   │   │
│   │   ├── integrated_oracle.py
│   │   ├── benders.py
│   │   ├── pricing.py
│   │   └── integrality.py
│   │
│   ├── application/
│   │   └── airline_rules/
│   │
│   ├── services/
│   │   ├── validator.py
│   │   ├── solver_service.py
│   │   └── result_formatter.py
│   │
│   └── utils/
│       ├── time.py
│       ├── logging.py
│       └── incidence.py
│
├── data/
│   ├── examples/
│   │   ├── toy_case_001.json
│   │   ├── toy_case_002.json
│   │   └── toy_case_003.json
│   │
│   └── expected/
│       ├── toy_case_001_expected.json
│       ├── toy_case_002_expected.json
│       └── toy_case_003_expected.json
│
├── tests/
│   ├── unit/
│   │   ├── test_schema.py
│   │   ├── test_scope.py
│   │   ├── test_strings.py
│   │   ├── test_pairings.py
│   │   ├── test_srm.py
│   │   ├── test_arm.py
│   │   ├── test_crm.py
│   │   └── test_prm.py
│   │
│   ├── oracle/
│   │   ├── test_integrated_oracle.py
│   │   ├── test_benders_vs_oracle.py
│   │   └── test_cg_vs_full_columns.py
│   │
│   └── regression/
│       └── test_toy_cases.py
│
└── logs/
```

---

# 5. Phase 0：先建立可验证的数据层

## 目标

先解决：

> “系统到底在优化什么数据？”

暂时不写任何优化模型。

---

## 5.1 定义统一数据 Schema

至少定义以下实体。

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

## 5.2 建立 Scenario 顶层 Schema

例如：

```json
{
  "recovery_window": {},
  "airports": [],
  "flights": [],
  "aircraft": [],
  "crew": [],
  "passengers": [],
  "airport_intervals": [],
  "disruptions": []
}
```

---

## 5.3 第一版 HTML 数据编辑器

页面至少包含以下 Tab：

```text
Scenario
Airports
Flights
Aircraft
Crew
Passengers
Airport Capacity
Disruptions
```

每个表格支持：

- Add Row
- Delete Row
- Edit Cell
- Duplicate Row
- Reset
- Load Example
- Export JSON
- Import JSON

---

## 5.4 后端 `/api/validate`

只做数据校验，不做优化。

校验至少包括：

### Flight

- origin 存在；
- destination 存在；
- dep < arr；
- aircraft 存在；
- crew 存在；
- max_delay >= 0。

### Aircraft rotation

- 航班机场连续；
- 时间顺序正确；
- aircraft equipment 一致。

### Crew

- duty 中航班存在；
- rating 与 fleet 兼容；
- duty 时间顺序正确。

### Passenger

- itinerary 航班存在；
- O-D 连续；
- connecting flights 顺序正确。

### Recovery horizon

- 所有参与恢复的数据在合理时间范围内；
- `t < T_end`。

---

## Phase 0 验收

必须满足：

- [ ] HTML 可以完整编辑 toy case
- [ ] 前端能导出 JSON
- [ ] JSON 能重新导入
- [ ] `/api/validate` 能返回错误位置
- [ ] 错误数据不能进入优化
- [ ] toy_case_001.json 可以稳定复现

完成 Phase 0 后才开始写数学模型。

---

# 6. Phase 1：人工建立标准 Toy Case + Expected Solution

## 目标

建立整个项目最重要的测试基准。

---

## 6.1 toy_case_001

建议：

```text
Airport: A, B, C
Flight: F1-F6
Aircraft: AC1, AC2
Crew: C1-C3
Passenger groups: P1-P4
```

人为设计一个简单扰动：

```text
B airport
09:00-11:00
departure capacity reduction
```

使得至少出现：

- 一个航班延误；
- 一个 aircraft propagation；
- 一个 crew connection 受到影响；
- 一个 passenger connection 受到影响。

---

## 6.2 人工建立列

第一阶段禁止自动生成。

人工建立：

```text
5-20 Flight Strings
5-20 Crew Pairings
若干 Passenger Itineraries
```

保存为：

```text
toy_case_001_columns.json
```

---

## 6.3 人工记录 Expected Solution

至少记录：

```json
{
  "expected_cancelled_flights": [],
  "expected_selected_strings": [],
  "expected_aircraft_assignment": {},
  "expected_crew_assignment": {},
  "expected_passenger_assignment": {},
  "expected_objective": 0
}
```

如果存在多个等价最优解：

不要强制比较完整 solution vector。

改为比较：

- objective；
- feasibility；
- cancellation count；
- delay；
- assignment invariants。

---

## Phase 1 验收

必须做到：

- [ ] 每条 Flight String 人工确认合法
- [ ] 每条 Crew Pairing 人工确认合法
- [ ] 每条 Passenger Itinerary 人工确认合法
- [ ] 能人工解释最优方案为什么优于主要替代方案
- [ ] Expected Solution 被写入版本库

---

# 7. Phase 2：固定列实现 SRM / ARM / CRM / PRM

## 目标

先验证四个数学模型，不做 Benders，不做 Column Generation。

---

## 7.1 SRM

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

---

## 7.2 ARM

实现：

```text
(3.8)-(3.12)
```

---

## 7.3 CRM

实现：

```text
(3.13)-(3.15)
```

---

## 7.4 PRM

实现：

```text
(3.16)-(3.18)
```

---

## 7.5 构造四个 Incidence Matrices

必须独立实现和测试：

```text
A_FS : Flight - String
A_MS : Maintenance - String
A_FP : Flight - Pairing
A_FI : Flight - Itinerary
```

建议做成通用稀疏结构。

---

# 8. Phase 2 的关键验证方法

每个模型都必须做：

```text
正常案例
+
故意破坏案例
```

---

## SRM 测试

### Case S1

正常 flight：

```text
必须恰好：
执行
or
取消
```

### Case S2

Strategic flight：

删除所有可执行 string。

期望：

```text
INFEASIBLE
```

### Case S3

人为降低 airport capacity。

检查 selected strings 是否变化。

---

## ARM 测试

### Case A1

一条 selected string 存在可执行 tail。

期望 feasible。

### Case A2

两条 selected string 只能由同一架 tail 执行。

期望 infeasible。

### Case A3

Maintenance aircraft 无 maintenance-compatible string。

期望 infeasible。

---

## CRM 测试

### Case C1

每个 flight 有合法 crew。

期望 feasible。

### Case C2

删除某个 flight 的全部合法 pairings。

期望：

```text
INFEASIBLE
```

---

## PRM 测试

### Case P1

10 seats，8 passengers。

全部可分配。

### Case P2

10 seats，20 passengers。

检查：

```text
reaccommodated <= 10
```

其余进入 unassigned。

---

## Phase 2 验收

- [ ] 四模型分别能独立运行
- [ ] 正常案例结果符合人工预期
- [ ] 故意破坏案例得到预期 infeasible / assignment change
- [ ] 所有 incidence matrices 有独立 unit tests
- [ ] solver = OPTIMAL 不是唯一验收标准

---

# 9. Phase 3：建立 Full Integrated Fixed-Column Oracle

## 这是后续所有高级算法最重要的 Ground Truth

暂时不要使用 Benders。

直接将：

```text
SRM
ARM
CRM
PRM
```

全部放入一个整体 MIP。

统一目标：

```text
SRM cost
+
ARM cost
+
CRM cost
+
PRM cost
```

---

## Oracle 用途

未来验证：

```text
Benders
Column Generation
Benders + CG
```

---

## 核心比较指标

必须保存：

```text
objective
selected strings
cancelled flights
aircraft assignments
crew assignments
passenger assignments
```

---

## Phase 3 验收

toy_case_001：

```text
Integrated Oracle
=
人工 Expected Solution
```

如果有多个等价解：

至少：

```text
objective 相同
所有约束可行
关键业务指标相同
```

---

# 10. Phase 4：Scope Limiting

实现论文 Appendix Algorithms 3-6。

---

## 目标

输入：

```text
direct disruption
```

自动得到：

```text
disruptable flights
disruptable aircraft
disrupted crew
disrupted passengers
```

---

## 必须验证传播链

```text
airport disruption
    ↓
flight
    ↓
aircraft rotation
    ↓
crew duty
    ↓
additional flights
    ↓
passenger connection
    ↓
additional candidate flights
```

---

## Oracle 验证

同一个 toy case：

### Full Scope

所有资源进入优化：

```text
OBJ_full
```

### Reduced Scope

使用 Algorithms 3-6：

```text
OBJ_scope
```

应满足：

```text
OBJ_scope == OBJ_full
```

同时：

```text
|F_scope| < |F_full|
```

如果 objective 变差：

说明 Scope Limiting 很可能漏掉了必要资源。

---

# 11. Phase 5：Flight String Generator

第一版：

**只做合法枚举，不做 pricing。**

---

## Generator 必须处理

- flight sequence continuity
- arrival + turn time
- departure feasibility
- max delay
- event-driven timing interval
- airport restrictions
- valid connection
- recovery horizon

---

## 第一层验证：人工案例

构造：

```text
F1 arrival = 09:00
min_turn = 40
```

必须拒绝：

```text
F2 dep = 09:30
```

必须允许：

```text
F2 dep >= 09:40
```

---

## 第二层验证：Brute Force Oracle

为 toy case 单独实现：

```text
brute_force_string_generator.py
```

允许非常慢。

例如：

```text
每10分钟枚举一次 timing
```

比较：

```text
smart_generator
vs
brute_force_generator
```

重点不是两者集合必须机械完全相等，而是：

- smart generator 不生成非法方案；
- 关键合法方案不能遗漏；
- smart generator 能覆盖 oracle 最优解所需列。

---

## Phase 5 验收

- [ ] 所有生成 strings 合法
- [ ] 无违反 turn time
- [ ] 无违反 max delay
- [ ] time-dependent boundaries 正确
- [ ] oracle 最优方案所需 string 不被遗漏

---

# 12. Phase 6：Crew Pairing Generator

第一版不做 pricing。

建立：

```text
crew duty network
G=(D,A)
```

对每个 crew：

```text
G_k
```

source-to-sink path：

```text
=
repaired pairing
```

---

## 最小 Crew Legality

如果真实 crew rule 数据暂时没有：

只定义一个明确的最小规则集，例如：

- airport continuity；
- 时间连续；
- maximum duty；
- minimum rest；
- fleet qualification；
- start station；
- required end station。

必须写入：

```text
assumptions.md
```

明确：

```text
这些是复现实现假设，不代表论文完整 crew legality，也不代表南航真实规则。
```

---

## 验收

- [ ] pairing 起点正确
- [ ] pairing 终点正确
- [ ] duty legality 正确
- [ ] flight coverage incidence 正确
- [ ] 人工 pairing 与 generator 结果一致

---

# 13. Phase 7：Passenger Itinerary Generator

因为原论文没有完整给出 itinerary generation algorithm，所以必须单独标记为：

```text
Implementation Assumption / Extension
```

---

## 第一版只考虑

- O-D continuity
- minimum connection time
- recovery horizon
- available flights
- seat capacity 在 PRM 中处理

---

## 验收

- [ ] 所有 itinerary 路径合法
- [ ] 时间顺序合法
- [ ] connection time 合法
- [ ] delay_minutes 计算正确
- [ ] flight-itinerary incidence 正确

---

# 14. Phase 8：Fixed-Column Benders

这一步才开始实现 Benders。

固定：

```text
S
P
Gamma
```

不允许动态新增列。

---

## 流程

```text
SRM Master
    ↓
ARM
CRM
PRM
    ↓
feasibility / optimality cuts
    ↓
SRM
```

---

## 第一验收标准

对于相同 fixed columns：

```text
OBJ_Benders
==
OBJ_Integrated_Oracle
```

---

## 第二验收标准

主动构造：

### ARM infeasible

必须产生 ARM feasibility cut。

### CRM infeasible

必须产生 CRM feasibility cut。

### CRM feasible but costly

optimality cut 必须影响 Master bound。

### PRM 同理。

---

## 必须记录每轮

```text
iteration
master_LP_obj
master_MIP_obj

num_ARM_cuts
num_CRM_feas_cuts
num_CRM_opt_cuts
num_PRM_feas_cuts
num_PRM_opt_cuts

ARM_status
CRM_status
PRM_status
```

---

# 15. Phase 9：Flight String Column Generation

这一步只解决：

```text
如何避免预先枚举全部 Flight Strings
```

先不要和全部复杂 Benders 逻辑同时开发。

---

## Pricing 输入

```text
master LP duals
flight network
current columns
```

输出：

```text
negative reduced cost strings
```

---

## 最关键验证方式：Full-column LP Oracle

toy case 上可以预先枚举：

```text
S_all
```

直接求：

```text
LP_full_columns
```

然后从：

```text
S0 ⊂ S_all
```

开始 column generation。

最终必须：

```text
OBJ_CG == OBJ_full_columns
```

---

## Pricing 终止验证

CG 声称结束时：

对所有：

```text
s ∈ S_all \ S_current
```

暴力重新计算 reduced cost。

必须满足：

```text
reduced_cost >= -epsilon
```

否则 pricing 漏列。

---

# 16. Phase 10：Crew Pairing Column Generation

实现论文 Eq. (5.6)：

```text
pairing reduced cost
```

动态生成：

```text
P_k
```

---

## Oracle 验证

toy case：

```text
全部 pairings 预枚举 LP
vs
column generation LP
```

必须一致。

---

# 17. Phase 11：Benders + Column Generation

只有前面全部通过后才实现。

包括：

- dynamic flight strings
- dynamic crew pairings
- Benders cuts
- cut invalidation
- Algorithm 2
- Farkas validity certificate

---

## 特别注意

新增 Flight String 后：

旧 Benders cut 可能失效。

必须严格按照当前复现约定处理。

不能：

```text
继续保留所有旧 cut
```

然后仅因为 solver 收敛就认为算法正确。

---

## 验收

toy case：

```text
Full Integrated Oracle
≈
Benders + CG
```

如果模型理论上对应同一固定问题：

objective 必须一致。

如果某些实现假设导致模型空间不同：

必须在日志中解释差异来源。

---

# 18. Phase 12：Integrality / Branching

最后再实现：

```text
ARM integrality
CRM follow-on branching
PRM branching
```

此前所有 LP / decomposition 逻辑必须已经验证。

---

# 19. Phase 13：HTML 结果可视化

前端不只显示：

```text
Objective = xxx
```

至少展示：

---

## Summary

```text
Total Cost
Cancelled Flights
Mean Flight Delay
Max Flight Delay
Passenger Delay
Unassigned Passengers
Crew Deadheads
Runtime
```

---

## Flight Recovery Table

```text
Flight
Original Dep
Recovered Dep
Delay
Cancelled?
Aircraft
Crew
```

---

## Aircraft Recovery

按 aircraft 展示：

```text
AC1:
F1 -> F4 -> F6
```

---

## Crew Recovery

展示：

```text
Crew C1
Original Pairing
Recovered Pairing
Deadhead
```

---

## Passenger Recovery

展示：

```text
Group
Original Itinerary
Recovered Itinerary
Delay
Unassigned
```

---

## Solver Diagnostics

必须提供开发模式：

```text
iterations
columns generated
cuts generated
master bound
subproblem status
runtime
```

这样前端不仅是业务界面，也是模型调试工具。

---

# 20. Phase 14：接真实航空公司数据前的验收门槛

必须至少满足：

```text
人工 Toy Solution
      =
Full Integrated Oracle
      =
Fixed-column Benders
```

以及：

```text
Full-column LP
      =
Column Generation LP
```

最后：

```text
Integrated Oracle
      =
Benders + Column Generation
```

在多个 toy cases 上均稳定成立。

---

# 21. Regression Test 体系

至少维护三个标准案例。

---

## toy_case_001：正常扰动

验证：

- delay propagation
- aircraft
- crew
- passenger

---

## toy_case_002：必须取消

人为制造：

```text
capacity + aircraft + crew
```

使一个 flight 必须取消。

验证 cancellation logic。

---

## toy_case_003：旅客容量冲突

制造：

```text
limited seats
multiple reaccommodation choices
```

验证 PRM。

---

每次修改代码：

```bash
pytest
```

必须全部通过。

---

# 22. Solver 日志规范

每次求解生成：

```text
run_id
scenario_id
git_commit
solver
solver_version
parameters
```

记录：

```text
master objective
master bound
MIP gap
iterations

number of strings
number of pairings
number of itineraries

cuts by type
pricing iterations

ARM status
CRM status
PRM status

runtime by module
```

最终业务结果：

```text
mean flight delay
max flight delay
cancellations
deadheads
mean passenger delay
unassigned passengers
total cost
```

---

# 23. Assumptions 管理

项目根目录必须长期维护：

```text
assumptions.md
```

每条假设格式：

```markdown
## A-001 Integrated Master Objective

Source status:
论文没有完整重新打印 integrated objective。

Implementation:
SRM objective + eta_CRM + eta_PRM

Reason:
标准 Benders 结构。

Impact:
可能影响与论文数值结果的严格一致性。
```

至少记录：

- integrated master objective
- passenger itinerary generation
- PRM `s_i` domain
- flight-string reduced cost mapping
- crew legality
- reserve crew
- diversion
- gate inventory interpretation
- Algorithm 1 中潜在符号歧义

---

# 24. 业务迁移原则

完整论文复现基本通过后，再建立：

```text
backend/application/airline_rules/
```

不要修改 core 模型来偷偷适配业务。

---

## 后续可以逐步加入

- 南航机组值勤规则
- reserve crew
- tail swap
- fleet substitution
- airport flow control
- weather restriction
- curfew
- maintenance rules
- important flights
- VIP / transfer passenger priority
- international/domestic restrictions
- ferry flights
- diversion
- cancellation hierarchy
- business-specific cost model

---

# 25. 推荐 Codex 执行方式

不要一次让 Codex：

```text
“把整个 Petersen AIR 模型实现出来”
```

而应该按 Phase 分任务。

---

## Task 1

```text
只搭建项目目录、FastAPI、HTML 数据编辑器和 Pydantic Schema。
不要实现任何优化模型。
完成后运行数据验证测试。
```

验收后 commit。

---

## Task 2

```text
建立 toy_case_001。
实现 JSON import/export 与 expected solution。
不要实现 Benders 或 column generation。
```

验收后 commit。

---

## Task 3

```text
实现 fixed-column SRM。
完成 SRM unit tests 和反例测试。
```

验收后 commit。

---

## Task 4

```text
实现 fixed-column ARM。
```

依次完成 CRM、PRM。

---

## Task 5

```text
实现 Full Integrated Fixed-Column Oracle。
```

必须与 Expected Solution 比较。

---

之后：

```text
Scope
→ String Generator
→ Pairing Generator
→ Itinerary Generator
→ Fixed Benders
→ Flight CG
→ Crew CG
→ Benders + CG
→ Integrality
```

每步一个独立任务和 commit。

---

# 26. 每个 Codex Task 的统一验收模板

Codex 每完成一个任务，必须输出：

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

禁止只回答：

```text
Done.
```

---

# 27. 禁止事项

在完整复现阶段，Codex 不应：

- 未经说明修改论文数学模型；
- 将业务规则混入 core；
- 跳过 toy case；
- 直接拿大规模数据验证；
- 只依赖 solver OPTIMAL 判断正确；
- 在 pricing 未通过 full enumeration 验证前进入大规模 CG；
- 在 Benders 未与 integrated oracle 对齐前加入 CG；
- 将论文未给出的内容描述为“原论文算法”；
- 为追求性能提前优化代码结构。

---

# 28. 最终成功标准

## Level 1：数据正确

HTML 编辑的数据经过 Python 校验完全一致。

---

## Level 2：模型正确

SRM / ARM / CRM / PRM 每条关键约束均有测试。

---

## Level 3：整体数学模型正确

```text
Full Integrated Oracle
=
人工 Expected Solution
```

---

## Level 4：分解算法正确

```text
Fixed-column Benders
=
Full Integrated Oracle
```

---

## Level 5：列生成正确

```text
Column Generation
=
Full-column LP
```

---

## Level 6：完整算法正确

```text
Benders + Column Generation
=
小规模 Oracle
```

---

## Level 7：应用迁移成功

真实航空公司数据下：

- 方案业务可行；
- 结果可解释；
- 运行时间可接受；
- 恢复质量优于基线；
- 所有业务扩展均有独立规则和测试。

---

# 29. 推荐当前立即执行的第一任务

当前不要实现 Benders、Column Generation 或 Crew Duty Network。

先让 Codex 完成：

```text
Phase 0 + Phase 1
```

即：

1. 创建项目骨架；
2. 创建 FastAPI；
3. 创建 HTML 数据编辑器；
4. 建 Pydantic schemas；
5. 实现 JSON import/export；
6. 实现 `/api/validate`；
7. 创建 `toy_case_001.json`；
8. 创建 `toy_case_001_expected.json`；
9. 创建基础数据一致性测试；
10. 确保前后端数据往返完全一致。

完成并验收后，再开始 SRM。

---

# 30. 核心原则总结

整个项目始终遵循：

```text
先数据
→ 后模型

先固定
→ 后动态

先整体
→ 后分解

先枚举
→ 后列生成

先小规模真值
→ 后真实规模

先证明正确
→ 再追求性能
```

最终每增加一种高级算法，都必须回答：

> **“它是否在已知正确的小实例上，得到与简单 oracle 相同的答案？”**

如果不能回答，就不得进入下一阶段。
