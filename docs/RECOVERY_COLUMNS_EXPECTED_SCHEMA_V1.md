# Recovery Columns / Expected Schema v1.0.0

## 1. 总原则

本项目后续统一采用：

```text
原始 Scenario
   ↓
flight_options
   ↓
aircraft_strings / crew_pairings / passenger_itineraries
   ↓
solver
   ↓
expected / solution
```

**禁止**再用 `F2_DELAY50`、`F2_CANCEL` 这类新 Flight ID 表示恢复动作。

应始终保持：

```text
base_flight_id = F2
```

恢复副本通过独立的：

```text
option_id
```

表示，例如：

```text
FO_F2_ORIG
FO_F2_D50
FO_F2_CANCEL
FO_F2_DEST_D
```

这样 incidence matrix、fixed-column model、column generation 始终能稳定映射回同一个原始航班。

---

# 2. Columns Schema

顶层：

```text
schema_version
scenario_id
time_unit
flight_options
aircraft_strings
crew_pairings
passenger_itineraries
```

## 2.1 flight_options

这是最底层“航班恢复副本”。

关键字段：

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
```

### operation_type

允许：

```text
operate
cancel
ferry
```

### change_types

可以组合：

```text
unchanged
delay
cancel
origin_change
destination_change
block_time_change
positioning
```

因此同一个 option 可以表达：

```text
delay + destination_change
```

不需要再造新的枚举类型。

### cancellation

取消属于 flight-level option：

```text
operation_type = cancel
```

此时：

```text
origin/destination/dep_time/arr_time = null
```

取消 option **不得**进入 aircraft string，也不得作为 crew operate segment 或 passenger flight segment。

### destination change

例如：

```text
base_flight_id = F11
operation_type = operate
change_types = [destination_change]

origin = A
destination = C
```

原航班身份仍然是 F11。

### ferry

调机航班没有对应原始计划航班：

```text
base_flight_id = null
operation_type = ferry
change_types = [positioning]
```

---

## 2.2 aircraft_strings

每条 string 表示一架具体飞机的完整候选执行路径：

```text
string_id
aircraft_id
leg_option_ids
start_station
end_station
maintenance_satisfied
cost_components
```

### Aircraft reassignment

不需要特殊 flight action。

如果：

```text
AC1 的 string
```

引用了：

```text
base flight F10
```

而 F10 原计划飞机是 AC4，

那么选择该 string 就自然表示：

```text
aircraft reassignment: F10 AC4 → AC1
```

---

## 2.3 crew_pairings

顶层：

```text
pairing_id
crew_id
duties
start_station
end_station
cost_components
```

每个 duty 包含有序 segments。

segment_type 支持：

```text
operate
deadhead
ground_transfer
rest
```

### Crew reassignment

若某 Crew Pairing 的 `operate` segment 覆盖了原本属于其他 crew 的航班 option，即表示换组。

---

## 2.4 passenger_itineraries

字段：

```text
itinerary_id
pax_group_id
status
segments
final_destination
arrival_time
arrival_delay_minutes
cost_components
```

status：

```text
transported
unserved
```

可表达：

- 保持原路径；
- 延误后的同一路径；
- 改签其他航班；
- surface transfer；
- spill / unserved。

旅客改签不修改 passenger group ID，只选择另一条 itinerary。

---

# 3. Expected Schema

Expected 不应只保存一个完整 solution vector。

统一拆成：

```text
reference_solution
+
oracle_invariants
+
comparison_policy
+
objective
```

---

## 3.1 reference_solution

这是“一套明确的人工参考恢复方案”。

包含：

```text
selected_flight_option_by_flight
selected_aircraft_string_by_aircraft
selected_crew_pairing_by_crew
selected_passenger_itinerary_by_group

resolved_flights
recovery_actions
passenger_outcomes
metrics
```

### resolved_flights

最终逐航班状态：

```text
flight_id
selected_option_id
status
change_types
recovered_origin
recovered_destination
recovered_dep
recovered_arr
departure_delay_minutes
arrival_delay_minutes
aircraft_id
crew_id
```

所以可以完整表达：

```text
delay
cancel
目的地变化
飞机换派
机组换派
```

### recovery_actions

用于人读和前端展示。

action_type 支持：

```text
delay
cancel
origin_change
destination_change
aircraft_reassignment
crew_reassignment
passenger_reaccommodation
passenger_unserved
ferry
ground_transfer
```

一个航班可以同时出现多条 action，不要求互斥。

---

# 4. 为什么 Expected 还需要 oracle_invariants

Phase 1 计划已经明确：

> 如果存在多个等价最优解，不应强制比较完整 solution vector。

因此：

```text
reference_solution
```

只是“一套参考答案”。

真正用于自动测试的是：

```text
oracle_invariants
```

例如：

- 哪个 flight option 必须选；
- 取消数；
- 总延误；
- capacity 是否满足；
- maintenance/terminal station；
- passenger 是否全部服务；
- objective（定义后）。

这样 solver 即使返回不同但等价的飞机/机组 assignment，也不会被错误判失败。

---

# 5. benchmark001 更新后的人工参考恢复

重新完整推演后，旧的 110 分钟纯传播方案不再作为首选参考。

原因：

```text
F3 和 F10 都是 C → A
```

所以可以交换 AC1 / AC4 的后续任务。

新的人工参考策略：

```text
不取消
不改始发/目的地
不使用 ferry
允许 aircraft reassignment
允许 passenger reaccommodation
优先减少总航班延误并保证全部旅客服务
```

结果：

```text
F2  +50
F10 +20
F11 +10
```

F3 保持原计划。

飞机：

```text
AC1: F1 → F2(+50) → F10(+20)
AC4: F3 → F11(+10) → F12
```

即：

```text
F3:  AC1 → AC4
F10: AC4 → AC1
```

机组不需要换派：

```text
C1: F1 → F2(+50) → F10(+20)
C4: F3 → F11(+10)
```

旅客：

```text
P4 原 F2 → F3
```

由于 F2 11:30 才到 C、F3 已在 11:00 起飞，因此改签：

```text
P4 → F8 (B → A)
```

P6 仍使用：

```text
F10 → F11
```

所以 F11 推迟 10 分钟至 12:30，保证连接。

最终：

```text
total flight delay = 80 min
aircraft reassignments = 2
passenger reaccommodated = 15 pax
unserved = 0
```

加权旅客延误：

```text
P1: 30 × 50 = 1500
P5: 18 × 10 = 180
P6: 12 × 10 = 120

total = 1800 passenger-minutes
```

---

# 6. 重要结论

这仍然叫：

```text
manual_reference
solution_status = feasible
```

不能叫：

```text
optimal
```

因为 Phase 2 尚未固定：

- cancellation cost；
- delay cost；
- aircraft reassignment cost；
- crew reassignment cost；
- passenger disruption cost；
- route-change cost。

一旦这些成本明确，再由 fixed-column / integrated oracle 证明真正最优解。

---

# 7. Phase 2 前 Codex 应实现的 validator

建议新增：

```text
backend/schemas/columns.py
backend/schemas/expected.py
backend/services/column_validator.py
backend/services/oracle_validator.py
```

至少检查：

1. option/string/pairing/itinerary ID 唯一；
2. `base_flight_id` 引用 Scenario；
3. cancel option 字段为空；
4. aircraft string 机场、时间连续；
5. crew pairing 机场、时间连续；
6. passenger itinerary OD、时间连续；
7. expected 所有 ID 都存在于 columns；
8. 每个原航班恰好选择一个 flight option；
9. selected operated option 恰好被 aircraft string 覆盖一次；
10. selected operated option 恰好被 crew operate segment 覆盖一次；
11. passenger 不使用 cancel option；
12. aircraft terminal / maintenance；
13. airport capacity `[start,end)`；
14. metrics 与 resolved result 一致。
