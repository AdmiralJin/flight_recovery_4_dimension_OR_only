# Phase 1 Benchmark 001 设计说明

> 场景 ID：`phase1_benchmark_001`  
> 用途：Phase 1 人工候选列、人工参考恢复方案与后续 Fixed-Column 模型的主要集成基准  
> 状态：**数据与人工 Reference 已建立；尚未由完整优化模型证明为全局最优解**

---

# 1. Benchmark 定位

`phase1_benchmark_001` 是 Phase 1 的主人工集成基准。

它与 `toy_case_001` 的职责不同：

```text
toy_case_001
    = Phase 0 / Phase 0.5 最小 smoke test
    = 用于验证 Scenario Schema、数据编辑器、可视化与基础跨实体一致性

phase1_benchmark_001
    = Phase 1 人工 integration benchmark
    = 用于人工建立恢复候选列、Reference Solution 与后续 Fixed-Column 模型对照
```

本 Benchmark 的目标不是模拟真实航空公司全规模运行，而是在仍可人工检查的规模下同时包含：

- 机场容量扰动；
- 航班延误；
- Aircraft Rotation；
- Aircraft Reassignment；
- Crew Pairing；
- Passenger Connection；
- Passenger Reaccommodation；
- Maintenance Terminal Requirement；
- Cancellation / Destination Change / Ferry 等备用候选表达能力。

---

# 2. 对应文件

推荐目录：

```text
data/
├── examples/
│   └── phase1_benchmark_001.json
├── columns/
│   └── phase1_benchmark_001_columns.json
└── expected/
    └── phase1_benchmark_001_expected.json

schemas/
├── recovery_columns_v1.schema.json
└── recovery_expected_v1.schema.json

docs/
├── RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md
└── benchmarks/
    └── PHASE1_BENCHMARK_001_DESIGN.md
```

---

# 3. 数据规模

| 对象 | 数量 | 设计目的 |
|---|---:|---|
| Airport | 4 | A / B / C / D，形成多个 OD，但仍可手工画图 |
| Flight | 12 | 足够产生多条连续 Rotation 与资源交叉 |
| Aircraft | 4 | 每架 3 段；AC4 带 Maintenance 要求 |
| Equipment Type | 1 | E1，避免 Phase 1 过早引入机型替代复杂度 |
| Crew | 5 | 含跨 Aircraft 的 Pairing |
| Passenger Group | 8 | 同时有单段与两段联程 |
| Airport Capacity Interval | 4 | B 为核心受扰容量桶 |
| Disruption | 1 | B 机场出港容量下降 |
| Recovery Window | 8 h | 08:00–16:00 UTC |

该规模明显比 `toy_case_001` 丰富，但仍允许逐条人工核对。

---

# 4. 原始 Aircraft Rotations

```text
AC1: F1 A→B → F2 B→C → F3 C→A
AC2: F4 C→B → F5 B→D → F6 D→C
AC3: F7 D→B → F8 B→A → F9 A→D
AC4: F10 C→A → F11 A→D → F12 D→C
```

其中：

```text
AC4
maintenance_required = true
maintenance_stations = [C]
required_station_at_T_end = C
```

原计划 AC4 最终回到 C，因此原 Rotation 满足该 Maintenance Terminal Requirement。

---

# 5. 原始 Crew Pairings

```text
C1: F1 → F2 → F10
C2: F4 → F5 → F6
C3: F7 → F8 → F9
C4: F3 → F11
C5: F12
```

本 Benchmark 一个重要设计点是：

```text
F2 属于 AC1
F10 属于 AC4
但 F2 与 F10 都由 C1 连续执行
```

这使机场扰动可以通过 Crew Chain 跨越 Aircraft Rotation。

---

# 6. Passenger Commodities

主要行程：

```text
P1: F1 → F2
P2: F4 → F5
P3: F7 → F8
P4: F2 → F3
P5: F3 → F11
P6: F10 → F11
P7: F9
P8: F12
```

Phase 1 Columns 中还提供部分备用 itinerary，例如：

- P4 可改签直达 F8；
- P1 存在其他航班组合候选；
- 部分旅客组提供 `unserved` 备用状态。

这些备用列用于确认数据接口能够表达 PRM 后续会涉及的恢复动作，并不代表所有备用 itinerary 都已完成正式座位容量验证。

---

# 7. 核心扰动

机场 B：

```text
Interval: [09:30, 10:30) UTC
Restriction: departure_capacity_reduction
dep_capacity = 2
```

原计划在该时间桶内的 B 出港航班：

```text
F2  09:40  B→C
F5  09:50  B→D
F8  10:00  B→A
```

所以：

```text
planned departures = 3
capacity = 2
```

原计划违反该时间桶的 Departure Capacity。

至少一个航班必须：

- 移出该时间桶；
- 或取消；
- 或通过其他允许的恢复动作消除冲突。

---

# 8. Recovery Column Schema 的核心原则

## 8.1 Flight ID 永远表示原始航班

禁止使用：

```text
F2_DELAY50
F2_CANCEL
F2_DIVERT_C
```

作为新的 Flight ID。

正确方式：

```text
base_flight_id = F2

FO_F2_ORIG
FO_F2_D50
FO_F2_CANCEL
```

即：

```text
Scenario Flight
    ↓
Flight Option
    ↓
Aircraft String / Crew Pairing / Passenger Itinerary
```

这样后续：

- SRM；
- ARM；
- CRM；
- PRM；
- Incidence Matrix；
- Column Generation；

都可以稳定映射回同一个原航班。

---

# 9. Phase 1 人工候选列

当前 `phase1_benchmark_001_columns.json` 基于 Recovery Columns Schema v1.0.0。

它分为四类：

```text
flight_options
aircraft_strings
crew_pairings
passenger_itineraries
```

当前人工资产大致包含：

```text
Flight Options:       22
Aircraft Strings:     11
Crew Pairings:        10
Passenger Itineraries:17
```

这些列不是最终自动列生成器的替代品，而是：

> **Phase 1 用于人工验证模型接口和 Fixed-Column 模型的有限候选空间。**

---

# 10. Flight Options 覆盖的恢复动作

当前候选接口已经能够表达：

```text
unchanged
delay
cancel
origin_change
destination_change
block_time_change
positioning / ferry
```

恢复动作可以组合。

例如未来允许：

```text
delay + destination_change
```

不需要再引入一个新的组合型 Flight ID。

---

# 11. Aircraft String 的恢复表达

Aircraft String 表示一架具体飞机的候选完整路径。

Aircraft Reassignment 不需要单独造“换飞机 Flight”。

如果：

```text
AC1 的 Aircraft String
```

覆盖了原计划属于 AC4 的 F10，则自然表示：

```text
F10 aircraft reassignment:
AC4 → AC1
```

这正是当前 Reference Solution 使用的恢复动作之一。

---

# 12. Crew Pairing 的恢复表达

Crew Pairing 由 Duties 与 Segments 构成。

未来 Segment 可以包括：

```text
operate
deadhead
ground_transfer
rest
```

当前 Benchmark Reference 没有使用 Deadhead 或 Ground Transfer。

Crew Reassignment 的表达规则与 Aircraft Reassignment 相同：

> 某 Crew Pairing 覆盖原计划属于其他 Crew 的 Flight Option，即表示 Crew Reassignment。

---

# 13. Passenger Itinerary 的恢复表达

Passenger Itinerary 可以表达：

```text
保留原行程
延误后的同一路径
改签其他航班
surface transfer
unserved / spill
```

Passenger Group ID 始终保持不变。

---

# 14. 当前人工 Reference Recovery

重新比较纯延误方案与资源交换方案后，当前采用以下人工 Reference：

## 14.1 F2 移出容量桶

F2 原计划：

```text
09:40 B→C
10:40 arrive C
```

恢复为：

```text
10:30 B→C
11:30 arrive C
```

即：

```text
F2 +50 min
```

此时 B `[09:30,10:30)` 中仅剩：

```text
F5
F8
```

所以：

```text
2 / 2
```

满足 Departure Capacity。

---

# 15. 为什么不再采用旧的 F3 +30 纯传播方案

如果保持原 Aircraft Assignment：

```text
AC1:
F1 → F2(+50) → F3
```

F2 到 C 已是 11:30，因此 F3 必须从 11:00 延迟到至少 11:30：

```text
F3 +30
```

同时 Crew C1 的下一任务 F10 也需：

```text
F10 +20
```

旧 Reference 因此出现：

```text
F2  +50
F3  +30
F10 +20
F11 +10

total = 110 flight-delay minutes
```

这个方案是可行的，但不是当前更合理的人工 Reference。

原因是：

```text
F3  = C → A
F10 = C → A
```

二者拥有相同 OD，可通过 AC1 / AC4 之间交换任务减少传播。

---

# 16. 当前 Aircraft Reassignment

当前人工 Reference：

```text
AC1:
F1 → F2(+50) → F10(+20)

AC4:
F3(original time) → F11(+10) → F12
```

因此：

```text
F3:
original aircraft AC1
recovered aircraft AC4

F10:
original aircraft AC4
recovered aircraft AC1
```

总 Aircraft Reassignments：

```text
2
```

这样 F3 可以维持原计划：

```text
11:00 C→A
```

不再需要 +30 分钟延误。

---

# 17. Crew Reference

当前 Reference 不需要 Crew Reassignment。

```text
C1:
F1 → F2(+50) → F10(+20)

C2:
F4 → F5 → F6

C3:
F7 → F8 → F9

C4:
F3(original) → F11(+10)

C5:
F12
```

因此：

```text
crew_reassignments = 0
```

---

# 18. P4 Passenger Reaccommodation

P4 原计划：

```text
F2 → F3
```

恢复后：

```text
F2 arrives C = 11:30
F3 departs C = 11:00
```

所以原连接不再成立。

当前人工 Reference 将 P4 改签到：

```text
F8
B → A
10:00–11:00
```

即：

```text
P4:
original F2→F3
→
recovered F8
```

P4 共：

```text
15 pax
```

因此当前 Reference：

```text
passenger_reaccommodated_groups = 1
passenger_reaccommodated_count = 15
```

注意：

Phase 1 尚未实现完整 PRM 座位容量模型，因此这里表示：

> 人工候选 itinerary 与当前 benchmark policy 下的参考选择。

真正的 seat-capacity feasibility 必须在后续 PRM / Fixed-Column 模型中正式验证。

---

# 19. 为什么 F11 +10

P6 原 itinerary：

```text
F10 → F11
```

恢复后：

```text
F10 arrive A = 12:30
```

F11 原计划：

```text
12:20 A→D
```

因此 F11 至少需要延迟至：

```text
12:30
```

当前 Phase 1 假设没有额外 Passenger MCT，只要求：

```text
previous arrival <= next departure
```

所以：

```text
F11 +10
```

足以保留 P6 的连接。

后续若正式引入 Minimum Connection Time，需要建立新的测试案例或更新该 Benchmark Policy，不能静默改变当前 Reference。

---

# 20. 当前 Reference 的 Flight Result

| Flight | Recovery |
|---|---:|
| F1 | unchanged |
| **F2** | **+50 min** |
| F3 | unchanged |
| F4 | unchanged |
| F5 | unchanged |
| F6 | unchanged |
| F7 | unchanged |
| F8 | unchanged |
| F9 | unchanged |
| **F10** | **+20 min** |
| **F11** | **+10 min** |
| F12 | unchanged |

因此：

```text
delayed_flights = 3
total_flight_departure_delay_minutes = 80
cancelled_flights = 0
origin_changed_flights = 0
destination_changed_flights = 0
```

---

# 21. Passenger Reference Outcome

当前 Reference 主要 Passenger Delay：

```text
P1: +50 min, 30 pax
P4: 通过 F8 改签，arrival_delay = 0
P5: +10 min, 18 pax
P6: +10 min, 12 pax
其余: 0
```

Weighted Passenger Delay：

```text
P1: 30 × 50 = 1500
P5: 18 × 10 = 180
P6: 12 × 10 = 120

total = 1800 passenger-minutes
```

当前：

```text
unserved_passengers = 0
```

---

# 22. Reference Metrics

当前人工 Reference 的核心指标：

```text
operated_flights = 12
cancelled_flights = 0
delayed_flights = 3

aircraft_reassignments = 2
crew_reassignments = 0

passenger_reaccommodated_groups = 1
passenger_reaccommodated_count = 15

total_flight_departure_delay_minutes = 80
passenger_delay_minutes_weighted = 1800
unserved_passengers = 0
```

---

# 23. 为什么它叫 Manual Reference，而不是 Optimal Solution

`phase1_benchmark_001_expected.json` 应明确：

```text
reference_type = manual_reference
solution_status = feasible
```

目前不能写：

```text
solution_status = optimal
```

原因是尚未正式确定完整 AIR 目标函数中的：

- Flight Delay Cost；
- Cancellation Cost；
- Aircraft Reassignment Cost；
- Crew Reassignment Cost；
- Passenger Disruption Cost；
- Route Change Cost；
- Ferry / Deadhead Cost；
- 其他论文实现所需成本系数。

例如：

> 如果一次 Aircraft Swap 的成本非常高，则 80 分钟 + 2 次换机未必优于 110 分钟纯延误方案。

因此当前人工 Reference 的意义是：

> 在明确的 Phase 1 Behavioral Policy 下提供一套可行、可解释、相对合理的恢复结果，用于验证后续模型。

---

# 24. Expected 文件为什么拆成 Reference + Oracle Invariants

Expected 不应只保存一个完整 Solution Vector。

当前设计：

```text
reference_solution
+
oracle_invariants
+
comparison_policy
+
objective
```

其中：

## `reference_solution`

保存一套具体人工恢复方案。

## `oracle_invariants`

保存真正应该用于自动验收的业务/数学不变量。

## `comparison_policy`

规定哪些字段必须严格相等，哪些允许等价解。

## `objective`

在成本未定义前：

```text
status = not_defined
value = null
```

---

# 25. 等价解问题

当前 benchmark 中存在资源交换空间。

因此后续 Solver 不应该在成本未定义前要求：

```text
returned aircraft assignment
==
manual reference aircraft assignment
```

而应该优先比较：

- 每个 Flight 的恢复状态；
- Cancellation；
- Delay Vector；
- Capacity Feasibility；
- Aircraft / Crew Path Feasibility；
- Terminal / Maintenance；
- Passenger Service；
- Objective（正式定义后）。

只有当成本和模型唯一确定后，才可以收紧 exact-assignment 比较。

---

# 26. Phase 1 当前完成度

## 已完成

- [x] 建立 `phase1_benchmark_001` Scenario；
- [x] 建立 Recovery Columns Schema v1.0.0；
- [x] 建立 Recovery Expected Schema v1.0.0；
- [x] 人工建立 Flight Options；
- [x] 人工建立 Aircraft Strings；
- [x] 人工建立 Crew Pairings；
- [x] 人工建立 Passenger Itineraries；
- [x] 建立人工 Reference Solution；
- [x] 建立 Oracle Invariants / Comparison Policy；
- [x] 人工解释主要恢复链和主要替代方案；
- [x] Python/Pydantic Columns / Expected Schema；
- [x] Column / Oracle Semantic Validator；
- [x] benchmark001 自动 regression test；
- [x] 按具体错误码断言的 negative tests；
- [x] Reference Metrics 程序化复算。

## 后续 Phase 尚未完成

- [ ] 由 Fixed-Column SRM/ARM/CRM/PRM 对人工 Reference 做程序化核验；
- [ ] 完整目标函数与成本系数；
- [ ] 由 Integrated Fixed-Column Oracle 证明真正 Optimality。

因此：

> **Phase 1 工程验收已完成；它证明当前数据/候选列/人工 Oracle 的语义一致性，不证明 AIR 恢复目标的数学全局最优性。**

---

# 27. 后续使用原则

`phase1_benchmark_001` 应长期作为：

```text
人工 Reference
      ↓
Fixed-column four models
      ↓
Full Integrated Oracle
      ↓
Benders
      ↓
Column Generation
      ↓
Benders + CG
```

的第一条集成验证链。

任何高级算法在该实例上与简单版本不一致，都应先解释差异，而不是直接扩大数据规模。

---

# 28. 本 Benchmark 的明确非目标

当前阶段不用于验证：

- 真实航空公司完整 Crew Legality；
- 真实 Minimum Connection Time；
- 真实 Seat Inventory；
- 多机型替代；
- Reserve Crew；
- 国际/国内航班限制；
- Curfew 复杂规则；
- 多机场天气联动；
- 大规模 Column Generation；
- Benders Convergence；
- 真实业务 Cost Calibration。

这些内容必须在后续 Phase 中逐层加入，并保留更简单版本作为 Oracle。

---

# 29. 一句话总结

```text
phase1_benchmark_001
=
一个仍可人工完整解释，
但已经同时包含 Flight、Aircraft、Crew、Passenger 与 Airport Capacity 耦合的
Phase 1 Fixed-Column 人工基准。
```

当前人工 Reference 为：

```text
F2 +50
Aircraft swap: F3 / F10
F10 +20
P4 → F8
F11 +10

Total Flight Delay = 80 min
Weighted Passenger Delay = 1800 passenger-min
Cancellation = 0
Unserved Pax = 0
```

它是 **Manual Feasible Reference**，不是尚未证明的全局最优解。
