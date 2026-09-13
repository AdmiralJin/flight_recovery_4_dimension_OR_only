# Phase 3 Full Integrated Fixed-Column Oracle 实施计划

> 前置条件：Phase 2 已完成最终验收，SRM、ARM、CRM、PRM 四个独立 Fixed-Column 子模型及审计工作台均已冻结。  
> Phase 3 的唯一目标：**把 Schedule、Aircraft、Crew、Passenger 四个维度放入同一个 MIP，建立可人工核验、可独立审计的 Full Integrated Fixed-Column Oracle。**
>
> 本阶段不进入 Benders、不进入 Column Generation、不动态生成 Recovery Columns，也不加入南航特定业务规则。

---

# 1. Phase 3 v1 冻结边界

严格继承 `assumptions.md` A-056：

```text
Fixed Recovery Columns
+
phase2_test_costs_v1
+
TEST / RESIDUAL Passenger Capacity
+
PassengerCommodity group 不拆分
+
SRM Market-seat Proxy 暂时保留
```

并继续遵守：

```text
不增加模型级权重
不增加隐藏 epsilon
不增加人为 tie-breaking penalty
允许等价最优解
```

Phase 3 v1 的可行性与最优性只对当前：

```text
人工 Fixed Columns
测试成本
测试 residual capacity
当前 assumptions
```

成立，不代表真实航空公司生产最优。

---

# 2. Phase 3 与 Phase 2 的关键区别

Phase 2：

```text
SRM 先给出 schedule
        ↓
ARM / CRM / PRM 分别消费外生 schedule
```

Phase 3：

```text
Schedule
Aircraft
Crew
Passenger
```

全部在**同一个 MIP 内联合决定**。

因此 Phase 3 不再以：

```text
required_operated_option_ids
```

作为 ARM / CRM / PRM 的外生求解输入。

Phase 2 的 canonical handoff 继续保留给独立模型测试，但 Integrated Oracle 应通过显式 linking constraints 直接耦合四类变量。

---

# 3. 实施流程

建议 Phase 3 只分为五步，按顺序完成。

```text
3.1 Integrated Model Scaffold
        ↓
3.2 Cross-model Linking
        ↓
3.3 Integrated Objective + Audit
        ↓
3.4 Toy Oracle Tests
        ↓
3.5 Main Benchmark + Final Acceptance
```

每一步独立测试，不要一次性写完整模型后再排错。

---

# 4. Phase 3.1 Integrated Model Scaffold

新增核心模块，建议：

```text
backend/core/integrated_oracle.py
```

如确有必要可增加：

```text
backend/core/integrated_audit.py
backend/core/integrated_incidence.py
```

但优先复用 Phase 2 已验证代码，不要复制四套模型。

## 4.1 输入

Integrated Oracle 至少接受：

```text
Scenario
RecoveryColumns
FixedColumnCostConfig
PassengerCapacityProfile
SolverAdapter
```

可新增轻量：

```text
IntegratedRecoveryRequest
```

只包含必要 profile / scenario identity。

不得再传：

```text
required_operated_option_ids
```

因为 schedule 是 Integrated MIP 的内部变量。

## 4.2 决策变量

直接复用 Phase 2 语义：

```text
x_o ∈ {0,1}   Flight Option
y_s ∈ {0,1}   Aircraft String
z_p ∈ {0,1}   Crew Pairing
w_i ∈ {0,1}   Passenger Itinerary
```

不要重新定义含义相近但命名不同的第二套变量。

## 4.3 Local Constraint Blocks

复用 Phase 2 已验证的本地约束。

### SRM

```text
Flight Coverage
Strategic Flight
Arrival Capacity
Departure Capacity
Gate Inventory Proxy
Market-seat Proxy
```

### ARM

保留与单架飞机自身有关的：

```text
one String per Aircraft
Terminal
Maintenance
Fixed-column feasibility
```

### CRM

保留：

```text
one Pairing per Crew
Fixed-column legality
Terminal / ownership
```

### PRM

保留：

```text
one Itinerary / UNSERVED per Passenger Group
Fixed itinerary feasibility
```

Phase 2 中依赖外生 schedule 的 coverage / no-leakage 约束，不应原样照搬，统一在下一步改成 linking constraints。

---

# 5. Phase 3.2 Cross-model Linking

这是 Phase 3 的核心。

---

## 5.1 Schedule ↔ Aircraft

对每个 revenue `OPERATE` Flight Option `o`：

```text
Σ A_FS[o,s] · y_s = x_o
```

含义：

```text
x_o = 1
→ 必须由恰好一条 Aircraft String 执行

x_o = 0
→ 不允许任何 Aircraft String 执行该 alternate option
```

这统一替代 Phase 2 ARM 的：

```text
required option coverage = 1
non-required option coverage = 0
```

---

## 5.2 Schedule ↔ Crew

对每个 revenue `OPERATE` Flight Option `o`：

```text
Σ A_FC_operate[o,p] · z_p = x_o
```

含义：

```text
被执行航班必须有 operating crew
未执行 alternate option 不得有 operating crew
```

DEADHEAD 不得计入 operating coverage。

---

## 5.3 Deadhead ↔ Schedule

若 Crew Pairing `p` 中包含在 Flight Option `o` 上的 DEADHEAD：

```text
z_p ≤ x_o
```

含义：

```text
只有实际执行的航班才能承载 deadhead crew
```

禁止：

```text
deadhead on cancelled option
deadhead on unselected alternate option
```

---

## 5.4 Schedule ↔ Passenger

若 Passenger Itinerary `i` 使用 Flight Option `o`：

```text
w_i ≤ x_o
```

对 itinerary 中每个 Flight Segment 都建立。

含义：

```text
Passenger 只能使用实际执行的 Flight Option
```

Surface segment 不建立该约束，但继续依赖现有 itinerary semantic validation。

---

## 5.5 Seat Capacity ↔ Schedule

Phase 3 v1 继续使用当前外生：

```text
PassengerCapacityProfile
```

对每个相关 revenue Flight Option：

```text
Σ pax_count[g(i)] · A_PI[o,i] · w_i
≤
seat_capacity[o] · x_o
```

因此：

```text
x_o = 0
→ passenger load = 0
```

必须继续标记：

```text
TEST / RESIDUAL CAPACITY
NOT AIRCRAFT PHYSICAL CAPACITY
```

本阶段不实现：

```text
Aircraft String
→ equipment
→ physical seats
→ passenger capacity
```

该升级留到 Integrated Oracle 验证完成以后。

---

# 6. CANCEL / FERRY / UNSERVED 的联合语义

## CANCEL

SRM 仍保证一个 base flight：

```text
operate option
或
cancel option
```

恰选一个。

当选择 CANCEL：

```text
所有该航班 operate x_o = 0
```

通过 linking 自动得到：

```text
无 Aircraft coverage
无 Operating Crew coverage
Passenger 不可使用该 flight option
```

不需要额外人工同步三个子模型。

## FERRY

FERRY 继续只由 ARM Aircraft String 表达：

```text
不属于 revenue Flight Coverage
不建立 SRM revenue x_o
成本由 ARM owner 收取
```

不要在 Phase 3 v1 擅自改变 Ferry 对机场容量 / Gate 的 Phase 2 既有语义。

## UNSERVED

UNSERVED Passenger Itinerary：

```text
不引用 Flight Option
不消耗 Seat Capacity
```

继续由 PRM：

```text
Passenger Group exactly-one
```

选择 transported 或 unserved。

---

# 7. Phase 3.3 Integrated Objective

统一目标：

```text
min
SRM Cost
+ ARM Cost
+ CRM Cost
+ PRM Cost
```

严格按当前 canonical owner：

| Cost | Owner |
|---|---|
| flight delay | SRM |
| cancellation | SRM |
| origin change | SRM |
| destination change | SRM |
| aircraft reassignment | ARM |
| ferry | ARM |
| crew reassignment | CRM |
| deadhead | CRM |
| passenger delay | PRM |
| unserved passenger | PRM |

禁止重复计费。

禁止新增：

```text
SRM weight
ARM weight
CRM weight
PRM weight
epsilon
hidden tie-break cost
```

---

# 8. Integrated Objective Audit

新增统一 objective breakdown，例如：

```text
srm_total
arm_total
crm_total
prm_total
grand_total
```

必须独立验证：

```text
grand_total
=
srm_total
+ arm_total
+ crm_total
+ prm_total
```

并保留各子项明细。

不要直接相信 Solver objective。

---

# 9. Integrated Result 与 Audit

继续复用：

```text
ModelSolveResult
```

最小扩展：

```text
model = INTEGRATED
single_model_only = false
```

如当前 enum 不支持，做最小兼容扩展。

diagnostics 至少包含：

```text
selected_option_by_flight
selected_string_by_aircraft
selected_pairing_by_crew
selected_itinerary_by_group

srm_audit
arm_audit
crm_audit
prm_audit
cross_model_audit
objective_breakdown
```

---

# 10. Cross-model Independent Audit

求解后必须重新独立检查：

## Schedule / Aircraft

```text
selected operate option aircraft coverage = 1
unselected operate option aircraft coverage = 0
```

## Schedule / Crew

```text
selected operate option operating crew coverage = 1
unselected operate option operating crew coverage = 0
```

## Deadhead

```text
selected Pairing 的 deadhead Flight Option 必须实际执行
```

## Passenger

```text
selected transported Itinerary 的所有 Flight Segment 必须实际执行
```

## Seat

```text
seat load <= residual capacity
```

## Local constraints

继续复算：

```text
Airport Capacity
Gate Proxy
Terminal
Maintenance
Crew legality
Passenger group selection
```

Integrated `OPTIMAL` 本身不能作为验收依据。

---

# 11. Phase 3.4 Toy Oracle Tests

在主 benchmark 前先建立两个很小的可手算案例。

---

## 11.1 `toy_case_004`：Aircraft Coupling

目标：

> 证明联合模型能够放弃 SRM 单独最便宜、但 Aircraft 不可行的 schedule。

构造：

```text
Schedule A
SRM cost 更低
但没有合法 Aircraft String

Schedule B
SRM cost 略高
但 Aircraft feasible
```

预期：

```text
Integrated Oracle 选择 Schedule B
```

必须人工可计算。

---

## 11.2 `toy_case_005`：Passenger Coupling

目标：

> 证明 Passenger cost 可以反向影响 Schedule choice。

构造：

```text
Schedule A
Flight recovery cost 低
但 passenger delay / unserved cost 高

Schedule B
Flight recovery cost 略高
但 passenger service 更好
```

预期：

```text
Integrated Oracle 根据总成本选择全局更优方案
```

Seat Capacity 必须真正 active。

---

## 11.3 必测负例

至少：

```text
selected flight 无 Aircraft String
selected flight 无 Operating Crew
deadhead 引用未执行 option
Passenger itinerary 引用未执行 option
Passenger capacity 超限
所有 integrated alternatives 均不可行
```

---

# 12. Phase 3.5 Main Benchmark

使用：

```text
data/examples/phase1_benchmark_001.json
data/columns/phase1_benchmark_001_columns.json
data/costs/phase2_test_costs_v1.json
data/capacities/phase2_test_seat_capacity_v1.json
```

不要预设：

```text
Integrated optimum = SRM optimum 70
```

当前已经知道：

```text
SRM optimum 70
→ fixed-column ARM 可能 INFEASIBLE
```

Integrated Oracle 应自行找到：

```text
jointly feasible optimum
```

---

# 13. Manual Reference 作为 Feasible Upper Bound

Phase 1 Manual Reference 已分别通过 ARM / CRM / PRM。

Phase 3 应把它作为：

```text
known interpretable feasible candidate
```

进行完整联合 audit。

用当前 canonical cost functions 独立计算：

```text
manual_candidate_integrated_objective
```

若 Manual Reference 在 Integrated Model 中确实 feasible，则应验证：

```text
Integrated optimum objective
<=
Manual Reference candidate objective
```

不要提前硬编码具体数值，先由统一 cost audit 计算。

如果 Manual Reference 被 Integrated Model 判为 infeasible：

```text
先视为高优先级问题
```

必须检查：

```text
linking constraints
column incidence
capacity profile
local constraint reuse
```

不能直接接受。

---

# 14. Integrated Optimum 的比较原则

Integrated optimum 可以与 Manual Reference 不同。

优先比较：

```text
Feasibility
Objective
Flight recovery decisions
Cancellation
Airport capacity
Aircraft terminal / maintenance
Crew coverage
Passenger service
Seat capacity
Cost breakdown
```

不要求：

```text
完整 Aircraft Assignment Vector
完整 Crew Pairing Vector
完整 Passenger Itinerary Vector
```

与人工 Reference 完全一致。

允许等价最优解。

---

# 15. Fixed-column Coverage Gap

如果 Integrated Model 无可行解：

先判断是否来自：

```text
模型错误
或
当前人工 Columns 覆盖不足
```

不得为了通过测试：

```text
修改 cost
放松 constraint
偷偷改变 schedule
```

若确认只是明显缺少一个合理 fixed column：

1. 在报告中先记录 gap；
2. 仅补最小、人工可解释的 candidate；
3. 通过现有 semantic validator；
4. 明确记录该列为何新增；
5. 不引入自动 Generator。

---

# 16. 实现复用原则

优先复用 Phase 2：

```text
RecoveryIncidence
Gate Inventory Builder
Aircraft incidence
Crew incidence
Passenger incidence
Cost functions
Passenger Capacity validation
Semantic validators
SolverAdapter
ModelSolveResult
```

禁止把：

```text
srm.py
arm.py
crm.py
prm.py
```

整段复制进 `integrated_oracle.py`。

如现有代码无法复用：

> 抽取 shared helper / builder，再由独立模型和 Integrated Oracle 共用。

不得为了 Phase 3 破坏 Phase 2 regression。

---

# 17. 建议测试结构

新增：

```text
tests/unit/test_integrated_oracle.py
tests/regression/test_phase3_toy_case_004.py
tests/regression/test_phase3_toy_case_005.py
tests/regression/test_phase3_benchmark_001.py
```

如新增 shared incidence / audit：

```text
tests/unit/test_integrated_incidence.py
tests/unit/test_integrated_audit.py
```

最终：

```bash
python -m pytest -q
```

要求：

```text
0 failed
0 skipped
```

Phase 3 Gurobi integration 不得 skip。

---

# 18. Assumptions 管理

Phase 3 实施前先读取最新 `assumptions.md`。

A-056 是 Phase 3 v1 的总边界，不应重复创建同义 assumption。

只有出现新的、影响：

```text
Feasible Region
Objective
Cross-model semantics
```

的决定时才新增 assumption。

特别禁止静默改变：

```text
Market-seat Proxy
Residual Seat Capacity
Passenger Group indivisibility
Cost ownership
Tie-breaking policy
```

---

# 19. 本阶段明确不做

不得进入：

```text
Scope Limiting
Automatic Flight String Generator
Automatic Crew Pairing Generator
Automatic Passenger Itinerary Generator
Benders
Column Generation
Benders + Column Generation
Integrality / Branching extensions
South China Airlines business rules
Physical aircraft seat-capacity coupling
Production cost calibration
Solve UI
```

其中 Solve UI 可在 Integrated Oracle 稳定后单独接入。

---

# 20. Phase 3 验收标准

Phase 3 只有以下全部满足才 PASS：

- [ ] x / y / z / w 在同一 MIP
- [ ] SRM local constraints 正确复用
- [ ] ARM local constraints 正确复用
- [ ] CRM local constraints 正确复用
- [ ] PRM local constraints 正确复用
- [ ] Schedule ↔ Aircraft linking 正确
- [ ] Schedule ↔ Crew linking 正确
- [ ] Deadhead ↔ Schedule linking 正确
- [ ] Passenger ↔ Schedule linking 正确
- [ ] Seat Capacity 与 schedule 联动
- [ ] CANCEL 能自动切断 Aircraft / Crew / Passenger 使用
- [ ] Ferry 保持 ARM-owned 语义
- [ ] Integrated Objective 无重复计费
- [ ] Objective 四个 owner 分项可独立复算
- [ ] 无模型级权重 / hidden epsilon
- [ ] `toy_case_004` PASS
- [ ] `toy_case_005` PASS
- [ ] Manual Reference 在 Integrated Model 中可解释并完成 full audit
- [ ] `phase1_benchmark_001` 可求解或能明确证明 fixed-column coverage gap
- [ ] Integrated result 有独立 cross-model audit
- [ ] full pytest 0 failed
- [ ] full pytest 0 skipped
- [ ] Gurobi Integrated regression 实际执行
- [ ] assumptions / README / reproduction notes / Reproduction Plan 同步
- [ ] 未进入 Benders / CG / Generator

---

# 21. Codex Report

完成后新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase3_integrated_fixed_column_oracle_report.md
```

保持结构清楚，至少包括：

```text
1. Modified Files
2. Integrated Model Scope
3. Reused Phase 2 Components
4. Decision Variables
5. Local Constraint Blocks
6. Cross-model Linking
7. Integrated Objective
8. Cost Ownership Audit
9. toy_case_004
10. toy_case_005
11. Manual Reference Audit
12. phase1_benchmark_001 Result
13. Integrated Objective Breakdown
14. Cross-model Independent Audit
15. Test / Gurobi Result
16. New Assumptions
17. Known Limitations
18. Acceptance Checklist
19. Final Decision
20. Next Recommended Step
```

最终明确：

```text
Phase 3 PASS
```

或：

```text
Phase 3 NOT PASS
```

---

# 22. Phase 3 完成后的下一步

只有 Phase 3 PASS 后再进入项目既定路线：

```text
Phase 4 Scope Limiting
        ↓
Flight String Generator
        ↓
Crew Pairing Generator
        ↓
Passenger Itinerary Generator
        ↓
Fixed-column Benders
        ↓
Column Generation
        ↓
Benders + Column Generation
```

Phase 3 Integrated Oracle 将作为后续所有复杂算法的 Ground Truth。
