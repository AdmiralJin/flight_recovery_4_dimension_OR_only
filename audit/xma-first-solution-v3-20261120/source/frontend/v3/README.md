# Workbench v3

独立的 React 工作台，沿用现有 `/api/v2` 与 `/api/cases`。三个工作区为数据准备、配置与运行、结果分析；v2 入口及构建目录保留。

## 使用

在 `frontend` 执行 `npm run build:v3`，用项目现有服务访问：

`http://127.0.0.1:8000/static/workbench-v3/index.html#/prepare`

开发：`npm run dev:v3`，地址 `http://127.0.0.1:5174/static/workbench-v3/#/prepare`，API 代理到 8000。

页面内切换保留编辑。切换草稿、创建或导入、关闭记录编辑时，未保存修改需要保存、放弃或取消。「仅保存」与「保存后继续」只持久化修改，不生成候选；开始求解仍须通过「保存并校验」。保存、校验、快照及提交分别显示当前阶段和等待时间。运行与分析使用不可变快照，当前编辑不会改写历史结果。

## 隔离验收

所有验收使用模拟 API 或独立数据库，不连接当前工作台记录：

```powershell
python scripts/prepare_v3_test_fixtures.py
cd frontend
npm run typecheck:v3
npm run lint:v3
npm run test:v3
npm run e2e:v3
```

准备夹具必须从项目根目录执行。浏览器测试读取真实接口生成的 `.workbench/v3_acceptance/api-fixtures.json`；未声明的 API 请求使模拟测试失败。测试的脚本不会安装依赖。

真实点击闭环预览：从根目录运行 `python scripts/workbench_v3_preview.py`，访问 `http://127.0.0.1:8013/static/workbench-v3/index.html#/prepare`。该服务使用 `.workbench/v3_acceptance/preview_store`，包括独立的求解工作进程；示例草稿和历史结果从验收夹具复制。

在 `frontend` 执行：

```powershell
$env:WB3_LIVE='1'
npm run e2e:v3 -- live.spec.ts
```

测试真实 AIR、厦航运行及 v2 入口。只应连接隔离服务，不连接当前工作台。可用 `WB3_LIVE_URL` 指定另一个独立预览端口，用 `WB3_VISUAL_PHASE` 区分验收输出。

## 隔离约束

- 构建只写 `frontend/workbench-v3`，不写 `frontend/dist`。
- v3 的 Zustand、主题和本地存储键使用独立的 `wb3.*`。
- 沿用 v2 API 合同、类型和图表计算函数；v3 的传输层使用 Web Worker 处理大型 JSON，不依赖 v2 的状态或 CSS。
- 运行订阅在应用根部，SSE 每 250 毫秒合并显示，历史轮询使用 `after` 游标增量补全，前台 4 秒、后台 15 秒；恢复前台立即同步，结束后再补取最后事件。切换运行会取消旧请求。
- AIR 使用 UTC；厦航依据输入的 UTC+8 时刻及业务结果显示北京时间，目标单位分开。
- v3 不提供新的 `/api/v3`，不修改后端、算法和长测冻结副本。

## v2 功能映射

| v2 入口 / 功能 | v3 位置 |
|---|---|
| Case 克隆、厦航、JSON 导入、另存草稿 | 数据准备 → 新建 / 导入；导出草稿后也可导入为独立副本 |
| 数据实体、记录检查器、撤销重做 | 数据准备 → 数据资源 / 扰动与容量；普通表单及记录证据 |
| 候选、成本、复杂结构与完整输入 | 数据准备 → 高级数据 → 完整草稿 JSON |
| 影响、容量变化、编译问题 | 数据准备 → 校验预览；结果分析 → 当前草稿 / 扰动影响 |
| XMA 目标、算法、候选网格与时限 | 配置与运行 → 求解配置 |
| AIR Runtime Profile、时限与节点限制 | 配置与运行 → 模板与自定义副本 |
| 启动取消、事件、界、历史 | 配置与运行；运行监听在应用级保持 |
| 航班、飞机、机组、传播图 | 结果分析 → 航班与资源（合并总览，保留方案对比与资源汇总） |
| 旅客甘特、容量热图、厦航座位分配 | 结果分析 → 旅客与容量 |
| 四模式对比、成本、延误 | 结果分析 → 模式切换 / 成本与延误 / 航班明细 |
| 审计、原始证据、JSON / CSV 导出 | 结果分析 → 审计与导出；技术证据按需展开 |

算法验证待办见根目录 `tudulist.md`；v3 开发和测试不恢复长测。

## 性能验证

结果分析保留完整模型的时间、数值域和资源索引，筛选仅遮罩数据；横纵轴滑块与缩放按钮支持手动控制，按数据来源及图层保存手动范围。图表说明使用 v3 独立的 `analysisCharts.ts`，不修改 v2 图表函数。运行时钟作为独立组件每秒更新，避免带动图表重绘；共享 `Help` 支持悬停、聚焦、点击及 Esc，参数说明与公式采用当前配置。

常用表单只复制编辑分支，撤销历史共享未改动的数据；不要直接修改 `draft.document` 或编辑副本。完整 JSON 的解析、格式化和导出交给一个按需启动的 Worker；不支持 Worker 的环境使用兼容路径。大型响应只在超过 128KiB 时交给 Worker 解析。

表格保持虚拟化，搜索与分析图表使用缓存及延后更新；折叠详情在展开时才加载，JSON 页面预览最多 12 万字符，完整数据可导出。Worker 能改善界面响应，求解器的构模、算法及最优性证据保持原有行为。

`e2e/performance.spec.ts` 使用固定的 10000 航班、20000 候选、8000 事件负载，同时检查慢请求反馈和仅保存行为。观测结果保存在 `.workbench/v3_acceptance/performance`。这些是本机浏览器观测，不作为跨机器的耗时保证。

## 设计规则与视觉证据

UI/UX Pro Max 2.15.0 固定为 commit `b7d5353e0130feb8c5574ef1251f8a1db1873ccb`，已安装到用户技能目录。来源与 hash 见 `docs/ui/workbench_v3_skill_source.json`；项目采用的规则见 `design-system/workbench-v3/MASTER.md`。

设计变量集中在 `src/tokens.css`。普通字段、表格、状态、对话框与图表使用共享组件；数字等宽、表格首列固定，深浅色分别定义对比度。前后截图保存在 `docs/codex_reports/assets/v3_task1` 与 `v3_task2`。
