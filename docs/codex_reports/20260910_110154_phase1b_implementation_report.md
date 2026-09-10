# Codex 工作报告：Phase 1B 程序化语义验证

- 时间：2026-09-10 11:01:54（Asia/Shanghai）
- 工作区：`D:\python_project\flight_recovery`
- 任务依据：`docs/chatgpt_review/PHASE1B_CODE_IMPLEMENTATION.md`
- 验收结论：**Phase 1B PASS；Phase 1 Completed**

## 1. 任务目标

在不实现 Solver、Incidence Matrix、SRM/ARM/CRM/PRM、Benders 或 Column Generation 的前提下，完成以下程序化验证闭环：

```text
Scenario JSON
→ Scenario Schema / Semantic Validator
→ Recovery Columns Schema / Semantic Validator
→ Expected Schema / Oracle Validator
→ Reference Metrics Recalculation
→ Expected Metrics Comparison
```

## 2. 项目检查

实施前阅读并核对了项目 Markdown 文档、Phase 0/0.5 约束、Phase 1 Benchmark、Columns/Expected Schema、人工 Reference 和 Phase 1B 验收标准。正式资产规模为：

```text
Scenario: 4 airports / 12 flights / 4 aircraft / 5 crew / 8 passenger groups
Columns: 22 flight options / 11 aircraft strings / 10 crew pairings / 17 passenger itineraries
```

实施前既有测试结果为 `31 passed`。

## 3. Python Schema

新增 `backend/schemas/columns.py`，实现：

- `RecoveryColumns`、`FlightOption`、`AircraftString`；
- `CrewPairing`、`CrewDuty`、`CrewSegment`；
- `PassengerItinerary`、`PassengerSegment`；
- Flight、Crew、Passenger 相关 Enum。

新增 `backend/schemas/expected.py`，实现：

- `RecoveryExpected`、`ReferenceSolution`、`ResolvedFlight`；
- `RecoveryAction`、`PassengerOutcome`、`RecoveryMetrics`；
- `OracleInvariants`、`ComparisonPolicy`、`RecoveryObjective`；
- `EquivalentPattern` 及相关 Enum。

所有模型继承 `SchemaModel`，拒绝未知字段；时间使用 `AwareDatetime`；字段、枚举和 Nullability 与 JSON Contract 对齐。Recovery Action 的 Python 字段 `from_` 使用 `from` 别名，按别名序列化后仍输出 `"from"`。

## 4. ValidationIssue

新增 `backend/services/validation_common.py`，统一提供 `ValidationIssue`、Location 格式化、Issue 构造和 Pydantic 错误转换。原 `validator.py` 改为复用公共结构，保持 Phase 0 的 `location / code / message` 行为不变。

## 5. Columns 语义校验

新增 `backend/services/column_validator.py`，覆盖：

- Scenario ID 和所有 Recovery ID 一致性/唯一性；
- Flight、Airport、Aircraft、Crew、Passenger、Option 引用；
- Operate、Cancel、Ferry 字段边界；
- Block Time、Departure/Arrival Delay、Max Delay、Change Type 自动核对；
- Aircraft String 时空连续、机型、终点和维修；
- Crew Pairing 时空连续和 Rating；
- Passenger Itinerary OD、时间、到达结果和 Unserved 规则；
- Passenger 禁止使用 Cancel/Ferry Option。

Phase 1 按设计只验证 Passenger 路径、OD 和时间，不声称已验证剩余座位容量。

## 6. Expected / Oracle 语义校验

新增 `backend/services/oracle_validator.py`，覆盖：

- Flight/Aircraft/Crew/Passenger Selection 完整性和引用；
- Operated Flight 的 Aircraft/Crew Coverage 恰好为 1；
- Cancelled Flight Coverage 为 0；
- Resolved Flight 与 Selected Option/Resource 一致；
- Passenger Outcome 与 Selected Itinerary 一致；
- Recovery Action 的实体及基础 `from/to` 一致；
- Airport Arrival/Departure Capacity，严格使用 `[start,end)`；
- Oracle Required Options、Cancelled Flights 和 Metrics 内部一致。

Gate Capacity 未实现未经设计的 Occupancy 算法，并通过代码注释和测试明确留给后续阶段。

## 7. Metrics 重算

新增 `backend/services/recovery_metrics.py`。指标从 Scenario、Columns、Selections、Resolved Flights 和 Passenger Outcomes 重算，不读取 Expected 中声明的 Metrics 作为计算来源。

Passenger Reaccommodation 根据恢复后的 Base Flight Sequence 与原 Itinerary 比较，不依赖 Itinerary ID 命名。

## 8. 发现的问题与假设

P4 改签 F8 后比原计划提前 60 分钟到达，但正式 Columns/Expected 将 `arrival_delay_minutes` 记为 0，同时 Phase 1B 要求该指标非负。因此在 `assumptions.md` 新增 A-020：

```text
passenger arrival delay = max(0, recovered_arrival - scheduled_arrival)
```

即提前到达不产生负延误，也不抵扣其他旅客的正延误。

此外，为 `data/examples/PHASE1_BENCHMARK_001_DESIGN.md` 增加历史说明，明确旧 110 分钟纯传播方案已被当前 80 分钟 Reference 取代。正式 Scenario、Columns 和 Expected JSON 未发现内部不一致。

## 9. 测试

扩展 `tests/conftest.py`，增加三个 Phase 1 深拷贝 Fixture。新增：

- `tests/unit/test_columns_schema.py`；
- `tests/unit/test_expected_schema.py`；
- `tests/unit/test_column_validator.py`；
- `tests/unit/test_oracle_validator.py`；
- `tests/unit/test_recovery_metrics.py`；
- `tests/regression/test_phase1_benchmark_001.py`。

覆盖实施说明要求的 N1–N18，并增加 Delay、Change Type、Block Time、Resolved Flight、Passenger Outcome、Recovery Action、容量边界以及 Gate/Seat 非验证边界测试。

## 10. Benchmark 结果

```text
Scenario semantic validation: PASS
Recovery Columns structural/semantic validation: PASS
Expected structural/semantic validation: PASS
Aircraft/Crew coverage: PASS
Airport capacity: PASS
Maintenance/terminal: PASS
Passenger itinerary continuity: PASS
Metrics recomputation: PASS
```

程序重算指标：

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

## 11. 最终验证

```text
python -m pytest -q                 → 71 passed
python -m compileall -q backend tests → PASS
git diff --check                    → PASS
```

测试仅输出既有 Starlette/httpx 依赖弃用警告，不影响验收结果。

## 12. 文档更新

更新了 README、开发计划、Benchmark 说明、复现记录与假设登记。JSON Schema 路径统一为：

```text
schemas/recovery_columns_v1.schema.json
schemas/recovery_expected_v1.schema.json
```

文档现统一表述：Phase 1 已证明当前数据、候选列和人工 Oracle 的程序化语义一致性，但未证明 AIR 恢复目标的数学全局最优性。

## 13. 未实施内容与下一步

本次未修改前端和 `/api/solve`，未实现 Solver、Incidence Matrix、SRM/ARM/CRM/PRM、Benders、Column Generation、Turn Time、Crew Duty Limits、Passenger MCT、Seat Inventory 或 Gate Occupancy。

下一阶段为 `Phase 2.0 Incidence Matrix Builder`。应先独立构建并测试 Flight Option 与 Aircraft String、Crew Pairing、Passenger Itinerary、Maintenance 的 Incidence Matrix，再进入 Fixed-Column 四模型。
