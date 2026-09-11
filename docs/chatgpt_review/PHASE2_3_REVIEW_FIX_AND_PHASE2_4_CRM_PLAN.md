# Phase 2.3 Review Fix + Phase 2.4 Fixed-Column CRM Plan

> 用途：供 Codex 在当前 `main` 基础上继续开发。  
> 执行顺序：**先完成 Phase 2.3 review fix 并留痕，再进入 Phase 2.4 Fixed-Column CRM。**  
> 本文件不包含 HTML / Frontend 修改。

---

# 1. 当前基线

当前已完成：

```text
Phase 2.1
Solver / Cost / Result Contract

Phase 2.2
Fixed-Column SRM
FINAL PASS

Phase 2.3
Fixed-Column ARM
PASS
```

当前已确认：

- SRM 可以独立选择 schedule options；
- ARM 接受外生 `required_operated_option_ids`；
- ARM 不重新决定 schedule；
- ARM 可选择 fixed `aircraft_strings`；
- ARM 已实现 flight-option coverage、non-required revenue leakage prohibition、terminal、maintenance、ferry、aircraft reassignment；
- SRM / ARM 均使用统一 Cost Contract；
- Gurobi integration 已有实际执行 gate；
- 求解结果均有独立约束与 objective audit。

当前主要收尾问题：

> SRM → downstream 的 schedule handoff 尚未形成统一 canonical extractor。

当前 benchmark 因没有 cancellation 而未暴露问题；若 SRM 以后选择 CANCEL，不能直接把全部 `selected_option_by_flight.values()` 传入 ARM / CRM。

---

# Part A — Phase 2.3 Review Fix

# 2. Phase 2.3 必改：统一 Schedule → Downstream Contract

## 2.1 当前风险

禁止继续在测试或后续模型中直接写类似：

```python
required = tuple(
    srm_result.diagnostics["selected_option_by_flight"].values()
)
```

因为其中可能包含：

```text
operation_type = cancel
```

而 ARM / CRM 所需的是：

```text
实际需要资源执行的 revenue operate Flight Options
```

CANCEL：

```text
不需要 aircraft
不需要 operating crew
```

因此必须在 Phase 2.4 前冻结统一转换。

---

# 3. Canonical extractor

建议新增一个模型间 handoff 模块，例如：

```text
backend/core/recovery_handoff.py
```

或放在现有更合适的 shared core 模块。

建议提供 pure function：

```python
extract_required_operated_option_ids(...)
```

输入至少：

```text
SRM ModelSolveResult
RecoveryColumns / FlightOption index
```

输出：

```text
tuple[str, ...]
```

要求只包含：

```text
operation_type == operate
base_flight_id != null
```

必须排除：

```text
cancel
ferry
```

## 3.1 输出不只用于 ARM

该函数必须明确定位为：

```text
schedule → resource recovery handoff
```

后续统一供：

```text
ARM
CRM
```

使用。

PRM 是否直接使用同一集合，等 Phase 2.5 根据 Passenger 语义再决定，不在本阶段提前耦合。

## 3.2 Fail-fast 要求

若 SRM result 中：

```text
selected_option_by_flight
```

包含：

- unknown option ID；
- ferry；
- option base flight 与映射不一致；
- 同一 base flight 多个 selected option；
- 缺失 base flight selection；

不得静默跳过。

应：

```text
raise explicit contract error
```

或返回明确 validation failure。

唯一允许被正常过滤的是：

```text
合法 CANCEL option
```

---

# 4. Cancellation regression

必须新增 regression：

构造一个 SRM 结果，其中至少包含：

```text
F1 -> operate option
F2 -> cancel option
F3 -> delayed operate option
```

canonical extractor 应输出：

```text
F1 operate
F3 delayed operate
```

不得包含：

```text
F2 cancel
```

随后：

```text
ARM request
CRM request
```

均应接受该结果。

测试至少覆盖：

```text
cancel is excluded
operate retained
delayed operate retained
ferry rejected / excluded according to contract
unknown option fails
```

---

# 5. Phase 2.3 文档收尾

修正 README / reproduction notes 中已经过时的表述。

当前准确状态应表达为：

```text
SRM/ARM 已实现 Phase 2 fixed-column test cost contract；
这些成本当前仍以 abstract_cost_units 为主；
并不等于真实航空公司生产成本；
CRM/PRM owned costs 尚未全部进入正式模型。
```

不要再笼统写：

```text
Delay / Cancellation / Reassignment / Ferry cost 尚未实现
```

---

# 6. Phase 2.3 留痕

在：

```text
docs/codex_reports/
```

新增：

```text
YYYYMMDD_HHMMSS_phase2_3_review_fix_report.md
```

至少记录：

```text
1. Review Finding
2. Handoff Contract
3. Cancellation Regression
4. Documentation Changes
5. Tests
6. Full Pytest
7. Gurobi Integration
8. Phase 2.3 Final Status
```

最终明确：

```text
Phase 2.3 FINAL PASS
```

或：

```text
Phase 2.3 NOT PASS
```

---

# 7. Phase 2.3 Review Fix Acceptance

- [ ] canonical operated-option extractor 已实现；
- [ ] ARM regression 不再直接复制 SRM 全部 selected options；
- [ ] cancellation regression PASS；
- [ ] unknown / invalid option fail fast；
- [ ] README cost 状态已更新；
- [ ] reproduction notes 状态已更新；
- [ ] full pytest PASS；
- [ ] Gurobi integration 实际执行；
- [ ] review-fix Codex Report 已新增。

完成后再开始 Phase 2.4。

---

# Part B — Phase 2.4 Fixed-Column CRM

# 8. Phase 2.4 目标

实现：

```text
Fixed-Column CRM
Crew Recovery Model
```

对应当前总计划中的论文：

```text
(3.13) - (3.15)
```

正式编码前必须重新核对论文原式及项目 Reproduction Plan，建立：

```text
paper equation
→ project constraint
→ data field
→ test
```

一一映射。

不得仅凭历史文字描述猜测 `(3.13)-(3.15)` 的精确数学含义。

---

# 9. Phase 2.4 范围

Phase 2.4 只回答：

> 给定已经确定必须执行的 revenue Flight Options，在现有 fixed Crew Pairings / Crew Columns 中，能否选择一组 crew recovery columns，以最低 CRM-owned cost 合法覆盖这些航班。

本阶段允许：

```text
Crew pairing selection
Required Flight Option crew coverage
Crew reassignment
Deadhead
Fixed-column crew feasibility
必要的 crew terminal / ownership consistency
```

本阶段禁止：

```text
重新决定航班 delay / cancellation
重新决定 Aircraft String
动态生成 Crew Pairing
Passenger reaccommodation
Integrated Oracle
Benders
Column Generation
HTML / Frontend 修改
真实南航 crew rules 推断
```

---

# 10. 输入合同

CRM 应建立独立显式请求对象，例如：

```text
CrewRecoveryRequest
```

至少包含：

```text
scenario_id
required_operated_option_ids
```

如 CRM 还需要 Aircraft 结果，只能在存在明确业务必要性时增加：

```text
selected_aircraft_string_ids
```

但默认不要耦合。

第一版 CRM 应尽量只依赖：

```text
schedule-selected operated options
+
fixed crew pairings
```

---

# 11. required_operated_option_ids 来源

必须统一通过 Phase 2.3 收尾新增的：

```text
extract_required_operated_option_ids(...)
```

获得。

禁止：

```text
CRM 自己重新解析 SRM diagnostics
```

也禁止：

```text
CRM 自己重新判断 CANCEL / OPERATE
```

这样 SRM → ARM / CRM 的输入语义保持一致。

---

# 12. Fixed Crew Columns

Phase 2.4 必须使用仓库现有：

```text
crew_pairings
```

或当前 schema 中等价的 fixed crew recovery columns。

编码前先核对其实际字段。

至少应确认当前 fixed column 是否能够表达：

```text
pairing_id
crew_id / crew ownership
leg_option_ids
deadhead information
start / terminal information
legality / feasibility metadata
```

如果 schema 中不存在其中某项：

> 不得自己假装存在。

应选择：

```text
补充最小 schema contract
```

或：

```text
明确将该约束作为 fixed-column validation assumption
```

并记录到 `assumptions.md`。

---

# 13. Crew feasibility 的基本原则

Phase 2.4 是：

```text
Fixed-Column CRM
```

因此第一版不应在 MIP 内重新构造完整 crew legality engine。

例如：

```text
duty time
rest time
qualification
base
connection
positioning legality
```

如果这些已经由人工 Pairing 生成/validator 保证：

```text
CRM 信任 validated fixed column
```

但必须明确记录：

> 这是 fixed-column feasibility assumption，不等于已经实现真实航空公司完整 Crew Scheduling Rules。

---

# 14. 建议稳定 Constraint IDs

建议先定义：

```text
CRM-C01-CREW-PAIRING-SELECTION
CRM-C02-FLIGHT-OPTION-COVERAGE
CRM-C03-NONREQUIRED-REVENUE-PROHIBITION
CRM-C04-CREW-FEASIBILITY
CRM-C05-TERMINAL-OR-OWNERSHIP
```

但最终数量和 `(3.13)-(3.15)` 的映射必须以论文核对结果为准。

如果论文只有三组正式约束：

> 可以让多个工程 validation / filtering rule 作为 implementation guards，而不是强行伪造成论文新公式。

Codex Report 中必须区分：

```text
paper_constraint
implementation_guard
fixed-column validation
```

---

# 15. 决策变量

对每个 fixed Crew Pairing：

```text
z_p ∈ {0,1}
```

其中：

```text
p = crew pairing / crew recovery column
```

不得动态生成新的 pairing。

---

# 16. CRM-C01 Crew Pairing Selection

第一版建议：

对每个参与恢复的 crew：

```text
sum(z_p for p owned by crew c) = 1
```

含义：

> 每个 crew 选择一条完整恢复 pairing。

如果当前数据允许某 crew 不参与恢复：

应显式存在：

```text
idle / no-op pairing
```

或由论文/当前 schema 给出明确处理方式。

不要偷偷把：

```text
= 1
```

改成：

```text
<= 1
```

只为了避免 infeasible。

如果现有数据结构并非“一条 pairing 属于一个 crew”，必须按真实 schema 和论文重新映射，不得硬套此公式。

---

# 17. CRM-C02 Required Flight Option Coverage

对每个：

```text
required_operated_option o
```

需要 crew 执行覆盖。

建议建立 / 复用：

```text
A_FC[o,p]
```

表示：

```text
Flight Option o 是否由 Crew Pairing p 作为 operating crew 执行
```

约束：

```text
sum(A_FC[o,p] * z_p) = required_crew_count(o)
```

第一版如果项目只建模单 crew-resource coverage，可暂时：

```text
required_crew_count(o) = 1
```

但必须登记 assumption。

不得把真实航班需要：

```text
Captain + FO + Cabin Crew...
```

的多岗位人员数量自行虚构出来。

如果论文原式就是 aggregate crew unit，则按论文实施。

---

# 18. Operating vs Deadhead 必须分开

这是 Phase 2.4 的关键语义。

同一 Flight Option 出现在 Crew Pairing 中，可能是：

```text
operating leg
deadhead / positioning leg
```

只有：

```text
operating leg
```

能够满足：

```text
required flight crew coverage
```

Deadhead：

```text
不能满足 operating coverage
```

但可以：

```text
产生 deadhead cost
改变 crew 时空位置
成为合法 pairing 的一部分
```

因此 fixed Crew Pairing schema 必须能区分：

```text
operating
deadhead
```

若当前 schema 无法区分：

> 这是 Phase 2.4 的 blocker，必须补 schema / metadata，不能仅用 `leg_option_ids` 猜。

---

# 19. CRM-C03 Non-required Revenue Leakage

与 ARM 相同，需要防止 selected Crew Pairing 执行当前 schedule 未选择的 revenue option。

若：

```text
required_operated_option_ids = {A, B, C}
```

则 Pairing 不应作为 operating crew 执行：

```text
D
```

其中 D 是当前 schedule 未选择的 revenue option。

因此对 non-required revenue operate option：

```text
sum(A_FC[o,p] * z_p) = 0
```

或预过滤所有包含冲突 operating legs 的 pairings。

## 19.1 Deadhead 特例

Deadhead 搭乘的航班必须是：

```text
实际 operated flight
```

因此 deadhead leg 也不能引用：

```text
cancelled flight
non-selected alternate flight option
```

第一版要求：

```text
deadhead_option_id ∈ required_operated_option_ids
```

除非 deadhead 本身使用独立 ferry/positioning transportation schema。

这一点必须有 negative test。

---

# 20. CRM-C04 Fixed Crew Feasibility

被选择的 pairing 必须已经满足当前 fixed-column legality contract。

至少验证当前 schema 能支持的：

```text
crew_id valid
all leg option IDs exist
time order valid
station continuity valid
no CANCEL as operating/deadhead leg
qualification metadata valid if present
rest/duty legality flag valid if present
start station/base compatibility if present
```

如果某规则当前只有：

```text
pairing.legality_satisfied = true
```

则 Phase 2.4 可暂时信任该 flag。

但必须在 Assumption 中写：

```text
Phase 2.4 trusts validated fixed Crew Pairing legality metadata.
```

---

# 21. CRM-C05 Terminal / Crew Ownership

如果 Scenario / Crew schema 已存在：

```text
required_station_at_T_end
crew_base
required_terminal
```

或等价字段，则应在 CRM 中正式约束。

如果当前 schema 没有：

> 不要为了“完整”自行发明 terminal requirement。

应在 Codex Report 标记：

```text
DEFERRED / NOT REPRESENTABLE BY CURRENT DATA
```

论文若明确要求 terminal consistency，而当前 schema 缺字段：

```text
先补最小数据合同
+
Assumption
+
Schema tests
```

再进入模型。

---

# 22. Crew Reassignment

CRM-owned canonical coefficient：

```text
crew_reassignment
```

必须定义什么叫 reassignment。

建议优先沿用项目已有原计划 crew ownership：

```text
original crew ↔ base flight
```

若 selected pairing 让 crew 执行一个原本不属于其计划的 revenue base flight：

```text
count as reassignment
```

但正式实现前必须检查当前 Scenario 是否确实存储：

```text
original crew assignment
```

如果没有：

> 不得自己猜。

可以暂时建立明确 proxy，例如：

```text
pairing metadata contains reassignment_count
```

但必须标记 generated assumption，并验证 metadata 来源。

---

# 23. Deadhead Cost

CRM 是 deadhead 的 canonical owner。

使用 Phase 2.1 Cost Contract：

```text
deadhead_per_minute
```

第一版建议：

```text
deadhead_cost
=
sum(deadhead_leg_block_minutes)
*
deadhead_per_minute
```

前提是当前 Pairing 能明确指出：

```text
哪些 leg 是 deadhead
```

并能获得：

```text
block_minutes
```

如果论文定义的 deadhead cost 不是按分钟：

> 当前映射继续标记为 implementation assumption。

不得在 `crm.py` 中写 Magic Number。

---

# 24. CRM Objective

Phase 2.4 只能收取 CRM-owned cost：

```text
crew_reassignment
deadhead
```

Objective：

```text
min Σ pairing_crm_cost(p) * z_p
```

不得重复计入：

```text
flight delay
flight cancellation
origin change
destination change
aircraft reassignment
ferry
passenger delay
unserved passenger
```

---

# 25. Pairing Cost Pure Function

建议新增：

```python
crew_pairing_cost(...)
```

输入例如：

```text
scenario
recovery_columns
crew_pairing
cost_config
```

输出至少：

```text
total
crew_reassignment_count
crew_reassignment_cost
deadhead_minutes
deadhead_cost
```

必须：

```text
deterministic
side-effect free
auditable
```

求解后 objective 必须重新独立复算。

---

# 26. CRM Model Build 顺序

建议固定：

```text
1. validate Scenario
2. validate RecoveryColumns
3. validate CrewRecoveryRequest
4. build FlightOption index
5. build Crew Pairing index
6. build operating incidence
7. build deadhead incidence
8. identify required operated options
9. detect conflicting/non-required revenue operating legs
10. create z variables
11. objective
12. crew/pairing selection constraints
13. required flight coverage
14. non-required operating prohibition
15. fixed-column legality / terminal constraints
16. optimize through SolverAdapter
17. normalize ModelSolveResult
18. independent CRM audit
```

---

# 27. Crew incidence

不要在多个位置重复扫描 Pairing。

建议构建统一：

```text
CrewRecoveryIncidence
```

至少包含：

```text
crew_to_pairings
operated_option_to_pairings
deadhead_option_to_pairings
pairing_to_operated_options
pairing_to_deadhead_options
```

要求：

```text
immutable
deterministic ordering
explicit errors
```

---

# 28. ModelSolveResult

继续使用：

```text
ModelSolveResult
```

设置：

```text
model = CRM
single_model_only = true
```

不得声称：

```text
完整 recovery plan feasible
```

CRM OPTIMAL 仅表示：

> 当前 required schedule 在现有 fixed Crew Pairings 下，CRM 子模型找到最优 crew recovery。

它不能证明：

```text
Passenger feasible
Integrated recovery feasible
```

---

# 29. CRM Diagnostics

至少输出：

```text
selected_pairing_by_crew
covered_required_options
uncovered_required_options
duplicate_operating_coverage
unexpected_operating_options
deadhead_legs
deadhead_minutes
crew_reassignment_count
crew_legality_status
terminal_status
objective_breakdown
```

并明确区分：

```text
operating coverage
deadhead presence
```

---

# 30. Negative / Fail-fast Cases

至少覆盖：

```text
unknown required option
CANCEL passed as required operated option
FERRY passed as required revenue option
unknown pairing_id
duplicate pairing_id
unknown crew_id
unknown leg option
deadhead references cancelled/unselected option
pairing operates non-required alternate revenue option
required option has zero operating pairing coverage
crew has zero legal pairing
illegal pairing selected
```

---

# 31. Unit Tests

## 31.1 Pairing selection

```text
1 crew / 2 pairings
→ exactly one selected
```

## 31.2 Required operating coverage

```text
required option covered once
→ feasible
```

```text
required option uncovered
→ infeasible
```

```text
duplicate operating coverage
→ prohibited
```

## 31.3 Non-required leakage

构造：

```text
required = FO_F2_D50
```

某 pairing 同时 operating：

```text
FO_F2_D50
FO_F3_D30
```

而 `FO_F3_D30` 不在 schedule 中：

```text
该 pairing 不得被选
```

## 31.4 Deadhead does not satisfy coverage

构造：

```text
Pairing P1:
FO_F2_D50 = deadhead only
```

则：

```text
不能满足 F2 operating coverage
```

这是必须测试。

## 31.5 Deadhead on unselected option

若 Pairing deadhead：

```text
FO_F7_D30
```

但 schedule selected：

```text
FO_F7_ORIG
```

则 Pairing 应被视为 schedule-inconsistent。

## 31.6 Crew reassignment

使用临时非零 coefficient：

```text
crew_reassignment = 100
```

验证：

```text
reassignment count
reassignment cost
objective
```

均正确。

## 31.7 Deadhead cost

使用临时非零：

```text
deadhead_per_minute
```

验证：

```text
deadhead minutes
cost
objective
```

一致。

## 31.8 Legality / terminal

如果 schema 支持：

```text
legal pairing → feasible
all illegal → infeasible
terminal compatible → feasible
all incompatible → infeasible
```

---

# 32. Cross-model contract tests

必须新增：

```text
SRM → canonical operated-option extractor → CRM
```

至少两个场景。

### Case A：无取消

```text
所有 selected flight options 都 operate
→ CRM request 完整保留
```

### Case B：有取消

```text
SRM:
F1 operate
F2 cancel
F3 operate

CRM required:
F1
F3
```

不得包含 F2。

---

# 33. Benchmark Regression

使用当前：

```text
phase1_benchmark_001
phase1_benchmark_001_columns
phase2_test_costs_v1
```

推荐流程：

```text
SRM
↓
canonical required operated options
↓
CRM
```

但如果当前 fixed Crew Pairings 是按 Manual Reference 构建，而不覆盖当前 SRM optimum：

```text
CRM INFEASIBLE
```

可以是合法结果。

不得为使 regression 绿色而：

```text
偷偷修改 SRM
偷偷修改成本
偷偷动态生成 pairing
```

---

# 34. 建议增加第二个 CRM 可行 Benchmark

如果现有 Phase 1 Manual Reference 有明确 crew pairing：

建议另设 regression：

```text
Manual Reference schedule
↓
CRM
↓
FEASIBLE / OPTIMAL
```

用于证明：

> CRM 模型本身能在已知 fixed columns 上运行。

因此可以同时保留：

```text
SRM optimum → CRM may be INFEASIBLE
```

和：

```text
Manual Reference → CRM feasible
```

这与 ARM 当前测试方式保持一致。

---

# 35. Benchmark Audit

不能只测试：

```text
status
```

必须独立检查：

```text
- required options operating coverage == expected
- no unexpected operating revenue option
- deadhead never counted as operating coverage
- deadhead only references valid operated schedule option
- selected pairing ownership valid
- crew legality satisfied
- terminal satisfied if applicable
- reassignment count independently recomputed
- deadhead minutes independently recomputed
- objective independently recomputed
```

---

# 36. Assumptions

执行 Phase 2.4 前读取最新：

```text
assumptions.md
```

从下一个可用编号继续。

可能需要登记：

```text
CRM fixed-column input boundary
Crew Pairing ownership semantics
Operating-vs-deadhead representation
Required crew coverage multiplicity
Fixed-column legality trust
Crew reassignment mapping
Deadhead per-minute cost mapping
CRM single-model result boundary
```

原则：

> 能由论文或数据直接证明的，不写成 generated assumption；缺乏证据的必须明确记录。

---

# 37. Schema 修改原则

如果 CRM 发现当前 Pairing schema 缺少关键字段，例如：

```text
operating vs deadhead
crew ownership
```

允许做**最小必要 schema 扩展**。

但必须：

```text
1. 先更新 schema doc
2. 更新 example columns
3. 更新 validator
4. 更新 broken fixtures
5. 更新 tests
6. 再实现 CRM
```

不得只在 `crm.py` 中通过命名规则或字符串猜测。

---

# 38. 推荐文件结构

建议：

```text
backend/core/recovery_handoff.py
backend/core/crm.py
backend/core/crew_incidence.py
```

如果成本逻辑需要独立：

```text
backend/core/crew_cost.py
```

测试：

```text
tests/unit/test_recovery_handoff.py
tests/unit/test_crm.py
tests/unit/test_crew_incidence.py
tests/regression/test_phase2_crm_benchmark_001.py
```

按当前仓库实际风格适当合并，不要求为了形式过度拆文件。

---

# 39. Gurobi Integration

继续沿用 Phase 2.3 的不可 skip integration gate。

Phase 2.4 正式验收报告必须明确：

```text
total tests
passed
failed
skipped
Gurobi version
CRM integration executed = yes/no
```

如果 CRM integration 被 skip：

```text
Phase 2.4 不得标记完整 PASS
```

---

# 40. Phase 2.4 Acceptance Criteria

Phase 2.4 只有以下全部满足才 PASS：

- [ ] 已核对论文 `(3.13)-(3.15)`；
- [ ] Paper equation → implementation mapping 已记录；
- [ ] 使用 fixed Crew Pairings；
- [ ] 不动态生成 Crew Pairing；
- [ ] CRM 不重新决定 SRM schedule；
- [ ] canonical operated-option handoff 被复用；
- [ ] cancellation 不进入 CRM required coverage；
- [ ] operating / deadhead 明确区分；
- [ ] deadhead 不可满足 operating coverage；
- [ ] required revenue options 得到正确 crew coverage；
- [ ] non-required operating revenue option 不得泄漏；
- [ ] deadhead 不能搭乘未执行 schedule option；
- [ ] pairing / crew ownership constraint 生效；
- [ ] fixed-column legality contract 生效；
- [ ] terminal/base constraint 在数据支持时生效；
- [ ] Crew Reassignment cost 真正实现并有非零测试；
- [ ] Deadhead cost 真正实现并有非零测试；
- [ ] CRM 只收取 CRM-owned cost；
- [ ] objective 可独立复算；
- [ ] Normal / Negative / Infeasible tests 完整；
- [ ] SRM→CRM cancellation regression PASS；
- [ ] 至少一个 CRM feasible regression；
- [ ] 对 fixed-column coverage 不足能正确返回 INFEASIBLE；
- [ ] full pytest PASS；
- [ ] Gurobi integration 实际运行；
- [ ] assumptions 已更新；
- [ ] schema/doc/tests 同步；
- [ ] README / reproduction plan 状态同步；
- [ ] 未修改 HTML；
- [ ] 未进入 PRM；
- [ ] 未进入 Integrated Oracle / Benders / CG。

---

# 41. Phase 2.4 Codex Report

完成后新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase2_4_fixed_column_crm_report.md
```

至少包括：

```text
1. Modified Files
2. Paper (3.13)-(3.15) Mapping
3. CRM Input Contract
4. Crew Pairing Schema / Changes
5. Operating vs Deadhead Semantics
6. Constraint Mapping Table
7. Cost Ownership
8. New Assumptions
9. Unit / Negative / Infeasible Tests
10. SRM → CRM Handoff Test
11. Benchmark Result
12. Coverage Audit
13. Deadhead Audit
14. Crew Reassignment Audit
15. Objective Audit
16. Full Pytest Result
17. Gurobi Result
18. Known Limitations
19. Acceptance Checklist
20. Next Recommended Step
```

最终必须明确：

```text
Phase 2.4 PASS
```

或：

```text
Phase 2.4 NOT PASS
```

---

# 42. Phase 2.4 明确禁止

不得：

```text
修改 HTML / Frontend
实现 Passenger Recovery
实现 Integrated Oracle
实现 Benders
实现 Column Generation
动态生成 Pairings
引入未记录的真实航司 Crew Rule
使用字符串命名猜测 operating/deadhead
为了可行而自动放松 coverage
为了可行而自动修改 SRM result
为了匹配人工结果修改 Cost Config
```

---

# 43. Phase 2.4 完成后的下一步

只有 Phase 2.4 PASS 后，再进入：

```text
Phase 2.5 Fixed-Column PRM
```

主要处理：

```text
Passenger itinerary / reaccommodation
Seat capacity
Passenger delay
Unserved passenger
```

此阶段才正式解决 Passenger Seat Inventory / Market-seat 与 Passenger Capacity 的进一步关系。

不要在 Phase 2.4 提前实现。
