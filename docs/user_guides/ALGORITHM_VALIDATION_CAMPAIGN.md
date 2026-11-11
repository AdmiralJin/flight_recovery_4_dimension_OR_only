# 算法后台验证批次

入口是 `scripts/validation_campaign.py`，实验实现是 `scripts/validation_jobs.py`。只使用本机现有 Python、求解器和数据，不安装依赖、不修改求解 API。Windows 依赖 `psutil` 和 `pywin32`，科学依赖沿用项目环境。

## 启动与管理

在项目根目录运行，下列命令中的 `<批次目录>` 替换为 `prepare` 返回的绝对路径：

```powershell
# 基础设施验收：包括真正的 Windows 内存限制、子进程终止和恢复
python -m pytest tests/unit/test_validation_campaign.py

# 冻结清单、代码、数据及参考结果；默认单例 2 小时、整批 24 小时
python scripts/validation_campaign.py prepare --profile long

# 启动隐藏的调度器，并打开 11 个分类 CMD 和 1 个总览 CMD
python scripts/validation_campaign.py launch --folder "<批次目录>"

python scripts/validation_campaign.py status --folder "<批次目录>"
python scripts/validation_campaign.py monitors --folder "<批次目录>"
python scripts/validation_campaign.py stop --folder "<批次目录>"
python scripts/validation_campaign.py resume --folder "<批次目录>"

# 已结束批次的续测：只补跑失败、阻塞、依赖受阻等未完成项目
python scripts/validation_campaign.py prepare --continue-from "<原批次目录>" --profile long
# 用户明确要求不等待系统空闲资源时（仅对新批次生效）
python scripts/validation_campaign.py launch --continue-from "<原批次目录>" --profile long --no-resource-wait
# 如需使用本机现有 Java，prepare/launch 可附加 --java-executable "<java.exe绝对路径>"
```

也可直接 `launch --profile long`，一次完成准备和启动。`--no-windows` 仅隐藏监控窗口。单独双击 `monitors/*.cmd` 可重开某一个窗口。CMD 启动即显示，之后每 300 秒刷新；关闭 CMD 不会影响计算。

启动后先等待至少 **6 GiB 可用物理内存**。显示 `waiting_for_memory` 时没有运行正式求解，也没有开始 24 小时计时；内存达标后自动执行。不会关闭用户程序来释放内存。

`--no-resource-wait` 将此策略固定到新批次清单：立即开始计时，跳过启动和派发时的系统可用内存检查，关闭连续低内存停测规则；仍保留最多两项并行、性能独占、单例硬墙钟及 Windows 进程树内存上限。已有冻结批次不改动；应使用续测入口应用新策略。

计算和监控均为本机进程。关机后需要显式 `resume`；原始截止时间仍有效。恢复只重排被中断或主动停止的项目，保留已完成结果、尝试编号和原始日志；不会自动重跑超时或超内存项目。同一工作区只能有一个调度器，重复启动会拒绝。

`--continue-from` 创建新批次并拥有独立预算。它复制原批次冻结的算法、数据与任务参数，只覆盖列明的调度器、实验入口、基础设施验收和操作说明文件。已完成结果按路径与 SHA256 继续引用；原批次不修改。监控标题附带批次编号，便于区分旧窗口。

pytest 的临时工作区使用短路径 `.workbench/vtmp/frv_*`；路径太长时退回系统临时目录。每次尝试保存 `pytest_workspace.json` 映射并保留工作区，避免 Windows 未开启长路径支持时，嵌套的工件文件名超过 260 字符。JUnit、日志和最终结果仍写入本批目录。

## 任务与执行约束

- 回归：现有 `tests/unit`、`tests/api`、`tests/regression` 的全部 Python 测试文件，包含生成器暴力枚举对照、20 个 micro 输入合同和约束覆盖检查。
- 参考解：8 个 catalog Case 和其余可求解 micro。相同规范请求按 SHA256 合并，别名与所有预期断言保留在清单中。
- AIR：toy11/12 与 benchmark 全列 LP 对照动态列生成，独立检查遗漏列 reduced cost；benchmark、机组整数性案例的联合 Oracle 与 Benders/B&P 对拍。toy13/15 等阶段算法及分支约束由已有回归逐项覆盖。
- 终止与合理性：有效但不可行、立即取消、迭代/节点限制、容量放宽、候选扩充、输入重排。只对证明最优的结果断言单调性。
- 厦航小例子：正常、扰动、超售、拆分改签、整数分支，四算法与两种目标。
- 真实数据：固定约 20/100 班，以及随机约 20/100 班各两个种子 `20261106`、`20261107`；三种非枚举算法，AIR/Tianchi 两种目标分开比较。
- 压力：AIR P1–P5；厦航粗档 100/500/2364、细档 100/500 的三算法；全量细档只做输入及候选规模门槛检查。按整条机尾选样，实际航班数可能高于请求数。
- 官方 JAR：只核验现有派生工作簿及输出；Java 不可用时独立重算仍保留，但 JAR 记为依赖受阻。

粗档步长/最大延误为 `60/120` 分钟，细档为 `30/1440`。显式路径 Oracle 仅用于小例子，路径上限 100000；压力任务的 assignment 门槛显式提高到 10000000，全量细档预检维持 100000 门槛。完整请求、机尾列表、实际航班数和样本 hash 随结果保存。

先完成正确性和停止测试，再独占执行计时对照，最后递增压力。正确性最多两项并行，同一分类不重叠；性能及压力任务独占。所有求解器固定一线程、种子 0。小型计时先预热一次，再测三次，保存各次、中位数和范围。

轻/中/重任务使用约 1.5/2.5/4 GiB 的 **Windows 进程树提交内存上限**，并为系统预留至少 1.5 GiB 的物理内存。内存计数是不同口径：RSS 是每秒采样，commit 峰值来自 Windows Job；极短任务可能没有 RSS 样本。Windows 的历史 commit 峰值可能包含被拒绝的分配请求。单例硬墙钟覆盖进程启动、读入、建模、求解和落盘，最晚在下一轮约 1 秒的调度检查终止整棵进程树。系统可用内存连续 10 秒低于 1 GiB 时终止本批中内存最大的活动任务。

算法或独立审计的断言失败，会阻止对应路线后续计时和压力任务；许可证、依赖、超时、内存受限单独列出。24 小时到期停止活动任务，保留部分证据，并列出未运行项目。

## 结果与证据

每批目录为 `.workbench/validation_campaigns/<时间戳>/`：

| 文件 | 内容 |
|---|---|
| `manifest.json`、`manifest.sha256.json` | 不可变任务、参数、预期、来源、机器/依赖环境及代码数据 hash |
| `source/` | 完整冻结副本；不复制当前工作台 `.workbench`，不使用硬链接 |
| `state.json`、`00-overview.txt`、分类 `.txt` | 调度状态、时限、内存、进度和停止原因 |
| `jobs/<id>/attempt_NNN/` | 每次输入、完整配置、日志、事件、结果、审计和可用的选中方案 |
| `jobs/<id>/result.json` | 最近一次尝试的摘要，不覆盖旧尝试 |
| `summary.json`、`summary.csv`、`SUMMARY.md` | 全任务汇总；结束或中断时生成 |
| `campaign.junit.xml`、各 pytest `junit.xml` | 批次与测试文件级 JUnit |
| `performance_comparisons.json` | 同一输入及目标下三算法的可比性、各次时间、中位数、范围和允许计算的加速比 |

性能时间区分候选生成、建模、求解、独立审计及算法端到端流程。阶段可能嵌套，不能直接相加。AIR 全宇宙对照审计单独计时，不算入常规算法流程；CG 候选生成与定价交织，无法单列时记为缺失，不能当作零耗时。首次可行解记录的是全局可行上界事件的观测时间；没有可靠事件时保留缺失值。嵌套主问题、子问题、分支节点的界不会冒充全局上下界。

`passed` 是该测试断言通过；`completed` 是采样流程完成。科学结论还要分别看 `conclusions`、优化状态、参考值、上下界闭合和独立审计。只有相同问题、三次均最优且审计通过、目标一致的算法才计算加速比；超时无解不作为零耗时样本。三次重复只描述本机观测。

正式批次运行期间无需 Codex 在线。全部结束后，再结合原始证据复核算法可靠性、列生成收益及规模边界。

## 低额度后台监控

```powershell
python scripts/validation_watch.py start --folder "<批次目录>"
```

独立本地进程每 30 秒检查调度器存活，每 300 秒保存一次摘要及更新 `tudulist.md`，不调用模型。调度器异常退出时最多自动恢复三次，保留已完成结果和原截止时间；显式 STOP 不自动恢复。并发超过两项或独占计时被打破时请求停止并留证。

结束后自动核验冻结来源与继承结果 hash，合并历次任务证据及同问题性能对照，写入 `combined_evidence.json`、`combined_performance_comparisons.json` 和 `docs/codex_reports/*_validation_campaign_finished.md`。`watch_state.json` 给出监控状态与最终报告路径，`watch_events.jsonl` 记录采样与恢复。`completed` 仍只表示测量完成，不表示已证明最优。监控程序自身的 SHA256 单独记录，不修改运行中的冻结批次。
# 暂缓派发（Workbench v3 开发期间）

```powershell
python scripts/validation_campaign.py defer --folder .workbench/validation_campaigns/<批次>
```

独立后台控制器暂停原调度器的派发，保留当前工作进程及原 Windows Job 内存保护，继续检查单例时限、原批次截止时间和系统内存。当前任务结束后，原调度器在读取 STOP 后完成结果落盘，不再派发排队任务。控制器异常时受管进程自动终止；恢复前检查 `defer.json`、`state.json` 与已有结果。

当前任务未退出前，不要手工结束原调度器。`defer.json` 标记 finished、`state.json` 标记 finished 后，可用 `scripts/write_validation_todo.py --folder <批次>` 记录未执行与已执行项目；不要在仍有运行任务时生成已停队的清单。

后续可显式 `resume --folder <批次>`（沿用原截止时间），或用已有 `launch --continue-from <批次>` 创建续测批次、复用已完成证据。v3 开发、构建及浏览器验收均不自动恢复长测。

