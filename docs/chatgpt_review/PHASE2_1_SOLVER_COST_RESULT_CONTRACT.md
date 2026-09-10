# Phase 2.1 实施说明：Solver / Cost / ModelResult Contract

> 项目：`AdmiralJin/flight_recovery_4_dimension_OR_only`  
> 当前状态：Phase 2.0 Incidence / Index Builder 已完成。  
> 下一阶段：**Phase 2.1 — Solver / Cost / ModelResult Contract**。  
> 本阶段的目标是冻结后续 SRM / ARM / CRM / PRM 共用的求解接口、成本口径和结果结构。  
> **本阶段不实现 SRM、ARM、CRM、PRM，不建立任何业务优化模型。**

---

# 1. 为什么必须先做 Phase 2.1

Phase 2.0 已经把：

```text
Scenario
+
Recovery Columns
```

转换为稳定的 Index 与 Incidence。

下一步如果直接开始 SRM，会立即遇到三个尚未统一的问题：

```text
1. Solver 怎么调用、状态怎么解释？
2. Objective 中各种成本的单位和来源是什么？
3. Solver 输出与 RecoveryExpected 有什么区别？
```

如果这三件事不先固定，四个子模型会各自形成不同接口，后续 Phase 3 Integrated Oracle、Benders 和 Column Generation 都会被迫返工。

因此 Phase 2.1 只建立公共 Contract。

---

# 2. 本阶段最终要形成的三类 Contract

```text
A. Solver Contract
   统一求解器调用和状态映射

B. Cost Contract
   统一成本项、单位、来源和版本

C. Model Result Contract
   统一模型求解结果，不复用 RecoveryExpected
```

完成后：

```text
Phase 2.2 SRM
Phase 2.3 ARM
Phase 2.4 CRM
Phase 2.5 PRM
```

必须全部复用这些 Contract。

---

# 3. Solver 选择原则

推荐：

```text
Primary Solver = Gurobi
```

原因不是单纯“求解速度快”，而是后续项目明确需要：

```text
LP duals
reduced costs
LP relaxation
MIP status
objective bound
MIP gap
Benders
Column Generation
Pricing
```

因此求解器必须可靠暴露这些信息。

但业务代码不得直接散落：

```python
import gurobipy as gp
```

后续模型只能依赖统一 Solver Adapter。

---

# 4. 推荐目录

建议新增：

```text
backend/
├── solver/
│   ├── __init__.py
│   ├── base.py
│   └── gurobi.py
│
├── schemas/
│   └── model_result.py
│
└── config/
    └── costs.py

data/
└── costs/
    └── phase2_test_costs_v1.json

tests/
└── unit/
    ├── test_solver_contract.py
    ├── test_gurobi_adapter.py
    ├── test_cost_config.py
    └── test_model_result.py
```

具体文件名可以略调，但三种职责必须分开。

---

# 5. `SolverAdapter` 的职责

建议在：

```text
backend/solver/base.py
```

定义统一 Protocol / ABC。

后续 SRM/ARM/CRM/PRM 不应该知道 Gurobi API 细节。

至少统一以下能力：

```text
create model
add variable
add linear constraint
set objective
solve
read variable value
read objective
read status
read runtime
read bound / gap
read LP dual
read reduced cost
```

Phase 2.1 不需要做复杂建模 DSL。

目标是：

> 能用统一接口建立和求解一个最小 LP/MIP，并可靠取得后续算法必需信息。

---

# 6. Solver Capability 必须显式声明

建议 Adapter 暴露能力，例如：

```text
supports_mip
supports_lp_duals
supports_reduced_costs
supports_mip_gap
supports_objective_bound
```

不要默认所有 Solver 都具备相同能力。

后续 Column Generation 依赖：

```text
dual
reduced cost
```

如果 Adapter 不支持，必须 fail fast。

---

# 7. Solver Status Contract

不要把 Gurobi 原始整数 Status 传播到业务层。

建议统一枚举：

```text
OPTIMAL
FEASIBLE
INFEASIBLE
UNBOUNDED
INFEASIBLE_OR_UNBOUNDED
NO_SOLUTION
ERROR
```

同时单独保留：

```text
termination_reason
raw_status
```

用于诊断。

---

# 8. `FEASIBLE` 与 `OPTIMAL` 必须分开

后续 MIP 可能因为：

```text
time limit
node limit
manual interruption
```

得到一个可行 incumbent，但未证明最优。

这种情况：

```text
status = FEASIBLE
```

不能标成：

```text
OPTIMAL
```

同时记录：

```text
objective_value
best_bound
mip_gap
termination_reason
```

---

# 9. `INFEASIBLE` 结果不能伪造 Solution

如果模型不可行：

```text
status = INFEASIBLE
```

则：

```text
selected_variables
objective_value
recovery_solution
```

允许为空 / `null`。

这也是为什么不能复用当前 `RecoveryExpected`。

---

# 10. LP Dual 与 Reduced Cost

Phase 2.1 必须用最小 LP 测试证明：

```text
Adapter 能读取 constraint dual
Adapter 能读取 variable reduced cost
```

不要等到 Column Generation 阶段才发现 Solver Contract 不支持。

测试应使用一个解析解明确的小 LP，手工验证：

```text
objective
primal values
dual values
reduced costs
```

---

# 11. MIP Contract Smoke Test

再建立一个极小 Binary MIP：

```text
2–3 variables
少量 constraints
```

验证：

```text
status == OPTIMAL
objective 正确
selected variable 正确
runtime 可读取
best bound 可读取
gap 可读取
```

该测试只是 Solver Contract Test，不属于 SRM。

---

# 12. Solver 日志

统一至少记录：

```text
solver_name
solver_version
model_name
status
raw_status
termination_reason
runtime_seconds
objective_value
best_bound
mip_gap
```

未来再增加：

```text
node_count
simplex_iterations
barrier_iterations
```

当前可作为 optional diagnostics。

---

# 13. `RecoveryExpected` 的职责保持不变

当前：

```text
RecoveryExpected
```

继续表示：

```text
Manual Reference
Oracle Fixture
Regression Ground Truth
```

不要修改其角色。

后续 Solver 输出必须使用独立：

```text
ModelSolveResult
```

---

# 14. `ModelSolveResult` 推荐结构

建议：

```text
model_name
scenario_id
status

objective_value
best_bound
mip_gap
runtime_seconds

selected_variables
continuous_variables

solver_name
solver_version
raw_status
termination_reason

diagnostics
```

其中：

```text
selected_variables
```

建议为：

```text
variable_name → value
```

或者更结构化的 typed decisions。

Phase 2.1 先保证通用结果结构，具体 SRM Decision Result 可在 Phase 2.2 扩展。

---

# 15. 不要在 Model Result 中直接塞完整 Integrated Recovery

Phase 2.2–2.5 都是单独子模型。

例如 SRM 输出只代表：

```text
schedule decision
```

不代表完整：

```text
aircraft
crew
passenger
```

因此 Phase 2.1 的 `ModelSolveResult` 应保持模型中立。

完整：

```text
RecoveredFlight
RecoveredAircraft
RecoveredCrew
RecoveredPassenger
```

应留到 Phase 3 Integrated Oracle 的结果层设计。

---

# 16. Cost Contract 的核心原则

成本必须满足：

```text
名称稳定
单位明确
来源明确
版本明确
模型使用范围明确
```

不得在模型代码中散落：

```python
1000
50
0.1
```

这种 Magic Number。

所有成本统一从：

```text
FixedColumnCostConfig
```

读取。

---

# 17. 成本来源优先级

每个成本项必须标记来源。

优先级：

```text
1. Petersen et al. (2010) 明确定义或可直接推导
2. 论文引用的数据 / 参数来源
3. 为复现所需的透明 Implementation Assumption
4. 后续 Airline-specific Business Cost
```

当前 Phase 2 只能使用：

```text
1–3
```

不要提前混入南航真实业务成本。

---

# 18. 不要为匹配 Manual Reference 反向调成本

禁止：

```text
先要求 Solver 必须返回 80-minute Reference
↓
再调整成本直到它返回该方案
```

正确流程：

```text
先冻结透明成本
↓
求解
↓
比较 Manual Reference
```

如果 Solver 找到更低成本的合法方案：

> 优先检查人工 Reference 是否本来就不是最优。

---

# 19. 推荐 `FixedColumnCostConfig`

建议至少定义：

```text
flight_delay_per_minute
flight_cancellation
aircraft_reassignment
crew_reassignment

passenger_delay_per_pax_minute
unserved_passenger

origin_change
destination_change

ferry_per_minute
deadhead_per_minute
```

必要时再增加：

```text
strategic_flight_penalty
market_penalty
```

但必须有论文或实现逻辑依据。

---

# 20. 成本单位

必须明确写在 Schema / 文档中。

建议统一使用：

```text
abstract cost units
```

或：

```text
monetary-equivalent test units
```

只要尚未完成真实业务成本标定，就不要声称：

```text
USD
CNY
```

除非论文参数本身明确以货币计。

例如：

```text
flight_delay_per_minute
=
cost unit / flight-minute
```

```text
passenger_delay_per_pax_minute
=
cost unit / passenger-minute
```

---

# 21. 成本配置必须版本化

建议：

```text
phase2_test_costs_v1.json
```

至少包含：

```text
schema_version
cost_profile_id
source
units
coefficients
notes
```

例如：

```json
{
  "schema_version": "1.0.0",
  "cost_profile_id": "phase2_test_v1",
  "source": "paper_and_explicit_implementation_assumptions",
  "units": "abstract_cost_units",
  "coefficients": {}
}
```

不要在多个 test fixture 中复制一套系数。

---

# 22. Phase 2.1 不应随意填成本数值

本阶段需要：

1. 先检查论文当前已复现的 Objective 定义；
2. 能从论文确定的，按论文登记；
3. 论文缺失的，写入 `assumptions.md`；
4. 再建立唯一 canonical test-cost file。

如果某成本目前无法严谨确定：

```text
不要猜一个数字然后继续
```

应明确记录：

```text
unresolved
```

并将其作为进入对应模型前的 blocker。

---

# 23. 但 Phase 2.2 前必须有可执行成本

Phase 2.1 的最终验收不能停在：

```text
成本字段定义好了，但是全部 null
```

进入 SRM 前，SRM 所需成本必须有实际 test values。

ARM/CRM/PRM 尚未进入时，可以：

```text
字段已定义
值可延后到各自模型开始前最终确认
```

但更推荐 Phase 2.1 一次冻结完整 test profile。

---

# 24. Cost Config 的 Pydantic 校验

至少要求：

```text
所有成本 >= 0
```

如果某些模型允许负奖励，必须显式定义，不要默认允许。

同时拒绝：

```text
NaN
Infinity
未知字段
```

---

# 25. Cost Components 与 Columns 中现有 `cost_components`

当前 Columns 里存在：

```text
cost_components
```

但很多是空对象。

Phase 2.1 不应自动把所有最终成本写回每条 Column JSON。

推荐职责：

```text
Columns
=
物理 / 候选路径信息

CostConfig
=
全局成本参数

Cost Evaluation
=
根据 Column 与 Scenario 动态计算 cost
```

以后可缓存，但不要把同一成本逻辑复制进数据文件。

---

# 26. 推荐 Cost Evaluator 接口

Phase 2.1 可定义纯函数接口，但不要实现所有模型成本。

例如：

```python
def flight_option_cost(
    scenario: Scenario,
    option: FlightOption,
    costs: FixedColumnCostConfig,
) -> float:
    ...
```

```python
def aircraft_string_cost(...)
```

```python
def crew_pairing_cost(...)
```

```python
def passenger_itinerary_cost(...)
```

如果当前信息不足，可先只定义 Contract 和最小通用部分。

不要提前实现论文未核实的复杂成本。

---

# 27. 容易重复计费的逻辑

后续 Integrated Model 最容易出现：

```text
同一个 disruption cost 被 SRM 和 ARM 重复计算
```

因此 Phase 2.1 必须明确成本归属。

建议原则：

```text
Flight delay / cancel
→ SRM

Aircraft reassignment / ferry
→ ARM

Crew reassignment / deadhead
→ CRM

Passenger delay / unserved / reaccommodation
→ PRM
```

如果论文 Objective 的实际分配不同，以论文为准。

关键是：

> 一个成本项只能有一个 canonical owner，避免 Phase 3 合并时重复计费。

---

# 28. Route Change Cost

`origin_change` / `destination_change` 当前 Columns 可以表达。

但是否进入：

```text
SRM
ARM
```

必须在 Phase 2.1 明确。

推荐把它视为：

```text
flight recovery decision cost
```

由 SRM 管理，除非论文模型明确采用其他结构。

---

# 29. Ferry Cost

建议：

```text
ARM
```

负责。

原因：

Ferry 是 Aircraft Recovery Movement。

建议至少支持：

```text
ferry_per_minute
```

以后可扩展：

```text
fuel / distance / airport fee
```

Phase 2 不需要真实业务精度。

---

# 30. Deadhead Cost

建议由：

```text
CRM
```

负责。

注意：

Deadhead：

```text
不产生 operating flight coverage
```

但会产生：

```text
Crew movement
Cost
```

以后还可能占 Passenger Seat。

Seat coupling 留到 Integrated Model / PRM 设计时处理。

---

# 31. Passenger Reaccommodation Cost

建议优先使用：

```text
arrival-delay cost
+
unserved penalty
```

是否额外增加：

```text
itinerary-change fixed penalty
```

必须有明确依据。

不要为了让 P4→F8 看起来“贵/便宜”随意增加 penalty。

---

# 32. Phase 2.1 的 `assumptions.md` 更新

至少新增/确认：

```text
Solver choice
Solver abstraction boundary
Solver status mapping

Cost units
Cost profile source
Cost ownership by model
Any paper-missing coefficient assumptions

RecoveryExpected vs ModelSolveResult
```

所有未由论文明确给出的成本必须标记：

```text
Implementation Assumption
```

---

# 33. 推荐测试：ModelSolveResult

至少覆盖：

## OPTIMAL

允许：

```text
objective
bound
gap
selected variables
```

完整存在。

## FEASIBLE

允许：

```text
objective
bound
gap > 0
termination_reason = time_limit 等
```

## INFEASIBLE

要求：

```text
objective_value = null
selected_variables = {}
```

## UNBOUNDED

同样不能伪造可行 Solution。

---

# 34. 推荐测试：Cost Config

至少：

- 正常加载 canonical test profile；
- unknown field rejected；
- negative coefficient rejected；
- NaN / Inf rejected；
- missing required coefficient rejected；
- serialization round-trip。

---

# 35. 推荐测试：Solver Adapter LP

构造一个手工可解 LP。

验证：

```text
status
objective
primal solution
dual
reduced cost
```

全部与解析答案一致。

重点是：

> 不只测试 Solver “能跑”。

---

# 36. 推荐测试：Solver Adapter MIP

构造一个手工可解 Binary MIP。

验证：

```text
OPTIMAL
selected binary variables
objective
best bound
mip gap
runtime
```

---

# 37. 无 Solver / 无 License 时的处理

不要把：

```text
import error
license error
```

伪装成：

```text
INFEASIBLE
```

这属于：

```text
ERROR
```

并保留：

```text
termination_reason
diagnostics
```

测试层面：

- Contract / Result / Cost tests 必须不依赖有效商业 License；
- 实际 Gurobi integration test 若环境不可用，应明确 skip 原因；
- 不得把 skip 伪装成 PASS。

---

# 38. Phase 2.1 不修改 `/api/solve`

本阶段仍不启用真正业务求解 API。

保持当前安全边界。

原因：

目前只有 Solver Contract，没有 SRM/ARM/CRM/PRM Model。

---

# 39. Phase 2.1 不修改 Frontend

不要启用：

```text
Recovered Plan
```

不要显示：

```text
optimization result
```

因为尚无正式模型。

---

# 40. Phase 2.1 不修改 Manual Expected

不要把：

```text
phase1_benchmark_001_expected.json
```

中的：

```text
manual_reference
feasible
```

改成：

```text
optimal
```

Phase 2.1 只是定义模型求解基础设施。

---

# 41. 本阶段禁止事项

不要实现：

```text
SRM equations
ARM equations
CRM equations
PRM equations

Integrated MIP

Benders
Column Generation
Pricing
Automatic String Generation
Automatic Pairing Generation
```

不要为了测试 Solver Adapter 建立“迷你 SRM”。

只使用数学意义明确的通用 LP/MIP smoke model。

---

# 42. 推荐实施顺序

## Step 1

审阅：

```text
requirements.txt
pyproject.toml
```

加入 Solver Dependency 和必要配置。

---

## Step 2

建立：

```text
backend/solver/base.py
```

冻结 Solver Adapter Contract。

---

## Step 3

建立：

```text
backend/solver/gurobi.py
```

实现 Primary Adapter。

---

## Step 4

建立：

```text
backend/schemas/model_result.py
```

冻结 Result Contract。

---

## Step 5

建立：

```text
backend/config/costs.py
```

和：

```text
data/costs/phase2_test_costs_v1.json
```

---

## Step 6

核对论文 Objective / Cost Definitions。

更新：

```text
assumptions.md
reproduction_notes.md
```

必要时更新总计划。

---

## Step 7

增加：

```text
Solver LP smoke test
Solver MIP smoke test
ModelResult tests
CostConfig tests
```

---

## Step 8

完整运行：

```bash
python -m pytest
```

Phase 0–2.0 全部不能回归。

---

# 43. Phase 2.1 完成标准

只有全部满足才可标：

```text
Phase 2.1 PASS
```

## Solver

- [ ] Solver Adapter 已定义；
- [ ] Gurobi Adapter 已实现；
- [ ] Solver 原始状态不泄漏到业务层；
- [ ] OPTIMAL / FEASIBLE / INFEASIBLE / UNBOUNDED / ERROR 区分正确；
- [ ] Objective 可读取；
- [ ] Bound / Gap 可读取；
- [ ] Runtime 可读取；
- [ ] LP Dual 可读取；
- [ ] Reduced Cost 可读取；
- [ ] integration smoke tests 有解析答案。

## Result

- [ ] `ModelSolveResult` 独立于 `RecoveryExpected`；
- [ ] INFEASIBLE 不要求虚假 Solution；
- [ ] Solver metadata / diagnostics 可记录；
- [ ] serialization round-trip PASS。

## Cost

- [ ] Cost Config 集中管理；
- [ ] 单位明确；
- [ ] 来源明确；
- [ ] 成本所有权明确；
- [ ] 无散落 Magic Numbers；
- [ ] canonical test cost profile 存在；
- [ ] 进入 SRM 所需成本已具备实际 test values；
- [ ] 所有 Implementation Assumptions 已登记。

## Regression

- [ ] Phase 1 / Phase 2.0 tests 无回归；
- [ ] 全部新测试通过。

---

# 44. Phase 2.1 完成后的下一步

进入：

```text
Phase 2.2 — Fixed-Column SRM
```

Phase 2.2 才第一次建立真正业务优化模型。

输入：

```text
Validated Scenario
Validated Recovery Columns
RecoveryIndices
RecoveryIncidence
FixedColumnCostConfig
SolverAdapter
```

输出：

```text
ModelSolveResult
```

然后用人工可解释案例验证：

```text
Flight Option Selection
Cancellation
Airport Capacity
SRM Objective
```

---

# 45. Codex 最终报告要求

报告放到：

```text
docs/codex_reports/
```

至少写：

```text
1. Baseline commit
2. Modified files
3. Solver selected and version
4. SolverAdapter API
5. Status mapping
6. LP dual / reduced-cost verification
7. ModelSolveResult design
8. Cost profile and units
9. Cost-source classification
10. assumptions.md updates
11. Tests added
12. pytest result
13. Skipped integration tests, if any, and exact reason
14. Whether Phase 2.1 PASS
15. Exact blockers, if not PASS
16. Next step: Phase 2.2 Fixed-Column SRM
```

---

# 46. 最终验收模板

全部满足时才报告：

```text
Phase 2.1 PASS

Solver Contract:
- primary solver: PASS
- normalized status mapping: PASS
- objective / bound / gap / runtime: PASS
- LP dual access: PASS
- reduced-cost access: PASS

Model Result Contract:
- RecoveryExpected kept as oracle only: PASS
- ModelSolveResult added: PASS
- infeasible result semantics: PASS

Cost Contract:
- canonical cost profile: PASS
- units documented: PASS
- sources documented: PASS
- model ownership documented: PASS
- assumptions registered: PASS

Tests:
- LP analytical smoke test: PASS
- MIP analytical smoke test: PASS
- result-schema tests: PASS
- cost-config tests: PASS
- full pytest: PASS

Next:
Phase 2.2 — Fixed-Column SRM
```

如果 Cost / Solver 任何核心 Contract 尚未冻结：

```text
Phase 2.1 NOT COMPLETE
```

不得直接进入 SRM。
