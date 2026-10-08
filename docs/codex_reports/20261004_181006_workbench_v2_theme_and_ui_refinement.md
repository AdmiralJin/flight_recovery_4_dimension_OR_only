# Workbench v2 双主题与 UI 统一改造实施报告

- 完成时间：2026-10-04 18:10（Asia/Shanghai）
- 改造范围：默认 React Workbench v2
- 兼容边界：`/legacy`、后端 API、数据库与求解逻辑均未修改

## 完成内容

### 浅色 / 深色主题

- 新增 `ThemeMode = "light" | "dark"`、主题上下文与全局顶栏切换按钮。
- 首次访问默认浅色，使用中性浅灰页面背景和白色卡片；深色主题保留原有运营工作台风格并提高弱文本和边框对比度。
- 主题选择保存到 `localStorage` 的 `air-workbench-v2-theme`，刷新后恢复；存储不可用时仍能在当前会话切换。
- HTML 首次绘制前读取主题，并同步 `data-theme`、`color-scheme` 和 `theme-color`，避免明显闪烁。
- 浅色和深色均通过 Playwright axe WCAG 2.2 AA 检查。

### 字体、布局与响应式

- CSS 建立语义化颜色、背景、边框、状态和字号令牌；所有显式可见字号均不低于 12px。
- 表格行高、按钮、选择框、卡片间距和图表边距随字号同步调整。
- 指标栏改为自适应列数，四指标页面不再出现第五个空块。
- 数据检查器、编译证据、求解事件、可视化证据和航班证据支持收起/展开；桌面默认展开，移动端默认收起。
- 1180px 以下主画布与详情自动上下排列；390–768px 保留只读监控、筛选、主题切换和六步底部导航。
- 移动端空图高度由 430px 收紧到 260px，底部导航增加安全区和页面滚动留白。
- 方案对比和审计页步骤编号修正为 05、06。

### 图表统一

- 新增共享 ECharts 主题层，统一字体、tooltip、legend、轴线、刻度、主/次网格、泳道底纹、dataZoom 和 visualMap。
- 航班时空图的完整坐标与网格风格扩展到 Original、Impact、Recovered、Delta。
- 飞机/机组/旅客甘特、容量热力图、成本、延误、求解收敛和方案对比图全部使用同一主题配置。
- 容量热力图分离缩放条和视觉映射，避免控件重叠；单元格增加主题化边界。
- v2 SVG 时空网络新增整点 UTC 刻度、纵向时间网格、横向泳道分隔与交替底纹。
- ECharts 实例不再因 option 更新反复销毁；主题切换时保留已有 dataZoom 范围。

## 测试与验证

- `python -m pytest -q`：446/446 通过；仅保留既有 Starlette TestClient/httpx 弃用告警。
- `node --test tests/frontend/*.test.mjs`：22/22 通过。
- `npm run lint`：通过。
- `npm run typecheck`：通过。
- `npm test -- --run`：12/12 通过。
- `npm run build`：通过；仅保留既有 ECharts chunk 超过 500 kB 告警。
- `npm run e2e`：4/4 通过。
- Playwright 在 1440px 和 390px 验证浅色/深色主题、主题持久化、折叠栏、无横向溢出和 axe WCAG 2.2 AA。
- `git diff --check`：通过。

## 截图

- 浅色桌面：`docs/codex_reports/assets/browser_refactor_desktop.png`
- 深色桌面：`docs/codex_reports/assets/workbench_v2_dark.png`
- 浅色移动端：`docs/codex_reports/assets/browser_refactor_mobile_390.png`
- 深色移动端：`docs/codex_reports/assets/browser_refactor_mobile_390_dark.png`
- 浅色可视化：`docs/codex_reports/assets/workbench_v2_visualization.png`

## 已知边界

- 移动端仍是简化只读模式，不开放复杂数据编辑。
- `/legacy` 保持原样，不共享 v2 主题状态。
- ECharts 图表块约 706 kB（gzip 约 238 kB），仍触发既有 Vite chunk size warning；页面和图表继续按路由懒加载。
