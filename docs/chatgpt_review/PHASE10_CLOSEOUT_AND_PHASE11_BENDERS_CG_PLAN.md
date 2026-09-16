# Phase 10 Closeout & Phase 11 Benders + Column Generation Plan

## 1. Phase 10 Review Conclusion

**Phase 10 可以收尾并合并。当前未发现阻断性问题。**

当前 `feature/phase-10` 已完成：

```text
Fixed Schedule
    ↓
Crew All-Pairings LP Oracle
    ↓
Restricted Crew Master LP
    ↓
Phase I artificial feasibility
    ↓
LP dual / reduced-cost audit
    ↓
OPERATE / DEADHEAD typed-DAG pricing
    ↓
Phase II Column Generation
    ↓
full-pool omitted-column termination audit
```

已核对核心实现：

```text
backend/core/crew_pairing_master.py
backend/core/crew_pairing_pricing.py
backend/core/crew_pairing_column_generation.py
```

当前实现保持：

- Crew Pairing LP 变量 `z` 为 continuous；
- LP rows 与 CRM 的 pairing selection、required OPERATE coverage、nonrequired OPERATE/DEADHEAD prohibition、terminal ownership 对齐；
- Phase I real Pairing objective coefficient 为 `0`，人工变量负责恢复 LP feasibility；
- Phase II 使用 canonical Crew owner cost；
- formal pricer 只使用当前 fixed Schedule 的 required revenue Flight Options；
- OPERATE 与 DEADHEAD 在 operating coverage 中严格区分；
- qualification、MCT、duty、deadhead limit、duplicate option/base Flight 等继续复用 Phase 6 legality；
- priced Pairing 再次通过 independent legality validator；
- formal CG 不需要 full Pairing pool；
- Scope 外 Crew 使用 semantic original Pairing；
- input fingerprint、`OPTIMAL / INFEASIBLE / NOT_CONVERGED / ABORTED` 状态均已实现。

当前 README 记录的关键结果：

```text
toy_case_012:
initial long-deadhead pool objective = 300
Crew CG objective = 150

phase1_benchmark_001:
full Pairings = 374
final CG Pairings = 34
OBJ_CREW_CG_LP = OBJ_ALL_PAIRINGS_LP = 0

omitted Pairings = 340
minimum omitted reduced cost = 0
```

仓库总计划也已将 Phase 10 标记为完成，并将下一阶段设为：

```text
Phase 11 — Benders + Column Generation
```

---

## 2. Phase 10 Non-blocking Notes

### 2.1 Pricing 仍是 correctness-first resource-state traversal

当前 typed-DAG pricer 已脱离 Phase 6 full enumerator，但仍以显式 path/resource traversal 为主。

准确表述：

```text
Phase 10 已验证 Crew Pairing pricing / CG 数学正确性
≠
已经完成生产规模高性能 Crew RCSP pricing
```

性能优化后移。

### 2.2 Phase 6 v1 Legality 继续是边界

当前 Crew legality 仍是：

```text
single duty
OPERATE / DEADHEAD
qualification
MCT
max duty
deadhead limit
terminal station
```

不代表真实 FAR/CCAR 全量 duty/rest/roster 规则。

---

# 3. Phase 10 Closeout

在 `feature/phase-10`：

```bash
git status
pytest -q
python -m compileall -q backend
git diff --check
```

如果项目当前继续使用 Black：

```bash
python -m black --check <Phase10 Python files>
```

要求：

```text
working tree clean
0 failed
0 errors
```

确认以下内容均已提交：

```text
backend/config/crew_pairing_column_generation.py

backend/core/crew_pairing_master.py
backend/core/crew_pairing_pricing.py
backend/core/crew_pairing_column_generation.py

data/config/phase10_test_crew_pairing_cg_v1.json

tests/unit/test_crew_pairing_master.py
tests/unit/test_crew_pairing_pricing.py
tests/unit/test_crew_pairing_column_generation.py

Phase 10 oracle / regression / benchmark tests
toy_case_012 related fixture/data

README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/codex_reports/<latest_phase10_report>.md
```

---

# 4. Merge Phase 10

```bash
git switch main
git pull
git merge --no-ff feature/phase-10
```

合并后：

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
git switch -c feature/phase-11
```

确认远端 `main` 已包含 Phase 10 后，可删除 Phase 10 开发分支。

---

# 5. Phase 10 Freeze

Phase 11 不得为了 Benders + CG 随意修改以下已独立验证的合同：

```text
Phase 9 Aircraft Full-Column LP
Phase 9 Aircraft Phase I / Phase II
Phase 9 Aircraft reduced-cost formula
Phase 9 Aircraft pricing legality
Phase 9 Aircraft CG termination

Phase 10 Crew All-Pairings LP
Phase 10 Crew Phase I / Phase II
Phase 10 Crew reduced-cost formula
Phase 10 OPERATE / DEADHEAD semantics
Phase 10 Crew pricing legality
Phase 10 Crew CG termination
```

Phase 9 / 10 继续作为独立 CG Ground Truth。

---

# 6. Phase 11 Objective

Phase 11 目标：

> **将 Phase 8 的 Schedule Benders 与 Phase 9 Aircraft String CG、Phase 10 Crew Pairing CG 正确组合，并在小规模实例上证明 Benders + CG 与 Full Explicit-Column Integrated Oracle 得到一致的数学结论。**

Phase 11 的核心验收：

```text
OBJ_BENDERS_CG
=
OBJ_SMALL_SCALE_FULL_COLUMN_INTEGRATED_ORACLE
```

当前 `phase1_benchmark_001` 的 Full Integrated Ground Truth 仍应为：

```text
18080
```

如果当前 main 的 full explicit Oracle 合法变化，以运行时 Oracle 为准。

---

# 7. Phase 11 Is Not Phase 8 with Two Function Replacements

禁止简单修改：

```text
Phase 8 ARM MIP
→ Phase 9 Aircraft CG

Phase 8 CRM MIP
→ Phase 10 Crew CG
```

然后沿用旧 cuts。

原因：

Phase 8 的 cuts 基于：

```text
immutable explicit candidate universe
+
exact binary MIP recourse
```

Phase 11 的 Aircraft / Crew recourse 来自：

```text
implicit column universe
+
LP Column Generation
+
dynamically discovered columns
```

两者 cut validity contract 不同。

---

# 8. Phase 11 v1 Scope Boundary

**Phase 11 v1 正式 solver 只支持：**

```text
scope = None
```

即 Full Scope。

如果传入：

```text
RecoveryScope
```

第一版应明确：

```text
UNSUPPORTED_DYNAMIC_SCOPE
```

或抛出专用异常。

原因：

当前 Phase 4 `RecoveryScope` 是基于已验证的 fixed RecoveryColumns universe 做 closure，并包含 candidate IDs。Phase 11 会动态发现新的 Aircraft Strings / Crew Pairings；在没有重新证明 dynamic-scope closure 完整性前，不能直接沿用旧 fixed-column Scope。

---

# 9. Phase 11 Architecture

```text
                   SRM Master
             x + thetaA + thetaC + thetaP
                         ↓
                selected Schedule x̄
                         ↓
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
 Aircraft CG LP      Crew CG LP       PRM exact MIP
 Phase 9             Phase 10          fixed itineraries
        ↓                ↓                ↓
 qA_LP / infeas     qC_LP / infeas    qP_exact / infeas
        ↓                ↓                ↓
     valid recourse lower-bound / feasibility certificates
                         ↓
                 Benders CG Cuts
                         ↓
                      Master
```

同时对可行 Schedule 构造 integer incumbent：

```text
Aircraft CG columns
        ↓
exact binary ARM on generated pool

Crew CG columns
        ↓
exact binary CRM on generated pool

fixed Passenger Itineraries
        ↓
exact PRM
```

---

# 10. LP Recourse Semantics

对 minimization recourse：

```text
Q_A_LP(x) <= Q_A_MIP(x)
Q_C_LP(x) <= Q_C_MIP(x)
```

Phase 9 / 10 CG 在 pricing 收敛后得到的是完整隐式列空间下的 LP optimum，而不是临时 Restricted Master objective。

因此：

```text
Q_A_LP(x̄)
Q_C_LP(x̄)
```

可以作为 full integer recourse 的合法下界。

---

# 11. Critical Cut Validity Policy

## Rule 1 — Never import Phase 8 cuts

Phase 11 solve：

```text
cuts = empty
```

不得直接复用历史 Phase 8 fixed-column cuts。

## Rule 2 — Restricted RMP objective cannot create a permanent cut

Aircraft / Crew CG 尚未完成 pricing convergence 前：

```text
RMP objective
```

不得生成永久 Benders cut。

## Rule 3 — Only pricing-certified full-LP values may create ARM/CRM cuts

只有：

```text
Aircraft CG status = OPTIMAL
Crew CG status = OPTIMAL
```

且 pricing 已证明无负 reduced-cost column 后，才允许：

```text
qA_LP
qC_LP
```

进入 Benders cut。

## Rule 4 — Restricted-pool infeasibility is not a schedule infeasibility certificate

当前 ARM/CRM restricted pool infeasible 时，不得直接 no-good。

只有 Phase I CG 完整 pricing 后仍：

```text
artificial objective > epsilon
+
no improving real column
```

才说明 full implicit LP infeasible。

LP infeasible ⇒ MIP infeasible，因此此时 schedule no-good 安全。

## Rule 5 — Passenger recourse remains exact fixed-universe MIP

Passenger Itineraries 继续是固定 explicit universe。

因此：

```text
PRM exact MIP infeasible
```

可安全 no-good；

```text
PRM exact objective
```

可用于 exact recourse cut。

## Rule 6 — Explicit pool growth does not invalidate a pricing-certified full-LP cut

后续新增显式列只是把同一隐式 universe 的列 materialize。

如果 cut 已由完整 pricing 证明为 full-LP optimum，则无需因 pool size 增长而失效。

## Rule 7 — Implicit-universe contract changes invalidate all cuts

以下任一变化：

```text
Scenario
Flight Options
Cost Config
Passenger Capacity Profile
Aircraft String Generation Config
Crew Pairing Generation Config
Aircraft CG Config
Crew CG Config
Passenger Itineraries
Phase 11 Config
scope mode
```

必须：

```text
invalidate all Phase 11 cuts
restart solve
```

---

# 12. Implicit Universe Fingerprint

新增：

```python
benders_cg_implicit_universe_fingerprint(...)
```

至少覆盖：

```text
Scenario semantic content
Flight Options semantic content
Passenger Itinerary semantic content
Cost Config
Passenger Capacity Profile
FlightStringGenerationConfig
CrewPairingGenerationConfig
AircraftStringColumnGenerationConfig
CrewPairingColumnGenerationConfig
Phase11 Config
scope mode
```

不要把当前动态 Aircraft String / Crew Pairing ID 列表放入该 fingerprint。

另行记录：

```text
aircraft_pool_fingerprint
crew_pool_fingerprint
```

仅用于 diagnostics。

---

# 13. New Phase 11 Cut Model

建议新增：

```python
class BendersCgCutSource(str, Enum):
    AIRCRAFT_FULL_LP = "aircraft_full_lp"
    CREW_FULL_LP = "crew_full_lp"
    PASSENGER_EXACT_MIP = "passenger_exact_mip"
    AIRCRAFT_LP_INFEASIBILITY = "aircraft_lp_infeasibility"
    CREW_LP_INFEASIBILITY = "crew_lp_infeasibility"
    PASSENGER_MIP_INFEASIBILITY = "passenger_mip_infeasibility"
```

以及：

```python
@dataclass(frozen=True)
class BendersCgCut:
    cut_type
    subproblem
    schedule_signature
    recourse_lower_bound
    conditional_m
    source
    implicit_universe_fingerprint
    certificate_id
```

每个 cut 必须携带 provenance。

---

# 14. Schedule Signature

继续复用 Phase 8：

```python
schedule_signature(...)
```

不建立第二套 Schedule identity。

---

# 15. Master

继续：

```text
SRM x
+
thetaA
+
thetaC
+
thetaP
```

objective：

```text
ScheduleCost(x)
+
thetaA
+
thetaC
+
thetaP
```

Master 不包含：

```text
Aircraft String y
Crew Pairing z
Passenger Itinerary w
```

---

# 16. Reuse Phase 8 Carefully

优先复用与 candidate universe 无关的公共部分：

```text
schedule_signature
SRM master semantics
theta variables
schedule no-good algebra
conditional schedule-cut algebra
LB / UB / gap helpers
```

但必须保证：

```text
solve_fixed_column_benders(...)
```

行为完全不变。

如果安全重构风险较高，则新建：

```text
backend/core/benders_column_generation.py
```

独立实现 orchestration。

---

# 17. Aircraft Recourse

给定 Master Schedule：

```text
required_operated_option_ids
```

调用：

```python
solve_aircraft_string_column_generation(...)
```

### OPTIMAL

得到：

```text
qA_LP
generated Aircraft String pool
CG diagnostics
```

### INFEASIBLE

得到 full implicit LP infeasibility certificate，可 no-good。

### NOT_CONVERGED / ABORTED

Phase 11 不得生成 cut，直接返回非成功状态。

---

# 18. Crew Recourse

调用：

```python
solve_crew_pairing_column_generation(...)
```

规则与 Aircraft 相同。

---

# 19. Passenger Recourse

继续调用：

```python
solve_fixed_column_prm(...)
```

使用 fixed Passenger Itineraries。

### OPTIMAL

得到：

```text
qP_exact
```

### INFEASIBLE

当前 Schedule 可安全 no-good。

其他状态：

```text
ABORT
```

---

# 20. Feasibility Cut

如果以下任一成立：

```text
Aircraft CG certified INFEASIBLE
Crew CG certified INFEASIBLE
PRM exact MIP INFEASIBLE
```

则加入 exact schedule no-good：

```text
Σ[o ∈ S(x̄)] x[o]
<=
N - 1
```

同一 Schedule 只加入一个 no-good cut。

---

# 21. ARM / CRM Lower-Bound Cut

对于 pricing-certified LP optimum：

```text
qk = Qk_LP(x̄)
```

使用：

```text
theta_k
>=
qk - Mk * Δ(x, x̄)
```

其中：

```text
Δ(x, x̄)
=
N - Σ[o ∈ S(x̄)] x[o]
```

推荐：

```text
Mk = qk
```

因为：

```text
theta_k >= 0
qk >= 0
```

在 visited Schedule 上：

```text
theta_k >= qk
```

其他 Schedule 上 RHS ≤ 0，不产生错误约束。

---

# 22. Passenger Cut

PRM 使用 exact MIP recourse：

```text
qP = QP_MIP(x̄)
```

同样使用：

```text
MP = qP
```

构造 conditional cut。

---

# 23. Restricted Binary Recourse Cannot Become a Lower-Bound Cut Automatically

Aircraft / Crew CG 完成后，在 generated columns 上解：

```text
binary ARM
binary CRM
```

得到：

```text
Q_A_RMIP
Q_C_RMIP
```

它们是 full implicit MIP recourse 的 upper bounds，不是天然 lower bounds。

禁止直接生成：

```text
thetaA >= Q_A_RMIP
thetaC >= Q_C_RMIP
```

除非另有 exactness certificate。

---

# 24. Integer Incumbent

对可行 Schedule：

### Aircraft

在 CG returned columns 上调用：

```python
solve_fixed_column_arm(...)
```

### Crew

在 CG returned Pairings 上调用：

```python
solve_fixed_column_crm(...)
```

### Passenger

使用 exact PRM result。

如果三者均可行，则形成 integrated feasible candidate：

```text
x + y + z + w
```

用于更新：

```text
UB
```

---

# 25. Why Generated-Pool Binary Solution Is a Safe UB

动态 generated pool 是完整隐式 universe 的合法子集。

因此：

```text
Q_full_MIP
<=
Q_generated_pool_MIP
```

只要 generated-pool binary solution 可行，它就是 full problem 中真实可行方案。

所以可安全用于 UB。

---

# 26. Integer Exactness Certificate

如果某 owner：

```text
CG full-LP lower bound
=
generated-pool binary MIP objective
```

在 tolerance 内成立，则：

```text
Q_LP
<=
Q_full_MIP
<=
Q_generated_MIP
=
Q_LP
```

因此：

```text
Q_full_MIP
=
Q_LP
=
Q_generated_MIP
```

记录：

```text
aircraft_integrality_certified
crew_integrality_certified
```

---

# 27. Integrality Gap Is a Phase 12 Boundary

若：

```text
Q_generated_MIP
>
Q_CG_LP
```

不说明 Phase 9/10 错误。

它表示：

```text
LP relaxation
vs
integer recourse
```

存在 gap，或 integer optimum 需要 LP pricing 不一定生成的非负-RC列。

这属于：

```text
Phase 12 — Integrality / Branching
```

---

# 28. New Phase 11 Status

建议：

```python
class BendersCgStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    INTEGRALITY_REQUIRED = "integrality_required"
    ABORTED = "aborted"
```

---

# 29. INTEGRALITY_REQUIRED

以下情形不得加无效 cut 强行推进：

```text
Master 再次选择同一 Schedule
该 Schedule 的 full-LP cuts 已存在
没有新的 valid lower-bound cut
LB < incumbent UB
Aircraft/Crew integer recourse 未能与 LP lower bound 对齐
```

此时：

```text
status = INTEGRALITY_REQUIRED
```

---

# 30. Bounds

## Lower Bound

每轮 Master optimal：

```text
LB_current = Master objective
LB = max(previous LB, LB_current)
```

Aircraft/Crew theta 只能由 pricing-certified full-LP lower-bound cuts 约束。

## Upper Bound

只从完整 integer feasible candidate 更新：

```text
UB_candidate
=
ScheduleCost
+
binary ARM cost
+
binary CRM cost
+
exact PRM cost
```

```text
UB = min(previous UB, UB_candidate)
```

---

# 31. Convergence

允许返回：

```text
OPTIMAL
```

仅当：

```text
UB exists
absolute_gap <= tolerance
or
relative_gap <= tolerance
```

并且：

```text
final incumbent Integrated diagnostics PASS
```

---

# 32. Full Explicit Oracle

Phase 11 correctness tests 必须继续保留：

```text
Phase 5 full Aircraft Strings
+
Phase 6 full Crew Pairings
+
Phase 7 Passenger Itineraries
        ↓
Integrated Fixed-Column Oracle
```

得到：

```text
OBJ_FULL_EXPLICIT_INTEGRATED
```

最终要求：

```text
OBJ_BENDERS_CG
=
OBJ_FULL_EXPLICIT_INTEGRATED
```

---

# 33. Formal Phase 11 Solver Must Not Call Full Enumerators

正式：

```python
solve_benders_with_column_generation(...)
```

不得调用：

```python
generate_aircraft_strings(...)
brute_force_legal_aircraft_strings(...)
generate_crew_pairings(...)
brute_force_legal_crew_pairings(...)
```

Full enumerators 只允许：

```text
Oracle
audit
tests
report
```

必须有 monkeypatch independence test。

---

# 34. Passenger Itineraries Remain Explicit

Phase 11 不实现 Passenger CG。

准确表述：

> Phase 11 dynamically generates Aircraft Strings and Crew Pairings only; Passenger Itineraries remain fixed explicit columns.

---

# 35. Phase 11 Config

建议新增：

```text
backend/config/benders_column_generation.py
```

至少字段：

```text
schema_version = "1.0.0"
profile_id
max_benders_iterations
absolute_gap_tolerance
relative_gap_tolerance
integrality_tolerance
require_full_scope = true
source
notes
```

Phase 9 / 10 pricing 参数不复制到 Phase 11 Config。

---

# 36. Suggested Core Module

新增：

```text
backend/core/benders_column_generation.py
```

第一版优先单文件 orchestration。

---

# 37. Suggested Public Structures

建议至少：

```text
BendersCgStatus
BendersCgCutSource
BendersCgCut
BendersCgRecourseCertificate
BendersCgIteration
BendersCgResult
BendersColumnGenerationError
```

`BendersCgRecourseCertificate` 至少记录：

```text
schedule_signature

aircraft_cg_status
aircraft_lp_objective
aircraft_column_count
aircraft_binary_status
aircraft_binary_objective
aircraft_integrality_certified

crew_cg_status
crew_lp_objective
crew_column_count
crew_binary_status
crew_binary_objective
crew_integrality_certified

prm_status
prm_objective
```

---

# 38. Iteration Record

每轮至少记录：

```text
iteration
schedule_signature

master objective
LB
candidate UB
incumbent UB
absolute gap
relative gap

Aircraft CG status / LP objective / columns / binary objective
Crew CG status / LP objective / columns / binary objective
PRM status / objective

cuts added by type
total cuts
runtime
```

---

# 39. Cut Deduplication

Cut semantic identity：

```text
cut type
owner/subproblem
schedule signature
implicit universe fingerprint
```

不要使用：

```text
iteration number
pool size
timestamp
```

---

# 40. Revisited Schedule Consistency

相同 implicit universe + 相同 Schedule 再次 CG 求解时：

```text
Q_LP
```

应在 tolerance 内保持一致。

如果变化超过 tolerance：

```text
ABORT
```

说明先前 cut validity 或 CG convergence 有问题。

---

# 41. Candidate Pool Policy

Phase 11 v1 推荐：

```text
每个 Schedule 独立调用 Phase 9 / Phase 10 CG
```

先不实现跨 Schedule global warm-start pool。

这样更容易证明：

```text
cut provenance
schedule compatibility
determinism
```

---

# 42. Temporary RecoveryColumns

对一个 Schedule：

```text
flight_options:
    fixed existing Flight Options

aircraft_strings:
    Aircraft CG returned columns

crew_pairings:
    Crew CG returned columns

passenger_itineraries:
    fixed Phase 7 universe
```

用于：

```text
binary ARM
binary CRM
final incumbent diagnostics
```

不要修改 baseline RecoveryColumns。

---

# 43. Final Integrated Audit

最终 incumbent：

```text
x
y
z
w
```

必须进入现有：

```python
recompute_integrated_diagnostics(...)
```

检查：

```text
SRM local
ARM local
CRM local
PRM local
Schedule-Aircraft
Schedule-Crew
Deadhead-Schedule
Passenger-Schedule
Seat-Schedule
objective recomputation
```

全部 PASS。

---

# 44. New Toy Case

建议新增：

```text
toy_case_013_benders_column_generation
```

至少有：

```text
Schedule A:
lowest schedule cost
Aircraft CG Phase I certifies infeasible

Schedule B:
feasible
Aircraft/Crew pricing必须加列
recourse expensive

Schedule C:
slightly higher schedule cost
CG finds cheaper resource recovery
global integrated optimum
```

至少一个 Schedule 要同时触发：

```text
Aircraft CG
Crew CG
```

---

# 45. toy_case_013 Mandatory Assertions

```text
Benders iterations >= 2

Aircraft CG invoked
Crew CG invoked

at least one dynamically generated Aircraft String
at least one dynamically generated Crew Pairing

at least one valid Benders cut

final LB = UB

OBJ_BENDERS_CG
=
OBJ_FULL_EXPLICIT_INTEGRATED
```

并证明 formal solver 不调用 full enumerators。

---

# 46. Cut Validity Negative Tests

## Test A — Restricted RMP cut forbidden

```text
Aircraft RMP objective = 300
pricing later finds column
full LP objective = 0
```

不得提前保存：

```text
thetaA >= 300
```

## Test B — Restricted pool infeasible is not no-good

initial pool infeasible，但 pricing 可生成 feasible String/Pairing。

不得 no-good。

## Test C — Phase I certified infeasible may no-good

完整 pricing 后仍 artificial > 0，允许 no-good。

## Test D — Universe fingerprint changes

修改：

```text
cost
Flight Option
legality config
CG config
capacity
```

旧 cuts 必须拒绝。

## Test E — Explicit pool growth

同一 implicit universe 内增加 legal explicit column，pricing-certified full-LP cut 保持有效。

---

# 47. LP / Integer Gap Test

构造：

```text
CG LP objective
<
generated-pool binary objective
```

验证：

```text
LP value only used for LB cut
binary value only used for UB
```

若无法闭合：

```text
INTEGRALITY_REQUIRED
```

---

# 48. Existing Regressions

Phase 11 任何修改后必须继续：

```text
Phase 8 Benders PASS
Phase 9 Aircraft CG PASS
Phase 10 Crew CG PASS
Phase 3 Integrated Oracle PASS
```

---

# 49. Full Explicit Integrated Oracle

Phase 11 Oracle tests 使用：

```text
existing Flight Options
Phase 5 full Aircraft Strings
Phase 6 full Crew Pairings
Phase 7 Passenger Itineraries
```

最终 Ground Truth 仍是：

```python
solve_integrated_fixed_column_oracle(...)
```

不是 Phase 8 Benders。

---

# 50. phase1_benchmark_001

Oracle side：

```text
77 Aircraft Strings
374 Crew Pairings
55 Passenger Itineraries
Full Integrated Oracle
```

Formal Phase 11 side：

```text
no full Aircraft String pool input
no full Crew Pairing pool input

Schedule Benders
+
Aircraft CG
+
Crew CG
+
fixed Passenger Itineraries
```

要求：

```text
OBJ_BENDERS_CG
=
OBJ_FULL_EXPLICIT_INTEGRATED
```

当前预期：

```text
18080
```

---

# 51. Metrics

Phase 11 report 至少记录：

```text
Benders iterations
unique visited Schedules

Aircraft CG calls
Aircraft Phase-I / Phase-II iterations
Aircraft generated columns

Crew CG calls
Crew Phase-I / Phase-II iterations
Crew generated Pairings

feasibility cuts
Aircraft LP lower-bound cuts
Crew LP lower-bound cuts
Passenger exact cuts

initial LB
final LB
first feasible UB
final UB
absolute gap
relative gap

Schedule cost
Aircraft integer cost
Crew integer cost
Passenger cost
Total
```

---

# 52. Formal Independence Test

Formal Phase 11 test 中 monkeypatch：

```text
generate_aircraft_strings → raise
brute_force_legal_aircraft_strings → raise
generate_crew_pairings → raise
brute_force_legal_crew_pairings → raise
```

`solve_benders_with_column_generation(...)` 仍应正常完成 toy case。

---

# 53. Error Handling

新增：

```python
class BendersColumnGenerationError(ValueError):
    ...
```

至少处理：

```text
scope != None
implicit universe fingerprint changed
Aircraft CG ABORTED
Crew CG ABORTED
Aircraft CG NOT_CONVERGED
Crew CG NOT_CONVERGED
Master nonoptimal
PRM unexpected status
invalid cut provenance
same Schedule full-LP value changed
illegal generated column
final Integrated audit failure
```

---

# 54. Public API

`backend/config/__init__.py`：

```text
BendersColumnGenerationConfig
BendersColumnGenerationConfigError
BendersColumnGenerationSource
load_benders_column_generation_config
```

`backend/core/__init__.py`：

```text
BendersCgStatus
BendersCgCutSource
BendersCgCut
BendersCgRecourseCertificate
BendersCgIteration
BendersCgResult
BendersColumnGenerationError

benders_cg_implicit_universe_fingerprint
solve_benders_with_column_generation
recompute_benders_cg_audit
```

---

# 55. Recommended Files

新增：

```text
backend/config/benders_column_generation.py
backend/core/benders_column_generation.py

data/config/phase11_test_benders_cg_v1.json

tests/unit/test_benders_column_generation.py

tests/regression/test_phase11_benders_cg_oracle.py
tests/regression/test_phase11_benders_cg_cut_validity.py
tests/regression/test_phase11_benders_cg_integrality_boundary.py
tests/regression/test_phase11_benders_cg_benchmark.py
```

新增：

```text
toy_case_013_benders_column_generation
```

---

# 56. Stable Files

原则上不要修改：

```text
backend/core/integrated_oracle.py

backend/core/aircraft_string_master.py
backend/core/aircraft_string_pricing.py
backend/core/aircraft_string_column_generation.py

backend/core/crew_pairing_master.py
backend/core/crew_pairing_pricing.py
backend/core/crew_pairing_column_generation.py

backend/core/prm.py
backend/schemas/columns.py
```

`backend/core/benders.py` 只允许非常小、向后兼容的 helper 提取。

---

# 57. Recommended Implementation Order

```text
1. Phase 10 closeout + merge
2. create feature/phase-11
3. first write assumptions / cut-validity policy
4. implement implicit-universe fingerprint
5. implement Phase 11 cut/provenance types
6. build Schedule master
7. integrate Aircraft CG recourse adapter
8. integrate Crew CG recourse adapter
9. integrate fixed PRM adapter
10. build binary ARM/CRM incumbent
11. implement LB / UB loop
12. implement INTEGRALITY_REQUIRED boundary
13. build toy_case_013
14. compare with Full Explicit Integrated Oracle
15. run phase1 benchmark
16. formal-enumerator-independence tests
17. full regression
18. docs + Codex report
```

关键顺序：

> **先证明 cut validity，再写完整 Benders loop。**

---

# 58. Phase 11 Acceptance Criteria

必须全部满足。

## A. Cut Validity

- [ ] Phase 8 cuts 不直接复用；
- [ ] restricted RMP objective 不生成 permanent cut；
- [ ] Aircraft cut 只来自 pricing-certified full LP；
- [ ] Crew cut 只来自 pricing-certified full LP；
- [ ] restricted-pool infeasibility 不 no-good；
- [ ] Phase-I certified infeasibility 可 no-good；
- [ ] PRM exact infeasibility 可 no-good；
- [ ] universe fingerprint 变化时旧 cuts 全失效；
- [ ] explicit pool growth 不使 certified cut 失效。

## B. Bounds

- [ ] Master objective 是合法 LB；
- [ ] generated-pool binary feasible solution 是合法 UB；
- [ ] LB 单调不下降；
- [ ] incumbent UB 单调不增加；
- [ ] gap 正确。

## C. Aircraft

- [ ] 每个 visited Schedule 调用真实 Phase 9 CG；
- [ ] CG 未收敛时不加 cut；
- [ ] returned columns 可进入 binary ARM；
- [ ] LP / integer recourse 分开记录。

## D. Crew

- [ ] 每个 visited Schedule 调用真实 Phase 10 CG；
- [ ] CG 未收敛时不加 cut；
- [ ] OPERATE / DEADHEAD semantics 不变化；
- [ ] returned Pairings 可进入 binary CRM；
- [ ] LP / integer recourse 分开记录。

## E. Passenger

- [ ] Phase 7 Itineraries 固定；
- [ ] PRM exact MIP 不变；
- [ ] passenger cost 不重复。

## F. Integrality Boundary

- [ ] binary recourse 不被错误用作 lower-bound cut；
- [ ] gap 无法闭合时 `INTEGRALITY_REQUIRED`；
- [ ] 不通过 invalid no-good 跳过 feasible Schedule。

## G. Oracle Equality

```text
toy_case_013:
OBJ_BENDERS_CG
=
OBJ_FULL_EXPLICIT_INTEGRATED
```

```text
phase1_benchmark_001:
OBJ_BENDERS_CG
=
OBJ_FULL_EXPLICIT_INTEGRATED
```

## H. Independence

- [ ] formal Phase 11 solver 不调用 Phase 5 full generator；
- [ ] formal Phase 11 solver 不调用 Phase 6 full generator。

## I. Regression

- [ ] Phase 8 PASS；
- [ ] Phase 9 PASS；
- [ ] Phase 10 PASS；
- [ ] Integrated Oracle PASS；
- [ ] full pytest PASS；
- [ ] compileall PASS；
- [ ] git diff --check PASS。

---

# 59. Definition of Done

只有以下完整链条成立才标记 Phase 11 完成：

```text
SRM Schedule Master
        ↓
selected Schedule
        ↓
Aircraft full-LP CG certificate
+
Crew full-LP CG certificate
+
Passenger exact MIP
        ↓
valid lower-bound / feasibility cuts
        ↓
generated-column binary ARM / CRM
        ↓
integer feasible incumbent
        ↓
valid LB / UB convergence
        ↓
Integrated incumbent diagnostics PASS
        ↓
OBJ_BENDERS_CG
=
OBJ_FULL_EXPLICIT_INTEGRATED
        ↓
formal solver independent from full enumerators
        ↓
full regression PASS
```

---

# 60. Phase 11 Report

生成：

```text
docs/codex_reports/
YYYYMMDD_HHMMSS_phase11_benders_column_generation_report.md
```

至少包括：

```text
1. Phase 10 closeout / baseline
2. Modified files
3. Phase 11 architecture
4. Why Phase 8 cuts are not reused
5. Implicit column universe
6. Cut validity / invalidation policy
7. Aircraft CG recourse
8. Crew CG recourse
9. Passenger fixed recourse
10. LP lower-bound vs binary upper-bound
11. Integrality boundary
12. toy_case_013
13. Full Explicit Integrated Oracle
14. Benders-CG trajectory
15. Benchmark result
16. Cut statistics
17. Column / pricing statistics
18. LB / UB trajectory
19. Final Integrated diagnostics
20. Formal enumerator-independence test
21. Full regression
22. Known limitations
23. Deferred work
24. Next step
```

---

# 61. Known Limitations

必须明确：

```text
scope=None only in Phase 11 v1

Flight Options remain fixed

Passenger Itineraries remain fixed explicit columns

Aircraft / Crew CG are LP pricing algorithms

binary incumbent uses generated-column ARM / CRM MIPs

if LP/integer gap prevents proof:
    INTEGRALITY_REQUIRED

no Branch-and-Price
no Crew follow-on branching
no Passenger branching
no dynamic Scope
no production-scale pricing acceleration
```

---

# 62. Next Step After Phase 11

若当前 toy / benchmark：

```text
LB = UB
OBJ_BENDERS_CG = Integrated Oracle
```

则进入：

```text
Phase 12 — Integrality / Branching
```

Phase 12 处理：

```text
ARM integrality
CRM follow-on branching
PRM branching if required
Branch-and-Price style CG under branching
```

Phase 12 解决的是：

```text
LP recourse lower bound
vs
integer recourse
```

不是补救 Phase 11 的 invalid cuts。

---

# 63. Final Principle

Phase 11 最核心的问题不是：

> “能不能把 Benders、Aircraft CG 和 Crew CG 串起来。”

而是：

> **动态 Column Generation 产生的 recourse 信息，哪些可以数学上安全地进入 Benders Master，并最终形成可证明的 integrated lower/upper-bound closure。**

优先级：

```text
Cut validity
>
Bound validity
>
CG completeness
>
Integrated Oracle equality
>
Integrality boundary clarity
>
runtime
```

任何为了快速复现：

```text
18080
```

而使用未经 pricing convergence 的 recourse cut、restricted-pool infeasibility no-good、或未经证明的 binary recourse lower-bound，都应视为 Phase 11 失败。
