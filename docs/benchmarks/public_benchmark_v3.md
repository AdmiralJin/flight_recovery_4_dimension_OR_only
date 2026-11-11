# Workbench v3 公开数据验证

基线为 `fa293d3`（`workbench-v3-optimized`），分支为 `feature/public-benchmark-v3-validation`。公开入口使用 `public-benchmark-1.0` 封装，转换器版本、原文件 SHA-256、记录位置、模型、候选、成本、算法配置和固定上下文均保存在输入 JSON。算法与求解器选择不参与问题指纹；改变问题必须重新转换。

首批冻结实验已结束，验收门槛未通过；实际结果、未执行任务与后续改进依据见[首批验证报告](public_v3_results.md)。

## 使用方式

在仓库根目录执行，使用安装了 `requirements.txt` 的 Python。Windows 正式运行依赖 pywin32 Job Object，子进程在执行之前加入内存限制。安装前端后执行 `cd frontend`、`npm run build`、`npm run build:v3`，再返回仓库根目录。隔离回归仍检查 v2 页面，两套构建都必须冻结。

```powershell
python scripts/public_benchmark.py inventory --output .public_benchmarks/source-inventory.json
python scripts/public_benchmark.py results2019 --output .public_benchmarks/results2019
python scripts/public_benchmark.py convert roadef --instance A01 --target 6 --output .public_benchmarks/a01.json
python scripts/public_benchmark.py convert delft --start 2015-01-01T06:00:00+00:00 --hours 12 --target 12 --connections --output .public_benchmarks/delft.json
python scripts/public_benchmark.py precheck .public_benchmarks/a01.json
python scripts/public_benchmark.py run .public_benchmarks/a01.json --algorithm air_bp --backend highs --seconds 120 --output .public_benchmarks/a01-run
python scripts/public_benchmark.py draft .public_benchmarks/a01.json --output .public_benchmarks/a01-draft.json
python scripts/public_benchmark.py external .public_benchmarks/a01.json --evidence .public_benchmarks/a01-run/evidence.json --output .public_benchmarks/a01-native
```

默认自动发现 `data` 下唯一名称含 `_3` 的下载目录。目录不唯一时指定 `--data-root`，值为包含三个数据目录的共同父目录。`convert` 保留不支持规则的预检结果，不悄悄删除飞机或需求。`--model aircraft_passenger` 只接受 ROADEF；不从 Delft 边际连接人数构造完整行程。

正式实验先冻结清单及代码副本，再执行；目录必须不存在。`pilot` 是开发验证配置，`full` 注册完整首批清单。

```powershell
python scripts/public_benchmark.py prepare --profile full --budget-hours 24 --output .public_benchmarks/formal-v3
python scripts/public_benchmark.py campaign .public_benchmarks/formal-v3 --background
python scripts/public_benchmark.py report .public_benchmarks/formal-v3
python scripts/public_benchmark.py analyze .public_benchmarks/formal-v3 --output .public_benchmarks/formal-v3-analysis
# 中断后续跑：再次执行 campaign；已完成任务不会重新执行
python scripts/public_benchmark.py campaign .public_benchmarks/formal-v3 --background
# 停止派发并终止当前受控进程树
New-Item .public_benchmarks/formal-v3/cancel.request -ItemType File
```

运行的是 `source/` 内冻结副本；修改工作区不会改变当前实验。恢复时验证清单、源代码及所有输入指纹。原始大文件仍保存在数据目录；不放入 Git。清除 `cancel.request` 后，已标记取消的任务仍属于历史结果；重新实验应建立新清单。

若接口修正需要替换已冻结清单，使用 `prepare --prior-campaign <已结束清单目录>` 将其已消耗的总预算和各阶段预算计入新清单，不能重新获得 24 小时。调度器重启时也保守计入中断任务的耗时；未完成的旧尝试保留为中断，继续派发其余任务。

只替换运行代码或依赖、需要保留全部原抽样与任务时，使用 `refreeze <已结束目录> --output <新目录> --reason <原因>`。输入、注册表和任务不变，源代码重新冻结，累计预算继续扣除，旧记录不覆盖。该命令不会根据已有结果挑选样本。

## 数据及规则映射

|来源|读取及追溯|当前证据用途|
|---|---|---|
|ROADEF 2009|32 组；空白分隔，跳过 `%` 注释，`#` 行终止；航班按日期展开；明确处理 `+1/-1`；机尾内的 `#` 保留|研究模型求解、原生方案导出、官方检查器与成本门槛、历史参考上界|
|Delft 2020|HDF5 分块读取；按分类字典还原业务 ID；航班号、计划起飞、起讫机场联合匹配；原始字段及源行保留|12 小时静态派生模型、跨日期和规模能力；没有原 370 组编号或逐例答案|
|Delft 2019|工作簿分别以公式和缓存值读取；文件、表、行、Iteration、run、CV、发布者状态、公式错误保留|外部结果资料分析；不生成虚构输入或与 2020 的伪配对|

2019 的 `CV != 0`、错误公式或缺失公式缓存不进入可用参考结果。发布者 `101` 或其他求解状态都不是本项目的最优性证明。历史成绩中的 `INF`、缺失和非数值不会转成数值零；X01—X04 单独标记为未参与竞赛评分。A 组参考值读取下载的官方资格赛 HTML 页面，B/X 组读取官方成绩表，均保留表号、行号与文件哈希；本地资料合计覆盖 32 组。没有历史逐例值时保持缺失。

ROADEF 正延误的 `alt_flights` 是固定执行航班，保留固定时间和原飞机、禁止取消；`-1` 表示必须取消。Delft `Delay` 的正起飞延误在本研究中明确作为最早起飞界，保持原计划飞行时长；负延误原值保留，候选不提前。固定前缀用观测到达延误计算资源就绪时间。`AC Unavailable` 没有可验证的区间语义时，相关实例预检拒绝，绝不转成机场关闭。尾部空格的重复到达延误字段与真正的 `ARRIVAL_DELAY` 分别保留。

|规则|统一研究模型 v1|原规则比较边界|
|---|---|---|
|机组|显式关闭 CRM；`original_crew=null`，没有机组或机组候选|旧 AIR 正式入口仍要求机组；机组证据来自原回归集|
|飞机范围|完整选择机尾在窗口内的轮转；仅选活动机尾，没有补充闲置备机|不是原始全机队无限制恢复问题；未选航班保存在固定上下文|
|边界|固定前缀确定资源位置与最早就绪，固定后缀限制回接；`boundary_from_fixed_context` 明确允许实际边界不同于原计划首末段|与 ROADEF 按机型/配置的软位置惩罚不同；旧案例仍校验原轮转位置|
|换机|仅允许相同原始机型、座位配置和过站时间的飞机互换|比原规则更窄；实际候选空间决定结论范围|
|候选|30 分钟，最大延误 120 分钟；加入源扰动的关键时间边界|60/30/15 分钟是嵌套网格；不声称连续时间全局最优|
|机场容量|原始小时容量、容量扰动保留；研究子模型暂不施加这些限制|非原规则可行性认证；官方检查拒绝时不比较历史成绩|
|旅客|完整落在已选航班内的原始旅客组；整组选择、单舱容量|不支持原舱等拆分/降舱；跨边界和地面交通行程保留但不纳入优化|
|连接统计|Delft 原始连接按组合键匹配，保留窗口外标记|只作为连接影响评价资料，不是重建后的 OD 需求|
|维护、航班串、地面交通|原文保留；维护导致预检不支持，后两者暂未建模|官方检查及映射缺口阻止错误比较|
|成本|冻结的 `public_air_linear_v1` 抽象非负线性成本|不能代替含舱等、赔偿及负运营成本变化的 ROADEF 原目标|

正确性微例依原始字段能力筛选机尾，排除维护或语义不明的不可用事件；筛选种子为 0/17/42，排除原因写入候选策略。该筛选在正式算法结果出现前冻结。压力实例不使用此筛选，全部保留预检拒绝结果。上述模型差异是当前实现限制，不能解读为完整复现公开业务模型。

## 算法及证明

|入口算法|比较对象|证明边界|
|---|---|---|
|`air_bp`|v3 AIR Benders＋列生成＋分支定价|主线；保留定价、节点、割、上下界及原始核心诊断|
|`air_cg`|AIR Benders＋列生成|不能把某个资源 LP 收敛当作整体整数最优|
|`integrated_oracle`|独立 DFS 完整飞机路径池的联合整数模型|最多 12 个可调整航班；20 万路径/100 万枚举节点；超过上限拒绝完整性声明|
|`fixed_benders`|与 Oracle 相同完整列池的固定列分解|区分分解、隐式定价与整数搜索问题|
|`xma_joint_arc_flow`、`xma_joint_path_oracle`、`xma_benders_joint`、`xma_benders_cg_bp`|复用四路线驱动，注入与 AIR 相同的飞机子模型|不启用厦航旅客模型；不将两套 PRM 的差异当作算法差异|
|组件对拍|同一固定计划的全列 LP/CG、终止定价审计、全列整数模型/B&P|证据保存在组件任务中；没有观察到整数间隙时，不能声称验证了困难分支搜索|

AIR 使用原生 `HighsAdapter`，支持 LP/MIP、LP 对偶及 reduced cost、有限有效界、取消和状态合同。公开实验显式选择后端。厦航现有代数建模仍依赖 `gurobipy`，选择 HiGHS 时只使用其建模接口，优化交给 HiGHS，不进行许可证错误后的隐式切换。零变量模型的常数约束会独立检查，避免把 HiGHS 的 `Empty` 直接误判为可行。

厦航两条分解路线保留 v3 默认的资源 LP 主问题强化及其规模保护。关闭强化的早期开发运行只作为诊断，不能代表优化版性能。冻结副本的 Workbench 来源信息从清单读取，避免继承外层工作区后来提交的 HEAD。

独立方案审计重新计算覆盖、换机、资源连续性、时间、固定扰动、末端、旅客连接、容量和成本。最优结论必须同时满足审计通过、核心算法的最优终止和有限上下界闭合。零目标本身不构成证明。资源不可达的必要条件证书独立标记 `preprocessing_only`，不计为算法性能证据。

原规则导出保留完整原始问题及未调整上下文。官方程序返回码为零仍可能报告业务违规，因此必须检查全部 11 个报告存在且为空。只有这些检查通过、成本检查得到数值且映射没有未解决舱等问题，才生成历史上界差距。原始评分、分项输出和检查器二进制 SHA-256 单独保存。现阶段研究方案可能无法通过原规则检查，这是模型差异的实验结果。

## 实验清单、阶段门槛和证据

首批固定 6 个 ROADEF 微例和 6 个 Delft 日期微例、飞机＋旅客实例、两来源 20/50/100 班与三个选择种子、嵌套网格、重复及停止实验、全部 32 个 ROADEF 整例和 Delft 500 班/整窗口。目标规模与机尾闭包后的实际规模分别记录。性能任务预热一次、测量三次，求解器单线程。

预算按正确性 2 小时、对照 8 小时、稳定性 6 小时、压力 8 小时分配；最多 24 小时，开发/转换不计入。调度器采用安全的串行执行，正式重任务独占，进程树硬限制 6 GiB。时限、内存、规模和预算限制分别记录，不自动删需求或缩小候选。

**正确性阶段门槛要求所有已登记微例的八条路线都得到一致的完整最优/不可行证书，且回归、Workbench 和错误检查通过。** 未收敛不是通过；门槛不满足时，对照、稳定性及压力任务登记为 `blocked_by_correctness`。执行完清单只代表运行结束，`summary.json.acceptance_passed` 才表示本阶段验收。

|位置|内容|
|---|---|
|`manifest.json`、`registry.json`|冻结任务、软件环境、资源/预算、实际规模、输入/代码指纹|
|`source_references.json`、`reference-2019/`|历史参考及 2019 外部结果逐行资料|
|`conversion_failures.json`、各输入 `precheck_issues`|转换失败、能力缺口和排除原因|
|`jobs/<ID>/input.json`、`evidence.json`|完整求解输入、决策列、状态、界、证书、独立审计|
|`events.jsonl`、`checkpoint.json`、`worker.log`|搜索轨迹、经审计的可行方案检查点和原始日志|
|`native/checker-evidence.json`|11 项原规则检查、成本及可比性门槛|
|`workbench-state/`、`drafts/`|隔离的 v3 草稿、快照、运行、事件和方案制品|
|`runs.csv`、`summary.json`、`report.md`|包括失败/未执行任务的完整汇总及验收缺口|

调度器被迫终止任务时保留已审计的检查点；它不能因此变成最优解。重复运行允许最优决策不同，只比较目标、有效界、状态和时间。报告给出中位数、范围和标准差；只有同一问题、两路线各三次均审计且认证同一最优值，才计算相对直接联合路线的加速比。超时、未收敛和未执行不从登记分母删除。同日窗口及同网络变体按相关样本解释，样本不足不输出伪精确的置信区间。

汇总器检查内核的结构化求解器诊断；Gurobi `10010` 必须单列为许可证受限，即使旧内核将其包装成未收敛。`runs.csv` 同时保留原始分类与规范分类，原任务记录不被覆盖；报告记录汇总代码与原始状态的 SHA-256。
耗时描述统计按实例、算法、后端和阶段分别汇总。正确性阶段的单次认证耗时仅供诊断，不代替预热加三次测量的性能证据；未执行任务仍保留在注册任务统计分母中。

AIR 证据提供求解器接口构造、求解调用、完整枚举及独立审计分项计时；注册表另记规范化与候选生成时间，工作进程记录端到端与内存。厦航分项及原始 HDF 解析目前未逐项计时，不宜据此比较单独的解析/构模阶段。

`analyze` 只读取证据，不重新求解：按文件/工作表分别统计 2019 合法参考记录的成本、KPI 和不同定义的时间分布；对审计通过的我方方案复算取消、延误、换机、优化旅客与原始逐航段登机人数暴露。Delft 连接评价使用原始组合键、公开最小转机时间和冻结窗口外上下文；没有上下文或事件语义时标为未知。逐航段人数和连接人数不等于独立旅客人数，也不代表已经完成旅客重分配。分析文件记录自身代码、输入及证据指纹。

v3 复核时在数据准备页导入 `drafts/*.json`，保存校验、启动运行、查看恢复结果。公开候选和配置冻结；编辑展示数据会导致指纹校验失败。Workbench 使用相同的公开求解入口，旧 AIR 入口仍拒绝缺少机组的实例。

## 来源

- ROADEF [算例](https://roadef.org/challenge/2009/en/instances.php)、[检查器](https://roadef.org/challenge/2009/en/verif.php)、[历史成绩](https://roadef.org/challenge/2009/en/resultats.php)。本地下载的相应页面及文件哈希属于来源证据。
- TU Delft [2019 结果资料](https://research.tudelft.nl/en/datasets/aircraft-disruption-problem-case-study-results-datasets/)、[2020 案例输入](https://research.tudelft.nl/en/datasets/aircraft-disruption-management-case-studies/)。
- HiGHS [官方 Python 接口](https://ergo-code.github.io/HiGHS/dev/interfaces/python/example-py/)，实现同时核对本机 1.15.1 的实际接口。
