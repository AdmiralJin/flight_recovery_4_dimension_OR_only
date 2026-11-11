# Workbench v3 交互效率优化

时间：2026-11-07 07:39（北京时间）。

完成 v3 保存、编辑和运行监控的效率优化，并重新构建 `frontend/workbench-v3`。本轮未修改后端文件、求解算法、v2 文件及原算法验证批次。

## 定位与改动

- 原先每次输入复制整份草稿，多处刷新重复序列化完整输入。改为复制编辑分支、共享未变资源与撤销历史，使用常数时间判断修改状态；保存冲突和过期响应保护保留。
- 大型 JSON 的编解码、格式化和导出交给按需启动的 Web Worker。小响应直接解析，Worker 不可用时保留兼容路径。
- 新增「仅保存」，保存修改时不生成候选；切换草稿和关闭编辑时的「保存后继续」也不再执行编译。开始求解仍要求当前输入和配置校验通过。
- 保存、校验、运行快照和后台提交分别显示真实阶段与已用时间；等待期间允许工作区切换及主题切换，禁止重复提交。
- 运行事件使用现有 `after` 游标增量补全；SSE 每 250ms 合并更新，前台轮询 4 秒、后台 15 秒，恢复前台立即同步。结束后补取最后事件，切换运行取消旧请求，未知事件类型仍由历史接口补齐。
- 页面按需订阅状态，运行刷新不再重绘草稿编辑器；表格保持虚拟化，搜索与图表缓存计算结果，时间格式器按时区复用。
- 折叠的日志、审计和 JSON 在展开时才生成。JSON 预览最多显示 12 万字符，完整内容仍可导出；方案对比也改为展开时读取。
- 浏览器测试输出按阶段和 PID 隔离，避免并发验收互相清理 trace 文件。

## 固定负载观测

同一浏览器测试使用 10000 航班、20000 候选和 8000 条事件，草稿 JSON 共 5712125 字符。

| 指标 | 优化前 | 最终优化后 |
|---|---:|---:|
| 连续输入相同文本，含固定键入间隔 | 3311ms | 271ms |
| 20 次修改状态检查 | 525.8ms | 低于本次计时分辨率 |
| 8000 条事件更新到两次动画帧回调 | 274.7ms | 6.7ms |
| 折叠详情预生成的 JSON 字符 | 3756927 | 0 |

以上是本机固定模拟负载的排查性观测，不代表后端求解加速比。原始测量、当前源码 hash 及对比保存在 `.workbench/v3_acceptance/performance/comparison.json`。

## 方法选择

客户端瓶颈集中于对象复制、JSON 和重复渲染，因此采用后台 CPU 线程及减少重复工作。[MDN Web Worker 文档](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Using_web_workers)说明了后台线程与界面线程的职责；搜索交互参考了 [React 延后更新文档](https://react.dev/reference/react/useDeferredValue)，并结合已安装的 UI/UX Pro Max 主线程预算、按需加载和等待反馈规则。

本机为 Windows，安装的 gurobipy 为 13.0.3。Gurobi 当前 GPU PDHG 支持 Linux/NVIDIA，MIP 使用范围限于初始根松弛，不能直接用于本轮浏览器操作，见[官方部署说明](https://support.gurobi.com/hc/en-us/articles/43498824105873-Installing-and-Running-GPU-enabled-Gurobi)。本轮保留原求解器与算法行为，构模及求解本身的耗时没有作出加速承诺。

## 验证与隔离

- `build:v3`、TypeScript 检查及 `lint:v3` 通过。
- 28 项单元测试通过，包含保存冲突、请求竞争、不可变编辑、撤销重做、Worker 降级、事件游标和结束补取。
- 23 项模拟浏览器测试通过，覆盖保存/校验/提交/取消/历史恢复、慢请求响应、仅保存、导出、1440/1024/390 宽度及浅深色可访问性。对应输出为 `.workbench/v3_acceptance/playwright-efficiency_verified.json`。
- 3 项真实浏览器测试通过：AIR 完整流程、厦航完整流程、v2 入口兼容。测试使用端口 8014 和独立数据库 `.workbench/v3_acceptance/efficiency_20261107_073000`，输出为 `playwright-efficiency_live_verified.json`。
- 真实测试前后，当前工作台 SQLite、WAL、SHM 三个文件 SHA256 全部相同，证据为 `.workbench/v3_acceptance/performance/production_isolation.json`。
- 截图保存在 `docs/codex_reports/assets/v3_efficiency` 和 `v3_efficiency_verified`。本次新增的 8014 测试预览进程在验收后关闭；原有服务与后台批次保持原设置。

构建仍有 ECharts 独立分包大小提示，当前约 232KB gzip；本轮没有删除既有图表能力。刷新现有 v3 页面即可使用新构建。
