# Phase 4 Closeout + Phase 5 Flight String Generator Plan

> 用途：供 Codex 完成 Phase 4 最后收尾，并进入 Phase 5 Flight String Generator。  
> 原则：Phase 4 只做小修，不再改 Scope Engine 主逻辑；Phase 5 第一版只生成合法 Aircraft Strings，不做 Pricing、Column Generation 或 Benders。

---

# 1. Phase 4 极小收尾

Phase 4 已通过，不再修改 Scope Limiting 核心算法。

仅完成以下两项。

## 1.1 加严 Original Candidate Resolver

当前 original resolver 需要进一步防止未来自动生成候选后误判“原计划列”。

### Aircraft String

原计划 Aircraft String 除了 revenue OPERATE sequence 与 `Aircraft.original_rotation` 一致外，还必须：

```text
不包含额外 FERRY / positioning leg
```

### Crew Pairing

原计划 Crew Pairing 除了 OPERATE sequence 与 `Crew.original_pairing` 一致外，还必须：

```text
不包含额外 DEADHEAD / recovery-only segment
```

### Passenger Itinerary

原计划 Passenger Itinerary 除了 flight sequence 与 `PassengerCommodity.original_itinerary` 一致外，还必须：

```text
不包含额外 recovery-only segment
```

如匹配 0 个或大于 1 个，必须显式报错，不得依赖 `*_ORIGINAL` 字符串命名猜测。

补充相应 unit tests。

## 1.2 清理少量旧文档

更新 README / assumptions 中已经过时的表述，例如：

```text
Integrated Objective 尚未完成
Solver 尚未存在
```

改为当前事实：

```text
Phase 3 Integrated Oracle 已完成
后端 Solver 已存在
前端 Solve API / Recovered UI 尚未接入
```

完成后 Phase 4 正式关闭，不再继续扩展 Scope。

---

# 2. Phase 5 目标

项目总计划对 Phase 5 的定义是：

> 第一版只生成合法 Aircraft Strings，不做 Pricing。

至少处理：

```text
Station continuity
Flight timing
Turn Time
Max Delay
Airport restrictions
Recovery Horizon
Maintenance
Terminal Station
```

核心问题：

> 给定 Scenario、Flight Options、Aircraft 和 Recovery Scope，能否自动生成一套合法、完整、可审计的 Aircraft Strings，替代 Phase 1 人工编写的 Aircraft Strings？

本阶段不生成 Crew Pairings、Passenger Itineraries，不做 Pricing、Reduced Cost 或 Benders。

---

# 3. 输入与输出

建议新增：

```text
backend/core/flight_network.py
backend/core/string_generator.py
```

输入：

```text
Scenario
Flight Options
RecoveryScope
FlightStringGenerationConfig
```

输出：

```text
list[AircraftString]
```

输出必须继续符合现有 `backend.schemas.columns.AircraftString`，不得新建不兼容 Schema。

---

# 4. Phase 5 v1 暂不自动生成 Flight Options

Flight Options 继续来自现有 Recovery Columns：

```text
Scenario
→ existing flight_options
→ Flight String Generator
→ generated aircraft_strings
```

原因：

1. 单独验证 String Generation；
2. 不同时改变 Flight Option 和 Aircraft String 两个候选宇宙；
3. 可直接与 Phase 3/4 Oracle 比较；
4. 避免提前进入更复杂的候选生成阶段。

因此 Phase 5 不应顺手实现 delay / destination-change / ferry Flight Option generator。

---

# 5. 使用 Phase 4 Scope

Generator 应接收 `RecoveryScope`。

### Scoped Aircraft

自动生成 candidate Aircraft Strings。

### Out-of-scope Aircraft

仅保留 original Aircraft String。

同时支持：

```text
scope=None
```

用于小案例 full-enumeration oracle。

---

# 6. Flight Network

`flight_network.py` 建立确定性网络。

节点可表示：

```text
Aircraft start state
Flight Option
Aircraft terminal state
```

边表示两个 Flight Options 可以由同一架飞机连续执行。

至少要求：

```text
previous.destination == next.origin
```

以及：

```text
previous.arr_time + minimum_turn <= next.dep_time
```

Flight Network 只处理 aircraft-local legality。

禁止把 Airport capacity、Gate capacity、Passenger seat capacity、Crew legality 塞进 String Generator；这些继续由 Integrated Model 处理。

---

# 7. Turn Time 必须显式配置

当前项目仍保留 Phase 1 的最小时间连续规则，Phase 5 首次正式引入 Aircraft Turn Time，因此不得写 Magic Number。

建议新增版本化配置，例如：

```text
data/config/phase5_test_string_generation_v1.json
```

最小字段：

```text
profile_id
default_min_turn_minutes
equipment_overrides
source
notes
```

逻辑：

```text
min_turn(aircraft)
=
equipment override
or
default value
```

测试 profile 只用于工程验证，不声明为真实航空公司参数。

在 `assumptions.md` 中登记为 Implementation Assumption。

---

# 8. Flight Option Eligibility

Aircraft 能执行 Flight Option 至少要求：

```text
operation_type == OPERATE
或
operation_type == FERRY
```

Revenue Flight 继续遵守现有 aircraft / equipment compatibility 语义。

同时检查：

```text
dep_time < arr_time
within Recovery Horizon
departure_delay <= Flight.max_delay
airport / curfew local restriction
```

CANCEL 永远不能进入 Aircraft String。

注意：Airport capacity reduction 属于全局约束，不应被当成 aircraft-local eligibility 去删除合法 Flight Option。

---

# 9. Station / Timing / Terminal

相邻 legs 必须满足：

```text
leg_i.destination == leg_{i+1}.origin
```

以及：

```text
leg_i.arr_time + min_turn <= leg_{i+1}.dep_time
```

第一条 leg：

```text
origin == Aircraft.initial_station_at_t
```

完整 String 最终：

```text
end_station == Aircraft.required_station_at_T_end
```

Recovery Horizon 外执行不得进入 String。

---

# 10. Maintenance

当前 Schema 只有：

```text
maintenance_required
maintenance_stations
maintenance_satisfied
```

没有 maintenance duration / due time / maintenance task。

因此 Phase 5 v1 不得虚构完整维修排程。

如果 `maintenance_required == false`，生成列可标记 `maintenance_satisfied = true`。

如果 `maintenance_required == true`，String 必须满足当前 Scenario 和既有 validator 能证明的 maintenance-station 条件，只有 `maintenance_satisfied = true` 的 String 才能输出。

具体判定必须与现有 semantic validator / assumptions 一致。

---

# 11. String Enumeration

Phase 5 v1 不做 Pricing。

建议采用：

```text
Flight Network + DFS / DAG path enumeration
```

从 Aircraft 初始位置出发，在合法连接上扩展，直到 Recovery Horizon / terminal condition。

要求：

```text
deterministic
stable ordering
无重复 String
```

可基于：

```text
aircraft_id + ordered leg_option_ids
```

建立 canonical key 去重。

---

# 12. Original / Idle String

每架 Aircraft 必须至少存在一个合法 candidate。

对 scoped aircraft，原计划 String 若合法应始终保留。

若允许原地等待，应显式生成 idle / null String，仅在以下条件满足时允许：

```text
initial station == required terminal station
maintenance requirement 允许
```

不能通过“零条 selected String”表达 idle，因为 ARM / Integrated Oracle 已冻结为 one explicit String per Aircraft。

---

# 13. Ferry

Phase 5 v1 不自动创造新的 Ferry Flight Options。

但如果输入 `flight_options` 已存在合法 `operation_type = FERRY`，Generator 必须能够将其作为 leg 使用。

Ferry 不参与 revenue Flight Coverage，成本继续由现有 ARM cost logic 计算。

---

# 14. 独立 String Legality Validator

建议将单条 String 合法性做成独立 pure function，例如：

```text
validate_generated_aircraft_string(...)
```

至少复算：

```text
aircraft ownership
known Flight Options
CANCEL exclusion
equipment compatibility
start station
station continuity
timing / turn time
max delay
recovery horizon
airport local restrictions
maintenance
terminal station
```

Generator 输出后必须再次通过 validator。

不能认为“由 Generator 产生”就天然合法。

---

# 15. Smart Generator vs Brute-force Oracle

必须新增一个真正的小规模 Oracle，建议：

```text
toy_case_007_string_generator
```

规模足够小，可以暴力枚举所有 Flight Option 子序列，再逐条通过独立 legality predicate 判断，得到：

```text
brute-force legal string set
```

Smart Generator 使用：

```text
network + DFS pruning
```

Oracle 使用：

```text
exhaustive sequence enumeration
```

两者可以共享单条 String legality predicate，但不得共享 path-generation 算法。

优先验收：

```text
generated_string_set == brute_force_legal_string_set
```

---

# 16. 与现有 Manual Aircraft Strings 比较

在 `phase1_benchmark_001` 上运行 Generator。

至少检查 Manual Reference 所需关键 Aircraft Strings 在 generated set 中存在语义等价列。

不要比较 ID，应比较：

```text
aircraft_id
ordered leg_option_ids
start_station
end_station
maintenance_satisfied
```

Generator 生成更多合法 Strings 是允许的。

---

# 17. Generated Strings 重新进入 Integrated Oracle

构造：

```text
原 flight_options
+
generated aircraft_strings
+
原 crew_pairings
+
原 passenger_itineraries
```

重新运行 Phase 3 Integrated Oracle，必要时也运行 Phase 4 Scope-limited Oracle。

比较：

```text
OBJ_generated_strings
vs
OBJ_manual_strings
```

解释原则：

### 相等

自动 Strings 至少保留了当前 fixed-column optimum。

### 更低

不直接判错。检查新增 String 是否完全合法；若审计通过，说明人工 fixed columns 原本漏列。

### 更高或 infeasible

优先视为 Generator 漏掉关键合法 String，Phase 5 不得 PASS。

---

# 18. 推荐测试

建议新增：

```text
tests/unit/test_flight_network.py
tests/unit/test_string_generator.py
tests/regression/test_phase5_string_generator_oracle.py
tests/regression/test_phase5_benchmark_001.py
```

至少覆盖：

```text
station mismatch rejected
timing overlap rejected
turn time violation rejected
max delay violation rejected
recovery horizon rejected
cancel excluded
ferry supported
terminal mismatch rejected
maintenance failure rejected
original string retained
idle/null string legality
duplicate path removed
scope limits aircraft generation
deterministic output
```

以及：

```text
smart generator == brute-force oracle
```

---

# 19. Phase 5 Metrics

报告至少输出：

```text
Aircraft count
Scoped Aircraft count
Flight Option count
Network node count
Network edge count
Generated String count by Aircraft
Rejected candidate count by reason
Generation runtime
```

Benchmark 还要记录：

```text
manual Aircraft String count
generated Aircraft String count
manual-reference key strings recovered?
Integrated objective with generated Strings
```

---

# 20. Assumptions

新增前先读取最新 `assumptions.md` 编号。

至少明确：

```text
Aircraft Turn Time test profile
Airport restriction eligibility boundary
Maintenance simplification
Idle/null String rule
Phase 5 uses existing Flight Options
Phase 5 does not perform Pricing
```

继续区分：

```text
Paper-defined
Implementation Assumption
Airline-specific Extension
```

---

# 21. Phase 5 明确不做

不得实现：

```text
Reduced Cost
Dual extraction
Pricing
Column Generation
Benders
Crew Pairing Generator
Passenger Itinerary Generator
真实 maintenance scheduling
真实 tail compatibility rules
真实航司 Turn Time 标定
动态 Flight Option generation
```

Phase 5 是合法列生成器，不是 Pricing Generator。

---

# 22. 文档与报告

完成后更新：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

明确：

```text
Phase 5 = explicit/full candidate String generation
not Column Generation
```

新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase5_flight_string_generator_report.md
```

报告至少包括：

```text
1. Phase 4 Closeout
2. Modified Files
3. Generator Input / Output
4. Flight Network
5. Legality Rules
6. Turn Time Contract
7. Maintenance / Terminal Semantics
8. Smart Generator
9. Brute-force Oracle
10. Toy Oracle Comparison
11. Benchmark Generated Strings
12. Manual Key-string Coverage
13. Integrated Oracle Result
14. Tests
15. New Assumptions
16. Known Limitations
17. Acceptance Checklist
18. Final Decision
```

---

# 23. Acceptance Criteria

Phase 5 只有以下全部满足才 PASS：

- [x] Phase 4 original resolver 已加严
- [x] Phase 4 旧文档已清理
- [x] Flight Network 已实现
- [x] Aircraft String Generator 已实现
- [x] 使用现有 Flight Options，不静默扩大 Flight Option universe
- [x] Station continuity 正确
- [x] Flight timing 正确
- [x] Turn Time 使用显式配置，不使用 Magic Number
- [x] Max Delay 正确
- [x] Recovery Horizon 正确
- [x] Airport local restrictions 正确
- [x] Maintenance 语义与当前数据能力一致
- [x] Terminal Station 正确
- [x] CANCEL 不进入 String
- [x] Existing FERRY Option 可进入 String
- [x] Original / idle semantics 正确
- [x] Scope 能限制需要生成的 Aircraft
- [x] Generator deterministic 且无重复
- [x] Generated String 通过独立 legality validator
- [x] Smart Generator 与 brute-force oracle 对齐
- [x] Benchmark Manual Reference 所需关键 Strings 未遗漏
- [x] Generated Strings 可重新运行 Integrated Oracle
- [x] objective 未改善，保持 `18080`，无需新增合法性解释
- [x] objective 未变差且模型未 infeasible
- [x] full pytest 0 failed
- [x] full pytest 0 skipped
- [x] Phase 3 / Phase 4 regression 无回归
- [x] 未进入 Pricing / CG / Benders

## 23.1 实施结果（2026-09-14）

```text
toy_case_007_string_generator:
  generated strings = 6
  smart legal set = brute-force legal set

phase1_benchmark_001:
  network nodes = 80
  network edges = 188
  generated strings = 77
  by aircraft = AC1 10, AC2 27, AC3 13, AC4 27
  manual semantic key coverage = 11 / 11
  Integrated Oracle status = OPTIMAL
  Integrated objective = 18080

full pytest:
  309 passed, 0 failed, 0 skipped
```

**Final Decision：Phase 5 PASS。**

Phase 5 PASS 后进入：

```text
Phase 6 Crew Pairing Generator
```
