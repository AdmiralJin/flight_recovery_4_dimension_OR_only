# Workbench v3 重构与 UI 优化交付

任务1、任务2均已完成。保留 v2、现有 API 与默认入口；本轮后端文件未修改。

## 使用入口

- [打开 v3 隔离预览](http://127.0.0.1:8013/static/workbench-v3/index.html#/prepare)：已启动，使用独立测试数据，不写入当前工作台记录。
- 项目现有服务入口：`/static/workbench-v3/index.html#/prepare`。构建产物在 `frontend/workbench-v3`，未覆盖 `frontend/dist`。
- 开发、构建、隔离测试命令与功能映射见 [v3 README](../../frontend/v3/README.md)。

## 本轮实现

- 新建独立 React / TypeScript v3，沿用 TanStack Query、Zustand、ECharts、Lucide；三个工作区为数据准备、配置与运行、结果分析。
- 统一 Case、厦航、JSON 与空白草稿入口；数据按资源、扰动容量、校验、高级数据组织，保留复杂 JSON 和完整证据。
- 未保存修改使校验失效并阻止运行；切换草稿与关闭编辑提供保存、放弃、取消；409 保留本地修改；过期请求不能覆盖新选择。
- 应用级运行监听、历史事件恢复、取消与快照分析；执行状态和求解结论分开显示。AIR / 厦航分别保留目标单位和 UTC / 北京时间。
- 合并四模式图表、资源联动、成本延误、审计与 JSON / CSV 导出；表格继续虚拟化。

## Skill 与针对性优化

安装 [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/b7d5353e0130feb8c5574ef1251f8a1db1873ccb)，版本 **2.15.0**，MIT，固定 commit `b7d5353e0130feb8c5574ef1251f8a1db1873ccb`。查证时 146008 星，未归档；74 个包文件与固定 Git blob hash 一致，脚本依赖已检查，无新增项目依赖。

采用适合分析工作台的简洁风格、数据排版、表单反馈和图表规则；营销首页建议未用于工作区结构。来源见 [provenance](../ui/workbench_v3_skill_source.json)，项目规则见 [MASTER.md](../../design-system/workbench-v3/MASTER.md)。

| 优化项 | 落实结果 |
|---|---|
| 字体与数字 | 表格 13px、辅助文字 12px；移动输入 16px；等宽数字及简洁时间显示 |
| 控件 | 共享主题变量；桌面 40px、窄屏 44px；加载、禁用、错误、焦点与按下状态 |
| 数据阅读 | 标识符优先、首列固定；万行数据保持虚拟化；长厦航样本名正常换行 |
| 图表 | 中文文字图例；LB / UB 不同线型及形状；键盘缩放、范围重置、主题切换保留缩放 |
| 错误反馈 | 错误摘要可聚焦，弹窗内可见错误，保留字段及本地修改 |
| 浅深色 | 普通文字对比度最低约 5.66:1；关键控件边界最低 3.31:1，分别验证两套主题 |

前后截图共 42 张：任务1 18 张、任务2 24 张。

- 数据准备：[优化前](assets/v3_task1/prepare_1440_light.png) / [优化后](assets/v3_task2/prepare_1440_light.png)
- 窄屏深色分析：[优化前](assets/v3_task1/results_390_dark.png) / [优化后](assets/v3_task2/results_390_dark.png)
- [厦航长样本名窄屏](assets/v3_task2/xma_prepare_390_light.png)

## 验收结果

| 检查 | 结果 |
|---|---|
| v3 状态、校验与竞态单测 | 13 项通过 |
| 模拟浏览器、异常与响应式 | 20 项通过；1440 / 1024 / 390、浅深色、键盘及 axe 自动检查 |
| 独立数据库真实浏览器 | 3 项通过；AIR、厦航求解导出闭环及 v2 页面兼容 |
| 停队基础设施 | 17 项通过；正常、超时、异常、进程树保护、控制器退出及重复停队 |
| v2 兼容 | 24 项前端测试、9 项现有 API 测试通过；临时目录构建通过 |
| 工程检查 | v2 / v3 TypeScript、v3 ESLint、v3 生产构建通过 |
| 隔离 | 162 个后端 / v2 / 原构建文件 hash 不变；当前数据库 hash 和各表行数不变（34 草稿、27 运行） |

结构化证据在 `.workbench/v3_acceptance/FINAL_ACCEPTANCE.json`，另存测试 JSON、JUnit、主题对比度及隔离检查。自动检查覆盖所列场景，不代表所有数据、浏览器或无障碍需求的穷尽证明。图表库独立懒加载，构建仍有其体积提示。

## 暂缓任务

当前算例已结束，调度器停止派发；**34 项未执行、32 项已执行待复核**已逐项记录到 [tudulist.md](../../tudulist.md)。原冻结来源与截止时间保留；v3 开发和测试未恢复长测。后续按用户安排显式续测，再审查算法证据。
