# Phase 2 Final Review Report

## 1. Costs + Constraints Review Fix

Constraints Precheck 已接入 canonical Phase 1 benchmark Scenario、Recovery Columns 与 Phase 2 test/residual Passenger Capacity Profile。完整输入结果为 16 Passed / 4 Warning / 0 Failed；4 个 Warning 均是缺少外生 schedule request 时不能断言 exact coverage/eligibility，不是模型 infeasible。

无 Columns 时不再统一提前返回：Scenario-owned prerequisites 继续检查，结果为 3 Passed / 17 Warning / 0 Failed。Precheck 始终声明 `DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY`。

## 2. Four-model Status

| Model | Gurobi | Core constraints | Canonical objective | Independent audit | Result |
|---|---|---|---|---|---|
| SRM | executed | C01-C06 | delay/cancel/origin/destination | yes | PASS |
| ARM | executed | C01-C05 | reassignment/ferry | yes | PASS |
| CRM | executed | C01-C05 | reassignment/deadhead | yes | PASS |
| PRM | executed | C01-C04 | passenger delay/unserved | yes | PASS |

四模型专项 regression 共 11 项，全部通过。Gurobi availability 实测 `(True, None)`，没有 skip。

## 3. Overall Manual Reference Smoke Test

新增 `tests/regression/test_phase2_overall_manual_reference.py`。同一 Phase 1 Manual Reference schedule 分别独立求解：

- ARM：OPTIMAL，objective 0，audit PASS；
- CRM：OPTIMAL，objective 0，audit PASS；
- PRM：OPTIMAL，objective 18,000，audit PASS。

三个模型仍是独立求解；测试没有合计 objective，也不称为 Integrated Oracle。

已知 SRM 独立 optimum（objective 70）到 ARM 在有限 Aircraft Strings 下仍可能 INFEASIBLE。该事实被原样保留，没有修改 SRM cost、solution 或补列；它说明 Phase 3 必须联合处理 Schedule 与资源恢复。

## 4. Full Test / Gurobi Result

```text
python -m pytest -q -ra
266 passed
0 failed
0 skipped
1 third-party StarletteDeprecationWarning
```

额外检查：Python compileall、app.js/api.js Node syntax、`git diff --check` 均通过。

## 5. Cost Ownership

| Cost | Owner |
|---|---|
| flight delay | SRM |
| cancellation | SRM |
| origin change | SRM |
| destination change | SRM |
| aircraft reassignment | ARM |
| ferry | ARM |
| crew reassignment | CRM |
| deadhead | CRM |
| passenger delay | PRM |
| unserved passenger | PRM |

新增 exact-map regression，10 项 owner 全量相等；各模型 objective breakdown 只使用自身 canonical owner，不存在已知重复计费。

## 6. Phase 2 Acceptance Checklist

- [x] Costs + Constraints 小修补完成
- [x] 四个独立模型均可运行并有 independent audit
- [x] Overall Manual Reference smoke PASS
- [x] full pytest 0 failed
- [x] full pytest 0 skipped
- [x] 四模型 Gurobi integration 实际执行
- [x] Phase 2 Acceptance Checklist 已收口
- [x] Cost Ownership 无重复
- [x] assumptions / README / reproduction notes / plan 一致
- [x] Phase 3 v1 原则已冻结
- [x] Final Review Report 已新增
- [ ] Frontend 真实浏览器 console 检查：当前 computer-use 无 browser surface

## 7. Phase 3 v1 Frozen Principles

- `Phase 3 v1 = Full Integrated Fixed-Column Oracle`。
- 只验证四模型联合建模和跨模型耦合。
- 继续使用 `phase2_test_costs_v1`，按 SRM + ARM + CRM + PRM canonical owner 求和。
- 不增加模型级权重、隐藏 epsilon 或人为 tie-breaking penalty，允许等价最优解。
- 继续使用 Phase 2 `TEST / RESIDUAL CAPACITY`，明确不是 aircraft physical capacity。
- PassengerCommodity 不拆分，一组整体选择一条 itinerary 或 UNSERVED。
- 暂时保留 SRM Market-seat Proxy，持续标记 `PROVISIONAL / PROXY`。
- 不加入南航特定规则，不动态生成 Columns，不进入 Benders / Column Generation，不追求生产参数。

冻结内容登记于 `assumptions.md` A-056，并同步到 Reproduction Plan 与 reproduction notes。

## 8. Known Limitations

- Phase 2 四模型仍相互独立，不是 Integrated Oracle。
- SRM optimum 不保证在有限 ARM strings 下可行。
- Passenger capacity 是 test/residual profile，不是 aircraft physical inventory。
- Passenger group 不拆分，与论文整数 passenger-flow formulation 有明确差异。
- Gate Inventory 与 Market-seat 仍是 provisional proxy。
- 完整 precheck 的 4 个 Warning 需要外生 schedule request 才能做 exact schedule compatibility 判断。
- 当前 computer-use 未提供任何浏览器，无法核验真实 console 与视觉交互。

## 9. Final Decision

```text
Phase 2 NOT PASS
```

代码、数据、模型、Gurobi、自动测试、文档与 Phase 3 接口冻结均通过；但计划要求全部条件满足后才能标记 FINAL PASS。真实浏览器 console 验收无法在当前 `apps: [] / browsers: []` 环境中执行，因此不虚报 `Phase 2 FINAL PASS`，也不创建或推送 `phase2-complete` tag。
