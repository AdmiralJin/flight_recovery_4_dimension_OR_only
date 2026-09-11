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
论文实现使用 CPLEX 12.1，但本项目后续明确需要稳定访问 MIP status、objective bound、gap、LP dual 和 reduced cost。具体 Python Solver 及工程抽象不属于论文算法定义。

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

# 后续必须继续登记的假设

进入 Phase 2+ 后，至少还需要继续补充：

- Integrated Master Objective 与 tie-breaking；
- 真实航空公司成本标定与正式货币单位；
- Aircraft Turn Time；
- Crew maximum duty / minimum rest；
- Passenger MCT；
- PRM `s_i` domain；
- Seat Capacity 解释；
- Reserve Crew；
- Flight String Reduced Cost Mapping；
- Crew Pairing Reduced Cost；
- 正式/tail-level Gate Inventory；
- Diversion / Destination Change 的业务语义；
- Algorithm 1 / Algorithm 2 中的符号或实现歧义；
- Benders Cut 与动态列之间的有效性规则。

任何新增假设必须先记录，再实现。
