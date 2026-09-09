# Phase 0.5 可视化页面开发说明（供 Codex 直接执行）

> 仓库：`AdmiralJin/flight_recovery_4_dimension_OR_only`  
> 目标分支基线：当前 `main`  
> 本阶段定位：**Phase 0 数据层之上的只读可视化层**  
> 核心原则：**不实现 OR，不伪造恢复结果，不改变现有 Scenario Schema，不引入前端框架。**

---

## 1. 任务目标

在现有数据工作台中增加一个一级 `Visualization` 视图，让用户能直观看到：

1. **时空网络图**：机场 × 时间 × 航班方向；
2. **扰动覆盖层**：扰动发生在哪个机场、哪个时间段，哪些航班直接暴露，哪些后续航班存在传播风险；
3. **资源联动详情**：点击航班后，查看其飞机、机组、旅客及上下游链；
4. **机场容量热力图**：查看给定容量时间桶内的计划进港/离港航班数与容量的关系。

机场拓扑图可作为小型辅助图，但不是第一版核心验收项。

最终用户应能在同一个浏览器工作台中完成：

```text
Load / Import / Edit
        ↓
     Validate
        ↓
Visualization
        ↓
直观看原计划 + 扰动 + 资源传播风险
```

---

# 2. 当前仓库事实与必须遵守的约束

当前前端是：

```text
frontend/
├─ index.html
├─ css/
│  └─ styles.css
└─ js/
   ├─ api.js
   ├─ app.js
   ├─ results.js
   └─ tables.js
```

当前技术栈：

- FastAPI 提供后端与静态文件；
- 原生 HTML / CSS / JavaScript ES modules；
- 没有 React、Vue、npm、Webpack、Vite 等构建链；
- 当前编辑场景只存在 `frontend/js/app.js` 的 `state` 内存变量中；
- 当前后端已经有 `/api/validate`；
- Phase 0 不含优化模型。

因此本任务必须遵守：

### 2.1 不创建独立、无法共享状态的第二套网页

**不要**创建一个完全独立的 `visualization.html` 并让它自己重新加载 example。

原因：

当前人工修改后的场景只在 `app.js -> state` 中，页面跳转后会丢失。

正确做法：

```text
同一个 index.html
      │
      ├── Data Editor
      │      └── 使用 state
      │
      └── Visualization
             └── 使用同一个 state 的校验后快照
```

### 2.2 不新增后端可视化 API

第一版所有可视化数据都可以从当前 Scenario 推导。

不要新增：

```text
/api/visualization/*
```

继续复用：

```text
POST /api/validate
```

### 2.3 不新增或修改 OR / Solver

严禁为了展示效果：

- 自动计算航班实际延误；
- 自动取消航班；
- 自动换飞机；
- 自动换机组；
- 自动改签旅客；
- 生成所谓 recovered schedule。

当前 Visualization 只能展示：

```text
Original schedule
+
Known disruption
+
Deterministic exposure / propagation-risk analysis
```

它不是优化结果。

### 2.4 不修改核心 Scenario Schema

第一版不为机场增加经纬度，不增加 solver result 字段。

当前：

```text
Airport
- airport_id
- name
```

保持不变。

真实地理地图以后如需要，单独维护显示层机场坐标参考数据，不污染 OR 核心 Schema。

### 2.5 不引入前端框架或大型图表依赖

第一版继续使用：

- 原生 JS；
- SVG；
- HTML；
- CSS Grid / Flex。

不要引入：

- React；
- Vue；
- ECharts；
- D3；
- Plotly；
- npm 构建系统。

原因：当前功能完全可以用原生 SVG 完成，优先保持项目简单、离线可用、容易审计。

---

# 3. 页面总体结构

## 3.1 新增一级视图切换

在现有 command bar 下方、原数据 tabs 上方加入：

```text
[ Data Editor ] [ Visualization ]
```

建议 DOM：

```html
<nav class="view-switcher" aria-label="Workbench view">
  <button ...>Data Editor</button>
  <button ...>Visualization</button>
</nav>
```

不要把 `Visualization` 混入现有：

```text
Scenario
Airports
Flights
Aircraft
Crew
Passengers
Airport Capacity
Disruptions
```

因为这些是 **数据 section tabs**，而 `Visualization` 是更高一级的工作模式。

页面逻辑应为：

```text
Data Editor
    ├─ command bar
    ├─ 8 个现有 section tabs
    ├─ workspace
    └─ validation panel

Visualization
    ├─ visualization toolbar
    ├─ time-space network
    ├─ selected-object detail
    └─ capacity heatmap
```

现有顶部 `Load Example / Import / Export / Reset All / Validate` 建议保持全局可见。

---

# 4. 文件修改计划

建议最终结构：

```text
frontend/
├─ index.html                     # 修改
├─ css/
│  ├─ styles.css                  # 少量通用修改
│  └─ visualization.css           # 新增
└─ js/
   ├─ api.js                      # 原则上不改
   ├─ app.js                      # 修改：一级视图与状态协调
   ├─ results.js                  # 原则上不改
   ├─ tables.js                   # 原则上不改
   └─ visualization.js            # 新增：全部可视化推导与渲染

tests/
└─ manual/
   ├─ phase0_frontend_checklist.md
   └─ phase0_5_visualization_checklist.md   # 新增

README.md                         # 修改：增加 Visualization 使用说明
```

如实现过程中发现少量通用 CSS 应继续放入 `styles.css`，但所有图形专用样式优先放在 `visualization.css`。

---

# 5. 状态管理设计

这是本任务最重要的工程约束之一。

当前：

```js
let state = null;
let baseline = null;
let activeSection = "scenario";
```

增加：

```js
let activeView = "data";
```

推荐仅保留一个真正可编辑的数据源：

```text
state = authoritative editable scenario
```

Visualization **不得维护第二份可编辑 scenario**。

## 5.1 进入 Visualization 时先校验

用户点击 `Visualization`：

```text
current state
    ↓
validateScenario(state)
    ↓
valid?
 ┌───────┴─────────┐
 yes               no
 ↓                 ↓
normalized_data    阻止绘图
 ↓                 显示 validation 错误
render             提供 Back to Data Editor
```

伪代码：

```js
async function openVisualization() {
  const result = await validateScenario(state);

  if (!result.valid) {
    showValidation(result);
    showVisualizationBlocked(result);
    return;
  }

  showValidation(result);
  renderVisualization(result.normalized_data);
}
```

要求：

- **不要**因为校验通过就偷偷覆盖用户的 `state`；
- `normalized_data` 只作为本次可视化只读输入；
- 原始 `state` 仍然是 Data Editor 的唯一编辑源；
- Validation 失败时不能继续画“半正确”的图。

## 5.2 切回 Data Editor

切回时：

- 不重置 `state`；
- 不重置 `activeSection`；
- 不重新加载 example；
- 保留用户刚才正在编辑的 section。

## 5.3 全局按钮在 Visualization 下的行为

### Load Example

载入后：

- 更新 `state`；
- 更新 `baseline`；
- 如果当前处于 Visualization，则重新校验并重新绘图。

### Import JSON

继续使用当前逻辑：

- 先校验；
- 成功后更新 `state` 和 `baseline`；
- Visualization 激活时重新绘图。

### Reset All

重置 `state = clone(baseline)` 后：

- Data Editor：正常重新渲染；
- Visualization：重新校验并绘图。

### Export JSON

始终导出 `state`，不是可视化派生对象。

---

# 6. Visualization 页面布局

桌面端建议：

```text
┌──────────────────────────────────────────────────────────────┐
│ Visualization toolbar                                        │
│ [Original Plan] [Disruption Overlay] [Recovered disabled]    │
│ Legend                                                       │
├──────────────────────────────────────┬───────────────────────┤
│                                      │                       │
│       Time-Space Network             │  Selected Flight      │
│       主图，约 70%                    │  Resource Detail       │
│                                      │  约 30%               │
│                                      │                       │
├──────────────────────────────────────┴───────────────────────┤
│ Airport Capacity Heatmap                                    │
└──────────────────────────────────────────────────────────────┘
```

移动端：

```text
Toolbar
↓
Time-Space Network（允许组件内部横向滚动）
↓
Selected Flight Detail
↓
Capacity Heatmap（允许组件内部横向滚动）
```

禁止整个网页发生不可控的横向溢出。

---

# 7. Visualization 顶部模式

加入三个模式：

```text
Original Plan
Disruption Overlay
Recovered Plan
```

## 7.1 Original Plan

显示：

- 机场；
- 航班；
- 时间；
- 原始飞机 / 机组 / 旅客关联。

隐藏：

- disruption 红色覆盖；
- direct exposure；
- downstream risk。

作用：单纯回答“原计划是什么”。

## 7.2 Disruption Overlay

在原计划基础上增加：

- 扰动时间区域；
- 直接暴露航班；
- 下游传播风险；
- 受影响资源信息。

这是当前 Phase 0.5 的默认核心视图。

## 7.3 Recovered Plan

按钮必须存在但禁用：

```text
Recovered Plan
Available after optimization
```

不要伪造任何恢复数据。

---

# 8. 核心组件一：时空网络图

这是整个 Visualization 的主图。

## 8.1 坐标含义

横轴：

```text
时间
```

范围严格使用：

```text
scenario.recovery_window.start_time
→
scenario.recovery_window.end_time
```

纵轴：

```text
airport
```

每个机场一条水平 lane。

例如：

```text
C |                    ●
  |                  ↗
B |         ●───────
  |       ↗
A | ●
  +--------------------------------→ Time
```

## 8.2 航班绘制

每个 Flight：

```text
departure point:
x = sched_dep
y = origin airport lane

arrival point:
x = sched_arr
y = destination airport lane
```

使用 SVG：

```html
<line ... />
<circle ... />
<text ... />
```

或使用 SVG `path`。

必须表现出方向。

推荐：

- departure 端小圆点；
- arrival 端箭头；
- 航班号放在路径中点附近；
- 点击线或标签均可选择航班。

不要画动画飞机。

## 8.3 时间定位

所有时间先转换为 epoch milliseconds，再计算：

```text
ratio =
(time - recovery_start)
/
(recovery_end - recovery_start)

x =
left_margin
+
ratio * drawable_width
```

不要按照字符串位置计算时间。

## 8.4 时间轴显示

为了避免浏览器本地时区造成变化：

第一版统一将时间轴明确显示为：

```text
UTC
```

显示如：

```text
08:00
09:00
10:00
...
```

页面上必须明确写：

```text
Time axis: UTC
```

底层定位仍按绝对时间戳计算。

## 8.5 时间刻度自适应

目标约 8–14 个主要刻度。

可以从下列间隔中选：

```text
15 min
30 min
60 min
120 min
180 min
360 min
```

选择使刻度数量最接近约 10 个的间隔。

不要求复杂日历刻度系统。

## 8.6 尺寸

建议：

```text
minWidth ≈ 900 px
airport row height ≈ 64–76 px
```

SVG 可根据：

- recovery window 长度；
- 机场数量；

计算合理尺寸。

图自身允许横向滚动，但不要让 `body` 横向滚动。

## 8.7 航班基本样式

至少需要：

```text
normal
directly exposed
downstream risk
selected
```

推荐视觉语义：

```text
Normal             中性深色 / forest
Direct exposure    danger red
Downstream risk    amber
Selected           强调描边 / 加粗
```

不要只靠颜色表达；同时使用：

- 实线 / 虚线；
- 标签；
- legend；
- detail status badge。

建议：

```text
Normal          实线
Direct          粗实线
Downstream      虚线
Selected        外层高亮
```

---

# 9. 核心组件二：扰动覆盖层与影响推导

必须严格区分：

```text
Known disruption
≠
actual delay
≠
cancellation
≠
recovery solution
```

当前系统只有扰动输入，因此只能推导：

```text
direct exposure
downstream propagation risk
```

不能称为：

```text
delayed
cancelled
recovered
```

---

## 9.1 扰动区域绘制

每条 `Disruption`：

```text
airport
start_time
end_time
capacity_change
restriction_type
```

在对应 airport lane 上绘制半透明时间矩形：

```text
x1 = start_time
x2 = end_time
y  = airport lane
```

标签至少包含：

```text
restriction_type
capacity_change
```

如：

```text
departure_capacity_reduction · -1
```

边界使用：

```text
[start_time, end_time)
```

即：

```js
eventTime >= start && eventTime < end
```

---

# 10. Direct Exposure 规则

必须集中写成纯函数，不要散落在 DOM 渲染代码里。

建议：

```js
deriveFlightImpacts(scenario)
```

输出类似：

```js
Map {
  "F1" => {
    status: "normal",
    directDisruptions: [],
    propagationSources: []
  },
  "F2" => {
    status: "direct",
    directDisruptions: [0],
    propagationSources: []
  }
}
```

---

## 10.1 先识别 disruption 类型

建议实现：

```js
classifyDisruptionType(restrictionType)
```

统一转小写。

### Departure 类

若字符串包含：

```text
departure
depart
dep_
```

则判为：

```text
departure
```

### Arrival 类

若包含：

```text
arrival
arrive
arr_
```

则判为：

```text
arrival
```

### Both 类

若明确表示整个机场不可用，例如包含：

```text
closure
closed
airport_shutdown
curfew
```

可判为：

```text
both
```

### Unknown

无法确定语义：

```text
unknown
```

不要擅自把 unknown 当作 departure 或 arrival。

---

## 10.2 Departure disruption 的 direct exposure

Flight 满足：

```text
flight.origin == disruption.airport
AND
flight.sched_dep ∈ [disruption.start_time, disruption.end_time)
```

则：

```text
status = direct
```

例如 toy case：

```text
B
09:00–11:00
departure_capacity_reduction
```

因此：

```text
F2 09:40 B→C = direct
F5 09:50 B→A = direct
```

---

## 10.3 Arrival disruption 的 direct exposure

满足：

```text
flight.destination == disruption.airport
AND
flight.sched_arr ∈ [start, end)
```

则 direct。

---

## 10.4 Both disruption

满足任一：

```text
departure from airport during interval
OR
arrival at airport during interval
```

则 direct。

---

## 10.5 Unknown disruption

不要把航班标为 direct。

仍然绘制扰动区域，并在 legend / detail 中说明：

```text
Unknown restriction type: disruption shown,
but flight exposure is not inferred.
```

这样避免业务误判。

---

# 11. Downstream Propagation Risk

这是本阶段最复杂的逻辑。

目标不是计算真实延误，而是回答：

> 如果某航班直接受到扰动，那么按照原计划资源链，它后面的哪些航班存在传播风险？

传播只沿 **已经明确存在于输入数据中的原始链** 向后传播。

禁止自行建立新的连接关系。

---

## 11.1 Aircraft propagation

对每个：

```text
aircraft.original_rotation
```

例如：

```text
AC1: [F1, F2, F3]
```

如果 `F2` 是 direct：

```text
F3 = downstream risk
```

只向列表后方传播。

不要向 `F1` 反向传播。

算法：

```js
for each aircraft:
    seenDirect = false

    for flightId in original_rotation:
        if flightId is direct:
            seenDirect = true
            continue

        if seenDirect and flightId is not direct:
            add propagation source:
                type = "aircraft"
                resource_id = tail_id
```

如果一个 rotation 中后面又出现另一个 direct flight：

- 该航班保持 `direct`；
- direct 优先级高于 downstream；
- 后续航班可以记录多个传播来源。

---

## 11.2 Crew propagation

同样沿：

```text
crew.original_pairing
```

向后传播。

例如：

```text
C1: [F1, F2, F3]
```

若 F2 direct：

```text
F3 downstream via crew C1
```

### Duty 边界

第一版：

- 传播逻辑按 `original_pairing` 连续向后；
- `original_duties` 只在 detail 中用于展示 duty 边界；
- 不在 Phase 0.5 自行假定跨 duty 是否可恢复或是否断开。

因为当前项目尚未实现完整 crew legality。

---

## 11.3 Passenger propagation

旅客不是航班运行资源，不应像飞机一样把所有后续系统航班染色。

正确做法：

对每个 PassengerCommodity：

```text
original_itinerary
```

若 itinerary 中包含：

```text
direct flight
OR
aircraft/crew downstream-risk flight
```

则这个 passenger group：

```text
at risk
```

同时：

在该 group 的 itinerary 中，从第一个受影响航班开始的后续航段，可在 detail 中标为：

```text
passenger itinerary at risk
```

**不要仅因为乘客风险而把一个原本正常的航班升级成全局 downstream flight。**

航班全局 downstream 状态只由：

- aircraft chain；
- crew chain；

推导。

这样避免把“某批旅客可能错过连接”误表示成“该航班运行本身发生传播延误”。

---

# 12. Impact 状态优先级

每个 Flight 最终状态：

```text
DIRECT
DOWNSTREAM
NORMAL
```

优先级：

```text
DIRECT > DOWNSTREAM > NORMAL
```

数据结构建议：

```js
{
  status: "direct" | "downstream" | "normal",

  directDisruptions: [
    {
      disruptionIndex,
      airport,
      restrictionType
    }
  ],

  propagationSources: [
    {
      type: "aircraft",
      resourceId: "AC1",
      sourceFlightId: "F2"
    },
    {
      type: "crew",
      resourceId: "C1",
      sourceFlightId: "F2"
    }
  ]
}
```

如果同一航班同时受到多个扰动或多个传播来源：

**全部保留，不覆盖。**

---

# 13. 核心组件三：资源联动详情

主图右侧建立：

```text
Selected Flight
```

默认未选择时：

```text
Select a flight in the network to inspect aircraft, crew and passenger links.
```

点击航班后显示。

---

## 13.1 Flight summary

至少显示：

```text
Flight ID
Origin → Destination
Scheduled departure
Scheduled arrival
Duration
Equipment
Strategic flag
Market flag
Max delay
Impact status
```

注意：

`max_delay` 是输入约束，不是实际延误。

标签建议：

```text
Maximum allowed recovery delay
```

不能显示成：

```text
Delay
```

---

## 13.2 Impact explanation

若 direct：

```text
Directly exposed

Reason:
B departure disruption
09:00–11:00 UTC
departure_capacity_reduction
capacity change: -1
```

若 downstream：

```text
Downstream propagation risk

Aircraft:
AC1, downstream of F2

Crew:
C1, downstream of F2
```

若 normal：

```text
No direct exposure or aircraft/crew downstream risk
under the current Phase 0.5 rules.
```

---

## 13.3 Aircraft detail

找到：

```text
flight.original_aircraft
```

显示：

```text
Tail
Equipment
Initial station
Required end station
Maintenance required
Original rotation
```

Rotation 用 sequence chip：

```text
F1 → [F2] → F3
```

规则：

- 当前 selected flight 明显高亮；
- direct flight 用 direct style；
- downstream 用 risk style；
- 正常用 neutral style。

在 sequence 中点击其他 flight chip，应切换 selected flight。

---

## 13.4 Crew detail

找到：

```text
flight.original_crew
```

显示：

```text
Crew ID
Rating
Start station
Required end station
Original pairing
Original duties
```

Pairing：

```text
F1 → [F2] → F3
```

Duty 显示边界，例如：

```text
Duty 1: F1 → F2
Duty 2: F3 → F4
```

不要做 duty legality 计算。

---

## 13.5 Passenger detail

找出所有：

```text
passenger.original_itinerary.includes(selectedFlightId)
```

显示：

```text
Passenger groups on this flight
Total passenger count represented
```

每组：

```text
P1 · 28 pax
A → C
F1 → [F2]
Status: At risk / Not currently flagged
```

### passenger at-risk 判定

若该 itinerary 中存在：

- direct flight；
- 或 aircraft/crew downstream flight；

则 group 为：

```text
At risk
```

最好同时显示：

```text
First affected flight: F2
```

不要计算：

- missed connection；
- rebooking；
- arrival delay；
- compensation。

当前没有这些结果。

---

# 14. 主图与 Detail 的联动

必须支持：

```text
点击主图 F2
     ↓
F2 高亮
     ↓
detail 更新
     ↓
AC1 rotation 高亮
C1 pairing 高亮
P1 itinerary 高亮
```

再点击 detail 中 `F3`：

```text
selectedFlightId = "F3"
↓
主图选中 F3
↓
detail 切换到 F3
```

Selection 必须是本地 UI 状态，不修改 Scenario。

建议：

```js
let selectedFlightId = null;
```

放在 `visualization.js` 模块内部即可。

---

# 15. 核心组件四：机场容量热力图

当前 `AirportInterval`：

```text
airport
start_time
end_time
arr_capacity
dep_capacity
gate_capacity
curfew_flag
weather_restrictions
```

项目约定：

```text
[start_time, end_time)
```

容量单位：

```text
架次 / 该时间桶
```

因此热力图必须直接按照这些 interval 计算。

---

# 16. Heatmap 模式

增加：

```text
[ Departures ] [ Arrivals ]
```

第一版暂时不要实现 Gate utilization。

原因：

虽然存在 `gate_capacity`，但当前项目尚未正式定义可视化层计算“桶内最大同时在地航空器”的完整事件处理约定。

可以在 hover/detail 中显示：

```text
Gate capacity: 3
Planned gate occupancy: not computed in Phase 0.5
```

不要给用户一个未经定义的 gate utilization。

---

# 17. Departure heatmap 计算

对每个 `AirportInterval`：

```text
scheduled_departures =
count(
  flight.origin == interval.airport
  AND
  flight.sched_dep >= interval.start_time
  AND
  flight.sched_dep < interval.end_time
)
```

显示：

```text
scheduled_departures / dep_capacity
```

例如：

```text
2 / 1
```

表示：

```text
planned schedule exceeds the provided scenario capacity
```

注意：

这不是 solver infeasibility 的最终判定，只是直观输入检查。

---

# 18. Arrival heatmap 计算

同理：

```text
scheduled_arrivals =
count(
  flight.destination == interval.airport
  AND
  sched_arr ∈ [start, end)
)
```

显示：

```text
scheduled_arrivals / arr_capacity
```

---

# 19. Heatmap 状态颜色

不要引入任意的 80%、90% 阈值。

使用离散、可解释规则：

### capacity > 0

```text
load == 0
    → empty / neutral

0 < load < capacity
    → within capacity

load == capacity
    → at capacity

load > capacity
    → over capacity
```

### capacity == 0

```text
load == 0
    → zero capacity, no scheduled movement

load > 0
    → over capacity / blocked
```

Legend 必须说明。

---

# 20. Heatmap 的重要语义限制

### 不允许反推 pre-disruption capacity

仓库约定：

```text
AirportInterval
=
场景中实际使用的容量

Disruption.capacity_change
=
扰动元数据
```

因此禁止：

```text
nominal_capacity =
airport_interval_capacity - capacity_change
```

或任何类似逆推。

页面应明确：

```text
Capacity view uses AirportInterval values as provided.
It does not reconstruct pre-disruption capacity.
```

---

# 21. Heatmap 布局

建议：

纵轴：

```text
Airport
```

横轴：

```text
Time
```

每个输入 `AirportInterval` 在自己的：

```text
[start_time, end_time)
```

范围画一个 cell/block。

不同机场可以拥有不同时间桶。

不要求为了“整齐”而人工拆分或合并用户输入的 interval。

每个 cell 显示：

```text
2 / 1
```

hover 或点击显示：

```text
Airport B
09:00–11:00 UTC

Scheduled departures: 2
Departure capacity: 1
Gate capacity: 3
Curfew: false
Weather:
- reduced_departure_rate
```

如果用户点击容量 cell，可在下方显示简单 detail；不是强制核心交互。

---

# 22. 机场拓扑小图（辅助，可选）

如果核心四项完成后代码仍然清晰，可以增加：

```text
Airport topology · schematic
```

要求：

- 明确标注 `Schematic / not geographic`；
- 不使用真实地图；
- 不需要经纬度；
- 节点 = airport；
- edge = 原计划中存在的 OD；
- 相同 OD 多航班可聚合；
- 点击节点可以高亮与该机场有关的航班；
- 点击 edge 可高亮该 OD 航班。

布局可以用确定性的圆形布局：

```text
A      B

    C
```

不要引入 force simulation。

这不是第一版必须通过的验收项。

---

# 23. visualization.js 推荐结构

不要写成一个几百行的巨型 `renderVisualization()`。

建议拆成纯推导 + DOM/SVG 渲染。

```js
// 时间/索引
parseScenarioTimes(...)
buildScenarioIndexes(...)
chooseTimeTickMinutes(...)

// 影响分析
classifyDisruptionType(...)
deriveDirectExposure(...)
deriveAircraftPropagation(...)
deriveCrewPropagation(...)
derivePassengerRisk(...)
deriveFlightImpacts(...)

// capacity
countIntervalDepartures(...)
countIntervalArrivals(...)
deriveCapacityCells(...)

// render
renderVisualization(...)
renderVisualizationToolbar(...)
renderTimeSpaceNetwork(...)
renderDisruptionOverlay(...)
renderFlightLayer(...)
renderFlightDetail(...)
renderCapacityHeatmap(...)

// selection
selectFlight(...)
```

其中：

```text
derive*
count*
classify*
```

尽量保持纯函数：

```text
input → output
```

不要直接操作 DOM。

这样以后 Solver 接进来，可以继续复用这些函数。

---

# 24. 推荐的可视化派生对象

可在 `renderVisualization()` 开头构建：

```js
const model = {
  scenario,
  indexes,
  impacts,
  passengerRisk,
  capacity
};
```

示意：

```js
const indexes = {
  airportsById: new Map(),
  flightsById: new Map(),
  aircraftById: new Map(),
  crewById: new Map(),
  passengersById: new Map()
};
```

不要在每次点击 F2 时重新遍历所有数组寻找资源。

---

# 25. 空数据与边界情况

Visualization 必须安全处理：

## 25.1 No flights

仍显示：

```text
No scheduled flights in this scenario.
```

机场 lanes 可以保留。

## 25.2 No disruptions

Disruption Overlay 模式：

```text
No disruptions defined.
```

所有 flights 保持 normal。

## 25.3 No airport intervals

Heatmap：

```text
No airport capacity intervals defined.
```

不要崩溃。

## 25.4 No aircraft / crew / passengers

对应 detail section 显示：

```text
No linked aircraft data.
No linked crew data.
No passenger commodities use this flight.
```

合法场景正常情况下引用会被 validator 约束，但 UI 仍要 defensive。

## 25.5 很多机场 / 很长 recovery window

使用：

- 图内部滚动；
- 自适应 time tick；
- 不把 SVG 无限压缩到不可读。

## 25.6 同一航班多个影响来源

全部显示。

例如：

```text
Downstream via:
- Aircraft AC1 after F2
- Crew C7 after F8
```

---

# 26. 可访问性与基础交互

必须做到：

- view switch 用 `<button>`；
- selected flight 不能只靠 hover；
- 航班可点击；
- 重要状态有文字；
- SVG flight 元素增加可识别标签；
- legend 可读；
- 键盘至少可以通过 detail 中的 flight buttons 切换航班；
- 不需要第一版实现复杂 SVG 键盘导航。

---

# 27. CSS 设计要求

继续沿用当前项目已有视觉语言：

```text
--forest
--mint
--amber
--danger
--paper
--surface
--line
```

不要重新设计一套完全不同的 Dashboard 风格。

新增 `visualization.css` 时尽量复用这些 CSS variables。

推荐新 class 前缀：

```text
.viz-
```

例如：

```text
.viz-toolbar
.viz-grid
.viz-network
.viz-detail
.viz-legend
.viz-flight
.viz-flight--direct
.viz-flight--downstream
.viz-capacity
```

降低与现有 table CSS 冲突概率。

---

# 28. index.html 具体修改要求

至少新增：

```html
<link rel="stylesheet" href="/static/css/visualization.css">
```

在 main 中加入：

```text
一级 view switcher
```

并把现有数据相关区域包进：

```html
<div id="data-view">...</div>
```

增加：

```html
<div id="visualization-view" hidden>
    ...
</div>
```

Visualization 内建议预留容器：

```html
<section id="viz-toolbar"></section>

<div class="viz-main-grid">
  <section>
    <div id="time-space-network"></div>
  </section>

  <aside id="flight-detail"></aside>
</div>

<section>
  <div id="capacity-heatmap"></div>
</section>
```

不要把大量静态图形节点写死在 HTML。

SVG / heatmap 内容由 `visualization.js` 渲染。

---

# 29. app.js 具体重构建议

现有 `render()` 当前只负责 Data Editor。

建议改成：

```js
function renderDataView() {
  ...
}

async function renderVisualizationView() {
  ...
}

function renderShell() {
  ...
}
```

或等价清晰结构。

关键要求：

### Data Editor 行为不能回归

现有全部功能继续工作：

- Load Example；
- Import JSON；
- Export JSON；
- Reset All；
- 8 个 tabs；
- Edit；
- Add Row；
- Duplicate Row；
- Delete Row；
- Reset section；
- Validate。

### Visualization 不接管 state

它只接收：

```js
renderVisualization(normalizedScenario)
```

不要让 `visualization.js` import / 修改 `state`。

---

# 30. 不要做的事情

本任务明确不做：

- OR solver；
- delay optimization；
- cancellation optimization；
- aircraft reassignment；
- crew reassignment；
- passenger rebooking；
- recovered schedule；
- KPI cost；
- delay minutes result；
- compensation；
- 真实中国地图；
- 飞机动态图标移动；
- WebSocket；
- database；
- localStorage；
- 后端持久化；
- React/Vue；
- npm；
- 新的前端构建系统；
- 自动修改 Scenario Schema；
- 根据 `capacity_change` 自动重算 `AirportInterval`；
- 根据 direct exposure 擅自生成“预计延误分钟”。

---

# 31. Toy case 的预期结果

使用：

```text
data/examples/toy_case_001.json
```

Recovery window：

```text
08:00–16:00 UTC
```

机场：

```text
A
B
C
```

扰动：

```text
B
09:00–11:00 UTC
departure_capacity_reduction
capacity_change = -1
```

## 31.1 Direct exposure

应识别：

```text
F2
B → C
09:40 departure

F5
B → A
09:50 departure
```

即：

```text
F2 = DIRECT
F5 = DIRECT
```

## 31.2 Aircraft propagation

```text
AC1:
F1 → F2 → F3
```

所以：

```text
F3 = downstream via AC1 after F2
```

```text
AC2:
F4 → F5 → F6
```

所以：

```text
F6 = downstream via AC2 after F5
```

## 31.3 Crew propagation

```text
C1:
F1 → F2 → F3
```

所以 F3 也应有：

```text
downstream via crew C1 after F2
```

```text
C2:
F4 → F5 → F6
```

所以 F6 也应有：

```text
downstream via crew C2 after F5
```

最终：

```text
F1 = NORMAL
F2 = DIRECT
F3 = DOWNSTREAM

F4 = NORMAL
F5 = DIRECT
F6 = DOWNSTREAM
```

## 31.4 Passenger risk

```text
P1 = [F1, F2], 28 pax
```

因为包含 F2 direct：

```text
P1 = AT RISK
first affected flight = F2
```

```text
P2 = [F4, F5], 22 pax
```

因为包含 F5 direct：

```text
P2 = AT RISK
first affected flight = F5
```

```text
P3 = [F3], 16 pax
P4 = [F6], 18 pax
```

F3 / F6 是 aircraft/crew downstream risk，因此：

```text
P3 = AT RISK
P4 = AT RISK
```

这里的 `AT RISK` 只表示：

```text
itinerary contains an operationally flagged flight
```

不能显示成：

```text
missed connection
delayed passenger
rebooked passenger
```

---

# 32. Toy case 容量预期

B 的容量 interval：

```text
09:00–11:00 UTC

arr_capacity = 2
dep_capacity = 1
gate_capacity = 3
```

在该时间桶：

离港：

```text
F2 09:40
F5 09:50
```

所以：

```text
scheduled departures = 2
dep capacity = 1

2 / 1
→ OVER CAPACITY
```

进港：

```text
F1 arrives B 09:00
F4 arrives B 09:10
```

由于区间为：

```text
[09:00, 11:00)
```

所以二者都计入。

结果：

```text
scheduled arrivals = 2
arr capacity = 2

2 / 2
→ AT CAPACITY
```

这是第一版最重要的人工验收例。

---

# 33. Manual 验收文件

新增：

```text
tests/manual/phase0_5_visualization_checklist.md
```

至少包含下面的验收项。

---

## A. 原 Phase 0 回归

- [ ] Load Example 正常；
- [ ] Edit 正常；
- [ ] Add / Duplicate / Delete 正常；
- [ ] Import / Export 正常；
- [ ] Validate pass / fail 正常；
- [ ] 原 `phase0_frontend_checklist.md` 项目无回归。

---

## B. 一级视图

- [ ] Data Editor → Visualization 能切换；
- [ ] Visualization → Data Editor 能切回；
- [ ] 切换不会丢失人工修改；
- [ ] 切换不会重置当前 Data section；
- [ ] Visualization 使用当前 state，而不是重新加载 toy case。

---

## C. Validation gate

制造：

```text
duplicate flight_id
```

然后进入 Visualization：

- [ ] 页面拒绝绘图；
- [ ] 显示 validation blocked；
- [ ] 能看到原 validation error；
- [ ] 修复后可以正常进入。

---

## D. Time-space network

toy case：

- [ ] 3 个 airport lanes；
- [ ] 6 条 flight；
- [ ] F1 A→B；
- [ ] F2 B→C；
- [ ] F3 C→A；
- [ ] F4 C→B；
- [ ] F5 B→A；
- [ ] F6 A→C；
- [ ] 横轴范围 08:00–16:00 UTC；
- [ ] 航班方向可识别；
- [ ] 点击航班可以选中。

---

## E. Disruption overlay

- [ ] B 09:00–11:00 出现 disruption overlay；
- [ ] F2 direct；
- [ ] F5 direct；
- [ ] F3 downstream；
- [ ] F6 downstream；
- [ ] F1/F4 normal；
- [ ] 页面没有把 direct 写成 actual delay；
- [ ] 页面没有显示 cancellation；
- [ ] Recovered Plan 按钮禁用。

---

## F. Resource detail

点击 F2：

- [ ] 显示 B→C；
- [ ] Aircraft = AC1；
- [ ] Rotation = F1→F2→F3；
- [ ] Crew = C1；
- [ ] Pairing = F1→F2→F3；
- [ ] Passenger P1 = 28 pax；
- [ ] 显示 direct exposure 原因。

点击 F3：

- [ ] 显示 downstream；
- [ ] 至少显示 AC1 来源；
- [ ] 至少显示 C1 来源；
- [ ] P3 可见。

---

## G. Capacity heatmap

Departure：

- [ ] B 09:00–11:00 = 2 / 1；
- [ ] 状态 = over capacity。

Arrival：

- [ ] B 09:00–11:00 = 2 / 2；
- [ ] 状态 = at capacity。

并确认：

- [ ] 没有用 `capacity_change` 反推原容量；
- [ ] gate capacity 可显示；
- [ ] 没有伪造 gate utilization。

---

## H. Responsive

- [ ] 桌面正常；
- [ ] 390px 宽度下 body 无整体横向溢出；
- [ ] network 自己可以横向滚动；
- [ ] capacity 自己可以横向滚动；
- [ ] detail 移到主图下方。

---

# 34. README 更新

在 README 当前：

```text
数据编辑入口
```

附近增加简短说明：

```text
Visualization
```

说明：

- 同一页面切换；
- 进入 Visualization 会先校验；
- 当前展示 original schedule、disruption exposure、propagation risk、capacity load；
- 当前不展示 recovery result；
- Phase 0.5 仍不包含优化模型。

不要把 README 写成详细设计文档。

详细逻辑留在本文件和代码中。

---

# 35. 完成后的代码质量要求

Codex 完成修改后必须：

1. 运行：
   ```bash
   python -m pytest
   ```

2. 启动：
   ```bash
   python -m uvicorn backend.main:app --reload
   ```

3. 浏览器人工完成：
   ```text
   phase0_frontend_checklist.md
   phase0_5_visualization_checklist.md
   ```

4. 检查浏览器 console：
   ```text
   no uncaught errors
   ```

5. 不提交：
   - 临时截图；
   - 浏览器缓存；
   - node_modules；
   - 新的无必要依赖；
   - 调试日志。

---

# 36. 实施顺序

严格建议按以下顺序修改，避免一次改太多：

### Step 1
增加一级：

```text
Data Editor / Visualization
```

先保证状态不丢。

### Step 2
进入 Visualization 时接入现有 `/api/validate`。

### Step 3
完成时空网络图，只画原计划。

### Step 4
完成 disruption overlay + direct exposure。

### Step 5
完成 aircraft / crew downstream propagation。

### Step 6
完成 flight selection + resource detail。

### Step 7
完成 passenger risk。

### Step 8
完成 departure / arrival capacity heatmap。

### Step 9
响应式布局 + empty state + unknown disruption 类型。

### Step 10
README + manual checklist + 全回归测试。

机场 topology 小图只在上述全部稳定后再考虑。

---

# 37. 最终设计边界

这一版完成后，页面表达的语义必须严格是：

```text
原计划是什么？
        +
扰动在何时何地发生？
        +
哪些计划航班直接暴露于扰动？
        +
按照原飞机/机组链，哪些后续航班存在传播风险？
        +
哪些旅客行程经过这些风险航班？
        +
当前计划流量与给定机场容量时间桶是什么关系？
```

它**不能回答**：

```text
最终应该延误多少分钟？
取消哪些航班？
换哪架飞机？
换哪个机组？
旅客改签到哪里？
恢复方案成本是多少？
```

这些问题必须等待后续 OR Solver。

---

# 38. 为后续 Solver 预留，但当前不实现

写代码时避免把 `Original Plan` 写死成只能处理一种 schedule。

未来理想接口可以演化为：

```js
renderTimeSpaceNetwork({
  scenario,
  solution: null,
  mode: "original" | "disruption" | "recovered" | "difference"
});
```

当前：

```text
solution = null
```

因此：

```text
original    可用
disruption  可用
recovered   disabled
difference  不显示
```

不要提前定义虚假的 solution JSON Schema。

---

# 39. Codex 最终交付说明要求

修改完成后，Codex 最终回复需要列出：

1. 修改/新增了哪些文件；
2. Visualization 的入口在哪里；
3. direct exposure 的判定规则；
4. downstream risk 的传播规则；
5. capacity heatmap 如何计数；
6. toy case 的实际可视化结果：
   - F2/F5 direct；
   - F3/F6 downstream；
   - B departure 2/1；
   - B arrival 2/2；
7. `python -m pytest` 结果；
8. 前端人工验收结果；
9. 如果有任何未完成项，明确列出，不允许用“基本完成”掩盖。

---

## 一句话实现原则

> **把当前合法 Scenario 变成一个可解释的“原计划 + 扰动暴露 + 原始资源链传播风险 + 容量负荷”视图；只做确定性展示，不跨越到优化求解。**
