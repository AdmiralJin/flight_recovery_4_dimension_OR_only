# Phase 8 Fixed-Column Benders 实施报告

生成时间：2026-09-15 14:35:55（Asia/Shanghai）

实施分支：`feature/phase-8`

阶段结论：PASS

## 1. Baseline / Phase 7 Status

Phase 8 从 `main` 提交 `a0e54c8` 建立。开始前重新执行 Phase 7 全量基线：

```text
353 passed
0 failed
0 skipped
1 existing StarletteDeprecationWarning
compileall PASS
git diff --check PASS
```

用户提供的 `docs/chatgpt_review/PHASE8_FIXED_COLUMN_BENDERS_PLAN.md` 是当时唯一未跟踪文件，已保留并纳入本阶段交付。

完整 Phase 7 benchmark universe 的实际数量为：

| Candidate | Count |
|---|---:|
| Schedule `x`（OPERATE/CANCEL） | 21 |
| FERRY（不属于 SRM `x`） | 1 |
| Aircraft Strings | 77 |
| Crew Pairings | 374 |
| Passenger Itineraries | 55 |

计划中的 21 是 Schedule `x` candidate 数量；原始 `flight_options` 总数为 22，其中包含 1 个 FERRY。实现按现有 SRM 语义处理，未把 FERRY 错纳入 Master `x`。

## 2. Modified Files

新增核心与配置：

```text
backend/config/benders.py
backend/core/benders.py
data/config/phase8_test_benders_v1.json
```

新增 dedicated toy：

```text
data/examples/toy_case_010_fixed_column_benders.json
data/columns/toy_case_010_fixed_column_benders_columns.json
data/capacities/toy_case_010_fixed_column_benders_capacity.json
```

新增测试：

```text
tests/unit/test_benders.py
tests/regression/test_phase8_benders_oracle.py
tests/regression/test_phase8_benders_scope.py
tests/regression/test_phase8_benders_benchmark.py
```

更新公共导出、fixture 与文档：

```text
backend/config/__init__.py
backend/core/__init__.py
tests/conftest.py
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/chatgpt_review/PHASE8_FIXED_COLUMN_BENDERS_PLAN.md
```

未修改稳定的 `srm.py`、`arm.py`、`crm.py`、`prm.py`、`integrated_oracle.py` 或 Columns Schema。

## 3. Benders Architecture

```text
Fresh SRM Master: x + theta_arm/theta_crm/theta_prm
        ↓ canonical selected schedule
Existing ARM MIP | Existing CRM MIP | Existing PRM MIP
        ↓ exact feasibility / owner recourse
Deterministic exact-schedule cuts
        ↓
LB / incumbent UB / gap
        ↓
Existing Integrated diagnostics audit
```

Master 每轮从 immutable cut list 重新构建，避免长期 mutable solver state。`solver_factory` 由调用方注入，核心模块没有硬编码 Gurobi。

## 4. Why Logic-Based Fixed-Column Baseline

ARM、CRM、PRM 当前均为 binary MIP；solver adapter 只允许对 optimal continuous model 读取 dual/reduced cost。因此本阶段实现的是 correctness-first Logic-Based Fixed-Column Benders，不声称 classical LP-dual Benders。

没有实现 Pricing、Reduced Cost、Column Generation、Benders + CG、callback、dual stabilization、cut strengthening 或动态列。

## 5. Config Contract

`FixedColumnBendersConfig` 提供：固定 `schema_version=1.0.0` 与 algorithm、严格正整数 `max_iterations`、严格非负 float gap tolerance、严格 bool owner 开关、frozen、extra forbid、duplicate JSON key rejection、versioned source 与 notes。

测试 profile 使用 `max_iterations=500`，实际 benchmark 只需要 8 轮，因此未修改该计划值。

## 6. Master Definition

Master 直接调用 `build_fixed_column_srm(...)` 复用 SRM-C01～C06，然后追加三个非负连续 theta、scope flight fixes 和累积 cuts。目标严格为：

```text
ScheduleOwnerCost(x) + theta_arm + theta_crm + theta_prm
```

ARM/CRM/PRM owner cost 没有进入 `x` coefficient。

## 7. ARM/CRM/PRM Subproblem Contracts

canonical schedule signature 经一次统一解析得到 revenue OPERATE option IDs，并构造现有 `AircraftRecoveryRequest`、`CrewRecoveryRequest`、`PassengerRecoveryRequest`。三个 subproblem 均调用现有 solve/audit contract，每次使用独立 solver instance。

只有 OPTIMAL 才可产生 exact recourse cut；INFEASIBLE 触发 schedule no-good；其他状态使 Benders 返回 ABORTED，不生成错误 bound/cut。

## 8. Scope Handling

Master 对 out-of-scope Flight 添加 `x[semantic_original]=1`。Subproblem 使用新的 `RecoveryColumns` view：scope 内 owner 保留全部 fixed candidates，scope 外 Aircraft/Crew/Passenger 只保留 semantic original candidate。输入 `RecoveryColumns` 不被修改。

`toy_case_006_scope` 的 out-of-scope `S6_U1/S6_AC2/S6_C2/S6_P2` 均通过 original fix audit；free binary candidates 为 10/14。

## 9. Feasibility Cut Definition

对 visited signature `S`、base Flight 数量 `N`：

```text
sum(x[o] for o in S) <= N - 1
```

unit test 穷举两航班四种组合，证明只拒绝 visited schedule，其他三个 schedule 均允许；相同 semantic cut key 不重复加入。

## 10. Optimality Cut Definition

对 owner `k` 的 exact recourse `Qk`：

```text
theta_k - Mk * sum(x[o] for o in S) >= Qk - Mk * N
```

unit test 验证 visited schedule 上 `theta >= Q`；任一 base Flight 改变后 RHS 不高于 0，不错误限制 `theta >= 0`。

## 11. Big-M Derivation

三类 Big-M 均按 scope-restricted universe 中每个 owner 的最大候选 owner cost 求和。benchmark 结果：

| Owner | Big-M |
|---|---:|
| ARM | 300 |
| CRM | 1,500 |
| PRM | 400,000 |

缺失 owner candidate 或负/非有限 owner cost 会 fail fast，不用 `M=0` 掩盖数据问题。

## 12. Bound / Gap Definition

只有 optimal Master objective 更新 `LB=max(previous,current)`。三个启用 subproblem 全部 optimal 时形成 candidate UB，并以 `UB=min(previous,candidate)` 更新 incumbent。

```text
absolute_gap = max(0, UB - LB)
relative_gap = absolute_gap / max(1, abs(UB))
```

达到 tolerance 后仍必须完成 Integrated audit 才返回 OPTIMAL。达到 max iterations 返回 NOT_CONVERGED；unit tests 已验证不会伪装 OPTIMAL。

## 13. toy_case_010 Result

| Schedule | SRM | Recourse behavior | Result |
|---|---:|---|---:|
| ORIG | 0 | ARM infeasible | no-good cut |
| D10 | 10 | passenger UNSERVED cost 2,500 | UB 2,510 |
| D20 | 20 | passenger delay cost 200 | optimum 220 |

```text
Integrated objective = 220
Benders objective    = 220
iterations           = 4
visited schedules    = 3
feasibility cuts     = 1
ARM/CRM/PRM opt cuts = 2 / 2 / 2
final gap            = 0
Integrated audit     = PASS
```

## 14. Existing Oracle Case Results

| Case | Integrated | Benders | Iterations | Unique cuts |
|---|---:|---:|---:|---:|
| toy_case_004 | 110 | 110 | 3 | 4 |
| toy_case_005 | 1,010 | 1,010 | 3 | 6 |
| toy_case_006_scope full | 2,040 | 2,040 | 3 | 4 |

## 15. Scope Regression

| Path | Integrated | Benders | Scope audit |
|---|---:|---:|---|
| Full | 2,040 | 2,040 | N/A |
| Canonical Scope | 2,040 | 2,040 | PASS |

该 fixture 的 out-of-scope owner 原本就各只有一条 original candidate，所以 scope view 的 raw candidate count 不下降；真实自由度缩减由 `free_binary_candidates 14 → 10` 证明。本报告采用实际数据，不虚构 physical deletion 数量。

## 16. Phase 1 Benchmark Result

| Metric | Value |
|---|---:|
| Integrated objective | 18,080 |
| Benders objective | 18,080 |
| Difference | 0 |
| Iterations | 8 |
| Visited schedules | 7 |
| Feasibility cuts | 2 |
| ARM optimality cuts | 5 |
| CRM optimality cuts | 5 |
| PRM optimality cuts | 5 |
| Total unique cuts | 17 |
| Initial LB | 70 |
| Final LB | 18,080 |
| Initial incumbent UB | 45,070 |
| Final UB | 18,080 |
| Final absolute gap | 0 |
| Final relative gap | 0 |

## 17. Iteration / Cut Statistics

```text
ARM solves = 8
CRM solves = 8
PRM solves = 8
```

未实现 subproblem cache。第 6、7 轮存在不可行 resource recourse，因此各加入一个 complete-schedule feasibility cut；其余 5 个首次访问的可行 schedules 各产生三类 optimality cut。

## 18. LB / UB Trajectory

| iter | Master/LB | ARM | CRM | PRM | candidate UB | incumbent UB | cuts added | total | gap |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 70 | 0 | 0 | 45,000 | 45,070 | 45,070 | 3 opt | 3 | 45,000 |
| 2 | 80 | 0 | 0 | 18,000 | 18,080 | 18,080 | 3 opt | 6 | 18,000 |
| 3 | 80 | 0 | 0 | 60,000 | 60,080 | 18,080 | 3 opt | 9 | 18,000 |
| 4 | 90 | 0 | 0 | 18,000 | 18,090 | 18,080 | 3 opt | 12 | 17,990 |
| 5 | 110 | 0 | 0 | 18,000 | 18,110 | 18,080 | 3 opt | 15 | 17,970 |
| 6 | 5,070 | infeasible | infeasible | 90,000 | — | 18,080 | 1 feas | 16 | 13,010 |
| 7 | 5,080 | infeasible | infeasible | 90,000 | — | 18,080 | 1 feas | 17 | 13,000 |
| 8 | 18,080 | 0 | 0 | 18,000 | 18,080 | 18,080 | 0 | 17 | 0 |

LB 单调不下降，incumbent UB 单调不增加。

## 19. Final Integrated Audit

最终 Benders `x/y/z/w` 送入现有 Integrated diagnostics 后，SRM/ARM/CRM/PRM local、Schedule-Aircraft、Schedule-Crew、Deadhead-Schedule、Passenger-Schedule、Seat-Schedule、Scope Fix（scope case）与 Objective recomputation 全部 PASS。

| Owner | Cost |
|---|---:|
| Schedule | 80 |
| Aircraft | 0 |
| Crew | 0 |
| Passenger | 18,000 |
| Total | 18,080 |

## 20. Full Test Result

Phase 8 增加 15 个测试；最终全量结果：

| Check | Result |
|---|---|
| pytest | 368 passed, 0 failed, 0 skipped |
| compileall backend | PASS |
| Black（9 个本阶段 Python 文件） | PASS |
| git diff --check | PASS |

仍有 1 个既有 `StarletteDeprecationWarning`。全仓 Black 会命中 62 个历史未格式化文件，因此按既有做法只检查本阶段 Python 文件，未扩大为无关格式化。环境未安装 Ruff，且它不属于当前仓库既有验收命令。

## 21. Known Limitations

- cuts 弱且只对 exact visited schedule 提供 recourse 信息；
- binary MIP recourse，没有 classical dual cut；
- 不做 subproblem cache、callback 或并行；
- component enable flags 可用于局部诊断，但只有三类 owner 全启用时才执行最终 Integrated equivalence audit；
- cut 仅对单次 solve 的 fixed universe/scope/profiles 有效；
- 性能基线只面向当前 finite schedule correctness cases。

## 22. Deferred Work

```text
LP-dual / strengthened Benders cuts
Flight / Aircraft String Pricing
Crew / Passenger Pricing
Column Generation
Benders + Column Generation
Dynamic-column cut validity policy
Cut cache / persistence / strengthening
Production-scale performance engineering
```

## 23. Next Recommended Step

进入 Phase 9 Flight / Aircraft String Column Generation 前冻结两个 Ground Truth：

```text
Integrated Oracle = 18,080
Fixed-Column Benders = 18,080
```

下一阶段先独立验证 Pricing/Column Generation 与 full explicit enumeration 的等价性；在此之前不组合 Benders + CG，也不复用 Phase 8 cuts 到动态候选宇宙。
