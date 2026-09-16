# Phase 8 Closeout & Phase 9 Aircraft String Column Generation Plan

## 1. Phase 8 Review Conclusion

**Phase 8 可以收尾并合并。未发现阻断性问题。**

当前 `feature/phase-8` 已完成并验证：

```text
SRM x + thetaA/thetaC/thetaP Master
        ↓
existing ARM / CRM / PRM exact MIP recourse
        ↓
exact-schedule no-good feasibility cuts
+
conditional exact-recourse owner Big-M cuts
```

关键结果：

```text
toy_case_010:
Benders objective = Integrated objective = 220

toy_case_004 / toy_case_005:
Benders objective = Integrated objective

toy_case_006_scope:
Full Benders = Full Integrated
Scope Benders = Scope Integrated
Scope fix audit = PASS

phase1_benchmark_001:
iterations = 8
unique cuts = 17
LB = 18080
UB = 18080
Benders objective = Integrated Oracle objective = 18080
Integrated audit = PASS
```

Phase 8 正确保持了以下边界：

- candidate universe 在一次 Benders solve 内冻结；
- ARM / CRM / PRM 仍为现有 exact binary MIP；
- 不把当前 Logic-Based cuts 表述为 classical LP-dual Benders；
- Full 与 canonical RecoveryScope 均支持；
- 最终 incumbent 由现有 Integrated diagnostics 独立复算；
- 非 optimal Master / Subproblem 不生成错误 bound/cut；
- max-iteration 不伪装为 `OPTIMAL`。

Phase 8 作为 correctness-first fixed-column decomposition baseline 可以冻结。

---

# 2. Phase 8 简单收尾

在 `feature/phase-8` 上执行：

```bash
git status
pytest -q
python -m compileall -q backend
git diff --check
```

要求：

```text
0 failed
0 errors
working tree clean
```

确认以下内容已经提交：

```text
backend/config/benders.py
backend/core/benders.py
data/config/phase8_test_benders_v1.json

tests/unit/test_benders.py
tests/regression/test_phase8_benders_oracle.py
tests/regression/test_phase8_benders_scope.py
tests/regression/test_phase8_benders_benchmark.py

README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/codex_reports/<latest_phase8_report>.md
```

合并：

```bash
git switch main
git pull
git merge --no-ff feature/phase-8
```

合并后再次执行：

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

通过后：

```bash
git push origin main
```

确认 GitHub `main` 已包含 Phase 8 后，可删除开发分支。

---

# 3. Phase 8 Freeze

Phase 9 不得为了实现 Column Generation 随意修改 Phase 8 的：

```text
Benders partition
schedule signature
exact-schedule feasibility cut
conditional recourse cut
LB / UB semantics
scope semantics
Integrated incumbent audit
```

Phase 8 继续作为：

```text
Fixed-Column Decomposition Ground Truth
```

Phase 9 不与 Benders 联合。

---

# 4. Phase 9 定位

仓库总计划定义 Phase 9 为：

```text
Flight / Aircraft String Column Generation
```

本阶段的准确含义是：

> **在 existing Flight Options 上，对 Aircraft Strings 实现 LP Pricing + Column Generation。**

不是：

```text
自动生成新的 Flight Options
```

也不是：

```text
Crew Pairing Column Generation
Passenger Itinerary Column Generation
Benders + Column Generation
Branch-and-Price
```

Phase 9 只解决 Aircraft String 列生成。

---

# 5. Phase 9 核心目标

当前 Phase 5 会预枚举全部 legal Aircraft Strings：

```text
Flight Options
        ↓
Aircraft-local DAG
        ↓
DFS full enumeration
        ↓
all Aircraft Strings
```

Phase 9 改为：

```text
small Restricted Master LP
        ↓
LP duals
        ↓
Aircraft-local Pricing
        ↓
negative reduced-cost Aircraft Strings
        ↓
add columns
        ↓
repeat
```

最终必须证明：

```text
OBJ_CG_LP
==
OBJ_FULL_COLUMN_LP
```

注意：

```text
Phase 9 比较的是 LP objective，
不是 Integrated MIP objective 18080。
```

`18080` 继续属于 Integrated Oracle / Fixed-Column Benders ground truth，不是 Phase 9 CG 的直接验收值。

---

# 6. Phase 9 Ground Truth 层级

Phase 9 必须同时保留三层：

```text
Phase 5 Full Aircraft String Enumeration
        ↓
Full-Column Aircraft String LP Oracle
        ↓
Aircraft String Column Generation LP
```

验收关系：

```text
Full-column generated string universe
        ↓
OBJ_FULL_COLUMN_LP
        ==
OBJ_CG_LP
```

在 tiny case 上还必须有：

```text
Pricing Network Result
        ==
Brute-force / Full-pool Reduced-Cost Oracle
```

---

# 7. Phase 9 明确不做

本阶段禁止：

```text
Flight Option generation
Crew Pairing Pricing
Passenger Itinerary Pricing
Benders + CG
dynamic Benders cuts
branching
integer column generation
branch-and-price
dual stabilization
trust region
column deletion
parallel pricing
solver callbacks
UI Solve workflow
真实航空公司业务规则扩展
```

这些后移。

---

# 8. 保持 existing Flight Options 固定

Phase 9 solve 开始后：

```text
Scenario
Flight Options
Schedule request
Cost profile
String-generation legality profile
RecoveryScope
```

全部冻结。

Pricing 只能生成：

```text
AircraftString
```

不得生成或修改：

```text
FlightOption
```

---

# 9. Phase 9 的固定 Schedule Contract

Phase 9 是独立的 Aircraft String CG。

输入继续复用：

```python
AircraftRecoveryRequest
```

即：

```text
required_operated_option_ids
```

Schedule 在一次 CG solve 中固定。

因此 Phase 9 的直接对象是：

```text
fixed schedule
        ↓
Aircraft String LP recourse
```

不是 Integrated `x/y/z/w` 联合优化。

后续 Phase 11 再把 Aircraft String CG 接入 Benders。

---

# 10. LP Relaxation

现有 ARM 使用：

```text
y[string] ∈ {0,1}
```

Phase 9 RMP 使用：

```text
y[string] >= 0
```

为 continuous LP variable。

在 aircraft selection equality 下无需依赖 integrality。

Phase 9 不声称恢复 binary ARM optimum。

整数性与 branching 按总计划留到后续阶段。

---

# 11. Full-Column LP Oracle

必须新增 Full-Column LP Oracle。

输入：

```text
Scenario
existing Flight Options
all legal Aircraft Strings from Phase 5
AircraftRecoveryRequest
Cost Config
RecoveryScope | None
```

输出：

```text
LP objective
y values
constraint duals
reduced costs
diagnostics
```

该 Oracle 使用：

```text
Phase 5 full explicit string universe
```

只用于：

```text
small/toy/benchmark correctness verification
```

不能作为 Phase 9 CG 内部依赖。

---

# 12. Restricted Master LP

建议新增：

```text
backend/core/aircraft_string_master.py
```

或等价名称。

RMP 必须有明确 constraint handles，供 dual extraction。

至少保留与 ARM 对应的：

```text
Aircraft string selection
Required flight-option coverage
Schedule leakage / non-required option handling
Terminal compatibility
Maintenance compatibility
```

可以对已经由 Phase 5 legality contract 保证的冗余行进行简化，但只有在：

```text
Full-column simplified LP
==
Full-column ARM LP relaxation
```

已通过 regression 后才允许。

默认优先保持当前 ARM constraint semantics，避免 Phase 9 无意改变数学模型。

---

# 13. 不直接修改现有 binary ARM 行为

原则上：

```text
backend/core/arm.py
```

保持现有 binary default behavior。

若为了复用代码，需要增加：

```text
continuous relaxation mode
constraint handles
```

必须满足：

```text
default = current binary behavior
existing ARM tests unchanged
existing ARM objective unchanged
```

不得把 Phase 2 ARM 默认为 LP。

如果会显著污染 `arm.py`，宁可新增专用 LP master module。

---

# 14. Solver Contract

现有 solver abstraction 已支持：

```text
get_constraint_dual(...)
get_reduced_cost(...)
```

Phase 9 必须使用该公共接口。

不得：

```text
直接访问 gurobipy model.Pi
直接访问 gurobipy Var.RC
```

Phase 9 core 不应绑定 Gurobi 私有 API。

dual / reduced cost 只允许在：

```text
optimal continuous LP
```

后读取。

若 RMP 非 OPTIMAL：

```text
不得 pricing
不得声明 convergence
```

---

# 15. RMP 每轮重新 Build

当前 SolverAdapter 没有必要扩展 dynamic-column coefficient mutation。

Phase 9 v1 推荐：

```text
current column pool
        ↓
fresh build RMP
        ↓
solve LP
        ↓
read duals
        ↓
pricing
        ↓
append new columns to immutable pool
        ↓
next iteration fresh rebuild
```

与 Phase 8 correctness-first 风格一致。

不要为了性能提前增加复杂 solver mutation API。

---

# 16. Initial RMP Feasibility

不能假设：

```text
Original Aircraft Strings
```

一定与当前 disrupted schedule compatible。

因此不得简单使用：

```text
original-only initial pool
```

并假定 RMP 一定可行。

Phase 9 v1 应实现：

```text
Phase I artificial-variable feasibility stage
```

---

# 17. Phase I

Phase I 目的：

> 在不预枚举全部 Aircraft Strings 的情况下，为 RMP 找到真实可行列集合。

允许初始 real string pool 为空或很小。

对需要 RHS=1 的关键 rows 加非负 artificial variable。

Phase I objective：

```text
min Σ artificial variables
```

真实 Aircraft String 在 Phase I：

```text
objective coefficient = 0
```

重复：

```text
solve Phase-I RMP
→ duals
→ pricing
→ add negative reduced-cost real strings
```

终止条件：

### Feasible

```text
Phase-I artificial objective <= feasibility_epsilon
```

进入 Phase II。

### Infeasible

若：

```text
artificial objective > epsilon
```

且所有 aircraft pricing 均：

```text
reduced_cost >= -pricing_epsilon
```

则：

```text
fixed schedule infeasible in current Flight Option / legality universe
```

明确返回 infeasible。

不得用任意 Big-M artificial penalty 混入正式 cost objective。

---

# 18. Phase II

Phase I 到达真实可行 column pool 后：

```text
remove artificial variables
```

正式 objective：

```text
min Σ string_cost[s] * y[s]
```

循环：

```text
solve RMP
→ extract duals
→ pricing
→ add negative reduced-cost strings
```

直到：

```text
min reduced cost >= -pricing_epsilon
```

---

# 19. Reduced Cost 定义

必须从实际 RMP row coefficients 推导 reduced cost。

基本形式：

```text
rc(s)
=
c(s)
-
Σ_row dual[row] * coefficient[row, s]
```

不得手写未经验证的符号方向。

对 Aircraft String 至少包含：

```text
aircraft selection dual
flight-option coverage duals
terminal dual（若该 row 保留）
maintenance dual（若该 row 保留）
```

Schedule-leakage row 如果 pricing 已严格禁止 non-required revenue options，则该项为 0。

---

# 20. Reduced Cost 必须双重验证

Phase 9 最重要的单元测试之一：

对于已经在 RMP 中的每一条 real Aircraft String：

```text
manual_reduced_cost(string, duals)
≈
solver.get_reduced_cost(y[string])
```

允许 tolerance：

```text
1e-6
```

如果符号、row coefficient 或 dual mapping 错误，该测试必须失败。

---

# 21. Aircraft String Cost

Pricing 的 primal cost 必须复用现有：

```python
aircraft_string_cost(...)
```

语义必须与 ARM 一致：

```text
aircraft reassignment
+
ferry minutes
```

Pricing 内部可以把 cost 分解为 additive leg cost，但最终生成 candidate 后必须：

```text
pricing accumulated primal cost
==
aircraft_string_cost(candidate).total
```

独立复算。

不得建立第二套不同 cost semantics。

---

# 22. Pricing Network

优先复用现有：

```text
backend/core/flight_network.py
```

即 Phase 5 已验证的：

```text
AircraftFlightNetwork
```

以及：

```text
validate_flight_option_for_aircraft(...)
validate_generated_aircraft_string(...)
```

不要新建另一套 station/timing/turn-time/equipment legality。

---

# 23. Schedule-Compatible Pricing Universe

给定：

```text
required_operated_option_ids
```

Pricing 可以使用：

```text
required OPERATE Flight Options
+
eligible FERRY Flight Options
```

不得生成包含：

```text
non-required revenue OPERATE option
```

的 String。

这等价于 ARM schedule leakage contract，并避免生成必定被：

```text
coverage = 0
```

row 固定为零的无效列。

---

# 24. Pricing Problem

对每架 aircraft 独立求：

```text
minimum reduced-cost legal Aircraft String
```

输入：

```text
Aircraft
AircraftFlightNetwork
required schedule options
RMP duals
cost config
string legality config
pricing config
```

输出：

```text
best legal string
reduced cost
primal string cost
dual contribution breakdown
```

如果无 negative reduced-cost string：

```text
return no improving column
```

不是错误。

---

# 25. Pricing 不能调用 Full Enumeration

正式：

```python
price_aircraft_strings(...)
```

不得内部调用：

```python
generate_aircraft_strings(...)
brute_force_legal_aircraft_strings(...)
```

否则 Phase 9 失去意义。

Full enumeration 只允许用于：

```text
Oracle tests
termination audit
benchmark comparison
```

---

# 26. Pricing Algorithm

Phase 5 network 是时间有向网络。

Phase 9 推荐实现：

```text
deterministic DAG label-setting / dynamic programming
```

label 至少需要保留：

```text
current node
path option IDs
used base-flight IDs
accumulated reduced-cost contribution
```

因为 Phase 5 legality 禁止：

```text
duplicate Flight Option
duplicate base flight
```

不得为了简单 shortest path 而丢掉该语义。

---

# 27. Label / Dominance

Phase 9 correctness 优先。

第一版允许使用：

```text
(node, used_base_flights)
```

作为状态。

可以实现安全 dominance，但不强制。

如果实现 dominance，只能在数学上明确安全时剪枝。

不得因为：

```text
成本更高
```

就删除一个拥有不同 used-base-flight state 的 label。

---

# 28. Terminal Candidate

只有路径满足现有 Phase 5 legality：

```text
start station
terminal station
turn time
recovery horizon
equipment
maintenance
duplicate-base-flight rule
```

才可作为 priced Aircraft String。

每个 pricing 输出必须再次调用：

```python
validate_generated_aircraft_string(...)
```

若 pricer 输出 illegal candidate：

```text
raise Phase9 error
```

不得静默丢弃。

---

# 29. Idle String

如果 Phase 5 contract 下 idle string 合法，则 Pricing 必须考虑：

```text
empty Aircraft String
```

其 reduced cost 同样需要正确计算。

不能只搜索至少一段航班的 path。

---

# 30. Stable String Identity

新列继续沿用 Phase 5 的 semantic identity：

```text
aircraft_id
+
ordered leg_option_ids
```

不得引入另一种 String ID 规则。

如果 Phase 5 ID helper 当前是私有函数，可：

```text
提取为稳定 public helper
```

但必须保持现有 generated String IDs 不变。

---

# 31. Column Deduplication

current pool 按 semantic key 去重。

如果 pricing 返回已存在 String：

```text
不得重复加入
```

如果该 String reduced cost 显示显著负值但已经在 optimal RMP 内：

```text
视为 dual / reduced-cost / model bug
```

因为 optimal RMP 中 existing variable 不应有违反 tolerance 的负 reduced cost。

必须报错或进入 diagnostics。

---

# 32. 每轮加入多少列

建议 config：

```text
max_columns_per_aircraft_per_iteration
```

第一版可默认：

```text
1
```

即每架 aircraft 每轮最多加入最负 reduced-cost String。

这样：

```text
迭代确定性高
易于 Oracle 检查
```

后续再做 multi-column pricing。

---

# 33. Phase 9 Config

建议新增：

```text
backend/config/column_generation.py
```

或更明确：

```text
backend/config/aircraft_string_column_generation.py
```

配置至少：

```text
schema_version = 1.0.0
profile_id

pricing_epsilon
feasibility_epsilon
max_iterations
max_columns_per_aircraft_per_iteration

source
notes
```

要求：

```text
frozen
extra=forbid
strict
duplicate JSON key rejection
versioned
```

测试配置：

```text
data/config/phase9_test_aircraft_string_cg_v1.json
```

---

# 34. 建议核心文件

建议新增：

```text
backend/core/aircraft_string_master.py
backend/core/aircraft_string_pricing.py
backend/core/aircraft_string_column_generation.py
```

职责：

### `aircraft_string_master.py`

```text
Full-column LP
Restricted Master LP
Phase-I artificial master
dual extraction
LP diagnostics
```

### `aircraft_string_pricing.py`

```text
reduced-cost formula
network label-setting
pricing result
pricing audit
```

### `aircraft_string_column_generation.py`

```text
Phase I loop
Phase II loop
column pool
termination
result / metrics
full audit
```

如果实现后文件较小，可以合并，但职责必须清晰。

---

# 35. 建议公共类型

至少有：

```text
AircraftStringMasterDuals
AircraftStringPricingResult
AircraftStringCGIteration
AircraftStringCGResult
AircraftStringCGStatus
AircraftStringCGError
```

结果必须能报告：

```text
Phase-I objective
Phase-II objective
iteration count
column counts
dual values
minimum reduced cost
selected fractional y
pricing results
termination reason
```

---

# 36. Full-Column LP Builder

建议公共入口：

```python
solve_full_column_aircraft_string_lp(...)
```

要求：

```text
continuous y
all Phase-5 generated legal strings
same fixed schedule
same cost
same scope
same row semantics
```

这是 Phase 9 的 primary Oracle。

---

# 37. CG Solver Public API

建议：

```python
solve_aircraft_string_column_generation(
    scenario,
    flight_options,
    request,
    costs,
    string_generation_config,
    cg_config,
    *,
    solver_factory,
    scope=None,
) -> AircraftStringCGResult
```

正式 solver 不接收：

```text
all generated Aircraft Strings
```

否则会形成 full-enumeration dependency。

测试层可以单独把 full pool 传给 Oracle/audit helper。

---

# 38. Scope

Phase 9 应支持：

```text
scope=None
RecoveryScope
```

规则：

### in-scope aircraft

```text
允许 pricing
```

### out-of-scope aircraft

```text
只允许 semantic original string
不执行 pricing
```

保持 Phase 4–8 的 original-only 语义。

---

# 39. Scope 与 Pricing

对 out-of-scope aircraft：

```text
original string
```

必须先通过现有 String legality validator。

若 original string 无法唯一解析或非法：

```text
raise Phase9 error
```

不得改成 idle 或其他 String。

---

# 40. New Toy Case

建议新增：

```text
toy_case_011_aircraft_string_column_generation
```

该 toy 必须真正需要 Column Generation，不能初始列就已经最优。

至少设计：

```text
2+ aircraft
multiple required flight options
multiple legal strings
one expensive initial feasible combination
one omitted negative reduced-cost string
at least 2 pricing iterations
```

最好同时包含：

```text
reassignment cost
ferry or alternate connection
```

使 reduced cost 非平凡。

---

# 41. toy_case_011 必须有 Full Enumeration Oracle

先使用 Phase 5：

```text
generate_aircraft_strings(...)
```

得到全部 legal strings。

再：

```text
solve_full_column_aircraft_string_lp(...)
```

得到：

```text
OBJ_FULL
```

Column Generation 必须得到：

```text
OBJ_CG == OBJ_FULL
```

---

# 42. Pricing Oracle Test

对 toy case 每轮 dual：

```text
network pricer
```

与：

```text
scan every full-enumeration String
→ compute manual reduced cost
→ take minimum
```

比较：

```text
best reduced cost
best semantic key 或等价 minimum set
```

要求：

```text
rc_pricer == rc_bruteforce
```

如果存在多个等价最优 priced Strings：

```text
允许 semantic key 不同
```

但 minimum reduced cost 必须一致，且返回 String 必须属于 minimum set。

---

# 43. Existing-Column Reduced-Cost Audit

在 Full-Column LP 和 RMP 上：

对每个当前 real variable：

```text
manual_rc
==
solver RC
```

该测试必须覆盖：

```text
positive RC
zero RC
```

最好有：

```text
negative RC
```

出现在 restricted master pricing 前的 omitted column oracle 中。

---

# 44. Termination Audit

CG 声称收敛时：

```text
all pricing results >= -epsilon
```

在 toy/benchmark 上进一步使用 Full Enumeration 做独立终止检查：

```text
for every legal full-pool String not in RMP:
    manual reduced cost >= -epsilon
```

如果存在遗漏 negative reduced-cost String：

```text
Phase 9 FAIL
```

---

# 45. Phase-I Oracle

toy_case_011 至少测试：

### Case A：initial real pool insufficient

```text
Phase-I artificial objective > 0
→ pricing adds columns
→ artificial objective → 0
→ enter Phase II
```

### Case B：真实 fixed schedule infeasible

```text
Phase-I artificial objective > 0
+
no negative reduced-cost real columns
→ status = INFEASIBLE
```

不得无限迭代。

---

# 46. Phase-II Termination

Phase II 必须满足：

```text
RMP status = OPTIMAL
all aircraft pricing complete
min reduced cost >= -pricing_epsilon
```

才可：

```text
status = OPTIMAL
```

达到 `max_iterations`：

```text
status = NOT_CONVERGED
```

不得返回 OPTIMAL。

---

# 47. Benchmark Regression

使用：

```text
phase1_benchmark_001
```

Flight Options 与 Phase 5 string-generation profile 保持现状。

Full pool 当前预期仍为：

```text
77 Aircraft Strings
```

但不要把 77 作为算法正确性的唯一硬编码。

对至少一个固定 feasible schedule 执行：

```text
Full-column Aircraft String LP
vs
Aircraft String CG LP
```

要求：

```text
objective equal
```

如果当前 Integrated optimum schedule 的 ARM LP objective 为 0，可以保留该 regression，但不能只依赖这一条；`toy_case_011` 必须提供非平凡 pricing。

---

# 48. Existing Phase 5 Oracle 继续保留

Phase 9 不删除：

```text
toy_case_007_string_generator
brute_force_legal_aircraft_strings(...)
Phase 5 full enumeration
```

它们现在升级为 Phase 9 的：

```text
pricing / full-column Oracle infrastructure
```

---

# 49. 与 Phase 8 的关系

Phase 9 不修改：

```text
solve_fixed_column_benders(...)
```

也不把 CG 接入 ARM subproblem。

Phase 9 验收完成时应同时存在：

```text
Integrated Oracle
Fixed-Column Benders
Full-Column Aircraft String LP
Aircraft String CG LP
```

彼此职责独立。

---

# 50. 不直接比较 CG LP 与 Fixed-Column Benders MIP

以下比较没有直接数学意义：

```text
OBJ_CG_LP == 18080
```

禁止把它作为 Phase 9 验收。

Phase 9 正确比较：

```text
OBJ_CG_AIRCRAFT_LP
==
OBJ_FULL_COLUMN_AIRCRAFT_LP
```

Phase 11 才处理：

```text
Benders + Column Generation
```

---

# 51. LP Integrality 结果只记录，不承诺

如果 tiny/benchmark 中 Full-column Aircraft LP 恰好 integral，可以记录：

```text
observed integral solution
```

但不得由此宣称：

```text
Aircraft String master generally integral
```

也不得跳过后续 Integrality / Branching 阶段。

---

# 52. Diagnostics

每轮至少记录：

```text
phase               I / II
iteration
RMP objective
real column count
artificial objective
dual count
priced aircraft count
minimum reduced cost
negative columns found
new columns added
duplicate columns rejected
runtime
```

最终：

```text
termination reason
full-column objective（oracle mode）
CG objective
objective difference
total generated columns
full-pool count（oracle only）
column reduction ratio
```

---

# 53. Determinism

相同输入下应保持：

```text
initial pool semantics
pricing order
new-column semantic keys
iteration sequence
final column pool
objective
termination reason
```

尽可能 deterministic。

solver dual 在高度退化 LP 中可能存在多个等价解，因此测试应优先验证：

```text
objective
reduced-cost validity
minimum reduced cost
final convergence
```

不要不必要地强制所有 dual 数值逐项完全一致。

---

# 54. Numerical Tolerance

统一通过 config 使用：

```text
pricing_epsilon
feasibility_epsilon
```

禁止散落：

```text
1e-6
1e-8
```

magic numbers。

判断 negative reduced cost：

```text
rc < -pricing_epsilon
```

判断 Phase-I feasible：

```text
artificial objective <= feasibility_epsilon
```

---

# 55. Error Handling

必须明确区分：

```text
OPTIMAL
INFEASIBLE
NOT_CONVERGED
ABORTED
```

以下情况不得继续 pricing：

```text
RMP not optimal
dual unavailable
NaN/Inf dual
invalid priced string
manual RC != solver RC
duplicate semantic ID conflict
candidate universe changed
scope invalid
```

错误信息至少包含：

```text
phase
iteration
aircraft_id
schedule/request
reason
```

---

# 56. Candidate Universe Fingerprint

建议记录：

```text
Scenario ID
Flight Option semantic content
Cost profile
String-generation profile
Schedule request
Scope
CG config
```

Phase 9 的 fixed input 在一次 solve 中若发生变化：

```text
abort
```

新生成的 Aircraft Strings 不属于“input mutation”，它们属于明确记录的 CG state。

---

# 57. Unit Tests

建议新增：

```text
tests/unit/test_aircraft_string_master.py
tests/unit/test_aircraft_string_pricing.py
tests/unit/test_aircraft_string_column_generation.py
```

至少覆盖：

```text
continuous y variables
constraint handles
dual extraction
solver reduced cost access

manual RC == solver RC
string primal cost audit

schedule-compatible pricing universe
non-required OPERATE excluded
FERRY allowed when legal

idle string
duplicate base flight prevention
station continuity
turn time
terminal
maintenance

stable semantic ID
column deduplication

Phase-I artificial master
Phase-I feasible transition
Phase-I infeasible detection

Phase-II negative column insertion
no-negative-RC termination
max iteration status
determinism
```

---

# 58. Regression Tests

建议新增：

```text
tests/regression/test_phase9_pricing_oracle.py
tests/regression/test_phase9_full_column_lp.py
tests/regression/test_phase9_column_generation.py
tests/regression/test_phase9_benchmark.py
tests/regression/test_phase9_scope.py
```

---

# 59. Phase 9 核心验收

必须全部满足。

## A. Full-column LP

- [ ] 使用全部 Phase-5 legal Aircraft Strings；
- [ ] continuous LP；
- [ ] fixed schedule；
- [ ] objective/cost 与 ARM owner contract 一致；
- [ ] dual/reduced cost 可读。

## B. Pricing

- [ ] 不调用 full enumeration；
- [ ] 复用 Phase-5 network legality；
- [ ] schedule leakage 被排除；
- [ ] duplicate base flight rule 保留；
- [ ] 输出 String 再次通过 independent validator；
- [ ] primal string cost 独立复算一致。

## C. Reduced Cost

- [ ] 公式由实际 RMP rows 推导；
- [ ] manual RC = solver RC；
- [ ] network pricing minimum RC = brute-force full-pool minimum RC。

## D. Phase I

- [ ] 不要求预先存在 feasible real pool；
- [ ] artificials 可使 initial RMP feasible；
- [ ] feasible instance 最终 artificial objective = 0；
- [ ] infeasible fixed schedule 能正确识别。

## E. Phase II

- [ ] 只加入 negative reduced-cost columns；
- [ ] semantic duplicate 不重复加入；
- [ ] RMP 每轮 OPTIMAL 后才读取 dual；
- [ ] termination 时无遗漏 negative-RC column。

## F. Oracle Equality

```text
toy_case_011:
OBJ_CG == OBJ_FULL_COLUMN_LP

benchmark:
OBJ_CG == OBJ_FULL_COLUMN_LP
```

## G. Scope

- [ ] in-scope aircraft 可 pricing；
- [ ] out-of-scope aircraft original-only；
- [ ] Scope LP CG = Scope full-column LP。

## H. Regression

- [ ] Phase 1–8 原有测试全部通过；
- [ ] Phase 5 full enumeration behavior 不变；
- [ ] Phase 8 Benders objective/regression 不变。

---

# 60. Definition of Done

Phase 9 只有在以下链条全部成立后才能标记完成：

```text
Existing Flight Options
        ↓
Phase 5 Aircraft Flight Network
        ↓
Full Aircraft String Enumeration
        ↓
Full-Column LP Oracle
        ↕
Restricted Master LP
        ↓
LP Duals
        ↓
Network Pricing
        ↓
Negative Reduced-Cost Strings
        ↓
Column Generation Iteration
        ↓
No Negative Reduced-Cost String
        ↓
Exhaustive Termination Audit
        ↓
OBJ_CG == OBJ_FULL_COLUMN_LP
        ↓
Full Regression PASS
```

禁止仅因为：

```text
CG 能运行
有负 reduced cost
最后没有新列
solver 返回 OPTIMAL
```

就结束 Phase 9。

---

# 61. 推荐实施顺序

严格按以下顺序：

## Step 1 — Phase 8 Close

```text
full test
merge feature/phase-8 → main
post-merge regression
```

## Step 2 — Phase 9 Branch

```bash
git switch main
git pull
git switch -c feature/phase-9
```

## Step 3 — LP Master

先实现：

```text
Full-column continuous Aircraft String LP
RMP
constraint handles
dual extraction
```

先不要写 pricing。

## Step 4 — Reduced-Cost Audit

用 full-column LP 验证：

```text
manual RC == solver RC
```

先冻结符号和 row mapping。

## Step 5 — Pricing

复用：

```text
AircraftFlightNetwork
Phase-5 legality validator
```

实现 network pricer。

## Step 6 — Pricing Oracle

在 tiny case 比较：

```text
network min RC
==
full-enumeration min RC
```

## Step 7 — Phase I

加入 artificial feasibility stage。

## Step 8 — Phase II CG Loop

实现：

```text
RMP → dual → pricing → add columns
```

## Step 9 — toy_case_011

要求真正产生多轮 CG。

## Step 10 — Full-column Equality

```text
OBJ_CG == OBJ_FULL
```

## Step 11 — Scope Regression

验证：

```text
scope full LP == scope CG LP
```

## Step 12 — Benchmark

使用 Phase 1 benchmark。

## Step 13 — Full Regression

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

## Step 14 — Documentation

更新：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

## Step 15 — Codex Report

输出 Phase 9 实施报告。

---

# 62. Phase 9 Report

新增：

```text
docs/codex_reports/
YYYYMMDD_HHMMSS_phase9_aircraft_string_column_generation_report.md
```

至少包括：

```text
1. Phase 8 baseline
2. Modified files
3. Full-column LP formulation
4. RMP formulation
5. Phase-I formulation
6. Dual mapping
7. Reduced-cost formula
8. Pricing algorithm
9. Pricing legality boundary
10. toy_case_011 design
11. Pricing-vs-brute-force result
12. Full-column LP result
13. CG iteration trajectory
14. Scope result
15. Benchmark result
16. Termination exhaustive audit
17. Full regression result
18. Known limitations
19. Deferred work
20. Next step
```

---

# 63. Report 必须给出的数字

至少：

```text
full string count
initial real column count
final CG column count

Phase-I iterations
Phase-II iterations
total iterations

columns added by aircraft
minimum reduced cost by iteration

Full-column LP objective
CG LP objective
difference

full-pool minimum omitted reduced cost at termination

runtime
pytest passed / failed / skipped
```

---

# 64. Known Limitations 必须明确

Phase 9 完成后仍必须写明：

```text
Flight Options remain fixed
Only Aircraft String CG implemented
Schedule remains fixed inside one CG solve
No Crew Pairing CG
No Passenger Itinerary CG
No Benders + CG
No branching / integrality recovery
No airline-specific production pricing rules
```

---

# 65. Phase 9 完成后的下一步

按当前仓库总计划：

```text
Phase 10 — Crew Pairing Column Generation
```

Phase 10 应复制 Phase 9 已验证的方法学：

```text
Full Pairing LP Oracle
        ↕
Crew RMP
        ↓
Duals
        ↓
Crew Pairing Pricing
        ↓
OBJ_CG == OBJ_ALL_PAIRINGS_LP
```

只有：

```text
Fixed-Column Benders
Aircraft String CG
Crew Pairing CG
```

全部独立通过后，才进入：

```text
Phase 11 — Benders + Column Generation
```

Phase 11 必须重新处理：

```text
new columns
vs
old Benders cut validity
```

不得直接复用 Phase 8 cuts 并假定仍然有效。

---

# 66. 最终开发原则

Phase 9 的唯一核心问题是：

> **在不预枚举全部 Aircraft Strings 的正式求解路径中，能否只依靠 LP dual + aircraft-local pricing 找到足够的负 reduced-cost Strings，并最终得到与 Full-Column LP 完全相同的最优值。**

优先级：

```text
Reduced-cost correctness
> Pricing completeness
> Full-column Oracle equality
> Reproducibility
> Column reduction
> Runtime
```

Phase 9 不以“更快”为首要验收条件。

首先证明：

```text
Column Generation is correct.
```

之后再优化性能。
