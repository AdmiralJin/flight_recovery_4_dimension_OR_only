# Costs + Constraints Visual Workbench Report

## 1. Modified Files

后端：

- `backend/api/config.py`
- `backend/api/model_constraints.py`
- `backend/api/validate.py`
- `backend/config/costs.py`
- `backend/config/__init__.py`
- `backend/core/constraint_registry.py`
- `backend/core/__init__.py`
- `backend/services/constraint_precheck.py`
- `backend/main.py`

前端：

- `frontend/index.html`
- `frontend/css/workbench.css`
- `frontend/js/api.js`
- `frontend/js/app.js`
- `frontend/js/costs.js`
- `frontend/js/constraints.js`
- `frontend/js/visualization.js`

测试：

- `tests/api/test_api.py`
- `tests/api/test_workbench_api.py`
- `tests/frontend/workbench.test.mjs`
- `tests/unit/test_cost_config.py`
- `tests/unit/test_constraint_registry.py`
- `tests/unit/test_constraint_precheck.py`
- `tests/unit/test_workbench_js.py`

文档：

- `README.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`
- `reproduction_notes.md`
- 本报告

## 2. Workbench Architecture

前端一级视图扩展为 Data、Visualization、Costs、Constraints。`workbenchState` 分离 Scenario、Scenario baseline、cost baseline、cost overrides、effective costs、constraint metadata、precheck 和 capacity summary，Cost/Constraint 没有写入 Scenario Schema。

Data 仍是 Scenario 字段的唯一可编辑真源。Constraint 的 Related Inputs 只导航回 Data 对应 section，不复制第二份参数状态。

## 3. Costs UI

Costs 按 SRM / ARM / CRM / PRM owner 分组，显示 Coefficient、Meaning、Baseline、Override、Effective、Unit 与 Source。每项可展开查看 owner、source、source reference 与 notes，并区分 PAPER、IMPLEMENTATION ASSUMPTION、USER OVERRIDE。

已提供 Validate Costs、Reset Cost Overrides、Export Scenario、Export Workbench Config 和 Reset Workbench。

## 4. Cost Override Contract

Canonical profile 只从 `data/costs/phase2_test_costs_v1.json` 加载。`CostOverrideConfig` 只接受 `base_cost_profile_id` 和 key/value overrides：

- key 必须是已知 coefficient；
- value 必须为 finite 且 `>= 0`；
- effective profile 由 pure `apply_cost_overrides` 创建；
- baseline 不 mutation；
- owner、unit、source、source reference 等 metadata 不可覆盖；
- 浏览器 override 不写回 canonical JSON。

## 5. Constraint Registry

新增统一 backend registry，登记实际代码中的 20 个约束 ID：SRM 6、ARM 5、CRM 5、PRM 4。Registry 包含 model、name、paper equation、kind、provenance、implementation status、formula summary、dependencies、related sections、assumption refs、provenance detail 和 notes。

没有为计划中的拆分描述另造与代码冲突的 ID；ARM/CRM 的合并约束语义在 notes 中明确说明。

## 6. Constraint Inspector

Inspector 按四个模型分组，公式为 backend metadata 的只读摘要。Paper、implementation assumption、fixed-column validation、proxy 和 deferred 具有独立 badge。Gate Inventory 与 Market-seat 显著标记 PROXY，并说明不是 tail-level gate occupancy / physical seat capacity。

PRM profile 只读展示为 `TEST / RESIDUAL CAPACITY`，并标记 `NOT AIRCRAFT PHYSICAL CAPACITY`。

## 7. Precheck Semantics

API 与 UI 固定声明：

```text
DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY
PRECHECK != MIP FEASIBILITY
```

Precheck 校验 Scenario、Recovery Columns schema/semantic、flight options、strategic operate candidates、capacity memberships、gate inventory construction、aircraft strings、crew pairings、passenger itineraries 与 residual capacity profile。缺少 Columns 或 capacity 时返回 Warning，不假设 infinite capacity；它不构建或调用 solver，不返回 Feasible/Optimal。

## 8. APIs Added

```text
GET  /api/config/costs
POST /api/config/costs/validate-overrides
GET  /api/model/constraints
POST /api/model/constraints/precheck
```

`/api/solve` 继续返回 501，未接入正式 Solve。

## 9. Tests Added

新增/扩展测试覆盖：

- canonical profile API；
- valid / unknown / negative / NaN / Infinity override；
- baseline immutable 与 effective-only value；
- registry ID 与模型常量完全一致、唯一性、枚举和 assumption 格式；
- benchmark precheck、flight option coverage 缺口、坏 capacity、缺失 capacity；
- Costs/Constraints view contract；
- cost override/reset pure functions；
- Scenario 与 Workbench export 分离；
- constraint 分组、badge 与 Related Inputs 导航 wiring。

## 10. Full Test Result

```text
python -m pytest -q
261 passed
0 failed
0 skipped
1 third-party StarletteDeprecationWarning
```

额外检查：

- `node --check`：`app.js`、`api.js`、`costs.js`、`constraints.js` 通过；
- `python -m compileall -q backend` 通过；
- `git diff --check` 通过；
- 本地 HTTP smoke：页面、3 个 JS、CSS、Costs API、Constraints API 均返回 200。

## 11. Manual Browser Test

FastAPI 已成功启动，`/api/health` 返回 200，静态资源与新增 API 均可通过 HTTP 访问。

但 computer-use 环境返回：

```text
apps: []
browsers: []
Browser is not available: iab
```

因此无法执行计划中的真实浏览器点击、视觉布局、下载与 console-error 检查。本报告不将该项虚报为 PASS；需要在提供 Chrome、Edge 或 in-app browser surface 后复验 18 项 manual checklist。

## 12. Known Limitations

- 没有 Integrated Oracle、Benders、Column Generation 或动态 Recovery Columns；
- Workbench 不调用正式 solver；
- UI 当前只有 Scenario editable state，没有 Recovery Columns 编辑器，因此页面 precheck 对 columns-dependent 检查会明确显示 incomplete warning；
- PRM capacity 是 benchmark 用 test/residual profile，默认 toy Scenario 与该 profile 不构成可求解组合；
- Workbench Config 仅支持导出，导入被显式拒绝；
- 真实浏览器 manual QA 因当前工具环境无 browser surface 尚未完成。

## 13. Acceptance Checklist

- [x] Costs 一级 View
- [x] Constraints 一级 View
- [x] 前端不再硬编码 Phase 0.5 展示文案
- [x] canonical Cost Config 是后端单一真源
- [x] cost override 不修改 canonical provenance
- [x] 成本按 SRM / ARM / CRM / PRM owner 分组
- [x] Constraint metadata 来自后端统一 registry
- [x] 20 个实际 Phase 2 constraint ID 均有 metadata
- [x] Paper / Assumption / Proxy / Validation / Deferred 可区分
- [x] Constraint formula 只读
- [x] 无核心约束开关
- [x] Related Inputs 回到 Scenario canonical state
- [x] PRM test capacity 明确为非 aircraft physical capacity
- [x] Precheck 不冒充 solver feasibility
- [x] Scenario Export 与 Workbench Export 分离
- [x] Data / Visualization 自动化无回归
- [x] 自动化测试 PASS
- [ ] Manual Browser Test：受无 browser surface 阻塞
- [x] 未接正式 Solve
- [x] 未修改 Phase 2 数学模型
- [x] 未进入 Phase 3 Integrated Oracle

## 14. Next Recommended Step

在启用可控 Chrome、Edge 或 in-app browser 后，按计划第 21 节完成 18 项浏览器验收；重点检查桌面/窄屏布局、override 输入反馈、Reset、Related Inputs、两类下载和 console。通过后将本报告 manual checklist 更新为 PASS。

## Final Result

```text
Costs + Constraints Workbench NOT PASS
```

原因仅为强制 Manual Browser Test 无可用 browser surface；实现、契约、自动化回归与 HTTP smoke 均已通过。
