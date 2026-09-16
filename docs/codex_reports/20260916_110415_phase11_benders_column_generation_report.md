# Phase 11 Benders + Column Generation 实施报告

时间：2026-09-16 11:04:15（Asia/Shanghai）

工作分支：`feature/phase-110`

Phase 11 实现提交：

```text
7e7d0c3 feat: implement phase 11 benders column generation
```

## 1. Phase 10 收尾与基线

Phase 10 已先完成格式、编译与 394 项全量回归，并以 `--no-ff` 合入 `main`：

```text
801101f docs: close phase 10 and add phase 11 plan
62593f4 merge: phase 10 crew pairing column generation
f997a6a docs: record phase 10 closeout merge
```

Phase 11 分支严格从 `f997a6a` 建立。单独收尾记录见 `docs/codex_reports/20260916_104424_phase10_closeout_and_merge_report.md`。

计划建议分支名为 `feature/phase-11`，但用户明确指定 `feature/phase-110`，本次以用户指定名称为准。

## 2. Modified Files

核心与配置：

```text
backend/config/benders_column_generation.py
backend/config/__init__.py
backend/core/benders_column_generation.py
backend/core/__init__.py
```

数据与测试：

```text
data/config/phase11_test_benders_cg_v1.json
data/examples/toy_case_013_benders_column_generation.json
data/columns/toy_case_013_benders_column_generation_columns.json
data/capacities/toy_case_013_benders_column_generation_capacity.json
tests/conftest.py
tests/unit/test_benders_column_generation.py
tests/regression/test_phase11_benders_cg_oracle.py
tests/regression/test_phase11_benders_cg_cut_validity.py
tests/regression/test_phase11_benders_cg_integrality_boundary.py
tests/regression/test_phase11_benders_cg_benchmark.py
```

文档：

```text
README.md
assumptions.md
docs/AIR_HTML_Python_Reproduction_Plan.md
reproduction_notes.md
```

## 3. Phase 11 Architecture

正式求解链为：

```text
SRM Schedule Master: x + thetaA + thetaC + thetaP
        ↓ canonical Schedule
Aircraft Phase 9 full-LP CG certificate
Crew Phase 10 full-LP CG certificate
Passenger fixed-column exact MIP
        ↓ valid cuts
generated-column binary ARM / CRM + exact PRM
        ↓ integer-feasible incumbent
LB / UB closure
        ↓
Integrated diagnostics audit
```

公开入口为 `solve_benders_with_column_generation(...)`。Phase 8 `solve_fixed_column_benders(...)` 未被修改。

## 4. Why Phase 8 Cuts Are Not Reused

Phase 8 的 recourse 是冻结显式列上的 exact binary MIP；Phase 11 的 Aircraft/Crew recourse 列池会动态增长。若直接复用 Phase 8 cut，会把 restricted pool 的 objective 或 infeasibility 错当成完整隐式 universe 的事实。

因此 Phase 11 使用独立 `BendersCgCut` 与 `BendersCgCutSource`，只接受：

- `AIRCRAFT_FULL_LP`：Aircraft pricing 收敛后的 full implicit LP；
- `CREW_FULL_LP`：Crew pricing 收敛后的 full implicit LP；
- `PASSENGER_EXACT_MIP`：固定 Passenger Itineraries 上的 exact MIP；
- Phase-I certified Aircraft/Crew LP infeasibility；
- exact PRM infeasibility。

不存在 restricted RMP 或 generated binary objective 的 cut source。

## 5. Implicit Column Universe

`benders_cg_implicit_universe_fingerprint(...)` 覆盖：

- Scenario semantic content；
- Flight Options；
- Passenger Itineraries；
- Cost Config 与 Passenger Capacity Profile；
- Aircraft String / Crew Pairing generation configs；
- Aircraft / Crew CG configs；
- Phase 11 config；
- scope mode。

运行中生成的 Aircraft String / Crew Pairing IDs 不进入 fingerprint。各次动态 pool 另有 diagnostics fingerprint。

## 6. Cut Validity / Invalidation Policy

- Solver 每次从空 cut 集开始，禁止导入 Phase 8 cuts。
- Optimality cut 使用 `theta_k >= q_k - q_k * Delta`，即 `M_k = q_k`。
- 同一 Schedule 只生成一个 no-good，即使多个 recourse 同时 infeasible。
- cut identity 为 cut type、subproblem、Schedule 与 implicit-universe fingerprint。
- cut provenance、source/subproblem 对应关系、canonical Schedule 与 fingerprint 均进行验证。
- implicit contract 改变需要重新启动求解，旧 cuts 不可复用。
- 显式 pool 增长不改变 pricing-certified full-LP cut 的有效性。

## 7. Aircraft CG Recourse

每个首次访问 Schedule 独立调用真实 Phase 9 CG。仅 `OPTIMAL` 的 LP objective 生成 Aircraft lower-bound cut；`INFEASIBLE` 只在 Phase-I 无改善列时形成 no-good；`NOT_CONVERGED`/`ABORTED` 不生成 cut并直接返回相应非成功状态。

CG 返回列会在 binary ARM 中求解，所得 objective 仅用作 UB。

## 8. Crew CG Recourse

每个首次访问 Schedule 独立调用真实 Phase 10 CG，保留 OPERATE coverage 与 DEADHEAD reposition 语义。状态与 cut 策略同 Aircraft；CG 返回 Pairings 只进入 binary CRM incumbent。

## 9. Passenger Fixed Recourse

Phase 11 未实现 Passenger CG。Passenger Itineraries 继续固定显式输入，PRM 继续使用 exact MIP。Passenger objective 没有在 Schedule 或其他 owner 中重复计费。

## 10. LP Lower Bound vs Binary Upper Bound

Aircraft/Crew pricing-certified LP objective 进入 Master cut；generated-pool binary ARM/CRM objective 只进入：

```text
UB_candidate = Schedule + ARM_binary + CRM_binary + PRM_exact
```

测试通过人为把 binary ARM objective 提高 1，验证 lower-bound cut 仍保持 LP 值 0，最终返回 `INTEGRALITY_REQUIRED`，而不是错误宣布 OPTIMAL。

## 11. Integrality Boundary

当相同 Schedule 已有全部合法 LP cuts、Master 仍满足 `LB < UB`，且 Aircraft 或 Crew binary objective 与 LP objective 不相等时，返回：

```text
INTEGRALITY_REQUIRED
```

若 LP 与 generated binary objective 在 tolerance 内相等，则记录 owner-specific integrality certificate。

## 12. toy_case_013

三个 Schedule 的确定性轨迹：

| Master 轮次 | Schedule | LB | Candidate UB | 结果 |
|---:|---|---:|---:|---|
| 1 | `FO_T13_F1_ORIG` | 0 | — | 08:00 curfew 导致 Aircraft Phase-I certified infeasible，加入 no-good |
| 2 | `FO_T13_F1_D10` | 10 | 2510 | resource feasible，但 Passenger 只能 UNSERVED |
| 3 | `FO_T13_F1_D20` | 20 | 220 | 新 incumbent，Passenger delay 200 |
| 4 | `FO_T13_F1_D20` | 220 | — | Master LB 与 incumbent UB 闭合，不重复调用 CG |

最终成本：

```text
Schedule 20
Aircraft 0
Crew 0
Passenger 200
Total 220
```

## 13. Full Explicit Integrated Oracle

toy oracle 使用 Phase 5/6 全枚举得到 2 Aircraft Strings 与至少 3 Crew Pairings，再调用现有 Integrated Fixed-Column Oracle。结果：

```text
OBJ_BENDERS_CG = 220
OBJ_FULL_EXPLICIT_INTEGRATED = 220
```

## 14. Benders-CG Trajectory

toy：4 个 Master 轮次、3 个 unique visited Schedules、1 个 feasibility cut 与 6 个 recourse cuts。

benchmark：8 个 Master 轮次、7 个 unique visited Schedules；第 2 个 Schedule 首次得到 incumbent `18080`，第 8 轮 Master 证明 `LB = 18080`。

## 15. Benchmark Result

Oracle side：

```text
77 Aircraft Strings
374 Crew Pairings
55 Passenger Itineraries
Full Explicit Integrated Oracle = 18080
```

Formal Phase 11 side：

```text
0 pre-generated Aircraft Strings
0 pre-generated Crew Pairings
55 fixed Passenger Itineraries
Benders + Aircraft CG + Crew CG = 18080
```

最终：

```text
LB = UB = OBJ_FULL_EXPLICIT_INTEGRATED = 18080
```

## 16. Cut Statistics

| Case | Feasibility | Aircraft LP | Crew LP | Passenger exact | Total |
|---|---:|---:|---:|---:|---:|
| toy_case_013 | 1 | 2 | 2 | 2 | 7 |
| phase1_benchmark_001 | 2 | 5 | 5 | 5 | 17 |

## 17. Column / Pricing Statistics

| Case | Aircraft CG calls | Aircraft P-I / P-II | Aircraft generated | Crew CG calls | Crew P-I / P-II | Crew generated |
|---|---:|---:|---:|---:|---:|---:|
| toy_case_013 | 3 | 5 / 2 | 2 | 3 | 6 / 3 | 3 |
| phase1_benchmark_001 | 7 | 35 / 5 | 96 | 7 | 42 / 11 | 167 |

计数为各独立 Schedule CG pool 的总和，不是跨 Schedule 去重后的 global pool；Phase 11 v1 有意不做 warm start。

## 18. LB / UB Trajectory

```text
toy:      initial LB 0, first feasible UB 2510, final LB/UB 220/220
benchmark: initial LB 70, first feasible UB 45070, final LB/UB 18080/18080
```

LB 使用 `max(previous LB, current master objective)`，UB 使用所有 integer-feasible candidates 的最小值。

## 19. Final Integrated Diagnostics

toy 与 benchmark 的最终 generated-column incumbent 均通过现有 Integrated diagnostics：

```text
all_constraints_satisfied = true
```

benchmark 成本分解：

```text
SRM 80
ARM 0
CRM 0
PRM 18000
Grand Total 18080
```

## 20. Formal Enumerator-Independence Test

测试把以下函数 monkeypatch 为立即抛错：

```text
generate_aircraft_strings
brute_force_legal_aircraft_strings
generate_crew_pairings
brute_force_legal_crew_pairings
```

正式 `solve_benders_with_column_generation(...)` 仍在 toy_case_013 上得到 OPTIMAL 220。

## 21. Full Regression

```text
python -m pytest: 406 passed, 0 failed, 0 skipped
python -m compileall -q backend tests: PASS
python -m black --check <Phase 11 Python files>: PASS
git diff --check: PASS
```

唯一 warning 为既有 FastAPI/Starlette `httpx` deprecation warning。

## 22. Known Limitations

- Phase 11 v1 仅支持 `scope=None`。
- Flight Options 固定，不做动态 Schedule option generation。
- Passenger Itineraries 固定显式，不做 Passenger CG。
- Aircraft/Crew CG 是 LP pricing；integer incumbent 仅在当前 generated pools 上求解。
- 正式输入必须清空 Aircraft Strings 与 Crew Pairings，以防全列泄漏。
- 没有 Branch-and-Price、Crew follow-on branching、Passenger branching、跨 Schedule warm pool、dual stabilization 或生产级 pricing acceleration。
- Phase 6 仍是单 duty 测试边界，不代表完整 FAR/CCAR duty/rest 规则。

## 23. Deferred Work

- branching node 下的 Aircraft/Crew pricing；
- integer-improving nonnegative reduced-cost columns；
- Crew follow-on branching；
- 如需要，Passenger branching / Passenger CG；
- dynamic Scope 的 universe contract 与 cut invalidation；
- 生产规模 dominance、stabilization、并行 pricing 与 warm start。

## 24. Next Step

进入 Phase 12 — Integrality / Branching。重点是在不破坏 Phase 11 cut/bound validity 的前提下闭合 ARM/CRM LP 与整数 recourse；不得通过 binary objective 下界割或未经证明的 no-good 绕过该问题。
