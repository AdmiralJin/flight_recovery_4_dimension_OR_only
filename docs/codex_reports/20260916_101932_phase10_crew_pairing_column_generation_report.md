# Phase 10 Crew Pairing Column Generation 实施报告

时间：2026-09-16 10:19:32（Asia/Shanghai）

分支：`feature/phase-10`

实现提交：`0ae5c7b feat: implement phase 10 crew pairing column generation`

依据：`docs/chatgpt_review/PHASE9_CLOSEOUT_AND_PHASE10_CREW_PAIRING_CG_PLAN.md`

## 1. Phase 9 closeout / baseline

Phase 9 已以 `--no-ff` merge commit `5dd75b5` 合入 `main`，closeout 报告提交后主线为 `9956aef`，并已推送远端。`feature/phase-10` 从该提交创建。Phase 10 未修改已冻结的 Aircraft LP、Aircraft pricing、Aircraft CG、Benders 或 Integrated Oracle 语义。

## 2. Modified files

主要新增：

- `backend/config/crew_pairing_column_generation.py`
- `backend/core/crew_pairing_master.py`
- `backend/core/crew_pairing_pricing.py`
- `backend/core/crew_pairing_column_generation.py`
- `data/config/phase10_test_crew_pairing_cg_v1.json`
- `toy_case_012_crew_pairing_column_generation` scenario/columns
- Phase 10 unit 与 regression tests

`pairing_generator.py` 只公开既有稳定 ID/constructor；Phase 6 Pairing IDs 与生成语义未改变。README、总计划、assumptions 与 reproduction notes 已同步。

## 3. Crew Full-Column LP

新增独立 All-Pairings continuous LP Oracle，变量为 `0 <= z[p] <= 1`。模型保留 CRM pairing selection、required OPERATE coverage、nonrequired OPERATE prohibition、nonrequired DEADHEAD prohibition、terminal ownership 行；Pairing feasibility 继续由 Phase 6 validator 保证。目标只调用 canonical `crew_pairing_cost()`。

## 4. Crew RMP

Restricted Master 与 All-Pairings LP 共用同一 row builder，只接收当前 Pairing pool。每轮 fresh rebuild，不扩展 solver adapter 做动态 mutation。Scope 内 Crew 可定价，Scope 外 Crew 仅保留语义 original Pairing。

## 5. Phase I

全 Scope 默认从 0 条真实列开始。Phase I 对 RHS=1 的 Crew selection、required OPERATE coverage 与 terminal rows 分别加入非负 artificial；真实 Pairing objective coefficient 为 0。RHS=0 的 nonrequired OPERATE/DEADHEAD rows 不加 artificial。toy 的 artificial objective 为 `8 -> 5 -> 2 -> 0`；另有全员不具备 OPERATE qualification 的真实不可行测试，正确返回 INFEASIBLE。

## 6. CRM row / dual mapping

`CrewPairingMasterDuals` 显式保存：

- `selection_by_crew`
- `required_operate_coverage_by_option`
- `nonrequired_operate_by_option`
- `nonrequired_deadhead_by_option`
- `terminal_by_crew`

核心只调用公共 `SolverAdapter.get_constraint_dual()` 和 `get_reduced_cost()`，未访问 Gurobi 私有对象。

## 7. Reduced-cost formula

统一公式：

```text
rc(p) = crew_pairing_cost(p) - sum(dual[row] * coefficient[row,p])
```

Phase I 将真实 Pairing primal cost 固定为 0；Phase II 使用 crew reassignment 加 deadhead-minute cost。OPERATE 才贡献 required coverage dual，DEADHEAD 不贡献。统一 evaluator 同时服务正式 pricing、full-pool oracle 和 termination audit。

## 8. Pricing resource state

正式 pricer 复用 `CrewFlightNetwork`，显式 label 状态包含：last typed leg、ordered typed path、used option IDs、used base-flight IDs、deadhead count、first departure、duty elapsed。搜索安全剪枝 duplicate option/base flight、deadhead limit 与 max duty；qualification、station、time、MCT、horizon 由 Phase 6 network/validator 复用。

## 9. OPERATE / DEADHEAD handling

正式 pricing universe 只含 fixed schedule 的 required revenue options，但每个 option 可形成 OPERATE 或 DEADHEAD typed leg。OPERATE 可能产生 reassignment cost并满足 coverage；DEADHEAD 产生 block-minute cost、只用于 reposition。idle Pairing 保留 selection 与 terminal coefficients，其 reduced cost 可非零。monkeypatch 测试证明正式 CG 不调用 Phase 6 full/brute-force enumerator。

## 10. toy_case_012

Toy 含 3 名同起终点 Crew 与 2 个 required parallel flights。每名 Crew 可 OPERATE 或 DEADHEAD 长/短航段；每个 Crew 必须选一条 Pairing，两个航班各恰好被 OPERATE 一次，因此第三名 Crew 必须 DEADHEAD。长航段 deadhead cost 为 `300`，短航段为 `150`。通过既有 cost override 将 crew reassignment 设为 test-only `100`，同时验证 reassignment owner cost，未建立第二套成本逻辑。

## 11. Pricing vs exhaustive Oracle

在省略短航段 DEADHEAD Pairings 的 Phase II RMP 上：

```text
formal typed-DAG minimum RC = -150.0
full-pool exhaustive min RC = -150.0
```

Pricer 返回 `DEADHEAD(S12_Z_SHORT)`，Pairing semantic key/ID 与 Phase 6 full pool 一致。

## 12. All-Pairings LP vs CG

Toy full Pairings 为 `12`，初始真实列 `0`，最终 CG 列 `12`。Phase I 4 轮、Phase II 2 轮，共 6 轮：

| Iteration | Phase | RMP obj | Artificial | Min RC | Added |
|---:|---|---:|---:|---:|---:|
| 1 | I | 8 | 8 | -3 | 3 |
| 2 | I | 5 | 5 | -3 | 3 |
| 3 | I | 2 | 2 | -2 | 3 |
| 4 | I | 0 | 0 | n/a | 0 |
| 5 | II | 300 | 0 | -150 | 3 |
| 6 | II | 150 | 0 | n/a | 0 |

```text
All-Pairings LP objective = 150.0
Crew CG LP objective      = 150.0
Difference                = 0.0
```

每名 Crew 最终各 4 条列；采样 runtime 约 `0.021s`。

## 13. Scope

Dedicated scope 仅允许 `S12_C3` 定价，`S12_C1/C2` 固定到各自 original OPERATE Pairing。Scope-restricted full pool 为 6，CG 初始列 2、最终列 6；Phase I 4 轮、Phase II 2 轮：

```text
All-Pairings Scope LP = 150.0
Crew CG Scope LP      = 150.0
Difference            = 0.0
```

## 14. Benchmark

Schedule source 为 `phase1_benchmark_001` 的 semantic original Flight Options，即 Phase 1 Manual Reference schedule。Phase 6 full universe 为 `374` Pairings；Crew CG 从 0 条真实列开始，最终保留 `34` 条：`C1:6`，`C2/C3/C4/C5:7`。

- Phase I：6 轮，artificial `22 -> 15 -> 6 -> 4.5 -> 2 -> 0`
- Phase II：3 轮，RMP objective `300 -> 0 -> 0`
- 总计：9 轮
- 采样 runtime：约 `0.137s`

```text
All-Pairings LP objective = 0.0
Crew CG LP objective      = 0.0
Difference                = 0.0
```

## 15. Termination audit

Full Pairing enumeration 只在独立 audit boundary 使用：

- toy：最终已含 12/12 Pairings，遗漏 0，PASS。
- dedicated scope：最终已含 restricted 6/6 Pairings，遗漏 0，PASS。
- benchmark：最终 34/374 Pairings，遗漏 340；minimum omitted RC 为 `0.0`，满足 `>= -1e-7`，PASS。

## 16. Existing-column RC audit

每个 optimal RMP 后均以实际 row coefficients 手算现有变量 RC，并与 solver public reduced-cost 接口比较。toy、scope、benchmark 的 maximum audit error 均为 `0.0`；超过 `1e-6` 时驱动器会返回 ABORTED。

## 17. Full regression

最终验证：

```text
pytest -q: 394 passed, 0 failed, 0 skipped
python -m compileall -q backend tests: PASS
git diff --check: PASS
python -m black --check <Phase10 files>: PASS
```

唯一提示为既有 FastAPI/Starlette `httpx` deprecation warning，不属于 Phase 10 失败。

## 18. Known limitations

- Flight Options 固定，一次 Crew CG solve 内 Schedule 固定。
- 继续使用 Phase 6 v1 single-duty legality，不是完整 FAR/CCAR duty/rest 系统。
- correctness-first resource-state traversal 未实现复杂 dominance 或 stabilization。
- 无 Benders + CG、Aircraft/Crew joint pricing、Passenger CG。
- 无 branching 或 integrality recovery，结果是 LP optimum。
- 无生产级航空公司 Crew legality/cost 标定。

## 19. Deferred work

未实现 multi-duty/overnight rest、reserve crew、真实 duty/rest regulation、并行 pricing、multi-column acceleration、dual stabilization、branch-and-price、dynamic-column Benders cut policy 或 UI。这些均保持在 Phase 10 范围外。

## 20. Next step

下一阶段为 Phase 11 Benders + Column Generation。进入实现前必须冻结 Cut Validity Policy、Cut Invalidation/Refresh Policy、recourse lower-bound refresh 和 candidate-universe fingerprint；不得直接把 Phase 9/10 CG 嵌入 Phase 8 fixed-column cuts。
