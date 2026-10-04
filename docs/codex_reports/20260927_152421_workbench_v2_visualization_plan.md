# Workbench v2 可视化板块实施计划

## 1. 现状结论

Workbench v2 已有基础图形能力，但没有完整保留旧版可视化的核心体验：

- 侧栏没有独立的“可视化”入口；图形被分散在“扰动影响”和“方案对比”中。
- `TimeSpaceNetwork` 目前仅绘制机场泳道、航班线和端点，没有 UTC 时间刻度、箭头、扰动时域带、容量背景、延误位移连线等关键语义。
- v2 的扰动图没有消费 `typed_disruptions` 与 `capacity_changes` 来绘制扰动窗口及基线/有效容量差异。
- 飞机、机组、旅客目前在 Compare 页主要以表格呈现，没有轮转/执勤/行程甘特或时间线。
- 容量图只选取一组数据绘制，不能直观看到基线、有效容量与恢复负荷之间的对照。
- 当前公开结果丢失了部分完整可视化所需的数据：机组 REST/GROUND_TRANSFER 的时间地点、选中动态 Pairing 的完整 duty、飞机 ferry 腿详情、旅客 surface 段等。前端不能据此猜测。

因此新增独立 `/workbench-v2/visualization` 页面，并以服务端生成的 canonical visualization model 为唯一数据源。

## 2. 信息架构

侧栏调整为：

`数据设计 → 扰动影响 → 求解 → 可视化 → 方案对比 → 审计`

- “扰动影响”继续负责编译、错误修复、候选规模和输入证据。
- “求解”继续负责实时 LB/UB、Gap、割、列、节点和事件流。
- “可视化”成为原计划、扰动暴露、恢复方案和差异分析的主入口。
- “方案对比”保留结构化明细表和精确字段对照，避免与图形探索混为一体。

页面遵守“一次一个核心视觉中心”：顶部为公共状态和控制，中央只显示当前图，右侧为所选实体的证据抽屉；不把所有图堆成 dashboard。

## 3. 页面交互模型

### 3.1 公共控制

- 数据源：当前草稿/编译快照、当前运行、历史运行。
- 语义模式：`Original / Impact / Recovered / Delta`。
- 图形标签：航班时空图、飞机甘特、机组甘特、旅客行程、容量热力图、传播链、成本、延误。
- 范围过滤：UTC 时间窗、机场、航班、飞机、机组、旅客组、Changed/Unchanged、变化类型、直接/传播暴露。
- 共享选择：选择航班后，在全部图形中联动相关飞机、机组、旅客、扰动规则和容量区间；实体选择使用 `{type, id}`，不再只存一个含义模糊的字符串。
- URL 保存 run、mode、view、selected entity 和主要筛选，支持刷新恢复与深链。

### 3.2 四种模式的严格语义

- `Original`：只绘制基线计划、原飞机/机组/旅客路径和基线容量。
- `Impact`：绘制基线运行图、编译后的扰动时域、有效容量、直接暴露及资源链传播风险；禁止使用恢复决策颜色。
- `Recovered`：仅在 optimal 且结果完整时绘制求解后的计划、资源与旅客方案。
- `Delta`：基线使用中性 ghost，恢复方案使用变化类别；取消、延误、O-D、block time、飞机和机组改派全部可见。
- 非 optimal 运行禁用 Recovered/Delta，但保留 Original、Impact 和失败证据。
- 暴露和传播只描述“规则证据/风险路径”，不得表述为某恢复决策的因果原因。

## 4. 核心图形

### 4.1 机场—时间航班箭头图（默认主图）

- 横轴为 UTC，纵轴为机场泳道；航班从起飞机场/时刻指向到达机场/时刻，必须有方向箭头。
- 显示小时/日期刻度、跨日分隔、当前可见时间窗、缩放、平移和 brush 范围选择。
- Impact 模式在机场泳道上绘制扰动时域带：规则类型、开始/结束边界、到达/起飞适用方向、基线和有效容量、截断警告。
- 直接扰动航班用粗实线与明确标签；传播风险用不同线型并标明飞机链或机组链；正常航班保持中性。
- Delta 模式同时绘制原计划 ghost 和恢复箭头；用连接线表现时间/航路位移，用取消标记表现取消，不用“消失”代替取消。
- 变化主颜色按：取消 → O-D → 时间 → 飞机 → 机组 → unchanged；所有次级标签仍保留。
- 点击航班打开证据抽屉：原计划、规则暴露、传播来源、恢复时刻/O-D、飞机、机组、旅客、变化标签、关联容量区间。
- 500 航班使用 ECharts Canvas/custom series 分层绘制；不为每个航班创建大量 React SVG 节点。

### 4.2 飞机轮转甘特图

- 每架飞机一条泳道，统一 UTC 时间轴。
- Original 显示原轮转；Recovered 显示恢复轮转；Delta 同时显示原轮转 ghost 与恢复段。
- 区分正常执行、飞机改派、ferry/positioning、地面等待和取消造成的轮转缺口。
- 标记初始机场、最终机场要求、实际最终机场、机型、维护要求与维护站；仅展示数据中真实存在的维护信息，不虚构维护时段。
- 点击任一段联动到航班箭头图和相关机组/旅客。

### 4.3 机组执勤甘特图

- 每个机组一条泳道，显示 duty 边界。
- 明确区分 `OPERATE / DEADHEAD / REST / GROUND_TRANSFER`，同时使用文本/图案，不能只靠颜色。
- 展示原 pairing、恢复 pairing、执勤衔接、起始/期末机场、改派航班和 deadhead。
- REST 与 GROUND_TRANSFER 只有在服务端返回完整起止时间和地点时才绘制；缺失时显示“结果未提供”，不得推断。

### 4.4 旅客行程图

- 以旅客组为单位展示原行程与恢复行程时间线，标明人数。
- Impact 模式标出首次受影响航班及后续风险段。
- Recovered/Delta 显示改签、surface 段、到达延误、未承运和最终目的地。
- 支持按受影响人数、延误、未承运、是否改签筛选。
- 小规模可用路径/Sankey，大规模默认使用分组时间线，避免 Sankey 变成不可读的线团。

### 4.5 机场容量热力图

- 机场为行、时间区间为列；到达/起飞分别切换。
- 可切换基线容量、有效容量、原计划负荷、恢复负荷、余量和利用率。
- Delta 直接显示容量变化和负荷变化；零容量、超容量、刚好 binding 使用不同形状/标签。
- 点击单元格联动该机场时域内的扰动规则和航班。
- 区间必须采用与编译器相同的半开区间语义 `[start, end)`。

### 4.6 扰动传播链

- 展示“直接暴露航班 → 飞机/机组资源链 → 下游风险航班”。
- 默认只显示所选航班的局部邻域和传播层级，禁止一次性绘制全量 hairball。
- 边标明资源类型、资源 ID、前序航班和传播层级；直接规则节点可回溯到 rule ID 与容量区间。
- 图中固定显示“传播风险不是求解决策因果解释”。

### 4.7 成本与延误

- 成本瀑布图：schedule、aircraft、crew、passenger 四分量必须与 objective total 对平；若后端提供明细，再下钻到取消、延误、改派、deadhead、旅客延误和未承运等成本项。
- 延误图：起飞/到达延误直方图、分位数或 ECDF、按航班点图；必须覆盖仅到达延误。
- Changed/Unchanged 分区完整，取消航班不被错误计入数值延误。

### 4.8 可选后续：求解方案演进回放

- 基于真实 trace 的 incumbent/schedule candidate 事件提供迭代滑块，回放各轮候选方案的取消/延误/变化数量。
- 只有事件中存在真实候选排班时启用，禁止生成伪进度或补造中间方案。

## 5. 服务端可视化数据合同

新增只读接口：

- `GET /api/v2/drafts/{draft_id}/visualization`：Original/Impact，绑定 working hash 或 compiled hash。
- `GET /api/v2/runs/{run_id}/visualization`：四模式完整模型，绑定 immutable snapshot 和 result。

返回 `VisualizationModel v1`，至少包含：

- metadata：snapshot/run/input hash、optimization status、UTC 范围、可用图层。
- disruption windows：规则、机场、时域、运动方向、基线/有效容量、应用规则和警告。
- flight legs：original/effective/recovered、impact、change flags、primary change、原/恢复飞机和机组。
- propagation edges：source/target、resource type/id、层级和证据来源。
- aircraft timelines：完整的原/恢复 segment、ferry、地面间隔、初始/最终站和维护元数据。
- crew timelines：完整 duty 和 OPERATE/DEADHEAD/REST/GROUND_TRANSFER segment。
- passenger journeys：原/恢复 flight 与 surface segment、人数、延误、未承运。
- capacity cells：baseline/effective/recovered 的容量、负荷、slack、利用率和 binding。
- objective breakdown、delay distribution、recovery actions。

服务端必须从 immutable snapshot、compile preview、求解结果和选中列产物构建该模型；前端只做显示和过滤，不重复推导业务含义。

为补足当前数据缺口：

- v1 `RecoveredResult` 保持兼容，不塞入破坏合同的大对象。
- v2 worker 在求解完成时额外保存“selected solution columns”内容寻址 artifact。
- artifact 保存选中 Aircraft String 的完整 leg、Crew Pairing 的完整 duties/segments、Passenger Itinerary 的完整 segments 和成本组成。
- comparison/visualization builder 通过 option ID 关联完整航段，保留 ferry、deadhead、rest、ground transfer、surface。
- 如果历史运行没有该 artifact，接口返回明确的 layer availability/reason，并降级为已有数据，不猜测。
- 大模型响应支持 gzip、ETag/input hash；500 航班仍一次返回可视化所需的规范化数据，超出后再引入分片。

## 6. 前端结构

新增：

- `pages/VisualizationPage.tsx`
- `visualization/VisualizationToolbar.tsx`
- `visualization/FlightTimeSpaceChart.tsx`
- `visualization/ResourceGanttChart.tsx`
- `visualization/PassengerJourneyChart.tsx`
- `visualization/CapacityHeatmap.tsx`
- `visualization/PropagationGraph.tsx`
- `visualization/CostWaterfall.tsx`
- `visualization/DelayDistribution.tsx`
- `visualization/EntityEvidenceDrawer.tsx`
- `visualization/selectors.ts` 与严格 TypeScript 类型

技术取舍：

- 航班网络、甘特、容量、成本和延误使用 ECharts Canvas/custom series。
- 传播链使用按需渲染的 ECharts graph 或轻量 SVG，只绘制选中邻域。
- 统一 time scale、颜色/线型 token、tooltip、legend 和 cross-selection；不在各组件中各算一套状态。
- 组件按图形 lazy-load，避免 ECharts 全量首屏包体继续增大。
- `prefers-reduced-motion` 下关闭位移动画；键盘可切换图层、聚焦实体并打开详情。
- 390/768px 为只读简化模式：保留运行选择、模式、航班时空图、变化航班和详情；复杂甘特提供横向局部浏览，不提供密集编辑。

## 7. 实施顺序

### 阶段 A：合同与主图恢复（P0）

1. 定义 `VisualizationModel`、availability 和 hash 规则。
2. 增加 draft/run visualization API 与合同测试。
3. 新增侧栏入口、路由和共享选择状态。
4. 实现机场—时间航班箭头图、UTC 时间轴、扰动时域带、Original/Impact/Recovered/Delta。
5. 迁移旧版可复用语义：直接暴露、传播风险、扰动窗口、航班详情、恢复 ghost 和取消标记。

### 阶段 B：资源甘特与容量（P1）

1. 保存选中列 artifact，补全动态 Aircraft String/Crew Pairing 的段信息。
2. 实现飞机轮转甘特与机组执勤甘特。
3. 实现基线/有效/恢复容量热力图和 binding/slack。
4. 完成跨图实体选择和筛选联动。

### 阶段 C：旅客、传播、成本与延误（P1）

1. 补全旅客 surface 段并实现旅客行程时间线。
2. 实现局部传播链。
3. 实现成本瀑布和延误分布，增加成本求和校验。
4. 为每个视图加入 empty/partial/non-optimal 状态。

### 阶段 D：性能、无障碍与收尾（P2）

1. 500 航班 fixture 下验证首图、缩放、筛选、切换和选择性能。
2. 完成 Vitest、MSW、Playwright、axe、视觉快照和 390/768/1440 响应式测试。
3. 更新 README、用户指南、人工验收清单和 OpenAPI。
4. 旧版可视化在 v2 达到验收门槛前继续保留作为对照，不先删除。

## 8. 验收标准

- 8 个现有 Case 均能进入可视化页；没有结果时仍可看 Original/Impact。
- 扰动机场、时域边界、规则类型和有效容量与 compile preview 完全一致。
- 每个航班恰好属于 normal/direct/downstream；传播边可以回溯到资源与直接暴露源。
- optimal 结果的 changed + unchanged 等于航班总数；arrival-only delay、取消、改航、飞机/机组改派全部显示正确。
- Original/Impact 绝不使用恢复决策样式；非 optimal 不绘制恢复方案。
- 飞机恢复轮转、机组 OPERATE/DEADHEAD/REST/GROUND_TRANSFER、旅客 flight/surface/unserved 均与选中列 artifact 一致。
- 基线/有效/恢复容量负荷可复算，slack/binding 正确，区间边界一致。
- 成本明细之和等于四分量，四分量之和等于 objective total。
- 图形选择在航班、飞机、机组、旅客和容量之间一致联动，刷新后由 URL 恢复。
- 500 航班视图不产生未捕获异常；参考 CI/机器记录首图 p95、缩放/筛选响应和内存基线，性能退化作为门禁。
- 390/768/1440 无 body 横向溢出；核心只读操作可键盘完成；axe 无严重/关键问题；非颜色线型和文本标签可识别状态。
- 新旧测试保持全绿，新增可视化合同、边界、交互和视觉回归测试。

## 9. 明确边界

- 不从图形推导新的求解决策或因果关系。
- 不虚构缺失的维护窗口、REST/地面转运时间或 ferry 航段；先补服务端 artifact。
- 不把所有图同时堆叠在一个 dashboard；通过标签切换主视觉。
- 不改变现有数学模型、最优性语义和 v1 API 合同。
- 首版不做地图地理投影；机场—时间图是运营时空图，不是地理航线地图。
