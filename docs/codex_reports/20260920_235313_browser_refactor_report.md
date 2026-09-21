# AIR Recovery Workbench 浏览器重构实施报告

- 完成时间：2026-09-20 23:53（Asia/Shanghai）
- 工作分支：`feature/air-workbench-data-ui-improvements`
- 实施范围：安全稳定门、v2 数据内核、异步运行与 Trace、React 工作台、对比/审计、测试与文档
- 数据边界：单机、单活动求解任务、无账号/云同步、仅 full scope

## 1. 交付结果

新版工作台已可从 `/workbench-v2` 使用；存在 `frontend/dist` 构建产物时根路径 `/` 默认进入新版，旧版保留在 `/legacy`。界面采用 React 19 + TypeScript + Vite，保持深蓝—青绿色基线，移除旧版大 Hero 和重复工具栏，改为：

```text
数据设计 → 扰动影响 → 求解 → 方案对比 → 审计
```

桌面端提供完整工作面，390/768px 为只读监控与结果查看布局。每个页面保留一个核心视觉中心，详情进入右侧面板或下方记录区。

## 2. 安全稳定门

旧版同步 UI 已修复以下 P0 竞态：

- Solve 锁在首次异步等待前建立，双击不会提交两次；
- 求解提交时冻结 Case ID、input revision、Solve Bundle 和 Scenario；
- 求解中编辑、Reset、Import、切换 Case 或乱序响应会让旧响应失效，不再登记为当前结果；
- STALE Recovery 使用当次求解 Scenario/输入快照，不再与当前 Scenario 混算；
- Scenario/Cost validation 使用请求代次与 revision guard；
- Case 先在临时状态完成 validate/precheck，再原子提交，失败不会留下半切换状态。

## 3. v2 数据与持久化

新增 `.workbench/` 本地库（已 gitignore）：

- SQLite/WAL：草稿、修订、快照、运行、事件和运行 Profile 索引；
- gzip JSON：以规范化 JSON SHA-256 内容寻址；
- 临时文件 + `os.replace` 原子写入；
- 内置 Case 只读，编辑前克隆；
- 工作副本使用 optimistic hash 防止覆盖；
- 求解快照固化 SolveRequest、编译预览、草稿文档、git commit、dirty 状态和 diff hash。

类型化扰动支持到达/起飞/双向容量 delta、机场关闭和宵禁；容量区间按边界切分，关闭/宵禁优先，其他 delta 累加并在零截断。旧 v1 Case 标记为 `effective_legacy`，不会再次应用旧自由文本扰动。

候选编译支持原计划、取消、默认 10 分钟步长/最大 60 分钟延误候选；改航和调机仍为手工候选。Passenger Itineraries 复用现有生成器，Aircraft Strings/Crew Pairings 继续由求解器内部生成。旅客存在时，缺失显式剩余容量会阻止快照。

## 4. v2 接口与运行

新增 `/api/v2`：

- Draft：列表、创建、工作副本、compile preview、immutable snapshot、导入导出；
- Profile：列表、克隆和白名单参数更新；内置 Profile 只读；
- Run：创建、列表、详情、SSE、取消、结果、comparison、audit、完整导出；
- Capabilities：真实 Gurobi/package/license 探测、单并发、候选生成边界；
- 错误：统一顶层 `ProblemDetails`，含 code/message/issues/run_id/retryable。

运行使用独立 Python 子进程和单并发 supervisor。SSE 事件含连续 `seq`，支持 `Last-Event-ID` 续传。协作取消由 Gurobi callback 检查；5 秒超时后终止隔离进程并保留事件。服务重启会把 preparing/running 标记为 `interrupted`。

Trace 实时记录 validation、Phase 11/12 Benders iteration、schedule、LB/UB、absolute/relative gap、Aircraft/Crew CG 状态与列数、binary/LP 目标、PRM、割、B&P 节点汇总、integrated audit 和结果构建。integrated audit 原始 lhs/rhs/slack/binding 结构进入审计事件与导出包。

修复的后端诊断问题：

- precheck 现在拒绝错误外层 `schema_version` 与 `algorithm`；
- `/api/health` 使用实际 Gurobi availability，不再硬编码可用；
- v2 明确输出 absolute/relative gap；
- `finished_at` 和 runtime 在结果构建完成后统一；
- Phase 12 infeasibility certificate owner 按 Aircraft/Crew/Passenger 来源生成。

## 5. React 工作台与可视化

Data Studio 使用 TanStack Table/Virtual 提供虚拟表格、搜索、行级 JSON 检查与编辑、撤销/重做、草稿导入导出；可检查/修改 Scenario、Flight Options、Passenger Itineraries、剩余容量、成本和算法 Profile。

Impact 页提供有效输入时空网络、direct/downstream 风险、容量变化和编译证据，不读取恢复决策样式。

Solve 页提供真实 LB/UB 收敛图、absolute/relative gap、结构化事件流、运行历史、运行 Profile 和取消。

Compare 使用服务端 canonical comparison model，统一 Original / Impact / Recovered / Delta：

- 完整 changed/unchanged 分区；
- arrival-only delay 纳入 `time_changed`；
- 多标签保留，主优先级为取消 → O-D → 时间 → 飞机 → 机组 → block → unchanged；
- 航班网络、飞机、机组、旅客、容量、成本四分量和延误分布共享选择语义。

Audit 展示不可变输入、选择、恢复动作、目标、界、Expected 对拍、integrated constraints、Trace、运行环境和审计包导出。

## 6. 测试与验收

全部通过：

- Python：`440 tests`；
- legacy Node：`22/22`；
- React Vitest：`2/2`；
- TypeScript：通过；
- Vite production build：通过；
- Playwright + Edge：`2/2`；
- axe WCAG 2.2 AA 自动规则：0 violation；
- 1440×1000 与 390×844：无 body 横向溢出、无 console error；
- `git diff --check`：通过；
- 真实异步 smoke：`completed / optimal / objective 0`，10 个事件，integrated audit 和 absolute/relative gap 可回读。

新增回归覆盖：外层合同 precheck、草稿 hash 冲突、clone-only Profile、SSE resume、真实 Phase 11 LB 单调、类型化扰动 hash/关闭优先、legacy 双重扣减防护、arrival-only change 和 changed/unchanged 完整分区。

## 7. 浏览器截图

- [桌面端 Impact](assets/browser_refactor_desktop.png)
- [390px Solve Monitor](assets/browser_refactor_mobile_390.png)

## 8. 已知边界

- ECharts 被懒加载为独立大 chunk（gzip 约 379 KB），首屏主 bundle 已降至 gzip 约 97 KB；构建仍提示该懒加载 chunk 超过 500 KB。
- 当前实时 Trace 的 CG 与 B&P 细节为每个 Benders schedule 的结构化汇总；尚未把每个 pricing 子迭代和每个 branch node 单独流式化。完整 integrated audit 已导出。
- 首版不自动生成改航、调机或生产级业务规则；这些候选必须手工添加/导入。
- `.workbench/` 是本机研究数据，不自动迁移或云同步；服务重启不恢复正在运行的进程。
- Windows Computer Use 的 Edge 连接器两次返回 `nodeRepl.fetch request failed`；最终浏览器验收改由 Playwright 直接驱动本机 Edge 完成，结果可重复。
