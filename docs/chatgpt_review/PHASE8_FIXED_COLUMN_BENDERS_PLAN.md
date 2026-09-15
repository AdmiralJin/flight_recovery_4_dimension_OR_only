# Phase 8 — Fixed-Column Benders 实施计划

## 1. 阶段定位

Phase 7 已完成并进入 `main`。当前仓库已具备：

```text
Scenario / Recovery Columns
        ↓
SRM / ARM / CRM / PRM
        ↓
Full Integrated Fixed-Column Oracle
        ↓
Recovery Scope
        ↓
Aircraft String Generator
        ↓
Crew Pairing Generator
        ↓
Passenger Itinerary Generator
```

当前稳定候选宇宙为：

```text
Schedule Flight Options
Aircraft Strings
Crew Pairings
Passenger Itineraries
```

Phase 8 的目标不是继续扩大候选宇宙，而是在**完全固定的候选集合**上实现 Schedule Master + ARM/CRM/PRM Subproblems 的 Benders 分解，并证明：

```text
OBJ_Benders == OBJ_Integrated_Oracle
```

Phase 8 是后续 Column Generation 的前置正确性阶段。

本阶段禁止进入 Pricing、Reduced Cost、Column Generation 或 Benders + Column Generation。

---

# 2. 当前仓库基线

开始 Phase 8 前，Codex 必须重新检查当前 `main`，不得直接依赖本计划中的数字。

当前 Phase 7 冻结基线应至少包括：

```text
Phase 1 benchmark:
Schedule x candidates        = 21
Generated Aircraft Strings   = 77
Generated Crew Pairings      = 374
Generated Passenger Itineraries = 55

Integrated Oracle objective  = 18080
Scope-limited objective      = 18080

Phase 7 test baseline:
353 passed
0 failed
0 skipped
```

开始前执行：

```bash
git status
pytest -q
python -m compileall -q backend
git diff --check
```

要求：

```text
working tree clean
0 failed
0 errors
```

如果基线数字已经因后续提交变化，以当前 `main` 为准，并在 Phase 8 report 中记录真实值。

---

# 3. Phase 8 核心目标

实现以下固定列分解：

```text
                 ┌──────────────┐
                 │ SRM Master   │
                 │ x + θA θC θP │
                 └──────┬───────┘
                        │ selected schedule
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
       ARM MIP        CRM MIP        PRM MIP
          │             │             │
          └─────── feasibility / recourse ───────┘
                        │
                        ↓
                 Benders Cuts
                        │
                        └────→ Master
```

其中：

```text
x      = Schedule Flight Option binary variables

θA     = Aircraft recourse lower-bound variable
θC     = Crew recourse lower-bound variable
θP     = Passenger recourse lower-bound variable
```

Master objective：

```text
ScheduleCost(x)
+ θA
+ θC
+ θP
```

Subproblems 继续使用现有：

```text
ARM
CRM
PRM
```

不得复制第二套 aircraft / crew / passenger 数学模型。

---

# 4. Phase 8 的实现类型必须明确

当前：

```text
ARM
CRM
PRM
```

均为 binary MIP。

当前 solver adapter 虽声明支持 LP dual，但 dual 读取仅允许连续 LP solution；不能直接从现有 binary ARM/CRM/PRM MIP 中读取 classical Benders dual multipliers。

因此 Phase 8 v1 应明确实现：

```text
Fixed-Column Logic-Based Benders Baseline
```

而不是声称：

```text
完整复现经典 LP-dual Benders cut
```

Phase 8 v1 使用：

```text
exact schedule no-good feasibility cuts
+
conditional exact-recourse optimality cuts
```

它的目的：

```text
correctness
finite convergence
auditability
Integrated Oracle equivalence
```

不是追求大规模性能。

必须在：

```text
assumptions.md
reproduction_notes.md
Phase 8 Codex report
```

中明确这一边界。

---

# 5. Phase 8 明确不做

本阶段禁止实现：

```text
Flight Pricing
Aircraft String Pricing
Crew Pairing Pricing
Passenger Pricing
Reduced Cost
Column Generation
Benders + Column Generation
Dynamic candidate insertion
Dual stabilization
Trust region
Pareto-optimal cuts
Lazy-constraint callbacks
Gurobi callbacks
Parallel subproblems
Cut bundling heuristics
Cut deletion
Cut strengthening
Warm-start performance engineering
真实航司规则扩展
UI Solve workflow
```

也禁止新增：

```text
Flight Options
Aircraft Strings
Crew Pairings
Passenger Itineraries
```

Phase 8 输入 candidate universe 必须在求解开始前完全冻结。

---

# 6. 必须保持的 Ground Truth

现有：

```text
backend/core/integrated_oracle.py
```

继续作为 Ground Truth。

Phase 8 不得替代 Integrated Oracle。

必须保留：

```text
x = Flight Option
y = Aircraft String
z = Crew Pairing
w = Passenger Itinerary
```

以及现有：

```text
Schedule-Aircraft linking
Schedule-Crew linking
Deadhead-Schedule linking
Passenger-Schedule linking
Seat-Schedule linking
```

Phase 8 最终 incumbent 必须通过现有 Integrated diagnostics 独立复算。

---

# 7. Master / Subproblem 分工

## 7.1 Master 负责

Master 只负责：

```text
Schedule Flight Option selection
SRM local constraints
Scope flight fixes
Aircraft recourse lower bound θA
Crew recourse lower bound θC
Passenger recourse lower bound θP
Accumulated Benders cuts
```

Master 不直接包含：

```text
Aircraft String y
Crew Pairing z
Passenger Itinerary w
```

## 7.2 ARM Subproblem 负责

给定 Master 选择的 operated Flight Options：

```text
required_operated_option_ids
```

ARM 求：

```text
Aircraft String selection
Aircraft coverage
Terminal station
Maintenance
Aircraft cost
```

## 7.3 CRM Subproblem 负责

给定 Master schedule：

```text
Crew Pairing selection
Operate coverage
Deadhead consistency
Crew terminal
Crew cost
```

## 7.4 PRM Subproblem 负责

给定 Master schedule：

```text
Passenger itinerary selection
Schedule consistency
Seat capacity
Passenger delay
Unserved
Passenger cost
```

---

# 8. 必须复用现有 Fixed-Column Models

优先直接复用：

```text
backend/core/srm.py
backend/core/arm.py
backend/core/crm.py
backend/core/prm.py
```

建议：

```text
build_benders_master(...)
```

内部调用：

```text
build_fixed_column_srm(...)
```

建立：

```text
x
SRM constraints
```

然后再增加：

```text
θA
θC
θP
scope fixes
Benders cuts
```

不要复制 SRM-C01～C06。

ARM / CRM / PRM 继续使用现有 request/build/solve contract。

原则上不要修改：

```text
backend/core/srm.py
backend/core/arm.py
backend/core/crm.py
backend/core/prm.py
backend/core/integrated_oracle.py
backend/schemas/columns.py
```

除非测试证明存在真正阻碍 Phase 8 的兼容性缺陷。

若必须修改上述稳定文件，Phase 8 report 必须单独解释：

```text
why
behavior change
regression protection
Integrated Oracle impact
```

---

# 9. 新增配置

建议新增：

```text
backend/config/benders.py
```

公共配置：

```python
FixedColumnBendersConfig
FixedColumnBendersConfigError
BendersImplementationSource
load_fixed_column_benders_config(...)
```

建议字段：

```text
schema_version = "1.0.0"
profile_id

algorithm = "logic_based_fixed_column_benders"

max_iterations

absolute_gap_tolerance
relative_gap_tolerance

enable_arm
enable_crm
enable_prm

source
notes
```

建议 test profile：

```text
data/config/phase8_test_benders_v1.json
```

示意：

```json
{
  "schema_version": "1.0.0",
  "profile_id": "phase8_test_benders_v1",
  "algorithm": "logic_based_fixed_column_benders",
  "max_iterations": 500,
  "absolute_gap_tolerance": 1e-6,
  "relative_gap_tolerance": 1e-9,
  "enable_arm": true,
  "enable_crm": true,
  "enable_prm": true,
  "source": "implementation_assumption",
  "notes": [
    "Correctness-first fixed-column decomposition.",
    "No pricing, reduced cost, or dynamic columns.",
    "Binary recourse is handled with logic-based exact-schedule cuts."
  ]
}
```

Config 必须：

```text
frozen
extra = forbid
strict types
duplicate JSON key rejection
versioned
deterministic
```

---

# 10. 新增核心模块

建议新增：

```text
backend/core/benders.py
```

本阶段先保持单模块，避免过早拆分。

如果文件明显过大，再拆：

```text
backend/core/benders_master.py
backend/core/benders_cuts.py
backend/core/benders.py
```

但不要为了目录美观提前增加无必要抽象。

---

# 11. 建议公共数据结构

至少包含：

```python
class BendersSubproblem(str, Enum):
    ARM = "arm"
    CRM = "crm"
    PRM = "prm"
```

```python
class BendersCutType(str, Enum):
    FEASIBILITY = "feasibility"
    OPTIMALITY = "optimality"
```

```python
@dataclass(frozen=True)
class BendersCut:
    cut_type: BendersCutType
    subproblem: BendersSubproblem | None
    schedule_signature: tuple[str, ...]
    recourse_value: float | None
    big_m: float | None
```

```python
@dataclass(frozen=True)
class BendersIterationRecord:
    iteration: int
    master_objective: float
    lower_bound: float
    incumbent_upper_bound: float | None
    absolute_gap: float | None
    relative_gap: float | None

    schedule_signature: tuple[str, ...]

    arm_status: str
    crm_status: str
    prm_status: str

    arm_objective: float | None
    crm_objective: float | None
    prm_objective: float | None

    feasibility_cuts_added: int
    optimality_cuts_added: int
```

```python
@dataclass(frozen=True)
class FixedColumnBendersResult:
    status: str

    objective_value: float | None
    lower_bound: float | None
    upper_bound: float | None

    iterations: tuple[BendersIterationRecord, ...]
    cuts: tuple[BendersCut, ...]

    x_values: Mapping[str, float]
    y_values: Mapping[str, float]
    z_values: Mapping[str, float]
    w_values: Mapping[str, float]

    selected_flight_options: tuple[str, ...]
    selected_aircraft_strings: tuple[str, ...]
    selected_crew_pairings: tuple[str, ...]
    selected_passenger_itineraries: tuple[str, ...]

    diagnostics: Mapping[str, object]
```

具体字段可按现有项目 style 调整，但必须保证：

```text
结果可序列化
迭代可审计
cut 可审计
最终 incumbent 可独立复算
```

---

# 12. Solver Factory

Benders 每次需要独立求解：

```text
Master
ARM
CRM
PRM
```

公共接口建议接受：

```python
solver_factory: Callable[[], SolverAdapter]
```

例如：

```python
solve_fixed_column_benders(
    scenario,
    columns,
    cost_config,
    passenger_capacity_profile,
    scope,
    config,
    *,
    solver_factory,
)
```

不得在 `benders.py` 中硬编码：

```text
GurobiSolverAdapter()
```

这样测试可使用现有 solver abstraction。

---

# 13. Master 变量

## 13.1 Schedule variables

继续使用：

```text
x[flight_option_id] ∈ {0,1}
```

且保持现有 SRM 语义。

## 13.2 Recourse variables

新增：

```text
θA >= 0
θC >= 0
θP >= 0
```

类型：

```text
continuous
```

下界：

```text
0
```

当前 canonical costs 都是非负，因此零下界有效。

如果以后允许负 recourse cost，必须重新审查 Phase 8 cut validity；本阶段不要预留未经验证的复杂逻辑。

---

# 14. Master Objective

必须严格使用：

```text
min
ScheduleOwnerCost(x)
+ θA
+ θC
+ θP
```

Schedule owner cost 必须继续复用 canonical cost ownership。

不得：

```text
重复计算 aircraft cost
重复计算 crew cost
重复计算 passenger cost
```

不得把 Integrated Oracle 中其他 owner 的成本提前塞入 Master x cost。

---

# 15. Schedule Signature

必须定义稳定公开函数：

```python
schedule_signature(...)
```

建议语义：

```text
按 base flight ID 排序
每个 base flight 记录被选择的唯一 Flight Option ID
```

即：

```text
(
    selected_option_for_F1,
    selected_option_for_F2,
    ...
)
```

要求：

```text
exactly one selected option per base flight
deterministic
independent of dict insertion order
```

不得使用：

```text
Python hash()
set order
solver variable order
```

作为 signature。

该 signature 用于：

```text
cut identity
cache key
iteration diagnostics
duplicate detection
```

---

# 16. Required Operated Option Set

从 Master x 解中派生：

```text
required_operated_option_ids
```

只包含当前被选中的：

```text
revenue OPERATE
```

不包含：

```text
CANCEL
```

是否包含 FERRY 必须严格沿用现有 SRM/ARM/CRM contract；不得自行改变现有 option semantics。

优先复用已有 helper。

---

# 17. ARM / CRM / PRM Request 构造

给定 Master schedule：

```text
x̄
```

必须使用同一 schedule 构造：

```text
AircraftRecoveryRequest
CrewRecoveryRequest
PassengerRecoveryRequest
```

不得三个 subproblem 各自解释 schedule。

建议新增内部 helper：

```python
_build_subproblem_requests_from_schedule(...)
```

确保：

```text
required operated options
selected schedule options
schedule consistency
capacity reference
```

完全一致。

---

# 18. Scope 支持

Phase 8 必须从第一版支持：

```text
scope=None
```

以及：

```text
RecoveryScope
```

不能只做 Full Scope。

---

# 19. Master 的 Scope Fix

现有 Integrated Oracle 对 out-of-scope flights 使用：

```text
x[original_option] = 1
```

Benders Master 必须使用同样语义。

禁止通过删除 out-of-scope base flight 来规避变量。

---

# 20. Subproblem 的 Scope Fix

现有 ARM/CRM/PRM standalone builders 没有直接接收 RecoveryScope。

Phase 8 推荐做法：

对 subproblem 构造一个**scope-restricted RecoveryColumns view**：

```text
scoped owner:
    保留该 owner 的所有 fixed candidates

out-of-scope owner:
    只保留唯一 semantic original candidate
```

适用于：

```text
Aircraft
Crew
Passenger
```

Original candidate 必须通过现有 semantic resolver 解析。

不得依赖 candidate ID 文本命名。

不得修改原始 `RecoveryColumns` 对象。

建议 helper：

```python
build_scope_restricted_columns(...)
```

只供 Phase 8 使用，行为必须有 unit tests。

---

# 21. Candidate Universe 冻结

Phase 8 solve 开始后：

```text
flight_options
aircraft_strings
crew_pairings
passenger_itineraries
```

必须 immutable。

求解过程中禁止：

```text
新增列
删除列
替换列
重建 generator
```

Phase 8 所有 cuts 只对当前 fixed candidate universe 声明有效。

必须新增 assumption：

> Phase 8 cuts are valid only for the immutable fixed-column universe used to derive them.

未来进入 Column Generation 后，不能默认复用 Phase 8 cuts，除非 Phase 10/后续阶段重新证明 cut validity。

---

# 22. Feasibility Cut

如果任一 subproblem 在 schedule `x̄` 下：

```text
INFEASIBLE
```

第一版采用 exact schedule no-good cut。

设：

```text
S(x̄)
```

为每个 base flight 在 `x̄` 中被选中的 option 集合。

若 base flight 数量为：

```text
N
```

加入：

```text
Σ[o ∈ S(x̄)] x[o] <= N - 1
```

由于 SRM-C01 保证每个 base flight 恰选一个 option，因此该 cut：

```text
只排除当前 exact schedule
不排除任何其他 schedule
```

这是 Phase 8 v1 最重要的 correctness-first feasibility cut。

---

# 23. Feasibility Cut 的使用规则

如果：

```text
ARM infeasible
CRM infeasible
PRM infeasible
```

任意一个成立，当前完整 schedule 不可作为 integrated feasible solution。

第一版可以只加入一个：

```text
exact schedule no-good cut
```

不需要对三个 subproblem 重复加相同 no-good cut。

但 diagnostics 必须记录：

```text
ARM status
CRM status
PRM status
```

以及导致 feasibility cut 的 subproblem 集合。

如果为性能考虑选择“发现第一个 infeasible 就停止后续 subproblem”，必须保证：

```text
deterministic subproblem order
```

建议顺序：

```text
ARM
CRM
PRM
```

但为了报告更完整，Phase 8 test profile 推荐三个均求解并记录状态。

---

# 24. Exact Recourse Optimality Cut

如果某 subproblem `k` 在 schedule `x̄` 下：

```text
OPTIMAL
```

记精确 recourse：

```text
Qk(x̄)
```

加入 conditional exact-schedule cut：

```text
θk >= Qk(x̄) - Mk * Δ(x, x̄)
```

其中：

```text
Δ(x, x̄)
=
N - Σ[o ∈ S(x̄)] x[o]
```

于是：

### 当 x = x̄

```text
Δ = 0
θk >= Qk(x̄)
```

### 当 x != x̄

由于每个 base flight 恰选一个 option：

```text
Δ >= 1
```

只要：

```text
Mk >= Qk(x̄)
```

且：

```text
θk >= 0
```

该 cut 对其他 schedule 不产生错误下界。

---

# 25. Optimality Cut 的线性形式

实现时可写为：

```text
θk - Mk * Σ[o ∈ S(x̄)] x[o]
>=
Qk(x̄) - Mk * N
```

必须在 unit test 中直接验证：

```text
在 x̄ 上 cut tight
schedule 改一个 base flight 后 cut 不错误限制 θk >= 0
```

禁止只测试“模型能跑”。

---

# 26. Big-M 的安全构造

Phase 8 v1 不允许手写 magic M。

必须程序化计算 recourse upper bounds。

---

# 27. ARM Big-M

由于每架 aircraft 选择一条 string，且成本非负：

```text
M_ARM
=
Σ_aircraft
max(cost of candidate strings for that aircraft)
```

如果 scope 限制某 aircraft 只有 original string，则使用 restricted universe 中的最大值。

要求：

```text
M_ARM >= any feasible ARM objective
```

---

# 28. CRM Big-M

同理：

```text
M_CRM
=
Σ_crew
max(cost of candidate pairings for that crew)
```

使用当前 scope-restricted candidate universe。

---

# 29. PRM Big-M

每个 Passenger Group 选择一条 itinerary：

```text
M_PRM
=
Σ_pax_group
max(cost of candidate itineraries for that group)
```

使用 canonical passenger owner cost。

必须包含：

```text
UNSERVED
```

等合法候选。

---

# 30. Big-M 验证

新增 unit tests：

```text
M >= all manually enumerated feasible owner-selection objective
M >= current subproblem optimum
M deterministic
M scope-aware
```

如果某 owner 没有 candidate：

```text
raise Phase 8 input validation error
```

不得返回：

```text
M = 0
```

掩盖数据问题。

---

# 31. 为什么 Phase 8 v1 采用该 cut

这是一个：

```text
weak but exact
```

的 finite-schedule decomposition baseline。

它不是为了快。

它保证：

1. infeasible exact schedules 最终会被排除；
2. 每个访问到的 feasible schedule 会得到精确 recourse lower bound；
3. schedule universe 有限；
4. 因此算法有限收敛；
5. 最终结果可以与 Integrated Oracle 对齐。

这是进入 classical/stronger Benders、Pricing 或 CG 前的 correctness reference。

---

# 32. Subproblem Status 规则

Phase 8 v1 只接受：

```text
OPTIMAL
INFEASIBLE
```

对于：

```text
TIME_LIMIT
FEASIBLE but not proven optimal
UNKNOWN
ERROR
```

不得生成 exact optimality cut。

不得把一个未证明最优的 subproblem objective 当作：

```text
Qk(x̄)
```

否则 cut 可能无效。

第一版遇到这些状态应：

```text
返回明确非成功状态
停止 Benders
记录 diagnostics
```

不要悄悄继续。

---

# 33. Master Status 规则

每轮 Master 也必须求到：

```text
OPTIMAL
```

才可把：

```text
master objective
```

作为 valid lower bound。

如果 Master：

```text
TIME_LIMIT
FEASIBLE
UNKNOWN
```

不得宣称：

```text
LB valid
Benders converged
```

Phase 8 v1 直接停止并报告。

---

# 34. Lower Bound

每次 Master optimal 后：

```text
LB_current = Master objective
```

全局：

```text
LB = max(previous LB, LB_current)
```

理论上在 valid cuts 下应单调不下降。

测试和 report 应记录：

```text
LB trajectory
```

允许浮点 tolerance 内微小波动。

---

# 35. Upper Bound

若当前 schedule 的：

```text
ARM
CRM
PRM
```

全部 OPTIMAL，则得到一个完整 integrated feasible candidate。

计算：

```text
UB_candidate
=
ScheduleCost(x̄)
+ Q_ARM(x̄)
+ Q_CRM(x̄)
+ Q_PRM(x̄)
```

全局：

```text
UB
=
min(previous incumbent UB, UB_candidate)
```

保存对应：

```text
x
y
z
w
```

作为 incumbent。

必须独立复算 objective，不得只信 solver reported objective。

---

# 36. Gap

使用：

```text
absolute_gap = UB - LB
```

当 incumbent 存在时：

```text
relative_gap =
absolute_gap / max(1, abs(UB))
```

收敛条件：

```text
absolute_gap <= absolute_gap_tolerance
OR
relative_gap <= relative_gap_tolerance
```

同时必须确认：

```text
incumbent integrated diagnostics PASS
```

---

# 37. Master Infeasible 的处理

若 Master 在累积 cuts 后：

```text
INFEASIBLE
```

### 没有 incumbent

则：

```text
整个 fixed-column integrated problem infeasible
```

### 已有 incumbent

则说明：

```text
所有尚未排除 schedule 已不存在
```

当前 incumbent 为最优。

结果必须明确区分：

```text
OPTIMAL
INFEASIBLE
ABORTED
```

不要统一返回 PASS。

---

# 38. Iteration Loop

推荐严格流程：

```text
initialize cuts = []
initialize incumbent = None
initialize UB = +inf
initialize LB = -inf

for iteration in 1..max_iterations:

    build fresh Master from:
        SRM
        scope fixes
        θ variables
        accumulated cuts

    solve Master to OPTIMAL

    derive schedule signature

    solve ARM
    solve CRM
    solve PRM

    if any subproblem INFEASIBLE:
        add exact schedule feasibility cut
        continue

    require all subproblems OPTIMAL

    compute exact recourse values
    compute candidate UB
    update incumbent

    add conditional recourse optimality cuts
        ARM
        CRM
        PRM

    update LB / UB / gap

    if converged:
        stop OPTIMAL

if max_iterations reached:
    return NOT_CONVERGED
```

---

# 39. Fresh Master vs Mutable Master

Phase 8 v1 推荐：

```text
每轮根据 immutable cut list 重新 build Master
```

而不是：

```text
长期持有一个 solver model 持续 mutation
```

原因：

```text
更容易审计
更容易 deterministic regression
更容易检查 cut set
更少 solver-state 隐式依赖
```

性能优化以后再做。

---

# 40. Cut Deduplication

必须有 deterministic cut key。

建议：

### Feasibility

```text
(
    "feasibility",
    schedule_signature
)
```

### ARM optimality

```text
(
    "optimality",
    "arm",
    schedule_signature
)
```

CRM / PRM 同理。

重复 cut 不再次加入。

---

# 41. Subproblem Cache

推荐但不强制实现 cache。

Key 可使用：

```text
operated schedule semantic signature
+
scope fingerprint
+
candidate universe fingerprint
```

Phase 8 v1 如果实现 cache，必须证明：

```text
cache hit 与重新 solve 的 objective / selected solution audit 一致
```

为了降低复杂度，第一版也可以不做 cache。

如果做，不能只用 iteration number。

---

# 42. Determinism

相同输入下：

```text
iteration schedule sequence
cut sequence
cut IDs
selected incumbent
objective
LB / UB trajectory
```

应尽可能 deterministic。

允许 solver 在多个完全等价 optimum 中选择不同具体 y/z/w，但：

```text
objective
feasibility
diagnostics
semantic invariants
```

必须一致。

测试不要强行要求等价 optimum 下所有 variable vector 完全相同。

---

# 43. Benders Cut ID

若需要 ID，使用 semantic hash：

```text
BEND_F_<hash>
BEND_O_ARM_<hash>
BEND_O_CRM_<hash>
BEND_O_PRM_<hash>
```

hash 输入：

```text
cut type
subproblem
schedule signature
```

不得使用：

```text
iteration index
timestamp
random UUID
```

作为 cut 身份。

---

# 44. 独立 Benders Audit

建议新增：

```python
recompute_benders_solution_audit(...)
```

至少检查：

```text
final x obeys SRM
final y obeys ARM
final z obeys CRM
final w obeys PRM

all integrated linking constraints
scope fixes
seat/schedule coupling

Schedule owner cost
ARM owner cost
CRM owner cost
PRM owner cost

recomputed total objective
reported Benders objective
Integrated diagnostics objective
```

---

# 45. 复用 Integrated Diagnostics

最终 incumbent 产生后，建议：

1. 使用相同：
   ```text
   Scenario
   RecoveryColumns
   Costs
   Passenger Capacity Profile
   RecoveryScope
   ```

2. 构造现有 Integrated model metadata；

3. 把 Benders incumbent：

   ```text
   x_values
   y_values
   z_values
   w_values
   ```

   送入现有：

   ```text
   recompute_integrated_diagnostics(...)
   ```

4. 要求：

   ```text
   all local constraints PASS
   all linking PASS
   objective recomputation PASS
   ```

这一步是 Phase 8 验收的硬条件。

---

# 46. 不要求 selected vector 与 Integrated Oracle 完全相同

若存在多个等价 optimum：

```text
Benders selected y/z/w
```

可能与：

```text
Integrated Oracle selected y/z/w
```

不同。

Phase 8 验收要求：

```text
objective equal
all constraints valid
all costs independently equal/recomputed
```

不要求每个 binary variable 完全相同。

若 schedule x 也存在等价最优解，同样适用。

---

# 47. Unit Tests

建议新增：

```text
tests/unit/test_benders.py
```

至少覆盖：

```text
config strict/frozen/version
duplicate JSON key rejection

schedule signature deterministic
exactly one selected option/base flight validation

scope-restricted candidate view

ARM Big-M
CRM Big-M
PRM Big-M

feasibility cut algebra
optimality cut algebra
cut tightness at visited schedule
cut nonbinding on changed schedule
cut deduplication
cut deterministic identity

master θ lower bounds
master objective ownership
scope x fixes

reject nonoptimal master
reject nonoptimal subproblem
reject invalid candidate universe
```

---

# 48. Feasibility Cut Unit Test

构造两个 base flights：

```text
F1: A / B
F2: C / D
```

visited：

```text
A + C
```

cut：

```text
x_A + x_C <= 1
```

验证：

```text
A + C      rejected
B + C      allowed
A + D      allowed
B + D      allowed
```

不能只测试 visited schedule rejected。

---

# 49. Optimality Cut Unit Test

设：

```text
N = 2
Q = 100
M = 500
visited = A + C
```

cut：

```text
θ - 500(x_A + x_C) >= 100 - 1000
```

验证：

### visited schedule

```text
x_A = 1
x_C = 1
→ θ >= 100
```

### change one flight

```text
x_A = 0
x_C = 1
→ θ >= -400
```

结合：

```text
θ >= 0
```

应保持非约束。

---

# 50. 推荐 dedicated toy case

建议新增：

```text
toy_case_010_fixed_column_benders
```

目标不是大，而是必须让 Benders 真正产生 cuts。

建议设计三个 schedule alternatives：

```text
Schedule A:
lowest SRM cost
but ARM or CRM infeasible

Schedule B:
SRM feasible
all subproblems feasible
but high passenger/crew recourse

Schedule C:
slightly higher SRM cost
lower recourse
integrated optimum
```

这样至少验证：

```text
1 feasibility cut
+
multiple optimality cuts
+
LB/UB convergence
```

---

# 51. toy_case_010 验收

要求：

```text
Integrated Oracle objective = known value
Benders objective = same known value

at least one feasibility cut
at least one optimality cut

LB monotonic nondecreasing
UB monotonic nonincreasing after incumbent exists
final gap <= tolerance

final incumbent Integrated audit = PASS
```

不要把 cut 数量写死到某个不必要的精确值，除非算法顺序已完全 deterministic。

---

# 52. 复用现有 Integrated Oracle Cases

除新 toy 外，Phase 8 应优先复用现有 Phase 3/4 回归场景。

至少检查仓库中的：

```text
toy_case_004
toy_case_005
toy_case_006_scope
```

若实际 fixture 名称略有变化，以仓库现有名称为准。

目标：

### cross-model cases

```text
OBJ_Benders == OBJ_Integrated_Oracle
```

### scope case

```text
OBJ_Benders_full
==
OBJ_Integrated_full

OBJ_Benders_scope
==
OBJ_Integrated_scope
```

并验证 scope fixes。

---

# 53. Scope Oracle Case

`toy_case_006_scope` 或当前等效 scope fixture 必须验证：

```text
scope=None
```

与：

```text
scope=canonical RecoveryScope
```

两条路径。

要求：

```text
objective 保持与 Integrated Oracle 一致
out-of-scope owners 被 original-only 冻结
candidate reduction 仍真实存在
```

主 benchmark 当前会闭包为 Full Scope，不能替代这个测试。

---

# 54. Phase 1 Benchmark Regression

使用 Phase 7 完成后的真实 candidate universe。

预期当前基线：

```text
21 schedule candidates
77 aircraft strings
374 crew pairings
55 passenger itineraries
```

但测试不要硬编码数量作为模型正确性的唯一依据。

核心验收：

```text
Integrated Oracle objective = 18080
Benders objective = 18080
```

如果当前 main 的 objective 已合法变化，以新的 Integrated Oracle ground truth 为准，但必须解释变化来源。

---

# 55. Benchmark 必须记录的 Benders 数据

Phase 8 report 至少记录：

```text
iteration count

initial LB
final LB
initial incumbent UB
final UB
final absolute gap
final relative gap

visited schedule count

feasibility cut count
ARM optimality cut count
CRM optimality cut count
PRM optimality cut count
total unique cuts

ARM solve count
CRM solve count
PRM solve count

final schedule cost
final aircraft cost
final crew cost
final passenger cost
final total objective
```

---

# 56. LB / UB Trajectory

报告中至少给一个紧凑表：

```text
iter | master/LB | ARM | CRM | PRM | candidate UB | incumbent UB | cuts | gap
```

不要只报告：

```text
Benders = 18080
```

必须证明迭代过程与 bounds 合法。

---

# 57. Cut Validity Audit

建议增加程序化 helper：

```python
audit_benders_cut(...)
```

用于测试：

```text
feasibility no-good cut
optimality conditional cut
```

至少可以在 tiny case 对所有 schedule 枚举：

```text
cut 不错误排除其他 feasible schedule
cut 不高估其他 schedule recourse lower bound
```

对 toy 小规模 case 应尽量做 exhaustive validation。

---

# 58. 与 Integrated Oracle 的 Objective Ownership 对齐

Phase 8 必须保持：

```text
SRM owner costs → Master

ARM owner costs → ARM recourse
CRM owner costs → CRM recourse
PRM owner costs → PRM recourse
```

避免：

```text
Schedule delay cost 在 Master 与 PRM 重复
Aircraft reassignment cost 同时进入 x 和 y
Passenger delay 同时进入 Master 和 PRM
```

建议 unit test 直接比较：

```text
Benders decomposed owner cost sum
==
Integrated canonical owner cost
```

---

# 59. Passenger Capacity Contract

继续使用现有：

```text
PassengerCapacityProfile
```

Phase 8 不修改其语义。

PRM 必须继续独立处理：

```text
seat capacity
```

Master 不加入 passenger seat approximation。

否则会改变 Phase 7/Integrated Oracle contract。

---

# 60. Deadhead Contract

CRM 的：

```text
DEADHEAD
```

schedule consistency 必须继续由 CRM subproblem 使用当前 selected schedule 检查。

Master 不新增 duplicated deadhead constraints。

最终 Integrated diagnostics 必须再次验证：

```text
Deadhead → Schedule
```

---

# 61. Aircraft Coverage Contract

ARM 根据 selected operated options 求解：

```text
每个 required operated option exact coverage
```

Master 不添加 aircraft coverage proxy。

否则 Phase 8 就不再是清晰 decomposition。

---

# 62. Scope 与 Cut Validity

一个 cut 只对：

```text
当前 candidate universe
+
当前 scope semantics
+
当前 cost/capacity profile
```

有效。

如果：

```text
scope changed
candidate universe changed
cost profile changed
capacity profile changed
```

必须创建新的 Benders solve state。

不得复用旧 cuts。

Phase 8 v1 不做跨 solve cut persistence。

---

# 63. Input Fingerprint

建议为 diagnostics 生成稳定 fingerprint，至少覆盖：

```text
scenario_id
flight option semantic IDs
aircraft string semantic IDs
crew pairing semantic IDs
passenger itinerary semantic IDs
cost profile ID/version
capacity profile ID/version
scope semantic content
Benders config profile
```

用途：

```text
report
cache safety
future reproducibility
```

不需要实现复杂数据库持久化。

---

# 64. Error Handling

新增：

```python
class FixedColumnBendersError(ValueError):
    ...
```

或项目风格一致的异常类型。

必须明确处理：

```text
invalid candidate universe
missing original scope candidate
missing capacity for passenger-referenced option
duplicate semantic candidate
master nonoptimal status
subproblem nonoptimal/noninfeasible status
invalid Big-M
invalid cut
max iterations exceeded
integrated audit failure
objective mismatch
```

错误信息必须包含：

```text
iteration
schedule signature
subproblem
status/reason
```

---

# 65. Max Iterations

如果达到：

```text
config.max_iterations
```

仍未收敛：

```text
status = NOT_CONVERGED
```

不得自动返回 incumbent 并标记：

```text
OPTIMAL
PASS
```

可以保留 incumbent 供诊断，但 Phase 8 验收不通过。

---

# 66. Public API

Phase 8 完成后，建议 `backend/core/__init__.py` 导出：

```text
BendersSubproblem
BendersCutType
BendersCut
BendersIterationRecord
FixedColumnBendersResult
FixedColumnBendersError

schedule_signature
build_fixed_column_benders_master
solve_fixed_column_benders
recompute_benders_solution_audit
```

`backend/config/__init__.py` 导出：

```text
FixedColumnBendersConfig
FixedColumnBendersConfigError
BendersImplementationSource
load_fixed_column_benders_config
```

名称可按当前项目风格调整，但不要让测试依赖私有 `_...` API。

---

# 67. 推荐新增文件

```text
backend/config/benders.py
backend/core/benders.py

data/config/phase8_test_benders_v1.json

tests/unit/test_benders.py
tests/regression/test_phase8_benders_oracle.py
tests/regression/test_phase8_benders_benchmark.py
```

如需要 dedicated toy：

```text
data/examples/toy_case_010_fixed_column_benders.json
data/columns/toy_case_010_fixed_column_benders_columns.json
```

如果当前项目 toy fixture 主要集中在：

```text
tests/conftest.py
```

则保持现有风格，不强制增加 JSON。

---

# 68. 推荐修改文件

```text
backend/config/__init__.py
backend/core/__init__.py

assumptions.md
reproduction_notes.md

README.md
docs/AIR_HTML_Python_Reproduction_Plan.md

tests/conftest.py     # only if needed
```

Phase 8 开发计划文件建议保存：

```text
docs/chatgpt_review/PHASE8_FIXED_COLUMN_BENDERS_PLAN.md
```

---

# 69. Assumptions 建议新增内容

编号以仓库当前最后编号继续，不要强制使用以下编号。

至少记录：

### Benders Partition

```text
SRM x is Master.
ARM/CRM/PRM are exact fixed-column recourse subproblems.
```

### Binary Recourse Boundary

```text
Current subproblems are MIP.
Phase 8 does not claim classical LP-dual Benders cuts.
```

### Feasibility Cut

```text
Exact schedule no-good cut.
```

### Optimality Cut

```text
Conditional exact-schedule recourse cut with safe owner-specific Big-M.
```

### Fixed Universe

```text
Cuts are valid only for the immutable candidate universe/scope/profile.
```

### Scope

```text
Master and subproblem scope semantics mirror Integrated Oracle.
```

---

# 70. reproduction_notes 更新要求

明确记录：

```text
Phase 8 是工程 correctness decomposition baseline
Integrated Oracle 继续保留
未实现 classical dual cut derivation
未实现 CG
未实现 Benders + CG
```

并记录与论文/原路线的关系：

```text
SRM Master + ARM/CRM/PRM recourse decomposition direction is retained;
cut realization is an implementation extension constrained by the current binary fixed-column subproblem contract.
```

不要声称：

```text
Phase 8 完整复现论文所有 Benders cuts
```

除非未来有明确公式与实现验证。

---

# 71. 实施顺序

必须按以下顺序执行。

## Step 1 — Baseline

```text
inspect current main
run full tests
record Phase 7 baseline
```

## Step 2 — Config

```text
benders.py config
JSON test profile
config tests
```

## Step 3 — Core types

实现：

```text
signature
cut types
iteration/result dataclasses
errors
```

## Step 4 — Scope-restricted views

实现并测试：

```text
flight x fixes
aircraft original-only
crew original-only
passenger original-only
```

## Step 5 — Big-M

实现：

```text
ARM M
CRM M
PRM M
```

并独立测试 upper-bound validity。

## Step 6 — Master

复用 fixed-column SRM：

```text
x
SRM constraints
θ variables
scope fixes
cut application
objective
```

## Step 7 — Subproblem orchestration

使用 selected schedule 构建并求：

```text
ARM
CRM
PRM
```

## Step 8 — Feasibility cut

实现 exact schedule no-good。

## Step 9 — Optimality cuts

实现：

```text
ARM conditional recourse cut
CRM conditional recourse cut
PRM conditional recourse cut
```

## Step 10 — Iteration loop

实现：

```text
LB
UB
incumbent
gap
termination
diagnostics
```

## Step 11 — Independent audit

复用：

```text
Integrated diagnostics
```

## Step 12 — toy_case_010

证明：

```text
feasibility cut
optimality cut
finite convergence
Integrated equality
```

## Step 13 — Existing oracle cases

运行：

```text
toy_case_004
toy_case_005
toy_case_006_scope
```

或当前仓库等效 fixture。

## Step 14 — Phase 1 benchmark

运行完整 Phase 7 candidate universe。

## Step 15 — Full regression

```bash
pytest -q
python -m compileall -q backend
python -m black --check ...
git diff --check
```

## Step 16 — Documentation

更新：

```text
assumptions
reproduction notes
README
master plan
```

## Step 17 — Codex report

生成完整 Phase 8 report。

---

# 72. Phase 8 核心验收标准

全部满足才可标记 PASS。

## A. Baseline

- [ ] Phase 7 main baseline 全测试通过；
- [ ] candidate universe 与报告一致或变化有解释；
- [ ] Integrated Oracle Ground Truth 可重复。

## B. Master

- [ ] 复用现有 SRM；
- [ ] x 语义不变；
- [ ] θA/θC/θP 连续且下界 0；
- [ ] objective owner 无重复；
- [ ] scope flight fixes 与 Integrated 一致。

## C. Subproblems

- [ ] ARM 使用 exact selected schedule；
- [ ] CRM 使用 exact selected schedule；
- [ ] PRM 使用 exact selected schedule；
- [ ] scope-restricted owners 正确；
- [ ] 不复制第二套模型。

## D. Feasibility Cut

- [ ] exact schedule 被排除；
- [ ] 其他 schedule 不被错误排除；
- [ ] duplicate cut 被去重；
- [ ] cut deterministic。

## E. Optimality Cut

- [ ] visited schedule 上 tight；
- [ ] 其他 schedule 上不产生错误 recourse lower bound；
- [ ] ARM/CRM/PRM Big-M 均程序化；
- [ ] 不使用 magic M。

## F. Bounds

- [ ] Master optimal objective 是合法 LB；
- [ ] feasible subproblem组合给出合法 UB；
- [ ] LB 单调不下降；
- [ ] incumbent UB 单调不增加；
- [ ] gap 计算正确。

## G. Status

- [ ] 非 optimal Master 不生成错误 bound；
- [ ] 非 optimal/non-infeasible subproblem 不生成错误 cut；
- [ ] max iteration 不伪装 OPTIMAL；
- [ ] infeasible overall 正确报告。

## H. Oracle Equality

至少：

```text
toy_case_010:
OBJ_Benders == OBJ_Integrated

cross-model toy cases:
OBJ_Benders == OBJ_Integrated

scope toy:
OBJ_Benders_scope == OBJ_Integrated_scope

phase1_benchmark_001:
OBJ_Benders == OBJ_Integrated
```

当前 benchmark 预期：

```text
18080 == 18080
```

## I. Final Incumbent Audit

- [ ] SRM local PASS；
- [ ] ARM local PASS；
- [ ] CRM local PASS；
- [ ] PRM local PASS；
- [ ] Schedule-Aircraft PASS；
- [ ] Schedule-Crew PASS；
- [ ] Deadhead-Schedule PASS；
- [ ] Passenger-Schedule PASS；
- [ ] Seat-Schedule PASS；
- [ ] Scope Fix PASS；
- [ ] Objective recomputation PASS。

## J. Tests

- [ ] Phase 8 unit tests PASS；
- [ ] Phase 8 oracle/regression tests PASS；
- [ ] Full pytest PASS；
- [ ] 0 failed；
- [ ] compileall PASS；
- [ ] Black PASS；
- [ ] git diff --check PASS。

---

# 73. Definition of Done

只有以下完整链条成立，Phase 8 才允许 Completed：

```text
Fixed Phase 7 Candidate Universe
        ↓
SRM Master
        ↓
ARM / CRM / PRM Exact MIP Recourse
        ↓
Exact Schedule Feasibility Cuts
        ↓
Conditional Exact-Recourse Optimality Cuts
        ↓
Valid LB / UB
        ↓
Finite Convergence
        ↓
Final Incumbent
        ↓
Integrated Diagnostics PASS
        ↓
OBJ_Benders == OBJ_Integrated_Oracle
        ↓
Scope Regression PASS
        ↓
Full Test Suite PASS
```

以下任何一个单独成立都不能结束 Phase 8：

```text
Benders 能迭代
Solver 返回 OPTIMAL
Benchmark objective 看起来接近
有 incumbent
某一个 toy case 通过
```

---

# 74. Phase 8 Codex Report

在：

```text
docs/codex_reports/
```

生成：

```text
YYYYMMDD_HHMMSS_phase8_fixed_column_benders_report.md
```

必须包括：

```text
1. Baseline / Phase 7 Status
2. Modified Files
3. Benders Architecture
4. Why Logic-Based Fixed-Column Baseline
5. Config Contract
6. Master Definition
7. ARM/CRM/PRM Subproblem Contracts
8. Scope Handling
9. Feasibility Cut Definition
10. Optimality Cut Definition
11. Big-M Derivation
12. Bound / Gap Definition
13. toy_case_010 Result
14. Existing Oracle Case Results
15. Scope Regression
16. Phase 1 Benchmark Result
17. Iteration / Cut Statistics
18. LB / UB Trajectory
19. Final Integrated Audit
20. Full Test Result
21. Known Limitations
22. Deferred Work
23. Next Recommended Step
```

报告必须给具体数字。

---

# 75. Report 至少输出以下表格

## Benchmark summary

```text
Integrated objective
Benders objective
difference
iterations
visited schedules
feasibility cuts
ARM optimality cuts
CRM optimality cuts
PRM optimality cuts
final LB
final UB
absolute gap
relative gap
```

## Final owner costs

```text
Schedule
Aircraft
Crew
Passenger
Total
```

## Test summary

```text
pytest passed
failed
skipped
compileall
Black
git diff --check
```

---

# 76. Phase 8 完成后的下一阶段

Phase 8 通过后，不要立即把所有 Column Generation 一次性加入。

推荐下一阶段：

```text
Phase 9 — Flight / Aircraft String Column Generation
```

或严格遵循仓库现有总计划中的 Phase 编号。

进入下一阶段前必须冻结：

```text
Integrated Oracle = Ground Truth
Fixed-Column Benders = Decomposition Ground Truth
```

后续任何 Pricing / Column Generation 都必须分别与这两个基线比较。

---

# 77. 最终原则

Phase 8 只解决：

> 在固定 Flight Options、Aircraft Strings、Crew Pairings 和 Passenger Itineraries 下，能否把现有 integrated x/y/z/w MIP 正确分解为 Schedule Master + ARM/CRM/PRM recourse，并得到与 Integrated Oracle 完全一致的最优目标。

本阶段不解决：

> 如何通过 dual pricing 动态生成列、如何提高真实规模性能、如何将 Benders 与 Column Generation 联合。

因此 Phase 8 优先级始终是：

```text
correctness
> auditability
> reproducibility
> decomposition equivalence
> performance
```

任何为了减少 iteration 或加速求解而削弱 Integrated Oracle 对齐、cut validity 或 independent audit 的修改，都不属于 Phase 8。
