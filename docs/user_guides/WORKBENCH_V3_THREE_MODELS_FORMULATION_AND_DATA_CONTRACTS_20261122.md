# Workbench v3 三类恢复模型：数学表述与固定数据合同

整理日期：2026-11-22。本文承接[技术路线、数据与数学模型全景说明](WORKBENCH_V3_TECHNICAL_ROUTES_DATA_AND_MODELS_20261114.md)第 4—6 节，按当前源码核对，集中说明原始 AIR、厦航业务模型和公开基准研究模型。核对时 Git HEAD 为 `33ab4c9ee09dd4c2485fff36fae3e45d73ffcf1f`；工作区存在未提交变更，故该提交号不能单独代表本次核对的全部文件。

本文的公式是**当前实现的数学归纳**，不是对原论文、竞赛全部规则或真实航司全部业务的复现声明。依据为本地源码、配置和冻结输入；本次未重新求解，亦未重新核验外部文献。文末给出可追溯的源码入口。

## 1. 模型边界与共同符号

### 1.1 三类模型的根本差异

| 维度 | 原始 AIR | 厦航业务模型 | 公开基准研究模型 |
|---|---|---|---|
| 优化对象 | 航班、飞机、聚合机组、旅客组 | 航班、飞机、航段人数与改签 | 飞机；可选整组旅客 |
| 旅客决策单位 | 不可拆分的 OD 组 | 可拆分的整数人数；无完整 OD 需求 | ROADEF 原行程组，不可拆分 |
| 座位容量 | 候选上的外生剩余容量 | 选定机尾的物理座位 | 相同座位配置换机条件下的固定容量 |
| 飞机终点 | 逐机尾硬终点 | 机型—机场的机队数量平衡 | 逐机尾硬终点，包含窗口外回接 |
| 机组与维修 | 有聚合机组；有简化维修语义 | 二者显式关闭 | 机组关闭；不支持的维修输入拒绝 |
| 目标单位 | 抽象研究成本 | 天池分数或独立的线性研究成本 | `public_air_linear_v1` 抽象成本 |
| 结论适用范围 | 给定候选与资源合法性合同 | 已支持动作、人数账本与有限时刻候选 | 冻结转换后的研究问题 |

**同一工作台不等于同一数学问题。** 更换求解算法或求解器通常不改变问题；改变旅客粒度、候选时刻、飞机交换范围、边界或成本系数，则可能改变问题。

### 1.2 共同符号与单位

以下符号在全文保持含义；某模型没有的实体集合取空集。

| 符号 | 定义 |
|---|---|
| \(\mathcal F,\mathcal A,\mathcal K,\mathcal G,\mathcal V\) | 收入航班、飞机机尾、聚合机组、旅客组和机场的集合；索引分别为 \(f,a,k,g,v\) |
| \(\mathcal O_f^+,\mathcal O_f^-\) | 航班 \(f\) 的执行候选和取消候选；\(\mathcal O_f=\mathcal O_f^+\cup\mathcal O_f^-\)，\(\mathcal O^+=\bigcup_f\mathcal O_f^+\)，\(\mathcal O=\bigcup_f\mathcal O_f\) |
| \(f(o)\) | 收入航班候选 \(o\) 所属的基准航班 |
| \(x_o\) | 二元变量：选中候选 \(o\) 时为 1 |
| \(c_f=\sum_{o\in\mathcal O_f^-}x_o\)，\(e_f=1-c_f\) | 航班取消、执行指示；二者是派生量，不必另设变量 |
| \(\bar t_f^{\rm dep},\bar t_f^{\rm arr}\) | 航班 \(f\) 原计划起飞、到达时刻 |
| \(t_o^{\rm dep},t_o^{\rm arr},h_o,\delta_o\) | 执行候选的起飞、到达时刻，航段时间和起飞延误；\(h_o=t_o^{\rm arr}-t_o^{\rm dep}\)，\(\delta_o=t_o^{\rm dep}-\bar t_{f(o)}^{\rm dep}\) |
| \(\operatorname{org}(o),\operatorname{dst}(o)\) | 候选的起点、终点；对原航班用 \(\operatorname{org}(f),\operatorname{dst}(f)\) |
| \(a_f^0,k_f^0,E_f\) | 原计划机尾、原聚合机组及原机型；公开模型无 \(k_f^0\) |
| \(E_a,v_a^0,v_a^T\) | 飞机机型、初始机场、合同要求的终点；厦航的 \(v_a^T\) 是原终点，只用于机队数量统计 |
| \(n_g\) | 旅客组 \(g\) 的人数，仅用于整组模型 |
| \(\mathbf1\{B\}\)，\([z]_+\) | 条件 \(B\) 成立时为 1、否则为 0；\([z]_+=\max\{0,z\}\) |
| \(\mathbb B,\mathbb Z_+\) | \(\mathbb B=\{0,1\}\)；\(\mathbb Z_+=\{0,1,2,\ldots\}\) |

公式中的时刻统一理解为相对某个**固定参考时刻**的分钟数，时间差因而以分钟计；JSON 保存带时区的时间戳。厦航采用北京时间；公开输入采用 UTC。AIR 数据要求时区明确，工作台按 UTC 展示。取消候选不具有实际起降行为；厦航内部虽保留原时刻作为占位字段，也不能将其计为真实起降。未另写集合的航班／飞机求和分别遍历 \(\mathcal F/\mathcal A\)；“指示”或“表示是否”的参数均取 0 或 1。

## 2. 通用的固定基础数据合同

### 2.1 “固定”指一次求解中固定

合同是具有明确字段、单位、引用和版本的输入约定。这里的“固定参数”不是所有案例共用同一常数，而是**运行开始前冻结、运行中不可由优化器任意改变**的数据。原计划机尾是参数，恢复机尾是决策；原旅客人数是参数，改签人数是决策。

| 层次 | 固定内容 | 作用 |
|---|---|---|
| 原始证据 | 来源文件、文件 SHA-256、原表／原行、原业务 ID | 说明数据来自何处 |
| 基础实例 | 原时刻、机场、机型、原分配、人数、资源初始状态 | 定义受恢复的对象 |
| 规则与边界 | 时间窗、禁飞、关闭、过站／中转、资源终点、固定上下文 | 定义合法性 |
| 候选域 | 时刻网格、最大延误、允许动作、已给定旅客行程、换机范围 | 定义可选择的方案空间 |
| 评价口径 | 目标版本、系数、单位、容量语义 | 定义何为更优及如何审计 |
| 运行控制 | 算法、后端、时限、节点／迭代限额、数值容差 | 控制搜索与终止；不应冒充业务规则 |

候选生成参数虽然名为“配置”，仍可能改变可行域。列生成增加的是既定航班候选组成的资源路径，不会自动补出任意连续起飞时刻。数学上的连续时间业务问题与有限候选问题须分别表述。

### 2.2 共用对象与最小一致性要求

AIR 与公开转换共用 `Scenario`、`RecoveryColumns`、容量与成本对象；厦航采用独立 `XmaDataset`，仅复用工作台外壳。下表是**概念共同项**，不是要求三者使用同一个 JSON 结构。

| 对象 | 必须说明的信息 | 一致性要求 |
|---|---|---|
| 航班 | ID、OD、原起降时刻、航段时间、原机尾／机型、可调整上界 | ID 唯一，资源与机场引用存在，时间先后正确 |
| 飞机 | 机尾、机型、初始位置、原轮转、终点与可用边界 | 原轮转可追溯；终点是逐机尾还是机队平衡必须明示 |
| 旅客 | 整组 OD 与原行程，或航段人数与连接关系 | 不将航段人数总和解释为独立旅客总数 |
| 时空限制 | 时间戳、区间端点、适用机场／资源、限制数值 | 开区间、闭区间、半开区间不可混用 |
| 候选 | 所属航班、执行／取消、实际时刻与变更类型 | 候选 ID 唯一；取消与执行结构分离 |
| 容量 | 起降架次、地面飞机数、旅客座位及各自单位 | 三种容量互不替代；缺失容量不能默认为现实无限容量 |
| 成本 | profile、系数、单位、计费对象、版本 | 每项成本只计入规定模块；分数与抽象成本不相加 |

已解析的基础 schema 通常拒绝未声明字段；引用完整性、跨对象一致性还须由业务校验器检查。通过数据校验仅表示输入就绪，不保证存在可行方案。

工作台进一步保存 `DraftDocument → SnapshotRecord → RunRecord`：草稿可修改，输入快照和运行证据按内容哈希保存。`draft_hash`、编译后输入哈希、研究问题签名与结果工件哈希承担不同职责，不宜互相替代。

## 3. 原始 AIR：四模块联合恢复模型

### 3.1 专有数据与候选合法性合同

AIR 的基础对象为 `Scenario`。其恢复窗口 `recovery_window.start_time/end_time` 规定候选时间边界；飞机、机组、旅客与机场时段之外，还保存 `disruptions` 扰动描述。

| 对象 | 固定字段及其业务语义 |
|---|---|
| 航班 `Flight` | `flight_id, origin, destination, sched_dep, sched_arr, duration`；`original_aircraft, original_equipment, original_crew`；`max_delay`；`strategic_flag, market_flag, min_seats`；可选 `earliest_departure, fixed_delay, cancel_required` |
| 飞机 `Aircraft` | `tail_id, equipment_type, initial_station_at_t, required_station_at_T_end, original_rotation`；`maintenance_required, maintenance_stations`；可选 `ready_at, available_until, unavailable, boundary_from_fixed_context` |
| 机组 `Crew` | `crew_id, rating, start_station_at_t, required_station_at_T_end, original_duties, original_pairing`；原 duties 展平后须与 pairing 一致 |
| 旅客 `PassengerCommodity` | `pax_group_id, count, origin, destination, original_departure, scheduled_arrival, original_itinerary` |
| 机场与时段 | 机场 `airport_id, name`；时段 `airport, start_time, end_time, arr_capacity, dep_capacity, gate_capacity, curfew_flag, weather_restrictions` |
| 扰动与有效容量 | 旧 `Disruption` 保存 `airport, start_time, end_time, capacity_change, restriction_type`；工作台类型化规则编译为有效容量，避免与已生效容量重复扣减 |

`min_seats` 是市场保留代理的参数，不是飞机座位。`Flight` 要求起讫机场不同，航段时间等于原起降差的整数分钟；这与厦航保留同机场记录的合同不同。

设 \(\mathcal S_a\) 为机尾 \(a\) 的合法飞机串集合，\(\mathcal P_k\) 为机组 \(k\) 的合法执勤串集合，\(\mathcal I_g\) 为组 \(g\) 的合法旅客行程集合。飞机串可包含显式调机候选，其集合记为 \(\mathcal O^{\rm ferry}\)；调机没有基准收入航班，其起降时刻和 \(h_o\) 沿用前述实际时刻与航段时间定义。旅客行程含“未服务”方案。

合法性分两层执行：基础列校验检查结构和引用，正式资源生成／定价按相应配置检查完整路径规则。

| 候选集合 | 进入集合前须满足的条件 | 当前默认参数／边界 |
|---|---|---|
| \(\mathcal O_f\) | 执行候选的时刻、延误和变更标记自洽；取消候选无实际旅行字段 | 通用工作台默认复用候选；重新生成时步长 10 分钟、最大延误 60 分钟，再受 `max_delay` 限制；不额外保证补齐非整除的最大延误点 |
| \(\mathcal S_a\) | 所属机尾、机型、起终点、地点连续、时间连续、不重复原航班、窗口及可用边界；硬关闭／宵禁资格检查；简化维修满足 | 最短过站默认 15 分钟，测试机型 `E1` 为 0；可用边界与不可用区间有值时生效；允许合法闲置串 |
| \(\mathcal P_k\) | 所属机组、执飞机型资质、初终点、同机场连接、先后顺序、重复航班限制、执勤跨度、置位上限 | 单 duty；最短连接 0、跨度最多 480 分钟、deadhead 最多 1 段；允许置位和合法闲置 |
| \(\mathcal I_g\) | 原 OD、首段不早于原出发要求、空间连续、MCT、恢复窗口、到达延误、航段上限与未服务结构 | MCT 默认 0、最多 3 航段、允许未服务、不生成地面交通 |

维修的当前含义是“需要维修的机尾选中维修满足串，并在允许维修站结束”；没有维修工时、任务排序、机库容量或维修期间不可用的完整排程。单 duty 的 480 分钟及零 MCT 均为测试设定，不能作为真实航司法规或校准参数。

### 3.2 决策变量与目标函数

除 \(x_o\) 外，定义 \(y_{as},z_{kp},w_{gi}\in\mathbb B\)：分别选择飞机串 \(s\in\mathcal S_a\)、机组串 \(p\in\mathcal P_k\)、旅客行程 \(i\in\mathcal I_g\)。这三个变量与代码 `y[string_id]`、`z[pairing_id]`、`w[itinerary_id]` 对应；所有者已编码在候选中。

定义包含关系 \(B^A_{o,as}\)、\(B^{C,\rm op}_{o,kp}\)、\(B^{C,\rm dh}_{o,kp}\)、\(B^P_{o,gi}\in\mathbb B\)，依次表示飞机串包含候选、机组串执飞候选、机组串在候选上置位、旅客行程使用候选。定义 \(U_{gi}\) 为未服务行程指示，\(\Delta^{\rm arr}_{gi}\) 为已运输行程最终到达相对组原到达时刻的非负延误；未服务时该延误贡献按 0 计。

记 \(\chi_o^{\rm org},\chi_o^{\rm dst}\) 为显式起点／终点变更指示。下表定义全部成本系数及当前基准值；单位均为抽象成本单位，记作 CU。

| 符号 | 配置键 | 基准值与计费单位 |
|---|---|---|
| \(\alpha_d\) | `flight_delay_per_minute` | 1 CU／航班分钟 |
| \(\alpha_c\) | `flight_cancellation` | 25,000 CU／取消航班 |
| \(\alpha_o,\alpha_v\) | `origin_change, destination_change` | 各 5,000 CU／变更航班 |
| \(\alpha_a\) | `aircraft_reassignment` | 0 CU／换机航班 |
| \(\alpha_\phi\) | `ferry_per_minute` | 5 CU／调机分钟 |
| \(\alpha_k\) | `crew_reassignment` | 0 CU／换机组航班 |
| \(\alpha_h\) | `deadhead_per_minute` | 5 CU／置位分钟 |
| \(\alpha_p\) | `passenger_delay_per_pax_minute` | 10 CU／人分钟 |
| \(\alpha_u\) | `unserved_passenger` | 2,500 CU／未服务旅客 |

目标分为四个计费主体：

\[
\min Z_{\rm AIR}=\sum_{o\in\mathcal O}C_o^Sx_o
+\sum_{a\in\mathcal A}\sum_{s\in\mathcal S_a}C_{as}^Ay_{as}
+\sum_{k\in\mathcal K}\sum_{p\in\mathcal P_k}C_{kp}^Cz_{kp}
+\sum_{g\in\mathcal G}\sum_{i\in\mathcal I_g}C_{gi}^Pw_{gi}. \tag{A1}
\]

各候选的固定成本定义为：

\[
C_o^S=\begin{cases}\alpha_c,&o\in\mathcal O_f^-\text{，某个 }f,\\
\alpha_d\delta_o+\alpha_o\chi_o^{\rm org}+\alpha_v\chi_o^{\rm dst},&o\in\mathcal O^+;\end{cases} \tag{A2}
\]
\[
C_{as}^A=\alpha_a\sum_{o\in\mathcal O^+}B^A_{o,as}\mathbf1\{a\ne a_{f(o)}^0\}
+\alpha_\phi\sum_{o\in\mathcal O^{\rm ferry}}h_oB^A_{o,as}, \tag{A3}
\]
\[
C_{kp}^C=\alpha_k\sum_{o\in\mathcal O^+}B^{C,\rm op}_{o,kp}\mathbf1\{k\ne k_{f(o)}^0\}
+\alpha_h\sum_{o\in\mathcal O^+}h_oB^{C,\rm dh}_{o,kp},\qquad
C_{gi}^P=n_g\bigl[\alpha_p(1-U_{gi})\Delta^{\rm arr}_{gi}+\alpha_uU_{gi}\bigr]. \tag{A4}
\]

调机成本由 ARM 计，置位成本由 CRM 计；不再计入 SRM。候选 `cost_components` 只是附带信息，正式成本函数按规范输入重算。基准文件为 `phase2_test_costs_v1.json`，profile 为 `phase2_test_v1`；override 只能改变非负有限系数值，不能改变计费单位和归属。

### 3.3 选择、覆盖与旅客耦合约束

\[
\sum_{o\in\mathcal O_f}x_o=1\ (f\in\mathcal F),\quad
\sum_{s\in\mathcal S_a}y_{as}=1\ (a\in\mathcal A),\quad
\sum_{p\in\mathcal P_k}z_{kp}=1\ (k\in\mathcal K),\quad
\sum_{i\in\mathcal I_g}w_{gi}=1\ (g\in\mathcal G). \tag{A5}
\]

每个收入执行候选恰由一架飞机和一个聚合机组覆盖：

\[
\sum_{a\in\mathcal A}\sum_{s\in\mathcal S_a}B^A_{o,as}y_{as}=x_o,\qquad
\sum_{k\in\mathcal K}\sum_{p\in\mathcal P_k}B^{C,\rm op}_{o,kp}z_{kp}=x_o
\quad(o\in\mathcal O^+). \tag{A6}
\]

置位和旅客行程只能引用已执行候选：

\[
z_{kp}\le x_o\quad\text{若 }B^{C,\rm dh}_{o,kp}=1,\qquad
w_{gi}\le x_o\quad\text{若 }B^P_{o,gi}=1. \tag{A7}
\]

令 \(Q_o\) 为 `seat_capacity_by_option_id[o]` 给出的剩余座位，则

\[
\sum_{g\in\mathcal G}\sum_{i\in\mathcal I_g}n_gB^P_{o,gi}w_{gi}\le Q_ox_o
\quad(o\in\mathcal O^+\text{，且被旅客候选引用}). \tag{A8}
\]

\(Q_o\) 不随选定机尾变化，deadhead 机组也未自动计入该座位负载。因此，式（A7）的置位可用性不等于“机组置位占座已完整建模”。

### 3.4 服务保留与机场约束

定义 \(\mathcal F^{\rm keep}\) 为战略航班及同时满足 `market_flag=true, min_seats>0` 的航班集合，则

\[
\sum_{o\in\mathcal O_f^+}x_o=1\quad(f\in\mathcal F^{\rm keep}). \tag{A9}
\]

市场代理只保证执行，不形成真实的最小座位供给约束。

令 \(q\in\mathcal Q\) 为机场时段，机场为 \(v_q\)，区间为 \([l_q,r_q)\)，起降上限为 \(D_q,A_q\)。定义 \(d_{qo}=\mathbf1\{\operatorname{org}(o)=v_q,l_q\le t_o^{\rm dep}<r_q\}\)、\(a_{qo}=\mathbf1\{\operatorname{dst}(o)=v_q,l_q\le t_o^{\rm arr}<r_q\}\)，则

\[
\sum_{o\in\mathcal O^+}d_{qo}x_o\le D_q,\qquad
\sum_{o\in\mathcal O^+}a_{qo}x_o\le A_q. \tag{A10}
\]

令 \(G_v^0\) 为机场初始在地飞机数，\(G_{vt}^{\max}\) 为检查时刻 \(t\) 的地面上限，\(\mathcal T_v\) 为窗口边界、时段边界和所有候选起降事件组成的检查时刻集合，则

\[
0\le G_v^0+\sum_{o\in\mathcal O^+}\left[
\mathbf1\{\operatorname{dst}(o)=v,t_o^{\rm arr}\le t\}
-\mathbf1\{\operatorname{org}(o)=v,t_o^{\rm dep}\le t\}\right]x_o
\le G_{vt}^{\max}\quad(t\in\mathcal T_v). \tag{A11}
\]

这是聚合地面库存代理，不是逐机尾机位排程；它不计调机运动。恢复终点容量优先取终止于窗口末端的时段；空档或终点没有唯一可解释容量时，构造器拒绝歧义输入。

### 3.5 合法路径约束与源码覆盖

式（A1）—（A11）须与候选集合的定义同时使用。对飞机相邻执行段 \(o,o'\)，要求终点等于下一起点、\(t_{o'}^{\rm dep}\ge t_o^{\rm arr}+\tau_a\)，其中 \(\tau_a\) 是该机型最短过站；机组用最短连接参数替代 \(\tau_a\)，并限制首段起飞至末段到达的跨度；旅客用 MCT 并检查原 OD 与首段出发下界。终点、归属、资质、维修等规则通过合法集合排除非法列，不必全部重复写成独立行。

注册表的 20 项约束按短 ID 对应如下；联合链接另有 5 项，不能把 20 项理解为全部联合方程数量。

| 注册表短 ID | 覆盖内容 |
|---|---|
| SRM-C01—C06 | 每班唯一候选、战略保留、到达容量、出发容量、地面库存代理、市场保留代理 |
| ARM-C01—C05 | 每机一串、执行覆盖、硬终点、简化维修、飞机串合法性 |
| CRM-C01—C05 | 每组一串、执飞覆盖、非执行航班禁执飞／置位、机组串合法性、终点与归属 |
| PRM-C01—C04 | 每组一行程、与执行日程一致、剩余座位、行程合法性 |
| INTEGRATED-L01—L05 | 式（A6）的两项、式（A7）的两项、式（A8） |

原 AIR 正式服务要求全范围 `scope=None`。Scope 组件实验若开启，则范围外实体固定到唯一原计划候选，完整约束仍保留；它不是删除范围外实体的模型。

### 3.6 输入与输出合同

正式 `SolveRequest` 使用 `schema_version=1.0.0`，包含 `scenario, recovery_columns, capacity_profile, cost_profile_id, cost_overrides, algorithm, profile_ids`。算法固定为 `benders_branch_and_price_v1`；六类 profile 分别控制飞机合法性、机组合法性、飞机 CG、机组 CG、Benders-CG 与 B&P。旅客生成另有 Phase 7 配置。

正式入口接收航班候选和必要旅客行程，**拒绝预生成飞机串与机组串**，在算法内生成资源列；固定列 Oracle 则接收显式列池。二者不能混用输入合同。存在旅客时必须提供有效剩余容量，不能根据 `min_seats` 猜测。

输出 `RecoveredResult` 包含 `selected` 四类候选 ID、原计划与恢复航班、飞机／机组／旅客 outcomes、恢复动作、四模块成本、指标、诊断和版本元数据。未收敛但具有经独立审计的完整方案时，可以保留方案与上界；这不构成最优性证明。

## 4. 厦航：航班、飞机与人数账本的业务联合模型

### 4.1 固定数据合同与数据使用范围

`XmaDataset(schema_version=xma-1.0)` 不等同于 AIR `Scenario`。原工作簿为 `data/厦航-天池比赛数据/data/XMAE_data.xlsx`；导入器保存文件哈希、工作表、行号及 `source_tables` 原始内容。

| 来源／对象 | 规范字段或参数 | 模型中的实际用途 |
|---|---|---|
| 航班表 `XmaFlight` | `flight_id, date, flight_no, domestic, origin, destination, sched_dep, sched_arr, original_aircraft, equipment, passengers, through_passengers, seats, importance, source` | 原计划、机型、人数、原座位与评分重要性；允许保留同机场航段 |
| 派生飞机 `XmaAircraft` | `tail_id, equipment, seats, initial_station, original_terminal, original_rotation` | 同机尾的机型和座位须一致；物理座位来自实际分配飞机 |
| 航线—飞机限制 | `route_prohibitions` 中的 OD—机尾三元组 | 禁止对应机尾执行该航线 |
| 机场关闭 | `airport, close_minutes, open_minutes, effective_date, expiration_date, source` | 有效日期内的每日起降时刻过滤 |
| 台风场景 | `airport, kind, start, end, parking_limit, flight_id, tail_id, source` | 起降禁行或特殊停机限制；指定单航班／机尾的场景当前拒绝 |
| 飞行时间表 | `travel_minutes`，机型—OD 键 | 原表保留，重复键后行覆盖；当前同机型、不改航路模型仍保持原计划航段时间，不据此重新计算飞行时间 |
| 机场表 | `airports`：机场到国内／国际属性的映射 | 引用验证与原资料保留；不自动产生正常机场架次上限 |
| 中转表 `Transfer` | `inbound, outbound, minimum_minutes, count, source` | 连接失败判定与人数账本；不是完整 OD 路径 |
| 联程与短过站 | `connected_pairs, original_turn_minutes` | 同一原机尾相邻、同日同航班号识别联程；保存原相邻过站例外 |
| 来源与子集 | `dataset_id, source_sha256, timezone, notes, subset_selection, boundary_flights` | 选择过程与跨子集进港边界可追溯 |
| 特殊桥接字段 | `public_rules` | 仅用于公开问题复用厦航算法驱动；存在时进入另一套公开模型构造器，不套用本节人数方程 |

原始本地数据为 2,364 班、142 架飞机；“普通人数”和“联程人数”均为航段观察量。导入校验要求：原轮转恰覆盖每班一次且时空连续；联程对不重叠、人数一致；中转引用合法且不重复；对每个航班，中转进出人数之和不超过普通人数与扣除联程后的座位二者的较小值。原超售本身可以存在，由后续溢出账本处理。

| 固定规则 | 数值或精确定义 |
|---|---|
| 可调整集合 \(\mathcal F^{\rm adj}\) | 原计划起飞位于北京时间 `[2017-05-06 06:00, 2017-05-09 00:00]`，包含两端；一般实例以 `adjustment_start/end` 为准 |
| 最大延误 | 国内 1,440 分钟，国际 2,160 分钟，再与请求 `maximum_delay_minutes`、可选 `recovery_end` 共同取界 |
| 默认候选网格 | `delay_step_minutes=30`；默认 `maximum_delay_minutes=1440`；`None` 表示不再用该请求字段缩小国内／国际上限 |
| 候选补点 | 除均匀网格外加入最大延误点、机场关闭及台风禁起降边界；执行候选保持原航段时间 |
| 窗口外航班 | 原时刻、原机尾、执行状态和送出改签冻结；仍可作为改签接收航班 |
| 普通过站 | 50 分钟；原相邻航班 \((f,j)\) 允许 \(\tau_{fj}=\min\{50,\bar\tau_{fj}\}\)，其中 \(\bar\tau_{fj}\) 是保存的原过站分钟；非原相邻对取 50 |
| 关闭端点 | 有效日期 `[effective_date, expiration_date)`；每日关闭用严格条件 `close_minutes < 分钟时刻 < open_minutes`；台风禁起降用 `(start,end)`；不额外赋予跨午夜关闭的新解释 |
| 特殊起降容量 | 受台风起降影响的机场，两个运动窗口内起降合计每 5 分钟最多 2 次；窗口含两端，分桶均锚定第一窗口起点 |
| 两个运动窗口 | 北京时间 `2017-05-06 15:00—16:00`、`2017-05-07 17:00—19:00`；来自导入器对源评估规则的实现，不是工作簿单元格 |
| 恢复截止 | `recovery_end` 限制实际到达，**不同于**按原计划起飞定义的可调整窗口终点 |

当前不生成提前、跨机型、调机、改 OD 或联程拉直方案；机组和维修分别为 `crew_enabled=false, maintenance_enabled=false`。不存在的正常机场容量、机组和维修数据不得补造。

### 4.2 飞机变量、资源流与联程约束

定义 \(u_{ao}\in\mathbb B\) 表示机尾 \(a\) 执行候选 \(o\)。候选仅对同机型、非禁飞且满足窗口外固定轮转边界的机尾建立分配对；若指定 `tail_pool_size`，还须属于相应同机型交换池。以 \(\mathcal D\subseteq\mathcal A\times\mathcal O^+\) 表示这些合法分配对，未建立的 \(u_{ao}\) 约定为 0。基本覆盖为

\[
\sum_{o\in\mathcal O_f}x_o=1,\qquad
\sum_{a:(a,o)\in\mathcal D}u_{ao}=x_o\quad(o\in\mathcal O^+). \tag{X1}
\]

直接模型以机场事件网络表示每架飞机的单位流。记 \(\mathcal N_a,\mathcal E_a\) 为其节点与弧集合，\(\nu_a^0,\nu_a^T\) 为源节点和汇节点，\(q_{a\ell}\in\mathbb B\) 为弧 \(\ell\in\mathcal E_a\) 的流量；\(\operatorname{out}_a(\nu),\operatorname{in}_a(\nu)\) 为节点出入弧集合。则其等价守恒形式为

\[
\sum_{\ell\in\operatorname{out}_a(\nu)}q_{a\ell}
-\sum_{\ell\in\operatorname{in}_a(\nu)}q_{a\ell}
=\begin{cases}1,&\nu=\nu_a^0,\\-1,&\nu=\nu_a^T,\\0,&\text{其他节点}.\end{cases} \tag{X2}
\]

执行候选入口、落地出口的流量均等于 \(u_{ao}\)。代码中的 `board, ground, release, arc:END, short_enter, short_wait, short_exit` 是该流的分解：普通落地后 50 分钟进入公共机场时间线；原短过站和联程使用只能通向指定后段的专用通道。当前没有源到汇的纯闲置路径，**每架飞机须至少执行一段**。

为紧凑描述终点、联程和停机，可使用等价的完整路径表达；这不意味着直接算法实际枚举路径。定义 \(\mathcal R_a\) 为机尾 \(a\) 的合法非空路径集合，\(\lambda_{a\rho}\in\mathbb B\) 选择路径 \(\rho\)，\(H_{o,a\rho}\) 表示该路径包含候选 \(o\)，则

\[
\sum_{\rho\in\mathcal R_a}\lambda_{a\rho}=1,\qquad
u_{ao}=\sum_{\rho\in\mathcal R_a}H_{o,a\rho}\lambda_{a\rho}. \tag{X3}
\]

令 \(T_{Ev}^0=\sum_a\mathbf1\{E_a=E,v_a^T=v\}\) 为原机队在机型 \(E\)、机场 \(v\) 的终点数，\(D_{a\rho v}\) 表示路径在机场 \(v\) 结束，则

\[
\sum_{a:E_a=E}\sum_{\rho\in\mathcal R_a}D_{a\rho v}\lambda_{a\rho}=T_{Ev}^0. \tag{X4}
\]

这里的 \(E\) 遍历数据中的机型。式（X4）允许同机型飞机交换终点；它不要求每架机尾回到自己的原终点。

令 \(\mathcal C\) 为有序联程对集合；\(J_{a\rho,fj}\) 表示 \(f,j\) 在路径中直接相邻，则

\[
\sum_a\sum_{\rho\in\mathcal R_a}J_{a\rho,fj}\lambda_{a\rho}\ge e_f+e_j-1
\quad((f,j)\in\mathcal C). \tag{X5}
\]

若任一段不在 \(\mathcal F^{\rm adj}\)，该对两段均禁止取消。两段都执行时，式（X5）强制同机尾、直接衔接；不能仅检查起降时间而允许中间插入其他航班。

### 4.3 起降与停机约束

记 \(\mathcal B\) 为按源码形成的“机场—5 分钟桶”集合，\(m_{bo}\) 为候选 \(o\) 在桶 \(b\) 的起降计数系数，包含适用运动窗口的计数。则

\[
\sum_{o\in\mathcal O^+}m_{bo}x_o\le L^{\rm mov}\quad(b\in\mathcal B),\qquad L^{\rm mov}=2. \tag{X6}
\]

桶号为相应起降时刻距**第一运动窗口起点**的分钟差除以桶宽后的向下取整；不能对第二窗口重新从 0 编号。

记 \(\mathcal H_v\) 为机场 \(v\) 的停机场景集合，每个场景 \(s\) 有 \([l_s,r_s]\) 和上限 \(L_s^{\rm park}\)。定义 \(P_{a\rho s}\) 为路径中满足“前段到达不晚于 \(l_s\)、相邻后段起飞不早于 \(r_s\)、衔接机场为 \(v\)”的相邻航班对数量。则当前约束为

\[
\sum_a\sum_{\rho\in\mathcal R_a}\sum_{s\in\mathcal H_v}P_{a\rho s}\lambda_{a\rho}
\le\min_{s\in\mathcal H_v}L_s^{\rm park}\quad(\mathcal H_v\ne\varnothing). \tag{X7}
\]

它累加同机场各场景贡献；只计算被一对相邻执行航班完整包住的停车，初始或最终停车不计。直接模型用 `park_pre, park_future, park_no_departure, park_span` 二元变量实现相同判定。该规则不同于 AIR 的瞬时聚合地面库存，也不同于一般逐时停机容量。

### 4.4 中转、联程和超售的人数账本

定义 \(P_f,T_f\) 为普通、联程旅客人数，\(S_a\) 为机尾物理座位，\(S_f=\sum_{o\in\mathcal O_f^+}\sum_aS_au_{ao}\) 为选定航班供给。\(S_f\) 随恢复机尾变化，取消时为 0。

中转记录集合记为 \(\mathcal L\)，每条 \((i,j)\in\mathcal L\) 的进出港航班、人数与最短中转分别为 \(i,j,n_{ij},m_{ij}\)。子集外进港航班可由 `boundary_flights` 固定在原计划。定义 \(t_f^{\rm dep}=\sum_{o\in\mathcal O_f}t_o^{\rm dep}x_o\)、\(t_f^{\rm arr}=\sum_{o\in\mathcal O_f}t_o^{\rm arr}x_o\)；在这两个内部表达式中，取消候选采用原时刻占位。定义 \(\eta_{ij}\in\mathbb B\) 表示“进港未取消，但中转时间不足”。由于时刻按分钟对齐，

\[
\eta_{ij}=\mathbf1\{c_i=0,\ t_j^{\rm dep}-t_i^{\rm arr}-m_{ij}\le-1\}. \tag{X8}
\]

实际模型以足够大的分钟上界 \(M_t\) 实现：令 \(g_{ij}=t_j^{\rm dep}-t_i^{\rm arr}-m_{ij}\)，约束为 \(\eta_{ij}\le1-c_i\)、\(g_{ij}\ge-M_t(\eta_{ij}+c_i)\)、\(g_{ij}\le-1+M_t(1-\eta_{ij}+c_i)\)。\(M_t\) 从候选时间跨度及最大中转要求计算，并对边界航班扩展，不是任意业务惩罚。

定义三个派生人数：

\[
C_f^{\rm in}=\sum_{(i,f)\in\mathcal L}n_{if}c_i,\qquad
F_f^{\rm in}=\sum_{(i,f)\in\mathcal L}n_{if}\eta_{if},\qquad
I_f^{\rm in}=\sum_{(i,f)\in\mathcal L}n_{if}. \tag{X9}
\]

它们分别是进港取消人数、中转失败人数和原中转进港人数。令 \(p(f)\) 为联程搭档，\(B_f^{\rm th}=T_fc_{p(f)}\) 为搭档取消导致的联程损失；没有搭档时取 0。令 \(\gamma_f=1\) 表示联程第一段，否则为 0。对执行航班，定义可留乘账面人数 \(N_f\)、溢出人数 \(O_f\)、留乘人数 \(R_f\)：

\[
N_f=\begin{cases}P_f+T_f-C_f^{\rm in}-F_f^{\rm in}-B_f^{\rm th},&f\in\mathcal F^{\rm adj},\\
P_f+T_f,&f\notin\mathcal F^{\rm adj},\end{cases}\qquad
O_f=[N_f-S_f]_+,\quad R_f=N_f-O_f. \tag{X10}
\]

取消航班另取 \(O_f=R_f=0\)。待恢复／未服务计费基数 \(L_f\) 为

\[
L_f=\begin{cases}
P_f+\gamma_fT_f,&c_f=1,\\
C_f^{\rm in}+F_f^{\rm in}+O_f+\gamma_fB_f^{\rm th},&c_f=0,\ f\in\mathcal F^{\rm adj},\\
O_f,&c_f=0,\ f\notin\mathcal F^{\rm adj}.
\end{cases} \tag{X11}
\]

\(O_f,R_f,L_f\in\mathbb Z_+\)。式（X10）—（X11）是源评估规则的分支账本，不是去重 OD 需求守恒；联程损失只在规定的第一段计入相关损失基数。

模型用整数变量和 `overflow_flag` 二元变量线性化最大值、执行／取消分支。人数上界统一取
\(M=2\max_f(P_f+T_f)+\max_aS_a+1\)。另设 \(\pi_o\in\mathbb Z_+\) 对应 `resident_part[o]`，满足 \(0\le\pi_o\le Mx_o\)、\(\sum_{o\in\mathcal O_f^+}\pi_o=R_f\)，从而将“选定时刻下的留乘人数成本”写成线性项。

### 4.5 改签变量与全部送出、接收限制

定义合法改签对集合 \(\mathcal E^{\rm rb}\)：源航班 \(f\in\mathcal F^{\rm adj}\)，目标执行候选 \(o\in\mathcal O_j^+\)、\(j\ne f\)，二者同 OD，且 \(t_o^{\rm dep}\ge\bar t_f^{\rm dep}\)。令 \(r_{fo}\in\mathbb Z_+\) 为改签人数，对应 `sign[f,o]`。定义

\[
R_f^{\rm out}=\sum_{o:(f,o)\in\mathcal E^{\rm rb}}r_{fo},\qquad
R_f^{\rm in}=\sum_{h\in\mathcal F}\sum_{o\in\mathcal O_f^+:(h,o)\in\mathcal E^{\rm rb}}r_{ho},\qquad
U_f=L_f-R_f^{\rm out}. \tag{X12}
\]

其中 \(h\) 在式（X12）中是源航班索引，\(U_f\) 为未服务账本人数。再定义 \(s_f\in\mathbb B\) 为送出改签指示，则

\[
0\le r_{fo}\le Mx_o,\quad R_f^{\rm out}\le L_f,\quad
s_f\le R_f^{\rm out}\le Ms_f,\quad
R_f^{\rm in}\le M(1-s_f),\quad
R_f+R_f^{\rm in}\le S_f. \tag{X13}
\]

最后两项禁止同一航班同时接收和送出改签，并限制物理占座；不允许通过连续改签构造链条。送出还受以下业务限制：

\[
\begin{aligned}
&R_f^{\rm out}\le F_f^{\rm in}+O_f &&\text{当 }c_f=0,\\
&R_f^{\rm out}\le P_f-I_f^{\rm in}-C_f^{\rm in} &&\text{当 }c_f=1\text{ 且 }R_f^{\rm out}>0,\\
&R_f^{\rm out}=0 &&\text{当 }f\notin\mathcal F^{\rm adj}.
\end{aligned} \tag{X14}
\]

第二条是带送出指示的条件约束，不能在“不送出”时强行要求其右端非负；原代码以 big-M 激活。执行航班的进港取消人数和某些联程损失虽计入 \(L_f\)，不因此自动全部获得送出改签资格。这正是需要单独列出式（X14）的原因。

### 4.6 天池评分目标

令 \(v_f>0\) 为航班重要系数；\(\kappa_f=15\) 当原起飞不晚于调整起日 16:00，否则为 5。令 \(A_f=\mathbf1\{f\in\mathcal F^{\rm adj}\}\)，并定义改签起飞延误 \(\Delta_{fo}^{\rm rb}=t_o^{\rm dep}-\bar t_f^{\rm dep}\ge0\)。目标为

\[
\begin{aligned}
\min Z_T={}&\sum_f1200v_fc_f
+\sum_{o\in\mathcal O^+}v_{f(o)}\frac{100\delta_o}{60}x_o\\
&+\sum_{(a,o)\in\mathcal D}v_{f(o)}\kappa_{f(o)}\mathbf1\{a\ne a_{f(o)}^0\}u_{ao}\\
&+\sum_{o\in\mathcal O^+}A_{f(o)}g(\delta_o/60)\pi_o
+\sum_{(f,o)\in\mathcal E^{\rm rb}}A_{f(o)}h(\Delta_{fo}^{\rm rb}/60)r_{fo}
+4\sum_fU_f.
\end{aligned} \tag{X15}
\]

函数的自变量为小时数 \(t\)；\(g(t)\) 是每名留乘旅客的延误分，\(h(t)\) 是每名改签旅客的起飞延误分：

\[
g(t)=\begin{cases}
0,&t\le0,\\1,&0<t\le2,\\1.5,&2<t\le4,\\2,&4<t\le8,\\3,&8<t\le36,\\10^9,&t>36,
\end{cases}\qquad
h(t)=\begin{cases}
t/30,&0\le t<6,\\t/24,&6\le t<24,\\t/18,&24\le t<36,\\t/16,&36\le t\le48,\\10^9,&t>48.
\end{cases} \tag{X16}
\]

`rebook_delay_cost` 计算前将负值截为 0；合法改签域已保证非负。式（X15）中的 \(A_{f(o)}\) 指**目标航班**是否可调整：窗口外航班的留乘延误和接收改签延误不计天池分。航班取消、延误、换机乘重要系数，旅客项不乘该系数。

分段函数在候选生成后成为常数系数，目标仍为线性整数规划。单位改签分超过未服务单价 4 时，代码将该改签变量上界置 0：改签没有强制最小量，去掉这种选择可释放目标座位，因而是支配消除。`empty_flight, type_change, straighten, flight_ahead` 等评分分项仍可在审计字典出现，但当前受支持动作中为 0，不代表这些动作已优化。

### 4.7 厦航线性研究目标

使用第 3 节定义的 \(\alpha_c,\alpha_d,\alpha_a,\alpha_p,\alpha_u\)，其默认值依次为 25,000、1、0、10、2,500。`air_linear_v1` 为

\[
\begin{aligned}
\min Z_{XA}={}&\alpha_c\sum_fc_f+\alpha_d\sum_{o\in\mathcal O^+}\delta_ox_o
+\alpha_a\sum_{(a,o)\in\mathcal D}\mathbf1\{a\ne a_{f(o)}^0\}u_{ao}\\
&+\alpha_p\left(\sum_{o\in\mathcal O^+}\delta_o\pi_o
+\sum_{(f,o)\in\mathcal E^{\rm rb}}\Delta_{fo}^{\rm rb}r_{fo}\right)
+\alpha_u\sum_fU_f.
\end{aligned} \tag{X17}
\]

式（X17）不使用重要系数和机组成本；改签按起飞延误计，与 AIR 按完整行程最终到达延误计不同。它沿用厦航账本和约束，不能称为原 AIR。两套目标互斥选择，不能把天池分与抽象成本相加。

### 4.8 求解合同、边界与输出

`XmaSolveRequest` 除完整 `dataset`，还包含 `objective_profile, air_objective, algorithm, solver_backend, delay_step_minutes, maximum_delay_minutes, recovery_end, first_solution_search, tail_pool_size`，以及各类运行限额。`model_mode=xma_research`；目标版本为 `tianchi_2017` 或 `air_linear_v1`。

完整机尾子集保存 `subset_selection`。对 Q1/H1 使用的条件子集：外部进港按原时刻冻结，外部出港影响被排除，源机场限制不缩放，也不扣除子集外占用。这是边界假设，不是完整机队问题的等价分解；不同子集不应直接拼接或比较总成本优劣。

当前 Q1/H1/FULL 冻结输入分别为 598／1,176／2,364 班，36／71／142 架飞机；均采用 30 分钟基础网格、`maximum_delay_minutes=null`、`recovery_end=2017-05-10T21:40:00+08:00`、`first_solution_search=true`。这与旧 120 分钟直接基线不同。首解搜索从原机尾池逐步扩展同机型交换池，受限池最优或局部下界不能冒充全交换域最优或全局下界。

输出为 `xma-result-1.0`：`business_decisions` 按航班给出选定候选、机尾、取消、实际时刻与 `rebook` 目标人数；`passenger_allocations` 保存取消进港、失败中转、留乘、送入／送出、未服务及占座账本；另含航班／飞机 outcomes、成本分解、独立审计、CSV、研究签名、输入与来源哈希、搜索范围和停止原因。`passenger_outcomes` 不伪造整组 OD 行程；机组 outcomes 为空。

## 5. 公开基准：冻结转换后的飞机／旅客研究模型

### 5.1 来源、固定转换与缺失信息

公开来源不能直接等同于统一模型输入。ROADEF 的原规则、Delft 的计划与扰动、Delft 2019 的结果资料分别保留，通过显式转换形成研究实例。

| 来源 | 原资料／合同信息 | 当前可建模部分与限制 |
|---|---|---|
| ROADEF 2009 | `config, flights, rotations, aircraft, itineraries, alt_flights, alt_aircraft` 等原表；容量、维护、规则与行号也保留 | 飞机模型；可选完整落入所选航班的原旅客整组；舱等被合并，未恢复全部原规则 |
| TU Delft 2020 输入资料 | 计划、扰动、连接 HDF5；`ACType, TAT` 及其他辅助表；原行号与分类字典 | 静态飞机模型；连接边际观察不等于完整 OD 需求，故不建立完整旅客模型 |
| TU Delft 2019 Results | 运行成本、KPI、时间及状态观察 | 外部结果分析；没有可逐例配对的完整输入，不作为可重跑数学实例 |

当前 Delft 转换按明确窗口构建派生实例，未声称复现发布者原始“370 组”划分，也不将 2019 结果资料与 2020 输入自然配对。

`PublicSolveRequest(schema_version=public-benchmark-1.0)` 的固定字段如下：

| 字段 | 合同含义 |
|---|---|
| `instance_id, model_type, components` | `aircraft` 或 `aircraft_passenger`；组件严格为飞机开启、旅客按模式开启、机组关闭 |
| `source` | 数据集与来源实例、转换器版本、基准标识、源文件哈希、规范记录、原始表、扰动解释和参考答案类型 |
| `scenario, recovery_columns` | 明确的时间窗、所选飞机／航班及旅客；冻结航班候选与旅客行程；飞机路径按算法生成 |
| `capacity_profile, costs, configs` | 每候选座位、完整成本对象、完整算法／合法性配置；不能只记录 profile 名而遗漏实际值 |
| `candidate_policy` | 网格、最大延误、抽样种子、目标规模、实际规模、选中机尾、完整轮转闭包、能力过滤与排除机尾 |
| `fixed_context` | 未进入优化的原航班、被排除行程和窗口长度；用于解释条件边界，不会自动变成决策变量 |
| `rule_mapping, precheck_issues` | 原规则到研究规则的映射，以及维护／事件语义等未支持项 |
| `algorithm, backend, problem_sha256` | 求解路线、显式求解后端及冻结问题指纹 |

`problem_sha256` 覆盖除自身、`algorithm`、`backend` 以外的规范化请求字段；因此候选、成本、配置和上下文也进入指纹。更换算法或后端允许保持同一问题指纹；改网格、成本或上下文须重新生成实例。算法配置虽可能仅影响搜索，也由当前工程合同纳入冻结载荷。

设研究窗口为 \([t_0,t_1]\)。转换只选择原起降均位于窗口内的航班，并按完整机尾窗口内轮转闭包抽样；按固定种子优先受扰动机尾，实际规模可能超过目标。只选活动机尾，不自动加入原资料中的闲置备机。

| 固定转换规则 | 精确含义 |
|---|---|
| 复合机型 | 原机型＋完整座位配置向量＋来源过站时间组成 equipment；三者完全一致才允许互换 |
| 初始位置与 ready | 非取消前缀决定位置；`ready_at` 取窗口起点与前缀到达加来源上下文延误及过站的最大值 |
| 末端回接 | `available_until` 由窗口终点和后缀起飞减过站形成；要求结束于后续固定航班的起点；没有后缀则为窗口内原末段终点 |
| 资源不可用 | 有明确起止时刻的区间参与航段重叠检查；不明语义保留并拒绝，不解释为机场关闭 |
| ROADEF 明确扰动 | `alt_flights` 中非负指定值固定执行延误及原机尾，禁止取消；`-1` 强制取消；不是将所有正值都当可继续延后的下界 |
| Delft Delay | 正出发延误作为最早起飞下界，保持原计划 block；负值留痕但不生成提前；不能声称复现原动态模型 |
| 候选 | 支持 60／30／15 分钟嵌套网格，首批默认 30、最大延误 120 分钟；补最大值、来源延误与不可用边界，实际到达不得越过窗口末端 |
| 旅客范围 | 仅 ROADEF `aircraft_passenger`；原行程完整且所有航段均被选中的组进入优化，其余保留在排除清单 |
| 地方容量与维修 | 原机场小时容量保留但当前研究飞机模型不施加；Scenario 使用宽松代理时段；未支持的维修／事件形成预检拒绝项 |

### 5.2 决策变量与合法飞机网络

使用共同的 \(x_o,c_f\)，以及第 4 节定义的飞机执行变量 \(u_{ao}\)。旅客模式使用第 3 节的 \(w_{gi},U_{gi},\Delta^{\rm arr}_{gi}\)；纯飞机模式取 \(\mathcal G=\varnothing\)。不设机组变量。

对每架飞机，定义合法执行候选集合 \(\mathcal O_a^{\rm leg}\subseteq\mathcal O^+\)。候选进入该集合须同时满足：

1. 复合机型相同，起讫机场与原航班相同，block 与原航班相同。
2. 不属于强制取消航班；若存在固定延误，则延误值等于指定值且仅原机尾有资格。
3. \(t_0\le t_o^{\rm dep}<t_o^{\rm arr}\le t_1\)，满足 `ready_at, available_until, earliest_departure`。
4. 与任何资源不可用区间 \([l,r)\) 不重叠：不同时满足 \(t_o^{\rm dep}<r\) 与 \(t_o^{\rm arr}>l\)。
5. \(0\le\delta_o\le\delta_f^{\max}\)，其中 \(\delta_f^{\max}\) 为航班冻结最大延误；实际时刻与延误字段一致。

定义 \(\tau_a\) 为来源过站分钟，合法连接弧集合为

\[
\mathcal E_a^{\rm conn}=\{(o,o'):o,o'\in\mathcal O_a^{\rm leg},\ f(o)\ne f(o'),\
\operatorname{dst}(o)=\operatorname{org}(o'),\ t_{o'}^{\rm dep}\ge t_o^{\rm arr}+\tau_a\}. \tag{P1}
\]

每条弧严格按时间前进。再定义二元变量 \(b_{ao},d_{ao}\) 分别表示从源进入候选、从候选结束；\(q_{a,oo'}\) 表示连接弧；\(\zeta_a\) 表示飞机整窗闲置。只有候选起点为 \(v_a^0\) 时可建立 \(b_{ao}\)；对未建立的源变量按 0 理解。

### 5.3 完整的直接模型约束与目标

每班唯一选择、执行覆盖为式（X1），此时合法分配对取 \(\mathcal D=\{(a,o):a\in\mathcal A,o\in\mathcal O_a^{\rm leg}\}\)，按本节公开规则判定；对战略／固定执行航班另有 \(\sum_{o\in\mathcal O_f^+}x_o=1\)。每架飞机的流量为

\[
\sum_{o\in\mathcal O_a^{\rm leg}}b_{ao}+\zeta_a=1, \tag{P2}
\]
\[
b_{ao}+\sum_{o':(o',o)\in\mathcal E_a^{\rm conn}}q_{a,o'o}
=u_{ao}
=d_{ao}+\sum_{o':(o,o')\in\mathcal E_a^{\rm conn}}q_{a,oo'}
\quad(o\in\mathcal O_a^{\rm leg}). \tag{P3}
\]

逐机尾硬终点为

\[
\sum_{o\in\mathcal O_a^{\rm leg}:\operatorname{dst}(o)=v}d_{ao}
+\mathbf1\{v_a^0=v\}\zeta_a
=\mathbf1\{v_a^T=v\}\quad(a\in\mathcal A,v\in\mathcal V). \tag{P4}
\]

因此，只有初始机场等于要求终点时，闲置才能单独满足该机尾资源流。与厦航不同，不要求每架飞机至少飞一段，也不以机型—机场总数量替代逐机尾终点。

旅客约束是式（A5）的每组一行程、式（A7）的行程可用性及式（A8）的座位限制。公开容量 \(Q_o\) 等于原飞机各舱座位之和；因为只允许相同完整座位配置互换，这个固定值在当前交换域内与实际供给一致。它不是一般跨容量换机模型。

目标为

\[
\begin{aligned}
\min Z_{\rm PUB}={}&\alpha_c\sum_fc_f+\alpha_d\sum_{o\in\mathcal O^+}\delta_ox_o
+\alpha_a\sum_a\sum_{o\in\mathcal O_a^{\rm leg}}\mathbf1\{a\ne a_{f(o)}^0\}u_{ao}\\
&+\sum_{g\in\mathcal G}\sum_{i\in\mathcal I_g}
n_g\bigl[\alpha_p(1-U_{gi})\Delta^{\rm arr}_{gi}+\alpha_uU_{gi}\bigr]w_{gi}.
\end{aligned} \tag{P5}
\]

系数沿用第 3 节的 25,000／1／0／10／2,500，profile 标记为 `public_air_linear_v1`。转换器不生成改 OD、调机或机组候选，这些成本不进入式（P5）。当前旅客行程默认 MCT=0、最多 3 段、允许未服务，无舱等选择与拆组。

直接模型不建立原小时机场容量、原舱等／降舱、维修、原联程串和地面交通等完整约束；不应将它们写进式（P1）—（P5）后声称已有实现。复用 AIR 算法的路线可以经过宽松 Scenario 容量代理，这仍不构成原容量恢复。

### 5.4 求解、输出与原规则认证边界

直接 MIP、完整路径 Oracle、AIR 分解及公开飞机问题上的厦航算法驱动，改变的是同一冻结研究问题的求解组织。公开 `xma_*` 路线通过 `public_rules` 注入公开飞机约束；不使用厦航人数账本、天池目标或机队终点平衡，且当前只支持 `model_type=aircraft`。

直接模型显式建立合法连接弧，避免枚举完整路径，但仍可能产生大量连接变量。Oracle 的完整性则依赖枚举未触及保护上限；截断列池不能被称为完整参照。

批量原始结果保存 `problem_sha256, selected, solution_columns, objective, lower_bound, upper_bound, gap, audit, certified_optimal, certified_infeasible, timings, model_size, certificate_scope, original_rules` 等证据；按路线可能另含枚举完整性、预处理证明或内核信息。工作台转换为通用恢复结果与方案工件，机组明确关闭。

认证范围只能是“冻结研究模型与候选域内”。若与 ROADEF 原规则和历史可行上界比较，还须导出原生方案，确认全部 11 个官方违规报告存在且为空、成本检查返回数值、舱等映射无未解决项。检查器进程退出码为 0 不等于业务合规；历史最好成绩也不等于已知全局最优。

## 6. 跨模型的输入、参数与输出核对表

### 6.1 不可混用的参数语义

| 项目 | AIR | 厦航 | 公开研究 |
|---|---|---|---|
| 最短飞机过站 | 测试 profile：15 分钟，E1=0 | 普通 50；原相邻短过站例外 | 由来源飞机／机型数据给出 |
| 最短旅客中转 | 行程生成默认 MCT=0 | 每条原中转关系自带分钟数 | 旅客行程默认 MCT=0 |
| 最大候选延误 | 工作台重新生成默认 60，再受逐航班上界限制 | 国内／国际 24／36 小时，再受请求上界限制 | 首批研究默认 120 分钟，并受窗口末端限制 |
| 对旅客计延误 | 整组最终到达延误 | 留乘起飞延误；改签相对源原起飞的延误 | 整组最终到达延误 |
| 航班重要性 | 基准目标没有厦航重要系数 | 天池航班项乘 `importance` | 统一成本中不使用厦航重要系数 |
| 正常机场容量 | 有效时段起降容量＋地面库存代理 | 未指定，不补造；仅特殊运动与停机规则 | 原容量未施加；宽松代理不代表原容量 |
| 原计划外部上下文 | 场景或 Scope 合同明确给出 | 原窗口外冻结；条件子集有外部进港 | 前缀／后缀形成逐机尾硬边界 |

### 6.2 搜索控制参数：保存，但不写成业务决策

| 入口 | 默认或固定运行配置 |
|---|---|
| 原 AIR 正式服务 | `GurobiAdapter`；六类 profile 选择固定配置；飞机／机组 CG 默认各 100 轮，Benders-CG 500 轮，B&P 1,000 节点、深度 100；数值容差详见配置文件 |
| 厦航请求 | `algorithm=joint_arc_flow`、`solver_backend=auto`；Benders 500 轮、B&P 1,000 节点、CG 1,000 轮、Oracle 路径 100,000；时限 300 秒、`mip_gap=0`；合法分配对保护 100,000，可显式改为其他值或关闭该保护 |
| 厦航首解模式 | 仅显式 HiGHS＋`joint_arc_flow`；请求不得同时给固定 `tail_pool_size`；按资源准入逐步扩域，局部界单独标识 |
| 公开请求 | 完整 `configs` 冻结；后端为 HiGHS 或 Gurobi；工作台支持 `direct_mip, air_bp, integrated_oracle`，Oracle 限 12 班；批量入口另有其他路线 |
| 公开直接模型保护 | 默认变量、约束各不超过 1,000,000；触限返回 `input_limit`，不以截断模型冒充原模型 |
| 公开枚举保护 | 最多 12 个可调整航班、200,000 路径、1,000,000 枚举节点；触限不作完整性声明 |

原 AIR 的 CG 配置另固定 `pricing_epsilon=feasibility_epsilon=1e-7`、检验数审计容差 `1e-6`、每资源每轮最多加入 1 个负检验数列；Benders-CG 的绝对／相对 gap 容差为 `1e-6/1e-8`、整数容差 `1e-6`；B&P 的整数／界容差均为 `1e-6`，按 best-bound 选节点。固定列 Benders 组件的绝对／相对容差为 `1e-6/1e-9`，最多 500 轮，三类追索开启。Phase 13 的受限 B&P profile 将节点上限改为 1，用于受限运行，不是业务模型修改。

上述变量域描述最终整数问题；LP／CG 松弛阶段可将相应选择变量改为非负连续变量。Benders 的追索成本变量、CG 的对偶与人工可行性变量、B&P 的分支界属于算法辅助量，不是新的航班、人数或资源业务决策。

厦航显式 HiGHS 目前仍用 gurobipy 构建线性表达式和矩阵，再交原生 highspy 优化；“用 HiGHS”不代表完全取消 Gurobi 建模依赖。`auto` 的降级范围也不能解释为任意异常都自动切后端。

运行模板还能设置时限、节点、迭代和 gap 容差。厦航时限及轮数／节点限额取请求与运行控制中的较小值；相对 gap 映射到请求 `mip_gap`。复现实验应使用保存的有效输入和运行控制，不能只照搬上表默认值。

### 6.3 解、界与状态的共同输出解释

设 \(U\) 为完整可行方案经独立审计后得到的目标上界，\(L\) 为适用于**同一完整研究问题**的有效下界。若二者均存在，绝对间隙为 \(G_{\rm abs}=\max\{0,U-L\}\)；若另报告相对间隙，可明确采用 \(G_{\rm rel}=G_{\rm abs}/\max\{1,|U|\}\)。不同字段可能采用求解器自身相对 gap 定义，不能仅凭同名字段视为相同口径。

| 输出内容 | 必须保留的解释 |
|---|---|
| 方案 | 覆盖所有应决策航班／资源／旅客；只有目标数值不构成完整方案 |
| 独立审计 | 从方案重算约束、容量与目标；不能仅转录求解器“可行”标签 |
| 最优性 | 需要对应问题范围内的有效界、完整路径／定价证据及相应终止条件；LP 最优不自动证明整数最优 |
| 缺失界 | 缺失则保存为 `null`／显示“未取得”，不能填 0 |
| 搜索范围 | 固定日程子问题、限制换机池、必要条件松弛的界不能当全问题收敛证据 |
| 停止原因 | 时限、内存、用户取消、输入／枚举限制须与不可行、最优分开 |
| 任务状态 | `job_status=completed` 只表示任务执行结束；可以对应未收敛或不可行 |
| 无解与不可行 | 尚未找到可行方案，不等于已经证明不可行 |

Q1/H1 已有审计通过方案，但因内存限制结束且未证明最优；FULL 尚无完整可行方案。它们是结果状态示例，不改变本文件定义的模型。历史结果接入工作台只做证据校验、重新审计和转换，不重新求解，也不生成全部候选空间。

## 7. 信息覆盖与明确缺口

下表把“有数据”“有字段”“已进入优化”区分开；未列入某模型约束的资料仍可保留作来源证据或结果解释。

| 信息／能力 | AIR | 厦航 | 公开研究 |
|---|---|---|---|
| 延误、取消与飞机轮转 | 已建模，有限候选 | 已建模，有限候选 | 已建模，冻结候选 |
| 提前、改航路／机场、调机 | schema 可表示部分动作；通用生成器不自动产生改机场／调机 | 当前不支持 | 当前转换不生成 |
| 飞机物理座位随换机变化 | 未耦合，使用外生剩余容量 | 已耦合 | 以相同配置换机限制保证固定容量一致 |
| 机组 | 聚合单元、单 duty、有限置位；非完整岗位／休息法规 | 无数据且关闭 | 无数据且关闭 |
| 维修 | 终点站与满足标记的简化模型 | 关闭，不解释同机场记录为维修 | 原资料可有；未支持时拒绝 |
| 旅客 OD、拆分与中转 | 整组 OD，不拆分；候选 MCT 为测试设定 | 航段整数账本、原中转关系、可拆分改签；无完整 OD | 仅完整纳入的 ROADEF 整组；Delft 连接观察不替代 OD |
| 舱等、降舱与地面交通 | 结构可表示部分地面段，正式生成不覆盖；无完整舱等模型 | 不支持 | 原资料保留，但研究模型未完整支持 |
| 机场地面容量 | 聚合库存代理 | 源评估的特殊跨场景停机计数 | 原容量未完整施加 |
| 现实成本／原竞赛成本 | 测试抽象成本 | 支持动作的天池评分，或抽象成本 | 统一研究成本，不等于 ROADEF 原成本 |
| 模型外不确定性 | 当前静态实例 | 当前静态实例 | Delft 被转换为派生静态问题 |

因此，论文表述宜使用“在给定候选域、容量语义和边界合同下的恢复模型”，并同时报告目标版本、数据来源与未建模信息；不宜笼统称为“全部航空业务约束下的综合恢复最优解”。

## 8. 核对来源与复现入口

下列链接均指本项目文件。它们用于核对实现，不作为外部论文引用；配置注明的文献来源仅是仓库原有元数据，本次未据此扩展未验证的论文结论。

| 主题 | 主要来源 |
|---|---|
| 前序全景文档 | [2026-11-14 技术路线与数据说明](WORKBENCH_V3_TECHNICAL_ROUTES_DATA_AND_MODELS_20261114.md) |
| 通用实体与候选 | [scenario.py](../../backend/schemas/scenario.py)、[flight.py](../../backend/schemas/flight.py)、[aircraft.py](../../backend/schemas/aircraft.py)、[crew.py](../../backend/schemas/crew.py)、[passenger.py](../../backend/schemas/passenger.py)、[capacity.py](../../backend/schemas/capacity.py)、[columns.py](../../backend/schemas/columns.py) |
| AIR 联合方程与约束登记 | [integrated_oracle.py](../../backend/core/integrated_oracle.py)、[constraint_registry.py](../../backend/core/constraint_registry.py)、[srm.py](../../backend/core/srm.py)、[gate_inventory.py](../../backend/core/gate_inventory.py) |
| AIR 路径合法性 | [flight_network.py](../../backend/core/flight_network.py)、[string_generator.py](../../backend/core/string_generator.py)、[pairing_generator.py](../../backend/core/pairing_generator.py)、[itinerary_generator.py](../../backend/core/itinerary_generator.py) |
| AIR 成本与容量 | [costs.py](../../backend/config/costs.py)、[passenger_capacity.py](../../backend/config/passenger_capacity.py)、[基准成本 JSON](../../data/costs/phase2_test_costs_v1.json) |
| AIR 正式输入与结果 | [solve_service.py](../../backend/application/solve_service.py)、[result.py](../../backend/schemas/result.py)、[compiler.py](../../backend/workbench/compiler.py)、[workbench.py](../../backend/schemas/workbench.py) |
| 固定合法性 profile | [飞机过站](../../data/config/phase5_test_string_generation_v1.json)、[机组](../../data/config/phase6_test_crew_pairing_generation_v1.json)、[旅客](../../data/config/phase7_test_itinerary_generation_v1.json) |
| 厦航合同与导入 | [schema.py](../../backend/business/xma/schema.py)、[importer.py](../../backend/business/xma/importer.py)、[rules.py](../../backend/business/xma/rules.py) |
| 厦航方程、成本和独立审计 | [model.py](../../backend/business/xma/model.py)、[objectives.py](../../backend/business/xma/objectives.py)、[evaluator.py](../../backend/business/xma/evaluator.py) |
| 厦航研究签名与首解范围 | [service.py](../../backend/business/xma/service.py)、[search.py](../../backend/business/xma/search.py)、[首解操作说明](XMA_HIGHS_FIRST_SOLUTION.md) |
| 公开数据读取与冻结转换 | [roadef.py](../../backend/benchmarks/roadef.py)、[delft.py](../../backend/benchmarks/delft.py)、[model.py](../../backend/benchmarks/model.py) |
| 公开直接方程与独立审计 | [direct.py](../../backend/benchmarks/direct.py)、[audit.py](../../backend/benchmarks/audit.py)、[solve.py](../../backend/benchmarks/solve.py) |
| 公开算法桥接与工作台合同 | [xma.py](../../backend/benchmarks/xma.py)、[workbench.py](../../backend/benchmarks/workbench.py)、[原规则核验](../../backend/benchmarks/external.py) |

供实际字段核对的冻结输入：AIR [微型 B&P 输入](../../data/validation_suite/frozen/micro/micro-branch-and-price.json)；公开 [ROADEF 旅客实例](../../.public_benchmarks/formal-v3-20261111-r4/inputs/roadef-pax.json)；厦航 [Q1](../../.public_benchmarks/xma-first-solution-v3-20261120/inputs/Q1.json)、[H1](../../.public_benchmarks/xma-first-solution-v3-20261120/inputs/H1.json)、[FULL](../../.public_benchmarks/xma-first-solution-v3-20261120/inputs/FULL.json)。`.public_benchmarks` 是本机实验目录，通常不随 Git 分发；对外共享时须同时提供相应冻结证据。
