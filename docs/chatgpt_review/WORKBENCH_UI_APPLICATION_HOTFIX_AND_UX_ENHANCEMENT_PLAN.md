# Workbench UI / Application Integration Hotfix & UX Enhancement Plan

## 0. 文档定位

本文用于对 `main` 当前 AIR Recovery Research Workbench v1 进行一次**纯应用层 / 前端集成层修复与优化**。

目标：

```text
修复前端状态管理与 Solve 生命周期问题
→ 修复 Solve Bundle / Constraints / Costs 同步问题
→ 增加合理的示例选择与状态反馈
→ 改善人工测试与交互体验
→ 增强错误处理、结果一致性和导入导出
→ 补齐自动化测试
→ 形成稳定的 Workbench v1.1
```

建议分支：

```text
fix/workbench-ui-integration
```

建议版本：

```text
AIR Recovery Research Workbench v1.1
```

本次允许调整 HTML、CSS、前端 JS、FastAPI 应用/API glue layer、示例加载接口、前端状态结构、UI 功能增删改和自动化测试。

原则上不得修改：

```text
backend/core/
SRM / ARM / CRM / PRM 数学约束
Benders cuts
Column Generation
Branch-and-Price
pricing
branching
Integrated Oracle
Phase 11/12 exactness logic
```

如果为了 API 适配必须修改 solver result 外层包装，只允许增加兼容字段或应用层转换，不改变核心求解行为。

---

# 1. 当前问题总览

当前 `main` 已完成 Phase 0–13、Solver API、RecoveredResult 和 Recovery UI，但人工使用暴露出一组 Web/Application Integration 问题。

典型现象：

```text
默认 phase1_benchmark_001
→ 可以点击 Solve
→ 可以得到结果

切换或导入其他 Scenario / Bundle
→ Solve 可能不可点击
→ 页面未明确解释原因
→ Constraints / Costs / Scenario 可能不同步
→ Reset 后问题定义可能变化
```

问题不是单一 HTML bug，而是 Example loading、Workbench state、Solve readiness、Async solve lifecycle、Constraints state、Cost baseline、Recovery result validity 与 UI feedback 缺少统一状态管理。

---

# 2. 核心设计原则

## 2.1 单一事实源

页面中所有与当前案例相关的数据必须来自同一个 `WorkbenchCase`，禁止 Scenario、SolveBundle、Constraints、Capacity、Costs 各自维护并漂移。

建议：

```javascript
workbenchState.case = {
  caseId,
  source,
  scenario,
  solveBundle,
  recoveryColumns,
  passengerCapacityProfile,
  costProfileId,
  costOverrides,
  costOverridesBaseline,
  algorithmProfiles,
  solveReady,
  solveReadiness,
  revision
}
```

所有视图必须读取当前 case。

## 2.2 Solve Result 必须绑定输入 revision

任何 Scenario、Flight Options、Passenger Itineraries、Capacity、Costs、Algorithm Profiles 发生变化，都必须使旧结果失效。

```javascript
state.revision += 1
state.recoveredResult = null
state.recoveredResultRevision = null
```

Solve 发起时记录：

```javascript
const solveRevision = state.revision
```

返回时：

```javascript
if (solveRevision !== state.revision) {
    discard stale result
}
```

禁止旧结果写到新案例页面。

## 2.3 显式区分三种状态

```text
Scenario Valid
Solve Ready
Optimization Status
```

例如：

```text
Scenario Valid: YES
Solve Ready: NO

Missing:
- Flight Options
- Passenger Itineraries
- Passenger Capacity Profile
```

不要把“按钮灰色”当成唯一提示。

## 2.4 Core Solver Freeze

所有 UI / API 优化继续调用当前正式 `benders_branch_and_price_v1`，不要改约束、成本定义、Branch-and-Price、pricing、oracle。

---

# 3. P0：修复 Solve 生命周期与过期结果

## 3.1 当前风险

现状可能出现：

```text
用户点击 Solve
→ async precheck
→ 用户快速再次点击 Solve
→ 第二个请求也启动
```

以及：

```text
Solve Case A
→ 求解过程中用户 Load / Import / Edit Case B
→ Case A 返回
→ A 的结果写进 B 的 UI
```

这是数据一致性问题。

## 3.2 立即锁定 Solve

点击 Solve 后，在任何异步操作之前：

```javascript
if (workbenchState.solving) return
workbenchState.solving = true
renderSolveState()
```

不要在 `await refreshSolveReadiness()` 之后才设置。

推荐：

```javascript
async function runSolve() {
    if (workbenchState.solving) return

    workbenchState.solving = true
    const requestRevision = workbenchState.revision

    try {
        const readiness = await refreshSolveReadiness()

        if (!readiness.solve_ready) return

        const result = await solveRecovery(currentSolveBundle())

        if (requestRevision !== workbenchState.revision) {
            showGlobalNotice(
              "Solve result discarded because the workbench input changed."
            )
            return
        }

        workbenchState.recoveredResult = result
        workbenchState.recoveredResultRevision = requestRevision
    } finally {
        workbenchState.solving = false
        renderSolveState()
    }
}
```

## 3.3 Solve 运行期间的 UI 锁定

禁止：

```text
再次 Solve
Reset
Load Example
Import
修改 Scenario
修改 Costs
修改 Constraints 相关输入
```

允许：

```text
切换页面查看已有输入
查看 Solving 状态
查看 elapsed time
```

## 3.4 增加 elapsed timer

显示：

```text
Solving… 00:03
Solving… 00:17
Solving… 01:24
```

## 3.5 测试

新增：

```text
start solve A
change revision to B
resolve A
assert result is discarded
```

以及：

```text
double click Solve
assert only one POST /api/solve
```

---

# 4. P0：统一 Solve Bundle / Constraints / Capacity 状态

## 4.1 当前问题

导入完整 Solve Bundle 后，可能只更新 `solveBundle`，但 `recoveryColumns`、`passengerCapacityProfile`、Constraints summary 仍来自默认 benchmark，导致：

```text
Solve 用 Case B
Constraints 页面显示 Case A
```

## 4.2 新增统一 `applySolveBundle()`

建立唯一入口：

```javascript
function applySolveBundle(bundle) {
    workbenchState.case.solveBundle = deepClone(bundle)
    workbenchState.case.scenario = deepClone(bundle.scenario)
    workbenchState.case.recoveryColumns = deepClone(bundle.recovery_columns)
    workbenchState.case.passengerCapacityProfile =
        deepClone(bundle.passenger_capacity_profile)

    workbenchState.case.costProfileId = bundle.cost_profile_id
    workbenchState.case.costOverrides =
        deepClone(bundle.cost_overrides || {})
    workbenchState.case.costOverridesBaseline =
        deepClone(bundle.cost_overrides || {})

    workbenchState.case.algorithmProfiles =
        extractAlgorithmProfiles(bundle)

    invalidateRecoveredResult()
    bumpRevision()
    refreshAllViews()
}
```

所有以下入口必须调用它：

```text
initial load
Load Example
Import Solve Bundle
Reset Case
```

禁止散落赋值。

## 4.3 Constraints 不再依赖固定 benchmark

`/api/model/constraints` 与 `/api/model/constraints/benchmark-inputs` 可以保留兼容，但前端不应将其作为当前 case 的事实源。

Constraints 页面优先读取：

```text
current case recovery_columns
current case passenger_capacity_profile
```

当前 case 不包含时，显示：

```text
Not available for this Scenario-only case
```

不得悄悄回退到 benchmark001。

## 4.4 Capacity Summary

必须绑定当前 case 的 passenger capacity profile，切换 case 时实时刷新。

---

# 5. P0：修复 Reset Workbench 语义

## 5.1 当前问题

当前 Reset 如果直接：

```text
costOverrides = {}
```

会删除 toy_case_016 自带的必要 override，改变原问题定义。

## 5.2 改成两个动作

建议 UI：

```text
Reset Changes
Reload Example
```

### Reset Changes

恢复当前 Case 加载时 baseline。

### Reload Example

重新从服务器加载当前 example。

## 5.3 baseline snapshot

加载案例时保存：

```javascript
case.baseline = deepClone({
  scenario,
  solveBundle,
  costOverrides,
  recoveryColumns,
  passengerCapacityProfile,
  algorithmProfiles
})
```

Reset 统一恢复 baseline，不手工拼字段。

---

# 6. P1：增加真正的 Example / Case Selector

## 6.1 当前问题

`Load Example` 当前本质上固定加载 `phase1_benchmark_001`，用户看不到其他可用案例。

## 6.2 页面增加 Example Selector

顶部建议：

```text
Example
[ phase1_benchmark_001                 ▼ ] [ Load ]

Status:
Solve-ready benchmark
```

至少提供：

```text
phase1_benchmark_001
toy_case_016_benders_branch_and_price
```

其他 toy case 如只是 Scenario，应分类：

```text
Solve-ready examples
--------------------
phase1_benchmark_001
toy_case_016_benders_branch_and_price

Scenario-only examples
----------------------
toy_case_001
toy_case_002
...
```

Scenario-only 标记：

```text
Scenario only — not solve-ready
```

## 6.3 新增 example metadata API

建议：

```http
GET /api/solve/examples
```

返回：

```json
[
  {
    "case_id": "phase1_benchmark_001",
    "label": "Phase 1 Benchmark",
    "type": "solve_bundle",
    "solve_ready": true,
    "description": "Main 4D recovery benchmark"
  },
  {
    "case_id": "toy_case_016_benders_branch_and_price",
    "label": "Toy 016 – Integrality",
    "type": "solve_bundle",
    "solve_ready": true,
    "description": "Phase 12 Branch-and-Price integrality case"
  }
]
```

不要把列表硬编码在前端。

## 6.4 Loader

Solve-ready case：

```http
GET /api/solve/example-bundle/{case_id}
```

Scenario-only：

```http
GET /api/examples/{case_id}
```

UI 必须明确类型差异。

---

# 7. P1：Solve Readiness 成为一等 UI 状态

增加顶部状态卡：

```text
Scenario        VALID
Solve Input     NOT READY
Solver          IDLE
Result          NONE
```

如果 Solve 不可点击，页面持续显示：

```text
Solve unavailable

Missing:
• Flight Options
• Passenger Itineraries
• Passenger Capacity Profile
```

如果是 profile 错误：

```text
Invalid:
• unknown cost override: xxx
```

disabled Solve tooltip 同样显示原因。

---

# 8. P1：移除 Visualization 的死 Recovered Plan 按钮

当前 Visualization 中永久 disabled 的 `Recovered Plan` 与正式设计冲突。

推荐直接删除，改为：

```text
Open Recovery →
```

无结果时进入 Recovery 显示：

```text
No recovered result. Run Solve first.
```

有结果后直接打开 Recovery。

---

# 9. P1：新增全局消息 / Toast / Error Surface

大量 Validate、Import error、API error、Solve error 不能只写入 Data 页隐藏 Validation panel。

新增：

```html
<div id="global-toast-region"></div>
```

支持：

```text
success
warning
error
info
```

例如：

```text
✓ Scenario validation passed
⚠ Solve bundle incomplete
✕ Import failed: missing schema_version
✓ Solve completed: objective 18,080
⚠ Stale solve result discarded
```

重大状态如 infeasible、not_converged、solver error 必须在 Recovery 页面持续显示，不只用 Toast。

---

# 10. P1：Validate 行为按当前视图语义化

```text
Data
→ Validate Scenario

Visualization
→ Validate current Scenario

Costs
→ Validate Cost Config

Constraints
→ Validate Constraints / Capacity

Recovery
→ Validate Solve Bundle / Recovered Result
```

Recovery 页面建议显示：

```text
Input readiness
RecoveredResult audit
Current result revision
Integrated audit
```

避免点击 Validate 后结果写到隐藏 Data panel。

---

# 11. P1：HTTP / API 错误处理增强

前端不要默认 `await response.json()`。

新增统一 helper：

```javascript
async function requestJson(url, options = {}) {
    const response = await fetch(url, options)
    const text = await response.text()

    let payload = null

    if (text) {
        try {
            payload = JSON.parse(text)
        } catch {
            payload = { detail: text }
        }
    }

    if (!response.ok) {
        throw new ApiError({
            status: response.status,
            detail: payload?.detail || response.statusText,
            payload
        })
    }

    return payload
}
```

所有 API 调用统一使用。

例如 Gurobi license 失败，应显示：

```text
Solver failed to start.

Possible cause:
Gurobi license is unavailable or invalid.

See server log for details.
```

不要显示 JSON parse error。

---

# 12. P1：Solve 超时与取消策略

本次不引入 Celery、Redis、WebSocket 或后台队列。

必做：

```text
elapsed time
long-running warning
```

例如：

```text
Solving… 00:31
This exact solve is taking longer than the benchmark baseline.
```

如加入 `AbortController`，按钮名称应为：

```text
Stop Waiting
```

除非后端确实支持安全终止 Gurobi，否则不要写 `Cancel Solve`，避免语义错误。

---

# 13. P1：Recovery 页面优化

推荐结构：

```text
Recovery
├─ Solve Status
├─ Summary
├─ Compare Mode
│  ├─ Original
│  ├─ Disrupted
│  ├─ Recovered
│  └─ Difference
├─ Flight
├─ Aircraft
├─ Crew
├─ Passenger
├─ Recovery Actions
├─ Diagnostics
└─ Export
```

Summary 显示：

```text
Status
Objective
Schedule Cost
Aircraft Cost
Crew Cost
Passenger Cost
LB
UB
Gap
Runtime
```

Difference 应成为人工验收重点，Solve 后可默认打开 Difference，或在 Summary 显示：

```text
Changed Flights: N
```

Mode 切换时，表格标题、数据源、统计值必须语义一致。

---

# 14. P1：Cost Workbench 优化

显示三层：

```text
Base profile
Case overrides
Effective costs
```

例如：

```text
Passenger delay
Base       10
Override   —
Effective  10
```

toy016：

```text
Crew reassignment
Base       0
Override   100
Effective  100
```

任何 effective cost 改变：

```text
Recovered result becomes stale
```

页面提示：

```text
Inputs changed after the last solve.
Run Solve again.
```

Reset Costs 必须恢复当前 case baseline override。

---

# 15. P1：Import / Export 重构

明确三类输入：

```text
Scenario JSON
Solve Bundle JSON
Workbench Snapshot JSON
```

不要全部叫 `Import Scenario`。

推荐：

```text
Import ▼
├─ Scenario
├─ Solve Bundle
└─ Workbench Snapshot
```

或者自动识别并提示：

```text
Detected: Solve Bundle
Case ID: toy_case_016_benders_branch_and_price
Solve Ready: YES
```

Export：

```text
Export ▼
├─ Scenario
├─ Solve Bundle
├─ Recovered Result
└─ Workbench Snapshot
```

如果保留 `Export Workbench Config`，必须增加对应 Import；否则删除单向功能。

---

# 16. P1：Case dirty / stale 状态

新增：

```text
CLEAN
MODIFIED
SOLVED
STALE RESULT
```

示例：

```text
phase1_benchmark_001
Modified
Recovered result is stale
```

Solve 后：

```text
Solved
revision 12
```

修改成本后：

```text
Modified
Last solution invalidated
```

---

# 17. P2：顶部导航与整体 UI

推荐顶部：

```text
AIR Recovery Workbench

Case:
[ phase1_benchmark_001 ▼ ] [Load]

[Import] [Export]

Scenario: VALID
Solve: READY
Solver: IDLE

[Validate] [Solve]

Tabs:
Data | Visualization | Recovery | Costs | Constraints
```

Solve 始终可见，但 disabled 时必须给原因。

状态颜色可用绿色/橙色/红色/灰色，但必须同时有文字，不依赖颜色传达唯一含义。

---

# 18. P2：Data / Constraints / Diagnostics 页面优化

## Data

显示：

```text
Case ID
Source
Scenario ID
Solve Bundle schema version
Revision
Loaded at
```

Scenario-only 显示：

```text
This case contains Scenario data only.

It can be inspected and validated,
but cannot be solved until a complete Solve Bundle is provided.
```

## Constraints

只能使用当前 Case 数据。

分组：

```text
Recovery Columns
Passenger Capacity
Model Constraints
Input Validation
```

没有 Solve Bundle 时显示：

```text
No recovery columns loaded.
No passenger capacity profile loaded.

This Scenario is not solve-ready.
```

禁止 fallback benchmark。

## Diagnostics

结构化展示：

```text
Algorithm
Status
Runtime
LB
UB
Gap

Benders
- iterations
- feasibility cuts
- LP cuts
- exact integer cuts

Aircraft
- CG calls
- generated columns
- B&P nodes

Crew
- CG calls
- generated pairings
- B&P nodes

Passenger
- itinerary count

Audit
- formal full enumerators used
- integrated audit
```

原始 JSON 可折叠显示。

---

# 19. P2：健康检查与 URL 可复现性

页面启动后调用：

```text
GET /api/health
```

显示：

```text
API: ONLINE
Solver: ENABLED
Algorithm: Benders + Branch-and-Price
Scope: Full only
Flight Option Generator: No
Production Ready: No
```

如实现成本低，可支持：

```text
/?case=phase1_benchmark_001
/?case=toy_case_016_benders_branch_and_price
```

便于人工测试、截图和复现。

---

# 20. 后端 API 整理

保留：

```text
GET  /api/health
POST /api/validate
POST /api/solve/precheck
POST /api/solve
GET  /api/solve/example-bundle/{case_id}
```

新增推荐：

```text
GET /api/solve/examples
```

不要新增算法版本接口，不要出现 `/api/solve/phase14`。

---

# 21. 前端状态建议重构

建议整理为：

```javascript
const workbenchState = {
    activeView: "data",

    case: {
        caseId: null,
        source: null,
        baseline: null,

        scenario: null,
        solveBundle: null,
        recoveryColumns: null,
        passengerCapacityProfile: null,

        costProfileId: null,
        costOverrides: {},
        costOverridesBaseline: {},

        revision: 0,
        dirty: false
    },

    validation: {
        scenario: null,
        constraints: null,
        costs: null
    },

    solve: {
        ready: false,
        readiness: null,
        solving: false,
        requestId: null,
        requestRevision: null,
        startedAt: null,
        elapsedMs: 0
    },

    result: {
        recoveredResult: null,
        revision: null,
        stale: false
    },

    ui: {
        compareMode: "difference",
        toastQueue: []
    }
}
```

推荐 helper：

```text
applySolveBundle()
applyScenario()
captureBaseline()
resetToBaseline()
bumpRevision()
invalidateRecoveredResult()
refreshSolveReadiness()
refreshAllViews()
setSolvingState()
setRecoveredResult()
showGlobalNotice()
showGlobalError()
currentSolveBundle()
currentEffectiveCosts()
```

避免 event handler 自己修改多个散落字段。

---

# 22. 自动化测试要求

## JS 单元测试

新增至少：

```text
example selector loading

applySolveBundle synchronizes:
- scenario
- recovery columns
- capacity
- cost overrides

reset restores case baseline

cost change invalidates recovered result
scenario change invalidates recovered result

double Solve sends one request
stale Solve result is discarded

solve-disabled reason rendered
Scenario-only case shows not-solve-ready

toy016 preserves cost overrides

global error visible outside Data view

Recovered Plan dead button removed
```

## API tests

新增：

```text
GET /api/solve/examples

example metadata matches available bundles

phase1 example bundle precheck -> ready

toy016 example bundle precheck -> ready

unknown example -> 404

scenario-only invalid solve bundle -> 422
```

## E2E A — phase1 benchmark

```text
Load
Solve
status = optimal
objective = 18080
Difference = 4 changed flights
Export result works
```

## E2E B — toy016

```text
Select toy016
Load
Solve readiness = true
Solve
status = optimal
objective = 95200
```

同时确认：

```text
case cost overrides retained
Constraints belong to toy016
```

## E2E C — Scenario-only

```text
load scenario-only example
Scenario valid
Solve disabled
visible missing-input explanation
```

## E2E D — stale result

```text
start solve
change case before response
old result returns
result discarded
```

必要时 mock API。

---

# 23. 人工验收用例

## Case 1 — phase1

```text
phase1_benchmark_001
```

预期：

```text
Scenario: VALID
Solve: READY

Solve
→ OPTIMAL
→ 18080
```

Recovery：

```text
Difference = 4 changed flights
```

## Case 2 — toy016

```text
toy_case_016_benders_branch_and_price
```

预期：

```text
Scenario: VALID
Solve: READY

effective cost overrides:
crew_reassignment = 100
deadhead_per_minute = 1

Solve
→ OPTIMAL
→ 95200
```

## Reset

toy016：

```text
change cost
Reset Changes
```

必须恢复 toy016 baseline override，而不是 `{}`。

## Import

导入完整 Solve Bundle 后必须同步：

```text
Data
Constraints
Costs
Recovery
Solve readiness
```

## Scenario-only

导入只有 Scenario 的 JSON：

```text
Scenario valid
Solve unavailable
```

并明确缺少内容。

---

# 24. UI 文案统一

统一使用：

```text
Scenario
Solve Bundle
Solve Readiness
Recovered Result
Recovery
Difference
Cost Profile
Cost Overrides
Passenger Capacity Profile
Recovery Columns
```

不要混用：

```text
Recovered Plan
Optimized Plan
Expected Result
Solution Plan
```

除非历史文档语境。

---

# 25. README / reproduction_notes 更新

README 增加：

```text
Workbench v1.1 Manual Workflow
```

说明：

```text
1. Select Example
2. Validate
3. Check Solve Readiness
4. Solve
5. Inspect Difference
6. Inspect Flight/Aircraft/Crew/Passenger
7. Export Recovered Result
```

明确：

```text
Scenario-only examples are inspectable but not solve-ready.
```

`reproduction_notes.md` 记录：

```text
Workbench v1.1 fixes application-level consistency issues only.
No core optimization mathematics changed.
```

列出：

```text
state synchronization
solve revision protection
example selector
reset semantics
global error feedback
constraints/capacity synchronization
import/export cleanup
```

---

# 26. 明确禁止事项

本次禁止：

```text
重新设计 SRM/ARM/CRM/PRM
新增数学约束
为了 UI 测试修改 objective
改变 benchmark expected objective
修改 Phase 12 B&P branching
修改 CG pricing
把 full enumeration 放回正式 solver
引入 React/Vue
引入复杂前端 build chain
引入 Celery/Redis
把研究工作台宣称为 production ready
```

继续保持：

```text
HTML
CSS
JavaScript
FastAPI
```

---

# 27. 建议实施顺序

```text
Step 1
统一 workbenchState
加入 revision / baseline / solve lifecycle

Step 2
applySolveBundle()
同步 Constraints / Capacity / Costs

Step 3
double-click protection
stale-result protection
input locking
elapsed time

Step 4
baseline snapshot
Reset Changes

Step 5
/api/solve/examples
Example selector
phase1 + toy016

Step 6
visible Solve readiness
disabled reason
status badges

Step 7
global toast / error
view-specific Validate

Step 8
remove dead Recovered Plan
Recovery mode cleanup

Step 9
Import / Export cleanup

Step 10
JS / API / E2E tests

Step 11
README / reproduction_notes / Codex report
```

---

# 28. Definition of Done

必须保持：

```text
Core solver unchanged
```

并满足：

```text
phase1_benchmark_001
→ one-click load
→ solve-ready
→ optimal
→ 18080
```

```text
toy_case_016_benders_branch_and_price
→ selectable in UI
→ solve-ready
→ preserves cost overrides
→ optimal
→ 95200
```

```text
Scenario-only case
→ visible
→ valid if schema valid
→ Solve disabled
→ explicit reason shown
```

```text
Import Solve Bundle
→ Scenario / Columns / Capacity / Costs synchronized
```

```text
Reset
→ current case baseline restored
```

```text
Solve running
→ no duplicate request
→ elapsed time shown
→ input-changing actions blocked
```

```text
input changes during/after solve
→ stale result cannot become current result
```

```text
global API errors visible from every view
```

```text
Visualization no longer contains permanently disabled Recovered Plan button
```

以及：

```text
all previous Python tests PASS
all previous frontend tests PASS
all new tests PASS
phase1 E2E PASS
toy016 E2E PASS
```

---

# 29. Final Acceptance

最终 Workbench 应达到：

```text
Select Case
    ↓
Load Case
    ↓
Scenario Valid
    ↓
Solve Readiness
    ↓
Solve
    ↓
Recovered Result
    ↓
Difference
    ↓
Flight / Aircraft / Crew / Passenger
    ↓
Diagnostics
    ↓
Export
```

用户不能再遇到：

```text
按钮灰了但不知道为什么
Load 了 Case B 但 Constraints 还是 Case A
Reset 后问题定义偷偷变化
Solve A 返回后覆盖到 Case B
Recovered Plan 永久点不动
Validate 点了没有任何可见反馈
```

---

# 30. 最终定位

完成后建议标记为：

```text
AIR Recovery Research Workbench v1.1
```

含义：

```text
v1.0
= Core optimization + Solve API + Recovery UI complete

v1.1
= Workbench state / UX / manual-testing integration hardened
```

之后再进入：

```text
Business Migration M1
```

不要把本次 UI/Application hotfix 重新包装成新的算法 Phase。
