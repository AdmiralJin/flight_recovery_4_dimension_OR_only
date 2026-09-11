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

# 12. Phase 2.0：Indices / Incidence

Phase 2.0 已完成：

- deterministic ordered indices；
- base flight / aircraft / crew / passenger candidate-choice incidence；
- aircraft / operating crew / deadhead / passenger operational incidence；
- maintenance incidence；
- arrival / departure capacity incidence；
- Ferry / Cancel / Deadhead 分离；
- `[start,end)` 容量边界；
- benchmark001 regression。

Gate incidence 仍明确暂缓，等待 Gate Occupancy 语义冻结。

---

# 13. Phase 2.1：Solver / Cost / Result Contract

Phase 2.1 已建立：

- Gurobi 13.0.3 Primary Adapter；
- solver-independent variable/constraint/objective/solve/read contract；
- normalized solver status 与 capability declaration；
- LP dual / reduced-cost 访问；
- MIP objective / bound / gap / runtime 访问；
- 独立 `ModelSolveResult`；
- 版本化 `FixedColumnCostConfig` 与 `phase2_test_costs_v1`；
- 每项成本的单位、来源和 canonical model owner。

论文 Table 2 中可直接映射的测试值与工程假设严格分开。该成本 profile 是 abstract test units，不是当前航空公司业务成本，也没有为匹配 Phase 1 Manual Reference 调参。

---

# 14. Phase 2.2：Fixed-Column SRM

Phase 2.2 已建立固定候选列的 Schedule Recovery Model：

- `SRM-C01-FLIGHT-COVERAGE`：每个 revenue flight 恰选一个 operate/cancel option；
- `SRM-C02-STRATEGIC-FLIGHT`：strategic flight 禁止取消；
- `SRM-C03-ARRIVAL-CAPACITY` / `SRM-C04-DEPARTURE-CAPACITY`：复用 Phase 2.0 的 `[start,end)` incidence；
- `SRM-C05-GATE-INVENTORY`：明确标记为 `PROVISIONAL_AGGREGATE_GATE_INVENTORY`；
- `SRM-C06-MARKET-SEAT`：明确标记为 `MARKET_SEAT_PROXY`，只保存市场服务，不证明真实座位容量。

模型只为 revenue `operate` / `cancel` options 建变量，Ferry 留给 ARM。求解后不依赖 Gurobi status 直接宣称正确，而是独立复算每个约束实例、capacity/gate slack 与 SRM-owned objective breakdown。

在 `phase1_benchmark_001` 上，Phase 2 test cost profile 的 SRM optimum 为 70：`F2_D50` 消除 B 机场 departure-capacity 冲突，`F10_D20` 保持 aggregate ground inventory 非负。该结果不包含 Aircraft/Crew/Passenger 联动，因此不能替代 80 分钟的完整恢复 Manual Reference。

---

# 15. 当前仍未实现

截至当前阶段，以下仍未完成：

```text
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

# 16. 当前工程状态

Phase 1、Phase 2.0、Phase 2.1 与 Phase 2.2 已完成：

```text
Benchmark design
Manual columns
JSON exchange schemas
Manual feasible reference
Oracle comparison design
Documentation
Python/Pydantic Columns / Expected Schema
Column / Oracle Semantic Validation
Reference Metrics recomputation
Benchmark regression and negative tests
Deterministic indices and incidence builder
Solver / Cost / ModelSolveResult contracts
Analytical LP/MIP solver smoke tests
Fixed-column Schedule Recovery Model
SRM-C01 至 SRM-C06 constraints
Provisional Aggregate Gate Inventory
Market Service Preservation Proxy
Independent SRM constraint/objective diagnostics
```

当前已建立第一个 AIR 业务优化子模型 SRM。`phase1_benchmark_001` 在 Phase 2 test cost profile 下的 SRM optimum 为 70，选择 `F2_D50` 与 `F10_D20`；Phase 1 的 80 分钟 Manual Reference 仍是完整恢复人工参考，不是 SRM optimum，也没有被改写。

---

# 17. 下一工程步骤

下一步进入：

```text
Phase 2.3 Fixed-column ARM
```

Phase 2.3 应使用现有 Aircraft Strings 建立 tail assignment、Ferry 和 Maintenance 可行性，同时复用 Solver/Cost/Result contracts，禁止把 ARM-owned 成本或决策回填到 SRM。

---

# 18. Reproduction Integrity Rule

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
