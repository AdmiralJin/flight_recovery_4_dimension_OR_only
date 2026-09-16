# Phase 13 Solver Integration / Recovered Result 报告

- 日期：2026-09-17（Asia/Shanghai）
- 工作分支：`feature/phase-13`，基于已合并 Phase 12 的 `main`（`465f3d6`）
- 依据：`docs/chatgpt_review/PHASE12_CLOSEOUT_AND_PHASE13_SOLVER_INTEGRATION_PLAN.md`

## 1. Phase 12 收尾与顺序

先在 `feature/phase-12` 复核、提交收尾记录，`418` 个 Python 测试通过；再以 `git merge --no-ff feature/phase-12` 合并到 `main`，合并提交为 `465f3d6`，复测并推送 `main`。随后才从新 `main` 创建 `feature/phase-13`。Phase 12 的详细报告见 `20260916_163131_phase12_closeout_and_merge_report.md`。

## 2. 主要修改

新增 `backend/schemas/result.py` 的版本化 `SolveRequest` / `RecoveredResult` 契约；新增 `backend/application/solve_service.py`、`result_builder.py` 和 `backend/api/solve.py`；在 Phase 11/12 结果中仅增加 `solution_columns` 兼容字段，使应用层可追溯求解生成的选中列，没有修改数学模型、pricing、branching 或 cuts。移除原 `/api/solve` 的 501 占位响应，并在 `backend/main.py` 注册正式路由。

前端新增 `frontend/js/recovery.js`、`frontend/css/recovery.css`，更新 `frontend/index.html`、`frontend/js/app.js`、`frontend/js/api.js`：Solve 状态、Recovery Summary、Flight/Aircraft/Crew/Passenger 表、诊断折叠面板、Original/Disrupted/Recovered/Difference 对比、结果 JSON 导出，以及完整 Solve Bundle 导入。更新 `README.md`、`docs/AIR_HTML_Python_Reproduction_Plan.md`、`assumptions.md`、`reproduction_notes.md`。新增 API / builder / DOM contract 测试与限节点终态测试 profile。

## 3. 输入、就绪与服务

`SolveRequest(schema_version=1.0.0)` 包含 Scenario、现有 Flight Options、显式 Passenger Itineraries、Passenger Capacity Profile、canonical cost profile/overrides、`benders_branch_and_price_v1` 与各算法 profile ID。正式输入禁止预生成 Aircraft Strings / Crew Pairings。`POST /api/solve/precheck` 返回 `solve_ready`、缺失项、非法项与警告；它只检查输入就绪，不声明优化可行性。Scenario-only、缺 Flight Options / Passenger Itineraries / Capacity、未知成本覆盖项都明确以 422 拒绝。

`POST /api/solve` 同步调用 Phase 12 exact Benders + Branch-and-Price。合法但不可行或未收敛返回 HTTP 200 和 `infeasible` / `not_converged` 状态，不产生伪造决策；未预期异常才进入 500。`GET /api/solve/example-bundle/{case_id}` 提供显式演示 bundle；主 benchmark 的 55 条 Passenger Itineraries 在示例装配阶段按 Phase 7 profile 生成，正式 solve 路径不隐式生成它们。`toy_case_016` 示例保留其 Oracle 对拍所需的显式成本覆盖。

## 4. 结果映射与独立审计

`RecoveredResult` 包含 x/y/z/w 选中 ID、Flight 恢复状态/时间/资源、Aircraft rotation/ferry、Crew OPERATE/DEADHEAD、Passenger itinerary/unserved、恢复动作、成本分量、业务指标、算法诊断和运行元数据。Builder 独立检查每类 owner 恰选一列、选中 OPERATE option 的 Aircraft/Crew 唯一覆盖、Passenger 路径只引用选中航班，重新计算成本及指标，并要求 Integrated final audit PASS；非 optimal 状态强制空决策。诊断保留 LB/UB/gap、Benders iterations/cuts、CG columns、B&P nodes 和 runtime。

## 5. 前端边界

Original 显示原计划；Disrupted 显示既有扰动规则下的直接暴露/下游传播风险，**不是** solver action；Recovered 显示求解结果；Difference 只筛选变化航班。场景或成本编辑会使旧结果失效并重新检查 Solve 就绪。导出完整 `RecoveredResult` JSON。当前实现仍是研究工作台：仅支持 `scope=None`，不生成 Flight Options，没有真实航司生产规则、后台任务或规模性能承诺；健康检查明确 `production_ready=false`。

## 6. 验收证据

- Python 全量回归：`428` tests passed，0 failed，0 skipped；仅既有 Starlette/httpx 弃用警告。
- `phase1_benchmark_001` API objective = `18080`，Integrated audit PASS。
- `toy_case_016_benders_branch_and_price` API objective = `95200`，Integrated audit PASS。
- 覆盖 Scenario-only、非法成本、缺显式 Passenger Itineraries、合法但 infeasible、限节点 not_converged、重复请求结构确定性。
- 前端 Node tests：`17` passed；JS syntax、Black、Python compileall、`git diff --check` 通过。
- Headless Chromium 端到端：点击 Solve 后状态 optimal、总成本 18,080；Disrupted 显示 3 条直接暴露，Difference 显示 4 条变化航班；结果导出按钮可用。

## 7. 后续范围

研究工作台 v1 核心 AIR 复现已闭合，但不等于生产系统。真实航司接入需要数据映射、Flight Option 生成/筛选、成本标定、机组法规与保障规则、业务可解释性、运行时限和规模/稳定性验证。Phase 13 保留在 `feature/phase-13`，本次不合并到 `main`。
