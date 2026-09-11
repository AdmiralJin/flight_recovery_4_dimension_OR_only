# Phase 2.3 Fixed-Column ARM 实施报告

- 时间：2026-09-11 09:31:04（Asia/Shanghai）
- 任务依据：`docs/chatgpt_review/PHASE2_2_REVIEW_FIX_AND_PHASE2_3_ARM_PLAN.md`
- 论文来源：`docs/An Optimization Approach to Airline Integrated Recovery.pdf`
- 范围：Fixed-Column Aircraft Recovery Model；不含动态 String、CRM、PRM、Integrated Oracle、Benders、Column Generation 或 Frontend

## 1. Modified Files

新增：

- `backend/core/arm.py`
- `tests/unit/test_arm.py`
- `tests/regression/test_phase2_arm_benchmark_001.py`
- `tests/regression/test_phase2_gurobi_integration_gate.py`
- `docs/codex_reports/20260911_091708_phase2_2_review_fix_report.md`
- `docs/codex_reports/20260911_093104_phase2_3_fixed_column_arm_report.md`

更新：

- `backend/core/gate_inventory.py`
- `backend/core/__init__.py`
- `backend/config/costs.py`
- `backend/config/__init__.py`
- `tests/unit/test_gate_inventory.py`
- `tests/regression/test_phase2_srm_benchmark_001.py`
- `assumptions.md`
- `README.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`
- `reproduction_notes.md`

未修改 Frontend、Phase 1 Expected/Manual Reference、Scenario/Columns 正式 benchmark 数据。

## 2. Paper (3.8)-(3.12) Mapping

已直接核对论文第 9 页 ARM formulation：

| 论文项 | 论文语义 | 当前工程映射 |
|---|---|---|
| (3.8) | tail-to-string assignment cost objective | `sum(aircraft_string_cost * y)`，只含 ARM-owned reassignment/Ferry |
| (3.9) | SRM 已选 String 分配给 eligible aircraft | 当前 SRM 输出 Flight Options，因此映射为 required option exact coverage + non-required revenue zero leakage |
| (3.10) | 每架 aircraft 的 String assignment | `ARM-C01` 每架 aircraft 恰选一条显式 fixed String；idle 必须是显式 null String |
| (3.11) | maintenance opportunity cover | `ARM-C04` 对 maintenance-required tail 选择 validated `maintenance_satisfied` String |
| (3.12) | binary tail/String assignment | 每个 `y[string_id]` 为 binary |

论文正文中的 terminal/null-string 和其他 tail eligibility 规则映射到 `ARM-C03` 与 pre-model `ARM-C05`。当前 tail-specific String Schema 与论文 generic equipment string 结构不同，差异已登记为 implementation mapping assumptions。

## 3. ARM Input Contract

新增 immutable：

```text
AircraftRecoveryRequest
- scenario_id
- required_operated_option_ids
```

入口验证：

- scenario ID 必须一致；
- ID 必须唯一且存在；
- 只能是 revenue `operate` option；
- 同一 base flight 最多一个 required option；
- ARM 不读取 SRM 全局变量，也不重新选择 schedule。

Unit tests 可直接构造 request；benchmark 从 Phase 2.2 SRM diagnostics 提取 selected operated options，再显式传给独立 ARM。

## 4. Constraint Mapping Table

| ID | 实现 | 来源 |
|---|---|---|
| `ARM-C01-AIRCRAFT-STRING-SELECTION` | 每架 aircraft 的 tail-specific candidate String 选择和 = 1 | paper (3.10) + A-034 |
| `ARM-C02-FLIGHT-OPTION-COVERAGE` | required revenue option coverage = 1；non-required revenue option coverage = 0 | paper (3.9) fixed-option mapping + A-035 |
| `ARM-C03-TERMINAL-STATION` | 每架 aircraft 的 selected terminal-compatible String 选择和 = 1 | paper prose + A-036 |
| `ARM-C04-MAINTENANCE` | maintenance-required aircraft 的 eligible satisfied String 选择和 = 1 | paper (3.11) + A-037 |
| `ARM-C05-STRING-FEASIBILITY` | 建模前复用完整 Recovery Columns semantic validation | pre-model validation + A-036 |

`ARM-C05` 是 validation gate，不伪装成额外数学公式；二元变量域单独记录为 paper (3.12)。

## 5. Cost Ownership

新增 pure `aircraft_string_cost` 与 immutable breakdown：

```text
total
reassignment_count
reassignment_cost
ferry_minutes
ferry_cost
```

规则：

- revenue leg 的 `base_flight.original_aircraft != string.aircraft_id` 计一次 reassignment；
- Ferry 按 `block_minutes * ferry_per_minute`；
- 系数只来自 `FixedColumnCostConfig`；
- Columns `cost_components` 不是真源；
- 不收取 delay/cancel/route change、Crew 或 Passenger 成本。

非零临时 reassignment coefficient 测试确认 objective 会响应；delayed operated option 测试确认 ARM 不重复收取 SRM delay。

## 6. New Assumptions

按“先登记、后实现”新增：

- A-033：ARM external schedule input boundary；
- A-034：one explicit tail-specific String per aircraft；
- A-035：paper (3.9) 的 fixed-option/no-leakage 映射；
- A-036：terminal 与 fixed-string eligibility；
- A-037：validated `maintenance_satisfied` flag trust；
- A-038：reassignment/Ferry cost mapping；
- A-039：ARM single-model result boundary。

同时更新 A-029，完成 Phase 2.2 Gate internal/terminal boundary review fix。

## 7. Unit / Negative Tests

新增 17 个 ARM unit test cases，覆盖：

- 1 aircraft / 2 strings exactly-one；
- required option exact coverage、无 covering String、duplicate coverage；
- non-required conflicting revenue option leakage；
- terminal compatible/incompatible；
- maintenance false、required+satisfied、required+unsatisfied；
- ARM 不收取 SRM delay；
- non-zero reassignment coefficient；
- Ferry 可作为 String leg、排除 revenue coverage、minutes/cost 正确；
- request duplicate、unknown、cancel、同 base conflicting options；
- duplicate String、unknown aircraft、unknown leg、cancel leg；
- aircraft 没有显式 candidate String。

新增 2 个 ARM benchmark regressions 和 1 个不可 skip 的 Gurobi Phase 2 integration gate。Phase 2.2 review fix 另新增 3 个 Gate boundary tests。

## 8. Benchmark Result

### SRM optimum → ARM

```text
SRM status = OPTIMAL
SRM objective = 70
required schedule includes F2_D50, F10_D20, F11_ORIG
ARM status = INFEASIBLE
```

独立 fixed-column analysis：

```text
aircraft_without_schedule_compatible_string = [AC4]
required_options_without_eligible_string = [F3_ORIG, F11_ORIG, F12_ORIG]
```

AC4 的现有 Strings 均会携带至少一个 non-required revenue option（例如 `F11_D10` 或 `F10_ORIG`），因此零泄漏合同正确拒绝。没有调整 SRM objective，也没有静默新增/修改 Aircraft String。

### Phase 1 Manual schedule → ARM

```text
ARM status = OPTIMAL
selected strings = AS_AC1_SWAP_F10, AS_AC2_ORIGINAL,
                   AS_AC3_ORIGINAL, AS_AC4_SWAP_F3_ORIG
ARM objective = 0
reassignment count = 2
ferry minutes = 0
```

该结果只证明人工 schedule 在现有 Aircraft Strings 下的 aircraft 子问题可行，不把 Manual Reference 改称 integrated optimum。

## 9. Objective Audit

求解后对每条 selected String 重新调用 pure canonical cost evaluator，分项复算 reassignment 与 Ferry；总和必须在容差内等于 Solver objective，否则抛出 runtime audit error。

Manual benchmark 当前 `aircraft_reassignment = 0`，因此两次 reassignment 的成本为 0；无 Ferry，ARM objective 为 0。这不表示 reassignment 逻辑被省略，non-zero coefficient unit test 已验证其真实生效。

## 10. Terminal / Maintenance Audit

- 每架 aircraft 都独立复算 selected String end station 与 required terminal；
- maintenance-required AC4 通过 `maintenance_to_strings` incidence 复算；
- diagnostics 输出 selected String、required/actual terminal、maintenance flag、eligible stations 和 satisfied 状态；
- 无 compatible terminal 或 maintenance String 的模型测试均返回 infeasible。

## 11. Ferry / Reassignment Audit

- Ferry 只随 selected Aircraft String 进入 ARM；
- Ferry 不在 required/non-required revenue coverage 域中；
- unit case：60 ferry minutes × 5 = 300 ARM cost；
- benchmark manual schedule：0 Ferry minutes；
- reassignment 逐 revenue leg 比较 original aircraft 与 String aircraft，并输出总次数。

## 12. Full Pytest Result

```text
181 collected
181 passed
0 failed
0 skipped
1 existing StarletteDeprecationWarning
compileall passed
black --check passed
git diff --check passed
```

## 13. Gurobi Result

```text
available = true
version = 13.0.3
non-skippable Phase 2 integration gate = executed and passed
SRM integration = executed
ARM feasible integration = executed
ARM infeasible integration = executed
```

## 14. Known Limitations

- 使用人工 fixed Aircraft Strings，不动态生成新 String；
- SRM 的 70-cost schedule 因 fixed-column coverage 不足而 ARM infeasible；
- String 已预绑定 tail，不是论文 generic equipment String 后再分配 tail 的原始变量结构；
- `maintenance_satisfied` 是 validated fixed-column flag，不是细粒度维修排程；
- 没有 aircraft minimum turn time、tail-specific airport restriction 或真实航司成本校准；
- ARM optimal/feasible 不代表 Crew、Passenger 或 Integrated Recovery 可行。

## 15. Acceptance Checklist

- [x] 核对并记录 paper (3.8)-(3.12)；
- [x] 使用 fixed Aircraft Strings，无动态生成；
- [x] 外生 schedule contract，ARM 不重新决定 SRM schedule；
- [x] 每架 aircraft exactly one String；
- [x] required option exact coverage；
- [x] non-required revenue no leakage；
- [x] Ferry 属于 ARM 且排除 revenue coverage；
- [x] Terminal / Maintenance 生效；
- [x] Reassignment / Ferry canonical cost 生效；
- [x] Objective 独立复算；
- [x] normal/infeasible/negative/benchmark tests；
- [x] full pytest PASS，Gurobi 实际执行且 0 skipped；
- [x] assumptions、README、plan、reproduction notes 同步；
- [x] 未修改 HTML；
- [x] 未进入 CRM/PRM/Integrated Oracle/Benders/CG。

## 16. Next Recommended Step

进入 Phase 2.4 Fixed-Column CRM：显式接收 required operated options，使用现有 Crew Pairings 建立 crew assignment、operating/deadhead coverage、terminal/pairing feasibility，以及 crew reassignment/deadhead canonical objective；继续保持与 SRM/ARM 独立，不提前实现 Integrated Oracle。

```text
Phase 2.3 PASS
```
