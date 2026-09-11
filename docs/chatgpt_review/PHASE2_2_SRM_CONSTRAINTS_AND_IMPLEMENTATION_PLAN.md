# Phase 2.2 前置约束补全与 Fixed-Column SRM 实施任务

> 用途：供 Codex 在当前 `main` 基础上继续开发。  
> 范围：**约束语义、Assumptions、后端模型、测试、文档**。  
> 明确不包含：HTML / Frontend 修改、ARM/CRM/PRM、Integrated Oracle、Benders、Column Generation。

---

## 1. 当前基线

当前已完成：

- Phase 0：Scenario Schema / Validator / HTML Data Editor；
- Phase 0.5：确定性可视化；
- Phase 1：人工 Recovery Columns、Manual Reference、Semantic Validation；
- Phase 2.0：Indices、Incidence Builder、Arrival/Departure Capacity incidence；
- Phase 2.1：Solver Adapter、Gurobi Adapter、Cost Contract、`ModelSolveResult`。

当前下一正式阶段：

```text
Phase 2.2 = Fixed-Column SRM
```

SRM 计划对应：

```text
(3.1) objective
(3.2) flight coverage
(3.3) strategic flights
(3.4) arrival capacity
(3.5) departure capacity
(3.6) gate constraint
(3.7) market-seat constraint
```

当前已知 blocker：

- Gate incidence / Gate Inventory 尚未正式程序化；
- Market-seat 的“seat contribution”缺少真实 aircraft seat capacity；
- 当前 `min_seats` 不能解释为完整 Passenger Seat Inventory；
- Phase 2.1 已明确这些内容不属于 2.1。

本任务的原则不是等待全部真实业务参数，而是：

> **先建立显式、可测试、可替换的 Generated / Provisional Constraint Contract；严禁把生成规则伪装成论文已明确规则。**

---

# 2. 强制原则

## 2.1 三类来源必须分开

所有约束及其补充语义必须明确标记为：

```text
paper_defined
implementation_assumption
airline_specific_extension
```

不得混写。

## 2.2 先登记，再实现

任何新增约束语义，如果论文或现有数据未完整定义：

1. 先写入根目录 `assumptions.md`；
2. 再写代码；
3. 再写测试；
4. Codex Report 中单独列出。

当前最新正式基线已经登记到 `A-026`。新增假设从下一个可用编号继续；执行前必须读取当前 `assumptions.md`，避免编号冲突。

## 2.3 不修改历史 Oracle 的含义

`phase1_benchmark_001_expected.json` 继续保持：

```text
manual_reference
feasible
```

不得因为 Phase 2.2 求出新结果，就把历史 Manual Reference 静默改成 `optimal`。

## 2.4 不把 SRM 偷偷扩展成 ARM/CRM/PRM

Phase 2.2 只解决 Schedule Recovery。

不得在本阶段加入：

- Aircraft tail assignment；
- Maintenance feasibility；
- Crew legality；
- Passenger reaccommodation；
- Passenger seat consumption；
- Ferry assignment；
- Benders；
- 动态列生成。

若某个 SRM 约束只能通过这些后续模型精确定义，应使用**明确的 provisional proxy**，并记录局限。

---

# 3. Phase 2.2 约束合同

建议在代码和测试中使用稳定约束 ID：

```text
SRM-C01-FLIGHT-COVERAGE
SRM-C02-STRATEGIC-FLIGHT
SRM-C03-ARRIVAL-CAPACITY
SRM-C04-DEPARTURE-CAPACITY
SRM-C05-GATE-INVENTORY
SRM-C06-MARKET-SEAT
```

这些 ID 用于：

- 测试命名；
- diagnostics；
- Codex Report；
- 后续 HTML Constraint 面板；
- 后续 Integrated Oracle 对齐。

---

## 3.1 SRM-C01 Flight Coverage

### 来源

```text
paper_defined
```

### 当前数据

使用：

```text
Flight.flight_id
FlightOption.base_flight_id
FlightOption.operation_type
RecoveryIncidence.base_flight_to_options
```

### 约束

对每个原计划 revenue flight `f`：

```text
sum(x_o for o in options(f)) = 1
```

其中：

- `operate` option 是实际执行方案；
- `cancel` option 是取消方案；
- `ferry` 没有 `base_flight_id`，不得进入该约束。

### 防御条件

建模前必须检查：

- 每个 base flight 至少有一个合法 option；
- option 不得同时属于多个 base flight；
- ferry 不得进入 base-flight coverage；
- 不得通过修改原 `flight_id` 表示恢复副本。

### 必测

1. 一个 flight 有 original + delayed + cancel → 恰选一个；
2. 删除该 flight 全部 options → 明确失败；
3. 同时选择两个 option 应被模型约束禁止；
4. ferry 不影响任何 base-flight coverage。

---

## 3.2 SRM-C02 Strategic Flight

### 来源

```text
paper_defined
+
implementation_mapping_assumption
```

论文有 strategic-flight 约束；本项目需明确 `strategic_flag` 到当前 option schema 的映射。

### Generated / Provisional 语义

第一版定义：

```text
Flight.strategic_flag == true
→ 该 flight 必须选择 operation_type == operate 的 option
→ cancel option 不允许被选择
```

等价：

```text
sum(x_o for o in operated_options(f)) = 1
```

对 strategic flight：

```text
x_cancel = 0
```

### 说明

不得把：

```text
strategic_flag
```

解释成：

- 更高成本；
- VIP；
- 国际航班；
- 南航重要航班规则；

除非以后作为 `airline_specific_extension` 单独加入。

### 必测

1. Strategic flight 同时有 operate/cancel → cancel 永远不能入解；
2. Strategic flight 只剩 cancel → `INFEASIBLE`；
3. Non-strategic flight 可以按成本选择 cancel；
4. Strategic flight 的 delayed operate option 仍属于合法执行。

---

## 3.3 SRM-C03 Arrival Capacity

### 来源

```text
paper_defined
```

### 当前可复用资产

Phase 2.0 已有：

```text
RecoveryIncidence.arrival_capacity_to_options
```

并已冻结 AirportInterval：

```text
[start_time, end_time)
```

边界语义。

### 约束

对每个 airport interval `k`：

```text
sum(a_ko * x_o) <= arr_capacity_k
```

只计算实际有 arrival event 的：

```text
operate
```

Phase 2.2 不主动引入 ferry；若 Columns 中存在 ferry，不得因为 SRM 而把 ARM-owned ferry 纳入 schedule objective/decision。

### 必测

1. 容量足够 → 原计划可行；
2. 降低某 interval arrival capacity → solution 必须响应；
3. `event_time == end_time` 不属于当前桶；
4. cancel 不计入 arrival capacity。

---

## 3.4 SRM-C04 Departure Capacity

与 Arrival Capacity 同构。

### 当前可复用资产

```text
RecoveryIncidence.departure_capacity_to_options
```

### 约束

```text
sum(d_ko * x_o) <= dep_capacity_k
```

### Benchmark 强制行为测试

`phase1_benchmark_001` 已包含 B airport 的 departure capacity disruption。

至少验证：

- 原始冲突确实存在；
- SRM 必须通过合法 retiming / cancellation 等 schedule choice 消除冲突；
- 结果不是仅检查 `solver_status == OPTIMAL`；
- 必须重新计算 interval load 并验证不超过容量。

---

# 4. Generated Constraint：Gate Inventory

## 4.1 问题

当前已有：

```text
AirportInterval.gate_capacity
Aircraft.initial_station_at_t
FlightOption.origin
FlightOption.destination
FlightOption.dep_time
FlightOption.arr_time
```

但 Phase 2.0 明确：

```text
Gate incidence intentionally deferred
```

当前又没有在 SRM 中做 tail-level Aircraft String assignment。

因此不得假装已经拥有精确的“某 tail 在哪个 gate 停多久”的信息。

---

## 4.2 Phase 2.2 provisional gate 规则

来源标记：

```text
implementation_assumption
generated_provisional
```

采用**机场聚合 Ground Inventory**，不做具体 gate number / tail assignment。

对 airport `a`，初始库存：

```text
initial_ground(a)
=
count(aircraft.initial_station_at_t == a)
```

对任一需要检查的事件时刻 `t`：

```text
ground(a,t)
=
initial_ground(a)
+ cumulative selected arrivals to a up to t
- cumulative selected departures from a up to t
```

约束：

```text
0 <= ground(a,t) <= gate_capacity(a, interval(t))
```

### 事件时点

必须至少检查：

- 该机场 recovery window 内所有 selected-option 候选到达/离港时刻；
- AirportInterval 边界；
- recovery start。

实现时应从**全部候选 event times**预构造 deterministic checkpoint set，不能根据求解后结果临时产生约束。

### 同时刻到达/离港

Generated rule：

```text
同一 airport、同一 timestamp 的 arrival / departure 先做净变化，再检查库存
```

即：

```text
ground_after(t)
=
ground_before(t)
+ arrivals_at_t
- departures_at_t
```

原因：

- 避免纯粹因为事件处理顺序产生虚假的瞬时超容量；
- 等价于允许同一时刻离开的航空器释放位置给同一时刻到达的航空器。

必须写入 `assumptions.md`，以后可人工调整。

### 明确局限

该约束**不是**：

- gate-number assignment；
- terminal-specific gate compatibility；
- widebody/narrowbody gate compatibility；
- towing / remote stand；
- tail-level ground continuity。

这些属于后续业务扩展或 ARM / Integrated Model。

---

## 4.3 Gate incidence / coefficient builder

不要把复杂表达式散落在 `srm.py`。

建议新增独立、可测试结构，例如：

```text
backend/core/gate_inventory.py
```

或同等职责模块。

输出应是 deterministic、可审计结构，例如：

```text
GateCheckpoint(
    airport,
    timestamp,
    capacity_interval_key,
    initial_ground,
    arrival_option_ids,
    departure_option_ids,
)
```

或等价 immutable structure。

要求：

- deterministic ordering；
- unknown airport / uncovered interval 明确报错；
- ferry 在 Phase 2.2 默认排除；
- cancel 不产生 movement；
- 所有 coefficient 可被单元测试直接检查。

---

# 5. Generated Constraint：Market-seat

## 5.1 当前数据缺口

Scenario 有：

```text
Flight.market_flag
Flight.min_seats
Flight.original_equipment
```

但目前没有正式：

```text
equipment seat capacity
tail seat capacity
remaining sellable seat inventory
cabin/class inventory
```

而 `assumptions.md` 已明确：

```text
min_seats != 完整 Passenger Seat Inventory
```

因此 Phase 2.2 不能声称实现真实 passenger seat-capacity。

---

## 5.2 Phase 2.2 provisional proxy

来源：

```text
implementation_assumption
generated_provisional
```

第一版只实现 **Market Service Preservation Proxy**：

若：

```text
market_flag == true
and
min_seats > 0
```

则要求该原航班选择一个 `operate` option：

```text
sum(x_o for o in operated_options(f)) >= 1
```

由于 Flight Coverage 同时要求恰选一个 option，实际等价于：

```text
market flight 不允许 cancel
```

### 为什么允许这一版

它可以：

- 让 `(3.7)` 在工程结构中有明确位置；
- 测试 market constraint 是否真正参与模型；
- 不虚构 aircraft seat capacity；
- 保留 `min_seats` 数据和后续升级入口。

### 为什么不能称为最终 Market-seat

它没有证明：

```text
available_seats >= min_seats
```

因此 diagnostics / docs 中必须写：

```text
MARKET_SEAT_PROXY
```

不得写：

```text
FULL_SEAT_CAPACITY_VERIFIED
```

---

## 5.3 后续升级入口

未来有真实 seat capacity 后，应升级为：

```text
sum(seat_contribution_o * x_o) >= required_market_seats
```

或论文精确的 market aggregation 形式。

升级时：

1. 新增正式 aircraft/equipment seat-capacity contract；
2. 更新 assumption；
3. 删除 proxy 或将其迁移为 compatibility mode；
4. 增加 threshold crossing tests；
5. 不静默改变旧 benchmark 的含义。

---

# 6. 建议新增 Assumptions

实际编号以执行时当前 `assumptions.md` 为准。若仍以 A-026 结尾，可顺序登记：

```text
A-027 Phase 2.2 SRM decision domain / ferry exclusion
A-028 strategic_flag → no-cancel mapping
A-029 provisional aggregate Gate Inventory
A-030 same-timestamp gate event netting
A-031 provisional Market Service Preservation Proxy
A-032 Phase 2.2 single-model result boundary
```

每条至少包含：

```text
来源状态
实现方式
原因
影响
未来替换条件
```

不得只写一句“temporary assumption”。

---

# 7. Phase 2.2 模型实现

## 7.1 文件职责

建议：

```text
backend/core/srm.py
    SRM model construction only

backend/core/gate_inventory.py
    provisional gate coefficient/checkpoint construction

backend/config/costs.py
    继续作为 cost canonical contract
    不把约束逻辑塞入这里

backend/solvers/*
    继续保持 solver abstraction
```

可按现有项目实际目录微调，但职责必须分离。

---

## 7.2 决策变量

第一版至少：

```text
x[flight_option_id] ∈ {0,1}
```

只对 SRM-owned revenue-flight schedule options 建变量。

必须显式决定并记录：

- `operate`：进入；
- `cancel`：进入；
- `ferry`：Phase 2.2 排除，由 ARM owner 处理。

不得为方便而给 ferry 隐式 schedule cost。

---

## 7.3 Objective

使用 Phase 2.1 已冻结：

```text
schedule_flight_option_cost(...)
```

SRM-owned：

```text
flight delay
flight cancellation
origin change
destination change
```

要求：

```text
min Σ cost(option) * x(option)
```

不得重复计入：

```text
aircraft reassignment
ferry
crew reassignment
deadhead
passenger delay
unserved passenger
```

这些已有 canonical owner。

---

## 7.4 Constraint build 顺序

建议固定：

```text
1. validate scenario / columns
2. build deterministic indices
3. build/reuse incidence
4. build gate checkpoints
5. create x variables
6. objective
7. SRM-C01 coverage
8. SRM-C02 strategic
9. SRM-C03 arrival
10. SRM-C04 departure
11. SRM-C05 provisional gate
12. SRM-C06 provisional market
13. optimize through SolverAdapter
14. normalize into ModelSolveResult
15. recompute constraint diagnostics independently
```

最后一步非常重要：

> 不允许只因为 Solver 返回 OPTIMAL 就认为所有业务约束正确。

---

# 8. Result / Diagnostics

`ModelSolveResult` 继续保持模型中立。

SRM 层应额外提供可审计 diagnostics 或 formatter，至少可以得到：

```text
selected_option_by_flight
cancelled_flights
flight_delay_minutes
arrival_capacity_load / slack
departure_capacity_load / slack
gate_inventory / slack
strategic constraint status
market proxy status
objective breakdown by SRM cost item
```

必须明确：

```text
model = SRM
single_model_only = true
```

不得输出“完整恢复方案已经可执行”的含义。

---

# 9. Tests

## 9.1 Pure unit tests

至少覆盖：

### Flight Coverage

- exactly-one；
- missing options；
- cancel vs operate；
- ferry exclusion。

### Strategic

- cancel forbidden；
- delayed operate allowed；
- no operated option → infeasible。

### Capacity

- normal；
- overloaded；
- boundary `[start,end)`；
- cancelled option not counted。

### Gate

构造极小案例：

```text
initial ground = 1
gate cap = 1
```

验证：

1. departure 后 inventory 下降；
2. arrival 后 inventory 上升；
3. 超 gate cap → infeasible；
4. 同时刻 arrival/departure 按净变化；
5. initial inventory 已超过 cap → 明确 infeasible / validation failure；
6. cancel 不改变 inventory。

### Market Proxy

1. `market_flag=false` → 可取消；
2. `market_flag=true,min_seats>0` → 禁止取消；
3. 无 operate option → infeasible；
4. 测试名称必须包含 `proxy`，防止以后误认为完整 seat capacity。

---

## 9.2 Negative tests

至少：

- option 引用未知 base flight；
- airport event 找不到对应 AirportInterval；
- duplicate option ID；
- strategic flight 只有 cancel；
- market proxy flight 只有 cancel；
- gate checkpoint coefficient 构造异常；
- cost profile 缺失/非法仍应由 Phase 2.1 contract 拒绝。

---

## 9.3 Benchmark regression

运行：

```text
phase1_benchmark_001
```

至少检查：

- solver status；
- 每个 flight exactly one schedule choice；
- strategic flights 均 executed；
- market proxy flights 均 executed；
- B airport disruption interval dep load <= capacity；
- arrival load <= capacity；
- gate inventory 不越界；
- objective 可由独立函数复算；
- selected solution 的成本分项总和 == objective（容差内）。

不得硬编码：

```text
必须等于 Phase 1 Manual Reference 的 80 min
```

因为 Phase 1 Reference 不是已证明的 SRM optimum，且 SRM objective 已加入 cancellation / route-change cost。

如果结果与人工 Reference 不同：

1. 先检查模型是否满足所有约束；
2. 再解释 cost difference；
3. 不为匹配 80 min 反向修改成本。

---

# 10. Acceptance Criteria

Phase 2.2 只有同时满足以下条件才能 PASS：

- [ ] `(3.1)–(3.7)` 在当前 fixed-column 语义下均有明确工程映射；
- [ ] C01–C04 为正式 SRM 约束并通过测试；
- [ ] C05 Gate 明确标记 provisional/generated；
- [ ] C06 Market-seat 明确标记 proxy/generated；
- [ ] 所有新假设先进入 `assumptions.md`；
- [ ] 不存在未登记 Magic Number；
- [ ] 不把 ferry / ARM / CRM / PRM 成本混进 SRM；
- [ ] 所有模型通过 `SolverAdapter`；
- [ ] `ModelSolveResult` 语义保持不变；
- [ ] Normal + Broken/Infeasible tests 均存在；
- [ ] benchmark 的所有约束可独立复算；
- [ ] full pytest PASS；
- [ ] Gurobi SRM integration test 在可用环境实际运行，不得被悄悄 skip 后仍宣称完整通过；
- [ ] README / Reproduction Plan / assumptions / Codex Report 同步；
- [ ] 未修改 Frontend。

---

# 11. 本任务明确禁止

不得：

- 修改 HTML / CSS / JS；
- 启用 Recovered Plan 前端；
- 启用正式 `/api/solve` 用户入口；
- 引入真实南航业务规则；
- 虚构 E1 的真实座位数；
- 把 `min_seats` 当成 aircraft capacity；
- 把 Gate proxy 写成精确 gate assignment；
- 把 Market proxy 写成完整 seat-capacity proof；
- 修改成本使结果强行贴合 80-minute Manual Reference；
- 进入 ARM/CRM/PRM；
- 进入 Benders / CG。

---

# 12. Codex 最终报告格式

完成后在：

```text
docs/codex_reports/
```

新增报告，至少包含：

```text
1. Modified Files
2. Constraint Mapping Table
   - constraint_id
   - paper equation
   - implementation
   - provenance
   - test
3. New Assumptions
4. Objective / Cost Ownership
5. Tests Added
6. Full Pytest Result
7. Gurobi Test Result
8. phase1_benchmark_001 Result
9. Constraint Diagnostics
10. Difference vs Manual Reference
11. Known Limitations
12. Acceptance Checklist
13. Next Recommended Step
```

结论必须明确写：

```text
Phase 2.2 PASS
```

或：

```text
Phase 2.2 NOT PASS
```

不得仅回复 `Done`。
