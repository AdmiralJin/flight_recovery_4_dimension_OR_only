# Phase 1B 代码实施说明：Recovery Columns / Expected 的程序化语义验证

> 目标仓库：`AdmiralJin/flight_recovery_4_dimension_OR_only`  
> 目标阶段：**Phase 1B：工程验收**  
> 主 Benchmark：`phase1_benchmark_001`  
> 本任务完成后，才允许把项目状态从“Phase 1 数据与 Reference 已建立”改为“Phase 1 Completed”。  
> **本任务不实现 Solver、不实现 Incidence Matrix、不实现 SRM/ARM/CRM/PRM。**

---

# 1. 当前仓库状态

当前已经建立：

```text
Phase 0
    Scenario Schema
    Scenario Validator
    Data Editor
    toy_case_001

Phase 0.5
    Visualization

Phase 1A
    phase1_benchmark_001
    Manual Recovery Columns
    Recovery Columns JSON Schema v1.0.0
    Recovery Expected JSON Schema v1.0.0
    Manual Reference Recovery
    Oracle Invariants
    Comparison Policy
```

当前 Manual Reference：

```text
F2  +50 min
F10 +20 min
F11 +10 min

F3:
AC1 → AC4

F10:
AC4 → AC1

P4:
F2→F3
→
F8
```

核心 Reference Metrics：

```text
operated_flights = 12
cancelled_flights = 0
delayed_flights = 3

aircraft_reassignments = 2
crew_reassignments = 0

passenger_reaccommodated_groups = 1
passenger_reaccommodated_count = 15

total_flight_departure_delay_minutes = 80
passenger_delay_minutes_weighted = 1800
unserved_passengers = 0
```

该结果是：

```text
reference_type = manual_reference
solution_status = feasible
```

不是 Proven Global Optimum。

---

# 2. 开始代码前先做两个小的路径一致性修正

当前实际：

```text
schemas/
├── recovery_columns_v1.schema.json
└── recovery_expected_v1.schema.json
```

部分 Markdown 仍写：

```text
schemas/recovery/
```

### 本任务要求

**不要为了这一步额外搬目录。**

统一文档引用为当前实际：

```text
schemas/recovery_columns_v1.schema.json
schemas/recovery_expected_v1.schema.json
```

避免在同一个 Phase 中继续改目录结构。

---

# 3. Phase 1B 的真正目标

Phase 1A 已经回答：

> “人工想表达什么？”

Phase 1B 必须回答：

> “程序能否证明这些 Columns / Expected 在当前 Phase 1 规则下内部一致、资源连续、容量合法，并且 Reference Metrics 可以从数据重新计算得到？”

完整闭环：

```text
Scenario JSON
    ↓
Scenario Pydantic + Semantic Validator
    ↓
Recovery Columns JSON
    ↓
Recovery Columns Pydantic
    ↓
Column Semantic Validator
    ↓
Expected JSON
    ↓
Expected Pydantic
    ↓
Oracle Semantic Validator
    ↓
Recompute Reference Metrics
    ↓
与 Expected Metrics 对比
```

Phase 1B 不求解任何优化模型。

---

# 4. 本任务最终建议新增文件

建议：

```text
backend/
├── schemas/
│   ├── columns.py
│   └── expected.py
│
└── services/
    ├── column_validator.py
    ├── oracle_validator.py
    └── recovery_metrics.py

tests/
├── unit/
│   ├── test_columns_schema.py
│   ├── test_expected_schema.py
│   ├── test_column_validator.py
│   └── test_oracle_validator.py
│
└── regression/
    └── test_phase1_benchmark_001.py
```

可按现有项目风格调整具体拆分，但必须保持职责分离。

---

# 5. 不建议新增的内容

本 Phase 不要新增：

```text
backend/core/incidence.py
backend/core/srm.py
backend/core/arm.py
backend/core/crm.py
backend/core/prm.py
```

也不要新增：

```text
/api/solve 的真实求解逻辑
Gurobi
Pyomo
Column Generation
Benders
```

不要因为已经有 Manual Reference 就提前“求解”。

---

# 6. Python Schema 的统一风格

现有项目已经有：

```python
class SchemaModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )
```

新的 Recovery Schema 应继续继承当前：

```text
backend.schemas.common.SchemaModel
```

必须保持：

```text
extra = forbid
```

即 JSON 中出现未定义字段必须报错。

时间字段继续使用：

```python
AwareDatetime
```

不要使用普通 `datetime` 允许无时区时间。

---

# 7. `backend/schemas/columns.py`

需要完整映射：

```text
schemas/recovery_columns_v1.schema.json
```

建议定义：

```text
RecoveryColumns
FlightOption
AircraftString
CrewPairing
CrewDuty
CrewSegment
PassengerItinerary
PassengerSegment
```

并定义对应 Enum。

---

# 8. Flight Option Schema

建议：

```python
class FlightOperationType(str, Enum):
    OPERATE = "operate"
    CANCEL = "cancel"
    FERRY = "ferry"
```

```python
class FlightChangeType(str, Enum):
    UNCHANGED = "unchanged"
    DELAY = "delay"
    CANCEL = "cancel"
    ORIGIN_CHANGE = "origin_change"
    DESTINATION_CHANGE = "destination_change"
    BLOCK_TIME_CHANGE = "block_time_change"
    POSITIONING = "positioning"
```

FlightOption 至少包含：

```text
option_id
base_flight_id
operation_type
change_types
origin
destination
dep_time
arr_time
block_minutes
departure_delay_minutes
arrival_delay_minutes
notes
```

---

# 9. Flight Option 的 Pydantic 层校验

Pydantic 层处理“字段自身是否合法”。

## `operate`

必须：

```text
origin != null
destination != null
dep_time != null
arr_time != null
block_minutes != null
```

并：

```text
dep_time < arr_time
```

---

## `cancel`

必须：

```text
base_flight_id != null

origin = null
destination = null
dep_time = null
arr_time = null
block_minutes = null
departure_delay_minutes = null
arrival_delay_minutes = null
```

并建议要求：

```text
"cancel" in change_types
```

取消 Option 不代表实际航段。

---

## `ferry`

必须：

```text
base_flight_id = null
origin != null
destination != null
dep_time != null
arr_time != null
block_minutes != null
```

并建议：

```text
"positioning" in change_types
```

---

# 10. Change Types 的一致性

必须避免类似：

```text
change_types = ["unchanged", "delay"]
```

这种自相矛盾表达。

建议规则：

## unchanged

若：

```text
"unchanged" in change_types
```

则：

```text
len(change_types) == 1
```

---

## cancel

若：

```text
operation_type == cancel
```

则：

```text
change_types == ["cancel"]
```

---

## ferry

至少：

```text
positioning
```

---

# 11. `backend/schemas/expected.py`

需要映射：

```text
schemas/recovery_expected_v1.schema.json
```

建议定义：

```text
RecoveryExpected
ReferenceSolution
ResolvedFlight
RecoveryAction
PassengerOutcome
RecoveryMetrics
OracleInvariants
ComparisonPolicy
RecoveryObjective
EquivalentPattern
```

Enum：

```text
ReferenceType
SolutionStatus
ResolvedFlightStatus
RecoveryActionType
RecoveryEntityType
PassengerOutcomeStatus
```

---

# 12. Python 关键字 `from`

Expected JSON 中：

```json
{
  "from": {},
  "to": {}
}
```

Python 不能使用：

```python
from
```

作为字段名。

建议：

```python
from_: dict[str, Any] | None = Field(alias="from")
to: dict[str, Any] | None
```

序列化时：

```python
model_dump(
    mode="json",
    by_alias=True,
)
```

必须重新输出：

```json
"from"
```

而不是：

```json
"from_"
```

---

# 13. `RecoveryMetrics`

必须定义正式类型，不要使用：

```python
dict[str, Any]
```

当前 Metrics：

```text
operated_flights
cancelled_flights
delayed_flights
origin_changed_flights
destination_changed_flights

aircraft_reassignments
crew_reassignments

passenger_reaccommodated_groups
passenger_reaccommodated_count

total_flight_departure_delay_minutes
passenger_delay_minutes_weighted
unserved_passengers
```

全部：

```text
integer >= 0
```

---

# 14. ValidationIssue 风格

当前 Scenario Validator 返回：

```text
location
code
message
```

Phase 1B 必须沿用相同错误结构。

例如：

```json
{
  "location": "aircraft_strings[2].leg_option_ids[1]",
  "code": "unknown_flight_option",
  "message": "flight option 'FO_X' does not exist"
}
```

不要另外创造：

```text
error_type
field
detail
```

等第二套错误协议。

---

# 15. 是否重构现有 `ValidationIssue`

可以有两种实现。

## 推荐

抽取一个小型公共模块：

```text
backend/services/validation_common.py
```

放：

```python
ValidationIssue
format_location()
issue()
```

然后：

```text
validator.py
column_validator.py
oracle_validator.py
```

共同使用。

### 要求

这次重构只能改变代码组织，**不能改变已有 Phase 0 Validator 的错误 code / location / message 行为**。

如果 Codex 认为这会引入不必要风险，也可以暂时复用 `ValidationIssue`，但最终外部错误格式必须统一。

---

# 16. Column Semantic Validator API

建议：

```python
def validate_recovery_columns(
    scenario: Scenario,
    data: Any,
) -> tuple[RecoveryColumns | None, list[ValidationIssue]]:
    ...
```

执行顺序：

```text
RecoveryColumns.model_validate(data)
    ↓
若结构失败
    return None + Pydantic Issues
    ↓
Semantic validation
```

---

# 17. Column Validator：顶层一致性

必须检查：

```text
columns.scenario_id
==
scenario.scenario_id
```

错误：

```text
scenario_id_mismatch
```

---

# 18. 所有 Recovery ID 唯一

必须检查：

```text
flight_options.option_id
aircraft_strings.string_id
crew_pairings.pairing_id
crew duties.duty_id
passenger_itineraries.itinerary_id
```

至少同一集合内唯一。

错误：

```text
duplicate_id
```

与 Phase 0 保持同类命名。

---

# 19. Flight Option：base flight 引用

对于：

```text
operation_type = operate
```

且：

```text
base_flight_id != null
```

必须确认：

```text
base_flight_id
```

存在于：

```text
scenario.flights
```

错误：

```text
unknown_flight
```

---

# 20. Flight Option：机场引用

所有实际执行 Option：

```text
operate
ferry
```

必须确认：

```text
origin
destination
```

都存在于 Scenario Airport。

错误：

```text
unknown_airport
```

---

# 21. Flight Option：Recovery Window

所有实际执行 Option：

```text
dep_time >= recovery_window.start_time
arr_time <= recovery_window.end_time
```

否则：

```text
outside_recovery_window
```

---

# 22. Flight Option：Block Time

复用：

```text
backend.schemas.common.minutes_between
```

要求：

```text
block_minutes
==
minutes_between(dep_time, arr_time)
```

错误：

```text
block_time_mismatch
```

禁止重新写一套分钟计算逻辑。

---

# 23. Flight Option：Delay 一致性

若 `base_flight_id` 指向原始 Flight：

```text
departure_delay_minutes
=
dep_time - original.sched_dep
```

```text
arrival_delay_minutes
=
arr_time - original.sched_arr
```

必须按整分钟比较。

当前 Phase 1 不允许负延误。

若：

```text
dep_time < original.sched_dep
```

则报：

```text
negative_departure_delay
```

如果计算值与 JSON 声明值不一致：

```text
departure_delay_mismatch
arrival_delay_mismatch
```

---

# 24. Flight Option：Change Type 一致性

需要根据 Original Flight 自动检查。

例如：

```text
origin != original.origin
```

则：

```text
origin_change
```

必须存在。

```text
destination != original.destination
```

则：

```text
destination_change
```

必须存在。

```text
departure_delay_minutes > 0
or
arrival_delay_minutes > 0
```

则应包含：

```text
delay
```

如果完全无变化，则应：

```text
change_types = ["unchanged"]
```

不要只相信人工填写的 `change_types`。

---

# 25. Aircraft String 语义校验

每个 Aircraft String：

```text
aircraft_id
```

必须存在。

---

## 25.1 Leg Option 引用

每个：

```text
leg_option_ids
```

必须引用已存在 Flight Option。

禁止引用：

```text
cancel
```

允许：

```text
operate
ferry
```

错误：

```text
unknown_flight_option
cancel_option_in_aircraft_string
```

---

## 25.2 Aircraft 起点

String：

```text
start_station
```

必须等于：

```text
aircraft.initial_station_at_t
```

并且第一实际 Leg：

```text
origin
```

应与 Start Station 一致。

错误：

```text
initial_station_mismatch
```

---

## 25.3 Aircraft Station Continuity

连续 Leg：

```text
previous.destination
==
next.origin
```

否则：

```text
station_discontinuity
```

---

## 25.4 Aircraft Time Continuity

当前 Phase 1 规则：

```text
previous.arr_time <= next.dep_time
```

不额外引入 Turn Time。

如果重叠：

```text
time_overlap
```

---

# 26. Aircraft Equipment Compatibility

对于 Revenue Flight：

```text
base_flight.original_equipment
==
aircraft.equipment_type
```

否则：

```text
equipment_mismatch
```

当前 Ferry Option 没有 Equipment 字段，不在 Phase 1 新增额外 Ferry Equipment 规则。

---

# 27. Aircraft 终点

String：

```text
end_station
```

必须等于：

```text
aircraft.required_station_at_T_end
```

最后一个实际 Leg Destination 也必须一致。

错误：

```text
end_station_mismatch
```

---

# 28. Maintenance

当前 Phase 1 不实现复杂 Maintenance Scheduling。

只按当前 Benchmark / Scenario Metadata 检查：

如果：

```text
aircraft.maintenance_required == true
```

则：

```text
aircraft_string.maintenance_satisfied == true
```

并且至少要求最终：

```text
end_station in aircraft.maintenance_stations
```

当前 Benchmark：

```text
AC4
required end = C
maintenance_stations = [C]
```

必须成立。

错误建议：

```text
maintenance_not_satisfied
maintenance_station_mismatch
```

不要在本 Phase 发明 Maintenance Duration / Due Time。

---

# 29. Crew Pairing 语义校验

每个：

```text
crew_id
```

必须存在。

---

# 30. Crew Segment 的解析规则

## operate

若：

```text
segment_type = operate
```

则：

```text
flight_option_id != null
```

并且对应 Option 必须是实际执行 Option。

Phase 1 禁止 Crew Operate Segment 引用：

```text
cancel
```

---

## deadhead

接口保留，但当前 Benchmark 没有使用。

若未来出现：

- 可以引用一个实际执行 Flight Option；
- 它不代表该 Crew 执行该 Flight；
- Phase 1B 只做结构/时空连续检查；
- 不实现 Seat/Deadhead Cost。

---

## ground_transfer / rest

必须使用显式：

```text
origin
destination
start_time
end_time
```

或对 Rest 使用合理的 station/time 规则。

当前 Benchmark 没有这些 Segment，不要为了测试 Benchmark 而过度开发复杂业务规则。

---

# 31. Crew Pairing Start / End

必须：

```text
pairing.start_station
==
crew.start_station_at_t
```

```text
pairing.end_station
==
crew.required_station_at_T_end
```

错误：

```text
initial_station_mismatch
end_station_mismatch
```

---

# 32. Crew Station / Time Continuity

将每个 Segment 解析为：

```text
origin
destination
start
end
```

按整个 Pairing 顺序检查：

```text
previous.destination == next.origin
previous.end <= next.start
```

错误：

```text
station_discontinuity
time_overlap
```

---

# 33. Crew Rating

对于：

```text
segment_type = operate
```

且引用 Revenue Flight：

```text
crew.rating
==
base_flight.original_equipment
```

错误：

```text
rating_mismatch
```

---

# 34. Passenger Itinerary 语义校验

每个：

```text
pax_group_id
```

必须存在。

---

# 35. Passenger `transported`

若：

```text
status = transported
```

必须：

```text
segments 非空
final_destination != null
arrival_time != null
arrival_delay_minutes != null
```

---

# 36. Passenger Flight Segment

若：

```text
segment_type = flight
```

则：

```text
flight_option_id != null
```

对应 Option 必须：

```text
operation_type = operate
```

禁止：

```text
cancel
ferry
```

Passenger 不允许乘坐 Ferry。

错误：

```text
invalid_passenger_flight_option
```

---

# 37. Passenger Surface Segment

当前 Schema 已支持：

```text
surface
```

Phase 1B 只要求：

```text
origin
destination
dep_time
arr_time
```

合法且：

```text
dep_time < arr_time
```

不要实现真实地面交通时长数据库。

---

# 38. Passenger OD 连续

Itinerary 第一段：

```text
origin
==
passenger.origin
```

连续 Segment：

```text
previous.destination
==
next.origin
```

最后：

```text
destination
==
passenger.destination
==
itinerary.final_destination
```

错误：

```text
origin_mismatch
station_discontinuity
destination_mismatch
```

---

# 39. Passenger 时间连续

当前 Phase 1：

```text
previous.arrival <= next.departure
```

不额外加入 Passenger MCT。

错误：

```text
time_overlap
```

---

# 40. Passenger Arrival Delay

必须：

```text
itinerary.arrival_time
==
last_segment.arrival
```

并且：

```text
arrival_delay_minutes
=
arrival_time - passenger.scheduled_arrival
```

非负。

错误：

```text
arrival_mismatch
arrival_delay_mismatch
```

---

# 41. Passenger `unserved`

若：

```text
status = unserved
```

建议严格要求：

```text
segments = []
final_destination = null
arrival_time = null
arrival_delay_minutes = null
```

防止同时声明：

```text
unserved
+
有实际行程
```

---

# 42. Phase 1 暂不验证 Passenger Seat Capacity

这一点必须写进代码注释和测试说明。

当前：

```text
min_seats
```

不是完整 Remaining Seat Inventory。

所以 Phase 1B：

```text
验证 itinerary 时空与 OD 合法性
```

但不声称：

```text
P4→F8 已通过完整 PRM Seat Capacity
```

不要为了让 Benchmark 通过而自行定义座位容量。

---

# 43. Oracle Validator API

建议：

```python
def validate_recovery_expected(
    scenario: Scenario,
    columns: RecoveryColumns,
    data: Any,
) -> tuple[RecoveryExpected | None, list[ValidationIssue]]:
    ...
```

执行：

```text
Pydantic
↓
Cross-reference
↓
Selected-column coverage
↓
Resolved result consistency
↓
Capacity
↓
Passenger
↓
Metric recomputation
↓
Oracle internal consistency
```

---

# 44. Expected：scenario_id

必须：

```text
expected.scenario_id
==
columns.scenario_id
==
scenario.scenario_id
```

错误：

```text
scenario_id_mismatch
```

---

# 45. Selected Flight Option Map

必须检查：

```text
selected_flight_option_by_flight
```

对于 Phase 1 Benchmark：

```text
恰好覆盖 Scenario 中全部 12 个 Flight ID
```

不能：

- 缺 Flight；
- 多未知 Flight；
- 引用不存在 Option；
- Option 的 `base_flight_id` 与 Key 不一致。

错误示例：

```text
missing_flight_selection
unknown_flight
unknown_flight_option
flight_option_base_mismatch
```

---

# 46. Selected Aircraft String Map

每个：

```text
aircraft_id → string_id
```

必须满足：

```text
aircraft_id 存在
string_id 存在
string.aircraft_id == map key
```

---

# 47. Selected Crew Pairing Map

同理：

```text
crew_id → pairing_id
```

必须严格对应。

---

# 48. Selected Passenger Itinerary Map

每个：

```text
pax_group_id → itinerary_id
```

必须：

```text
group 存在
itinerary 存在
itinerary.pax_group_id == key
```

对于 `phase1_benchmark_001`：

```text
8 个 Passenger Group 都必须选 1 条
```

---

# 49. Aircraft Coverage

从 Selected Aircraft Strings 展开全部：

```text
leg_option_ids
```

对每个 Selected Revenue Operated Flight Option：

```text
必须被 Aircraft 覆盖恰好 1 次
```

Cancel Option：

```text
必须被覆盖 0 次
```

错误：

```text
missing_aircraft_coverage
duplicate_aircraft_coverage
cancelled_flight_has_aircraft_coverage
```

Ferry 不属于 Scenario Revenue Flight Coverage，可单独存在。

---

# 50. Crew Coverage

从 Selected Crew Pairings 中读取：

```text
segment_type = operate
```

对每个 Selected Revenue Operated Flight Option：

```text
必须由 Crew operate 恰好 1 次
```

Cancel：

```text
0 次
```

错误：

```text
missing_crew_coverage
duplicate_crew_coverage
cancelled_flight_has_crew_coverage
```

Deadhead 不算 Flight Operating Coverage。

---

# 51. Resolved Flights

`resolved_flights` 必须：

```text
每个 Scenario Flight 恰好 1 条
```

不得重复或遗漏。

每条必须与：

```text
selected_flight_option_by_flight
```

一致。

---

# 52. Resolved Operated Flight

若 Selected Option：

```text
operation_type = operate
```

则：

```text
status = operated
```

并且：

```text
recovered_origin
recovered_destination
recovered_dep
recovered_arr
departure_delay_minutes
arrival_delay_minutes
```

必须全部与 Flight Option 一致。

---

# 53. Resolved Cancelled Flight

若 Selected Option：

```text
operation_type = cancel
```

则：

```text
status = cancelled
recovered_origin = null
recovered_destination = null
recovered_dep = null
recovered_arr = null
aircraft_id = null
crew_id = null
```

不要在 Phase 1B 容许“取消但仍分配飞机/机组”。

---

# 54. Resolved Aircraft / Crew Assignment

对每个 Operated Flight：

`resolved_flights.aircraft_id`

必须等于实际覆盖该 Option 的 Selected Aircraft String 的 Aircraft。

Crew 同理。

这一步可以自动得到：

```text
Aircraft Reassignment
Crew Reassignment
```

---

# 55. Airport Capacity Validation

必须基于：

```text
Selected Operated Flight Options
```

而不是原 Flight Schedule。

对于每个 `AirportInterval`：

### Departure

计数：

```text
option.origin == interval.airport
AND
option.dep_time >= interval.start_time
AND
option.dep_time < interval.end_time
```

必须：

```text
count <= dep_capacity
```

### Arrival

```text
option.destination == interval.airport
AND
option.arr_time >= interval.start_time
AND
option.arr_time < interval.end_time
```

必须：

```text
count <= arr_capacity
```

严格保持：

```text
[start_time, end_time)
```

错误：

```text
departure_capacity_exceeded
arrival_capacity_exceeded
```

---

# 56. Gate Capacity

Phase 0 文档定义了：

```text
gate_capacity
```

但 Phase 1 当前尚没有正式确定 Recoverd Gate Occupancy 的完整事件算法。

因此本 Phase 1B：

**不要悄悄实现一个未经设计的 Gate Constraint。**

做法：

- 保留 TODO / warning；
- Arrival / Departure Capacity 要验证；
- Gate Capacity 留给 Phase 2 SRM 约束设计正式处理。

这点需要在测试说明中明确。

---

# 57. Passenger Outcome

`passenger_outcomes`：

每个 Passenger Group 恰好一条。

必须与：

```text
selected_passenger_itinerary_by_group
```

一致。

---

# 58. Passenger Transported Outcome

如果 Selected Itinerary：

```text
status = transported
```

则 Outcome：

```text
status = transported
selected_itinerary_id != null
arrival_time = itinerary.arrival_time
arrival_delay_minutes = itinerary.arrival_delay_minutes
unserved_count = 0
```

---

# 59. Passenger Unserved Outcome

若 Selected Itinerary：

```text
status = unserved
```

则：

```text
outcome.status = unserved
arrival_time = null
arrival_delay_minutes = null
unserved_count = passenger.count
```

---

# 60. Recovery Actions 的定位

`recovery_actions` 是：

```text
人可读 / 前端展示
```

不是最终数学 Ground Truth 的唯一来源。

Canonical Result 应优先来自：

```text
selected options
selected strings
selected pairings
selected itineraries
resolved_flights
```

因此：

- 校验 `recovery_actions` 中 Entity 是否存在；
- 基础 from/to 是否与实际变化不矛盾；

但**不要要求 actions 数量精确等于自动推导动作数**。

否则未来 Equivalent Representation 会造成误报。

---

# 61. `recovery_metrics.py`

新增纯函数：

```python
def recompute_recovery_metrics(
    scenario: Scenario,
    columns: RecoveryColumns,
    expected: RecoveryExpected,
) -> RecoveryMetrics:
    ...
```

不要从：

```text
expected.reference_solution.metrics
```

读取结果再返回。

必须从实际 Selection / Resolved Outcome 重新计算。

---

# 62. operated / cancelled

从 `resolved_flights`：

```text
status = operated
status = cancelled
```

统计。

必须：

```text
operated + cancelled
==
len(scenario.flights)
```

---

# 63. delayed_flights

定义：

```text
departure_delay_minutes > 0
OR
arrival_delay_minutes > 0
```

的 Operated Flight 数量。

当前 Benchmark：

```text
F2
F10
F11
```

因此：

```text
3
```

---

# 64. origin / destination changed

与 Original Scenario Flight 比较：

```text
resolved.recovered_origin != original.origin
```

```text
resolved.recovered_destination != original.destination
```

取消航班不算 Origin/Destination Change。

---

# 65. Aircraft Reassignment

对于 Operated Flight：

```text
resolved.aircraft_id
!=
flight.original_aircraft
```

则 +1。

当前：

```text
F3
F10
```

所以：

```text
2
```

---

# 66. Crew Reassignment

同理：

```text
resolved.crew_id
!=
flight.original_crew
```

当前：

```text
0
```

---

# 67. Total Flight Departure Delay

对所有 Operated Flight：

```text
sum(departure_delay_minutes)
```

当前：

```text
50 + 20 + 10 = 80
```

---

# 68. Passenger Reaccommodated Group

不能通过：

```text
itinerary_id 是否含 ORIGINAL
```

判断。

正确方式：

对 Selected Itinerary 的所有 Flight Segment：

```text
flight_option
→
base_flight_id
```

得到恢复后的 Base Flight Sequence。

与：

```text
passenger.original_itinerary
```

比较。

例如：

```text
P1
selected:
FO_F1_ORIG, FO_F2_D50
→
[F1, F2]
```

和原：

```text
[F1, F2]
```

相同。

所以：

```text
不是 reaccommodation
```

P4：

```text
selected:
F8

original:
F2,F3
```

不同：

```text
reaccommodated
```

若含 Surface Segment，也视为 Reaccommodation。

---

# 69. Passenger Reaccommodated Count

所有 Reaccommodated Group：

```text
sum(passenger.count)
```

当前：

```text
P4 = 15
```

---

# 70. Weighted Passenger Delay

只对：

```text
transported
```

的 Passenger：

```text
passenger.count
*
arrival_delay_minutes
```

求和。

当前：

```text
P1: 30 × 50 = 1500
P5: 18 × 10 = 180
P6: 12 × 10 = 120

total = 1800
```

---

# 71. Unserved Passengers

对 Outcome：

```text
status = unserved
```

累加：

```text
unserved_count
```

并与 Passenger Group Count 一致。

当前：

```text
0
```

---

# 72. Expected Metrics 对比

自动复算：

```text
observed_metrics
```

必须同时与：

```text
reference_solution.metrics
oracle_invariants.required_metrics
```

比较。

任何一个不一致：

```text
metric_mismatch
```

错误位置必须具体：

```text
reference_solution.metrics.total_flight_departure_delay_minutes
```

---

# 73. Oracle Invariants 内部一致性

当前：

```text
oracle_invariants.required_flight_option_by_flight
```

应该与 Reference 中当前 Benchmark 必须要求的 Flight Decision 相符。

Phase 1B 至少检查：

- Flight IDs 合法；
- Option IDs 合法；
- Option Base Flight 正确；
- `expected_cancelled_flights` 与 Required Flight Options 中 Cancel 状态一致；
- `required_metrics` 可由 Reference 复算。

---

# 74. Comparison Policy

`comparison_policy` 本阶段只做结构合法性。

不要在 Phase 1B 写：

```text
solver result comparator
```

因为还没有 Solver Result。

后面 Integrated Oracle / Solver 接入时再实现：

```text
compare_solution_to_oracle()
```

---

# 75. Objective

当前 Expected：

```text
objective.status = not_defined
objective.value = null
```

如果：

```text
status = not_defined
```

必须：

```text
value = null
```

不要填：

```text
80
```

因为 80 是：

```text
flight-delay metric
```

不是 AIR Monetary Objective。

---

# 76. Phase 1 Benchmark Regression Test

新增：

```text
tests/regression/test_phase1_benchmark_001.py
```

应真实读取：

```text
data/examples/phase1_benchmark_001.json
data/columns/phase1_benchmark_001_columns.json
data/expected/phase1_benchmark_001_expected.json
```

禁止在 Test 中重新手写一份 Benchmark。

---

# 77. Benchmark Regression：第一层

```python
scenario, scenario_issues = validate_scenario(...)
```

必须：

```text
scenario != None
scenario_issues == []
```

---

# 78. Benchmark Regression：第二层

```python
columns, column_issues = validate_recovery_columns(...)
```

必须：

```text
columns != None
column_issues == []
```

---

# 79. Benchmark Regression：第三层

```python
expected, oracle_issues = validate_recovery_expected(...)
```

必须：

```text
expected != None
oracle_issues == []
```

---

# 80. Benchmark Regression：硬性事实

必须 assert：

```text
Scenario:
4 airports
12 flights
4 aircraft
5 crew
8 passenger groups
```

Columns：

```text
22 flight options
11 aircraft strings
10 crew pairings
17 passenger itineraries
```

如果实际文件数量和这里不同，以当前人工 Column 文件为准，但 Codex 必须先核对，不能静默改测试。

---

# 81. Benchmark Recovery Facts

必须明确断言：

```text
F2 = FO_F2_D50
F3 = FO_F3_ORIG
F10 = FO_F10_D20
F11 = FO_F11_D10
```

---

# 82. Benchmark Aircraft

必须：

```text
AC1 → AS_AC1_SWAP_F10
AC4 → AS_AC4_SWAP_F3_ORIG
```

并验证展开后：

```text
AC1:
F1 → F2 → F10

AC4:
F3 → F11 → F12
```

---

# 83. Benchmark Crew

Reference：

```text
C1:
F1 → F2 → F10

C4:
F3 → F11
```

Crew Reassignment：

```text
0
```

---

# 84. Benchmark Passenger

必须：

```text
P4 → PI_P4_REACCOM_F8
```

并验证 Base Flight Sequence：

```text
[F8]
```

不同于：

```text
[F2,F3]
```

---

# 85. Benchmark Capacity

B：

```text
[09:30,10:30)
dep_capacity = 2
```

Reference 中：

```text
F5 09:50
F8 10:00
```

F2：

```text
10:30
```

不属于当前桶。

因此：

```text
2 <= 2
```

必须通过。

特别测试边界：

```text
dep_time == interval.end_time
```

不计入该桶。

---

# 86. Benchmark Maintenance

AC4 Selected String：

```text
AS_AC4_SWAP_F3_ORIG
```

必须：

```text
start C
end C
maintenance_satisfied = true
```

并满足：

```text
C in AC4.maintenance_stations
```

---

# 87. Benchmark Metrics

程序重新计算必须严格等于：

```text
operated_flights = 12
cancelled_flights = 0
delayed_flights = 3
origin_changed_flights = 0
destination_changed_flights = 0

aircraft_reassignments = 2
crew_reassignments = 0

passenger_reaccommodated_groups = 1
passenger_reaccommodated_count = 15

total_flight_departure_delay_minutes = 80
passenger_delay_minutes_weighted = 1800
unserved_passengers = 0
```

不能直接 assert JSON 自己等于 JSON 自己。

---

# 88. Negative Tests：总体原则

不要为每个错误复制一个完整 1300 行 JSON。

推荐：

```python
copy.deepcopy(valid_columns)
copy.deepcopy(valid_expected)
```

然后只破坏一个字段。

每个 Negative Test 必须确认：

```text
特定 code 出现
```

不要只断言：

```text
issues != []
```

---

# 89. 必做 Negative Tests：Columns

至少：

## N1 Duplicate Flight Option

制造重复：

```text
option_id
```

期望：

```text
duplicate_id
```

---

## N2 Unknown Base Flight

```text
base_flight_id = FX
```

期望：

```text
unknown_flight
```

---

## N3 Cancel Option 仍有 dep_time

期望结构/Pydantic 或语义错误。

---

## N4 Aircraft String 引用 Cancel

期望：

```text
cancel_option_in_aircraft_string
```

---

## N5 Aircraft Station Discontinuity

破坏：

```text
previous.destination != next.origin
```

期望：

```text
station_discontinuity
```

---

## N6 Aircraft Time Overlap

期望：

```text
time_overlap
```

---

## N7 Wrong Aircraft End Station

期望：

```text
end_station_mismatch
```

---

## N8 Maintenance Failure

把 AC4：

```text
maintenance_satisfied = false
```

期望：

```text
maintenance_not_satisfied
```

---

## N9 Crew Station Discontinuity

期望：

```text
station_discontinuity
```

---

## N10 Passenger Wrong Destination

期望：

```text
destination_mismatch
```

---

## N11 Passenger Uses Cancel Option

期望：

```text
invalid_passenger_flight_option
```

---

# 90. 必做 Negative Tests：Expected

## N12 Unknown Selected Aircraft String

期望：

```text
unknown_aircraft_string
```

---

## N13 Missing Aircraft Coverage

修改 Selected String 让某 Operated Flight 无 Aircraft。

期望：

```text
missing_aircraft_coverage
```

---

## N14 Duplicate Aircraft Coverage

期望：

```text
duplicate_aircraft_coverage
```

---

## N15 Missing Crew Coverage

期望：

```text
missing_crew_coverage
```

---

## N16 Capacity Violation

将 F2 Selection 恢复：

```text
FO_F2_ORIG
```

同时保持：

```text
F5
F8
```

则 B `[09:30,10:30)`：

```text
3 > 2
```

期望：

```text
departure_capacity_exceeded
```

---

## N17 Metrics Tampering

例如：

```text
total_flight_departure_delay_minutes = 81
```

期望：

```text
metric_mismatch
```

---

## N18 Scenario ID Mismatch

期望：

```text
scenario_id_mismatch
```

---

# 91. JSON Schema 文件与 Pydantic 的关系

当前：

```text
schemas/recovery_columns_v1.schema.json
schemas/recovery_expected_v1.schema.json
```

作为：

```text
外部交换 Contract / 文档 Contract
```

Python Pydantic Models 是：

```text
运行时代码 Contract
```

Phase 1B 要求两者在字段、枚举和 Nullability 上保持一致。

不要在 Pydantic 中偷偷添加 JSON Schema 不存在的业务字段。

如果确实发现 JSON Schema 有设计错误：

1. 先明确说明；
2. 同时修改 JSON Schema；
3. 修改 `RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md`；
4. 更新 Schema Version（如果是 Breaking Change）；
5. 不允许只在 Python 中绕过去。

---

# 92. 不强求 `model_json_schema()` 与手写 JSON Schema 字节级一致

Pydantic 自动输出 Schema 的组织形式可能不同。

因此不要写脆弱测试：

```text
pydantic.model_json_schema()
==
手工 json 文件
```

应该测试：

- 当前正式 benchmark 可以同时被 Pydantic 接受；
- 字段/枚举/required/nullability 按设计一致；
- 关键负例两层都能阻止。

---

# 93. 测试 Fixtures

当前：

```text
tests/conftest.py
```

只有：

```text
toy_case
```

建议增加：

```python
@pytest.fixture
def phase1_benchmark_001_data()

@pytest.fixture
def phase1_columns_001_data()

@pytest.fixture
def phase1_expected_001_data()
```

都：

```text
deepcopy
```

防止测试间污染。

---

# 94. 不要删除现有 `phase1_validation_001`

当前仓库已经有：

```text
phase1_validation_001
```

及对应 regression。

它与：

```text
phase1_benchmark_001
```

用途不同。

本任务不要为了“名字统一”删除旧 validation fixture。

保留：

```text
phase1_validation_001
    = Scenario-level Phase 1 validation fixture

phase1_benchmark_001
    = Recovery Columns / Expected integration benchmark
```

---

# 95. Existing Phase 0 Regression 不能回归

必须保证：

```bash
python -m pytest
```

现有全部测试通过。

特别关注：

```text
tests/regression/test_toy_cases.py
tests/regression/test_phase1_validation_case.py
```

不能为了新的 Validator 修改原 Scenario Validator 的语义。

---

# 96. 是否增加 API

本 Phase **不要求新增 API**。

不要增加：

```text
/api/validate-columns
/api/validate-expected
```

除非项目现有计划明确要求前端使用。

当前优先完成：

```text
Python service API
+
tests
```

等 Phase 2 / Solver 接入后再决定 HTTP Boundary。

---

# 97. 是否修改 Frontend

本 Phase：

```text
不要修改 frontend
```

尤其不要把：

```text
Expected
Recovered Plan
```

提前接到 Visualization。

Phase 0.5 的 Recovered Plan 继续保持 Disabled。

---

# 98. 是否修改 `/api/solve`

不要。

当前：

```text
合法 Scenario → HTTP 501
```

继续保留。

只有真正有审计后的 Solver 后才修改。

---

# 99. Codex 实施顺序

严格建议：

## Step 0

修正文档路径引用：

```text
docs/benchmarks → docs/benchmark
schemas/recovery/... → schemas/...
```

不要搬目录。

---

## Step 1

建立：

```text
backend/schemas/columns.py
```

并完成 Schema Unit Tests。

---

## Step 2

建立：

```text
backend/schemas/expected.py
```

并完成 Schema Unit Tests。

---

## Step 3

建立公共 Validation Issue 支持（如需要）。

保证 Phase 0 Validator 行为不变。

---

## Step 4

实现：

```text
column_validator.py
```

先让：

```text
phase1_benchmark_001_columns
```

Semantic PASS。

---

## Step 5

增加 Column Negative Tests。

---

## Step 6

实现：

```text
recovery_metrics.py
```

单独测试各 Metrics。

---

## Step 7

实现：

```text
oracle_validator.py
```

---

## Step 8

增加 Expected Negative Tests。

---

## Step 9

增加：

```text
test_phase1_benchmark_001.py
```

完成 Scenario → Columns → Expected 全链 regression。

---

## Step 10

完整运行：

```bash
python -m pytest
```

---

# 100. 完成标准

Phase 1B 只有全部满足才算完成。

## Schema

- [ ] Recovery Columns Pydantic Model 完整；
- [ ] Expected Pydantic Model 完整；
- [ ] 所有未知字段拒绝；
- [ ] AwareDatetime；
- [ ] Enum 与 JSON Schema 一致。

## Column Semantics

- [ ] ID 唯一；
- [ ] Flight Option 引用合法；
- [ ] Delay 自动核算；
- [ ] Change Type 一致；
- [ ] Aircraft String 时空连续；
- [ ] Equipment 合法；
- [ ] End Station 合法；
- [ ] Maintenance 合法；
- [ ] Crew Pairing 时空连续；
- [ ] Crew Rating 合法；
- [ ] Passenger Itinerary OD/Time 合法；
- [ ] Cancel/Ferry 使用边界正确。

## Expected Semantics

- [ ] Selected IDs 全部合法；
- [ ] 每个 Flight 恰好一个 Selection；
- [ ] Operated Flight Aircraft Coverage = 1；
- [ ] Operated Flight Crew Coverage = 1；
- [ ] Cancelled Flight Coverage = 0；
- [ ] Resolved Flight 与 Selected Option 一致；
- [ ] Passenger Outcome 一致；
- [ ] Airport Arrival/Departure Capacity 合法；
- [ ] Maintenance / Terminal 合法。

## Metrics

- [ ] Metrics 从数据重算；
- [ ] 不读取 Expected Metrics 作为计算来源；
- [ ] Benchmark 得到 80 Flight Delay；
- [ ] Aircraft Reassignment = 2；
- [ ] Crew Reassignment = 0；
- [ ] P4 Reaccommodation = 15 pax；
- [ ] Weighted Passenger Delay = 1800；
- [ ] Unserved = 0。

## Tests

- [ ] Positive Benchmark Test；
- [ ] 至少上述 18 类 Negative Scenario 中的核心错误均覆盖；
- [ ] 每个 Negative Test 检查具体 Error Code；
- [ ] 原 Phase 0 / 0.5 Test 无回归；
- [ ] `python -m pytest` 全部 PASS。

---

# 101. Phase 1 完成后的文档更新

当以上代码和测试全部通过后，Codex 可以更新：

```text
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
reproduction_notes.md
```

将：

```text
Phase 1 工程验收 🚧
```

改为：

```text
Phase 1 ✅ Completed
```

并注明：

```text
Phase 1 proves data/column/oracle semantic consistency,
not mathematical optimality of the AIR recovery objective.
```

不要把：

```text
manual_reference
```

改为：

```text
solver_optimal
```

---

# 102. Phase 1 完成后的下一阶段

Phase 1B 完成后：

```text
Phase 2.0
Incidence Matrix Builder
```

而不是立刻开始复杂 Solver。

下一阶段首先建立：

```text
Flight Option × Aircraft String
Flight Option × Crew Pairing
Flight Option × Passenger Itinerary
Maintenance × Aircraft String
```

等 Incidence Matrix 有独立测试后，再进入：

```text
Fixed-column SRM
Fixed-column ARM
Fixed-column CRM
Fixed-column PRM
```

---

# 103. 本任务明确禁止

不要：

- 实现 Gurobi；
- 实现任何 MIP；
- 实现 SRM/ARM/CRM/PRM；
- 实现 Benders；
- 实现 Pricing；
- 实现 Column Generation；
- 自动生成新 Flight String；
- 自动生成 Crew Pairing；
- 自动生成 Passenger Itinerary；
- 增加真实 Airline Business Rules；
- 增加 Passenger MCT；
- 增加 Aircraft Turn Time；
- 增加 Crew Duty Limits；
- 自行定义 Passenger Seat Inventory；
- 修改 Manual Reference 为“Optimal”；
- 启用前端 Recovered Plan；
- 修改 `/api/solve` 501 安全闸门。

---

# 104. Codex 最终回复必须报告

完成后必须明确列出：

```text
1. Modified Files
2. Added Python Models
3. Added Semantic Validation Rules
4. Added Metric Recalculation
5. Positive Benchmark Result
6. Negative Tests Added
7. pytest Result
8. Any Existing Data Inconsistency Found
9. Any Assumption Added
10. Whether Phase 1 Acceptance Criteria Are Fully Met
```

如果任何项没完成，必须明确：

```text
Phase 1 is NOT complete
```

不要用：

```text
mostly done
basically complete
```

替代验收结论。

---

# 105. 最终验收结论模板

如果全部通过，Codex 最终应能给出类似：

```text
Phase 1B PASS

phase1_benchmark_001:
- Scenario semantic validation: PASS
- Recovery Columns structural validation: PASS
- Recovery Columns semantic validation: PASS
- Expected structural validation: PASS
- Expected semantic validation: PASS
- Aircraft coverage: PASS
- Crew coverage: PASS
- Airport capacity: PASS
- Maintenance/terminal: PASS
- Passenger itinerary continuity: PASS
- Metrics recomputation: PASS

Recomputed metrics:
- total flight delay = 80
- aircraft reassignment = 2
- crew reassignment = 0
- passenger reaccommodation = 15 pax
- weighted passenger delay = 1800 passenger-min
- unserved passengers = 0

All existing and new tests: PASS

Phase 1 = Completed
Next: Phase 2.0 Incidence Matrix Builder
```

只有能程序化得到以上结果，Phase 1 才正式结束。
