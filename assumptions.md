# 实现假设登记表

本文件用于严格区分：

```text
Petersen et al. (2010) 论文明确给出的内容
vs
论文未完整给出、工程实现必须补全的约定
vs
未来真实航空公司业务扩展
```

任何会影响可行域、目标函数、候选列、恢复结果解释或论文复现一致性的实现选择，都应在这里登记。

---

## A-001 时间表示

**来源状态：**  
论文定义统一的外生恢复窗口 `T = [t, T_end]`，但没有规定 JSON 时间戳格式。

**实现方式：**  
当前 Scenario 只接受带时区信息的 ISO 8601 时间；必须包含 `Z` 或明确 UTC offset。项目示例统一使用 UTC（`Z`）。所有计划航班、机场容量区间和扰动区间必须位于恢复窗口内。

**原因：**  
绝对时间避免跨日期和时区歧义，并保证 JSON 往返稳定。

**影响：**  
接入真实航空公司数据前，需要单独定义机场当地时间与 UTC 的转换规则。

---

## A-002 航班时长

**来源状态：**  
论文中的 Flight String 含航班时刻，但没有定义独立 `duration` 输入字段。

**实现方式：**  
`Flight.duration` 使用整数分钟，并要求：

```text
duration
=
sched_arr - sched_dep
```

**原因：**  
在生成网络前即可发现时刻与时长不一致的数据。

**影响：**  
未来若允许恢复后 Block Time 改变，应通过 Recovery `flight_option` 的 `block_minutes` 表达，而不是静默修改原 Scenario Flight。

---

## A-003 机组资质

**来源状态：**  
论文考虑机组与机型资格，但完整 Crew Legality 取决于航空公司规则。

**实现方式：**  
当前 Scenario 使用单一 `rating` 字符串，并要求其与航班 Equipment 兼容。Phase 1 benchmark 仅使用一个 Equipment Type `E1`。

**原因：**  
先建立可人工核验的最小兼容规则。

**影响：**  
多机型资格、Reserve Crew、值勤限制等在后续 Phase 独立加入。

---

## A-004 原始 Duty 与 Pairing

**来源状态：**  
论文区分 Duty 与 Pairing，但没有规定 JSON 数据交换结构。

**实现方式：**  
`original_duties` 为有序航班 ID 列表的列表；`original_pairing` 等于按顺序展开全部 Duty。

**原因：**  
同时保留 Pairing 与 Duty Boundary，便于后续 CRM。

**影响：**  
当前尚不代表真实航空公司完整 Crew Legality。

---

## A-005 机场容量时间桶

**来源状态：**  
论文使用机场—时间区间上的绝对进港/离港容量。

**实现方式：**  
每条 `AirportInterval` 使用左闭右开：

```text
[start_time, end_time)
```

同机场容量区间不得重叠。

`arr_capacity`、`dep_capacity` 单位为：

```text
架次 / 当前时间桶
```

而不是默认的架次/小时。

**边界规则：**

```text
event_time == end_time
```

不属于当前桶。

**影响：**  
所有 SRM、可视化、benchmark 与后续测试必须使用同一边界语义。

---

## A-006 Disruption 与实际容量分离

**来源状态：**  
论文的优化约束使用实际可用容量。

**实现方式：**

```text
AirportInterval
=
当前 Scenario 实际容量

Disruption.capacity_change
=
描述扰动的元数据
```

禁止从 `capacity_change` 自动反推所谓“扰动前容量”。

**原因：**  
防止输入场景和扰动事件的语义混在一起。

**影响：**  
优化模型直接使用 `AirportInterval`。

---

## A-007 旅客商品组

**来源状态：**  
PRM 将具有共同 O-D、出发条件与到达目标的旅客聚合为 Commodity。

**实现方式：**  
每个 `PassengerCommodity` 包含：

```text
pax_group_id
count
origin
destination
original_departure
scheduled_arrival
original_itinerary
```

**原因：**  
满足论文商品流建模，同时保持人工可核验。

**影响：**  
票价、会员等级、VIP 优先级目前不是论文复现核心。

---

## A-008 Recovery Flight Identity

**来源状态：**  
论文使用恢复网络中的航班副本/时间选择，但没有规定本项目 JSON ID 结构。

**实现方式：**  
原始 Flight ID 永远表示 Scenario 中的原航班。

禁止：

```text
F2_DELAY50
F2_CANCEL
```

作为新的 Flight ID。

恢复方案使用：

```text
base_flight_id = F2
option_id = FO_F2_D50
```

**原因：**  
保证 SRM/ARM/CRM/PRM、Incidence Matrix 与 Column Generation 始终能映射到同一原航班。

**影响：**  
所有后续恢复决策必须引用 `flight_option.option_id`。

---

## A-009 Flight Option 操作语义

**来源状态：**  
论文允许延误、取消及恢复路径变化，但本项目需要统一交换格式。

**实现方式：**

`operation_type`：

```text
operate
cancel
ferry
```

`change_types` 可组合：

```text
unchanged
delay
cancel
origin_change
destination_change
block_time_change
positioning
```

**原因：**  
避免为每个组合恢复动作建立新的专用结构。

**影响：**  
一个航班可同时表达例如：

```text
delay + destination_change
```

---

## A-010 Cancellation 与 Aircraft String

**来源状态：**  
取消航班不会被飞机实际执行。

**实现方式：**  
Cancellation 是 Flight-level Option：

```text
operation_type = cancel
```

取消 option：

- 不进入 Aircraft String；
- 不进入 Crew `operate` segment；
- 不进入 Passenger `flight` segment。

**原因：**  
把“航班决策”和“实际执行路径”分开。

**影响：**  
后续 SRM 负责 Flight Coverage / Cancellation，ARM/CRM/PRM 只覆盖实际执行的 Flight Options。

---

## A-011 Ferry / Positioning Flight

**来源状态：**  
实际恢复中可能需要调机；论文与业务扩展中均存在相关概念，但本项目需要数据交换规则。

**实现方式：**

```text
operation_type = ferry
base_flight_id = null
change_types = [positioning]
```

**原因：**  
Ferry 不对应原计划 Revenue Flight。

**影响：**  
Ferry 可以进入 Aircraft String，后续是否需要 Crew 与成本由模型阶段定义。

---

## A-012 Aircraft / Crew Reassignment

**来源状态：**  
AIR 的核心目标之一是综合恢复 Aircraft 与 Crew。

**实现方式：**  
不额外建立“reassignment option”。

如果某 Aircraft String 覆盖原计划属于另一架飞机的 Flight Option，即表示 Aircraft Reassignment。

Crew 同理。

**原因：**  
Reassignment 是“列被哪一个 Resource 选中”的结果，不是 Flight 本身的新身份。

**影响：**  
Reassignment Count/Cost 必须通过原始 Assignment 与最终 Assignment 比较得到。

---

## A-013 Phase 1 最小时间连续规则

**来源状态：**  
完整 Aircraft Turn Time、Crew Connect Time、Passenger MCT 需要进一步从论文或业务规则定义。

**实现方式：**  
在 `phase1_benchmark_001` 的人工 Reference 中，目前只要求：

```text
previous_arrival <= next_departure
```

不额外加入：

- Aircraft minimum turn；
- Crew minimum connection；
- Passenger MCT。

**原因：**  
Phase 1 的目标是先建立人工可核验的候选列接口，不提前引入尚未正式定义的规则。

**影响：**  
例如 F10 12:30 到 A、F11 12:30 起飞在 Phase 1 当前语义下允许。后续正式引入 MCT/Turn Time 时必须建立新的测试或显式升级 Benchmark，不得静默改变 Oracle。

---

## A-014 Passenger Reaccommodation

**来源状态：**  
论文 PRM 支持受扰旅客重新分配，但没有提供本项目具体 JSON itinerary format。

**实现方式：**  
每个 Passenger Group 可以拥有多个 `passenger_itinerary`：

```text
original
delayed same path
alternative flights
surface
unserved
```

最终选择仍必须达到该 Commodity 的原目标机场，除非未来业务规则明确允许其他处理。

**原因：**  
将 Passenger Choice 与 Flight/Resource Choice 解耦。

**影响：**  
P4 在 Phase 1 Reference 中由 `F2→F3` 改签到 `F8`。

---

## A-015 Phase 1 Passenger Seat Feasibility

**来源状态：**  
完整 PRM Seat Capacity 约束尚未实现。

**实现方式：**  
Phase 1 人工列中的备用 Passenger Itinerary 先作为“路径候选”存在。当前 Manual Reference 对 P4→F8 的选择用于验证 Reaccommodation 接口和资源耦合，但尚未由正式 PRM Seat-Capacity Model 程序化证明。

**原因：**  
当前 Scenario 的 `min_seats` 是论文市场/座位需求相关输入，不等价于一套完整可销售剩余座位 Inventory。

**影响：**  
Phase 2 PRM 必须正式定义并验证 Passenger Capacity；在此之前，Phase 1 Reference 只能称为人工可行参考，而非经过完整 PRM 审计的最优结果。

---

## A-016 Manual Reference 与 Proven Optimal 的区别

**来源状态：**  
论文给出优化目标，但当前代码尚未完成四模型与完整成本系数。

**实现方式：**

`phase1_benchmark_001_expected.json` 当前使用：

```text
reference_type = manual_reference
solution_status = feasible
```

而不是：

```text
solver_optimal
optimal
```

**原因：**  
还没有正式确定并实现：

- Delay Cost；
- Cancellation Cost；
- Aircraft Reassignment Cost；
- Crew Reassignment Cost；
- Passenger Disruption Cost；
- Route Change Cost；
- Ferry / Deadhead Cost。

**影响：**  
当前 80 分钟 Reference 不能宣称为全局最优解。

---

## A-017 Expected / Oracle 比较原则

**来源状态：**  
可能存在多个等价或近等价资源 Assignment。

**实现方式：**  
Expected 分为：

```text
reference_solution
oracle_invariants
comparison_policy
objective
```

默认优先比较：

- Feasibility；
- Flight Recovery Option；
- Cancellation；
- Delay；
- Capacity；
- Maintenance / Terminal；
- Passenger Service；
- Objective（定义后）。

不默认要求完整 Aircraft/Crew Assignment Vector 与人工 Reference 完全一致。

**原因：**  
避免把合法等价解错误判为失败。

**影响：**  
只有在模型成本和唯一性足够明确后，才收紧 exact assignment comparison。

---

## A-018 Phase 1 Benchmark Reference Policy

**来源状态：**  
这是项目自己的人工基准策略，不是论文声明。

**实现方式：**  
当前 `phase1_benchmark_001` 人工 Reference 使用的策略是：

```text
不取消
不改 Origin/Destination
不使用 Ferry
允许 Aircraft Reassignment
允许 Passenger Reaccommodation
优先减少必要 Flight Delay，并保持所有 Passenger Groups 被服务
```

得到：

```text
F2 +50
F10 +20
F11 +10
Aircraft Reassignment = 2
P4 → F8
Total Flight Delay = 80 min
Weighted Passenger Delay = 1800 passenger-min
```

**影响：**  
这是 Phase 1 的 Behavioral Reference，不等价于未来完整 AIR Monetary Objective。

---

## A-019 Visualization 的语义边界

**来源状态：**  
Phase 0.5 可视化早于 Solver 实现。

**实现方式：**  
当前 Visualization 只展示：

```text
Original Plan
Known Disruption
Direct Exposure
Aircraft/Crew Downstream Risk
Airport Capacity Load
```

不把风险推导显示为：

```text
actual delay
cancellation
recovered solution
```

**原因：**  
防止把确定性输入分析与优化结果混淆。

**影响：**  
Recovered Plan 视图应在 Solver/Expected Result 接口正式接入后再启用。

---

## A-020 Passenger Arrival Delay 下限

**来源状态：**
Phase 1B 要求 `arrival_delay_minutes` 非负；`phase1_benchmark_001` 中 P4 改签 F8 后比原计划更早到达，正式 Columns / Expected 均将其记为 `0`。

**实现方式：**
旅客到达延误按以下方式计算：

```text
max(0, recovered_arrival - scheduled_arrival)
```

提前到达不产生负延误，也不抵扣其他旅客的正延误。

**原因：**
保持非负指标语义，并与当前正式人工 Reference 一致。

**影响：**
后续 PRM 成本若需要奖励提前到达，应使用独立成本项，不改变本指标定义。

---

## A-021 Phase 2 Primary Solver 与抽象边界

**来源状态：**
论文实现使用 CPLEX 12.1；本项目当前已通过 Solver Adapter 使用 Gurobi，并要求稳定访问 MIP status、objective bound、gap、LP dual 和 reduced cost。具体 Python Solver 及工程抽象不属于论文算法定义。

**实现方式：**
Phase 2 Primary Solver 选为 Gurobi 13.0.3，依赖固定为 `gurobipy==13.0.3`。SRM/ARM/CRM/PRM 只能依赖 `SolverAdapter`，不得散落 `gurobipy` 调用。Adapter 显式声明 MIP、LP dual、reduced cost、MIP gap 和 objective bound 能力。

当前 pip 包附带的 restricted license 仅用于研究、开发、验证和小规模 smoke tests，不代表生产授权，也不保证能够求解未来大规模实例。

**原因：**
隔离求解器 API，同时在进入 Column Generation 前验证 dual/reduced-cost 可读性。

**影响：**
更换 Solver 时必须实现同一 Contract 和解析 smoke tests。商业部署前必须单独解决正式 License 与规模限制。

---

## A-022 Solver Status Mapping

**来源状态：**
Gurobi 原始整数状态属于求解器 API，不属于 AIR 业务模型语义。

**实现方式：**
业务层只使用：

```text
OPTIMAL
FEASIBLE
INFEASIBLE
UNBOUNDED
INFEASIBLE_OR_UNBOUNDED
NO_SOLUTION
ERROR
```

只有 Gurobi `OPTIMAL` 映射为 `OPTIMAL`。Time/Node/Work/Iteration/Solution/Memory Limit 或 Interrupted 等终止若已有 incumbent，则映射为 `FEASIBLE`；没有 incumbent 则为 `NO_SOLUTION`。数值错误、未知状态和 Adapter 调用错误映射为 `ERROR`。原始状态只保留在 `raw_status` 诊断字段。

**影响：**
`FEASIBLE` 不得冒充已证明最优；import/license/parameter error 不得冒充 `INFEASIBLE`。

---

## A-023 RecoveryExpected 与 ModelSolveResult 分离

**来源状态：**
这是工程结果合同，不是论文数据格式。

**实现方式：**
`RecoveryExpected` 继续只表示 Manual Reference / Oracle Fixture。实际模型输出使用独立、模型中立的 `ModelSolveResult`，记录 status、objective、bound、gap、runtime、变量值、solver metadata 和 diagnostics。

`INFEASIBLE`、`UNBOUNDED`、`INFEASIBLE_OR_UNBOUNDED`、`NO_SOLUTION`、`ERROR` 不允许包含伪造的 objective 或 variable solution。

**影响：**
Phase 2.2-2.5 的单模型结果不代表完整 Integrated Recovery；完整恢复结果留到 Phase 3。

---

## A-024 Phase 2 Test Cost Units 与来源

**来源状态：**
Petersen et al. (2010) Table 2 给出计算实验参数：flight cancellation 25,000、tail assignment 0、crew pairing assignment 0、deadhead flight 1,000、deadhead-to-base 2,000、passenger delay 10/minute、unassigned passenger 2,500。论文没有给出本项目统一字段所需的 flight-delay/minute、origin/destination change、ferry/minute 或 deadhead/minute 系数。

**实现方式：**
`phase2_test_costs_v1` 统一使用 `abstract_cost_units`。直接对应 Table 2 的数值保留论文实验量级，但不声明为当前 USD/CNY 或真实航空公司成本；论文缺失或维度不一致的项标为 `implementation_assumption`，并在每个 coefficient 上记录来源、单位和说明。

**原因：**
形成可执行、可审计的测试 Objective，同时避免把 2010 年论文实验值伪装为当前业务成本。

**影响：**
该 profile 只用于 Phase 2 确定性测试，禁止用于业务报价、经营决策或真实收益评估。

---

## A-025 Cost Canonical Ownership

**来源状态：**
论文分别给出 SRM、ARM、CRM、PRM 目标；本项目需要为 Phase 3 合并明确防重复计费规则。

**实现方式：**

```text
flight delay / cancellation / origin change / destination change -> SRM
aircraft reassignment / ferry                              -> ARM
crew reassignment / deadhead                              -> CRM
passenger delay / unserved                                -> PRM
```

每个 `CostCoefficient` 必须包含且通过校验的唯一 `owner`。Columns 中的 `cost_components` 不作为全局参数真源；全局真源是版本化 `FixedColumnCostConfig`，具体列成本由 Scenario/Column 动态计算。

**影响：**
Phase 3 Integrated Objective 合并时，一个成本项只能由其 canonical owner 收取一次。

---

## A-026 Canonical Phase 2 Test Coefficients

**来源状态：**
以下是论文 Table 2 与明确 Implementation Assumption 的混合测试 profile；数值在建模前冻结，没有为匹配 Phase 1 的 80-minute Manual Reference 反向调参。

| coefficient | value | owner | source |
|---|---:|---|---|
| flight_delay_per_minute | 1 | SRM | Implementation Assumption；应用于 `departure_delay_minutes`；论文把 retiming 包含于 string，但 Table 2 的 equipment-string assignment cost 为 0 |
| flight_cancellation | 25,000 | SRM | Petersen et al. (2010), Table 2 |
| aircraft_reassignment | 0 | ARM | Table 2 individual-tail assignment cost = 0 的 fixed-column 映射 |
| crew_reassignment | 0 | CRM | Table 2 crew-pairing assignment cost = 0 的 fixed-column 映射 |
| passenger_delay_per_pax_minute | 10 | PRM | Petersen et al. (2010), Table 2 |
| unserved_passenger | 2,500 | PRM | Petersen et al. (2010), Table 2 |
| origin_change | 5,000 | SRM | Implementation Assumption |
| destination_change | 5,000 | SRM | Implementation Assumption |
| ferry_per_minute | 5 | ARM | Implementation Assumption |
| deadhead_per_minute | 5 | CRM | Implementation Assumption；论文是 1,000/deadhead flight 与 2,000/return-to-base，不是每分钟 |

**影响：**
SRM 已具备实际测试用 delay/cancellation/route-change 值。进入 ARM/CRM/PRM 时若发现当前字段无法忠实表达相应模型成本，应先版本化升级 profile，而不是在模型代码中加入 Magic Number。

---

## A-027 Phase 2.2 SRM Decision Domain 与 Ferry Exclusion

**来源状态：** `paper_defined + implementation_mapping_assumption`

**实现方式：**
Phase 2.2 为每个具有 `base_flight_id` 的 revenue-flight `operate` / `cancel` option 建立二元变量 `x[option_id]`。`ferry` 没有 base flight，明确排除在 SRM 决策、目标、机场容量和 Gate proxy 之外；它继续由 ARM canonical owner 处理。

**原因：**
论文 SRM 决策是 revenue schedule string/cancellation；当前项目以 fixed Flight Options 表达该选择，而 Ferry 是 Aircraft Recovery Movement。

**影响：**
Phase 2.2 结果只说明 schedule choice，不说明 Ferry、具体 Aircraft、Crew 或 Passenger 可行性。

**未来替换条件：**
进入 ARM / Integrated Model 后，通过独立 aircraft movement 决策和耦合约束处理 Ferry，不修改本 SRM ownership。

---

## A-028 `strategic_flag` 到 No-Cancel 的映射

**来源状态：** `paper_defined + implementation_mapping_assumption`

**实现方式：**
对 `Flight.strategic_flag == true` 的航班，要求其所有 `operation_type == operate` options 的选择和等于 1；cancel option 因而不能被选择。Delayed operate option 仍合法。

**原因：**
论文公式 (3.3) 禁止 strategic flight 被取消；`strategic_flag` 是本项目承载该集合成员关系的字段。

**影响：**
Strategic 不代表 VIP、国际航班、额外成本或任何航空公司特定等级。

**未来替换条件：**
真实航空公司重要航班规则必须作为 `airline_specific_extension` 使用独立字段和测试接入。

---

## A-029 Provisional Aggregate Gate Inventory

**来源状态：** `implementation_assumption + generated_provisional`

**实现方式：**
Phase 2.2 使用机场聚合库存：

```text
ground(a,t)
= initial aircraft at a
+ cumulative selected revenue-option arrivals through t
- cumulative selected revenue-option departures through t
```

在 recovery start、全部 revenue candidate movement times 和 AirportInterval 边界建立确定性 checkpoint，并约束 `0 <= ground(a,t) <= gate_capacity`。Cancel 和 Ferry 不产生 Gate proxy movement。

当前正式 Scenario 的 AirportInterval 没有覆盖每个机场的完整 recovery window。为不虚构缺失时间桶，capacity resolver 优先使用覆盖 checkpoint 的 `[start,end)` interval；内部边界 `interval_i.end_time == interval_j.start_time` 严格归属右侧 `interval_j`。

`recovery_window.end_time` 是显式 terminal gate checkpoint，不按普通半开区间 lookup：若唯一 interval 以 recovery end 为 `end_time`，终点库存审计使用该 interval 的 gate capacity；这不表示 interval 在 recovery end 之后仍有效。若没有这样的 terminal interval，仅当该机场所有已声明 intervals 的 `gate_capacity` 完全一致时，才沿用 provisional airport-wide capacity，并记录首个 interval 为 `capacity_source_key`。其他未覆盖 checkpoint 同样只允许这一一致值 fallback。机场没有 interval、terminal source 不唯一，或未覆盖时存在互相冲突的 gate capacities，builder 必须 fail fast。初始库存高于 recovery-start resolved capacity 也必须 fail fast。

**原因：**
现有数据可支持机场级总量 proxy，但不支持 tail-to-gate occupancy。右侧内部边界与显式 terminal convention 消除了半开区间终点歧义；一致值 extrapolation 则保留现有 benchmark 在不完整时间桶下的可审计兼容性。

**影响：**
该约束不是 gate-number assignment、terminal compatibility、机型兼容、remote stand、towing 或 tail-level continuity。`capacity_source_key` 是容量来源；对 terminal checkpoint 或一致值 fallback，它不声明该时刻在半开区间内部，也不把 interval 的有效性外推到 recovery end 之后。

**未来替换条件：**
Scenario 提供覆盖 recovery window 的完整 Gate Capacity intervals，并冻结 tail-level occupancy / boundary semantics 后，删除一致值 extrapolation，升级为正式 Gate incidence 或 Integrated gate model。

---

## A-030 Same-Timestamp Gate Event Netting

**来源状态：** `implementation_assumption + generated_provisional`

**实现方式：**
同一机场同一 timestamp 的所有 selected arrivals 和 departures 先做净变化，再检查 Gate Inventory：

```text
ground_after(t) = ground_before(t) + arrivals_at_t - departures_at_t
```

Checkpoint 的累计 arrival/departure coefficients 同时包含该 timestamp 的两类事件，不人为指定先后顺序。

**原因：**
允许同刻离港释放的聚合位置供同刻到港使用，避免由遍历顺序造成虚假瞬时超限。

**影响：**
该规则只适用于 aggregate Gate proxy，不证明真实 turnaround、pushback 或 gate occupancy 的事件顺序可行。

**未来替换条件：**
引入可操作的事件时序、buffer 或 tail-level gate assignment 后，用正式规则替换净额 proxy。

---

## A-031 Provisional Market Service Preservation Proxy

**来源状态：** `implementation_assumption + generated_provisional`

**实现方式：**
当 `market_flag == true and min_seats > 0` 时，要求航班选择一个 `operate` option。结合 C01 exactly-one 后等价于禁止 cancel。Diagnostics 固定标识 `MARKET_SEAT_PROXY`，不得标识为完整 seat-capacity proof。

**原因：**
论文公式 (3.7) 需要 equipment seat capacity；当前 Scenario 没有 equipment/tail capacity 或 sellable inventory，`min_seats` 不能独自证明 `available_seats >= required_seats`。

**影响：**
该 proxy 只保存 market flight service，不检查座位阈值，也不计算 Passenger seat consumption。

**未来替换条件：**
增加正式 equipment/aircraft seat-capacity contract 后，升级为 `sum(seat_contribution * x) >= min_seats` 并增加 threshold tests；不得静默改变旧 benchmark。

---

## A-032 Phase 2.2 Single-Model Result Boundary

**来源状态：** `implementation_interface`

**实现方式：**
SRM 继续返回通用 `ModelSolveResult`，并在其 diagnostics 中增加独立复算的 schedule choice、capacity、Gate proxy、strategic、Market proxy 和 objective breakdown。固定标识：

```text
model = SRM
single_model_only = true
```

**原因：**
SRM 未求解具体 Aircraft、Maintenance、Crew 或 Passenger 决策，不能输出完整 Recovery。

**影响：**
即使 SRM 为 OPTIMAL，也只能声称 schedule submodel 在当前 fixed-column/proxy 合同下最优；不能声称综合恢复可执行或 Phase 1 Manual Reference 被整体改进。

**未来替换条件：**
Phase 3 Integrated Oracle 完成并通过全资源可行性与统一目标验证后，另行设计完整恢复结果层。

---

## A-033 Phase 2.3 ARM External Schedule Input Boundary

**来源状态：** `implementation_interface`

**实现方式：**
ARM 接收独立、不可变的 `AircraftRecoveryRequest(scenario_id, required_operated_option_ids)`。SRM 到下游资源模型的转换统一由 pure `extract_required_operated_option_ids` 完成：它要求 SRM 对 Columns 中每个 base flight 恰有一个可核对的 selection，合法 cancel 被正常过滤，revenue operate 被保留；unknown ID、ferry、base-flight mapping 不一致、重复或缺失 selection 必须 fail fast。这些输出 IDs 必须是当前 Columns 中唯一、合法的 revenue `operate` options，且同一 base flight 最多出现一次。ARM/CRM 不自行解析 SRM diagnostics，也不重新选择 cancel、delay 或 route change。

**原因：**
Phase 2.3 是独立 aircraft recovery 子模型；canonical schedule-to-resource handoff 使 ARM 与 CRM 对 cancellation 的解释一致，也使 unit test、SRM→resource benchmark 流程和未来 Integrated coupling 都可审计。

**影响：**
Schedule 不可由 ARM 为获得可行性而静默改变。若现有 Aircraft Strings 无法覆盖外生 schedule，ARM 必须返回 infeasible。

**未来替换条件：**
进入 Integrated Oracle/Benders 后，用显式 master/subproblem coupling 替换测试流程中的顺序调用，但保留 schedule ownership。

---

## A-034 One Explicit Tail-Specific String per Aircraft

**来源状态：** `paper_defined:(3.10) + implementation_mapping_assumption`

**实现方式：**
每架 Scenario aircraft 必须从已绑定该 `aircraft_id` 的 fixed Aircraft Strings 中恰选一条。没有候选 String 时建模前 fail fast；需要原地等待时必须显式提供空 legs 的合法 idle/null String，不允许用“选择零条”隐式表达。

**原因：**
论文公式 (3.10) 写作等式 1，并在正文用 null string 处理原地等待；当前 Schema 的 String 已预先绑定具体 tail，因此变量为 `y[string_id]`。

**影响：**
这比论文正文中的“no more than one”表述采用更明确的公式/任务合同语义。候选列集合必须包含每架飞机的完整恢复选择。

**未来替换条件：**
若后续允许 aircraft 不参与 recovery，必须通过显式 idle/unavailable column 或新状态合同建模，不得静默把等式改为不等式。

---

## A-035 ARM Fixed-Option Mapping of Paper String Coupling

**来源状态：** `paper_defined:(3.9) + implementation_mapping_assumption`

**实现方式：**
论文 (3.9) 将 SRM 已选 schedule string 分配给 tail；当前 SRM 输出 Flight Options 而非 schedule-string variables。因此 ARM 使用 Phase 2.0 `option_to_aircraft_strings` incidence：每个 required revenue option 恰好由一条 selected Aircraft String 覆盖，所有 non-required revenue operate options 的 selected-string coverage 必须为零。Ferry 可随 selected String 执行，但不进入 revenue coverage。

**原因：**
required coverage 单独使用不足以阻止 String 携带与外生 schedule 冲突的额外 revenue option；零泄漏约束共同形成当前 fixed-option 版本的 (3.9) 映射。

**影响：**
该映射不声称与论文“SRM 直接选择完整 string”的变量结构相同，但保证 ARM 不重新决定 schedule。

**未来替换条件：**
Integrated Oracle 使用统一 schedule-string 变量或正式 linking constraints 后，以直接的 master-string coupling 替换此 fixed-option 映射。

---

## A-036 ARM Terminal and Fixed-String Eligibility

**来源状态：** `paper_prose + implementation_mapping_assumption`

**实现方式：**
Phase 2.3 继续信任现有 Column semantic validation 对 start station、station/time continuity、equipment compatibility、known legs 和 terminal fields 的检查，并在 ARM 中额外显式约束 selected String 的 `end_station == required_station_at_T_end`。不加入未冻结的 aircraft minimum turn time。

**原因：**
论文把 terminal/null-string 与其他 tail eligibility 规则写在 ARM 正文而非独立编号公式中；当前人工 fixed columns 已携带可审计路径字段。

**影响：**
ARM-C03/C05 是对已验证候选列的模型防线，不代表完整航司 tail restriction、机场适航或 turnaround 规则。

**未来替换条件：**
新增正式 turn-time、tail restriction 或 station compatibility inputs 后，先登记并扩展 validator/column generator，再升级 ARM eligibility。

---

## A-037 Fixed-Column Maintenance Flag Trust

**来源状态：** `paper_defined:(3.11) + implementation_mapping_assumption`

**实现方式：**
若 aircraft `maintenance_required == true`，被选 String 必须 `maintenance_satisfied == true`。该 flag 与 maintenance station/end-station 一致性由现有 semantic validator 校验；ARM 不重新构造维修事件或时刻表。

**原因：**
论文 (3.11) 确保 String 包含合格维修机会，并说明具体维修计划可后处理；当前 Schema 只有已验证布尔属性，缺少细粒度 maintenance visit/timing 数据。

**影响：**
可证明 fixed-column maintenance flag 被执行，不能证明真实完整维修排程可执行。

**未来替换条件：**
引入 maintenance task、station capability、duration 与 due-time contract 后，用正式 visit/time incidence 替换布尔 flag。

---

## A-038 ARM Reassignment and Ferry Cost Mapping

**来源状态：** `implementation_assumption`

**实现方式：**
Aircraft String 中每个 revenue operate leg 的 `base_flight.original_aircraft != string.aircraft_id` 计一次 reassignment；每个 Ferry leg 按 `block_minutes * ferry_per_minute` 计费。系数只来自 `FixedColumnCostConfig`，Columns `cost_components` 不是真源。

**原因：**
论文 (3.8) 使用 tail-string assignment cost，但没有给出当前 per-ferry-minute 字段维度；该项目需要可执行且 canonical-owner 唯一的 ARM test objective。

**影响：**
ARM 只收取 aircraft reassignment 与 Ferry；不重复收取 SRM/CRM/PRM 成本。当前 test profile 的 reassignment 为 0，但计算逻辑仍保留并用非零临时系数测试。

**未来替换条件：**
真实航司提供校准的 tail disruption/ferry 成本合同后版本化升级 profile，不在模型中加入 Magic Number。

---

## A-039 Phase 2.3 ARM Single-Model Result Boundary

**来源状态：** `implementation_interface`

**实现方式：**
ARM 返回通用 `ModelSolveResult`，diagnostics 固定标识 `model = ARM`、`single_model_only = true`，并独立复算 String selection、required/unexpected coverage、terminal、maintenance、Ferry、reassignment 和 objective breakdown。

**原因：**
ARM 只验证外生 schedule 在现有 fixed Aircraft Strings 下的 aircraft recovery 子问题。

**影响：**
ARM feasible/optimal 不代表 Crew、Passenger 或 Integrated Recovery 可行；ARM infeasible 也不得触发对 SRM schedule 的静默修改。

**未来替换条件：**
Phase 3 Integrated Oracle 完成统一耦合与全资源审计后，另行形成完整恢复结果层。

---

## A-040 Phase 2.4 CRM External Schedule Input Boundary

**来源状态：** `implementation_interface`

**实现方式：**
CRM 接收独立、不可变的 `CrewRecoveryRequest(scenario_id, required_operated_option_ids)`；测试与顺序模型流程只能通过 A-033 的 canonical `extract_required_operated_option_ids` 从 SRM 结果构造该集合。CRM 不读取 SRM diagnostics，也不重新决定 schedule。

**原因：**
Crew recovery 必须消费已经确定的 revenue-operate schedule，取消航班不需要 operating crew。

**影响：**
若 fixed Crew Pairings 无法覆盖外生 schedule，CRM 返回 infeasible；不得静默修改或放松 schedule。

**未来替换条件：**
Integrated Oracle/Benders 建立显式 schedule-to-crew coupling 后替换顺序调用，但保留 schedule ownership。

---

## A-041 One Explicit Pairing per Crew and Paper (3.15) Mapping

**来源状态：** `paper_defined:(3.15) + implementation_mapping_assumption`

**实现方式：**
每个 Scenario crew 从绑定该 `crew_id` 的 fixed Crew Pairings 中恰选一条。论文 (3.15) 的 `nu_k` deadhead-to-base alternative 在当前 Schema 中没有独立变量；idle、reserve 或纯回基地行为必须由显式 pairing 表达，不能用“零条 pairing”暗示。

**原因：**
当前数据合同只有完整、crew-owned pairing，且包含 start/end station；不存在可可靠计算的独立 return-to-base option。

**影响：**
无显式候选 pairing 的 crew 在建模前 fail fast。该固定列映射不声称变量结构与论文完全相同。

**未来替换条件：**
引入正式 deadhead-to-base decision/cost contract 后，可按论文恢复 `nu_k` 或等价显式列。

---

## A-042 Single Crew-Unit Operating Coverage and Paper (3.14) Mapping

**来源状态：** `paper_defined:(3.14) + implementation_mapping_assumption`

**实现方式：**
每个 required revenue Flight Option 要求恰好一个 selected pairing 以 `CrewSegmentType.OPERATE` 覆盖；non-required revenue option 的 operating coverage 为零。论文 (3.14) 中允许 surplus/deadhead operating resources 的 `s_f` 在当前模型中不单独建变量，固定列版本采用严格的单 crew-unit exact coverage。

**原因：**
当前 Scenario 不含 Captain/FO/Cabin 等岗位和人数需求；不能自行虚构多岗位 crew complement。

**影响：**
模型验证 aggregate single crew-unit coverage，不证明真实航班机组编制满足。

**未来替换条件：**
增加岗位、资格与每航班人数需求后，将 incidence 扩展为 role-specific coverage，并重新核对 (3.14) 的 surplus 语义。

---

## A-043 Operating / Deadhead Separation and Schedule Consistency

**来源状态：** `implementation_guard`

**实现方式：**
仅 `CrewSegmentType.OPERATE` 可满足 A-042 coverage；`DEADHEAD` 独立记录且不能贡献 operating coverage。所有 fixed pairing 的 OPERATE/DEADHEAD flight segment 必须引用 revenue OPERATE option，CANCEL 或 FERRY reference 在建模前 fail fast；selected pairing 的 deadhead leg 还只能引用 required operated revenue option，non-selected alternate 通过模型约束禁止。

**原因：**
同一航班上的 operating crew 与 positioning crew 业务含义不同，且 deadhead 只能搭乘实际执行的 schedule leg。

**影响：**
CRM 同时约束 operating leakage 与 deadhead schedule leakage，并分别审计两种 incidence。

**未来替换条件：**
若引入独立 ground/ferry crew transportation contract，再以明确 transport type 扩展，不通过命名猜测。

---

## A-044 Fixed Crew Pairing Legality and Terminal Trust

**来源状态：** `fixed-column validation assumption`

**实现方式：**
Phase 2.4 信任现有 semantic validator 对 crew ownership、known options、OPERATE rating、start/end station、station continuity、time order与 CANCEL prohibition 的校验；CRM 另以显式 eligibility/terminal 约束形成模型防线。当前 Schema 没有 duty-time/rest-limit legality flag，CRM 不推断真实航司规则。

**原因：**
本阶段使用人工 fixed pairings，不是在 MIP 内生成 pairing 或实现完整 Crew Scheduling engine。

**影响：**
CRM feasible 只证明当前已验证固定列下的 crew recovery 可行，不证明真实航空公司 duty/rest/base 规则完整满足。

**未来替换条件：**
冻结 duty/rest/qualification/base 业务合同并由 pairing generator/validator 实现后，再升级 eligibility。

---

## A-045 CRM Reassignment and Deadhead Cost Mapping

**来源状态：** `paper_defined:(3.13) + implementation_assumption`

**实现方式：**
Pairing 中每个 OPERATE revenue leg 若 `base_flight.original_crew != pairing.crew_id`，计一次 crew reassignment；每个 DEADHEAD revenue leg按 `block_minutes * deadhead_per_minute` 计费。系数唯一来自 `FixedColumnCostConfig`，Columns `cost_components` 不是真源。

**原因：**
Scenario 已提供原始 crew ownership，Columns 已明确 segment type 与 block time；论文 (3.13) 给出 pairing/deadhead 成本结构，但没有直接给出当前 per-minute 数据映射。

**影响：**
CRM 只收取 crew reassignment 与 deadhead，不重复计入 SRM、ARM 或 PRM-owned costs。

**未来替换条件：**
真实航司提供校准成本及独立 deadhead-to-base 合同后版本化更新，不在模型中加入 Magic Number。

---

## A-046 Phase 2.4 CRM Single-Model Result Boundary

**来源状态：** `implementation_interface`

**实现方式：**
CRM 返回通用 `ModelSolveResult`，diagnostics 固定标识 `model = CRM`、`single_model_only = true`，并独立复算 pairing selection、operating/deadhead coverage、legality、terminal、reassignment、deadhead minutes 与 objective breakdown。

**原因：**
CRM 只求解外生 schedule 在现有 fixed Crew Pairings 下的 crew recovery 子问题。

**影响：**
CRM optimal 不代表 Aircraft、Passenger 或 Integrated Recovery 可行；CRM infeasible 不授权修改 schedule。

**未来替换条件：**
Phase 3 Integrated Oracle 完成统一耦合与全资源审计后，另行形成完整恢复结果层。

---

## A-047 Phase 2.5 PRM External Schedule Boundary

**来源状态：** `implementation_interface`

**实现方式：**
PRM 接收不可变 `PassengerRecoveryRequest(scenario_id, required_operated_option_ids, capacity_profile_id)`。测试与顺序流程复用 canonical `extract_required_operated_option_ids` 从 SRM 结果获得实际执行的 revenue Flight Options；PRM 不读取或重解 SRM schedule，也不依赖 ARM Result。

**原因：**
Phase 2.5 是独立 fixed-column passenger recovery 子模型，只消费外生 schedule 与 capacity。

**影响：**
schedule 不匹配的 transported itinerary 被显式固定为零；PRM 不得通过改变延误或取消决策恢复可行性。

**未来替换条件：**
Phase 3 Integrated Oracle 以显式 schedule-passenger coupling 取代顺序接口。

---

## A-048 Test Seat Capacity Profile and Paper (3.17) Mapping

**来源状态：** `paper_defined:(3.17) + implementation_mapping_assumption`

**实现方式：**
`PassengerCapacityProfile.seat_capacity_by_option_id` 是每个 revenue OPERATE option 可供当前模型内 Passenger Commodities 使用的 residual seat inventory，对应论文 (3.17) 的 equipment capacity 减 nondisrupted planned passengers 后的右端项。它是版本化、只读的外生 test input，来源只能标记 `implementation_assumption` 或 `test_fixture`。

**原因：**
当前 Scenario 没有 aircraft/equipment seat capacity、remaining inventory 或 cabin/class inventory；`Flight.min_seats` 是 SRM market-service proxy，不能作为 seat capacity。

**影响：**
Phase 2.5 首次程序化执行 passenger seat-load constraint，但 profile 数字不是真实 aircraft capacity、航司库存或论文数据。所有 required operated options 必须有显式 capacity，禁止默认无限容量。

**未来替换条件：**
引入真实 equipment/cabin inventory，并由 selected ARM assignment 映射到 Flight Option residual capacity 后版本化替换。

---

## A-049 Passenger Group Indivisibility and Paper (3.18) Mapping

**来源状态：** `paper_defined:(3.18) + implementation_mapping_assumption`

**实现方式：**
论文将 `z_{i,γ}`、`s_i` 定义为非负整数旅客人数流；当前项目的 `PassengerCommodity` 与 fixed `PassengerItinerary` 是 group-level 列，因此第一版为每条 itinerary 建 binary `w_i`，每个 group 恰选一条 transported 或 explicit unserved itinerary。group 不拆分；论文的独立 `s_i` 映射为显式 UNSERVED itinerary。

**原因：**
现有列由 `pax_group_id` 唯一归属，未提供可审计的 group splitting 输出合同。

**影响：**
容量冲突时整个 group 改签或 unserved，不能把部分成员分到不同 itineraries；这是比论文旅客流更粗的 fixed-column 映射。

**未来替换条件：**
若业务要求 group splitting，升级变量、结果 schema 与审计为整数 passenger flow，并重新核对 cost/capacity incidence。

---

## A-050 Fixed Passenger Itinerary Feasibility Trust

**来源状态：** `fixed-column validation assumption`

**实现方式：**
PRM 建模前复用 Recovery Columns validator 对 group ownership、known revenue option、OD/station continuity、时间不重叠、final destination、arrival time/delay 与 UNSERVED shape 的校验；模型不动态生成 itinerary。

**原因：**
Phase 2.5 冻结现有人工列，不实现 Passenger Itinerary Generator。

**影响：**
当前连接规则仅证明 `previous_arrival <= next_departure`，不代表真实 Minimum Connection Time 或航空公司旅客保护政策。

**未来替换条件：**
Phase 7 引入正式 MCT、connection 与 itinerary generation contract 后升级。

---

## A-051 Passenger Seat Load Uses Commodity Count

**来源状态：** `paper_defined:(3.17) + group_mapping`

**实现方式：**
选中 itinerary 在其每个 FLIGHT segment 上消耗 `PassengerCommodity.count` 个 seats；SURFACE 与 UNSERVED 不消耗 flight seats。约束为 `sum(count[g(i)] * A[o,i] * w_i) <= capacity[o]`。

**原因：**
论文容量左端是旅客人数，不是 itinerary/group 个数。

**影响：**
一个 15 人 group 消耗 15 seats，而不是 1 seat；group indivisibility 仍由 A-049 约束。

**未来替换条件：**
升级为可拆分 passenger flow 时，用整数流量本身替代 binary 乘 group count。

---

## A-052 PRM Delay and Unserved Cost Mapping

**来源状态：** `paper_defined:(3.16) + implementation_cost_contract`

**实现方式：**
transported itinerary 成本为 `count * arrival_delay_minutes * passenger_delay_per_pax_minute`；UNSERVED 成本为 `count * unserved_passenger`，不再叠加 arrival delay。系数唯一来自 `FixedColumnCostConfig`，Columns `cost_components` 不是真源。

**原因：**
这分别映射论文 (3.16) 的 aggregate passenger delay 与 unable-to-assign cost，并遵守 A-025 canonical ownership。

**影响：**
PRM 不重复收取 SRM flight delay，也不凭经验增加 reaccommodation、surface、missed-connection penalty。当前单位仍是 abstract test units。

**未来替换条件：**
真实航司成本或论文扩展项形成版本化合同后再升级。

---

## A-053 Reaccommodation Diagnostic Mapping

**来源状态：** `implementation_metric_mapping`

**实现方式：**
selected transported itinerary 的 base-flight sequence 与 Passenger Commodity `original_itinerary` 不同，或包含 SURFACE segment，则 group 计为 reaccommodated；仅由同一 base flight 的 ORIG option 改为 delayed option不计改签。UNSERVED 不同时计为 reaccommodated。

**原因：**
当前 Cost Contract 没有独立 reaccommodation penalty，且 option-level delay 不等于改变旅客路径。

**影响：**
reaccommodation 是可独立复算的 diagnostic，不是决策变量或 Cost Owner。

**未来替换条件：**
正式 fare/class、ticketing 或 protection policy 数据可支持更精细定义时版本化调整。

---

## A-054 Phase 2.5 PRM Single-Model Result Boundary

**来源状态：** `implementation_interface`

**实现方式：**
PRM 返回 `ModelSolveResult`，diagnostics 固定标识 `model = PRM`、`single_model_only = true`，并独立复算 group selection、schedule compatibility、seat load/slack、delay、unserved、reaccommodation 与 objective。

**原因：**
本阶段只求解外生 schedule 和 test capacity 下的 fixed Passenger Itineraries。

**影响：**
PRM optimal 不代表完整 AIR recovery optimal、真实 aircraft capacity feasible 或真实 passenger protection plan feasible。

**未来替换条件：**
Phase 3 Integrated Oracle 完成统一耦合与全资源审计后另行形成完整恢复结果层。

---

## A-055 SRM Proxy and Future ARM Capacity Coupling

**来源状态：** `implementation_boundary`

**实现方式：**
Phase 2.2 `SRM-C06 MARKET_SEAT_PROXY` 暂时保留为 schedule-level provisional constraint；Phase 2.5 capacity 是第一个显式 passenger seat-load constraint，但不从 ARM 推导。

**原因：**
SRM、ARM 与 PRM 当前仍为相互独立的 fixed-column 模型，删除 proxy 或伪造 equipment capacity 都会提前引入未冻结的跨模型语义。

**影响：**
test capacity 不得被当作 aircraft truth，ARM assignment 也不会在 PRM 内部重新求解。

**未来替换条件：**
Phase 3 冻结 selected aircraft/equipment 到 option capacity 的 handoff 后，统一审查 SRM proxy 的去留。

---

## A-056 Phase 3 v1 Frozen Boundary

**来源状态：** `implementation_phase_boundary`

**实现方式：**
Phase 3 v1 正式定义为 `Full Integrated Fixed-Column Oracle`，用于验证 SRM、ARM、CRM、PRM 联合建模及跨模型耦合。冻结原则如下：

- 继续使用现有 fixed Recovery Columns，不动态生成 Flight Options、Aircraft Strings、Crew Pairings 或 Passenger Itineraries；
- 继续使用 `phase2_test_costs_v1`，Integrated Objective 仅按 A-025 canonical owner 汇总 SRM + ARM + CRM + PRM 成本；
- 不增加模型级权重、隐藏 epsilon 或人为 tie-breaking penalty，允许等价最优解；
- 继续使用 A-048 的 Phase 2 test/residual Passenger Capacity Profile，并明确它不是 aircraft physical capacity；
- 继续保持 A-049 的 PassengerCommodity group 不拆分，一组整体选择一条 itinerary 或 UNSERVED；
- Phase 3 v1 暂时保留 A-055 的 SRM Market-seat Proxy，并持续标记 `PROVISIONAL / PROXY`；
- 不加入南航特定业务规则，不进入 Benders / Column Generation，也不追求生产级真实参数。

**原因：**
Phase 3 v1 的唯一目标是建立可审计的整体 fixed-column Oracle；同时改变列空间、业务规则、容量真源、成本权重或分解算法会使跨模型耦合验证失去清晰基线。

**影响：**
Phase 3 v1 的可行性和最优性只在当前人工列、test cost 与 test/residual capacity 合同内成立，不代表真实航空公司生产恢复最优。

**未来替换条件：**
Full Integrated Fixed-Column Oracle 通过 benchmark、independent audit 与等价解审查后，再分别版本化引入业务规则、真实 capacity、动态列与分解算法。

---

## A-057 Phase 3 v1 Explicit Cross-model Linking

**来源状态：** `implementation_mapping`

**实现方式：**
Integrated Oracle 不再接收 Phase 2 的外生 `required_operated_option_ids`。每个 revenue `OPERATE` option 建立 schedule binary `x[o]`，Aircraft String、Crew Pairing、Passenger Itinerary 分别使用 `y[s]`、`z[p]`、`w[i]`，并在同一 MIP 中执行：

- selected Aircraft operating coverage `= x[o]`；
- selected Crew operating coverage `= x[o]`，DEADHEAD 不计入 operating coverage；
- 每个 selected DEADHEAD incidence 满足 `z[p] <= x[o]`；
- itinerary 的每个 FLIGHT segment 满足 `w[i] <= x[o]`；
- passenger load 满足 `load[o] <= residual_capacity[o] * x[o]`。

`CANCEL` 仍是 base-flight coverage 中的 schedule option；选择它会令该 base flight 的所有 `OPERATE x[o]=0`，从而通过上述 linking 自动切断 Aircraft、operating Crew、Deadhead 和 Passenger 使用。`FERRY` 不建立 revenue schedule `x`，继续只存在于 Aircraft String 并由 ARM owner 收费；UNSERVED 不引用 Flight Option。

**原因：**
这是从 Phase 2 顺序子模型升级为单一 Integrated MIP 所必需的可审计耦合映射，并直接落实 Phase 3 实施计划的 feasible-region 语义。

**影响：**
Schedule、Aircraft、Crew 与 Passenger 可相互影响联合最优选择；未选 alternate option 不得被任何 selected resource/passenger column 泄漏使用。容量右端仍遵循 A-048/A-056 的 test/residual 语义。

**未来替换条件：**
引入动态列或分解算法时必须保持与本 Oracle 等价的 linking 语义；引入 aircraft physical capacity 时另行版本化替换 residual capacity 来源，不静默修改本假设。

---

## A-058 Phase 4 Paper Mapping and Fixed-column Closure Extension

**来源状态：** `paper_defined:Appendix Algorithms 3-6 + implementation_safety_extension`

**实现方式：**
论文 Algorithm 3 映射为 Scope 总控闭包；Algorithm 4 映射为 direct disruption 与 aircraft rotation/candidate string 的航班传播；Algorithm 5 映射为 crew pairing 的 OPERATE/DEADHEAD 传播；Algorithm 6 映射为 passenger itinerary 与替代航班传播。当前实现额外沿 fixed-column reassignment、airport capacity row、aggregate gate checkpoint 与 shared seat usage 传播，直到 Flight / Aircraft / Crew / Passenger 集合不再扩张。

**原因：**
论文伪代码面向其生成算法与 eligible move-up 定义；当前仓库尚无动态 generator，Phase 3 MIP 的可行域由人工 fixed columns 及共享约束共同定义。只照搬单轮论文伪代码会遗漏当前 Oracle 中真实存在的耦合。

**影响：**
这是可追溯的论文映射，不宣称逐字或精确复现 Algorithms 3-6。Scope 只对当前已验证 fixed-column universe 保证安全闭包。

**未来替换条件：**
Phase 5+ 引入 generator、正式 eligible move-up、turn time 与业务规则后，按新的候选宇宙重新验证传播与论文映射。

---

## A-059 Phase 4 Scope Freeze Semantics

**来源状态：** `implementation_phase_boundary`

**实现方式：**
Phase 4 v1 不删除 Scenario、Columns、变量或 Phase 3 约束。Scope 内 owner 的全部 candidates 保持自由；Scope 外 Flight / Aircraft / Crew / Passenger owner 分别通过 `SCOPE-FIX-*` 约束固定到唯一语义原计划 candidate。`scope=None` 不增加任何冻结约束并保持 Phase 3 Full Oracle 数学模型。

**原因：**
物理裁剪可能破坏 airport capacity、gate boundary、terminal、maintenance 或 seat linking 的全局语义。冻结方式可直接用 Full Oracle 审计等价性。

**影响：**
Phase 4 的缩减指标是 free decision candidates，而不是 Solver 模型中物理变量数量。Scope objective 只在当前 fixed columns、cost profile 与 residual capacity profile 下与 Full objective 比较。

**未来替换条件：**
等价性在更广泛案例持续成立后，另立 Phase 4.2 Reduced Materialization，并重新审计边界常数与所有共享约束。

---

## A-060 Semantic Original Candidate Resolution

**来源状态：** `implementation_contract`

**实现方式：**
原计划 Flight Option 按 OPERATE、唯一 UNCHANGED、原 route/times/block 与零 delay 识别；Aircraft String 按 original rotation 对应的 original revenue options 顺序识别；Crew Pairing 按 original pairing 对应的 original OPERATE options 顺序识别；Passenger Itinerary 按 original itinerary 对应的 original FLIGHT options 顺序识别。候选 ID 文本不参与判断；缺失或多解均显式失败。

**原因：**
`*_ORIGINAL` 等命名是测试数据惯例，不是业务语义，不能成为冻结正确性的依据。

**影响：**
所有要被 Scope 冻结的数据集都必须提供唯一可解析的原计划 candidate。原 Aircraft String 不得含额外 FERRY/positioning leg，原 Crew Pairing 不得含额外 DEADHEAD/ground/rest segment，原 Passenger Itinerary 不得含额外 SURFACE/recovery-only segment；这类候选即使 revenue/flight sequence 相同也不匹配原计划。

**未来替换条件：**
若未来 Schema 增加版本化的显式 original-candidate 标志，可在保持语义交叉校验的前提下升级 resolver。

---

## A-061 Conservative Shared-row Closure and Benchmark Connectivity

**来源状态：** `implementation_safety_assumption`

**实现方式：**
只要 scoped option 与其他 option 同处一个 arrival/departure capacity row 或 aggregate gate checkpoint，相关 revenue base flights 就加入 Scope；共享 scoped option 的 passenger groups 也加入 Scope。不会仅因行当前 slack 较大而跳过传播。

**原因：**
行是否 binding 是解相关属性，在求解前据此裁剪会产生循环推理并可能改变最优解。

**影响：**
保守闭包可能较大。`phase1_benchmark_001` 的三个直接受扰航班经累计 gate、resource candidates 与 passenger alternatives 连通全部实体，因此合法结果是 Full Scope；实际缩减由保留独立无关组件的 `toy_case_006_scope` 验证（free binary candidates `10/14`）。

**未来替换条件：**
若引入经证明安全的约束分解、边界固定或 reduced materialization，可在不依赖最优解猜测的前提下收紧 shared-row closure。

---

## A-062 Phase 5 Aircraft Turn Time Test Profile

**来源状态：** `implementation_assumption`

**实现方式：**
Phase 5 使用版本化 `FlightStringGenerationConfig`，`min_turn(aircraft)` 取 equipment override，否则取 `default_min_turn_minutes`。测试配置 `phase5_test_string_generation_v1` 默认 `15` 分钟；`E1` 显式 override 为 `0` 分钟，以保留 Phase 1 benchmark 已冻结的零间隔人工候选列。

**原因：**
Turn Time 首次进入自动 String legality，不能成为代码 Magic Number；同时不得静默改变既有 Phase 3/4 Oracle 的候选含义。

**影响：**
`E1=0` 只是向后兼容的工程测试边界，不是生产航空公司的合法过站标准。其他未 override 机型使用 15 分钟测试值。

**未来替换条件：**
接入航司机型、机场、国内/国际与维修场景的正式 turn-time 数据后，发布新的配置版本并重新生成/审计全部 Strings。

---

## A-063 Phase 5 Airport-local Restriction Boundary

**来源状态：** `implementation_assumption`

**实现方式：**
String Generator 仅把 `curfew_flag` 以及显式 hard-local tokens `closed`、`departure_closed`、`arrival_closed` 作为 aircraft-local 禁止条件。`reduced_departure_rate` 和 disruption `departure_capacity_reduction` 不删除 Flight Option，继续由 Integrated SRM airport-capacity constraints 处理。重叠 local intervals 被视为歧义并拒绝对应 movement。

**原因：**
容量削减是多航班共享约束，提前在单机网络删除 option 会错误收缩可行域；当前 `weather_restrictions` 没有完整航司语义字典。

**影响：**
未知 weather token 不被猜测为 hard closure。当前只承诺上述最小 hard-local 语义。

**未来替换条件：**
建立版本化机场限制 taxonomy 与业务规则后，扩展 eligibility 并增加逐规则 Oracle。

---

## A-064 Phase 5 Maintenance Simplification

**来源状态：** `implementation_assumption`

**实现方式：**
当前 Schema 无 maintenance task、duration、due time 或 capacity。`maintenance_required=false` 的生成列标记 `maintenance_satisfied=true`；`maintenance_required=true` 时，仅当 required terminal station 属于 `maintenance_stations` 才能输出，并继续要求 `maintenance_satisfied=true`。

**原因：**
该规则与现有 Column Validator、ARM-C04 能独立证明的语义一致，不虚构维修排程。

**影响：**
“到达维修站”不代表真实维修任务已在某一时段完成。

**未来替换条件：**
增加 maintenance task/time/capacity Schema 后，用正式资源约束替换此 terminal proxy。

---

## A-065 Phase 5 Explicit Idle String

**来源状态：** `implementation_assumption`

**实现方式：**
仅当 aircraft initial station 等于 required terminal station，且当前 maintenance proxy 允许时，生成零 leg 的显式 idle Aircraft String。ARM/Integrated Oracle 仍对每架 Aircraft 恰选一条 String，不用“零条被选列”暗示 idle。

**原因：**
保持 existing exactly-one String selection contract，并使 idle 决策可审计。

**影响：**
Idle String 不承担未建模的 parking、crew 或 maintenance duration 语义。

**未来替换条件：**
引入 ground-state network 或正式 parking/maintenance constraints 后重新定义 idle column。

---

## A-066 Phase 5 Existing-option Full Enumeration Boundary

**来源状态：** `implementation_phase_boundary`

**实现方式：**
Phase 5 只消费已有 Flight Options，以 Flight Network + DFS 显式枚举所有合法 Aircraft Strings。Scoped Aircraft 全量生成；out-of-scope Aircraft 只生成语义原计划 String；`scope=None` 对所有 Aircraft 全量生成。现有 FERRY option 可用，但不自动创建 FERRY、delay 或 route-change option。

**原因：**
必须先把 String legality 与 path completeness 对齐 brute-force oracle，再进入 Pricing 或同时扩大 Flight Option universe。

**影响：**
这是 explicit/full candidate generation，不计算 reduced cost、不读取 dual、不执行 Column Generation 或 Benders。完整性只相对于输入 Flight Options 成立。

**未来替换条件：**
Phase 5 通过后进入 Crew Pairing Generator；Flight Option generation、Pricing/CG 继续按独立阶段实现和验收。

---

## A-067 Candidate Universe Change Requires Scope Rebuild

**来源状态：** `implementation_safety_assumption`

**实现方式：**
`RecoveryScope` 只对构建它时传入的 `Scenario + RecoveryColumns` 候选宇宙闭包。任何 Flight Options、Aircraft Strings、Crew Pairings 或 Passenger Itineraries 发生变化后，进入下一生成器或 Scope-limited Solver 前必须重新调用 `build_recovery_scope(...)`。正式流水线为：Phase 5 generated Strings → rebuild Scope → Phase 6 generated Pairings → rebuild Scope → Phase 7 generated Itineraries → rebuild Scope → Phase 8。

**原因：**
新候选可能引入新的航班、资源 owner、共享 capacity/gate/seat 行和传播依赖；沿用旧 Scope 无法证明闭包安全。

**影响：**
Scope 不是可跨候选宇宙缓存的 Scenario 属性。Phase 6 benchmark 在生成 77 条 Strings 后和生成 374 条 Pairings 后各重建一次 Scope。

**未来替换条件：**
只有实现带候选宇宙指纹和严格增量闭包证明的 Scope cache 后，才允许复用计算结果。

---

## A-068 Phase 6 Crew Connection and Enumeration Test Profile

**来源状态：** `implementation_assumption`

**实现方式：**
版本化 `phase6_test_crew_pairing_generation_v1` 使用 `default_min_connection_minutes=0`、`max_duty_minutes=480`、`max_deadhead_legs=1`、`allow_deadhead=true`、`allow_idle=true`。零分钟 connection 用于保留 benchmark 已冻结的背靠背人工 Pairings；最多一个 DEADHEAD 是 Phase 6 v1 的显式枚举边界，使完整 linking model 可通过仓库的 size-limited solver gate。

**原因：**
当前 Schema 没有航司 Crew Connection、Duty/Rest 或 roster 规则真源，且无限制 DEADHEAD 组合会在 benchmark 产生 1,187 条 Pairings 及过多 linking constraints。

**影响：**
这些参数都是工程测试值，不是 FAR/CCAR 或任何真实航司标准。生成完整性仅相对于该配置和输入 Flight Options 成立。

**未来替换条件：**
接入正式 crew-rule profile 与不受 size limit 的求解环境后，发布新配置、取消或调整 DEADHEAD 上限，并重新执行 brute-force 与 Integrated 回归。

---

## A-069 Phase 6 Qualification and DEADHEAD Boundary

**来源状态：** `implementation_assumption`

**实现方式：**
Crew Schema 目前只提供单一 `rating`。OPERATE leg 要求 base Flight 的 `original_equipment == Crew.rating`；DEADHEAD 表示乘机调位，不执行航班，因此不检查执飞机型资质。两类 leg 都只能引用已有 revenue OPERATE Flight Option；CANCEL 和 FERRY option 不可作为机组飞行 segment。

**原因：**
该语义与现有 Column Validator、CRM operating/deadhead incidence 和 Integrated linking 一致，不虚构 rank、position、fleet family 或真实 qualification database。

**影响：**
当前模型仍是 aggregate single crew-unit coverage，不证明完整驾驶舱/客舱编制。DEADHEAD 不计入 operating coverage，并要求其 Flight Option 被 schedule 选中。

**未来替换条件：**
Schema 增加 crew role、rank、fleet qualification、seat/position requirement 后，版本化扩展 eligibility 与 coverage constraints。

---

## A-070 Phase 6 Single-duty and Rest Boundary

**来源状态：** `implementation_phase_boundary`

**实现方式：**
Phase 6 v1 每条生成 Pairing 恰含一个 duty。Duty duration 定义为首 leg departure 到末 leg arrival，并受配置上限约束；相邻 legs 检查 Station continuity 和 Min Connection。GROUND_TRANSFER、REST、多 duty、overnight rest 均不生成。

**原因：**
现有 Scenario/Crew Schema 无 sign-on、sign-off、reporting time、duty history、rest location 或跨日 roster 字段，无法可靠实现真实 duty/rest 法规。

**影响：**
480 分钟测试上限只能证明当前单 duty toy/benchmark 的工程合法性，不能声称生产级 crew legality。

**未来替换条件：**
增加 duty/rest 数据合同和规则真源后，用多 duty state network 替换此 v1 边界。

---

## A-071 Phase 6 Original, Idle, Scope and Explicit-generation Semantics

**来源状态：** `implementation_phase_boundary`

**实现方式：**
Scoped Crew 通过 crew-local DAG + DFS 执行 **full explicit enumeration within the Phase 6 v1 generation profile**；out-of-scope Crew 只保留由 original Flight Options 构成、且经独立 validator 验证的 original Pairing；`scope=None` 在相同 profile 内对全部 Crew 生成。仅当 Crew 起点等于 required terminal 且配置允许时生成显式零 leg idle Pairing。所有输出使用稳定 semantic key 与派生 ID，并再次通过 pure legality validator。

**原因：**
CRM/Integrated Oracle 对每个 Crew 恰选一条 Pairing，不能以“零条候选被选”表达 idle；Scope 外候选必须保持原计划冻结语义。

**影响：**
Phase 6 是 explicit candidate generation，不读取 dual、不计算 reduced cost、不做 Pricing/Column Generation/Benders。Airport/gate/passenger capacity 和 aircraft-string selection 仍由 Integrated Oracle 处理。

**未来替换条件：**
显式生成与 pricing oracle 在小规模实例上证明等价后，才可引入动态列生成。

---

## A-072 Phase 7 Passenger Generator Is an Engineering Extension

**来源状态：** `implementation_extension`

**实现方式：**
论文未提供当前仓库可直接照搬的完整 Passenger Itinerary generation algorithm。Phase 7 使用 passenger-local DAG + deterministic DFS，并以独立 permutation Oracle 验证 **full explicit enumeration within the Phase 7 v1 generation profile**。

**原因：**
必须先建立可审计的 passenger candidate universe，才能在后续 Benders/Pricing 中验证动态生成的正确性。

**影响：**
Phase 7 不读取 dual、不计算 reduced cost，不实现 Passenger Pricing、Column Generation 或 Benders，也不代表论文原算法的逐字复现。

**未来替换条件：**
后续 Passenger Pricing 必须先在相同小实例上与本显式 universe 对齐。

---

## A-073 Phase 7 MCT and Maximum-leg Test Profile

**来源状态：** `implementation_assumption`

**实现方式：**
版本化 `phase7_test_itinerary_generation_v1` 使用 `default_mct_minutes=0`、`max_flight_legs=3`、`allow_unserved=true`、`allow_surface=false`。零分钟 MCT 用于保留 benchmark 已冻结的背靠背人工 itinerary；toy Oracle 独立使用 30 分钟 MCT 测试 exact-boundary 与少 1 分钟的拒绝行为。

**原因：**
当前数据没有机场/航站楼/国内国际分类的真实 MCT 表；最大航段数是显式枚举的组合规模边界。

**影响：**
这些值不是航司生产规则。生成完整性只相对于输入 Flight Options 与 Phase 7 v1 profile 成立。

**未来替换条件：**
接入版本化真实 MCT 与 itinerary policy 后发布新 profile，并重跑 Oracle、PRM 与 Integrated 回归。

---

## A-074 Phase 7 Local Legality and Capacity Boundary

**来源状态：** `implementation_safety_assumption`

**实现方式：**
Generator 仅检查单条 itinerary 的 revenue option、O-D、时间、MCT、Recovery Horizon、最大航段数、重复 option/base flight 和 arrival delay。它不读取 passenger count 或 seat-capacity profile，不以容量删除局部合法 itinerary。

**原因：**
单列时空合法性不同于多个 Passenger Groups 同时选择后的共享容量可行性。后者继续由 PRM-C03 与 INTEGRATED-L05 处理。

**影响：**
Passenger count 大于某 option 的 test/residual capacity 时，该 itinerary 仍可能生成，但 Solver 不会在违反容量时选择它。Residual capacity 不代表 aircraft physical capacity。

**未来替换条件：**
只有在保持全局容量约束等价性的正式 pricing dominance 证明下，才可使用容量信息安全剪枝。

---

## A-075 Phase 7 Original, UNSERVED, Surface and Scope Semantics

**来源状态：** `implementation_phase_boundary`

**实现方式：**
每个 scoped Passenger Group 在 v1 profile 内生成全部合法 FLIGHT-only TRANSPORTED paths，并始终保留显式 UNSERVED；out-of-scope group 只保留通过业务字段解析和独立 validator 确认的 original itinerary，不能偷偷替换为 UNSERVED。`scope=None` 对全部 groups 生成。SURFACE Schema 保留，但 v1 generator 不创建，validator 在 profile 禁用时报告 `surface_disabled`。

**原因：**
PRM/Integrated Oracle 对每组恰选一条 itinerary；UNSERVED 必须是可审计候选。当前没有可靠的 surface O-D/time/cost/capacity 数据源。

**影响：**
Passenger Group 保持不可拆分 binary selection。生成 55 条 benchmark itineraries 后必须重新构建 canonical Scope，旧 Scope 仅能作为 generator owner 展开输入。

**未来替换条件：**
建立正式 surface network 或 split-flow 数学模型后，以新 Schema/profile 单独扩展。

---

## A-076 Phase 8 Fixed-Column Logic-Based Benders Partition

**来源状态：** `implementation_extension`

**实现方式：**
Phase 8 将 SRM 的 Schedule Flight Option `x` 保留在 Master，并增加非负连续变量 `theta[arm]`、`theta[crm]`、`theta[prm]`；ARM、CRM、PRM 继续使用现有 binary fixed-column MIP 和独立 diagnostics，不复制资源或旅客模型。

**原因：**
当前三个 recourse model 都是 MIP，现有 solver adapter 明确禁止从 MIP solution 读取 LP dual。因此 Phase 8 是 Logic-Based Fixed-Column Benders correctness baseline，不声称实现 classical LP-dual Benders cuts。

**影响：**
目标成本 ownership 保持 SRM → Master、ARM/CRM/PRM → 对应 recourse，不增加隐藏权重或重复成本。Integrated Oracle 继续作为 Ground Truth。

**未来替换条件：**
只有显式建立并验证连续 recourse relaxation、dual mapping 与强 cut 公式后，才可升级为 classical Benders。

---

## A-077 Phase 8 Exact-Schedule Cut Semantics

**来源状态：** `implementation_safety_assumption`

**实现方式：**
若任一 recourse MIP 对当前 schedule 不可行，加入只排除该 schedule 的 no-good cut。若 owner recourse 最优值为 `Qk`，加入 `theta_k >= Qk - M_k * delta(schedule, visited)` 的 conditional exact-recourse cut；cut ID 仅由 cut type、owner 和 canonical schedule signature 的 SHA-256 摘要生成。

**原因：**
这些 cut 在 binary recourse 下弱但精确，可对有限 Schedule universe 保证可审计的有限收敛，而无需伪造 dual multiplier。

**影响：**
算法目标是 correctness，不是大规模性能；可能访问多个 schedule 并重复求解 subproblem。visited schedule 之外的 recourse lower bound 仅为 0。

**未来替换条件：**
引入经证明有效的 combinatorial/dual strengthened cuts 后，必须继续对 tiny universe 做 exhaustive cut-validity 回归。

---

## A-078 Phase 8 Owner Big-M and Nonnegative Recourse

**来源状态：** `implementation_safety_assumption`

**实现方式：**
`M_ARM`、`M_CRM`、`M_PRM` 分别按当前 scope-restricted universe 中每个 Aircraft、Crew、Passenger Group 的最大候选 owner cost 求和，禁止 magic constant。每个 owner 必须至少有一条候选，且当前 canonical owner costs 必须非负。

**原因：**
每个 owner 恰选一条 fixed candidate，因此该和是任何可行 owner-selection recourse objective 的安全上界，并使非 visited schedule 上的 conditional cut 不强于 `theta >= 0`。

**影响：**
若未来允许负 recourse cost，现有 theta 下界与 Big-M 证明失效，必须重新设计。

**未来替换条件：**
成本合同改变或使用更强 schedule-dependent bound 时，需重新证明 upper-bound validity 并更新测试。

---

## A-079 Phase 8 Fixed Universe, Scope and Cut Lifetime

**来源状态：** `implementation_safety_assumption`

**实现方式：**
每次 solve 对 Scenario、Flight Options、Aircraft Strings、Crew Pairings、Passenger Itineraries、cost/capacity profile、scope 与 Benders config 生成稳定 fingerprint。cuts 只在该 immutable solve state 内使用，不跨 solve 持久化。Master 的 out-of-scope Flight 固定到语义 original option；subproblem 对 out-of-scope resource/passenger owner 使用 original-only 列视图。

**原因：**
candidate universe、scope 或 profile 变化会改变 recourse function 和 Big-M，旧 cut 不能自动视为有效。

**影响：**
Phase 8 不生成、删除或动态插入任何列；未来 Column Generation 不得直接复用本阶段 cuts。

**未来替换条件：**
只有后续阶段为动态列宇宙建立正式 cut validity/invalidation policy 后，才能安全复用。

---

## A-080 Phase 8 Bound, Status and Final Audit Rule

**来源状态：** `implementation_safety_assumption`

**实现方式：**
只有 OPTIMAL Master objective 才更新 LB；只有所有启用 recourse subproblem 都为 OPTIMAL 时才形成 UB。FEASIBLE/NO_SOLUTION/ERROR 等非终局状态均 ABORT，达到最大迭代返回 NOT_CONVERGED。全组件最优 incumbent 必须重新送入现有 Integrated diagnostics，检查 local、linking、scope 和 objective。

**原因：**
未证明最优的 MIP objective 不能生成 exact optimality cut，也不能作为合法 Benders bound。

**影响：**
`solver_status=OPTIMAL` 本身仍不足以验收；Phase 8 PASS 同时要求 LB/UB 收敛、Integrated audit 和 Oracle objective equality。

**未来替换条件：**
若支持 time-limit incumbent 或异步 subproblem，必须引入有证明的 bound/cut 处理规则，不能沿用当前 exact-cut 分支。

---

# 后续必须继续登记的假设

进入 Phase 2+ 后，至少还需要继续补充：

- 真实航空公司成本标定与正式货币单位；
- 生产级 Aircraft Turn Time 标定；
- Crew maximum duty / minimum rest；
- 生产级 Passenger MCT；
- Reserve Crew；
- Flight String Reduced Cost Mapping；
- Crew Pairing Reduced Cost；
- 正式/tail-level Gate Inventory；
- Diversion / Destination Change 的业务语义；
- Algorithm 1 / Algorithm 2 中的符号或实现歧义；
- Benders Cut 与动态列之间的有效性规则。

任何新增假设必须先记录，再实现。
