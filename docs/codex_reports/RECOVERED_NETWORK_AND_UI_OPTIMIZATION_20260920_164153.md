# AIR Workbench 恢复时空网络与 UI 优化报告

- 完成时间：2026-09-20 16:41:53（Asia/Shanghai）
- 工作分支：`feature/air-workbench-data-ui-improvements`
- 提交状态：未提交、未合并、未部署

## 任务 1：恢复结果接入时空网络图

已将 Solve 返回的 `resolved_flights` 接入可视化模型，并启用“恢复计划”模式。

### 完整性与状态控制

- 仅当求解状态为 `optimal`，且每个 Scenario 航班都有对应恢复结果时，启用“恢复计划”。
- Scenario-only、未求解、不可行、未收敛、不完整结果或已过期结果不会生成可能误导的恢复网络。
- 切换 Case 或修改输入导致结果过期时，“恢复计划”自动回退到扰动视图。

### 图中展示

- 恢复后的起飞与到达时间。
- 恢复后的始发站与目的站。
- 延误航班及延误分钟数。
- 取消航班、取消标记及原计划位置。
- O-D 变更。
- 飞机改派与机组改派文字标记。
- 对发生变更的航班，以灰色虚线保留原计划位置，便于对照审计。

### 详情面板

- 展示所选 Flight Option、恢复状态、恢复时刻、起飞/到达延误。
- 以状态标签区分延误、取消、O-D 变更、飞机改派和机组改派。
- 对比原计划飞机/机组与恢复方案飞机/机组。
- 展示恢复后的飞机轮转及机组 OPERATE 配对。

## 任务 2：整体 UI 优化

采用简洁的航空运行控制台视觉方向，对页面进行统一重构：

- 使用深蓝—青绿色专业配色，统一页面背景、卡片、边框、阴影和状态色。
- 缩减顶部区域高度，提高首屏有效信息密度。
- 重构五视图导航为全宽、吸顶式分段导航。
- 优化 Case 选择区、工作流、命令栏、数据页签与校验面板层级。
- 统一按钮、输入框、表格、徽标、空状态和焦点状态。
- 表头支持滚动区域内吸附，提高大型数据表可读性。
- 约束、成本、恢复结果及可视化面板使用一致的卡片与间距系统。
- 可视化详情面板在桌面端吸附，窄屏自动恢复普通流式布局。
- 改善平板和手机布局，避免操作按钮和主要导航拥挤。
- 技术型数据工作台不引入无关装饰图片，以数据图形和信息层级作为主要视觉表达。

## 主要修改文件

- `frontend/js/visualization.js`
- `frontend/js/app.js`
- `frontend/index.html`
- `frontend/css/styles.css`
- `frontend/css/workbench.css`
- `frontend/css/visualization.css`
- `frontend/css/recovery.css`
- `tests/frontend/visualization.test.mjs`
- `tests/api/test_api.py`

## 验证

- `node --check frontend/js/visualization.js`：通过。
- `node --check frontend/js/app.js`：通过。
- `node --test tests/frontend/*.test.mjs`：21 项全部通过。
- `pytest -q`：全量测试全部通过。
- 四个 CSS 文件的大括号结构检查通过。
- `git diff --check`：通过。

浏览器静态资源版本已更新为 `recovery-network-ui-20260920-1`，以避免旧缓存继续使用此前的 JavaScript 或 CSS。
