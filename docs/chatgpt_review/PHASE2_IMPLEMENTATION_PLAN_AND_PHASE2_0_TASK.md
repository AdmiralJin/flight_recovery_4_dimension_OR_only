# Phase 2 实施计划与当前 Codex 任务

> 项目：`AdmiralJin/flight_recovery_4_dimension_OR_only`  
> 当前状态：Phase 0、0.5、1 已完成。  
> 当前下一阶段：**Phase 2 — Fixed-Column SRM / ARM / CRM / PRM**。  
> 本文档同时给出 Phase 2 总路线，但 **本次 Codex 只执行“Phase 1 合同收尾 + Phase 2.0 Incidence / Index Builder”**。  
> 本次不得实现 Solver、SRM、ARM、CRM、PRM、Benders 或 Column Generation。

---

# 1. 当前基线

Phase 1 已完成以下闭环：

```text
Scenario
    ↓
Recovery Columns
    ↓
Manual Expected / Oracle
    ↓
Semantic Validation
    ↓
Metric Recalculation
```

主 Benchmark：

```text
phase1_benchmark_001
```

当前人工 Reference 的主要恢复结果：

```text
F2  +50 min
F10 +20 min
F11 +10 min

F3:  AC1 → AC4
F10: AC4 → AC1

P4:
F2→F3
→
F8
```

Reference Metrics：

```text
total flight delay = 80 min
aircraft reassignments = 2
crew reassignments = 0
passenger reaccommodated = 15 pax
weighted passenger delay = 1800 passenger-min
cancelled flights = 0
unserved passengers = 0
```

该 Reference 是：

```text
manual_reference
feasible
```

不是已经证明的 AIR 全局最优解。

---

# 2. Phase 2 的目标

Phase 2 只解决：

> 在一组**固定、已验证的候选列**上，分别实现并验证 SRM、ARM、CRM、PRM 四个数学模型。

Phase 2 不做：

```text
Automatic Flight String Generation
Automatic Crew Pairing Generation
Dynamic Passenger Itinerary Generation
Column Generation
Benders Decomposition
Full Integrated MIP
```

Full Integrated Fixed-Column Oracle 属于 Phase 3。

---

# 3. Phase 2 必须拆分执行

推荐顺序：

```text
Pre-Phase-2 Cleanup
        ↓
Phase 2.0 Incidence / Index Builder
        ↓
Phase 2.1 Solver / Cost / ModelResult Contract
        ↓
Phase 2.2 Fixed-Column SRM
        ↓
Phase 2.3 Fixed-Column ARM
        ↓
Phase 2.4 Fixed-Column CRM
        ↓
Phase 2.5 Fixed-Column PRM
        ↓
Phase 2 Acceptance Review
        ↓
Phase 3 Full Integrated Fixed-Column Oracle
```

每个子阶段单独测试、单独报告，建议单独 Commit。

---

# 4. Phase 2 前需要处理的两个小问题

## 4.1 JSON Schema 与 Pydantic 严格度统一

当前 Python Runtime Schema 继承 `SchemaModel`，会拒绝未知字段。

但：

```text
schemas/recovery_columns_v1.schema.json
schemas/recovery_expected_v1.schema.json
```

多数结构化 Object 没有显式：

```json
"additionalProperties": false
```

因此外部 JSON Schema 比 Python Runtime Schema 更宽松。

### 本次要求

在不改变 v1.0.0 业务字段和语义的前提下：

- 顶层 Object 和所有结构化 nested object / `$defs` 增加 `additionalProperties: false`；
- `cost_components`、selection map、`from` / `to` 等本来就设计成自由 key-value map 的字段除外；
- 增加 extra-field 测试，证明 JSON Schema 与 Pydantic 对未知字段的策略一致。

不要修改 benchmark columns / expected 的业务内容。

---

## 4.2 `RecoveryExpected` 不再承担真正 Solver Result 的职责

当前 `RecoveryExpected` 应继续定义为：

```text
Oracle / Reference Fixture
```

不要在 Phase 2 将其直接作为模型求解结果对象。

原因：

当前 Schema 允许：

```text
solution_status = infeasible
```

但仍要求完整：

```text
reference_solution
selected columns
resolved flights
passenger outcomes
metrics
```

这与真正的 `INFEASIBLE` 求解结果语义不自然。

### Phase 2 设计原则

保持：

```text
RecoveryExpected
=
测试 Oracle
```

Phase 2.1 再单独定义：

```text
ModelSolveResult
```

用于：

```text
OPTIMAL
FEASIBLE
INFEASIBLE
UNBOUNDED
ERROR
```

以及：

```text
objective
selected variables
runtime
solver diagnostics
```

**本次 Phase 2.0 只记录该决定，不实现完整 ModelSolveResult。**

---

# 5. Phase 2.0 的目标

Phase 2.0 不建立任何数学模型。

它只把已经验证的：

```text
Scenario
+
RecoveryColumns
```

转换成：

> 稳定、确定、可审计、可直接供后续四个 Fixed-Column 模型使用的索引与 Incidence 数据。

输入必须已经通过：

```python
validate_scenario(...)
validate_recovery_columns(...)
```

Incidence Builder 不负责修复非法 Columns。

---

# 6. 为什么不能只做旧计划中的四个矩阵

旧计划列出：

```text
Flight Option × Aircraft String
Maintenance × Aircraft String
Flight Option × Crew Pairing
Flight Option × Passenger Itinerary
```

这些是核心 Coverage 关系，但仍不够。

Phase 2.0 必须同时建立：

```text
A. Entity → Candidate Choice
B. Operational Coverage
C. Airport-capacity movement incidence
```

否则 SRM/ARM/CRM/PRM 会分别重新实现 ID 映射，导致语义分叉。

---

# 7. 集合定义

统一以下集合：

```text
F = 原始 Revenue Flights
O = 所有 Flight Options
A = Aircraft
S = Aircraft Strings
K = Crew
P = Crew Pairings
G = Passenger Groups
I = Passenger Itineraries
M = Maintenance-required Aircraft
C = Airport Capacity Intervals
```

Flight Options 必须区分：

```text
O_operate
O_cancel
O_ferry
```

以及：

```text
O_revenue_operate
=
operation_type == operate
AND base_flight_id != null
```

---

# 8. 原始 Flight 与 Flight Option 必须严格分离

```text
F2
```

是原始 Flight。

```text
FO_F2_ORIG
FO_F2_D50
FO_F2_CANCEL
```

是恢复候选 Option。

后续模型必须明确区分：

```text
Base Flight Selection
vs
Operated Recovery Copy
```

代码中始终使用明确字段名：

```text
flight_id
option_id
```

不要用含糊的 `flight` 指代两者。

---

# 9. 本次建议新增文件

```text
backend/core/
├── __init__.py
├── indices.py
└── incidence.py

tests/unit/
├── test_indices.py
└── test_incidence.py

tests/regression/
└── test_phase2_incidence_benchmark_001.py
```

不要新增任何 Solver 文件。

---

# 10. `indices.py`

建议定义只读、确定性索引结构，例如：

```python
@dataclass(frozen=True)
class OrderedIndex:
    ids: tuple[str, ...]
    position: Mapping[str, int]
```

至少为以下对象提供 Index：

```text
flights
flight_options
aircraft
aircraft_strings
crew
crew_pairings
passenger_groups
passenger_itineraries
maintenance_required_aircraft
capacity_intervals
```

---

# 11. Index 顺序

必须确定性。

推荐：

> **保留输入 JSON 的显式顺序。**

不要依赖：

```text
set iteration
unordered reconstruction
```

Index 只用于内部矩阵和 Solver 位置，不得替代业务 ID。

日志、结果、错误仍必须输出：

```text
FO_F2_D50
AS_AC1_SWAP_F10
```

而不是：

```text
row 3
column 7
```

---

# 12. Incidence 的核心数据结构

当前规模很小，Phase 2.0 目标是可审计性。

不建议现在引入 NumPy / SciPy Sparse。

建议定义类似：

```python
@dataclass(frozen=True)
class BinaryIncidence:
    rows: tuple[str, ...]
    columns: tuple[str, ...]
    row_to_columns: Mapping[str, frozenset[str]]
    column_to_rows: Mapping[str, frozenset[str]]
```

至少提供稳定 API：

```python
contains(row_id, column_id) -> bool
columns_for_row(row_id)
rows_for_column(column_id)
```

不要让测试和后续模型直接依赖内部 Dict 细节。

---

# 13. 第一类：Base Flight → Flight Option

定义：

```text
B_FO[f,o] = 1
```

当且仅当：

```text
option.base_flight_id == flight.flight_id
```

包括：

```text
operate
cancel
```

不包括：

```text
ferry
```

因为 Ferry：

```text
base_flight_id = null
```

作用：

> 后续 SRM 表达“一个原始 Flight 从其恢复候选 Options 中选择一个状态”。

不要通过 `option_id` 名称推断 Base Flight。

---

# 14. 第二类：Aircraft → Aircraft String

```text
B_AS[a,s] = 1
```

当：

```text
string.aircraft_id == aircraft.tail_id
```

作用：

> 每架飞机只能从属于自己的候选 Strings 中选择。

不要解析：

```text
AS_AC1_...
```

字符串前缀。

---

# 15. 第三类：Crew → Crew Pairing

```text
B_KP[k,p] = 1
```

完全依据：

```text
pairing.crew_id
```

---

# 16. 第四类：Passenger Group → Passenger Itinerary

```text
B_GI[g,i] = 1
```

依据：

```text
itinerary.pax_group_id
```

作用：

> 后续 PRM 表达每个 Passenger Group 选择一条 recovery itinerary / unserved option。

---

# 17. 第五类：Flight Option → Aircraft String

核心 Coverage：

```text
A_OS[o,s] = 1
```

当：

```text
o in string.leg_option_ids
```

允许：

```text
operate
ferry
```

禁止：

```text
cancel
```

注意：

`A_OS` 表示 **Flight Option 是否被该 Aircraft String 实际执行**，不是原始 Flight 是否属于该 String。

---

# 18. 第六类：Flight Option → Crew Pairing

定义 Operating Coverage：

```text
A_OP[o,p] = 1
```

仅当 Crew Pairing 中：

```text
segment_type = operate
flight_option_id = o
```

---

# 19. Deadhead 不能算 Operating Coverage

这是 Phase 2 高风险逻辑。

如果：

```text
segment_type = deadhead
flight_option_id = FO_F2_D50
```

该 Crew 是乘坐 F2，不是执行 F2。

因此 Deadhead 不得进入：

```text
A_OP
```

建议本次同时建立：

```text
D_OP[o,p] = 1
```

专门表示 Deadhead 使用关系。

当前 benchmark 的 `D_OP` 可以全部为 0，但该语义必须从一开始分开。

---

# 20. 第七类：Flight Option → Passenger Itinerary

```text
A_OI[o,i] = 1
```

当 Passenger Itinerary 中：

```text
segment_type = flight
flight_option_id = o
```

Passenger Flight Segment 只允许引用：

```text
operation_type = operate
```

不允许：

```text
cancel
ferry
```

如果同一 Itinerary 重复出现同一个 Option，不要静默压成一个 Binary Edge；应 fail fast 或由 Validator 拒绝。

---

# 21. 第八类：Maintenance → Aircraft String

当前 Scenario 没有独立 Maintenance Requirement ID。

Phase 2.0 不要发明新的长期业务实体。

定义：

```text
M
=
所有 maintenance_required == true 的 aircraft.tail_id
```

即以 Aircraft ID 作为 Maintenance Row Key。

定义：

```text
A_MS[a,s] = 1
```

当：

```text
string.aircraft_id == a
AND
string.maintenance_satisfied == true
AND
string.end_station in aircraft.maintenance_stations
```

不要在本阶段新增：

```text
maintenance duration
maintenance due time
hangar capacity
```

---

# 22. 第九类：Airport Capacity Incidence

SRM 下一阶段会立即使用机场容量。

因此 Phase 2.0 同时建立：

```text
A_DEP[c,o]
A_ARR[c,o]
```

其中 c 是一个具体 Airport Capacity Interval。

---

# 23. Capacity Interval Key

同一机场可能有多个区间，因此不能只用 Airport ID。

建议结构化 Key：

```python
@dataclass(frozen=True)
class CapacityIntervalKey:
    airport: str
    start_time: datetime
    end_time: datetime
```

或者等价稳定结构。

不要依赖人工拼接字符串来解析业务含义。

---

# 24. Departure Capacity Incidence

```text
A_DEP[c,o] = 1
```

当：

```text
option.operation_type in {operate, ferry}
option.origin == c.airport
option.dep_time ∈ [c.start_time, c.end_time)
```

### Ferry 的处理

当前 Phase 2 假设：

> Ferry 是真实 Aircraft Movement，应占用机场 Arrival / Departure Capacity。

如果以后论文复现或业务规则采用其他定义，必须更新 `assumptions.md`，不能静默修改代码。

---

# 25. Arrival Capacity Incidence

```text
A_ARR[c,o] = 1
```

当：

```text
option.operation_type in {operate, ferry}
option.destination == c.airport
option.arr_time ∈ [c.start_time, c.end_time)
```

严格使用：

```text
[start, end)
```

因此：

```text
event_time == end_time
```

不属于该桶。

Cancel Option 不进入任何 Movement Capacity。

---

# 26. Gate Incidence 本次不实现

当前 Scenario 有：

```text
gate_capacity
```

但项目尚未冻结恢复后的 Gate Occupancy 事件语义，例如：

- Initial on-ground aircraft 如何计数；
- Arrival 后到下一次 Departure 之间如何计；
- Recovery Window 边界如何处理；
- Cancel / Ferry 如何影响 Gate Inventory。

因此 Phase 2.0：

```text
实现 Arrival Capacity
实现 Departure Capacity
不实现 Gate Incidence
```

代码和报告必须明确：

```text
Gate incidence intentionally deferred.
```

不要自行发明一套未经登记的 Gate Constraint。

---

# 27. 推荐统一输出结构

建议：

```python
@dataclass(frozen=True)
class RecoveryIndices:
    flights: OrderedIndex
    flight_options: OrderedIndex
    aircraft: OrderedIndex
    aircraft_strings: OrderedIndex
    crew: OrderedIndex
    crew_pairings: OrderedIndex
    passenger_groups: OrderedIndex
    passenger_itineraries: OrderedIndex
    maintenance_aircraft: OrderedIndex
    capacity_intervals: OrderedIndex
```

以及：

```python
@dataclass(frozen=True)
class RecoveryIncidence:
    base_flight_to_options: BinaryIncidence
    aircraft_to_strings: BinaryIncidence
    crew_to_pairings: BinaryIncidence
    passenger_group_to_itineraries: BinaryIncidence

    option_to_aircraft_strings: BinaryIncidence
    option_to_operating_pairings: BinaryIncidence
    option_to_deadhead_pairings: BinaryIncidence
    option_to_passenger_itineraries: BinaryIncidence

    maintenance_to_strings: BinaryIncidence

    departure_capacity_to_options: BinaryIncidence
    arrival_capacity_to_options: BinaryIncidence
```

命名可略调，但语义不得合并或含糊。

---

# 28. Builder API

建议：

```python
def build_recovery_indices(
    scenario: Scenario,
    columns: RecoveryColumns,
) -> RecoveryIndices:
    ...
```

```python
def build_recovery_incidence(
    scenario: Scenario,
    columns: RecoveryColumns,
    indices: RecoveryIndices | None = None,
) -> RecoveryIncidence:
    ...
```

输入应是已经 Validation PASS 的 Pydantic Objects。

---

# 29. Builder 与 Validator 的职责边界

不要在 Incidence Builder 中复制整套：

```text
column_validator.py
```

规则。

原则：

```text
Validator
=
业务合法性边界

Incidence Builder
=
对合法输入进行确定性结构转换
```

但 Builder 必须 fail fast：

- unknown option；
- Cancel 被注入 Aircraft String；
- Passenger 被注入 Ferry；
- duplicate edge；
- 明显违反其自身 incidence 定义的引用。

不得静默过滤非法输入。

---

# 30. Benchmark Regression

新增：

```text
tests/regression/test_phase2_incidence_benchmark_001.py
```

必须读取正式：

```text
data/examples/phase1_benchmark_001.json
data/columns/phase1_benchmark_001_columns.json
```

并先运行现有 Validators。

---

# 31. Benchmark：Base Flight → Option

以：

```text
F2
```

为例，应关联当前 columns 中全部以：

```text
base_flight_id = F2
```

定义的 Options。

Ferry：

```text
FO_FERRY_CA_1140
```

不得属于任何 Base Flight Row。

---

# 32. Benchmark：Aircraft String Coverage

```text
AS_AC1_SWAP_F10
```

必须覆盖：

```text
FO_F1_ORIG
FO_F2_D50
FO_F10_D20
```

不得覆盖：

```text
FO_F3_ORIG
FO_F11_D10
```

```text
AS_AC4_SWAP_F3_ORIG
```

必须覆盖：

```text
FO_F3_ORIG
FO_F11_D10
FO_F12_ORIG
```

---

# 33. Benchmark：Crew Coverage

```text
CP_C1_RECOVERY
```

Operating Coverage：

```text
FO_F1_ORIG
FO_F2_D50
FO_F10_D20
```

```text
CP_C4_F3_ORIG_F11_D10
```

Operating Coverage：

```text
FO_F3_ORIG
FO_F11_D10
```

当前 Benchmark 的 Deadhead Incidence 应全部为 0。

---

# 34. Benchmark：Passenger Incidence

```text
PI_P4_REACCOM_F8
```

只能关联：

```text
FO_F8_ORIG
```

不得关联：

```text
FO_F2_D50
FO_F3_ORIG
```

---

# 35. Benchmark：Capacity Incidence

B：

```text
[09:30,10:30)
```

关键检查：

```text
FO_F5_ORIG dep 09:50 → included
FO_F8_ORIG dep 10:00 → included
FO_F2_D50 dep 10:30 → excluded
```

必须有专门测试证明：

```text
time == end
→ not included
```

---

# 36. Benchmark：Maintenance Incidence

对于：

```text
AC4
```

Maintenance Rows 中必须存在 AC4。

当前 Reference String：

```text
AS_AC4_SWAP_F3_ORIG
```

必须满足：

```text
A_MS[AC4, AS_AC4_SWAP_F3_ORIG] = 1
```

---

# 37. Unit Tests

至少覆盖：

## OrderedIndex

- 稳定顺序；
- ID → position；
- position → ID；
- unknown ID；
- empty optional set。

## BinaryIncidence

- row → columns；
- column → rows；
- contains；
- duplicate edge；
- unknown row / column；
- immutable behavior。

## Builder

- Base Flight → Option；
- Aircraft → String；
- Crew → Pairing；
- Passenger → Itinerary；
- Option → Aircraft String；
- Option → Operating Pairing；
- Deadhead 与 Operate 严格分开；
- Option → Passenger Itinerary；
- Maintenance；
- Departure / Arrival Capacity；
- `[start,end)`；
- Ferry；
- Cancel。

---

# 38. Phase 2.0 Negative Tests

无需重复 Phase 1 的几十个 Semantic Validation 负例。

只做 Builder 自身高价值防御：

1. unknown Option reference → fail fast；
2. Cancel 被强制放入 Aircraft String → fail fast；
3. Passenger Flight Segment 强制引用 Ferry → fail fast；
4. duplicate incidence edge → 不静默；
5. capacity end boundary → excluded；
6. Ferry → 计入 Movement Capacity；
7. Deadhead → 不计 Operating Crew Coverage。

---

# 39. 额外文档清理

用户已删除/归档旧的重复 Benchmark MD。

确认正式 Benchmark 文档只有：

```text
docs/benchmarks/PHASE1_BENCHMARK_001_DESIGN.md
```

如果 README 或其他 Markdown 中仍存在：

```text
“如果仍存在 data/colums...”
```

之类已经失效的历史提醒，可删除。

不要为了清理文档调整当前已经稳定的目录。

---

# 40. 本次 Codex 的明确工作范围

本次只执行：

```text
A. Phase 1 Contract Cleanup
   - JSON Schema additionalProperties 严格度对齐
   - extra-field tests
   - 删除失效的历史目录提醒（若仍存在）

B. Phase 2.0
   - OrderedIndex / RecoveryIndices
   - BinaryIncidence
   - RecoveryIncidence
   - Incidence Builder
   - Unit Tests
   - benchmark001 Incidence Regression
   - Codex Report
```

不要继续 Phase 2.1。

---

# 41. Phase 2.0 完成标准

全部满足才算 PASS：

- [ ] JSON Schema 与 Pydantic 对 unknown fields 的策略一致；
- [ ] Phase 1 既有测试无回归；
- [ ] Index 顺序确定；
- [ ] Entity → Candidate Choice Incidence 完整；
- [ ] Operational Coverage Incidence 完整；
- [ ] Operate / Deadhead 分离；
- [ ] Cancel 不进入物理执行 Coverage；
- [ ] Ferry 没有 Base Flight；
- [ ] Ferry 进入 Aircraft / Airport Movement；
- [ ] Passenger 不使用 Ferry；
- [ ] Maintenance Incidence 正确；
- [ ] Arrival / Departure Capacity 使用 `[start,end)`；
- [ ] Gate Incidence 明确暂缓；
- [ ] Benchmark001 关键关系与人工检查一致；
- [ ] 新增 Unit / Regression Tests 全通过；
- [ ] `python -m pytest` 全部 PASS。

---

# 42. Phase 2.0 完成后的 Phase 2.1

Phase 2.0 完成后**仍不要直接写 SRM**。

先冻结：

```text
Solver Contract
+
Cost Contract
+
Model Result Contract
```

---

# 43. Phase 2.1：Solver Contract

当前仓库没有 OR Solver Dependency。

必须先明确：

- Solver；
- Solver 版本；
- 本地 / CI 使用方式；
- LP/MIP Status Mapping；
- Objective / Bound / Gap；
- Runtime；
- Variable / Constraint naming；
- LP dual；
- reduced cost。

后续项目要实现：

```text
Benders
Column Generation
Pricing
```

因此 Solver 不能只满足“能解一个 MIP”，还必须可靠读取：

```text
duals
reduced costs
bounds
MIP status
```

---

# 44. Phase 2.1：Model Result Contract

新增独立：

```text
ModelSolveResult
```

不要复用：

```text
RecoveryExpected
```

最少支持：

```text
model_name
status
objective_value
selected_variables
runtime_seconds
solver_name
solver_version
bound
mip_gap
diagnostics
```

`INFEASIBLE` 时不要求虚假的 Recovery Solution。

---

# 45. Phase 2.1：Cost Contract

进入任何模型前，必须定义集中式测试成本。

至少区分：

```text
flight delay cost
flight cancellation cost
aircraft reassignment cost
crew reassignment cost
passenger arrival-delay cost
unserved passenger cost
route-change cost
ferry cost
deadhead cost
```

要求：

1. 单位明确；
2. 来源明确；
3. 不伪装成真实航空公司成本；
4. 能解释模型选择；
5. 写入 `assumptions.md`；
6. 测试中不得散落 Magic Numbers。

建议集中定义：

```text
FixedColumnCostConfig
```

---

# 46. 不允许为迎合 Manual Reference 调成本

错误做法：

```text
先要求 Solver 必须得到 80 min Reference
→
再反向调成本
```

正确做法：

```text
先定义透明成本
    ↓
模型求解
    ↓
与 Manual Reference 比较
```

如果 Solver 找到更低成本的合法解，应分析原因，而不是强迫模型匹配人工 Reference。

---

# 47. Phase 2.2：Fixed-Column SRM

目标：

> 独立验证 Schedule Recovery Model。

核心决策围绕：

```text
Flight Option Selection
```

至少实现并验证：

- Base Flight Coverage / Option Selection；
- Cancellation；
- Strategic Flight；
- Arrival Capacity；
- Departure Capacity；
- Gate Constraint（仅在 Gate Semantics 正式冻结后）；
- Market / Seat 相关约束按论文和当前数据能力逐项核实；
- SRM Cost。

不要在 SRM 中直接混入完整 Aircraft / Crew / Passenger 决策。

---

# 48. SRM Tests

至少：

```text
Normal benchmark
Capacity violation
Forced cancellation
Strategic flight has no feasible operating option
Capacity end-boundary
```

测试必须检查：

```text
selected variables
constraint satisfaction
objective components
```

而不只是：

```text
status == OPTIMAL
```

---

# 49. Phase 2.3：Fixed-Column ARM

核心输入：

```text
Aircraft Strings
B_AS
A_OS
A_MS
```

验证：

- 每架 Aircraft 的 String Selection；
- Operated Flight Option Aircraft Coverage；
- Aircraft Reassignment；
- End Station；
- Maintenance；
- Aircraft Cost。

Benchmark001 必须能够表达：

```text
AC1 → F10
AC4 → F3
```

如果 ARM 结构天然禁止该 Swap，则模型映射有问题。

---

# 50. ARM Negative Tests

至少：

- Operated Flight 无 Aircraft Coverage；
- 同一 Operated Flight 被两个 Aircraft 覆盖；
- Aircraft 无可选 String；
- Required End Station 不满足；
- Maintenance 无可行 String。

---

# 51. Phase 2.4：Fixed-Column CRM

核心输入：

```text
Crew Pairings
B_KP
A_OP
D_OP
```

关键逻辑：

```text
operate
!=
deadhead
```

Deadhead 可以影响：

```text
Crew movement
Seat use
Cost
```

但绝不能产生 Operating Flight Coverage。

---

# 52. CRM Tests

至少：

- 每个 Operated Flight 由一组 Operating Crew 覆盖；
- Missing Coverage；
- Duplicate Operating Coverage；
- Deadhead 不算 Operating Coverage；
- Crew 无可行 Pairing；
- Rating / Terminal 保持 Phase 1 规则。

---

# 53. Phase 2.5：Fixed-Column PRM

核心输入：

```text
Passenger Itineraries
B_GI
A_OI
```

Phase 2.5 必须正式解决此前一直暂缓的：

```text
Seat Capacity Contract
```

没有 Seat Capacity Contract，不能把 PRM 标为完成。

---

# 54. PRM 必须区分两种情况

```text
same base-flight itinerary but delayed option
```

与：

```text
true reaccommodation to different base flights
```

例如：

P1：

```text
F1,F2
→
F1,F2 delayed
```

不是 Base-Itinerary Reaccommodation。

P4：

```text
F2,F3
→
F8
```

才是真正 Reaccommodation。

---

# 55. PRM Tests

至少：

- Original Itinerary；
- Delayed same itinerary；
- Alternative itinerary；
- Unserved；
- Seat Capacity enough；
- Seat Capacity insufficient；
- Weighted passenger delay；
- Passenger Itinerary 只能使用被选择且实际执行的 Flight Options。

---

# 56. Phase 2 总验收

Phase 2 完成时必须：

```text
Incidence Builder PASS
SRM PASS
ARM PASS
CRM PASS
PRM PASS
```

每个模型都有：

```text
positive tests
negative tests
benchmark interpretation
```

Phase 2 仍不要求：

```text
四模型联合得到全局一致 Recovery
```

因为联合模型属于 Phase 3。

---

# 57. Phase 2 与 Phase 3 的边界

Phase 2：

```text
分别验证四个组件模型
```

Phase 3：

```text
SRM + ARM + CRM + PRM
→
Full Integrated Fixed-Column MIP
```

Phase 3 才第一次系统讨论：

```text
Manual Reference
是否在完整固定列目标下最优
```

---

# 58. Phase 2 全阶段禁止事项

在 Phase 3 Integrated Oracle 完成前，不提前实现：

```text
Benders
Column Generation
Pricing
Automatic Flight String Generation
Automatic Crew Pairing Generation
Branching
Large-scale airline data
```

---

# 59. 本次 Codex Report 要求

报告写入：

```text
docs/codex_reports/
```

至少包含：

```text
1. Baseline commit
2. Modified files
3. JSON Schema contract cleanup
4. Index structures
5. Incidence structures
6. Operate / Deadhead / Ferry / Cancel semantics
7. Capacity boundary implementation
8. Benchmark001 checked incidence facts
9. Tests added
10. pytest result
11. Known limitations
12. Whether Phase 2.0 is PASS
13. Exact next step: Phase 2.1
```

---

# 60. Phase 2.0 PASS 模板

只有全部通过才可报告：

```text
Phase 2.0 PASS

Phase 1 contract cleanup:
- JSON Schema strictness aligned with Pydantic: PASS

Indices:
- deterministic ordering: PASS
- stable bidirectional lookup: PASS

Incidence:
- base flight → options: PASS
- aircraft → strings: PASS
- crew → pairings: PASS
- passenger group → itineraries: PASS
- option → aircraft strings: PASS
- option → operating crew pairings: PASS
- option → deadhead pairings: PASS
- option → passenger itineraries: PASS
- maintenance → strings: PASS
- departure capacity → options: PASS
- arrival capacity → options: PASS

Semantics:
- cancel excluded from physical coverage: PASS
- ferry has no base flight: PASS
- ferry uses airport movement capacity: PASS
- deadhead excluded from operating coverage: PASS
- [start,end) boundary: PASS
- gate incidence intentionally deferred: PASS

Benchmark regression: PASS
All tests: PASS

Next:
Phase 2.1 — Solver / Cost / ModelResult Contract
```

如果任何核心项未完成：

```text
Phase 2.0 NOT COMPLETE
```

并明确列出阻塞项。
