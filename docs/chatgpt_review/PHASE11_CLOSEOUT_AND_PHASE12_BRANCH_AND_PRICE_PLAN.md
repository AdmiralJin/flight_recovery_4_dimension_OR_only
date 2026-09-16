# Phase 11 Closeout & Phase 12 Integrality / Branch-and-Price Plan

## 1. Phase 11 Review Conclusion

**Phase 11 可以收尾并合并。当前未发现阻断性问题。**

当前 `feature/phase-110` 已完成：

```text
SRM Schedule Master
        ↓
Aircraft String CG full-LP certificate
+
Crew Pairing CG full-LP certificate
+
Passenger exact PRM
        ↓
pricing-certified Benders lower-bound / feasibility cuts
        ↓
generated-column binary ARM / CRM incumbent
        ↓
LB / UB
        ↓
Integrated diagnostics
```

已核对当前实现与状态文档：

```text
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
reproduction_notes.md
assumptions.md

backend/core/benders_column_generation.py
backend/config/benders_column_generation.py

tests/regression/test_phase11_benders_cg_benchmark.py
tests/regression/test_phase11_benders_cg_cut_validity.py
```

当前已冻结的核心语义：

- Phase 11 不复用 Phase 8 fixed-column recourse cuts；
- Aircraft/Crew cut 只来自 pricing 已完整收敛后的 full implicit LP objective；
- restricted RMP objective 不生成永久 Benders cut；
- restricted-pool infeasibility 不生成 schedule no-good；
- Passenger 仍为 exact fixed-column MIP；
- CG 返回列上的 binary ARM / CRM 只形成可行 integer upper bound；
- LP objective 与 generated-pool binary objective 一致时才记录 integer exactness；
- 无新合法 cut、LB < UB 且存在 LP/integer gap 时返回 `INTEGRALITY_REQUIRED`；
- v1 正式入口只支持 `scope=None`；
- 正式 Phase 11 输入要求 Aircraft Strings / Crew Pairings 为空；
- final incumbent 必须通过 Integrated diagnostics。

当前项目状态记录：

```text
toy_case_013:
LB = UB = Full Explicit Integrated Oracle = 220

phase1_benchmark_001:
Benders + CG = Full Explicit Integrated Oracle = 18080
```

Benchmark regression 同时验证：

```text
full explicit oracle:
77 Aircraft Strings
374 Crew Pairings
55 Passenger Itineraries

formal Phase 11 input:
Aircraft Strings = []
Crew Pairings = []
```

因此 Phase 11 已满足当前总计划 Level 7：

```text
Benders + Column Generation
=
Small-scale Full Explicit Integrated Oracle
```

---

# 2. Phase 11 Closeout

在 `feature/phase-110`：

```bash
git status
pytest -q
python -m compileall -q backend
git diff --check
```

若工程当前继续使用 Black：

```bash
python -m black --check <Phase11 Python files>
```

要求：

```text
working tree clean
0 failed
0 errors
```

确认以下 Phase 11 资产均已提交：

```text
backend/config/benders_column_generation.py
backend/core/benders_column_generation.py

data/config/phase11_test_benders_cg_v1.json

tests/unit/test_benders_column_generation.py

tests/regression/test_phase11_benders_cg_oracle.py
tests/regression/test_phase11_benders_cg_cut_validity.py
tests/regression/test_phase11_benders_cg_integrality_boundary.py
tests/regression/test_phase11_benders_cg_benchmark.py

toy_case_013 related data / fixtures

README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/codex_reports/<latest_phase11_report>.md
```

如果实际测试文件名略有不同，以当前分支真实结构为准，不为匹配本文件强制重命名。

---

# 3. Merge Phase 11

执行：

```bash
git switch main
git pull
git merge --no-ff feature/phase-110
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

随后：

```bash
git switch -c feature/phase-12
```

确认远端 `main` 已包含 Phase 11 后，可删除 Phase 11 分支。

---

# 4. Phase 11 Freeze

Phase 12 不得为了整数化破坏以下已验证合同：

```text
Phase 9 Aircraft CG LP
Phase 10 Crew CG LP
Phase 11 Benders cut provenance
Phase 11 implicit-universe fingerprint
Phase 11 LP lower-bound semantics
Phase 11 generated-pool binary upper-bound semantics
Phase 11 INTEGRALITY_REQUIRED boundary
Phase 11 formal-enumerator independence
```

特别禁止：

```text
将 generated-pool binary objective
直接当作 full integer recourse lower bound

用 restricted-pool infeasibility
生成 no-good

为了消除 INTEGRALITY_REQUIRED
直接跳过当前 Schedule
```

---

# 5. Phase 12 Objective

Phase 12 对应总计划：

```text
Integrality / Branching
```

Phase 12 v1 的准确目标：

> **在 fixed Schedule 下，对 Aircraft String 与 Crew Pairing 的隐式列空间实现 exact Branch-and-Price，使整数 recourse 不再依赖 full enumeration，并将该 exact integer recourse 接回 Phase 11 Schedule Benders。**

最终要求：

```text
Benders + Branch-and-Price
=
Full Explicit Integrated Oracle
```

并且：

```text
Phase 11 中可能返回 INTEGRALITY_REQUIRED 的案例
在 Phase 12 能被 exact integer branching 正确闭合
```

---

# 6. Phase 12 Scope Boundary

Phase 12 v1 继续：

```text
scope = None
```

不在本阶段同时解决 dynamic RecoveryScope。

原因：

```text
dynamic pricing
+
branch restrictions
+
scope closure
```

属于三个独立复杂度来源。

Phase 12 先只解决 integrality。

---

# 7. Passenger Boundary

Phase 12 v1 **不实现 Passenger Branch-and-Price**。

当前 PRM：

```text
Passenger Itineraries = fixed explicit columns
w = binary
```

并且 Phase 11 已直接使用 exact PRM MIP。

因此 Phase 12 保持：

```text
Passenger = exact fixed-column MIP
```

当前总计划中的 “PRM Branching” 不在 v1 中额外重写；只有未来 Passenger Itinerary 也改为 Column Generation 时，才需要 Passenger Branch-and-Price。

---

# 8. Phase 12 Architecture

推荐分三层实现：

```text
Layer A
Fixed-Schedule Aircraft Branch-and-Price

Layer B
Fixed-Schedule Crew Branch-and-Price

Layer C
Schedule Benders
+
exact Aircraft B&P recourse
+
exact Crew B&P recourse
+
exact PRM
```

不要一开始直接写一个巨型：

```text
Benders + Aircraft B&P + Crew B&P
```

先分别建立两个 fixed-schedule integer Oracle。

---

# 9. Aircraft Branch-and-Price Goal

给定：

```text
AircraftRecoveryRequest
required_operated_option_ids
```

求完整隐式 Aircraft String universe 上的：

```text
exact binary ARM optimum
```

且正式 solver 不调用：

```python
generate_aircraft_strings(...)
brute_force_legal_aircraft_strings(...)
```

验收：

```text
OBJ_AIRCRAFT_BP
=
OBJ_FULL_EXPLICIT_ARM_MIP
```

---

# 10. Crew Branch-and-Price Goal

给定：

```text
CrewRecoveryRequest
required_operated_option_ids
```

求完整隐式 Crew Pairing universe 上：

```text
exact binary CRM optimum
```

正式 solver 不调用：

```python
generate_crew_pairings(...)
brute_force_legal_crew_pairings(...)
```

验收：

```text
OBJ_CREW_BP
=
OBJ_FULL_EXPLICIT_CRM_MIP
```

---

# 11. Branch-and-Price Node Contract

每个 branch node 必须保存：

```text
node_id
parent_id
depth
branch restrictions
LP lower bound
CG status
generated column pool
integrality status
```

每个 node 的 LP：

```text
branch-restricted implicit column universe
        ↓
Column Generation
        ↓
pricing-certified node LP optimum
```

只有 node CG：

```text
OPTIMAL
```

才可使用：

```text
node LP objective
```

作为 node lower bound。

---

# 12. Branch-and-Bound Rules

固定 Schedule 下，每个 Branch-and-Price solver：

```text
root node
    ↓
solve branch-restricted CG LP
    ↓
if infeasible:
    prune

if LP bound >= incumbent:
    prune by bound

if LP solution integral:
    update incumbent

else:
    choose deterministic branch
    create children
```

直到：

```text
no open nodes
```

得到 exact integer optimum。

---

# 13. Node Selection

Phase 12 v1 推荐：

```text
best-bound search
```

排序：

```text
lowest LP bound
then lower depth
then deterministic node_id
```

不得依赖：

```text
set iteration order
solver internal node order
randomness
```

---

# 14. Node Status

建议统一：

```python
class BranchAndPriceStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"
```

达到：

```text
max_nodes
max_pricing_iterations
```

返回：

```text
NOT_CONVERGED
```

不得伪装 OPTIMAL。

---

# 15. Aircraft Branching — Primary Rule

优先使用：

```text
Aircraft × Required Flight Option assignment branching
```

定义：

```text
A[a,o]
=
Σ_s y[s] * 1[string s belongs to aircraft a and contains option o]
```

对于 fractional：

```text
0 < A[a,o] < 1
```

建立两个 child：

```text
LEFT:
aircraft a must NOT cover option o

RIGHT:
aircraft a MUST cover option o
```

---

# 16. Aircraft Branch Restrictions

建议：

```python
@dataclass(frozen=True)
class AircraftBranchRestrictions:
    required_options_by_aircraft
    forbidden_options_by_aircraft
    forced_string_key_by_aircraft
    forbidden_string_keys
```

必须检查：

```text
same option simultaneously required and forbidden → node infeasible
multiple incompatible forced strings → node infeasible
```

---

# 17. Aircraft Pricing Under Branching

Phase 9 pricer 必须以向后兼容方式支持：

```text
branch_restrictions=None
```

默认：

```text
None
```

时 Phase 9 行为必须完全不变。

branch node 中：

### forbidden option

该 aircraft 的 priced String：

```text
不得包含该 Flight Option
```

### required option

priced String：

```text
必须包含该 Flight Option
```

### forced string

该 aircraft：

```text
只允许该 exact semantic String
```

### forbidden string

不得生成该 semantic key。

---

# 18. Aircraft Branching Fallback

如果：

```text
所有 A[a,o] 都在 tolerance 内整数
```

但 LP `y` 仍存在 fractional columns，则使用 fallback：

```text
exact String branching
```

选择 deterministic fractional String `s`：

```text
LEFT:
y[s] = 0

RIGHT:
aircraft owner 强制选择 semantic String s
```

该规则保证 Branch-and-Price 能继续推进，不依赖“assignment branching 一定足够”的未经证明假设。

---

# 19. Aircraft Integrality

Aircraft node 不能只检查：

```text
assignment A[a,o]
```

必须同时检查最终：

```text
all y values ∈ {0,1}
```

within tolerance。

只有 y integral 才是 node integer solution。

---

# 20. Crew Branching — Primary Follow-on Rule

Crew 采用：

```text
crew-local typed follow-on branching
```

对一个 Crew `c` 和 typed transition：

```text
arc = (CrewLegKey_left, CrewLegKey_right)
```

定义：

```text
F[c,arc]
=
Σ_p z[p] * 1[pairing p for crew c contains this consecutive typed arc]
```

选择 fractional：

```text
0 < F[c,arc] < 1
```

建立：

```text
LEFT:
crew c selected Pairing must NOT use arc

RIGHT:
crew c selected Pairing MUST use arc
```

这与 Crew DAG pricing 结构兼容。

---

# 21. Why Typed Follow-on

必须保留：

```text
OPERATE
DEADHEAD
```

类型。

以下两条不等价：

```text
OPERATE(F1) → OPERATE(F2)
OPERATE(F1) → DEADHEAD(F2)
```

Phase 12 branching key 必须包含：

```text
segment type
flight_option_id
```

不得只使用 base Flight ID。

---

# 22. Crew Branch Restrictions

建议：

```python
@dataclass(frozen=True)
class CrewBranchRestrictions:
    required_follow_ons_by_crew
    forbidden_follow_ons_by_crew

    required_typed_legs_by_crew
    forbidden_typed_legs_by_crew

    forced_pairing_key_by_crew
    forbidden_pairing_keys
```

---

# 23. Crew Pricing Under Branching

Phase 10 pricer 以向后兼容方式增加：

```text
branch_restrictions=None
```

默认行为必须完全保持 Phase 10。

branch node pricing：

```text
forbidden follow-on:
    transition 不允许扩展

required follow-on:
    emitted Pairing 必须包含该 transition

forbidden typed leg:
    path 不得使用

required typed leg:
    emitted Pairing 必须包含

forced Pairing:
    owner 只允许 exact semantic Pairing
```

同时继续满足：

```text
qualification
station
MCT
duty
deadhead
terminal
duplicate option/base flight
```

---

# 24. Crew Branching Fallback 1

如果没有 fractional follow-on，但 `z` 仍 fractional：

定义：

```text
L[c,typed_leg]
=
Σ_p z[p] * 1[p contains typed_leg]
```

对 fractional membership 做：

```text
typed-leg 0/1 branching
```

---

# 25. Crew Branching Fallback 2

如果：

```text
follow-on aggregate integral
typed-leg aggregate integral
```

但仍有 fractional `z`：

使用：

```text
exact Pairing branching
```

```text
LEFT:
z[p] = 0

RIGHT:
crew c forced to semantic Pairing p
```

确保有限推进。

---

# 26. Branch Restriction Fingerprint

每个 node 必须有：

```python
branch_restriction_fingerprint(...)
```

由：

```text
owner
required assignments/follow-ons
forbidden assignments/follow-ons
forced column
forbidden semantic keys
```

稳定生成。

Node CG fingerprint 必须包含该 branching fingerprint。

禁止跨不同 branch node 复用：

```text
LP bound
dual
pricing certificate
```

---

# 27. Column Reuse Between Parent and Child

允许性能上：

```text
child initial pool
=
parent generated columns
filtered by child restrictions
```

但必须满足：

```text
only legal child columns retained
```

并且：

```text
child pricing still runs to complete convergence
```

Parent column pool 只能作为 warm start，不能作为 child full universe。

---

# 28. Node CG Completeness

每个 Branch-and-Price node 的 `OPTIMAL` 必须继续满足 Phase 9/10 的定义：

```text
RMP optimal
+
pricing complete
+
no negative reduced-cost column
```

且 pricer 必须在 branch-restricted universe 内完整。

Branch restriction 不能只过滤当前 RMP columns 而不进入 pricing。

---

# 29. Full-Pool Branch Oracle

在 toy / regression 中允许使用 Phase 5/6 full explicit pools。

对于 branch node：

```text
full pool
→ filter by branch restrictions
→ solve full-column LP/MIP
```

与 Branch-and-Price node 比较：

```text
node CG LP = filtered full LP

eventual B&P integer optimum
=
filtered/full binary MIP optimum
```

这是 Phase 12 最关键 Oracle。

---

# 30. Aircraft Branch-and-Price Module

建议新增：

```text
backend/core/aircraft_string_branch_and_price.py
```

公共 API：

```python
solve_aircraft_string_branch_and_price(...)
```

输入：

```text
Scenario
Flight Options
AircraftRecoveryRequest
Cost Config
FlightStringGenerationConfig
AircraftStringCGConfig
AircraftBranchAndPriceConfig
solver_factory
```

输出：

```text
status
objective
selected Strings
tree nodes
LP bounds
incumbent trajectory
generated columns
branch decisions
```

---

# 31. Crew Branch-and-Price Module

新增：

```text
backend/core/crew_pairing_branch_and_price.py
```

公共 API：

```python
solve_crew_pairing_branch_and_price(...)
```

输入相应 Crew configs。

---

# 32. Phase 12 Config

建议新增：

```text
backend/config/branch_and_price.py
```

或分开：

```text
aircraft_branch_and_price.py
crew_branch_and_price.py
```

v1 可用统一：

```python
BranchAndPriceConfig
```

字段至少：

```text
schema_version
profile_id

integrality_tolerance
bound_tolerance

max_nodes
max_depth

node_selection = "best_bound"

source
notes
```

Pricing tolerance 继续来自 Phase 9 / Phase 10 CG config，不复制。

---

# 33. Branch Candidate Selection

必须 deterministic。

推荐：

```text
choose fractional aggregate closest to 0.5
then semantic lexical tie-break
```

Aircraft：

```text
(a, option_id)
```

Crew：

```text
(crew_id, typed follow-on)
```

fallback 同样 deterministic。

---

# 34. Branch-and-Price Lower Bound

全局 B&P lower bound：

```text
min LP bound among all open nodes
```

当 open nodes 为空：

```text
LB = incumbent objective
```

如果无 incumbent 且所有 nodes infeasible：

```text
INFEASIBLE
```

---

# 35. Branch-and-Price Upper Bound

来自：

```text
integral node solution
```

不能来自：

```text
fractional LP
```

更新：

```text
UB = min(existing UB, integer node objective)
```

---

# 36. Node Pruning

允许：

```text
infeasible prune

bound prune:
node_LB >= incumbent_UB - tolerance

integral prune:
node LP integral
→ update incumbent
→ node complete
```

不得：

```text
因为列数太多而静默 prune
因为 branch rule 不方便而 skip node
```

---

# 37. Fixed-Schedule Aircraft B&P Acceptance

至少建立一个新 toy：

```text
toy_case_014_aircraft_integrality
```

必须满足：

```text
root Aircraft CG LP fractional

root LP objective
<
full explicit binary ARM objective
```

Branch-and-Price 最终：

```text
OBJ_AIRCRAFT_BP
=
OBJ_FULL_EXPLICIT_ARM_MIP
```

且至少：

```text
one actual branch
```

---

# 38. Fixed-Schedule Crew B&P Acceptance

新增：

```text
toy_case_015_crew_integrality
```

要求：

```text
root Crew CG LP fractional

root LP objective
<
full explicit binary CRM objective

typed follow-on branch triggered
```

最终：

```text
OBJ_CREW_BP
=
OBJ_FULL_EXPLICIT_CRM_MIP
```

---

# 39. If Current Models Cannot Produce a Natural Gap

如果经过系统构造后发现：

```text
Aircraft root LP 在当前 v1 formulation 始终 integral
```

不得人为修改 ARM 数学模型制造 gap。

此时 Phase 12 report 应明确：

```text
Aircraft Branch-and-Price infrastructure implemented and Oracle-tested,
but current tested Aircraft instances exhibit zero integrality gap.
```

仍需测试：

```text
branch restriction correctness
fallback branch mechanics
full-MIP equality
```

Crew 必须尽量构造真实 fractional set-partitioning case。

---

# 40. Existing Phase 9 / 10 API Compatibility

Phase 12 如需扩展 Phase 9/10 pricer：

必须采用：

```text
optional branch_restrictions=None
```

或者新增 branch-aware wrapper。

要求：

```text
existing Phase 9 tests unchanged
existing Phase 10 tests unchanged
root CG results unchanged
```

不允许把普通 Phase 9/10 CG 默认变成 branch mode。

---

# 41. Integrate Back Into Schedule Benders

在 fixed-schedule Aircraft/Crew B&P 独立通过后，再新增：

```text
backend/core/benders_branch_and_price.py
```

不要直接重写：

```text
benders_column_generation.py
```

Phase 11 继续保留。

---

# 42. Phase 12 Benders Recourse Logic

给定 Master Schedule：

## First

可继续调用 Phase 9/10 CG root LP：

```text
Aircraft LP
Crew LP
```

得到快速 lower-bound cuts。

## Then

如果：

```text
LP objective == generated-pool binary objective
```

已有 Phase 11 integrality certificate：

```text
无需 Branch-and-Price
```

## Otherwise

调用：

```text
Aircraft Branch-and-Price
Crew Branch-and-Price
```

得到：

```text
exact integer recourse
```

---

# 43. Exact Integer Recourse Cut

Branch-and-Price 证明：

```text
Q_A_MIP(x̄)
```

后，可以加入 exact schedule-specific cut：

```text
thetaA
>=
Q_A_MIP(x̄)
-
Q_A_MIP(x̄) * Δ(x,x̄)
```

Crew 同理。

该 cut：

```text
只在当前 exact Schedule 上 tight
其他 Schedule RHS <= 0
```

因此不需要 classical integer Benders dual。

这与 Phase 8 exact-schedule cut philosophy 一致，但 recourse value 来自：

```text
dynamic Branch-and-Price exact proof
```

而不是 fixed full columns。

---

# 44. Exact Infeasibility

如果 Branch-and-Price 证明：

```text
full implicit integer recourse infeasible
```

则可生成：

```text
schedule no-good
```

注意：

```text
root LP infeasible already足够证明 integer infeasible
```

不必再跑 B&P。

---

# 45. Phase 12 Integrated Solver

建议入口：

```python
solve_benders_with_branch_and_price(...)
```

流程：

```text
Schedule Master
        ↓
root Aircraft/Crew CG
        ↓
LP cuts
        ↓
if integer exactness absent:
    Aircraft/Crew Branch-and-Price
        ↓
exact integer recourse cuts / incumbent
        ↓
Master
```

Passenger 继续 exact PRM。

---

# 46. Why Keep LP Cuts

即使 Phase 12 能得到 exact integer recourse，仍保留 Phase 11 LP cuts：

```text
LP cuts cheap
valid
often enough to close many Schedules
```

Branch-and-Price 只在：

```text
integrality gap
```

出现时触发。

这样 Phase 12 是：

```text
Phase 11 + exact integrality fallback
```

而不是全部推倒重写。

---

# 47. New Integrated Status

建议：

```python
class BendersBranchAndPriceStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"
```

Phase 12 不再把正常可解决 integrality gap 返回：

```text
INTEGRALITY_REQUIRED
```

只有内部 Branch-and-Price 受 node/iteration limit 时：

```text
NOT_CONVERGED
```

---

# 48. Exact Recourse Certificate

建议：

```python
@dataclass(frozen=True)
class IntegerRecourseCertificate:
    schedule_signature
    owner

    lp_objective
    integer_objective

    branch_and_price_status
    nodes_processed
    nodes_pruned_infeasible
    nodes_pruned_bound

    generated_columns
    selected_columns

    implicit_universe_fingerprint
    branching_fingerprint

    exact: bool
```

只有：

```text
status = OPTIMAL
exact = true
```

才可生成 exact integer recourse cut。

---

# 49. Full Enumerator Independence

正式：

```python
solve_aircraft_string_branch_and_price(...)
solve_crew_pairing_branch_and_price(...)
solve_benders_with_branch_and_price(...)
```

不得调用：

```python
generate_aircraft_strings(...)
brute_force_legal_aircraft_strings(...)
generate_crew_pairings(...)
brute_force_legal_crew_pairings(...)
```

必须 monkeypatch 这些函数为：

```text
raise AssertionError
```

formal solvers 仍可运行。

---

# 50. Full Explicit Oracles Remain Tests Only

Phase 12 tests 继续使用：

```text
Phase 5 full Aircraft Strings
Phase 6 full Crew Pairings
Phase 7 Passenger Itineraries
```

建立：

```text
Full binary ARM
Full binary CRM
Full Integrated Oracle
```

作为 Ground Truth。

---

# 51. New Integrated Toy Case

新增：

```text
toy_case_016_benders_branch_and_price
```

理想设计：

```text
one Schedule:
LP recourse fractional and attractive

another Schedule:
higher LP / schedule cost but lower exact integer total

Phase 11:
returns INTEGRALITY_REQUIRED
or cannot certify optimum

Phase 12:
branches
finds exact recourse
closes LB / UB
matches Full Explicit Integrated Oracle
```

这是 Phase 12 最重要的 end-to-end case。

---

# 52. Mandatory Phase 11 → Phase 12 Boundary Test

同一个 toy：

```text
solve_benders_with_column_generation(...)
```

必须得到：

```text
INTEGRALITY_REQUIRED
```

然后：

```text
solve_benders_with_branch_and_price(...)
```

得到：

```text
OPTIMAL
```

并：

```text
OBJ_PHASE12
=
OBJ_FULL_EXPLICIT_INTEGRATED
```

如果没有这个测试，Phase 12 只是在实现未被真正需要的框架。

---

# 53. phase1_benchmark_001

当前 benchmark Phase 11 已：

```text
LB = UB = 18080
```

因此 Phase 12 在该 benchmark 上可能：

```text
0 Branch-and-Price nodes beyond root
```

这是正常的。

Phase 12 benchmark 要求：

```text
Phase12 objective = 18080
Phase12 does not regress Phase11
```

但 Phase 12 的 branching correctness 不能只靠 benchmark 验收，必须依靠专门 integrality toy cases。

---

# 54. Branching Oracle Tests

对于 toy full pools：

### Aircraft

每个 visited branch node：

```text
filtered explicit Aircraft Strings
→ solve LP
```

必须等于：

```text
branch-restricted Aircraft CG node LP
```

最终：

```text
Full explicit binary ARM
=
Aircraft Branch-and-Price
```

### Crew

同理：

```text
filtered full Pairings LP
=
Crew node CG LP
```

最终：

```text
Full explicit binary CRM
=
Crew Branch-and-Price
```

---

# 55. Branch Restriction Negative Tests

必须覆盖：

```text
required + forbidden same Aircraft option

forced String violating forbidden option

required Crew follow-on impossible

forced Pairing violating duty/deadhead rules

branch child with no legal column

parent column filtered incorrectly into child
```

这些情况要：

```text
node INFEASIBLE
```

或明确 input error。

不得静默忽略 branch restriction。

---

# 56. Reduced-Cost Audit Under Branching

Phase 9/10 的：

```text
manual RC == solver RC
```

在 branch node 中仍必须成立。

Branch restrictions 如果通过：

```text
column filtering / pricing universe restriction
```

实现，则不应偷偷增加未进入 reduced-cost evaluator 的 LP rows。

如果未来使用 explicit branch rows，则必须把其 dual contribution 加入 RC。

Phase 12 v1 推荐优先使用：

```text
restricted column universe
```

而不是新 LP branch rows。

---

# 57. Node Warm Start

允许：

```text
parent columns
→ filter
→ child initial pool
```

但第一版不做：

```text
dual warm start
basis warm start
global stabilization
```

正确性优先。

---

# 58. Tree Metrics

每个 fixed-schedule B&P report：

```text
nodes created
nodes solved
nodes infeasible
nodes pruned by bound
integral nodes
max depth

root LP objective
final integer objective
integrality gap

total pricing calls
total Phase-I iterations
total Phase-II iterations

generated columns
reused parent columns
```

---

# 59. Integrated Phase 12 Metrics

至少：

```text
Benders master iterations
visited Schedules

Schedules closed by LP exactness
Schedules requiring Aircraft B&P
Schedules requiring Crew B&P

Aircraft B&P total nodes
Crew B&P total nodes

LP lower-bound cuts
exact integer recourse cuts
feasibility cuts

initial LB
final LB
first UB
final UB
gap
```

---

# 60. Recommended New Files

```text
backend/config/branch_and_price.py

backend/core/aircraft_string_branch_and_price.py
backend/core/crew_pairing_branch_and_price.py
backend/core/benders_branch_and_price.py

data/config/phase12_test_branch_and_price_v1.json
```

Tests：

```text
tests/unit/test_aircraft_string_branch_and_price.py
tests/unit/test_crew_pairing_branch_and_price.py
tests/unit/test_benders_branch_and_price.py

tests/regression/test_phase12_aircraft_integrality.py
tests/regression/test_phase12_crew_integrality.py
tests/regression/test_phase12_benders_branch_and_price.py
tests/regression/test_phase12_branching_oracles.py
tests/regression/test_phase12_benchmark.py
```

Toy cases：

```text
toy_case_014_aircraft_integrality
toy_case_015_crew_integrality
toy_case_016_benders_branch_and_price
```

如可用更少 fixture 覆盖全部核心边界，可合并，但必须保持测试职责清晰。

---

# 61. Existing Files That May Need Minimal Extension

可能需要向后兼容扩展：

```text
backend/core/aircraft_string_pricing.py
backend/core/aircraft_string_column_generation.py

backend/core/crew_pairing_pricing.py
backend/core/crew_pairing_column_generation.py
```

只允许增加：

```text
optional branch restrictions
optional initial column seed
node diagnostics
```

默认调用行为必须保持 Phase 9 / Phase 10 不变。

---

# 62. Stable Files

原则上不要修改：

```text
backend/core/integrated_oracle.py
backend/core/arm.py
backend/core/crm.py
backend/core/prm.py
backend/core/benders.py
backend/core/benders_column_generation.py
backend/schemas/columns.py
```

如果 Phase 12 集成需要复用 Phase 11 helper：

优先：

```text
提取小型 public helper
```

且必须保持所有 Phase 11 regression 不变。

---

# 63. Public API

建议 `backend/core/__init__.py` 新增：

```text
BranchAndPriceStatus

AircraftBranchRestrictions
AircraftBranchAndPriceNode
AircraftBranchAndPriceResult
AircraftBranchAndPriceError
solve_aircraft_string_branch_and_price

CrewBranchRestrictions
CrewBranchAndPriceNode
CrewBranchAndPriceResult
CrewBranchAndPriceError
solve_crew_pairing_branch_and_price

BendersBranchAndPriceStatus
IntegerRecourseCertificate
BendersBranchAndPriceIteration
BendersBranchAndPriceResult
BendersBranchAndPriceError
solve_benders_with_branch_and_price
```

---

# 64. Config API

`backend/config/__init__.py`：

```text
BranchAndPriceConfig
BranchAndPriceConfigError
BranchAndPriceSource
load_branch_and_price_config
```

---

# 65. Assumptions To Add

编号按当前文件继续。

至少记录：

## Aircraft branching

```text
Aircraft-option assignment branching
with exact-string fallback.
```

## Crew branching

```text
Crew-local typed follow-on branching
with typed-leg and exact-pairing fallbacks.
```

## Node pricing

```text
Every node requires pricing convergence in its branch-restricted implicit universe.
```

## Exact recourse

```text
Only Branch-and-Price OPTIMAL integer recourse may generate exact integer Benders cuts.
```

## Passenger

```text
Passenger remains fixed explicit exact MIP in Phase 12 v1.
```

## Scope

```text
Phase 12 v1 remains full-scope only.
```

---

# 66. Implementation Order

严格按以下顺序。

## Step 1 — Phase 11 Closeout

```text
full tests
merge feature/phase-110 → main
post-merge regression
```

## Step 2 — Create Phase 12 Branch

```bash
git switch main
git pull
git switch -c feature/phase-12
```

## Step 3 — Freeze Branching Semantics

先写：

```text
assumptions
branch restriction dataclasses
branch fingerprint
unit tests
```

不先写完整 tree。

## Step 4 — Aircraft Branch-aware CG

扩展 Phase 9：

```text
required/forbidden aircraft-option assignment
forced/forbidden exact String
```

验证：

```text
branch node CG LP
=
filtered full-pool LP
```

## Step 5 — Aircraft Branch-and-Price

实现 tree：

```text
best bound
assignment branching
exact-string fallback
```

验证：

```text
B&P = full ARM MIP
```

## Step 6 — Crew Branch-aware CG

扩展 Phase 10：

```text
typed follow-on
typed-leg
exact Pairing
```

验证 node LP Oracle。

## Step 7 — Crew Branch-and-Price

实现 follow-on tree。

验证：

```text
B&P = full CRM MIP
```

## Step 8 — Integrality Toy Boundary

确保至少一个 case：

```text
LP < integer
```

且实际发生 branching。

## Step 9 — Benders + B&P

新增 Schedule orchestration。

先复用 Phase 11 LP cuts。

仅 integrality gap 时调用 Branch-and-Price。

## Step 10 — Exact Integer Recourse Cuts

使用 B&P proven objective 回灌 current Schedule exact cut。

## Step 11 — Phase11-vs-Phase12 Toy

要求：

```text
Phase 11 = INTEGRALITY_REQUIRED
Phase 12 = OPTIMAL
```

## Step 12 — Full Explicit Integrated Oracle

对拍 Phase 12 objective。

## Step 13 — phase1 Benchmark

确认不回归：

```text
18080
```

## Step 14 — Formal Enumerator Independence

monkeypatch full generators。

## Step 15 — Full Regression

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

## Step 16 — Documentation / Report

更新状态。

---

# 67. Phase 12 Acceptance Criteria

全部满足才可 PASS。

## A. Aircraft Branch-and-Price

- [ ] root 使用 Phase 9 CG；
- [ ] branch restriction 真正进入 pricing universe；
- [ ] assignment branch 0/1 正确；
- [ ] exact String fallback 正确；
- [ ] node CG LP = filtered full-pool LP；
- [ ] B&P exact objective = full explicit ARM MIP；
- [ ] formal solver 不调用 full Aircraft generator。

## B. Crew Branch-and-Price

- [ ] root 使用 Phase 10 CG；
- [ ] typed follow-on branch 正确；
- [ ] OPERATE / DEADHEAD 类型保留；
- [ ] typed-leg fallback 正确；
- [ ] exact Pairing fallback 正确；
- [ ] node CG LP = filtered all-pairings LP；
- [ ] B&P exact objective = full explicit CRM MIP；
- [ ] formal solver 不调用 full Crew generator。

## C. Tree Correctness

- [ ] every node has branch fingerprint；
- [ ] LP bound only from pricing-complete node；
- [ ] infeasible pruning correct；
- [ ] bound pruning correct；
- [ ] integer incumbent only from integral node；
- [ ] best-bound deterministic；
- [ ] max-node limit returns NOT_CONVERGED。

## D. Phase 11 Integration

- [ ] Phase 11 LP cuts retained；
- [ ] LP-integral owner does not invoke unnecessary B&P；
- [ ] LP/integer gap owner invokes B&P；
- [ ] exact B&P objective generates safe exact Schedule cut；
- [ ] binary generated-pool heuristic value alone never generates exact cut。

## E. Integrality Boundary

必须至少一个 test：

```text
Phase 11:
INTEGRALITY_REQUIRED

Phase 12:
OPTIMAL
```

且：

```text
OBJ_PHASE12
=
OBJ_FULL_EXPLICIT_INTEGRATED
```

## F. Passenger

- [ ] PRM remains exact fixed-column MIP；
- [ ] no accidental Passenger CG / branching introduced。

## G. Scope

- [ ] `scope=None` only；
- [ ] non-None scope explicitly rejected。

## H. Regression

- [ ] Phase 8 Benders PASS；
- [ ] Phase 9 Aircraft CG PASS；
- [ ] Phase 10 Crew CG PASS；
- [ ] Phase 11 Benders + CG PASS；
- [ ] Integrated Oracle PASS；
- [ ] full pytest PASS；
- [ ] compileall PASS；
- [ ] git diff --check PASS。

---

# 68. Phase 12 Definition of Done

只有以下链条完整成立：

```text
Aircraft root CG LP
        ↓
branch-compatible Aircraft pricing
        ↓
Aircraft Branch-and-Price
        ↓
exact implicit ARM integer recourse

Crew root CG LP
        ↓
typed follow-on compatible Crew pricing
        ↓
Crew Branch-and-Price
        ↓
exact implicit CRM integer recourse

Schedule Benders
        ↓
LP cuts
        ↓
integrality gap detected
        ↓
exact B&P recourse
        ↓
exact Schedule recourse cuts
        ↓
LB / UB closure
        ↓
Integrated diagnostics
        ↓
Phase 12
=
Full Explicit Integrated Oracle
```

才允许标记 Phase 12 完成。

---

# 69. Phase 12 Report

生成：

```text
docs/codex_reports/
YYYYMMDD_HHMMSS_phase12_integrality_branch_and_price_report.md
```

至少包括：

```text
1. Phase 11 closeout / baseline
2. Modified files
3. Aircraft branching semantics
4. Crew follow-on branching semantics
5. Branch restriction fingerprint
6. Branch-aware pricing changes
7. Node CG Oracle validation
8. Aircraft Branch-and-Price result
9. Crew Branch-and-Price result
10. Integrality-gap toy cases
11. Phase11 INTEGRALITY_REQUIRED → Phase12 OPTIMAL case
12. Benders + B&P architecture
13. Exact integer recourse cut policy
14. Full Explicit Integrated Oracle comparison
15. phase1 benchmark
16. Tree / pricing statistics
17. Enumerator-independence tests
18. Full regression
19. Known limitations
20. Next step
```

---

# 70. Report Required Numbers

至少给出：

```text
Aircraft:
root LP
integer optimum
integrality gap
nodes solved
max depth
columns generated

Crew:
root LP
integer optimum
integrality gap
nodes solved
max depth
Pairings generated

Integrated:
Benders iterations
Schedules visited
Schedules requiring B&P
LP cuts
exact integer cuts
first LB / final LB
first UB / final UB
final gap

Full Oracle objective
Phase 12 objective
difference

pytest passed / failed / skipped
runtime
```

---

# 71. Phase 12 Known Limitations

必须明确：

```text
Full Scope only

Flight Options remain fixed

Passenger Itineraries remain fixed explicit

Aircraft / Crew branch pricing uses current Phase 5/6 legality profiles

Crew still single-duty v1

no production FAR/CCAR rostering

no dynamic RecoveryScope

no Passenger Column Generation

no cross-Schedule global column warm start in correctness baseline

no stabilization / parallel pricing / callback optimization
```

---

# 72. Next Step After Phase 12

如果 Phase 12 exact integrality 闭合完成，下一阶段按总计划应进入：

```text
Phase 13 — Recovered Result Visualization / Solver Integration
```

此时才具备更完整的后端求解链：

```text
Scenario
→ Solve
→ exact/recoverable algorithm result
→ Recovered Result
→ visualization / diagnostics
```

Phase 13 重点不是再修改数学模型，而是：

```text
稳定 Solve API
Recovered Result schema
Original / Disrupted / Recovered 对比
Flight / Aircraft / Crew / Passenger result views
solver diagnostics
runtime / cuts / columns / bounds
```

---

# 73. Final Principle

Phase 12 的唯一核心问题是：

> **Phase 11 已经证明 LP Column Generation 与 Benders lower-bound 组合正确；现在要在不预枚举全部资源列的情况下，把 Aircraft/Crew recourse 的整数性也证明到 exact。**

优先级：

```text
Branch validity
>
branch-compatible pricing completeness
>
integer lower/upper-bound proof
>
full-MIP Oracle equality
>
Benders exact recourse closure
>
runtime
```

任何以下做法都应视为 Phase 12 失败：

```text
用 generated-pool MIP objective 冒充 exact integer recourse

branch restriction 只过滤当前列、不进入 pricing

LP fractional 时直接 rounding

为了跳过 difficult Schedule 使用 no-good

用 full enumerator 作为正式 Branch-and-Price solver 的隐藏依赖
```
