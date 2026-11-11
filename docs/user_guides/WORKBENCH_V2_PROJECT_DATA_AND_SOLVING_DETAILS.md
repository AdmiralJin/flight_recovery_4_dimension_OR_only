# Workbench v2 项目、数据资产与端到端求解详解

核查日期：2026-11-06（北京时间）。依据当前工作区代码、冻结 JSON、原始工作簿及本地运行产物；Git HEAD 为 `1691ddb10fa3d97be0caff9584536e20fbced5b3`，工作区已有未提交修改，因此本文描述的是当前工作区，不能只凭该 commit 重建全部行为。

## 1. 项目实际在研究什么

项目围绕航空运行受扰后的恢复决策：哪些航班继续执行、延误或取消，如何重新安排飞机和机组，以及如何承运、改签或放弃服务旅客。

Workbench v2 是单机研究、实验和审计界面。核心研究对象是运筹优化模型与算法；仓库中的“数据集”主要是优化算例、候选方案、规则配置和实验记录。当前没有机器学习训练集、验证集、测试集划分，也没有模型训练流程。“validation_suite”表示输入及优化行为验证。

项目有两条求解路线，共用工作台生命周期，业务模型分别实现：

| 方面 | AIR 复现路线 | 厦航 XMA 研究路线 |
|---|---|---|
| 定位 | 项目 README 所述的 AIR 综合恢复模型复现与算法验证 | 厦航天池工作簿的业务接入、评分复算及规模研究 |
| 数据 | 人工可核验案例、算法反例、确定性合成压力实例 | 原始七表工作簿及保持整机尾轮转的派生子问题 |
| 决策主体 | 航班、飞机、机组、不可拆分旅客组 | 航班、飞机、按航段账本处理的整数旅客人数 |
| 机组与维修 | 有简化表示及测试配置 | 因源数据缺失而明确关闭 |
| 座位 | 外生的 Flight Option 剩余容量 | 所选飞机的物理座位 |
| 求解 | Benders + 飞机/机组列生成 + 必要的分支定价 | 联合网络流、显式路径基准、两种 Benders 分解 |
| 目标 | 研究用线性成本 | 天池评分或独立 AIR 线性研究成本 |
| 实现 | backend/core、backend/application | backend/business/xma |

厦航的 `air_linear_v1` 只是把线性成本用于厦航业务模型，不能视为旧 AIR 不可拆分 OD 旅客模型的同一数学问题。

## 2. 从当前 HTML 文件追到实际功能

`frontend/v2/index.html` 只负责主题初始化、根节点与加载 main.tsx。业务逻辑从下列链路进入：

~~~text
frontend/v2/index.html
  → src/main.tsx：React、QueryClient、主题、/workbench-v2 路由
  → src/App.tsx：六个任务页
  → src/api.ts：HTTP API
  → backend/api/workbench_v2.py：工作台服务
  → backend/workbench/compiler.py：按业务合同编译
  → backend/workbench/worker.py：按 schema 分派求解器
~~~

| v2 页面 | 主要职责 | 主要输入与输出 |
|---|---|---|
| 数据设计 DataStudio | 克隆案例、导入草稿、编辑数据及配置 | DraftDocument、Working hash |
| 扰动影响 ImpactPage | 编译扰动，显示直接暴露和资源链风险 | CompilePreview、有效容量、风险标记 |
| 求解 SolvePage | 保存待提交厦航配置、编译、快照、入队、监控、取消 | Snapshot、Run、SSE 事件 |
| 可视化 VisualizationPage | 航班网络、飞机/机组甘特、旅客、容量、传播、成本、延误 | 后端统一 VisualizationModel |
| 方案对比 ComparePage | 原计划与恢复计划字段和实体变化对比 | 后端 canonical comparison |
| 审计 AuditPage | 输入、决策、成本、约束、Trace、环境及导出 | Audit package |

后端由 FastAPI 提供接口，Pydantic 定义输入输出合同；SQLite/WAL 保存索引，gzip JSON 保存大对象。前端使用 React 19、TypeScript、Vite、TanStack Query/Table/Virtual、Zustand 和 ECharts。

前端构建输出为 frontend/dist。后端检测到构建产物时，根地址跳转到 `/workbench-v2/data`；旧页面保留在 `/legacy`。不要双击当前 HTML 作为完整应用启动。

## 3. “一份数据”在项目中的不同层次

| 对象 | 含义 | 是否已足够求解 |
|---|---|---|
| Scenario | 恢复时间窗、机场、原航班、飞机、机组、旅客组、机场容量和扰动 | 单独不够 |
| RecoveryColumns | 航班时刻候选、飞机路径、机组任务串、旅客行程等可选方案 | 仍需容量、成本和算法配置 |
| Capacity profile | 每个执行候选可供研究旅客使用的剩余座位 | AIR 的显式输入 |
| Cost/profile JSON | 成本系数、过站/衔接规则、定价和分支限制 | 研究假设及运行配置 |
| SolveRequest / Solve Bundle | 正式 AIR 求解输入的完整组合 | 通过 readiness 后可以提交 |
| XmaDataset / XmaSolveRequest | 厦航七表映射、来源、规则和研究参数 | 走厦航专用 readiness |
| DraftDocument 2.0.0 | v2 工作副本，包装 Scenario、Solve Bundle、类型化扰动、候选策略和 Expected | 编译成功后才能创建快照 |
| Snapshot | 不可变的规范输入、编译预览、草稿和环境标识 | 某次 Run 的固定依据 |
| Run / Result / selected artifact | 运行状态、恢复结果、动态生成并选中的资源列、评分和事件 | 是输出与复现证据 |
| Comparison / Visualization | 从快照及结果构造的只读展示对象 | 是展示数据，不参与重新求解 |

需要区分“业务原始数据”“允许选择的候选集合”“算法配置”“求解结果”。修改延误网格、余座或成本，即使原航班表不变，也可能已经改变研究问题。

## 4. 已建立的数据资产总清单

本次清点得到：

| 位置 | 数量 | 用途 |
|---|---:|---|
| data/examples | 16 个 Scenario JSON | 基础输入、多实体校验、各阶段算法验证 |
| data/columns | 14 个候选列 JSON | 人工参考、固定列模型、生成器及定价 Oracle |
| data/capacities | 8 个容量 JSON | AIR 剩余座位及容量敏感性 |
| data/costs | 1 个 canonical 成本 JSON | phase2_test_v1 的成本及来源说明 |
| data/config | 9 个算法/生成配置 JSON | 生成规则、Benders、列生成、分支定价和受限运行 |
| data/expected | 3 个 Expected JSON | 早期结构与人工恢复参考 |
| data/cases/catalog.json | 8 个案例入口 | v2 直接克隆的内置目录 |
| data/validation_suite/frozen | 20 个 micro + 5 个 stress | 人工验证、回归、压力与受控终止 |
| data/厦航-天池比赛数据/data | 原始 xlsx、评估 JAR、源码 ZIP、JAR 说明 | 厦航数据与外部评分依据 |
| docs/codex_reports/xma_experiments_* | 输入、结果和汇总 | 2026-10-08 的厦航规模实验证据 |
| .workbench | 本机草稿、快照、运行、事件和产物 | 工作台实际使用历史；通常不进入 Git |

这些数量不能相加为独立数据源：catalog 会引用 examples、columns、capacities；micro 又会包装 catalog 或已有阶段案例；P1 直接复用 benchmark。部分冻结文件内容完全相同，只承担不同入口或验证说明。

### 4.1 当前 v2 内置目录的 8 个入口

来源：[catalog.json](../../data/cases/catalog.json)。本次逐个装载、校验和编译，结果与下表的输入预期一致。目标值来自冻结 Expected 和既有回归证据，本次未重新求解。

| case_id | 研究问题 | 输入预期 | 已冻结优化预期 |
|---|---|---|---|
| benchmark-disruption-recovery | 机场离港容量下降，联动飞机互换及旅客改签 | 可求解 | optimal，18080 |
| crew-recovery-integrality | 机组 LP 与整数恢复之间存在缺口 | 可求解 | optimal，95200 |
| passenger-capacity-constrained | 原始时刻余座为 0，迫使航班延误承运旅客 | 可求解 | optimal，1010 |
| passenger-capacity-relaxed | 仅把原始候选余座改为 10 | 可求解 | optimal，0 |
| delay-cost-cancellation-tradeoff | 把航班延误单价改为 3000，比较延误与未承运 | 可求解 | optimal，25000；原航班照常，10 人未服务 |
| solve-ready-infeasible | 输入齐全，但限制后的航班候选无法联合满足资源条件 | 可求解 | infeasible |
| scenario-only-minimal | 验证编辑、导入导出及风险展示 | Scenario 有效，未具备求解输入 | 无优化预期 |
| invalid-missing-airport | 航班引用未声明机场的负例 | Scenario 无效，未具备求解输入 | 无优化预期 |

其中 6 个为 Solve Bundle、2 个为 Scenario-only。名称含 cancellation 的成本敏感性案例，实际冻结结果是选择“未承运旅客”，不要按案例 ID 推断发生了航班取消。

装载 Solve Bundle 时，case_service 会清空人工飞机串和机组串，让正式算法动态生成；主 benchmark 的旅客行程由生成器从人工的 17 条扩展为 55 条。因此其 v2 编译输入是 22 个航班候选、55 条旅客行程、0 条预生成飞机串、0 条预生成机组串。

### 4.2 16 个底层 Scenario 的角色

规模按“机场 / 航班 / 飞机 / 机组 / 旅客组”列示。算法小例子是阶段夹具；原阶段的目标与固定候选范围有关，不能直接当作当前动态列入口的目标。

| Scenario | 规模 | 建立目的 |
|---|---|---|
| toy_case_001 | 3 / 6 / 2 / 2 / 4 | Schema、编辑器、导入导出、可视化和风险传播 |
| phase1_validation_001 | 5 / 12 / 6 / 6 / 8 | 多实体、引用及时间/资源关系校验 |
| phase1_benchmark_001 | 4 / 12 / 4 / 5 / 8 | 可人工核算的综合恢复基准 |
| toy_case_003 | 3 / 3 / 3 / 3 / 2 | 旅客网络、行程和容量处理的早期小例子 |
| toy_case_004 | 2 / 1 / 1 / 1 / 1 | 固定候选飞机可行性反向影响航班方案选择 |
| toy_case_005 | 2 / 1 / 1 / 1 / 1 | 旅客容量反向影响航班时刻，衍生容量/成本敏感性 |
| toy_case_006_scope | 5 / 3 / 2 / 2 / 2 | 扰动范围闭包、独立组件冻结与 Full/Scope 对照 |
| toy_case_007_string_generator | 5 / 5 / 3 / 3 / 0 | 飞机路径生成的机型、过站、维修、终点和调机边界 |
| toy_case_008_crew_pairing_generator | 2 / 3 / 2 / 2 / 0 | 机组 OPERATE/DEADHEAD 任务串显式生成 |
| toy_case_009_passenger_itinerary_generator | 5 / 6 / 4 / 4 / 2 | 旅客 OD、衔接、最大航段与 UNSERVED 候选 |
| toy_case_010_fixed_column_benders | 2 / 1 / 1 / 1 / 1 | 固定列 Logic-based Benders 的可行割、追索割 |
| toy_case_011_aircraft_string_column_generation | 6 / 2 / 2 / 2 / 0 | 飞机负约化成本列和 LP 最优性认证 |
| toy_case_012_crew_pairing_column_generation | 2 / 2 / 2 / 3 / 0 | 机组定价，区分执行与搭乘成本 |
| toy_case_013_benders_column_generation | 2 / 1 / 1 / 1 / 1 | Benders、动态资源列与旅客追索组合；阶段目标 220 |
| toy_case_015_crew_integrality | 3 / 6 / 3 / 3 / 0 | 专用机组子问题 root LP=195、整数最优=200 |
| toy_case_016_benders_branch_and_price | 3 / 6 / 3 / 3 / 0 | 综合整数缺口闭合；正式案例目标 95200 |

项目保留了显式全列生成器与固定列 Integrated Oracle，以便在小实例上和动态算法对拍。正式 AIR 求解不会先枚举全部飞机串和机组串。阶段实现从“人工可验 → 联合固定列 → 全量小例子 Oracle → 列生成 → 整数分支 → 稳定 API”逐步建立正确性证据。

### 4.3 20 个微型验证入口

完整来源、冻结文件路径、SHA-256、预期与人工检查点在 [manifest.json](../../data/validation_suite/manifest.json)、[MICRO_CASE_CARDS.md](../../data/validation_suite/MICRO_CASE_CARDS.md) 中。

| micro ID（省略 micro- 前缀） | 来源/用途 |
|---|---|
| integrated-benchmark | 综合基准，18080 |
| crew-integrality | catalog 的机组整数案例，95200 |
| passenger-capacity-binding | 原始候选余座绑定，1010 |
| passenger-capacity-relaxed | 单变量容量放宽，0 |
| delay-unserved-tradeoff | 延误与未承运权衡，25000 |
| solve-ready-infeasible | 就绪性与优化可行性分离 |
| scenario-only-minimal | 有效 Scenario，缺少 Solve Bundle |
| invalid-missing-airport | 错误机场引用负例 |
| scenario-validation-rich | phase1_validation_001 的多实体校验 |
| basic-editor | toy_case_001 的基础编辑与传播 |
| aircraft-coupling | toy_case_004 的飞机与计划耦合 |
| scope-closure | toy_case_006 的范围闭包来源实例 |
| aircraft-string-generation | toy_case_007 的飞机路径生成 |
| passenger-itinerary-generation | toy_case_009 的旅客行程生成 |
| fixed-column-benders | toy_case_010 的固定列阶段来源实例 |
| aircraft-column-generation | toy_case_011 的飞机定价 |
| crew-column-generation | toy_case_012 的机组定价，综合入口预期 150 |
| benders-column-generation | toy_case_013 的组合算法，220 |
| crew-root-integrality | toy_case_015 的专用整数缺口来源实例 |
| branch-and-price | toy_case_016 的正式整数恢复，95200 |

20 个 micro 中，16 个为 Solve Bundle、4 个为裸 Scenario。加上 5 个压力 Bundle，总计 21 个 Solve Bundle、4 个 Scenario。

覆盖矩阵登记了 20 个 AIR 本地约束 ID：SRM 6 项、ARM 5 项、CRM 5 项、PRM 4 项。部分条目是输入合法性守卫或代理约束；登记“覆盖”不等于每项都在每个实例上绑定，也不等于已实现全部真实航司规则。

部分阶段数据包装为 Bundle 时，没有特定容量文件会填入明确标记为合成的非绑定容量 999999。这类数据用于隔离算法行为，不能作为真实座位利用率研究数据。

范围闭包、固定列、整数性等名称描述其来源和验证意图。包装后的 Bundle 仍走当前正式算法；例如 scope 案例通过 v2 求解不表示开启了动态 Scope。原阶段能力应结合对应底层函数和 regression 测试查看。

### 4.4 P1–P5 压力数据

来源：[STRESS_PROFILES.md](../../data/validation_suite/STRESS_PROFILES.md)、[calibration_results.json](../../data/validation_suite/calibration_results.json)。下面是实际冻结实体数，P1 的生成器直接返回 benchmark，不使用其名义生成参数构造另一个实例。

| 档位 | 机场 | 航班 | 飞机 | 机组 | 旅客组 | 航班候选 | 旅客行程 | 已记录的验证程度 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| P1-seconds | 4 | 12 | 4 | 5 | 8 | 22 | 55 | 2026-09-21 参考机约 1.308 秒，optimal=18080，审计通过 |
| P2-tens-seconds | 4 | 12 | 3 | 3 | 12 | 36 | 42 | 70.074 秒预算探测后 aborted；LB=120、UB=600 |
| P3-minutes | 6 | 20 | 6 | 6 | 30 | 60 | 102 | 已生成、通过输入就绪性；未做长时性能校准 |
| P4-tens-minutes | 8 | 40 | 12 | 13 | 80 | 160 | 412 | 同上 |
| P5-hours | 12 | 72 | 21 | 24 | 250 | 360 | 1764 | 同上 |

P2–P5 使用固定种子 202/303/404/505，生成枢纽—支线网络，每架运营飞机 4 个航段，可加入备用飞机和备用机组；枢纽某半小时时段降低起飞容量。旅客行程组合来自预设原路线上的时刻候选；部分原始候选被设置为比旅客负载少 1 座，以激活容量耦合。压力实例把旅客延误单价覆盖为 1，其余沿 canonical 成本。

“seconds/minutes/hours”是设计目标时间带，不是求解承诺。P2 是受控终止案例，不能作为已得到最优解的演示；P3–P5 的求解时间与最终最优结果尚无已完成校准证据。

### 4.5 v2 导入时的包装差异

v2“导入草稿”要求 DraftDocument 2.0.0。冻结的 Scenario、Solve Bundle、旧 Current Case 导出和审计包，都不是同一种导入文件。验证套件文档中的 Scenario/Solve Bundle 导入说明主要对应旧接口或旧页面，当前并未把全部 micro/stress 自动加入 v2 的 8 项下拉目录。

要在 v2 研究某个冻结 Bundle，可以在外部包装成下列结构，再导入草稿：

~~~python
import json
from pathlib import Path
from backend.schemas.workbench import DraftDocument

bundle = json.loads(
    Path("data/validation_suite/frozen/stress/P1-seconds.json")
    .read_text(encoding="utf-8")
)
draft = DraftDocument(
    name="P1 综合恢复研究",
    capacity_semantics="effective_legacy",
    scenario=bundle["scenario"],
    solve_bundle=bundle,
    expected={"optimization_status": "optimal", "objective_total": 18080.0},
)
Path("P1.draft.json").write_text(
    draft.model_dump_json(indent=2), encoding="utf-8"
)
~~~

这段是使用示例，本次核查没有执行文件生成或导入。Scenario-only 可以包装 scenario，但在补齐候选、容量和配置前仍不能求解。manifest 的 `expected.status` 与 v2 审计使用的 `expected.optimization_status` 命名不同，适配时应明确映射。

## 5. 厦航原始数据、清洗语义与派生研究样本

原文件：[XMAE_data.xlsx](../../data/厦航-天池比赛数据/data/XMAE_data.xlsx)。本次实际调用只读导入器解析，完整数据通过业务输入校验。

源文件 SHA-256：

~~~text
5f701764966453300af501d05d7f4d664523e97bcddbf5eed244ac1fdf43ed1f
~~~

| 工作表 | 有效数据行 | 模型用途 |
|---|---:|---|
| 航班 | 2364 | 原时刻、OD、机尾、机型、普通/联程旅客数、座位、重要系数 |
| 航线-飞机限制 | 8693 | 禁止某架飞机执行某条航线 |
| 机场关闭限制 | 6 | 每日关闭时间、有效日期范围 |
| 台风场景 | 11 | 禁起飞、禁降落及停机场景 |
| 飞行时间 | 8703 | 机型—OD 飞行时间来源数据；当前无跨机型/调机动作，不应误解为全部记录都进入当前模型 |
| 机场 | 79 | 机场及国内/国际标记 |
| 中转时间限制 | 773 | 指定进出港航班、最短转机时间及人数 |

从航班表还原 142 架飞机、4 个机型、616 对联程航段。导入器保留每项的 sheet/row 来源及原始表行。

输入中特别保留：

- 48 个普通旅客数加联程旅客数超过座位数的航班，交给超售/溢出账本处理。
- 212 个原飞机相邻航段过站不足 50 分钟的关系，用于原短过站例外。
- 5 个同机场起降记录，保留原含义，不自行解释为维修。
- 飞行时间表存在 1464 个重复键行；原始行保留，有效查找按来源 Java 的后写覆盖语义处理。

原航班时间覆盖北京时间 2017-05-05 00:30 至 2017-05-09 09:40；允许调整窗口为 2017-05-06 06:00 至 2017-05-09 00:00（含两端）。窗口和共享起降容量规则来自附带评估器源码，不是全部都能从 Excel 单元格直接读到。

原普通旅客数按航段求和为 207940，联程字段按航段求和为 46344。它们不是去重后的独立旅客总人数，不能把这两个和当作全网独立旅客规模。

### 5.1 固定与随机子集怎么建立

`select_subset` 以整架飞机的原轮转为单位，不是从航班表随机删几行。

| 请求规模 | 当前固定选择实际航班数 | 飞机数 | 保留的中转关系 | 固定外部进港边界航班 |
|---|---:|---:|---:|---:|
| 约 20 | 30 | 2 | 7 | 7 |
| 约 100 | 103 | 6 | 31 | 29 |
| 约 500 | 508 | 30 | 207 | 95 |
| 全量 | 2364 | 142 | 773 | 无子集外边界 |

固定选择优先选择原轮转经过受台风机场的机尾，再按机尾 ID 排序，累计达到请求规模即停止。随机选择也先把这类机尾和其他机尾分组，各组用种子打乱后依次取入；这不是对全体航班均匀独立抽样，也不是所有机尾的无条件均匀抽样。

随机样本保存请求/实际航班数、seed、选中机尾列表、算法版本和 selection_hash。未指定 seed 时后端生成新 seed。复现实验应同时保存原始文件哈希、选中机尾列表/样本哈希和完整快照。

所有进入选中出港航班的中转关系保留；若进港航班在子集外，就把该进港航班按原时刻固定为边界条件。子集外的后续出港影响不进入子问题目标。因此子集是有条件的独立研究问题，子集 CSV 不能直接当作全量工作簿的完整恢复方案。

子集仍保留全网机场表、限制表和来源表。预览里的 airports=79 表示机场字典数量；short_original_turns 等字段也可能统计保留的全网关系，不能全部解释为选中航班的局部规模。

### 5.2 七表之外的规则含义

- 台风禁起降时间、日内关闭时间使用来源规则的严格开区间；AIR 容量桶则通常是半开区间，两者不要混用。
- 受影响机场在指定窗口每 5 分钟起降合计不超过 2 次，并沿用来源评估器的分桶原点。
- 正常机场的真实起降容量没有给出，模型不会补造容量值。
- 停机按“相邻执行航段之间的地面间隔完整跨越停机场景”计数；不是所有时点的飞机库存。没有前序/后续执行航班的初始或最终停车，不按该口径计入。
- 普通过站为 50 分钟；原相邻短过站使用 min(50, original_turn)。
- 两段联程都执行时，必须由同一飞机连续执行。
- 终点要求按机型和机场保持机队总数，不要求每架机尾回到自己的原终点。
- 当前每架纳入模型的飞机需至少执行一个航段；不能自行假定支持任意飞机全天闲置。

## 6. Workbench v2 端到端流程

~~~mermaid
flowchart TD
    A[内置 Case 或厦航工作簿] --> B[DraftDocument 工作副本]
    B --> C[编译和输入就绪性检查]
    C --> D[不可变 Snapshot 与 Input hash]
    D --> E[Run 入队和隔离 worker]
    E --> F{业务 schema}
    F --> G[AIR Benders / CG / B&P]
    F --> H[XMA 联合或分解模型]
    G --> I[独立约束和成本复算]
    H --> I
    E --> J[SQLite 结构化事件与 SSE]
    I --> K[结果和选中列产物]
    K --> L[统一对比 / 可视化 / 审计包]
    J --> L
~~~

1. **建立草稿。** AIR 内置案例经 /api/cases 装载，再调用 /api/v2/drafts 克隆。厦航由 /api/v2/xma/import-preview 读取项目工作簿或上传字节，预览后保存完整业务草稿。
2. **编辑并保存。** 工作副本更新携带 base_hash；后端用条件更新避免覆盖另一版本，冲突返回 409。厦航保存会从业务 Solve Bundle 重新生成展示 Scenario，后者不是 AIR Scenario 的直接替代品。
3. **编译。** /drafts/{id}/compile 计算有效场景、候选数、风险标记和规范 Solve Request。厦航按 xma-solve-1.0 分派到业务编译器，禁止把 AIR 手工候选和类型化扰动混入。
4. **处理容量。** AIR 的 effective_legacy 表示机场容量已经受扰，不能再扣一次旧 disruption；baseline_compiled 才把类型化规则叠加到基线。按规则边界切分时段，关闭/宵禁优先将容量置 0，其他增减相加，负值截为 0 并给出警告。
5. **处理候选。** AIR 可保留已有候选，或由 v2 编译器生成原计划、取消与延误网格，加入人工候选并生成旅客行程。有旅客时必须显式提供剩余座位。默认网格步长 10 分钟、最大 60 分钟，还受每个航班 max_delay 限制。不会自动生成改机场或调机动作。
6. **检查输入就绪性。** 检查业务引用、候选语义、容量、成本及算法 Profile。Ready 代表输入可交给算法，不代表一定存在联合可行解。
7. **创建快照。** /drafts/{id}/snapshots 再次检查当前 hash 并重新编译，保存草稿、编译结果、规范输入和 Git commit/dirty/diff_hash。这里冻结输入，后续草稿改动不会改变历史运行。
8. **创建 Run。** /api/v2/runs 指向 snapshot_id 和 runtime_profile_id。当前同时最多运行 1 个任务，由 supervisor 启动独立 Python worker，按业务 schema 分派。
9. **求解与监控。** worker 保存带 seq、时间、阶段、LB/UB/Gap 和指标的事件；SSE /runs/{id}/events 支持 Last-Event-ID，另有 event-history 供重新读取。前端只用真实界事件绘制收敛曲线。
10. **独立复算。** AIR 复算选中列、覆盖、目标分量和恢复指标；厦航 evaluator 从业务决策重新计算合法性、两套成本和逐航段旅客账本。动态选中资源列另存为 selected_solution_artifact。
11. **查看并导出。** comparison、visualization、audit 都绑定本次快照。/runs/{id}/export 导出运行、快照、对比、可视化、选中列、审计和事件；厦航另有 /xma/runs/{id}/csv。

哈希使用排序键、无多余空白、禁止 NaN 的规范 UTF-8 JSON 再做 SHA-256。Working hash 标识完整草稿；Compiled/Input hash 标识规范求解输入。仅修改名称等展示信息可能改变 Working hash，但未必改变规范输入。

取消先通过数据库标记及求解器回调协作退出，约 5 秒后仍未退出则终止隔离进程。服务重启时遗留的活动任务标为 interrupted，不会自动恢复算法执行。浏览器刷新不会取消后端任务。

## 7. AIR 路线的模型与求解细节

### 7.1 四个决策块

| 模块 | 决策变量 | 实际负责的条件 |
|---|---|---|
| SRM：Schedule Recovery | x[o]：航班选择哪个执行/取消候选 | 每班恰选一个；战略航班执行；起降容量；地面库存代理；市场服务保留代理 |
| ARM：Aircraft Recovery | y[a,s]：飞机选择哪条航班串 | 每机恰选一条；执行航班被飞机覆盖；机型/地点/时间连续；终点和简化维修满足 |
| CRM：Crew Recovery | z[k,p]：机组选择哪个任务串 | 每组恰选一个；执行覆盖；OPERATE 资质、衔接、执勤；DEADHEAD 日程一致；终点 |
| PRM：Passenger Recovery | w[g,i]：旅客组选择哪个行程或 UNSERVED | 每组恰选一个；航段被执行；OD 与时间合法；剩余座位不超限 |

正式模型里的旅客组不可拆分：例如 15 人组只能整体选择一个行程或未承运。它不是把每个旅客作为可自由分流的连续流。

四块的联合正确性由五类 linking 表达：

~~~text
飞机对执行候选 o 的覆盖 = x[o]
机组 OPERATE 对候选 o 的覆盖 = x[o]
机组任务串含 DEADHEAD(o) → 该串的 z ≤ x[o]
旅客行程含 o → 该行程的 w ≤ x[o]
Σ(使用 o 的旅客组人数 × w) ≤ residual_capacity[o] × x[o]
~~~

飞机、机组和旅客只能使用真正被日程选中的执行候选。旅客容量是按候选给定的余座，没有通过 y 自动读取所分配飞机的物理座位；AIR Aircraft Schema 本身也没有座位数字段。机组搭乘的日程一致性与旅客座位占用不是同一条约束，当前上述座位 linking 只累计旅客组。

### 7.2 成本怎样计算

canonical 配置为 [phase2_test_costs_v1.json](../../data/costs/phase2_test_costs_v1.json)，单位是 abstract_cost_units，既有论文来源项，也有明确声明的实现假设，并非经过航司校准的经营成本。

| 项目 | 默认单价 | 成本归属 |
|---|---:|---|
| 航班起飞延误 | 1 / 航班分钟 | SRM |
| 取消航班 | 25000 / 班 | SRM |
| 改起飞机场、改到达机场 | 分别 5000 / 次 | SRM |
| 换飞机 | 0 / 次 | ARM |
| 调机 | 5 / 分钟 | ARM |
| 换机组 | 0 / 次 | CRM |
| 机组搭乘 DEADHEAD | 5 / 分钟 | CRM |
| 旅客到达延误 | 10 / 人分钟 | PRM |
| 旅客未承运 | 2500 / 人 | PRM |

总目标为 Schedule + Aircraft + Crew + Passenger，各项有唯一 owner，避免一个动作在多个模块重复收费。成本 override 在输入中显式记录，不能把调整后的数值误认成 canonical 常数。

### 7.3 用主 benchmark 看一次完整恢复

原计划在 B 机场的 [09:30,10:30) UTC 桶有 F2/F5/F8 三班起飞，但有效容量只有 2。F2/F5/F8 都有战略或服务约束，不能简单用取消消除冲突；现有候选与资源/旅客条件共同促成下列参考恢复：

1. F2 从 09:40 延误至 10:30，移出受限桶；到 C 的时间由 10:40 变为 11:30。
2. 原 AC1 来不及继续飞 11:00 的 F3，于是 AC4 接飞 F3，AC1 改飞 F10。
3. F10 延误 20 分钟至 11:30，衔接延误后的 F2。
4. P4 的 F2→F3 已无法衔接，15 人整体改走 B→A 的 F8。
5. F11 延误 10 分钟至 12:30，保护 P6 从 F10 的后续衔接。
6. 最终全部 12 班执行、3 班延误、2 次飞机重新分配、1 个旅客组改签、无人未承运。

航班延误合计 50+20+10=80 分钟；旅客加权到达延误为 30×50+18×10+12×10=1800 人分钟。因此默认目标为：

~~~text
80 × 1 + 1800 × 10 = 18080
~~~

飞机互换成本在默认配置里为 0。这里的最优性限于输入航班候选、生成 Profile 与给定旅客行程。早期 data/expected 中的文件仍把该方案记录为“人工可行参考、当时尚未定义货币目标”；当前 18080 的依据还包括后续成本合同、求解回归及 catalog Expected，不能把早期文件的 null objective 直接改读为最优目标。

### 7.4 正式算法怎样推进

正式入口为 application/solve_service.py 的 solve_request，核心调用 solve_benders_with_branch_and_price：

1. **航班主问题。** SRM 选择一套航班候选，加入飞机、机组、旅客成本的非负追索估计 θ。主问题给出当前研究模型的下界。
2. **固定这套日程。** 选中的执行候选交给飞机和机组子问题；PRM 在固定日程、显式旅客行程和余座上解整数模型。
3. **动态列生成。** 飞机/机组的 Restricted Master 先只保留少量列。Phase I 用人工变量寻找可行性；Phase II 优化真实成本。定价器在资源所属 DAG 上搜索负约化成本路径，把有改善的列加入，再解 LP。
4. **认证完整隐式 LP。** 只有在当前生成规则和分支条件下完成定价，才能把 RMP 的值认作相应完整 LP 的值；定价未结束时，不能直接用受限列池目标作完整模型下界。
5. **上界与下界分开。** 对已生成列做 binary ARM/CRM 可以给出可行整数上界；它本身不能证明未生成列也无法改善整数解。PRM 的显式整数解是该旅客候选集内的精确追索。
6. **更新 Benders 条件割。** 完整认证的不可行日程可加 no-good cut；认证的追索下界用于该完整日程的条件下界割。这里采用 correctness-first 的 Logic-based 结构，不能解释成适用于所有日程的经典 LP 对偶仿射割。
7. **处理整数缺口。** 先尝试 Phase 11 的 LP/整数界闭合；若核心中间状态为 INTEGRALITY_REQUIRED，再进入 Phase 12 Branch-and-Price。每个分支节点重新在合法的隐式列空间内做 CG，父节点列仅作为符合子分支条件的热启动候选。
8. **最终认证。** 精确整数追索回写条件割；直到 LB/UB 在容差内闭合，或因节点/轮次/求解限制返回未收敛等状态。最优返回前独立复算联合约束和目标。

对完整日程 s，令 n=|s|、match(x,s)=Σ(o∈s)x[o]。实现使用的代表性割为：

~~~text
已认证不可行：match(x,s) ≤ n - 1
追索成本下界：θ_owner ≥ L_owner(s) × [match(x,s) - n + 1]
已认证整数追索：θ_owner ≥ Q_owner(s) × [match(x,s) - n + 1]
~~~

相同完整日程时右端为该追索值；换成其他日程后右端不为正，由追索非负性保证有效。这样的条件割覆盖范围有限，算法正确性与大规模收敛速度应分别评价。

飞机分支优先按 tail-option assignment，必要时按 exact String；机组优先按带 OPERATE/DEADHEAD 类型的 follow-on，再用 typed leg 或 exact Pairing 兜底。分支后定价必须遵守对应限制。

### 7.5 生成规则和当前边界

- 飞机生成测试 Profile：默认最小过站 15 分钟，但 E1 覆盖为 0，保留主 benchmark 的兼容边界。
- 机组 Profile：最小衔接 0、单次执勤最长 480 分钟、最多 1 个 DEADHEAD、允许 idle。没有完整多日执勤与过夜休息模型；480 分钟是测试假设，不是对 CCAR/FAR 的合规声明。
- 旅客生成 Profile：MCT=0、最多 3 个飞行航段、允许 UNSERVED、不生成地面交通。它不是经过航司校准的 MCT 表。
- 维修是当前 Schema/候选规则中的简化满足性；不是完整维修任务、工位及持续时间排程。
- 正式 AIR 路线只接受 full scope，即 scope=None；Phase 4 的局部 Scope 能力保留在底层与测试中。
- 算法不会在正式求解内部创造新的航班时刻候选；v2 的候选编译发生在创建快照之前。
- 正式路线不接受预生成的飞机串/机组串；显式全列池主要用于早期阶段、Oracle 与回归对拍。
- AIR 使用 GurobiAdapter；厦航的 HiGHS 降级没有推广到这条核心路线。

## 8. 厦航路线的模型与求解细节

### 8.1 候选动作与离散时间

当前支持保留原计划、延误、取消、同机型换机尾，以及受规则约束的整数人数改签。不支持提前、跨机型替换、自动调机或联程拉直；这些比赛评分项会保留为零。

默认参数在 XmaSolveRequest 中：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| delay_step_minutes | 30 | 延误网格步长 |
| maximum_delay_minutes | 1440 | 最大生成延误范围；国内实际还受 1440 上限，国际受 2160 上限 |
| time_limit_seconds | 300 | 研究运行预算 |
| max_assignment_options | 100000 | 飞机—候选分配组合的预检查上限 |
| max_benders_iterations | 500 | Benders 轮次上限 |
| max_bp_nodes | 1000 | 分支节点上限 |
| max_cg_iterations | 1000 | 列生成轮次上限 |
| oracle_path_limit | 100000 | 显式基准路径数量限制 |
| mip_gap | 0 | 请求的 MIP gap 设置 |

候选不是单纯均匀网格：生成器加入最大延误端点，以及台风/机场关闭规则的精确边界时刻，然后过滤非法起降候选。窗口外航班只保留原时刻且冻结原飞机、取消和改签行为。

max_assignment_options 超限会明确拒绝输入，不会静默截断合法候选。提高这个数值只允许更大的模型通过预检查，不会减少变量或加速求解。候选最优也不等于连续时间、全动作空间下的最优。

### 8.2 为什么飞机与旅客必须联合求解

主要变量包括：

~~~text
x[o]：航班选中的执行/取消候选，二元
u[a,o]：飞机 a 是否执行候选 o，二元
飞机时空网络流或路径 λ[a,p]
resident[f]：原驻留旅客人数，整数
loss[f]：受扰损失人数，整数
sign[f,o]：从源航班 f 改签到执行候选 o 的人数，非负整数
~~~

每个航班恰选一个候选；执行候选恰有一架兼容飞机。飞机的初始地点、时间连续、过站、联程邻接、停机和机队终点平衡同时成立。

令 tc 为进港取消影响、tf 为转机失败影响、through_loss 为联程搭档取消影响。调整窗口内的执行航班先计算：

~~~text
N[f] = passengers[f] + through[f] - tc[f] - tf[f] - through_loss[f]
S[f] = Σ seats[a] × u[a,o]
overflow[f] = max(0, N[f] - S[f])
resident[f] = N[f] - overflow[f]
实际占座 = resident[f] + 接收改签人数 ≤ S[f]
未服务人数 = 按来源规则计算的 loss[f] - 送出改签人数
~~~

取消航班、冻结航班和联程第一段有单独账本分支，不能只套一个统一的“全网人数守恒”公式。源码先判进港取消，再判中转失败，避免同一转机关系在这两类里重复处理。

改签目标须同 OD、实际起飞不早于源原起飞且未取消；接收改签的航班不能同时继续送出改签。执行源只允许送出符合条件的中转失败/溢出人数，取消源还受来源普通旅客上限限制。

不同机尾即使同机型也可能有不同座位数；分配飞机会改变溢出、改签和未服务成本。因此厦航分解中的追索必须保留“飞机 + 旅客”的联合优化，不能沿用外生余座下彼此独立的 ARM/PRM 分解。

### 8.3 两套独立目标

天池 tianchi_2017 的以下常数来自项目附带评估器的 Configuration.java / ResultEvaluator.java，并由独立 Python evaluator 按当前支持动作复算：

| 项目 | 费用 |
|---|---|
| 取消航班 | 1200 × 航班重要系数 |
| 航班延误 | 100 × 延误小时 × 重要系数 |
| 同机型换机尾 | 原起飞不晚于 2017-05-06 16:00：15×重要系数；之后：5×重要系数 |
| 未服务旅客 | 4 × 来源账本人数 |
| 原驻留旅客延误 | 每人：0 小时为 0；(0,2] 为 1；(2,4] 为 1.5；(4,8] 为 2；(8,36] 为 3 |
| 改签旅客延误 | 每人延误小时 h：[0,6) 为 h/30；[6,24) 为 h/24；[24,36) 为 h/18；[36,48] 为 h/16 |

air_linear_v1 则默认采用：航班延误 1/分钟、取消 25000/班、换机尾 0、旅客延误 10/人分钟、未服务 2500/人；机组关闭，因此机组成本为 0。参数与天池常数分别维护。

两套目标不混合相加。比较不同算法必须固定数据、目标及其参数、候选网格、最大延误和边界条件。跨目标的总数值不能直接判断优劣，可分别复算目标并比较取消、延误、承运等业务指标。

### 8.4 四种算法及其用途

| algorithm | 做法 | 研究用途与代价 |
|---|---|---|
| joint_arc_flow | 在一个 MIP 中联立日程、飞机事件网络流及整数旅客账本 | 直接基准；不枚举所有路径，但细网格和多飞机会带来大量变量 |
| joint_path_oracle | 显式枚举合法飞机路径，再求联合整数模型 | 小实例正确性对拍；受 oracle_path_limit 限制 |
| benders_joint | 日程主问题 + 固定日程的联合飞机/旅客 MIP | 验证 Logic-based 分解；完整日程条件割可能较弱 |
| benders_cg_bp | 日程主问题 + 联合追索的飞机路径 CG 与 B&P | 不预枚举全路径；仍保留分配、旅客及其他整数变量 |

直接 arc 模型把机场时间事件之间的等待连接成地面弧，落地通常 50 分钟后释放；原短过站和指定联程用专用 shortcut 进入后续航班，防止错误接入同一时刻的其他航班。

厦航 Benders 主问题只负责航班成本与部分日程条件。固定日程后，子问题的认证成本要扣除主问题已计的航班成本，再生成追索条件割；合法整数解更新上界，只有认证不可行才加排除日程的割。

路径 CG 的 Phase I 为所有限制行加入人工变量，完整定价后人工目标仍为正才认证 LP 不可行。Phase II 恢复业务目标。定价是固定日程 DAG 上的精确最短路径，计入飞机选择、分配 linking、终点、联程、停机的对偶贡献，并独立核对 reduced cost。

B&P 优先按飞机分配 u 分支，再按其他未整数化的业务变量分支，每个节点重建受分支上下界约束的 RMP 并重新完成定价。路径列保持连续，通过整数业务分配及最终独立审计提取方案。

这些代码提供算法比较的能力，不能据此断言 Benders/CG/B&P 一定比直接联合模型快。已有实验中，小规模直接联合模型的表现明显更好；大规模仍需单独研究。

### 8.5 求解器降级、真实进度与预算

模型先用 gurobipy 构建，Gurobi 为主求解器。只有 Gurobi 优化抛出许可证规模错误 10010 时，XMA ScalableModel 才提取同一线性模型降级；其他 Gurobi 错误不会一概被吞掉。

- 大整数模型优先交给 highspy 原生 HiGHS，可发布 MIP incumbent、dual bound、节点数及协作取消回调。
- LP 降级使用 SciPy linprog/HiGHS，并恢复对偶，供定价使用。
- 原生 HiGHS 的 MIP 路径异常时，存在 SciPy milp/HiGHS 兼容兜底；该路径没有中间界回调，仅发布说明性的心跳。
- solver_fallback、mip_progress 和 solver_heartbeat 含义不同。心跳表示仍在执行，不能作为新的收敛点。
- XMA 仍依赖 gurobipy 构模及可启动的环境；这不是完全移除了 Gurobi 依赖的独立后端。

配置时限不是严格的端到端墙钟截止：预检查、候选生成、构模、矩阵转换、降级及审计会占用额外时间，某些阶段只在返回后检查剩余预算。实际运行耗时必须看 Run 和 diagnostics，不能把配置的 300 秒直接当作用户等待时间。

## 9. 已有结果到底证明到哪一步

### 9.1 2026-10-08 的冻结规模实验

原始记录位于 [direct/summary.json](../codex_reports/xma_experiments_20261008_direct/summary.json)、[decomposition/summary.json](../codex_reports/xma_experiments_20261008_decomposition/summary.json)。当时统一采用天池目标、60 分钟步长、最大延误 120 分钟、15 秒预算。

| 航班数 | 算法 | 状态 | 目标/UB | LB | 总耗时约 |
|---|---|---|---:|---:|---:|
| 30 | joint_arc_flow | optimal | 11444 | 11444 | 0.166 秒 |
| 103 | joint_arc_flow | optimal | 56897.62037 | 56897.62037 | 0.978 秒 |
| 508 | joint_arc_flow | not_converged，无完整 incumbent | — | — | 18.231 秒 |
| 30 | benders_joint | not_converged | — | 6900 | 15.187 秒 |
| 30 | benders_cg_bp | not_converged | — | 6900 | 15.204 秒 |
| 103 | benders_joint | not_converged | — | 24783.33333 | 15.221 秒 |
| 103 | benders_cg_bp | not_converged | — | 24700 | 15.218 秒 |
| 508 | benders_joint | not_converged | — | 121558.33333 | 16.321 秒 |
| 508 | benders_cg_bp | not_converged | — | 121508.33333 | 16.274 秒 |
| 2364 | 上述三种路线 | input_limit | — | — | 未进入正式求解 |

全量在该候选配置下有 361810 个飞机—候选组合，超过默认上限 100000。另有最大延误为 0、显式放大输入上限的全量探测；其 Benders master 不可行只证明这个非常受限的候选问题不可行，不能推广到允许充分延误的原始全量问题。

### 9.2 当前本机 .workbench 中的实际使用记录

2026-11-06 再次以只读连接核对：34 个草稿、27 个 revision、27 个快照、27 次 Run、4462 条事件、98 个内容寻址产物。草稿按业务分为 AIR 16 个、XMA 18 个；Run 为 AIR 9 次 optimal、XMA 12 次 optimal 和 6 次 not_converged。全部 Run 的 Job 状态均为 completed。

这些数量包含重复尝试和界面验证，不是相互独立的科学重复实验，也不等于 34 个独立数据集。随机草稿已出现 29、102、114、510 班样本，不能将某个样本的表现外推到所有同规模样本。

以下为保存结果的代表记录；30/103 班旧快照有些缺少后来增加的 subset_selection 字段，按实际航班数、机尾和 dataset_id 识别，不能因缺少该字段就称其为“2364 班全量”。

| 本地日期 | 样本与算法 | 步长 / 最大延误 | 结果 | 实际求解耗时 |
|---|---|---|---|---:|
| 2026-10-20 | 整机尾 30 班，joint_arc_flow | 30 / 1440 分钟 | optimal，8464，独立审计通过 | 6.634 秒 |
| 2026-10-20 | 整机尾 103 班，joint_arc_flow | 30 / 1440 分钟 | optimal，42473.56481，独立审计通过 | 231.282 秒 |
| 2026-11-02 | 随机 29 班，joint_arc_flow | 30 / 1440 分钟 | optimal，9693.16667，独立审计通过 | 5.189 秒 |
| 2026-11-02 | 随机 102 班，joint_arc_flow | 30 / 1440 分钟 | optimal，44085.4375，独立审计通过 | 1047.122 秒 |
| 2026-11-02 | 随机 510 班，joint_arc_flow | 30 / 1440 分钟 | not_converged，无 UB | 580.511 秒 |
| 2026-11-03 | 固定 508 班，joint_arc_flow | 30 / 1440 分钟 | not_converged，无 UB | 10438.486 秒，约 2.90 小时 |
| 2026-11-04 | 固定 508 班，benders_cg_bp | 30 / 1440 分钟 | not_converged，LB=91004.16667，无 UB | 20011.150 秒，约 5.56 小时 |

两个最近 508 班运行：

- joint_arc_flow，Run `dbe486a2-e823-45fb-99d0-3239cdca3d8c`：14399 个航班候选，5089430 个变量、1604803 条约束，实际求解器 HiGHS，记录 LB=-10656806.45231，没有可行 incumbent。
- benders_cg_bp，Run `80d69dad-d2b5-48d1-8dec-0a4dfa103637`：同为 14399 个候选，累计记录 20397 个飞机路径列、745 次 CG 迭代、5 个 BP 节点、5 个已访问日程；终止原因 bp_budget_or_node_limit，没有可行 incumbent。

负 LB 是保存的求解器下界，不代表找到了负业务成本方案；没有 UB 时也没有可解释的相对 Gap。列数与节点数是实现记录的累计统计，不宜当作同时驻留的唯一列数量。

这些结果说明：30/100 班已经存在经审计的最优解；约 500 班的细网格模型仍有明显规模和收敛困难。变量和约束规模为后续性能分析提供了线索，但本次没有做性能剖析，不能把慢的原因唯一归结为某一个因素。仓库现有记录中尚未取得 2364 班全量恢复最优解。

### 9.3 与官方 JAR 的验证范围

[baseline_verification.json](../codex_reports/xma_jar_validation_20261008/baseline_verification.json) 记录 103 班派生工作簿的 Java/Python 分数均为 56830.37037；另一个 [verification.json](../codex_reports/xma_jar_validation_20261008/verification.json) 记录分数均为 56870.37037，差值为 0。

后者明确添加了两条合成中转关系，覆盖进港取消和转机失败；派生工作簿排除了跨子集的中转。具体见 [fixture_note.md](../codex_reports/xma_jar_validation_20261008/fixture_note.md)。它与保留外部进港边界的普通子集研究不是同一个输入，分数不能直接横向比较；也不能据此声称已验证原始全量比赛实例的全部动作组合。

## 10. 结果、可视化与审计怎样解释

| 模式 | 表达什么 | 不应推断什么 |
|---|---|---|
| Original | 输入中的原计划、原资源 | 原计划一定满足受扰后的条件 |
| Impact | 编译后的有效容量、直接暴露、原资源序列上的风险 | 某航班必然延误/取消，或该传播就是实际因果链 |
| Recovered | 求解决策形成的完整恢复方案 | 存在可行 incumbent 就必然已证明最优 |
| Delta | 恢复相对原计划的字段/资源/行程变化 | 所有变化互斥，或必须只属于一种标签 |

Changed/Unchanged 是完整划分，Changed 可同时含取消、时刻、机场、飞机、机组等多种标签。AIR 结果构造器只在 optimal 时提供正式恢复决策；非 optimal 时仍可保留诊断和界，不伪造恢复图。

当前 XMA 代码更宽松且有明确依据：即使 not_converged，只要有完整决策且独立业务审计 valid，也可展示该 incumbent 并导出 CSV；最优性状态另行保留。当前 comparison.py 和 visualization.py 都做了这一处理。部分旧用户指南写成“Recovered 必须 optimal”，对这条 XMA 路径已经不完整。

各图层按实际数据可用性开关。XMA 没有机组数据，没有 AIR 式旅客 Itinerary 对象；旅客明细以 passenger_allocations 航段账本为主。普通机场容量未提供时，容量热力层也不能凭空显示一个真实容量。缺少选中列产物的历史运行可能只显示降级后的资源信息。

AIR Expected 与独立约束审计也不同：

- catalog 可声明目标、必选航班候选和业务指标。
- 当前 v2 build_audit 中的 expected_check 只直接核对优化状态与总目标，没有逐项检查 catalog 的所有 required_metrics/required_flight_options。
- 完整的业务不变量还要结合回归测试、独立诊断及结果字段核验，不能把两个 Expected 布尔值当作所有研究断言都已通过。

Job completed 表示程序正常执行完毕；它可以对应 optimal、infeasible 或 not_converged。只有输入错误或执行异常才是另一类问题。infeasible 的含义限于当前业务模型及候选范围；没有 incumbent 的 not_converged 不等于不可行。

绝对 Gap 通常为 max(0,UB-LB)，相对 Gap 为该值除以 max(|UB|,1)。缺少任一有效界时显示“—”。应用中某些旧 diagnostics 的 gap 表示绝对差，不能直接读成百分数。

AIR 示例时间带 Z/UTC；厦航导入按 Asia/Shanghai 解释，展示层多处使用 UTC 刻度。解释航班及台风时间时应始终核对时区标签。

## 11. 研究使用时应固定的口径

一次可解释的算法比较至少应固定：业务路线、源文件哈希、实际选中航班/机尾及边界、目标及成本参数、延误网格/最大延误、旅客行程或改签范围、容量语义、生成 Profile、求解器版本和许可证、运行限制。

XMA 的 study_signature 会把数据样本标识、目标及部分候选参数纳入比较标识，排除算法和预算，便于找到可比历史运行。它是代码实现的筛选机制，完整科学复现仍应保存整个快照、实际 runtime_controls、输入/有效输入哈希和环境。

以下解释边界尤其重要：

1. 同一航班数不代表同一问题：随机样本、飞机可互换性、衔接和台风暴露可能不同。
2. 网格和最大延误改变可行域：2026-10-08 的 60/120 实验不能与后来的 30/1440 实验当作同一算法速度对照。
3. 目标改变最优方案：天池低取消成本与 AIR 线性高未承运成本会导向不同取舍。
4. 包含完整原机尾轮转不代表消除了子集外影响：外部进港被固定，外部出港影响被排除。
5. 给输入上限放行和真正求得可行解是两件事；Ready、开始建模、生成很多列也都不等于已找到恢复方案。
6. Oracle 验证、约束覆盖登记、一次独立审计、全量业务验证与跨机器性能研究，是不同层级的证据。
7. 快照记录 Git commit、dirty 和 diff_hash，但不会把全部源代码打包；要复现未提交版本，应另行保存对应代码与依赖。
8. 历史运行及本次读取记录不等于当前代码版本下重新测得的性能；本次没有重跑任何优化或长时实验。

已有资产适合分别研究：AIR 小例子的算法正确性及模块耦合，P1–P5 的进度与规模行为，厦航子集的业务目标和候选范围敏感性，以及不同联合/分解表示的收敛情况。当前不能把这些成果表述为真实航司生产就绪或全量快速最优。

## 12. 代码阅读导航与本次核查

| 关注点 | 建议阅读位置 |
|---|---|
| v2 页面入口 | [App.tsx](../../frontend/v2/src/App.tsx)、[api.ts](../../frontend/v2/src/api.ts) |
| Case 如何变成求解输入 | [case_service.py](../../backend/application/case_service.py)，_complete_bundle、load_case |
| 草稿、规则、候选编译 | [compiler.py](../../backend/workbench/compiler.py)，compile_draft、_compile_capacity、_generate_bundle |
| 工作台数据合同 | [workbench.py](../../backend/schemas/workbench.py)，DraftDocument、SnapshotRecord、RunRecord |
| 持久化及内容哈希 | [storage.py](../../backend/workbench/storage.py)，content_hash、create_snapshot、put_artifact |
| 队列、取消、worker 分派 | [run_manager.py](../../backend/workbench/run_manager.py)、[worker.py](../../backend/workbench/worker.py) |
| AIR 输入就绪性与正式服务 | [solve_service.py](../../backend/application/solve_service.py)，solve_readiness、solve_request |
| AIR 20 项本地约束元数据 | [constraint_registry.py](../../backend/core/constraint_registry.py) |
| AIR 五类联合 linking/审计 | [integrated_oracle.py](../../backend/core/integrated_oracle.py) |
| AIR 正式 Benders/整数追索 | [benders_branch_and_price.py](../../backend/core/benders_branch_and_price.py) |
| AIR 定价与分支 | backend/core 下 aircraft_string_*、crew_pairing_* |
| AIR 恢复结果独立构造 | [result_builder.py](../../backend/application/result_builder.py) |
| 厦航数据、来源与整机尾抽样 | [importer.py](../../backend/business/xma/importer.py)，load_workbook、select_subset |
| 厦航候选、网络及规则 | [rules.py](../../backend/business/xma/rules.py) |
| 厦航联合方程与物理座位 | [model.py](../../backend/business/xma/model.py)，build_joint |
| 厦航四算法、CG/B&P | [algorithms.py](../../backend/business/xma/algorithms.py) |
| 厦航目标和独立评分 | [objectives.py](../../backend/business/xma/objectives.py)、[evaluator.py](../../backend/business/xma/evaluator.py) |
| 厦航求解器降级与回调 | [solver.py](../../backend/business/xma/solver.py) |
| 统一结果语义及审计范围 | [comparison.py](../../backend/workbench/comparison.py)、[visualization.py](../../backend/workbench/visualization.py) |
| 真实曲线与历史比较 | [solveMonitor.ts](../../frontend/v2/src/pages/solveMonitor.ts) |
| 验证/压力资产生成 | [validation_suite.py](../../backend/data_generation/validation_suite.py) |

本次执行的验证：

- 清点全部数据文件及 manifest，确认 20 个 micro、5 个 stress 与导入类型。
- 实际只读解析厦航原工作簿及 20/100/500 固定子集，业务校验均无错误。
- 逐个装载 8 个 catalog Case，核对 Scenario 校验与 v2 编译状态。
- 只读读取 SQLite 和内容寻址 gzip 产物，交叉核对近期运行输入、预算、目标、界和模型规模。
- 运行下列既有测试，6 项通过、排除的 P1 优化测试未运行：

~~~powershell
python -m pytest tests/unit/test_workbench_compiler.py tests/unit/test_validation_data_suite.py -k 'not frozen_p1_reference_solves' -q
~~~

这些测试包含类型化容量规则、旧容量防重复应用、冻结文件 SHA-256、micro/stress 输入合同与就绪性、固定种子生成确定性。未重新执行 Gurobi/HiGHS 求解、性能校准或浏览器端到端测试；本次只新增说明文档及工作报告。

