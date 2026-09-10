# Phase 2.1 Solver / Cost / ModelResult Contract Report

- 完成时间：2026-09-10 15:12:47 +08:00
- Baseline commit：`42a0b40fb96cc47af769eb0de88f63f1e9bc8ec0`（`feat: complete phase2.0 incidence and index builder`）
- 范围：Phase 2.1 公共合同；未实现 SRM、ARM、CRM、PRM 或 Integrated MIP
- 最终状态：**Phase 2.1 PASS**

## 1. Modified Files

Solver Contract：

- `backend/solver/__init__.py`
- `backend/solver/base.py`
- `backend/solver/gurobi.py`
- `requirements.txt`

Model Result Contract：

- `backend/schemas/model_result.py`
- `backend/schemas/__init__.py`

Cost Contract：

- `backend/config/__init__.py`
- `backend/config/costs.py`
- `data/costs/phase2_test_costs_v1.json`

Tests：

- `tests/unit/test_solver_contract.py`
- `tests/unit/test_gurobi_adapter.py`
- `tests/unit/test_model_result.py`
- `tests/unit/test_cost_config.py`

Documentation：

- `assumptions.md`
- `reproduction_notes.md`
- `README.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`

开始工作时唯一已有工作树改动是用户提供、尚未跟踪的 `docs/chatgpt_review/PHASE2_1_SOLVER_COST_RESULT_CONTRACT.md`。本次将其视为任务输入，没有改写或删除。

## 2. Solver Selected and Version

Primary Solver：

```text
Gurobi Optimizer / gurobipy 13.0.3
```

依赖固定为：

```text
gurobipy==13.0.3
```

当前验证环境使用 pip 包附带的 restricted、size-limited、non-production license，有效期显示为 2027-11-29。它足以运行本阶段的小型解析 LP/MIP；不代表生产授权或未来大规模模型可运行。

## 3. SolverAdapter API

`SolverAdapter` 冻结以下公共能力：

- `create_model`
- `add_variable`
- `add_linear_constraint`
- `set_objective`
- `solve`
- `get_variable_value`
- `get_objective_value`
- `get_status`
- `get_runtime_seconds`
- `get_best_bound`
- `get_mip_gap`
- `get_constraint_dual`
- `get_reduced_cost`
- `close`

统一定义 solver-independent：

- `VariableType`：continuous / integer / binary；
- `ConstraintSense`：less_equal / equal / greater_equal；
- `ObjectiveSense`：minimize / maximize；
- opaque `VariableHandle` / `ConstraintHandle`，并拒绝跨模型 handle；
- `SolverCapabilities`，显式声明 MIP、dual、reduced cost、gap、bound 能力；
- `SolverOutcome`，集中返回归一化状态与 solver metadata。

除 `backend/solver/gurobi.py` 外，业务基础设施没有散落 `gurobipy` API。

## 4. Status Mapping

业务状态固定为：

```text
OPTIMAL
FEASIBLE
INFEASIBLE
UNBOUNDED
INFEASIBLE_OR_UNBOUNDED
NO_SOLUTION
ERROR
```

映射规则：

- 只有 Gurobi `OPTIMAL` 映射为 `OPTIMAL`；
- limit/interrupted/suboptimal 等终止若已有 incumbent，映射为 `FEASIBLE`；
- limit/interrupted 等终止若无 incumbent，映射为 `NO_SOLUTION`；
- infeasible、unbounded、infeasible-or-unbounded 分别保留；
- numeric/unknown status 与 Solver API error 映射为 `ERROR`；
- `raw_status` 和 `termination_reason` 只作为诊断 metadata 保留。

Import、license 或参数错误不得伪装成 `INFEASIBLE`。

## 5. LP Dual / Reduced-Cost Verification

解析 LP：

```text
min x + 2y
s.t. x + y >= 1
x,y >= 0
```

Adapter 实测并与手工解析答案一致：

```text
status = OPTIMAL
x = 1
y = 0
objective = 1
dual(demand) = 1
reduced_cost(x) = 0
reduced_cost(y) = 1
best_bound = 1
```

Dual 和 reduced cost 对 MIP solution 会 fail fast，不会返回无意义值。

## 6. MIP Contract Verification

解析 Binary MIP：

```text
max 3x + 2y
s.t. 2x + y <= 2
x,y binary
```

Adapter 实测：

```text
status = OPTIMAL
x = 1
y = 0
objective = 3
best_bound = 3
mip_gap = 0
runtime_seconds >= 0
```

另有真实 Gurobi infeasible LP、unbounded LP 与无效参数测试，分别验证无伪造 solution 和 `ERROR != INFEASIBLE`。

## 7. ModelSolveResult Design

新增独立 `ModelSolveResult`，不复用 `RecoveryExpected`。字段覆盖：

- model / scenario identity；
- normalized status；
- objective / best bound / MIP gap / runtime；
- selected / continuous variable maps；
- solver name / version / raw status / termination reason；
- diagnostics。

语义约束：

- OPTIMAL / FEASIBLE 必须具有 objective；
- FEASIBLE 可保留非零 gap、incumbent 与 termination reason；
- INFEASIBLE / UNBOUNDED / INF_OR_UNBD / NO_SOLUTION / ERROR 不允许 objective 或 variable solution；
- 非有限数、负 gap/runtime 和未知字段被拒绝；
- JSON serialization round-trip 通过。

`RecoveryExpected` 继续是 Manual Reference / Oracle Fixture，没有修改其职责或正式 benchmark 内容。

## 8. Cost Profile and Units

Canonical profile：

```text
data/costs/phase2_test_costs_v1.json
cost_profile_id = phase2_test_v1
units = abstract_cost_units
```

每个 coefficient 都包含：

```text
value
dimensional unit
canonical owner
source classification
source reference
notes
```

Pydantic 合同拒绝 unknown/missing fields、负数、NaN、Infinity、错误单位和错误 owner。当前实现只增加最小 `schedule_flight_option_cost` pure evaluator，处理 SRM-owned delay/cancel/origin/destination change；Ferry 明确归 ARM，不在该函数重复计费。

## 9. Cost-Source Classification

论文直接映射的测试值：

| coefficient | value | owner | source |
|---|---:|---|---|
| flight_cancellation | 25,000 | SRM | Petersen et al. (2010), Table 2 |
| aircraft_reassignment | 0 | ARM | Table 2 individual-tail assignment cost 的 fixed-column 映射 |
| crew_reassignment | 0 | CRM | Table 2 crew-pairing assignment cost 的 fixed-column 映射 |
| passenger_delay_per_pax_minute | 10 | PRM | Petersen et al. (2010), Table 2 |
| unserved_passenger | 2,500 | PRM | Petersen et al. (2010), Table 2 |

明确的 Implementation Assumptions：

| coefficient | value | owner | reason |
|---|---:|---|---|
| flight_delay_per_minute | 1 | SRM | 应用于 departure delay；论文无直接每 flight-minute 系数 |
| origin_change | 5,000 | SRM | 论文无对应固定系数 |
| destination_change | 5,000 | SRM | 论文无对应固定系数 |
| ferry_per_minute | 5 | ARM | 论文 benchmark 无 ferry-minute 系数 |
| deadhead_per_minute | 5 | CRM | 论文给出 per-flight / return-to-base 值，不是 per-minute |

这些数值在建模前冻结，没有为匹配 80-minute Manual Reference 反向调参，也不声称是真实航空公司成本。

## 10. Cost Ownership

为防 Phase 3 重复计费，owner 固定为：

```text
delay / cancel / origin change / destination change -> SRM
aircraft reassignment / ferry                       -> ARM
crew reassignment / deadhead                       -> CRM
passenger delay / unserved                         -> PRM
```

Columns 的 `cost_components` 不是全局参数真源；唯一 canonical 参数源是版本化 `FixedColumnCostConfig`。

## 11. Assumptions and Reproduction Notes

`assumptions.md` 新增 A-021 至 A-026：

- Primary Solver 和 license / abstraction boundary；
- normalized status mapping；
- RecoveryExpected vs ModelSolveResult；
- abstract test units 和论文来源；
- canonical model ownership；
- 完整 test coefficient 表。

`reproduction_notes.md` 已补充 Phase 2.0、Phase 2.1 完成状态和边界。README 与总计划的当前状态也已同步，唯一下一步为 Phase 2.2。

## 12. Tests Added and Pytest Result

新增 37 个测试，覆盖：

- capability contract 与 normalized status mapping；
- 解析 LP primal / objective / dual / reduced cost；
- 解析 Binary MIP solution / objective / bound / gap / runtime；
- infeasible / unbounded / API error；
- OPTIMAL / FEASIBLE / no-solution ModelSolveResult 语义；
- ModelSolveResult finite values、unknown field 与 serialization；
- canonical cost load、source/owner/unit、round-trip；
- cost missing/unknown/negative/NaN/Inf 防御；
- 最小 schedule option cost evaluator。

完整命令：

```text
python -m pytest
```

结果：

```text
139 passed, 1 warning in 1.65s
```

Phase 0-2.0 的 102 个既有测试全部通过。唯一 warning 是既有 FastAPI/Starlette TestClient 对 `httpx` 的 deprecation warning，与 Phase 2.1 无关。

## 13. Skipped Integration Tests

```text
0 skipped
```

当前 Gurobi 13.0.3 和 restricted small-model license 可用，因此 LP/MIP integration smoke tests 实际执行，未伪装为 PASS。测试仍包含 availability probe；其他环境若 package/license 不可用，会显示包含具体原因的 skip。

## 14. Known Limitations

- restricted license 仅允许小规模、非生产用途；未来正式规模需要合适的 Gurobi license；
- 本次没有 SRM/ARM/CRM/PRM equations，没有业务优化结果；
- `/api/solve` 继续保持安全闸门，Frontend 未启用 Recovered Plan；
- `phase2_test_v1` 是 abstract test-cost profile，不是真实业务成本；
- 论文 per-deadhead-flight / return-to-base 成本尚未扩展为独立字段，当前 per-minute term 明确为 test assumption；
- Gate、Seat Capacity、Turn Time、Crew Legality 等原有后续 blocker 不在本阶段处理；
- Manual Reference 继续是 feasible reference，不是 proven optimal。

## 15. Acceptance

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
Phase 2.2 - Fixed-Column SRM
```

## 16. References

- Petersen et al. (2010), `docs/An Optimization Approach to Airline Integrated Recovery.pdf`, equations (3.1), (3.8), (3.13), (3.16) and Table 2.
- [Gurobi installation and pip license behavior](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python)
- [Gurobi optimization status codes](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/statuscodes.html)
- [Gurobi model attributes](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/model.html)
- [Gurobi linear-constraint dual attribute](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/constraintlinear.html)
- [Gurobi variable reduced-cost attribute](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html)
