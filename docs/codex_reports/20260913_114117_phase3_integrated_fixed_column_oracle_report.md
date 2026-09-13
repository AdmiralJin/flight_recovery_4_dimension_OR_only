# Phase 3 Full Integrated Fixed-Column Oracle Report

生成时间：2026-09-13 11:41:17（Asia/Shanghai）

## 1. Modified Files

核心实现：

- `backend/core/integrated_oracle.py`：新增 Integrated request、单一 MIP builder、solve wrapper、manual candidate audit、local/cross-model/objective independent audit。
- `backend/core/__init__.py`：导出 Phase 3 public API。

测试与数据：

- `data/examples/toy_case_004.json`
- `data/columns/toy_case_004_columns.json`
- `data/capacities/toy_case_004_capacity.json`
- `data/examples/toy_case_005.json`
- `data/columns/toy_case_005_columns.json`
- `data/capacities/toy_case_005_capacity.json`
- `tests/conftest.py`
- `tests/unit/test_integrated_oracle.py`
- `tests/regression/test_phase3_toy_case_004.py`
- `tests/regression/test_phase3_toy_case_005.py`
- `tests/regression/test_phase3_benchmark_001.py`

文档：

- `README.md`
- `assumptions.md`
- `reproduction_notes.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`
- 本报告。

## 2. Integrated Model Scope

Phase 3 v1 已实现 Full Integrated Fixed-Column Oracle：Schedule、Aircraft、Crew、Passenger 在同一个 Gurobi MIP 中联合决策。输入继续使用人工 Recovery Columns、`phase2_test_costs_v1` 与 test/residual passenger capacity。

本次未进入 Scope Limiting、自动 Flight/Aircraft/Crew/Passenger 列生成、Benders、Column Generation、南航业务规则、physical aircraft seat coupling 或 Solve UI。

## 3. Reused Phase 2 Components

实现复用了 Scenario/RecoveryColumns semantic validators、deterministic indices、Recovery/Aircraft/Crew/Passenger incidence、Gate Inventory builder、Passenger Capacity validator、四个 canonical cost functions、SolverAdapter、ModelSolveResult，以及 SRM/ARM/CRM/PRM 的四套 independent diagnostic recomputation。

Phase 2 的外生 `required_operated_option_ids` 仅在 audit 内部由当前 `x` 选择即时构造，用于复用 local audit；它不是 Integrated solve request 输入，也不决定 schedule。

## 4. Decision Variables

同一 solver model token 下建立：

- `x[o]`：revenue OPERATE/CANCEL Flight Option；
- `y[s]`：Aircraft String；
- `z[p]`：Crew Pairing；
- `w[i]`：Passenger Itinerary/UNSERVED。

FERRY 不建立 revenue `x`，继续只作为 Aircraft String leg。

## 5. Local Constraint Blocks

- SRM：Flight Coverage、Strategic Flight、Arrival/Departure Capacity、Gate Inventory Proxy、Market-seat Proxy。
- ARM：one String per Aircraft、Terminal、Maintenance；固定列可行性由既有 semantic validator 先行校验。
- CRM：one Pairing per Crew、Terminal/ownership；固定 pairing legality 由既有 validator 校验。
- PRM：one Itinerary/UNSERVED per Passenger Group；固定 itinerary feasibility 由既有 validator 校验。

Phase 2 中依赖外生 schedule 的 resource/passenger coverage 与 no-leakage 已由 Phase 3 linking 取代。

## 6. Cross-model Linking

新增并同时建模/独立复算五类约束：

1. `INTEGRATED-L01-SCHEDULE-AIRCRAFT`：`sum A_FS[o,s] y[s] = x[o]`。
2. `INTEGRATED-L02-SCHEDULE-CREW`：`sum A_FC_operate[o,p] z[p] = x[o]`。
3. `INTEGRATED-L03-DEADHEAD-SCHEDULE`：每个 deadhead incidence 满足 `z[p] <= x[o]`。
4. `INTEGRATED-L04-PASSENGER-SCHEDULE`：每个 itinerary flight segment 满足 `w[i] <= x[o]`。
5. `INTEGRATED-L05-SEAT-SCHEDULE`：`load[o] <= residual_capacity[o] * x[o]`。

CANCEL 通过令同一 base flight 的所有 OPERATE `x=0`，自动切断 Aircraft、operating Crew、Deadhead 与 Passenger 使用。

## 7. Integrated Objective

目标严格为：

```text
min SRM cost + ARM cost + CRM cost + PRM cost
```

没有模型级权重、epsilon、hidden tie-break 或人工扰动。允许等价最优解。

## 8. Cost Ownership Audit

- SRM：flight delay、cancellation、origin change、destination change。
- ARM：aircraft reassignment、ferry。
- CRM：crew reassignment、deadhead。
- PRM：passenger delay、unserved passenger。

Solver objective 之外，audit 使用相同 canonical cost functions 从 selected columns 独立复算每个子项、四个 owner total 与 grand total，并校验 grand total 等于 Solver objective，未发现重复计费。

## 9. toy_case_004

`FO_T4_F1_ORIG` 的 SRM cost 最低，但没有 Aircraft String coverage；`FO_T4_F1_D10` 延误 10 分钟且具有完整资源列。Integrated Oracle 选择 `FO_T4_F1_D10`，结果：

```text
status = OPTIMAL
SRM = 10
PRM = 100
grand_total = 110
```

该算例证明 Aircraft feasibility 能反向改变 schedule choice。

## 10. toy_case_005

原计划 option 的 residual capacity 为 0；D10 option 有 10 个 residual seats，可承载完整 10 人 group。模型在 unserved penalty 与 passenger delay 间联合比较后选择 `FO_T5_F1_D10` / `PI_T5_P1_D10`：

```text
status = OPTIMAL
SRM = 10
PRM = 1000
grand_total = 1010
unserved_passengers = 0
```

Seat constraint 实际 active，Passenger cost/capacity 能反向改变 schedule choice。

## 11. Manual Reference Audit

从 `phase1_benchmark_001_expected.json` 读取 Flight Option、Aircraft String、Crew Pairing、Passenger Itinerary 四类人工选择，在不求解该候选的情况下执行完整 local、cross-model 与 objective audit：

```text
all_constraints_satisfied = true
constraint_violation_count = 0
manual_candidate_integrated_objective = 18080
```

因此 Manual Reference 是可解释、已程序化验证的 integrated feasible upper bound。

## 12. phase1_benchmark_001 Result

Gurobi 13.0.3 实际求解结果：

```text
status = OPTIMAL
objective = 18080
manual upper bound = 18080
objective <= manual upper bound = true
```

选中 schedule 为：F1 ORIG、F2 D50、F3 ORIG、F4–F9 ORIG、F10 D20、F11 D10、F12 ORIG。该 schedule 与 Manual Reference 的恢复决策一致；验收不要求所有等价 assignment vector 必须唯一。

## 13. Integrated Objective Breakdown

Benchmark 的独立复算如下：

| Owner | Breakdown | Total |
|---|---|---:|
| SRM | flight delay 80；cancellation/origin/destination change 0 | 80 |
| ARM | aircraft reassignment 0；ferry 0 | 0 |
| CRM | crew reassignment 0；deadhead 0 | 0 |
| PRM | passenger delay 18000；unserved 0 | 18000 |
| Integrated | 四个 owner 合计 | 18080 |

## 14. Cross-model Independent Audit

求解后重新提取 `x/y/z/w` 数值，并独立检查：selected/unselected Aircraft coverage、selected/unselected operating Crew coverage、Deadhead flight execution、Passenger flight execution、seat load/right-hand-side，以及全部 Phase 2 local constraints。

Benchmark 结果为 `cross_model_audit.all_constraints_satisfied=true`、总 violation count `0`。Unit tests 还分别构造并检出：无 Aircraft、无 operating Crew、Passenger 引用未选 option、capacity 超限；另以真实 MIP 证明 deadhead 引用未选 option和互补但无联合交集的 alternatives 均 INFEASIBLE。

## 15. Test / Gurobi Result

执行命令与结果：

```text
python -m pytest tests/unit/test_integrated_oracle.py \
  tests/regression/test_phase3_toy_case_004.py \
  tests/regression/test_phase3_toy_case_005.py \
  tests/regression/test_phase3_benchmark_001.py -q -ra
11 passed, 0 failed, 0 skipped

python -m pytest -ra
277 passed, 0 failed, 0 skipped, 1 warning
```

Phase 3 tests 直接断言 Gurobi availability，不使用 skip。warning 是既有 FastAPI TestClient 的 Starlette/httpx deprecation warning，与本模型结果无关。

## 16. New Assumptions

新增 A-057 `Phase 3 v1 Explicit Cross-model Linking`，登记五类 linking、CANCEL 自动切断、FERRY ARM ownership、UNSERVED 无 Flight reference，以及未来分解/动态列必须保持 Oracle 等价的条件。

未改变 A-056，也未静默改变 Market-seat Proxy、residual capacity、Passenger group indivisibility、cost ownership 或 tie-breaking policy。

## 17. Known Limitations

- 结论只对当前人工 fixed columns 成立，可能存在 fixed-column coverage gap。
- capacity 是 test/residual profile，不是 selected aircraft/equipment 的 physical seats。
- Market-seat 仍是 provisional schedule proxy。
- Aircraft turn、真实 Crew duty/rest、Passenger MCT 和生产业务规则尚未建模。
- Cost profile 是 abstract test units，不是生产成本标定。
- 未提供 Solve UI；Phase 3 仅提供后端 Oracle/API-level Python contract。

## 18. Acceptance Checklist

- [x] x/y/z/w 位于同一 MIP。
- [x] SRM/ARM/CRM/PRM local blocks 正确保留或由 semantic validator 防守。
- [x] Schedule→Aircraft、Schedule→Crew、Deadhead→Schedule、Passenger→Schedule、Seat→Schedule linking 完成。
- [x] CANCEL 自动切断资源与旅客使用；FERRY 保持 ARM owner。
- [x] Integrated objective 无重复计费、模型级权重或 hidden epsilon，四 owner 可独立复算。
- [x] `toy_case_004`、`toy_case_005` PASS。
- [x] Manual Reference 完成 full integrated audit。
- [x] `phase1_benchmark_001` 求得 jointly feasible optimum。
- [x] Integrated result 包含 local/cross-model/objective independent audit。
- [x] full pytest 0 failed、0 skipped；Gurobi integration 实际执行。
- [x] assumptions、README、reproduction notes、Reproduction Plan 已同步。
- [x] 未进入 Benders、CG、Generators 或生产业务扩展。

## 19. Final Decision

```text
Phase 3 PASS
```

验收项均有代码、Gurobi regression、independent audit 和文档证据。

## 20. Next Recommended Step

进入 Phase 4 Scope Limiting，以 Phase 3 Integrated Fixed-Column Oracle 作为 Ground Truth。Scope Limiting 通过可手算案例和 benchmark 对齐后，再按路线分别推进 Flight String、Crew Pairing、Passenger Itinerary generators，随后才进入 Fixed-column Benders 与 Column Generation。
