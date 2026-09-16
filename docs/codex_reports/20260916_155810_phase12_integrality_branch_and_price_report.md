# Phase 12 Integrality / Branch-and-Price 实施报告

- 日期：2026-09-16
- 分支：`feature/phase-12`
- 基线：`main@5508eab`
- 计划：`docs/chatgpt_review/PHASE11_CLOSEOUT_AND_PHASE12_BRANCH_AND_PRICE_PLAN.md`

## 1. Phase 11 closeout / baseline

Phase 11 已先在 `feature/phase-110` 完成 406 项全回归、编译、diff 与 Black 检查，并以 `--no-ff` 合并到 `main`：

```text
b8015ec merge: phase 11 benders column generation
5508eab docs: record phase 11 closeout merge
```

`feature/phase-12` 从已推送的 `main@5508eab` 创建。详细收尾记录见 `20260916_150815_phase11_closeout_and_merge_report.md`。

## 2. Modified files

核心新增：

```text
backend/config/branch_and_price.py
backend/core/branch_restrictions.py
backend/core/aircraft_string_branch_and_price.py
backend/core/crew_pairing_branch_and_price.py
backend/core/benders_branch_and_price.py
```

向后兼容扩展：

```text
backend/core/aircraft_string_pricing.py
backend/core/aircraft_string_column_generation.py
backend/core/crew_pairing_pricing.py
backend/core/crew_pairing_column_generation.py
backend/config/__init__.py
backend/core/__init__.py
```

新增配置、案例与测试：

```text
data/config/phase12_test_branch_and_price_v1.json
data/examples/toy_case_015_crew_integrality.json
data/columns/toy_case_015_crew_integrality_columns.json
data/examples/toy_case_016_benders_branch_and_price.json
data/columns/toy_case_016_benders_branch_and_price_columns.json
data/capacities/toy_case_016_benders_branch_and_price_capacity.json
tests/unit/test_branch_and_price.py
tests/unit/test_benders_branch_and_price.py
tests/regression/test_phase12_*.py
```

文档更新：`README.md`、`docs/AIR_HTML_Python_Reproduction_Plan.md`、`assumptions.md`。

## 3. Aircraft branching semantics

Aircraft 主分支变量为 `(aircraft_id, required_option_id)` assignment aggregate。优先生成 forbid / require 两个 child；若 assignment 已整数而 String 变量仍分数，则按稳定 semantic key `(aircraft_id, leg_option_ids)` 执行 exact String forbid / force fallback。

当前模型与测试 universe 没有得到自然 Aircraft 整数缺口。依据计划第 39 节，未人为篡改 ARM 结构制造 gap，也未创建名不副实的 `toy_case_014`；branch-aware pricing、限制传播、fallback 合同及 root-integral B&P 路径均已实现和测试。

## 4. Crew follow-on branching semantics

Crew 优先按 crew-local consecutive typed follow-on 分支，typed leg 同时包含 `OPERATE/DEADHEAD` 与 Flight Option ID。没有 fractional follow-on 时依次使用 typed-leg membership、exact Pairing semantic key fallback。

`toy_case_015` 实际触发多层 typed follow-on branching，证明该规则不是只有接口而没有执行覆盖。

## 5. Branch restriction fingerprint

Aircraft/Crew restriction均冻结为不可变 canonical mapping/set，并对 required、forbidden、forced exact key、forbidden exact key排序后 SHA-256。restriction fingerprint 进入 node CG input fingerprint；不同 node 不复用 bound、dual 或 pricing certificate。

测试覆盖顺序无关稳定性、required/forbidden 冲突、forced/forbidden 冲突及未知 owner/option 拒绝。

## 6. Branch-aware pricing changes

- Aircraft pricer 在建图前移除 forbidden options，在 emit 时检查 required options 与 exact String 限制。
- Crew pricer保留现有 typed DAG 完整枚举，在 emit 时检查 required/forbidden follow-on、typed leg 与 exact Pairing 限制。
- node CG 会过滤 root seed 与 parent warm columns，只保留 child-legal columns。
- 所有外部 seed 均重新执行 Phase 5/6 legality validator。
- 默认 `branch_restrictions=None`、`initial_columns=()`，Phase 9/10 原 API 行为保持不变。

## 7. Node CG Oracle validation

Aircraft 与 Crew 均用 Phase 5/6 full explicit pool按相同 branch restriction过滤，再与 node CG LP objective 对拍；结果一致。另有不可能 required Crew follow-on 负例，node CG 返回 `INFEASIBLE`。

每个 node 只有 branch-restricted CG 返回 `OPTIMAL` 后，其 LP objective 才可作为有效 node lower bound。

## 8. Aircraft Branch-and-Price result

`toy_case_011` 固定 schedule：

```text
root LP                 0
integer optimum         0
integrality gap         0
nodes solved            1
max depth               0
unique columns generated 4
runtime                 0.019 s
```

结果在 root integral node 完成精确认证；未发生无必要的分支。

## 9. Crew Branch-and-Price result

`toy_case_015` 固定 schedule：

```text
root LP                  195
integer optimum          200
absolute integrality gap 5
relative gap             2.5% of integer optimum
nodes solved             9
max depth                4
unique Pairings generated 14
Phase-I iterations       13
Phase-II iterations      9
parent columns reused    69
runtime                  0.098 s
```

重复运行得到完全相同的 branch decision序列与 objective。

## 10. Integrality-gap toy cases

`toy_case_015` 使用三段闭合 triangle schedule 与三组 Crew。三个“两段 OPERATE + 一段 DEADHEAD”组合可各取 0.5，形成 LP=195；整数解必须使用完整三段 Pairing，代价为 200。该缺口来自现有 CRM set-partitioning 结构，不是测试替身或硬编码 objective。

Aircraft 当前结构未产生自然 gap，按计划允许的保守路径记录为零 gap。

## 11. Phase11 INTEGRALITY_REQUIRED → Phase12 OPTIMAL case

同一 `toy_case_016`：

```text
Phase 11 status  INTEGRALITY_REQUIRED
Phase 11 LB      95195
Phase 11 UB      95200

Phase 12 status  OPTIMAL
Phase 12 LB      95200
Phase 12 UB      95200
```

Aircraft root LP/整数值均为 0；Crew root LP=195、B&P integer=200。Phase 12 没有把 generated-pool binary objective当作下界，而是等待 B&P exact proof。

## 12. Benders + B&P architecture

Phase 12 先运行并保留 Phase 11 Schedule Benders + CG。若 Phase 11 已通过 LP/整数相等闭合，直接复用其精确结论；若返回 `INTEGRALITY_REQUIRED`，则对当前 Schedule重新执行 root CG和 generated-pool binary检查，只对有 gap 的 owner触发 B&P，再回到 Schedule Master。

Passenger始终调用 fixed explicit PRM exact MIP。动态 Scope明确拒绝。

## 13. Exact integer recourse cut policy

只有以下两种证明可产生 exact owner cut：

1. pricing-certified full LP objective 与合法 generated-pool integer feasible objective相等；
2. Branch-and-Price完整关闭搜索树并返回 `OPTIMAL`。

exact cut 只在其 Schedule tight，在其他 Schedule 的 RHS 不大于 0。root/child `NOT_CONVERGED` 或 `ABORTED` 不生成 exact cut；pricing-certified LP cuts继续保留。

## 14. Full Explicit Integrated Oracle comparison

`toy_case_016` 测试侧显式生成 6 条 Aircraft Strings 与 96 条 Crew Pairings：

```text
Full Explicit Integrated Oracle  95200
Phase 12                         95200
difference                           0
```

最终 `x/y/z/w` 通过独立 Integrated diagnostics，全部约束满足，objective breakdown相等。

## 15. phase1 benchmark

使用 Phase 5/6/7 测试 oracle universe（77 Strings、374 Pairings、55 Itineraries）对拍：

```text
Phase 12 objective  18080
expected/oracle     18080
difference              0
LB = UB             18080
```

该 benchmark在 Phase 11 的 LP exactness路径已闭合，无需 B&P节点。

## 16. Tree / pricing statistics

`toy_case_016` 集成轨迹：

```text
Benders master iterations                27  (Phase 11: 26, exact closure: 1)
visited Schedules                         25
Schedules requiring Aircraft B&P           0
Schedules requiring Crew B&P               1
Aircraft B&P total nodes                    0
Crew B&P total nodes                        9
LP lower-bound cuts                         3
exact integer recourse cuts                 2
feasibility cuts                           24
initial LB                              95195
final LB                                95200
first UB                               95200
final UB                               95200
final gap                                  0
integrated runtime                      1.512 s
```

## 17. Enumerator-independence tests

正式 `solve_aircraft_string_branch_and_price`、`solve_crew_pairing_branch_and_price`、`solve_benders_with_branch_and_price` 不导入或调用 Phase 5/6 full enumerators。测试将以下函数 monkeypatch 为抛出异常后，Phase 12仍返回 95200：

```text
generate_aircraft_strings
brute_force_legal_aircraft_strings
generate_crew_pairings
brute_force_legal_crew_pairings
```

full enumeration只存在于测试 oracle侧。

## 18. Full regression

最终验证：

```text
python -m pytest -q                  418 passed, 0 failed, 0 skipped
python -m compileall -q backend tests PASS
python -m black --check ...          PASS
git diff --check                     PASS
pytest runtime                       22.5 s
```

唯一 warning 为既有 FastAPI/Starlette `httpx` deprecation warning。

## 19. Known limitations

- Phase 12 v1仅支持 Full Scope；
- Flight Options仍为固定输入；
- Passenger Itineraries仍为固定显式输入，不含 Passenger CG/B&P；
- Aircraft/Crew branch pricing沿用当前 Phase 5/6 legality profiles；
- Crew仍是当前 single-duty profile，不代表完整 FAR/CCAR duty/rest/roster；
- best-bound tree为 correctness-first重建式 CG，未实现 basis/dual warm start；
- Aircraft当前测试模型没有自然整数缺口，因此实际多层 tree证据来自 Crew；
- Phase 12尚未接入 HTTP Solve API或前端 recovered-result视图。

## 20. Next step

进入 Phase 13：稳定 Solve API、Recovered Result schema和 Original / Disrupted / Recovered / Difference可视化，并向界面暴露 runtime、cuts、columns、bounds与终止状态。Phase 12分支本次不合并入 `main`，等待下一轮 review/closeout。
