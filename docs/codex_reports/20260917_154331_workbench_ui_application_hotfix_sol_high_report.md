# Workbench UI / Application Hotfix 工作报告

- 时间：2026-09-17 15:43:31（Asia/Shanghai）
- 分支：`fix/workbench-ui-sol-high`
- 需求依据：`docs/chatgpt_review/WORKBENCH_UI_APPLICATION_HOTFIX_AND_UX_ENHANCEMENT_PLAN.md`
- 版本定位：AIR Recovery Research Workbench v1.1

## 完成内容

1. 统一案例状态与输入同步
   - 增加 `applySolveBundle()` / `applyScenario()` 单一加载入口。
   - Scenario、Recovery Columns、Passenger Capacity、Cost Overrides 与 Algorithm Profiles 始终绑定当前案例。
   - Constraints 页面不再回退显示固定 benchmark 的 Columns / Capacity。
   - 增加 Case ID、来源、Scenario ID、Bundle schema、revision、加载时间等元数据。

2. 加固 Solve 生命周期
   - 在任何异步预检前锁定 Solve，阻止双击重复请求。
   - Solve 使用启动时冻结的 bundle 快照，结果与输入 revision 绑定。
   - 过期结果不会写入当前案例。
   - 求解期间锁定会改变输入的操作，并显示 elapsed time 与长耗时提示。
   - 新增可执行的状态单元测试，覆盖重复启动和 stale result 拒绝逻辑。

3. 修复 Reset 与成本基线
   - `Reset Changes` 恢复当前案例加载时的完整 baseline。
   - `Reset Cost Overrides` 恢复案例自带 override，而不是清空为 `{}`。
   - `toy_case_016_benders_branch_and_price` 的 `crew_reassignment=100`、`deadhead_per_minute=1` 得以保留。

4. 增强案例选择和 API
   - 新增 `GET /api/solve/examples`。
   - 两个正式 solve-ready bundle 明确标记；其余 `data/examples/*.json` 自动归类为 scenario-only。
   - 支持 `?case=<case_id>` URL 复现。
   - 页面显示 API / Solver 健康状态。

5. 改进 UX 与错误反馈
   - 顶部明确显示 Case、Solve Readiness、Solver、Result、API 状态。
   - Solve disabled 状态持续展示 missing / invalid 原因并写入 tooltip。
   - 增加全局 toast，覆盖导入、校验、预检、求解和初始化错误。
   - Validate 根据 Data / Visualization / Costs / Constraints / Recovery 当前视图执行相应校验。
   - Visualization 移除永久 disabled 的 `Recovered Plan`，改为可用的 `Open Recovery →`。
   - Recovery 默认打开 Difference，并补齐分项成本、changed flights、LB / UB / Gap / runtime 摘要。

6. 导入导出与 HTTP 错误处理
   - Import 自动识别 Scenario、Solve Bundle、`workbench_snapshot_v1`。
   - Export 分为 Scenario、Solve Bundle、Recovered Result、Workbench Snapshot。
   - 统一 JSON / 非 JSON HTTP 错误处理，避免服务器纯文本错误退化为 JSON parse error。

7. 文档与测试
   - 更新 `README.md` 和 `reproduction_notes.md` 的 Workbench v1.1 流程与边界说明。
   - 增加 API catalog、unknown example、状态生命周期、baseline reset、HTTP 错误及 dead-button 回归测试。
   - 将需求计划文档加入当前分支对应路径。

## 验证结果

- `python -m pytest -q`：430 项全部通过。
- `node --test tests/frontend/*.test.mjs`：24 项全部通过。
- Playwright 真实页面冒烟测试：通过。
  - URL 直达 toy016 后 Solve Ready。
  - toy016 成本 override `crew_reassignment=100` 正确保留。
  - Visualization 显示 `Open Recovery →`，无永久禁用 `Recovered Plan`。
  - 切换 `toy_case_001` 后 Solve disabled，Constraints 显示无 Recovery Columns。
  - 页面无 console error / page error。
- `phase1_benchmark_001` exact solve：测试期望 objective `18080` 通过。
- `toy_case_016_benders_branch_and_price` exact solve：测试期望 objective `95200` 通过。
- `git diff --name-only | rg '^backend/core/'`：无变更。

## 边界确认

- 未修改 `backend/core/`。
- 未修改 SRM / ARM / CRM / PRM 数学约束、Benders、Column Generation、pricing、branching 或 Integrated Oracle。
- 保持同步 exact solve 与 research workbench / not production-ready 定位。
- 工作区原有 `AGENTS.md/.AGENTS.md` 大小写相关未提交状态未作处理。
