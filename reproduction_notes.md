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

当前 Phase 2 test cost 状态为：

- SRM-owned delay / cancellation / route change 已实现；
- ARM-owned aircraft reassignment / ferry 已实现；
- CRM-owned crew reassignment / deadhead 已实现；
- PRM-owned passenger delay / unserved passenger 已进入 Fixed-Column PRM，并按 passenger-minutes / passenger count 独立复算。

上述成本仍是 `abstract_cost_units` / implementation test profile，不代表真实航空公司生产成本，也未完成真实业务校准。

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

Review fix 已冻结 Gate boundary：internal boundary 使用右侧 `[start,end)` interval；recovery-end terminal checkpoint 使用唯一以 recovery end 结尾的 interval。现有不完整 benchmark 只有在同一机场 gate capacities 全部一致时才允许 provisional fallback。

---

# 15. Phase 2.3：Fixed-Column ARM

Phase 2.3 接收外生 `AircraftRecoveryRequest.required_operated_option_ids`，不重新决定 SRM schedule，并使用现有人工 `aircraft_strings` 建立：

- `ARM-C01-AIRCRAFT-STRING-SELECTION`：每架 aircraft 恰选一条显式 String，对应论文 (3.10)；
- `ARM-C02-FLIGHT-OPTION-COVERAGE`：required revenue option 恰覆盖一次，non-required revenue option 覆盖为零，是论文 (3.9) 的 fixed-option 映射；
- `ARM-C03-TERMINAL-STATION`：selected String 满足 required terminal；
- `ARM-C04-MAINTENANCE`：maintenance-required aircraft 选择 validated satisfied String，对应论文 (3.11)；
- `ARM-C05-STRING-FEASIBILITY`：复用 pre-model semantic validation；
- 二元 String variables 对应论文 (3.12)，ARM-owned assignment objective 对应 (3.8)。

ARM Objective 只收取 aircraft reassignment 与 Ferry。Ferry 可作为 String leg，但不进入 revenue coverage；所有结果在求解后独立复算 coverage、schedule leakage、terminal、maintenance、reassignment、Ferry 和 Objective。

Benchmark 顺序测试得到：SRM optimum 70 的 schedule 在现有 fixed Aircraft Strings 下 `ARM = INFEASIBLE`。结构分析定位 AC4 没有不泄漏 schedule 的候选 String，`F3_ORIG`、`F11_ORIG`、`F12_ORIG` 没有 eligible exact cover。这是 fixed-column coverage 不足，未通过修改 SRM 或 Columns 掩盖。Phase 1 Manual schedule 则得到 ARM `OPTIMAL`、objective 0（当前 reassignment coefficient 为 0）、两次 reassignment、无 Ferry，全部独立审计通过。

---

# 16. Phase 2.4：Fixed-Column CRM

Phase 2.4 接收外生 `CrewRecoveryRequest.required_operated_option_ids`，复用 SRM 的 canonical operated-option handoff，不重新决定 schedule，并使用现有人工 `crew_pairings` 建立：

- 每个 crew 恰选一条显式 Pairing；
- required revenue option 由 OPERATE segment 恰覆盖一次；
- non-required OPERATE / DEADHEAD schedule leakage 禁止；
- fixed-column legality 与 terminal ownership 审计；
- CRM-owned crew reassignment / deadhead objective；
- 求解后独立复算 pairing selection、coverage、terminal、cost 与全部约束。

当前 crew reassignment 是“按 reassigned operating flight leg 计数”的 Phase 2 implementation mapping；未来真实业务成本标定时必须重新确认实际计费粒度是 crew / duty / pairing / flight-leg 中哪一种。Phase 2.4 不改变该既有成本逻辑。

---

# 17. Phase 2.5：Fixed-Column PRM

Phase 2.5 接收外生 `PassengerRecoveryRequest` 与独立 `PassengerCapacityProfile`，复用 canonical SRM operated-option handoff，不重新决定 schedule、aircraft 或 crew，并使用现有人工 `passenger_itineraries` 建立：

- `PRM-C01`：每个 passenger group 恰选一条 transported / explicit unserved itinerary；
- `PRM-C02`：引用 non-selected Flight Option 的 itinerary 固定为零；
- `PRM-C03`：按 `PassengerCommodity.count` 消耗每个 FLIGHT segment 的外生 residual seat capacity；
- `PRM-C04`：复用 fixed-column validator 的 OD、时间连续、arrival/delay 与 UNSERVED shape；
- `(3.16)` PRM-owned arrival delay / unserved objective 与独立复算；
- reaccommodation、unserved、weighted passenger delay、seat load/capacity/slack diagnostics。

论文 `(3.16)-(3.18)` 的变量是非负整数旅客流；当前 fixed-column 映射使用 binary、不可拆分 passenger group，并以 explicit UNSERVED itinerary 映射论文 `s_i`。Capacity profile 表示可供模型内 passenger groups 使用的 test residual inventory，不使用 `Flight.min_seats`，也不代表真实 aircraft capacity。

`toy_case_003` 提供容量瓶颈与 alternative itinerary 的可手算 Oracle。Phase 1 Manual schedule 下 PRM 复现 1800 pax-min、15 名 reaccommodated、0 unserved；SRM 70-cost schedule 下 PRM 可行，但因现有 fixed itinerary coverage 使 P6 的 12 人选择 explicit unserved。

---

# 18. 当前仍未实现

截至当前阶段，以下仍未完成：

```text
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

# 19. 当前工程状态

Phase 1、Phase 2.0、Phase 2.1、Phase 2.2、Phase 2.3、Phase 2.4 与 Phase 2.5 已完成：

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
Fixed-column Aircraft Recovery Model
External required-operated-option contract
Aircraft String / schedule no-leakage constraints
Terminal / fixed-column Maintenance audit
Aircraft reassignment / Ferry objective audit
Fixed-column Crew Recovery Model
External required-operated-option contract reuse
OPERATE / DEADHEAD separation and schedule no-leakage constraints
Crew terminal / fixed-column legality audit
Crew reassignment / deadhead objective audit
Fixed-column Passenger Recovery Model
External versioned residual seat-capacity contract
Passenger group / schedule / capacity constraints
Passenger delay / unserved objective and independent audit
toy_case_003 passenger-capacity Oracle
```

当前已建立 SRM、ARM、CRM 与 PRM 四个相互独立、fixed-column、可审计的业务恢复子模型。SRM→ARM benchmark 如实暴露现有 fixed Aircraft Strings 对 70-cost schedule 的 coverage 缺口；Phase 1 的 80 分钟 Manual Reference 仍是完整恢复人工参考，没有被改写。SRM market-seat proxy 继续作为 schedule-level provisional constraint；PRM seat capacity 是首个显式 passenger seat-load constraint。

---

# 20. 下一工程步骤

下一步进入：

```text
Phase 3 Full Integrated Fixed-Column Oracle
```

Phase 3 才将 Schedule + Aircraft + Crew + Passenger 放入同一 MIP，并统一四个 canonical cost owner。进入 Phase 3 前应总审查 cross-model coupling、seat-capacity source、market-seat proxy、tie-breaking 与 fixed-column coverage gaps。

---

# 21. Reproduction Integrity Rule

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

---

# 22. Costs + Constraints Workbench

当前前端在既有 Data 与 Visualization 之外增加 Costs 和 Constraints 两个一级视图。

Costs 的 canonical 单一真源仍为：

```text
data/costs/phase2_test_costs_v1.json
```

浏览器 cost override 只修改实验状态中的 coefficient value。后端拒绝未知 key、负数、NaN 与 Infinity；owner、unit、canonical source 和 source reference 不可通过 override 修改，canonical 文件也不会被自动写回。

Constraints 由后端统一 registry 提供 20 个实际代码约束 ID，包含 model、kind、provenance、implementation status、公式摘要、输入依赖和 assumption refs。Gate Inventory 与 Market-seat 明确标记为 proxy；PRM 容量明确标记为 `TEST / RESIDUAL CAPACITY` 和 `NOT AIRCRAFT PHYSICAL CAPACITY`。

Constraint precheck 仅检查当前输入和 fixed columns 的确定性结构条件：

```text
PRECHECK != MIP FEASIBILITY
```

它不运行 SRM / ARM / CRM / PRM solver，不产生 Feasible 或 Optimal 结论。该工作台是人工审计与实验配置工具，不代表 Phase 3 Integrated Oracle 已完成。

---

# 23. Phase 2 Final Review 与 Phase 3 v1 冻结

Phase 2 最终审查继续保持四个独立 fixed-column 子模型，不将其伪装为 Integrated Oracle。同一 Phase 1 Manual Reference schedule 已分别作为 ARM、CRM、PRM 的独立 Gurobi smoke；三个模型各自 feasible 且 independent audit 通过，但没有把三个 objective 相加称为 integrated objective。

SRM 独立最优在当前有限 Aircraft Strings 下可能使 ARM infeasible。这是被保留的正确边界，不通过修改 SRM cost、SRM solution 或偷偷补列掩盖；Phase 3 需要联合优化 Schedule 与资源恢复来处理该耦合。

Phase 3 v1 冻结为：

```text
Full Integrated Fixed-Column Oracle
```

它继续复用 `phase2_test_costs_v1`、当前人工列、不可拆分 PassengerCommodity group、test/residual passenger capacity 和 provisional SRM Market-seat Proxy。Integrated Objective 只按 canonical owner 汇总 SRM + ARM + CRM + PRM，不增加模型级权重、隐藏 epsilon 或 tie-breaking penalty，允许等价最优解。

Phase 3 v1 不加入南航特定业务规则，不动态生成 Columns，不进入 Benders / Column Generation，也不宣称使用生产级真实参数。完整冻结说明见 `assumptions.md` A-056。
