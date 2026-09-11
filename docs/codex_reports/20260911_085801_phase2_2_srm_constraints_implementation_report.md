# Phase 2.2 Fixed-Column SRM 实施报告

- 时间：2026-09-11 08:58:01（Asia/Shanghai）
- 任务依据：`docs/chatgpt_review/PHASE2_2_SRM_CONSTRAINTS_AND_IMPLEMENTATION_PLAN.md`
- 实施范围：Fixed-Column Schedule Recovery Model；不含 Frontend、ARM、CRM、PRM、Integrated Oracle、Benders 或 Column Generation

## 1. Modified Files

新增：

- `backend/core/gate_inventory.py`
- `backend/core/srm.py`
- `tests/unit/test_gate_inventory.py`
- `tests/unit/test_srm.py`
- `tests/regression/test_phase2_srm_benchmark_001.py`
- `docs/codex_reports/20260911_085801_phase2_2_srm_constraints_implementation_report.md`

更新：

- `backend/core/__init__.py`
- `assumptions.md`
- `README.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`
- `reproduction_notes.md`

历史 `data/expected/phase1_benchmark_001_expected.json` 未修改，仍保持 `manual_reference / feasible` 语义。

## 2. Implemented Features

实现 Fixed-Column SRM，并使用稳定约束 ID：

- `SRM-C01-FLIGHT-COVERAGE`：每个 revenue flight 恰选一个 operate/cancel option；
- `SRM-C02-STRATEGIC-FLIGHT`：strategic flight 必须选择 operate option；
- `SRM-C03-ARRIVAL-CAPACITY`：复用 Phase 2.0 arrival incidence；
- `SRM-C04-DEPARTURE-CAPACITY`：复用 Phase 2.0 departure incidence；
- `SRM-C05-GATE-INVENTORY`：机场级 provisional aggregate ground inventory；
- `SRM-C06-MARKET-SEAT`：`MARKET_SEAT_PROXY`，仅保证 market flight 不取消。

其他实现要点：

- SRM 只为 revenue `operate` / `cancel` option 建二元变量；Ferry 明确排除并留给 ARM；
- Objective 复用 Phase 2.1 `schedule_flight_option_cost`，只计算 SRM-owned delay/cancellation/origin/destination change；
- Gate builder 生成确定性、不可变 checkpoint/coefficient 结构；
- Gate checkpoint 覆盖 recovery start、全部 candidate movement times 和 AirportInterval 边界；
- 同一机场同一时刻到港/离港先净额化再检查库存；
- 无 interval、歧义 gate capacity、初始库存超容、重复 option 等情况 fail fast；
- 求解结果继续使用通用 `ModelSolveResult`，固定标记 `model = SRM`、`single_model_only = true`；
- 求解后独立复算覆盖、战略、容量、Gate、Market proxy 和 Objective，不仅依赖 Solver status。

## 3. Tests Added

新增 19 个 Phase 2.2 unit/regression tests，覆盖：

- exactly-one、缺失 options、operate/cancel、Ferry exclusion；
- strategic cancel forbidden、cancel-only infeasible、delayed operate allowed；
- arrival/departure capacity 正常、超载、调度响应、`[start,end)` 边界、cancel 排除；
- Gate departure/arrival 库存变化、同刻净额、超容、初始超容、缺 interval、重复 coefficient source、不可变性和确定性；
- Market Service Preservation Proxy 的禁止取消与无 operate option infeasible；
- unknown base flight、duplicate option ID；
- `phase1_benchmark_001` 的真实 Gurobi 求解和独立约束/目标审计。

## 4. Test Results

执行：

```text
python -m compileall -q backend tests
pytest -q
git diff --check
```

结果：

```text
158 passed
0 failed
0 skipped
1 existing StarletteDeprecationWarning
compileall passed
git diff --check passed
```

实际求解器：Gurobi 13.0.3。

## 5. Known Assumptions

已先登记后实现：

- A-027：SRM decision domain 与 Ferry exclusion；
- A-028：`strategic_flag` 映射为 no-cancel；
- A-029：Provisional Aggregate Gate Inventory；
- A-030：Same-Timestamp Gate Event Netting；
- A-031：Market Service Preservation Proxy；
- A-032：Phase 2.2 single-model result boundary。

论文定义的 C01–C04 与工程生成的 C05/C06 在 diagnostics 中分别标记 provenance，未混写。

## 6. Known Limitations

- Gate 是机场级 aggregate proxy，不是 gate-number、terminal、机型兼容或 tail-level occupancy；
- 现有 benchmark 的 AirportInterval 未覆盖完整 recovery window，因此只在同一机场已声明 gate capacities 完全一致时做显式 provisional extrapolation；
- Market constraint 不证明 `available_seats >= min_seats`，因为尚无 aircraft/equipment seat-capacity contract；
- SRM 不检查 Aircraft String、Maintenance、Crew legality、Passenger reaccommodation 或 Ferry feasibility；
- SRM optimum 不能表述为完整综合恢复方案可执行。

## 7. Comparison With Oracle

`phase1_benchmark_001` 的 Fixed-Column SRM 结果：

```text
status = OPTIMAL
objective = 70 abstract_cost_units
selected retiming = F2_D50 + F10_D20
cancelled flights = none
all independent constraint checks = satisfied
```

Phase 1 Manual Reference 为 80 分钟，并额外选择 `F11_D10`。该 10 分钟是需要由后续 Aircraft/Crew/Passenger 资源模型解释的差异，不能据此反向修改 SRM。按照任务要求，没有为匹配 80 分钟调整成本或历史 Expected；Manual Reference 仍保持完整恢复人工参考，而 SRM 的 70 只代表当前 schedule submodel/proxy 合同下的最优值。

## 8. Next Recommended Step

进入 Phase 2.3 Fixed-Column ARM：基于现有 Aircraft Strings 建立 tail assignment、flight-option coupling、Ferry、Maintenance 与 aircraft canonical objective，并以本次 SRM 结果作为单模型边界，不在 ARM 中重复收取 SRM 成本。
