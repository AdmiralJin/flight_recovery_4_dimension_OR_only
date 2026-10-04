# Workbench v2 独立可视化板块实施报告

- 完成时间：2026-09-27 16:17（Asia/Shanghai）
- 分支：`feature/air-workbench-data-ui-improvements`
- 基线提交：`1880d4b fix: html black screen`
- 新入口：`/workbench-v2/visualization`

## 完成内容

### 服务端规范化可视化模型

- 新增 draft/run 两个只读接口：
  - `GET /api/v2/drafts/{draft_id}/visualization`
  - `GET /api/v2/runs/{run_id}/visualization`
- 新增 `VisualizationModel 1.0.0`，统一输出：
  - Original/Impact/Recovered/Delta 可用性；
  - 类型化或 legacy 扰动时域；
  - 原始、有效和恢复航班；
  - 直接暴露、飞机/机组传播证据；
  - 飞机、机组和旅客时间线；
  - 基线/有效/恢复容量与 load/slack/utilization/binding；
  - 目标函数、成本项、延误和恢复动作。
- run 可视化只读取其不可变 snapshot，不读取当前草稿。
- non-optimal 或结果不完整时，Recovered/Delta 明确不可用，不生成虚构恢复计划。

### 选中列可复现产物

- v2 求解完成时额外保存内容寻址 gzip artifact：
  - 选中 Aircraft String；
  - 选中 Crew Pairing 及 duty/segments；
  - 选中 Passenger Itinerary，包括 surface；
  - 所有被引用的 Flight Option，包括 ferry。
- SQLite `runs` 增加 `solution_artifact_hash`，已有数据库通过幂等 `ALTER TABLE` 自动迁移。
- v1 `RecoveredResult` 和 `/api/solve` 合同未改变。
- 审计导出包现在包含 visualization model 和 selected solution artifact。
- 新运行能够完整画 REST/GROUND_TRANSFER/ferry/surface；旧运行没有 artifact 时返回明确的 layer availability reason 并降级。

### 独立可视化页面

- 工作流调整为六步：`数据设计 → 扰动影响 → 求解 → 可视化 → 方案对比 → 审计`。
- 新页面提供八个主视觉标签：
  - 机场—UTC 时间航班箭头图；
  - 飞机轮转甘特；
  - 机组执勤甘特；
  - 旅客行程时间线；
  - 机场容量热力图；
  - 局部传播证据图；
  - 成本瀑布；
  - 起飞/到达延误图。
- 航班主图支持：
  - UTC 时间轴、缩放、滑动范围；
  - 机场泳道和方向箭头；
  - `[start, end)` 扰动时域带；
  - 直接扰动粗实线、传播风险虚线；
  - Delta ghost、取消点和全部变化优先级。
- 飞机/机组/旅客甘特共用 UTC 时间轴；Impact 模式把直接/传播状态带入资源段。
- 统一支持机场、Changed/Unchanged、暴露类别和实体筛选。
- 实体选择保存为 `{type, id}`，图中点击和键盘实体选择器均可更新统一证据抽屉。
- URL 保存 mode、view、scope、airport、exposure、movement 和 selected entity。
- 390/768px 保留只读监控和图形浏览，底部导航扩展为六项。

### 性能和工程门禁

- ECharts 改为按需注册 Bar/Custom/Graph/Heatmap/Line/Scatter 及必要组件。
- Chart chunk 从约 1,127 kB / gzip 379 kB 降至约 689 kB / gzip 232 kB。
- 新增 500 航班 option 构建测试；航班使用 Canvas custom series，不创建每航班 React SVG 节点。
- 补充 ESLint 9 flat config，使原有 `npm run lint` 真正可执行。
- README 和浏览器用户手册更新为六步工作流。

## 关键缺陷修复

浏览器截图复验发现并修复两处仅靠 DOM 测试无法发现的问题：

1. 航班 lines 系列的 ISO/机场字符串没有被 ECharts 正确解析，主图为空；改为 Canvas custom series，显式使用时间戳和机场索引绘制线、端点、箭头及标签。
2. 扰动 custom series 未声明 encode，机场索引 `0` 被误当成时间数据，时间轴从 1970 拉伸到 2026；现已固定 `x=[start,end]`、`y=airport lane`。

## 验证结果

- `python -m pytest -q`：446/446 通过；唯一告警为既有 Starlette TestClient/httpx 弃用告警。
- `node --test tests/frontend/*.test.mjs`：22/22 通过。
- `npm run lint`：通过。
- `npm run typecheck`：通过。
- `npm test -- --run`：6/6 通过。
- `npm run build`：通过。
- `npm run e2e`（Microsoft Edge）：4/4 通过。
- Playwright axe WCAG 2.2 AA：0 violations。
- 1440px/390px：无 body 横向溢出、无未捕获 console error。
- 实际子进程求解烟测：completed/optimal，artifact 已保存；模型生成 19 个飞机恢复段、5 个机组 duty、13 个旅客恢复段。
- `git diff --check`：通过。

## 截图

- `docs/codex_reports/assets/workbench_v2_flight_visualization.png`
- `docs/codex_reports/assets/workbench_v2_aircraft_gantt.png`
- `docs/codex_reports/assets/workbench_v2_visualization.png`

## 已知边界

- 旧运行没有 selected solution artifact 时，恢复资源图只能按已有 result 降级；页面会明确提示，不推断缺失段。
- 维护模型只有 required flag/stations，没有维护时间窗，因此只展示维护元数据，不虚构维护甘特段。
- 成本保证展示并校验 objective 四分量；只有选中列中真实存在的 cost components 才能继续下钻。
- ECharts 图表块已经缩小约 39%，但仍有约 689 kB 的构建体积告警；页面和 Chart 均为 lazy chunk，不阻塞 Data 首屏。
- 传播图仅表示资源序列暴露证据，不解释恢复动作的因果来源。
