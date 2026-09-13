# Phase 2 Final Review / Freeze Plan

> 用途：供 Codex 对 Phase 2 做最后一次小修补、总验收和 Phase 3 接口冻结。  
> 原则：**不新增 Phase 2 模型功能，不重构已通过的 SRM / ARM / CRM / PRM。**  
> 完成后应正式标记 `Phase 2 FINAL PASS`，并进入 Phase 3。

---

# 1. 先完成 Costs + Constraints Workbench Review Fix

当前工作台主体已完成，只需做一次小修补。

## 1.1 Precheck 接入完整输入

当前 Constraints Precheck 主要只传 Scenario，需补充：

```text
Scenario
Recovery Columns
Passenger Capacity Profile
```

使前端能够真正检查依赖 fixed columns / capacity 的 ARM、CRM、PRM 约束。

优先复用现有：

```text
phase1_benchmark_001
phase1_benchmark_001_columns
phase2_test_seat_capacity_v1
```

## 1.2 改进缺少 Columns 时的行为

如果没有 Recovery Columns：

```text
不要让全部约束直接统一 WARNING 后提前结束
```

应：

- 能基于 Scenario 检查的继续检查；
- 只有依赖 Columns / Capacity 的约束标记 Warning；
- 继续明确 `PRECHECK != MIP FEASIBILITY`。

## 1.3 顺手清理文档

修正 README 中仍然残留的：

```text
Data Editor / Visualization 两种一级视图
```

使其与当前：

```text
Data
Visualization
Costs
Constraints
```

一致。

## 1.4 验收

至少确认：

```text
Costs 正常
Constraints 20 条 metadata 正常
完整 benchmark precheck 可运行
无 Columns 场景能合理降级
Frontend 无 console error
自动测试 PASS
```

新增简短报告：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_costs_constraints_review_fix_report.md
```

---

# 2. Phase 2 总验收

Phase 2 当前包含四个独立 Fixed-Column 子模型：

```text
SRM
ARM
CRM
PRM
```

本次只核对，不重新实现。

确认四个模型均满足：

```text
能够独立调用 Gurobi
核心约束有效
Objective 使用各自 canonical cost
结果有 independent audit
正常 / negative / regression tests 已覆盖
```

运行：

```bash
python -m pytest -q
```

要求：

```text
0 failed
0 skipped
```

并确认 SRM / ARM / CRM / PRM 的 Gurobi integration 均实际执行。

---

# 3. 增加一个 Phase 2 Overall Smoke Test

新增一个简单总体验收测试，例如：

```text
tests/regression/test_phase2_overall_manual_reference.py
```

使用同一套 Phase 1 Manual Reference schedule，分别检查：

```text
ARM feasible
CRM feasible
PRM feasible
```

目的：

> 证明同一人工参考恢复方案可以分别通过 Aircraft、Crew、Passenger 三个独立模型。

注意：

```text
这不是 Integrated Oracle
三个模型仍然独立求解
```

不要把三个 objective 相加后称为 integrated objective。

---

# 4. 保留并说明 SRM → ARM Infeasible

当前已知：

```text
SRM 独立最优
→ ARM 可能 INFEASIBLE
```

这是允许的。

最终报告必须明确：

> 独立 SRM optimum 不保证在有限 Aircraft Strings 下仍然满足 ARM，这正是 Phase 3 需要联合优化 Schedule 与资源恢复的原因。

禁止为了让 sequential pipeline 全部可行而修改 SRM cost、SRM solution 或偷偷补列。

---

# 5. Phase 2 文档与 Assumptions 收口

统一检查：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

完成以下事项：

- Phase 2 Acceptance Checklist 有证据的项目改为 `[x]`；
- SRM / ARM / CRM / PRM 均标记完成；
- 下一步明确为 Phase 3 Integrated Fixed-Column Oracle；
- 删除与当前代码冲突的旧描述；
- 保留重要 implementation assumption 与 limitation。

---

# 6. 冻结 Phase 3 v1 的关键原则

将以下内容正式写入 `assumptions.md`、Reproduction Plan 和 Final Review Report。

## 6.1 Phase 3 定位

```text
Phase 3 v1 = Full Integrated Fixed-Column Oracle
```

目标是验证四模型联合建模与跨模型耦合正确性。

不在 Phase 3 v1：

```text
加入南航特定业务规则
动态生成 Columns
进入 Benders / Column Generation
追求生产级真实参数
```

## 6.2 Seat Capacity

Phase 3 v1 暂时继续使用：

```text
Phase 2 test / residual Passenger Capacity Profile
```

不立即根据 Aircraft assignment 推导真实 aircraft physical capacity。

必须继续明确：

```text
TEST / RESIDUAL CAPACITY
NOT AIRCRAFT PHYSICAL CAPACITY
```

## 6.3 Integrated Objective

直接使用当前：

```text
phase2_test_costs_v1
```

并按 owner 求和：

```text
SRM + ARM + CRM + PRM
```

不增加：

```text
模型级权重
隐藏 epsilon
人为 tie-breaking penalty
```

允许等价最优解。

## 6.4 Passenger Group

继续保持：

```text
PassengerCommodity 不拆分
一个 group 整体选择一条 itinerary / unserved
```

并保留与论文 passenger-flow formulation 的差异说明。

## 6.5 Market-seat Proxy

Phase 3 v1 暂时保留现有：

```text
SRM Market-seat Proxy
```

继续标记：

```text
PROVISIONAL / PROXY
```

不把它描述成最终真实 market-seat constraint。

---

# 7. Cost Ownership 最终核对

确认不存在重复计费：

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

如果代码与该表不一致：

```text
Phase 2 FINAL PASS 不成立
```

---

# 8. Final Report

新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase2_final_review_report.md
```

保持简洁，至少包含：

```text
1. Costs + Constraints Review Fix
2. Four-model Status
3. Overall Manual Reference Smoke Test
4. Full Test / Gurobi Result
5. Cost Ownership
6. Phase 2 Acceptance Checklist
7. Phase 3 v1 Frozen Principles
8. Known Limitations
9. Final Decision
```

最终明确：

```text
Phase 2 FINAL PASS
```

或：

```text
Phase 2 NOT PASS
```

---

# 9. Phase 2 Final Acceptance

只有以下全部满足才 FINAL PASS：

- [ ] Costs + Constraints 小修补完成
- [ ] 四个独立模型均可运行并有独立 audit
- [ ] Overall Manual Reference smoke test PASS
- [ ] full pytest 0 failed
- [ ] full pytest 0 skipped
- [ ] 四模型 Gurobi integration 实际执行
- [ ] Phase 2 Acceptance Checklist 已收口
- [ ] Cost Ownership 无重复
- [ ] assumptions / README / reproduction notes / plan 一致
- [ ] Phase 3 v1 原则已冻结
- [ ] Final Review Report 已新增

完成后建议：

```bash
git tag phase2-complete
git push origin phase2-complete
```

然后进入：

```text
Phase 3 Full Integrated Fixed-Column Oracle
```
