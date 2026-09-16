# Phase 9 Closeout & Phase 10 Crew Pairing Column Generation Plan

## 1. Phase 9 Review

**Phase 9: PASS. 可以收尾并合并。**

已核对 `feature/phase-9` 的 README、总计划和核心实现。当前链路已经形成：

```text
Fixed Schedule
→ Aircraft Full-Column LP
→ Restricted Master LP
→ Phase I artificials
→ LP dual / reduced cost
→ Aircraft-local pricing
→ Phase II column generation
→ full-pool termination audit
```

当前实现满足主要验收要求：

- `AircraftString` Master 使用 continuous `y`；
- Phase I 使用显式 artificial variables；
- 只有 optimal LP 才读取 dual / reduced cost；
- manual reduced cost 与 solver reduced cost 有独立 audit；
- 正式 CG solver 不接收 Phase 5 full string pool；
- formal pricer 不调用 `generate_aircraft_strings(...)`；
- Scope 外 Aircraft 固定到 semantic original string；
- final termination 使用 Phase 5 full pool 检查 omitted columns；
- `OPTIMAL / INFEASIBLE / NOT_CONVERGED / ABORTED` 状态已区分。

README 当前记录：

```text
toy_case_011:
initial expensive solution = 300
CG objective = 0

phase1_benchmark_001:
full strings = 77
final CG columns = 15

OBJ_CG_LP = OBJ_FULL_COLUMN_AIRCRAFT_LP = 0
```

因此 Phase 9 已满足仓库计划的：

```text
Column Generation LP = Full-column LP
```

---

## 2. Phase 9 非阻断性问题

### 2.1 Aircraft Pricing 仍是 correctness-first path traversal

当前正式 pricer 已与 Phase 5 full-pool generator 解耦，但内部仍会在 schedule-compatible Aircraft DAG 上遍历合法路径，再选最负 reduced-cost 列。

这不影响 Phase 9 的数学正确性和 Oracle 验收，但应保持表述准确：

```text
Phase 9 已完成正确的 Aircraft String CG baseline
≠
已经解决真实规模最优 RCSP / shortest-path pricing 性能
```

只需在 `reproduction_notes.md` 和 Phase 9 report 中保留这一限制，不阻塞 merge。

### 2.2 总计划末尾状态文字滞后

`docs/AIR_HTML_Python_Reproduction_Plan.md` 前部已经：

```text
Phase 9 = COMPLETE
Phase 10 = next
```

但文档最末尾“当前立即执行的下一任务”仍残留 Phase 9。

Phase 9 收尾时改为：

```text
Phase 10 — Crew Pairing Column Generation
```

---

# 3. Phase 9 Closeout

在 `feature/phase-9`：

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

确认至少已提交：

```text
backend/config/aircraft_string_column_generation.py
backend/core/aircraft_string_master.py
backend/core/aircraft_string_pricing.py
backend/core/aircraft_string_column_generation.py
data/config/phase9_test_aircraft_string_cg_v1.json

tests/unit/test_aircraft_string_master.py
tests/unit/test_aircraft_string_pricing.py
tests/unit/test_aircraft_string_column_generation.py

toy_case_011 related fixtures/tests

README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/codex_reports/<latest_phase9_report>.md
```

修正总计划末尾下一任务后，再运行：

```bash
pytest -q
git diff --check
```

---

# 4. Merge Phase 9

```bash
git switch main
git pull
git merge --no-ff feature/phase-9
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

然后：

```bash
git switch -c feature/phase-10
```

确认远端 `main` 已包含 Phase 9 后，可删除 Phase 9 开发分支。

---

# 5. Phase 9 Freeze

Phase 10 不得为了 Crew CG 修改以下已验证语义：

```text
Aircraft LP row semantics
Aircraft Phase I / Phase II contract
Aircraft reduced-cost audit
Aircraft CG status contract
Aircraft Scope contract
Aircraft full-pool termination audit
```

Phase 9 继续作为：

```text
Aircraft String Column Generation Ground Truth
```

Phase 10 必须独立实现 Crew Pairing CG。

---

# 6. Phase 10 Objective

仓库总计划中的 Phase 10：

```text
Crew Pairing Column Generation
```

准确目标：

> 在 fixed Schedule 下，通过 Crew LP dual 和 crew-local pricing 动态生成负 reduced-cost Pairings，并证明最终 Crew CG LP 与 Phase 6 all-pairings LP 完全一致。

核心验收：

```text
OBJ_CREW_CG_LP
=
OBJ_ALL_PAIRINGS_LP
```

Phase 10 不做：

```text
Benders + CG
Aircraft + Crew 联合 RMP
Passenger Itinerary CG
Branch-and-Price
Integrality recovery
新 Flight Option generation
真实航空公司完整 duty/rest legality
```

---

# 7. Ground Truth Chain

必须保留：

```text
Phase 6 Full Crew Pairing Enumeration
        ↓
All-Pairings Crew LP Oracle
        ↓
Crew Pairing Column Generation LP
```

小规模 pricing 还必须有：

```text
Crew Network Pricing minimum reduced cost
=
Full-pool exhaustive minimum reduced cost
```

---

# 8. Fixed Schedule

Phase 10 输入继续复用：

```python
CrewRecoveryRequest
```

即：

```text
required_operated_option_ids
```

一次 CG solve 中 Schedule 固定。

Phase 10 不优化 `x`。

---

# 9. Formal Pricing Universe

当前 CRM 对非 required revenue Flight Option 同时施加：

```text
OPERATE = 0
DEADHEAD = 0
```

因此正式 Crew Pricing 只使用：

```text
required_operated_option_ids
```

对应的 revenue Flight Options。

每个 required option 可根据 crew legality形成：

```text
OPERATE
DEADHEAD
```

其中：

```text
OPERATE:
    contributes required flight coverage

DEADHEAD:
    does not contribute operating coverage
    may reposition crew
```

不得在正式 pricer 中加入 nonrequired revenue options。

---

# 10. Reuse Phase 6 Crew Network

必须优先复用：

```text
backend/core/crew_network.py

CrewFlightNetwork
CrewLegKey
build_crew_flight_network(...)
validate_flight_option_for_crew(...)
```

继续复用：

```python
validate_generated_crew_pairing(...)
pairing_semantic_key(...)
```

不得复制第二套：

```text
qualification
station continuity
time continuity
MCT
recovery horizon
max duty
deadhead limit
terminal rule
duplicate option/base-flight rule
```

---

# 11. Pairing ID / Constructor

当前 Phase 6 Pairing ID 已由：

```text
crew_id
+ ordered (segment_type, flight_option_id)
+ SHA-256
```

稳定生成。

若 Phase 10 pricer 需要直接构造 Pairing，建议最小重构：

```python
crew_pairing_id(...)
make_generated_crew_pairing(...)
```

将 Phase 6 private helper public 化。

要求：

```text
existing generated Pairing IDs unchanged
Phase 6 tests unchanged
```

禁止复制一套新 ID 逻辑。

---

# 12. New Core Modules

建议新增：

```text
backend/core/crew_pairing_master.py
backend/core/crew_pairing_pricing.py
backend/core/crew_pairing_column_generation.py
```

职责：

### `crew_pairing_master.py`

```text
All-Pairings LP
Restricted Master LP
Phase I artificials
row coefficients / handles
dual extraction
solver reduced cost
manual reduced-cost audit
Scope restriction
```

### `crew_pairing_pricing.py`

```text
crew reduced-cost evaluator
resource-state pricing
Pairing legality audit
pricing result
```

### `crew_pairing_column_generation.py`

```text
input fingerprint
initial pool
Phase I
Phase II
column insertion
deduplication
termination
metrics
full-pool termination audit
```

---

# 13. Crew Full-Column LP

新增：

```python
solve_full_column_crew_pairing_lp(...)
```

输入：

```text
Scenario
Flight Options
Phase 6 full Pairings
CrewRecoveryRequest
Cost Config
CrewPairingGenerationConfig
RecoveryScope | None
Solver
```

变量：

```text
0 <= z[pairing] <= 1
continuous
```

Full LP 只作为：

```text
Oracle / test / audit
```

正式 Crew CG solver 不得接收 full pairing pool。

---

# 14. Crew LP Rows

必须保持现有 CRM row semantics：

```text
CRM-C01 Crew Pairing Selection

CRM-C02 Required Flight Option OPERATE Coverage

CRM-C03 Nonrequired OPERATE Prohibition

CRM-C03 Nonrequired DEADHEAD Prohibition

CRM-C05 Terminal Ownership
```

`CRM-C04 Crew Feasibility` 继续作为候选 Pairing legality contract，不单独建立 master row。

Phase 10 不应未经验证删除 selection / terminal 等看似冗余的 rows。

---

# 15. Row Coefficients

一个 Pairing `p`：

### Selection

```text
1 for p.crew_id
```

### Required OPERATE coverage

若含：

```text
OPERATE(option_id)
```

则该 required option row：

```text
1
```

若只是：

```text
DEADHEAD(option_id)
```

则 required operating row：

```text
0
```

### Nonrequired OPERATE

若含：

```text
OPERATE(nonrequired_option)
```

对应 row：

```text
1
```

### Nonrequired DEADHEAD

若含：

```text
DEADHEAD(nonrequired_option)
```

对应 row：

```text
1
```

### Terminal

合法 Pairing：

```text
end_station == crew.required_station_at_T_end
```

对应 Crew terminal row：

```text
1
```

---

# 16. Crew LP Dual Contract

建议：

```python
@dataclass(frozen=True)
class CrewPairingMasterDuals:
    phase
    selection_by_crew
    required_operate_coverage_by_option
    nonrequired_operate_by_option
    nonrequired_deadhead_by_option
    terminal_by_crew
```

禁止 pricer 通过 constraint-name string 临时猜 dual。

---

# 17. Crew Pairing Cost

继续使用现有：

```python
crew_pairing_cost(...)
```

CRM owner cost：

```text
crew reassignment
+
deadhead minutes × deadhead_per_minute
```

### OPERATE segment

如果：

```text
base_flight.original_crew != pairing.crew_id
```

产生 crew reassignment cost。

### DEADHEAD segment

产生：

```text
block_minutes × deadhead_per_minute
```

Phase 10 不建立第二套 cost semantics。

---

# 18. Reduced Cost

统一公式：

```text
rc(p)
=
crew_pairing_cost(p)
-
Σ dual[row] × coefficient[row,p]
```

Phase II 应覆盖：

```text
selection dual
required OPERATE coverage dual
nonrequired OPERATE dual
nonrequired DEADHEAD dual
terminal dual
```

正式 pricing 不使用 nonrequired options，因此这些 contribution 在 formal priced columns 中为 0，但 Full LP audit 仍必须保留对应 rows。

---

# 19. Phase I

不能假定 original Pairings 对 disrupted schedule 一定可行。

因此使用：

```text
Phase I artificial feasibility
```

对 RHS=1 rows 加 nonnegative artificial：

```text
Crew Selection
Required OPERATE Coverage
Terminal Ownership
```

Phase I objective：

```text
min Σ artificials
```

real Pairings：

```text
objective coefficient = 0
```

RHS=0 的 nonrequired prohibition rows不加 artificial。

---

# 20. Phase I Reduced Cost

Phase I 中真实 Pairing：

```text
primal cost = 0
```

因此：

```text
rc_phase1(p)
=
0 - dual contribution
```

不能误用 Phase II crew cost。

必须有独立 unit test。

---

# 21. Existing-Column Reduced-Cost Audit

每个 optimal RMP 后：

```text
manual RC
≈
solver.get_reduced_cost(z[p])
```

若误差超过配置 tolerance：

```text
status = ABORTED
```

不得继续 pricing。

这是 Phase 10 的硬性 gate。

---

# 22. Phase 10 Config

建议新增：

```text
backend/config/crew_pairing_column_generation.py
```

字段：

```text
schema_version = 1.0.0
profile_id

pricing_epsilon
feasibility_epsilon
reduced_cost_audit_tolerance

max_iterations
max_columns_per_crew_per_iteration

source
notes
```

要求：

```text
frozen
extra="forbid"
strict
duplicate JSON key rejection
versioned
```

测试配置：

```text
data/config/phase10_test_crew_pairing_cg_v1.json
```

Crew legality 参数继续来自：

```text
CrewPairingGenerationConfig
```

不要重复配置：

```text
MCT
max duty
deadhead limit
allow deadhead
allow idle
```

---

# 23. Formal Crew Pricing

新增：

```python
price_crew_pairings(...)
```

输入至少：

```text
Scenario
Flight Options
Crew
CrewRecoveryRequest
Cost Config
CrewPairingGenerationConfig
CrewPairingMasterDuals
existing semantic keys
pricing epsilon
max columns
```

输出至少：

```text
crew_id
negative priced Pairings
minimum reduced cost
states / paths evaluated
duplicates skipped
resource-pruning counts
```

---

# 24. Formal Solver Independence

正式：

```python
price_crew_pairings(...)
solve_crew_pairing_column_generation(...)
```

不得调用：

```python
generate_crew_pairings(...)
brute_force_legal_crew_pairings(...)
```

必须有 monkeypatch test：

```text
full enumerators → raise AssertionError
```

然后正式 Crew CG 仍应正常完成。

---

# 25. Crew Pricing Problem

Crew Pricing 是 resource-constrained typed-path problem。

至少包含资源：

```text
used Flight Option IDs
used base Flight IDs
deadhead count
first duty departure time
duty elapsed minutes
```

节点类型：

```text
OPERATE
DEADHEAD
```

推荐实现：

```text
deterministic label-setting / resource-state search
```

不要简单复制 Phase 6 full Pairing enumerator。

---

# 26. Pricing State

建议状态至少包含：

```text
last CrewLegKey
ordered typed path
used option IDs
used base-flight IDs
deadhead count
first departure time
accumulated primal cost
accumulated dual contribution
accumulated reduced cost
```

Phase 10 correctness 优先。

不要求第一版实现复杂 dominance。

---

# 27. Safe Pruning

必须安全 prune：

```text
duplicate Flight Option
duplicate base Flight
deadhead count > max_deadhead_legs
duty time > max_duty_minutes
station discontinuity
MCT violation
qualification violation
recovery horizon violation
```

所有最终 emitted Pairing 再次运行：

```python
validate_generated_crew_pairing(...)
```

---

# 28. OPERATE / DEADHEAD Reduced-Cost Increment

对 required option：

### OPERATE

increment 包括：

```text
possible crew reassignment primal cost
-
required OPERATE coverage dual
```

### DEADHEAD

increment 包括：

```text
deadhead primal cost
```

因为 DEADHEAD 不贡献 required operating coverage。

Pairing-level constant：

```text
-selection dual
-terminal dual
```

可以放在 root 或 terminal evaluation。

最终结果必须与统一 reduced-cost evaluator 完全一致。

---

# 29. Idle Pairing

如果：

```text
allow_idle = true
```

且：

```text
crew.start_station_at_t
==
crew.required_station_at_T_end
```

则 pricing 必须考虑 idle Pairing。

Idle：

```text
0 legs
primal cost = 0
```

但仍有：

```text
selection coefficient = 1
terminal coefficient = 1
```

所以 reduced cost 不一定为 0。

---

# 30. Reduced-Cost Evaluator

新增：

```python
evaluate_crew_pairing_reduced_cost(...)
```

返回：

```text
Pairing
primal_cost
dual_contribution
reduced_cost
row_coefficients
```

该函数同时用于：

```text
formal pricing
full-pool exhaustive Oracle
termination audit
unit tests
```

禁止多套 reduced-cost 公式。

---

# 31. Phase I Termination

如果：

```text
artificial objective <= feasibility_epsilon
```

进入 Phase II。

如果：

```text
artificial objective > feasibility_epsilon
```

且所有 in-scope Crew 都不存在：

```text
rc < -pricing_epsilon
```

则：

```text
status = INFEASIBLE
```

---

# 32. Phase II

Phase II：

```text
remove artificials
min Σ crew_pairing_cost[p] * z[p]
```

循环：

```text
fresh RMP
→ solve OPTIMAL
→ duals
→ reduced-cost audit
→ per-Crew pricing
→ add negative-RC Pairings
```

若无新负 reduced-cost Pairing：

```text
OPTIMAL
```

达到 max iterations：

```text
NOT_CONVERGED
```

---

# 33. Fresh RMP Rebuild

与 Phase 9 一致：

```text
每轮 fresh build RMP
```

不扩展 solver adapter 做 dynamic-column mutation。

避免 solver-state 隐式依赖。

---

# 34. Scope

必须支持：

```text
scope=None
RecoveryScope
```

### in-scope Crew

```text
pricing enabled
```

### out-of-scope Crew

```text
semantic original Pairing only
no pricing
```

original Pairing 必须通过：

```text
crew.original_pairing
→ semantic original Flight Options
→ Pairing constructor
→ legality validator
```

解析。

不得依赖 ID 命名。

---

# 35. Column Deduplication

使用：

```python
pairing_semantic_key(...)
```

若 priced Pairing 已存在：

```text
不重复加入
```

如果 optimal RMP 中已有 Pairing 却显示：

```text
RC < -epsilon
```

视为 master/dual/RC bug，应 abort。

---

# 36. Per-Iteration Column Limit

建议默认：

```text
max_columns_per_crew_per_iteration = 1
```

即每个 Crew 每轮加入最负 reduced-cost Pairing。

先保证：

```text
determinism
auditability
```

后续再做 multi-column acceleration。

---

# 37. Toy Case

新增：

```text
toy_case_012_crew_pairing_column_generation
```

至少包含：

```text
2+ Crew
multiple required Flight Options
OPERATE / DEADHEAD choices
crew reassignment
deadhead cost
expensive initial feasible solution
omitted cheaper Pairing
nontrivial Phase I
nontrivial Phase II
```

必须显式验证：

```text
OPERATE contributes coverage
DEADHEAD does not
```

---

# 38. Pricing Exhaustive Oracle

在 `toy_case_012`：

```text
Phase 6 full Pairings
→ evaluate RC for every omitted Pairing
→ exhaustive minimum
```

与：

```text
formal crew pricer minimum
```

比较：

```text
minimum RC equal
```

若多个 Pairing 同时达到最小 RC，可允许具体 semantic key 不同，但 pricer 返回 Pairing 必须属于最优集合。

---

# 39. Full-Pool Termination Audit

CG 返回 `OPTIMAL` 后，仅在 audit boundary 使用：

```python
generate_crew_pairings(...)
```

得到 full pool。

对所有 omitted Pairings：

```text
RC >= -pricing_epsilon
```

否则：

```text
Phase 10 FAIL
```

正式 solver 本身不得接收 full pool。

---

# 40. True Infeasible Schedule Test

增加一个小 case：

```text
某 required option 没有任何 Crew 可合法 OPERATE
```

或因为：

```text
terminal / duty / connectivity
```

导致无法覆盖。

要求：

```text
Phase I artificial > 0
no improving Pairing
status = INFEASIBLE
```

---

# 41. Benchmark

使用：

```text
phase1_benchmark_001
```

当前 Phase 6 full generated universe：

```text
374 Crew Pairings
```

使用明确的 fixed Schedule，例如：

```text
Phase 1 Manual Reference schedule
```

或：

```text
Integrated optimum schedule
```

报告中必须写明具体 schedule source。

比较：

```text
All-Pairings Crew LP
vs
Crew Pairing CG LP
```

要求：

```text
objective equal
```

不要预先把具体 LP objective 写死。

---

# 42. Scope Benchmark

还必须有非 Full-Scope case：

```text
OBJ_CREW_CG_SCOPE_LP
=
OBJ_ALL_PAIRINGS_SCOPE_LP
```

主 benchmark 当前通常闭包为 Full Scope，因此不能替代 dedicated scope regression。

---

# 43. Determinism

相同输入下尽量保持：

```text
initial pool
Crew pricing order
iteration sequence
added Pairing semantic keys
final pool
objective
termination reason
```

LP degeneracy 下不要求 dual bitwise identical。

优先检查：

```text
objective
manual RC validity
pricing minimum RC
full-pool termination
```

---

# 44. Metrics

每轮记录：

```text
phase
iteration
RMP objective
artificial objective
column count before/after
dual count
priced Crew count
minimum reduced cost
negative columns found
new columns added
duplicate columns skipped
states/paths evaluated
runtime
```

最终：

```text
status
termination reason
Phase-I iterations
Phase-II iterations
full Pairing count
final CG Pairing count
minimum omitted RC
All-Pairings LP objective
CG LP objective
difference
max existing-column RC audit error
runtime
```

---

# 45. Recommended Files

新增：

```text
backend/config/crew_pairing_column_generation.py

backend/core/crew_pairing_master.py
backend/core/crew_pairing_pricing.py
backend/core/crew_pairing_column_generation.py

data/config/phase10_test_crew_pairing_cg_v1.json
```

测试：

```text
tests/unit/test_crew_pairing_master.py
tests/unit/test_crew_pairing_pricing.py
tests/unit/test_crew_pairing_column_generation.py

tests/regression/test_phase10_crew_pricing_oracle.py
tests/regression/test_phase10_crew_column_generation.py
tests/regression/test_phase10_crew_scope.py
tests/regression/test_phase10_crew_benchmark.py
```

fixture：

```text
toy_case_012_crew_pairing_column_generation
```

---

# 46. Stable Files

原则上不要修改：

```text
backend/core/crm.py
backend/core/integrated_oracle.py
backend/core/benders.py

backend/core/aircraft_string_master.py
backend/core/aircraft_string_pricing.py
backend/core/aircraft_string_column_generation.py

backend/schemas/columns.py
```

允许对：

```text
pairing_generator.py
```

做最小 public-helper 重构，但 Phase 6 semantics 和 IDs 必须不变。

---

# 47. Public API

建议 `backend/core/__init__.py` 导出：

```text
CrewPairingMasterPhase
CrewPairingMasterDuals
CrewPairingMasterModel
CrewPairingMasterResult
CrewPairingMasterError

CrewPairingPricedColumn
CrewPairingPricingResult
CrewPairingPricingError

CrewPairingColumnGenerationStatus
CrewPairingColumnGenerationIteration
CrewPairingColumnGenerationResult
CrewPairingColumnGenerationAudit
CrewPairingColumnGenerationError

build_crew_pairing_master
solve_crew_pairing_master
solve_full_column_crew_pairing_lp

evaluate_crew_pairing_reduced_cost
price_crew_pairings

solve_crew_pairing_column_generation
audit_crew_pairing_column_generation_termination
```

如需要，再导出：

```text
crew_pairing_id
make_generated_crew_pairing
```

---

# 48. Config API

`backend/config/__init__.py` 导出：

```text
CrewPairingColumnGenerationConfig
CrewPairingColumnGenerationConfigError
CrewPairingColumnGenerationSource
load_crew_pairing_column_generation_config
```

---

# 49. Unit Tests

至少覆盖：

```text
continuous z
Phase-I artificials
dual extraction
manual RC == solver RC

selection row
required OPERATE row
nonrequired OPERATE row
nonrequired DEADHEAD row
terminal row

OPERATE vs DEADHEAD coefficient difference
crew owner cost audit

idle Pairing
qualification
MCT
duty time
deadhead limit
duplicate option/base Flight

Pairing ID stability
semantic deduplication

Phase-I feasible transition
true infeasible case
Phase-II column insertion
no-negative-RC termination
max-iteration status
Scope original-only
formal CG independent from full enumerator
```

---

# 50. Core Acceptance Tests

必须：

```text
toy_case_012:
pricing minimum RC
=
full-pool exhaustive minimum RC
```

```text
toy_case_012:
OBJ_CREW_CG_LP
=
OBJ_ALL_PAIRINGS_LP
```

```text
scope case:
OBJ_CREW_CG_SCOPE_LP
=
OBJ_ALL_PAIRINGS_SCOPE_LP
```

```text
phase1_benchmark_001:
OBJ_CREW_CG_LP
=
OBJ_ALL_PAIRINGS_LP
```

终止：

```text
min omitted Pairing RC >= -epsilon
```

---

# 51. Full Regression

Phase 10 完成前：

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

如当前工程继续使用 Black：

```bash
python -m black --check <Phase10 files>
```

要求：

```text
0 failed
0 errors
```

同时确认：

```text
Phase 6 Pairing generator tests PASS
Phase 8 Benders regressions PASS
Phase 9 Aircraft CG regressions PASS
```

---

# 52. Documentation

完成后更新：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

准确区分：

```text
Phase 6:
full explicit Crew Pairing enumeration

Phase 10:
fixed-schedule Crew Pairing LP Column Generation
```

不得表述为：

```text
完整真实 crew scheduling
```

---

# 53. Recommended Execution Order

```text
1. Phase 9 closeout + merge
2. create feature/phase-10
3. public Pairing constructor/ID helper if needed
4. build Crew Full-Column LP
5. verify manual RC == solver RC
6. implement Crew pricing
7. pricing vs full-pool Oracle
8. implement Phase I
9. implement Phase II CG loop
10. toy_case_012
11. Scope regression
12. phase1 benchmark
13. full-pool termination audit
14. full regression
15. docs + Codex report
```

关键要求：

> **先冻结 LP rows 与 reduced-cost 公式，再写 pricing。**

---

# 54. Phase 10 Definition of Done

只有以下链条全部成立：

```text
Existing Flight Options
        ↓
Fixed Schedule
        ↓
Phase 6 Crew Network / Legality
        ↓
Phase 6 Full Pairing Enumeration
        ↓
All-Pairings Crew LP Oracle
        ↕
Restricted Crew Master LP
        ↓
LP Duals
        ↓
Crew Resource-Constrained Pricing
        ↓
Negative Reduced-Cost Pairings
        ↓
Column Generation
        ↓
No Negative Reduced-Cost Pairing
        ↓
Full-Pool Termination Audit
        ↓
OBJ_CREW_CG_LP
=
OBJ_ALL_PAIRINGS_LP
        ↓
Full Regression PASS
```

以下均不足以单独完成 Phase 10：

```text
Pricer 能生成 Pairing
CG 能迭代
solver 返回 OPTIMAL
最终列数少于 374
benchmark 看起来合理
```

---

# 55. Phase 10 Report

新增：

```text
docs/codex_reports/
YYYYMMDD_HHMMSS_phase10_crew_pairing_column_generation_report.md
```

至少包括：

```text
1. Phase 9 closeout / baseline
2. Modified files
3. Crew Full-Column LP
4. Crew RMP
5. Phase I
6. CRM row / dual mapping
7. Reduced-cost formula
8. Pricing resource state
9. OPERATE / DEADHEAD handling
10. toy_case_012
11. Pricing vs exhaustive Oracle
12. All-Pairings LP vs CG
13. Scope
14. Benchmark
15. Termination audit
16. Existing-column RC audit
17. Full regression
18. Known limitations
19. Deferred work
20. Next step
```

必须给数字：

```text
full Pairing count
initial/final CG column count
Phase-I / Phase-II iterations
Pairings added by Crew
minimum RC by iteration
All-Pairings LP objective
CG LP objective
objective difference
minimum omitted RC
max RC audit error
runtime
pytest summary
```

---

# 56. Phase 10 Known Limitations

必须保留：

```text
Flight Options fixed
Schedule fixed within one Crew CG solve
Phase 6 v1 single-duty legality only
No real FAR/CCAR duty/rest system
No Benders + CG
No joint Aircraft/Crew pricing
No Passenger CG
No branching / integrality recovery
```

---

# 57. Next Step After Phase 10

仓库总计划下一阶段：

```text
Phase 11 — Benders + Column Generation
```

进入 Phase 11 前必须冻结：

```text
Integrated Fixed-Column Oracle
Fixed-Column Benders
Aircraft Full-Column LP Oracle
Aircraft String CG
Crew All-Pairings LP Oracle
Crew Pairing CG
```

Phase 11 不允许简单把 Phase 9/10 CG 塞进 Phase 8 Benders。

首先必须解决：

```text
dynamic columns
vs
existing Benders cut validity
```

至少明确：

```text
Cut Validity Policy
Cut Invalidation / Refresh Policy
Recourse lower-bound refresh
candidate-universe fingerprint
```

---

# 58. Final Principle

Phase 10 只回答：

> **Crew Pairing Pricing / Column Generation 在 fixed Schedule、existing Flight Options 和 Phase 6 v1 Crew legality 下是否数学正确。**

优先级：

```text
Reduced-cost correctness
>
OPERATE / DEADHEAD semantics
>
Pricing completeness
>
All-Pairings LP equality
>
Termination audit
>
Column reduction
>
runtime
```

先证明：

```text
Crew Column Generation is correct.
```

再进入 Phase 11。
