# Phase 13 Final Closeout, Merge & Tag

## 1. 收尾目标

Phase 13 已完成 Solver Integration、Recovered Result、Recovery UI 与端到端验证。

本次只做阶段性收尾：

```text
统一说明文档
→ 最终回归
→ 合并 main
→ main 再回归
→ 打 v1 阶段标签
```

**不再新增算法功能，不启动 Phase 14。**

Phase 13 合并后，将：

```text
Phase 0–13
```

冻结为：

```text
AIR Recovery Research Workbench v1
```

后续真实航司接入另开 Business Migration 路线。

---

# 2. 文档统一收尾

基于 `feature/phase-13`，逐项检查并统一以下文件：

```text
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
assumptions.md
reproduction_notes.md
docs/codex_reports/20260917_073424_phase13_solver_integration_recovered_result_report.md
```

要求所有当前状态表述一致。

## 2.1 README.md

重点清理 Phase 13 前遗留表述。

当前状态应明确为：

```text
一级视图：
Data
Visualization
Recovery
Costs
Constraints
```

不得继续写：

```text
仅 4 个一级视图
Recovered Plan 尚未接入
/api/solve 仍 disabled / 501
Solver API 尚未开放
```

API 说明更新为：

```text
GET  /api/health
POST /api/validate
POST /api/solve/precheck
POST /api/solve
GET  /api/solve/example-bundle/{case_id}
```

明确：

```text
Phase 13 = COMPLETE
Solver API = enabled
Recovery UI = available
production_ready = false
scope = full only
Flight Option generation = not implemented
```

历史 Phase 1/2 中仍写“当前尚未……”的旧表述，如现在已经完成，改为历史时态，不删除有价值的阶段记录。

---

## 2.2 docs/AIR_HTML_Python_Reproduction_Plan.md

确认最终状态统一为：

```text
Phase 2.0–13 = COMPLETE
AIR Core Reproduction / Research Workbench v1 = COMPLETE
```

不再增加新的核心算法 Phase。

后续范围统一改为：

```text
Business Migration
- Real airline data mapping
- Flight Option generation / screening
- Cost calibration
- Airline-specific operational rules
- Large-scale runtime / stability
- Operational validation
```

如果文末仍残留：

```text
当前下一任务 = Phase 13
```

改为：

```text
Core roadmap complete.
Next work belongs to Business Migration.
```

---

## 2.3 assumptions.md

只做状态整理，不重写已有假设。

确认 Phase 13 边界清晰：

```text
SolveRequest requires explicit solve-ready inputs
formal solve does not accept pre-generated Aircraft Strings / Crew Pairings
scope=None / full-scope only
Flight Options are externally supplied
Passenger Itineraries are explicit in formal SolveRequest
RecoveredResult is an application/result contract
production_ready = false
```

删除或改写仍把：

```text
Solver API disabled
RecoveredResult future work
```

当作当前状态的过时文字。

---

## 2.4 reproduction_notes.md

增加或确认简短最终收尾：

```text
Phase 13 completes the AIR reproduction / research workbench v1.

The solver chain now includes:
Integrated Oracle
→ Benders
→ Aircraft/Crew Column Generation
→ Benders + CG
→ Branch-and-Price
→ stable Solve API
→ Recovered Result
→ Recovery UI.

This milestone is a research-grade, auditable workbench,
not a production airline recovery system.
```

并明确：

```text
Core algorithm roadmap is frozen.
Further development moves to airline-specific Business Migration.
```

---

## 2.5 Phase 13 Codex Report

保留现有报告，不重写历史事实。

只确认报告与当前代码一致：

```text
428 Python tests passed
17 frontend Node tests passed
phase1_benchmark_001 API objective = 18080
toy_case_016 API objective = 95200
Integrated audit PASS
Headless Chromium E2E PASS
```

报告末尾“Phase 13 尚未合并 main”属于报告生成时状态，合并后无需回改历史报告。

---

# 3. 最终一致性检查

文档修改完成后：

```bash
git diff --check
git status
```

人工确认：

```text
README 当前状态
==
Development Plan 当前状态
==
assumptions 当前边界
==
reproduction_notes 当前边界
==
Phase 13 实际代码
```

不得再出现：

```text
Solver disabled
Recovery future work
Phase 13 pending
Phase 13 next
Phase 14 core algorithm next
```

---

# 4. Phase 13 Final Regression

在 `feature/phase-13` 执行：

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

如当前工程继续使用 Black：

```bash
python -m black --check <Phase13 Python files>
```

执行当前前端 Node tests，并按现有 Phase 13 流程运行一次 Headless Chromium E2E。

最终至少保持：

```text
Python:
428 passed
0 failed

Frontend Node:
17 passed

phase1_benchmark_001:
objective = 18080

toy_case_016:
objective = 95200

Integrated audit = PASS
E2E Solve = PASS
```

如果测试数因收尾测试变化而增加，以实际最新值为准；硬条件是：

```text
0 failed
0 errors
```

---

# 5. Commit Final Closeout

建议：

```bash
git add README.md         docs/AIR_HTML_Python_Reproduction_Plan.md         assumptions.md         reproduction_notes.md
```

检查：

```bash
git diff --cached
```

提交：

```bash
git commit -m "docs: finalize phase 13 workbench closeout"
```

最终收尾不得加入新的算法功能。

---

# 6. Merge Into main

确认分支干净：

```bash
git status
```

然后：

```bash
git switch main
git pull origin main
git merge --no-ff feature/phase-13
```

建议 merge commit message：

```text
merge: complete phase 13 AIR recovery workbench v1
```

---

# 7. Post-Merge Regression

在 `main` 再执行：

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

再运行当前前端 tests。

重新确认：

```text
/api/health
/api/solve/precheck
/api/solve

phase1_benchmark_001 = 18080
toy_case_016 = 95200

Recovery UI loads
Solve succeeds
Recovered Result export works
```

最后：

```bash
git status
```

必须为 clean。

---

# 8. Push main

```bash
git push origin main
```

确认 GitHub `main` 已包含：

```text
Phase 13 code
Phase 13 tests
Phase 13 docs
Phase 13 Codex report
```

---

# 9. Create Final Stage Tag

建议 annotated tag：

```text
air-workbench-v1
```

创建：

```bash
git tag -a air-workbench-v1   -m "AIR recovery research workbench v1: phases 0-13 complete"
```

确认：

```bash
git show air-workbench-v1
```

推送：

```bash
git push origin air-workbench-v1
```

优先使用 annotated tag，不使用轻量 tag。

---

# 10. Optional Branch Cleanup

确认：

```text
main 已推送
tag 已推送
回归正常
```

后，可删除 Phase 13 分支：

```bash
git branch -d feature/phase-13
git push origin --delete feature/phase-13
```

如希望短期保留审计分支，可暂不删除远端分支。

---

# 11. Final Repository State

完成后仓库应明确呈现：

```text
main
└── AIR Recovery Research Workbench v1

tag:
air-workbench-v1

Core roadmap:
Phase 0–13 COMPLETE

Next roadmap:
Business Migration
```

下一步另立：

```text
Business Migration M1 — Real Airline Data Mapping
```

保持：

```text
Core Research / Reproduction
vs
Airline-specific Extension
```

边界清晰。
