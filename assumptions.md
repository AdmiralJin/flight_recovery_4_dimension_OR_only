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
- Gate Inventory；
- Diversion / Destination Change 的业务语义；
- Algorithm 1 / Algorithm 2 中的符号或实现歧义；
- Benders Cut 与动态列之间的有效性规则。

任何新增假设必须先记录，再实现。
