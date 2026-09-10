# Reproduction Notes

本文件记录 Petersen et al. (2010) AIR 论文与当前代码仓库之间的复现边界、已完成层级和仍未实现部分。

---

# 1. Reproduction Strategy

项目采用逐层 Oracle 结构：

```text
Scenario/Data Boundary
    ↓
Manual Columns + Manual Reference
    ↓
Fixed-column SRM / ARM / CRM / PRM
    ↓
Full Integrated Fixed-column Oracle
    ↓
Fixed-column Benders
    ↓
Column Generation
    ↓
Benders + Column Generation
```

核心原则：

> 复杂版本只有在小实例上与更简单、可审计版本一致后，才进入下一阶段。

---

# 2. Phase 0：Data Boundary

Phase 0 已建立：

- Scenario Schema；
- Airports；
- Flights；
- Aircraft；
- Crew；
- Passenger Commodities；
- Airport Capacity Intervals；
- Disruptions；
- 跨实体一致性 Validator；
- JSON Import / Export；
- FastAPI 数据接口；
- `toy_case_001`；
- HTML 数据编辑工作台。

Phase 0 不包含：

- Flight String optimization；
- Mathematical decision variables；
- Solver；
- Benders；
- Column Generation。

`/api/solve` 仍然是安全闸门：合法数据在真正 Solver 接入前不应假装求解成功。

---

# 3. Phase 0.5：Deterministic Visualization

Phase 0.5 已在同一前端工作台增加 Visualization。

当前可视化读取合法 Scenario，展示：

- 原计划时空网络；
- 已知 Disruption；
- Direct Exposure；
- 沿原 Aircraft/Crew Chain 的 Downstream Risk；
- Airport Capacity Load。

它不产生恢复决策。

特别注意：

```text
direct exposure / downstream risk
!=
actual delay / cancellation / optimized recovery
```

Phase 0.5 不属于 OR 求解器。

---

# 4. `toy_case_001` 的定位

`toy_case_001` 包含：

- 3 Airports；
- 6 Flights；
- 2 Aircraft；
- 2 Cockpit Crews；
- 4 Passenger Groups；
- 8 小时 Recovery Horizon；
- B 机场 Departure Capacity Reduction。

它现在主要是：

```text
Phase 0 / 0.5 smoke fixture
```

用于验证：

- Scenario Schema；
- Validator；
- Frontend round-trip；
- Visualization；
- 简单风险传播。

它不再承担 Phase 1 主 Integrated Benchmark 的全部职责。

---

# 5. Phase 1 主 Benchmark

Phase 1 主人工集成基准为：

```text
phase1_benchmark_001
```

主要规模：

```text
4 Airports
12 Flights
4 Aircraft
5 Crew
8 Passenger Groups
1 Departure-Capacity Disruption
```

其职责是：

- 人工建立 Flight Recovery Options；
- 人工建立 Aircraft Strings；
- 人工建立 Crew Pairings；
- 人工建立 Passenger Itineraries；
- 人工建立一套可解释 Reference Recovery；
- 为后续 Fixed-Column 模型提供第一套综合 Oracle 输入。

详细设计见：

```text
docs/benchmarks/PHASE1_BENCHMARK_001_DESIGN.md
```

---

# 6. Phase 1 Columns Exchange Format

Phase 1 已定义 Recovery Columns Schema v1.0.0。

顶层分为：

```text
flight_options
aircraft_strings
crew_pairings
passenger_itineraries
```

核心设计：

> 原 Flight ID 永不被恢复动作修改。

例如：

```text
base_flight_id = F2

FO_F2_ORIG
FO_F2_D50
FO_F2_CANCEL
```

该接口可表达：

- unchanged；
- delay；
- cancellation；
- origin change；
- destination change；
- ferry / positioning；
- aircraft reassignment；
- crew reassignment；
- passenger reaccommodation；
- unserved passenger。

Schema 设计详见：

```text
docs/RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md
```

---

# 7. Phase 1 Expected / Oracle Format

Expected Schema v1.0.0 不再把 Ground Truth 简化为一个完整 Solution Vector。

它区分：

```text
reference_solution
oracle_invariants
comparison_policy
objective
```

原因是后续可能存在等价 Assignment。

因此：

- `reference_solution`：给出一套人工具体方案；
- `oracle_invariants`：定义真正应通过的验证条件；
- `comparison_policy`：决定 exact / non-exact comparison；
- `objective`：成本模型定义后才填正式数值。

---

# 8. 当前 `phase1_benchmark_001` 人工 Reference

当前人工 Reference 使用：

```text
F2 +50 min
F10 +20 min
F11 +10 min
```

并通过 Aircraft Reassignment：

```text
AC1:
F1 → F2 → F10

AC4:
F3 → F11 → F12
```

保持 F3 原计划不延误。

同时：

```text
P4:
F2→F3
→
F8
```

作为 Passenger Reaccommodation。

Reference Metrics：

```text
operated_flights = 12
cancelled_flights = 0
delayed_flights = 3
aircraft_reassignments = 2
crew_reassignments = 0
passenger_reaccommodated_count = 15
total_flight_departure_delay_minutes = 80
passenger_delay_minutes_weighted = 1800
unserved_passengers = 0
```

---

# 9. 当前 Reference 不是 Proven Optimal

当前 Expected 明确应标记：

```text
reference_type = manual_reference
solution_status = feasible
```

而不是：

```text
solver_optimal
```

因为以下内容尚未正式实现和校准：

- SRM Objective；
- ARM Cost；
- CRM Cost；
- PRM Cost；
- Cancellation Penalty；
- Aircraft Reassignment Penalty；
- Crew Reassignment Penalty；
- Passenger Reaccommodation Cost；
- Destination Change / Ferry Cost。

所以：

> 当前 80 分钟方案是一套人工合理恢复结果，不是已经由 AIR 综合目标证明的全局最优解。

---

# 10. Paper-to-Schema Distinction

论文定义的是优化集合、网络、目标与约束，而不是完整的工程 JSON Interchange Format。

因此本项目新增的字段和 JSON 结构属于：

```text
Implementation Interface
```

而不是声称来自论文原始数据格式。

所有会改变可行域或目标的实现补充均应登记于：

```text
assumptions.md
```

---

# 11. SRM / ARM / CRM / PRM 数据映射

当前数据资产已经为四部分保留接口：

## SRM

- Flight；
- Flight Options；
- Strategic / Market flags；
- Airport-time capacities；
- Disruptions；
- Cancellation / Delay candidates。

## ARM

- Individual Tail；
- Equipment；
- Start / Required End Station；
- Maintenance；
- Aircraft Strings；
- Reassignment candidates。

## CRM

- Individual Crew；
- Rating；
- Start / Required End Station；
- Duties；
- Crew Pairings；
- Reassignment / future Deadhead interfaces。

## PRM

- Passenger Commodities；
- Original Itineraries；
- Alternative Itineraries；
- Reaccommodation；
- Unserved option。

---

# 12. 当前仍未实现

截至当前阶段，以下仍未完成：

```text
Python/Pydantic Recovery Columns Schema
Python/Pydantic Expected Schema
Column Semantic Validator
Oracle Semantic Validator
Incidence Matrix Builder

Fixed-column SRM
Fixed-column ARM
Fixed-column CRM
Fixed-column PRM

Full Integrated MIP Oracle

Scope Limiting
Automatic Flight String Generator
Automatic Crew Pairing Generator
Automatic Passenger Itinerary Generator

Benders
Column Generation
Benders + Column Generation
Integrality / Branching
```

---

# 13. Phase 1 当前状态

Phase 1 已完成的是：

```text
Benchmark design
Manual columns
JSON exchange schemas
Manual feasible reference
Oracle comparison design
Documentation
```

Phase 1 尚未完成的是：

```text
programmatic semantic validation
automated benchmark regression
negative tests
fixed-column mathematical verification
```

因此仓库状态应表述为：

> **Phase 1 data/reference assets established; Phase 1 engineering validation is still in progress.**

不要在 README 中提前写：

```text
Phase 1 completed
```

---

# 14. 下一工程步骤

在开始 SRM Solver 前，应先建立：

```text
backend/schemas/columns.py
backend/schemas/expected.py

backend/services/column_validator.py
backend/services/oracle_validator.py
```

以及：

```text
benchmark001 regression
negative semantic tests
```

之后进入：

```text
Incidence Matrix Builder
→
Fixed-column SRM / ARM / CRM / PRM
```

本轮文档更新不实现上述代码。

---

# 15. Reproduction Integrity Rule

任何阶段都不允许用：

```text
solver_status = OPTIMAL
```

单独证明实现正确。

必须回答：

```text
数据是否正确？
列是否可行？
约束是否正确？
是否与人工/整体 Oracle 一致？
是否存在等价解？
Objective 是否使用同一成本定义？
```

只有上述问题可以清楚回答，才能把复杂算法作为可信论文复现。
