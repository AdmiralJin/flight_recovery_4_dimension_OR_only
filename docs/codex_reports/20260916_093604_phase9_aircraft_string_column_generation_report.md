# Phase 9 Aircraft String Column Generation 实施报告

时间：2026-09-16 09:36:04（Asia/Shanghai）

分支：`feature/phase-9`

实现提交：`b495457 feat: implement phase 9 aircraft string column generation`
依据：`docs/chatgpt_review/PHASE8_CLOSEOUT_AND_PHASE9_AIRCRAFT_STRING_CG_PLAN.md`

## 1. Phase 8 baseline

Phase 8 已以 merge commit `0682a93` 合入 `main`，收尾报告 commit 为 `3c15cdd`。本分支从 `3c15cdd` 创建；Phase 9 未修改 Phase 8 Benders master、cuts、Big-M、recourse 或 Integrated audit。

## 2. Modified files

主要新增：

- `backend/config/aircraft_string_column_generation.py`
- `backend/core/aircraft_string_master.py`
- `backend/core/aircraft_string_pricing.py`
- `backend/core/aircraft_string_column_generation.py`
- `data/config/phase9_test_aircraft_string_cg_v1.json`
- `data/examples/toy_case_011_aircraft_string_column_generation.json`
- `data/columns/toy_case_011_aircraft_string_column_generation_columns.json`
- Phase 9 unit/regression tests

同时公开 Phase 5 稳定 Aircraft String semantic key、ID 和构造器，并更新 `README.md`、总计划、`assumptions.md` 与 `reproduction_notes.md`。

## 3. Full-column LP formulation

新增独立 continuous Aircraft String LP Oracle。变量为 `0 <= y_s <= 1`，保留现有 ARM 的 aircraft selection、required/non-required revenue option coverage、terminal station、maintenance 五类语义；目标只使用 canonical ARM owner cost，即 aircraft reassignment 与 ferry minutes。它与 Integrated/Benders ground truth 分离，不以 `18080` 为验收值。

## 4. RMP formulation

Restricted Master 与 Full LP 使用同一构建器和行定义，但只接收当前列池。每次迭代重新创建模型，不执行 solver-specific incremental mutation；所有变量均为 continuous，并通过公共 `SolverAdapter` 接口求解。

## 5. Phase-I formulation

Scope 内 aircraft 默认从空真实列池开始，Scope 外 aircraft 从唯一语义 original string 开始。Phase I 对 RHS=1 的 selection、required coverage、terminal、maintenance 行分别加入代价为 1 的人工变量，真实列成本为 0。人工目标降至 feasibility epsilon 后才进入 Phase II；若仍为正且不存在负 reduced-cost 列，则证明当前固定 Schedule 不可行。

## 6. Dual mapping

新增不可变 `AircraftStringMasterDuals`，分别映射 selection、required coverage、non-required coverage、terminal 与 maintenance dual。Phase 9 仅调用 `SolverAdapter.get_constraint_dual()` 和 `get_reduced_cost()`，未访问 Gurobi 私有模型对象。

## 7. Reduced-cost formula

统一使用实际主问题行系数：

```text
reduced_cost = primal_column_cost - sum(row_dual * column_row_coefficient)
```

Phase I 的真实列成本为 0，Phase II 为 canonical Aircraft String cost。每轮对现有变量同时计算 manual RC 与 solver RC；toy 和 benchmark 最大误差均为 `0.0`。

## 8. Pricing algorithm

定价器复用 `AircraftFlightNetwork`，按确定性 aircraft-local DAG DFS/label traversal 搜索。状态跟踪 path、used option 和 used base flight；默认每个 aircraft、每轮最多加入一条最负 reduced-cost 列。稳定 ID 与 Phase 5 完全一致。

## 9. Pricing legality boundary

正式 pricer 只允许 fixed schedule 中 required revenue `OPERATE` options 与输入 `FERRY` options，不生成 Flight Options，不允许 non-required revenue leakage。每个候选再次通过独立 `validate_generated_aircraft_string()`。正式 CG API 不接收 full string pool；测试通过 monkeypatch 明确禁止调用 Phase 5 full enumerator。

## 10. toy_case_011 design

Toy 含 2 架 aircraft、2 个 required revenue options。每架 aircraft 均有一条 direct 零成本 string 和一条覆盖相同 revenue option、但额外执行两段共 30 分钟 ferry 的 string。Phase I 在相同可行性 reduced cost 下按确定性路径顺序先加入昂贵 string，使 Phase II 能验证真正的负 reduced-cost 改进。

## 11. Pricing-vs-brute-force result

对 toy 的昂贵两列 RMP 读取 dual 后：

- DAG pricer 最小 reduced cost：`-150.0`
- 扫描 Phase 5 full pool 的最小 reduced cost：`-150.0`
- 生成 direct path：与 full pool semantic key/ID 一致

两种独立路径完全一致。

## 12. Full-column LP result

| Case | Full strings | Full-column LP objective | Status |
|---|---:|---:|---|
| toy_case_011 | 4 | 0.0 | OPTIMAL |
| phase1_benchmark_001 | 77 | 0.0 | OPTIMAL |

## 13. CG iteration trajectory

Toy 初始真实列数为 `0`，最终列数为 `4`；Phase I 2 轮、Phase II 2 轮，共 4 轮：

| Iteration | Phase | RMP obj | Artificial obj | Min RC | Added |
|---:|---|---:|---:|---:|---:|
| 1 | I | 6.0 | 6.0 | -3.0 | 2 |
| 2 | I | 0.0 | 0.0 | n/a | 0 |
| 3 | II | 300.0 | 0.0 | -150.0 | 2 |
| 4 | II | 0.0 | 0.0 | n/a | 0 |

最终列按 aircraft 为 `S11_AC1: 2`、`S11_AC2: 2`。采样 CG runtime 为约 `0.013s`。

## 14. Scope result

Scope test 只允许 `S11_AC1` 定价；`S11_AC2` 只保留唯一 original direct string，未进入 pricing。Scope CG 返回 OPTIMAL、objective `0.0`，且 out-of-scope aircraft 列数严格为 1。

## 15. Benchmark result

Benchmark 初始真实列数为 `0`，Full pool 为 `77`，CG 最终只保留 `15` 列：`AC1:3`、`AC2:4`、`AC3:4`、`AC4:4`。Phase I 5 轮、Phase II 1 轮，共 6 轮；人工目标轨迹为 `21 -> 13 -> 8 -> 5 -> 0`，对应最小 RC 为 `-8, -7, -4, -5`。采样 CG runtime 为约 `0.034s`。

```text
Full-column LP objective = 0.0
CG LP objective          = 0.0
Difference               = 0.0
```

## 16. Termination exhaustive audit

该 audit 是独立边界，允许接收 Phase 5 full pool，但正式 CG 不调用它。

- toy：最终已含全部 4 列，遗漏列 `0`，PASS。
- benchmark：最终 15/77 列，遗漏列 `62`；full-pool minimum omitted reduced cost 为 `0.0`，满足 `>= -1e-7`，PASS。

## 17. Full regression result

最终验证：

```text
pytest -q: 379 passed, 0 failed, 0 skipped
python -m compileall -q backend tests: PASS
git diff --check: PASS
```

唯一提示为既有 FastAPI/Starlette `httpx` deprecation warning，不属于 Phase 9 失败。

## 18. Known limitations

- Flight Options 保持固定；Phase 9 不生成或优化 Schedule。
- 只实现 Aircraft String CG；没有 Crew Pairing/Passenger Itinerary CG。
- 同一次 CG solve 内固定输入必须保持不变。
- 未组合 Benders + CG。
- 未做 branching/integrality recovery，结果是 LP optimum。
- 未做 dual stabilization、生产级 dominance 或 airline-specific pricing rules。
- correctness-first DFS 可能访问较多 aircraft-local 合法路径，但不会在正式 CG 内物化全局 full pool。

## 19. Deferred work

未实现 Flight Option generation、Crew/Passenger pricing、Benders cut 与动态列 validity policy、branch-and-price、callbacks、并行定价、UI 或生产参数标定。以上均保持在 Phase 9 范围外。

## 20. Next step

下一阶段为 Phase 10 Crew Pairing Column Generation：复用本阶段已验证的 Full-column LP Oracle、Phase I、公共 dual/RC 审计、network pricing、scope original-only 和 full-pool termination audit 方法；在该阶段独立验收完成前，不进入 Benders + CG。
