# Phase 4 Scope Limiting 实施计划

> 实施状态（2026-09-14）：**Phase 4 PASS**。实现结果与主 benchmark 的 Full Scope 诊断见第 25 节。

> 前置条件：Phase 3 Full Integrated Fixed-Column Oracle 已 PASS。  
> 目标：根据直接扰动自动识别真正需要恢复优化的 Flight / Aircraft / Crew / Passenger 范围，并在不改变 Phase 3 最优目标的前提下减少自由决策范围。
>
> 核心验收：
>
> ```text
> OBJ_scope == OBJ_full
> ```
>
> 同时要求 Scope 相比 Full Instance 有实际缩减。

---

# 1. Phase 4 定位

项目总计划要求 Phase 4 实现 Scope Limiting，并依据论文 Appendix Algorithms 3–6，从：

```text
direct disruption
```

逐步得到：

```text
disruptable flights
disruptable aircraft
disrupted crew
disrupted passengers
```

传播逻辑：

```text
airport disruption
→ flight
→ aircraft
→ crew
→ additional flights
→ passenger connection
→ additional candidates
```

本阶段只做：

```text
Scope identification
+
Scope closure
+
Scope-limited Integrated Oracle
+
Full-vs-Scope Oracle validation
```

不做：

```text
Flight String Generator
Crew Pairing Generator
Passenger Itinerary Generator
Benders
Column Generation
真实航司业务规则扩展
Solve UI
```

---

# 2. 先核对论文 Algorithms 3–6

编码前，Codex 应使用项目采用的 Petersen et al. AIR 论文权威版本核对 Appendix Algorithms 3–6，并在最终报告中给出简短映射：

| Paper Algorithm | 本项目实现 |
|---|---|
| Algorithm 3 | ... |
| Algorithm 4 | ... |
| Algorithm 5 | ... |
| Algorithm 6 | ... |

要求：

- 能直接对应论文的部分按 `Paper-defined` 实现；
- 当前数据结构无法严格照搬的部分写入 `assumptions.md`；
- 不得仅凭项目计划或记忆声称“论文精确复现”。

---

# 3. 新增 Scope 数据结构

建议新增：

```text
backend/core/scope.py
```

建立只读、确定性的 `RecoveryScope`。

至少包含：

```text
direct_flight_ids

flight_ids
aircraft_ids
crew_ids
passenger_group_ids

flight_option_ids
aircraft_string_ids
crew_pairing_ids
passenger_itinerary_ids

propagation_reasons
iteration_count
```

`propagation_reasons` 必须能解释一个对象为什么进入 Scope，例如：

```text
F2
  DIRECT_DISRUPTION

AC1
  COVERS_SCOPED_FLIGHT:F2

F10
  CANDIDATE_STRING:AS_AC1_SWAP_F10

P4
  ITINERARY_USES_SCOPED_FLIGHT:F2
```

Scope 必须：

```text
deterministic
不修改输入
stable ordering
可独立测试
```

---

# 4. Direct Disruption Seed

第一步只识别直接受扰动航班。

当前 benchmark 的已知扰动为：

```text
airport = B
restriction_type = departure_capacity_reduction
[start_time, end_time)
```

因此 Phase 4 至少正式支持：

```text
departure_capacity_reduction
```

直接 Seed：

```text
原计划 departure airport == disruption.airport
AND
scheduled departure ∈ [start_time, end_time)
```

多个 disruption 取并集。

禁止硬编码 `F2/F5/F8` 等 ID。

如果出现当前未定义语义的 `restriction_type`：

```text
显式报 unsupported
```

不要静默猜测。

若仓库已有 Phase 0.5 的可靠 Direct Exposure / 时间区间 helper，应优先复用。

---

# 5. Scope 使用 Fixed-Point Closure

只传播一轮不够安全。

Phase 4 应不断传播，直到：

```text
本轮没有新增 Flight / Aircraft / Crew / Passenger
```

建议复用：

```text
RecoveryIndices
RecoveryIncidence
CrewRecoveryIncidence
PassengerRecoveryIncidence
GateInventoryData
```

不要重新复制一套 Flight/String/Pairing/Itinerary 关系解析逻辑。

---

# 6. Flight → Resource / Passenger

一个 Base Flight 进入 Scope 后：

1. 获取该 Flight 的所有合法 Flight Options；
2. 找出覆盖这些 options 的 Aircraft Strings；
3. 将对应 Aircraft owner 加入 Scope；
4. 找出 OPERATE / DEADHEAD 引用这些 options 的 Crew Pairings；
5. 将对应 Crew owner 加入 Scope；
6. 找出引用这些 options 的 Passenger Itineraries；
7. 将对应 Passenger Group 加入 Scope。

目的：

> 不仅考虑原计划资源，还覆盖当前 Fixed Columns 中允许的 reassignment、deadhead 和 reaccommodation。

---

# 7. Resource / Passenger → Additional Flights

当 Aircraft 进入 Scope：

```text
该 Aircraft 的全部 candidate Strings
→ 引用的 revenue Base Flights 加入 Scope
```

当 Crew 进入 Scope：

```text
该 Crew 的全部 candidate Pairings
→ OPERATE / DEADHEAD 引用的 revenue Base Flights 加入 Scope
```

当 Passenger Group 进入 Scope：

```text
该 Group 的全部 candidate Itineraries
→ Flight segments 对应 Base Flights 加入 Scope
```

FERRY：

```text
可以属于 scoped Aircraft String
但不是 revenue Base Flight
```

Surface passenger segment 同理。

---

# 8. 必须考虑共享约束传播

只按 Aircraft/Crew/Passenger 链传播仍可能漏掉 Integrated MIP 中的共享耦合。

## Airport Capacity

若 scoped Flight Options 与其他 Flight Options 共同出现在同一个：

```text
Arrival Capacity row
或
Departure Capacity row
```

这些 options 对应的 Base Flights 应进入 Scope。

优先复用当前 `RecoveryIncidence`。

## Gate Inventory

若 scoped options 与其他 options 共同参与同一 Gate checkpoint：

```text
相关 Base Flights 加入 Scope
```

优先复用现有 `GateInventoryData`。

## Passenger Seat Capacity

若不同 Passenger Groups 的候选 Itineraries 使用同一个 scoped Flight Option：

```text
相关 Passenger Groups 应进入 Scope
```

---

# 9. 传播直到闭包稳定

推荐流程：

```text
scope = direct_disruption_seed

repeat:
    old_scope = scope

    Flight
      → Aircraft / Crew / Passenger

    Aircraft
      → candidate Strings
      → additional Flights

    Crew
      → candidate Pairings
      → additional Flights

    Passenger
      → candidate Itineraries
      → additional Flights

    Capacity / Gate / Seat shared coupling
      → additional Flights / Passengers

until scope == old_scope
```

集合应单调扩张并最终稳定。

---

# 10. Scope Safety Invariants

进入 Solver 前独立检查：

```text
所有 direct disrupted flights ∈ scope
```

```text
scoped Aircraft 的 candidate String 引用 revenue Flight
→ 对应 Base Flight 必须 scoped
```

```text
scoped Crew candidate Pairing 引用 revenue Flight
→ 对应 Base Flight 必须 scoped
```

```text
scoped Passenger candidate Itinerary 引用 revenue Flight
→ 对应 Base Flight 必须 scoped
```

共享 capacity / gate 传播也必须闭包。

若不满足：

```text
ScopeBuildError
```

---

# 11. 第一版不要物理裁剪 Scenario / Columns

不要直接：

```text
删除 out-of-scope Flights
删除 out-of-scope Aircraft
删除 out-of-scope Crew
删除 out-of-scope Passengers
删除相关 Constraints
```

原因是当前 Integrated Oracle 仍包含：

```text
Airport Capacity
Gate Inventory
Terminal
Maintenance
Seat Capacity
```

等全局/边界约束。

过早物理裁剪容易改变数学语义。

---

# 12. Phase 4 v1：冻结 Scope 外决策

建议给 Phase 3 Integrated Oracle 增加可选：

```text
scope: RecoveryScope | None = None
```

行为：

```text
scope is None
→ 完全保持 Phase 3 Full Oracle
```

```text
scope provided
→ Scope 内变量自由
→ Scope 外 owner 固定到原计划 candidate
```

具体：

```text
out-of-scope Flight
→ original Flight Option = 1

out-of-scope Aircraft
→ original Aircraft String = 1

out-of-scope Crew
→ original Crew Pairing = 1

out-of-scope Passenger Group
→ original Passenger Itinerary = 1
```

可使用显式约束：

```text
SCOPE_FIX_FLIGHT
SCOPE_FIX_AIRCRAFT
SCOPE_FIX_CREW
SCOPE_FIX_PASSENGER
```

不要修改 Phase 3 原有约束公式。

---

# 13. Original Candidate Resolver 不得依赖 ID 命名

虽然当前数据存在：

```text
FO_*_ORIG
AS_*_ORIGINAL
CP_*_ORIGINAL
PI_*_ORIGINAL
```

Phase 4 不得依赖字符串命名。

应按语义唯一识别。

## Flight

```text
operation_type = OPERATE
change_types = [UNCHANGED]
route / scheduled times 与 Scenario Flight 一致
```

## Aircraft

Aircraft String 的 revenue legs 应与：

```text
Aircraft.original_rotation
```

对应的 original Flight Options 一致。

## Crew

Crew Pairing 的 OPERATE legs 应与：

```text
Crew.original_pairing
```

一致。

## Passenger

Passenger Itinerary 的 Flight segments 应与：

```text
PassengerCommodity.original_itinerary
```

一致。

若不存在或不唯一：

```text
显式报错
```

不要猜。

---

# 14. Scope Metrics

每次运行输出：

```text
total flights / scoped flights
total aircraft / scoped aircraft
total crew / scoped crew
total passenger groups / scoped passenger groups

total x/y/z/w candidates
free x/y/z/w candidates
fixed x/y/z/w candidates

scope iteration count
propagation reason counts
```

同时输出：

```text
free_binary_ratio
scoped_flight_ratio
```

Phase 4 不预设任意人为缩减百分比。

但 benchmark 至少应满足：

```text
Scope 非 Full Scope
free variables < full variables
```

否则需要解释为什么 Scope 没有实际缩减。

---

# 15. Full Oracle vs Scope Oracle

在完全相同：

```text
Scenario
Recovery Columns
Cost Profile
Passenger Capacity Profile
```

下分别运行：

```text
Full Integrated Oracle
Scope-limited Integrated Oracle
```

要求：

```text
status_full == OPTIMAL
status_scope == OPTIMAL
```

核心验收：

```text
isclose(OBJ_scope, OBJ_full)
```

使用项目统一 tolerance。

同时要求 Scope solution：

```text
all_constraints_satisfied = true
cross_model_audit PASS
objective independent audit PASS
```

---

# 16. 不要求 Assignment Vector 完全一致

核心要求：

```text
OBJ_scope == OBJ_full
```

不要求：

```text
完整 Aircraft assignment 一致
完整 Crew assignment 一致
完整 Passenger itinerary 一致
```

存在等价最优解时允许不同。

---

# 17. Benchmark

主要使用：

```text
phase1_benchmark_001
phase1_benchmark_001_columns
phase2_test_costs_v1
phase2_test_seat_capacity_v1
```

当前直接扰动：

```text
B airport
09:30–10:30
departure_capacity_reduction
```

Scope 必须由数据自动推导。

禁止在生产逻辑中直接写实体 ID 列表。

---

# 18. 测试

建议新增：

```text
tests/unit/test_scope.py
tests/regression/test_phase4_scope_benchmark_001.py
```

`test_scope.py` 至少覆盖：

1. direct departure disruption seed；
2. multiple disruptions union；
3. Flight → Aircraft；
4. Flight → Crew；
5. Flight → Passenger；
6. Aircraft candidate → additional Flight；
7. Crew candidate → additional Flight；
8. Passenger alternative → additional Flight；
9. Capacity shared-row propagation；
10. Fixed-point convergence；
11. propagation reason deterministic；
12. unsupported restriction type 显式失败；
13. original candidate resolver 唯一性；
14. broken closure 被拒绝。

Regression 必须比较：

```text
Full Oracle objective
vs
Scope Oracle objective
```

并确认 Scope 有实际缩减。

---

# 19. 建议增加一个小型 Scope Toy Case

如主 benchmark 不够直观，可新增：

```text
toy_case_006_scope
```

只证明：

```text
一个直接扰动
→ 一个 Aircraft
→ 一个 downstream Flight
→ 一个 Passenger connection
```

同时保留一组完全无关资源。

要求：

```text
Scope 正确传播
无关资源保持 out-of-scope
OBJ_scope == OBJ_full
```

---

# 20. 若 Objective 不相等

如果：

```text
OBJ_scope != OBJ_full
```

禁止：

```text
硬编码 benchmark entity
修改 cost
放松 Integrated constraints
直接把 Scope 改成 Full Scope
```

应检查遗漏传播关系，优先检查：

```text
Aircraft reassignment
Crew deadhead / reassignment
Passenger alternative itinerary
Airport capacity shared row
Gate inventory shared checkpoint
Seat-capacity competition
```

每次扩大 Scope 都必须有可解释 dependency reason。

---

# 21. Phase 4 v1 不要求真正删变量

当前最安全验收指标：

```text
free decision candidates 减少
+
OBJ_scope == OBJ_full
```

完成并验证后，如确有必要，再单独做：

```text
Phase 4.2 Reduced Materialization
```

即真正生成物理缩减的 Scenario / Columns。

不要在 Oracle 等价验证前同时重写：

```text
Scenario
Columns
Capacity
Gate boundary
Objective constants
```

---

# 22. 文档与 Assumptions

完成后更新：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

至少明确：

```text
Phase 4 Scope 只对当前 Fixed-Column universe 保证
Scope 外 decisions 固定到原计划
Scope closure 包含 resource / passenger / shared-capacity dependencies
```

论文 Algorithms 3–6 与当前数据结构存在差异时：

```text
单独登记 assumption
```

---

# 23. Codex Report

新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase4_scope_limiting_report.md
```

至少包含：

```text
1. Paper Algorithms 3–6 Mapping
2. Modified Files
3. Direct Disruption Seed
4. Scope Propagation / Fixed Point
5. Scope Safety Invariants
6. Original Candidate Resolver
7. Scope Metrics
8. Full Oracle Result
9. Scope Oracle Result
10. OBJ_scope vs OBJ_full
11. Tests
12. New Assumptions
13. Known Limitations
14. Acceptance Checklist
15. Final Decision
```

最终明确：

```text
Phase 4 PASS
```

或：

```text
Phase 4 NOT PASS
```

---

# 24. Phase 4 Acceptance Criteria

- [x] 已核对论文 Appendix Algorithms 3–6，并记录项目映射
- [x] 独立 Scope Engine 已实现
- [x] Direct disruption 不靠硬编码 entity ID
- [x] Flight / Aircraft / Crew / Passenger 可递归传播
- [x] Capacity / Gate / Seat 共享耦合不会遗漏
- [x] Scope 使用 Fixed-Point Closure
- [x] 每个 scoped entity 有可解释 propagation reason
- [x] Scope Safety Invariants PASS
- [x] Original candidate resolver 不依赖 `*_ORIGINAL` 命名
- [x] `scope=None` 时 Phase 3 行为完全不变
- [x] Scope 外 decisions 正确冻结到原计划
- [x] Scope solution 通过 Phase 3 全部 independent audit
- [x] `OBJ_scope == OBJ_full`（统一 tolerance）
- [x] Scope 相比 Full 有实际缩减（由 `toy_case_006_scope` 验收）
- [x] unit / negative / regression tests PASS
- [x] full pytest 0 failed
- [x] full pytest 0 skipped
- [x] Phase 3 regression 无回归
- [x] assumptions / README / plan / notes 已同步
- [x] 未进入 Generator / Benders / Column Generation

Phase 4 PASS 后再进入：

```text
Phase 5 Flight String Generator
```

Phase 4 产生的 Recovery Scope 将成为后续各类 Candidate Generator 的输入边界。

---

# 25. 实施结果（2026-09-14）

实现入口：

```text
backend/core/scope.py
build_recovery_scope(...)
solve_integrated_fixed_column_oracle(..., scope=scope)
```

Oracle 结果：

```text
toy_case_006_scope:
  status_full  = OPTIMAL
  status_scope = OPTIMAL
  OBJ_full     = 2040
  OBJ_scope    = 2040
  free binary candidates = 10 / 14

phase1_benchmark_001:
  status_full  = OPTIMAL
  status_scope = OPTIMAL
  OBJ_full     = 18080
  OBJ_scope    = 18080
  strict fixed-point closure = Full Scope
```

`phase1_benchmark_001` 的三个 direct flights 为 `F2/F5/F8`，但这些 ID 是测试断言结果，不存在于生产 Scope 逻辑。它们经 aircraft/crew/passenger candidates、airport capacity 与累计 gate checkpoint 连通全部实体，因此 Full Scope 是安全闭包的真实结果。计划第 14 节允许在无缩减时解释原因；实际缩减由包含完全独立组件的 `toy_case_006_scope` 验收。

完整测试：

```text
293 passed
0 failed
0 skipped
```

最终决定：

```text
Phase 4 PASS
```
