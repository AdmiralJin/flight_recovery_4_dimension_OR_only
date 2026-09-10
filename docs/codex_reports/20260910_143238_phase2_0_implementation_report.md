# Phase 2.0 Implementation Report

- 完成时间：2026-09-10 14:32:38 +08:00
- 基线 Commit：`94f4bdbd5175638b3f582e589340614cd95357f4`（`94f4bdb add: phase1B`）
- 工作范围：Phase 1 Contract Cleanup + Phase 2.0 Incidence / Index Builder
- 最终状态：**Phase 2.0 PASS**

## 1. 项目基线与范围

项目在本次工作前已完成 Phase 0、0.5 和 Phase 1，已有 Scenario、Recovery Columns、Manual Expected/Oracle、语义校验与指标复算闭环。本次严格按 `docs/chatgpt_review/PHASE2_IMPLEMENTATION_PLAN_AND_PHASE2_0_TASK.md` 执行，只完成合同收尾和 Phase 2.0；没有实现 Solver、成本合同、ModelSolveResult、SRM、ARM、CRM、PRM、Benders 或 Column Generation。

开始工作时工作树中已存在用户改动：`data/examples/PHASE1_BENCHMARK_001_DESIGN.md` 已删除，Phase 2 任务文档尚未跟踪。本次保留这些改动，没有回退或覆盖。

## 2. Modified Files

实现文件：

- `backend/core/__init__.py`
- `backend/core/indices.py`
- `backend/core/incidence.py`

合同与依赖：

- `schemas/recovery_columns_v1.schema.json`
- `schemas/recovery_expected_v1.schema.json`
- `requirements.txt`

测试：

- `tests/unit/test_json_schema_contract.py`
- `tests/unit/test_indices.py`
- `tests/unit/test_incidence.py`
- `tests/regression/test_phase2_incidence_benchmark_001.py`

文档清理：

- `README.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`
- `docs/benchmarks/PHASE1_BENCHMARK_001_DESIGN.md`

## 3. JSON Schema Contract Cleanup

两份 v1 JSON Schema 的顶层和全部结构化 nested object / `$defs` 已增加 `additionalProperties: false`。以下有意设计为自由 key-value map 的字段继续开放：

- `cost_components`
- selected-column maps
- `required_flight_option_by_flight`
- recovery action 的 `from` / `to`
- objective `components`

`known_equivalent_patterns` 的 item schema 已补全 `name`、`description`，并关闭未知字段。新增测试同时调用 Draft 2020-12 JSON Schema Validator 和 Pydantic，证明结构化未知字段会被两侧一致拒绝，同时证明自由 map 仍可扩展。`jsonschema>=4.19,<5.0` 已加入开发/验证依赖。

## 4. Index Structures

新增不可变 `OrderedIndex`：

- 保留输入 JSON 的显式顺序；
- 提供 `position_of(id)` 和 `id_at(position)` 双向查询；
- unknown ID 明确抛出 `KeyError`；
- duplicate ID fail fast；
- 支持空的可选集合；
- `position` 使用只读映射。

新增 `RecoveryIndices`，覆盖：

- flights；
- all / operate / cancel / ferry / revenue-operate flight options；
- aircraft / aircraft strings；
- crew / crew pairings；
- passenger groups / passenger itineraries；
- maintenance-required aircraft；
- capacity intervals。

容量区间使用不可变结构化 `CapacityIntervalKey(airport, start_time, end_time)`，不依赖可解析的人工拼接字符串。

## 5. Incidence Structures

新增不可变 `BinaryIncidence`：

- `contains(row_id, column_id)`；
- `columns_for_row(row_id)`；
- `rows_for_column(column_id)`；
- 双向只读关系；
- 查询结果按已声明 index 顺序稳定返回；
- duplicate edge、unknown row、unknown column 均 fail fast。

新增 `RecoveryIncidence` 与 `build_recovery_incidence(...)`，建立：

- base flight → options；
- aircraft → strings；
- crew → pairings；
- passenger group → itineraries；
- option → aircraft strings；
- option → operating crew pairings；
- option → deadhead crew pairings；
- option → passenger itineraries；
- maintenance aircraft → satisfying strings；
- departure capacity interval → movement options；
- arrival capacity interval → movement options。

Builder 接收已经通过 Phase 1 validators 的 Pydantic 对象，不复制完整业务校验，但会对 incidence 自身边界上的 unknown reference、cancel physical coverage、passenger ferry/cancel usage、duplicate edge 和不匹配的预建 indices 明确失败。

## 6. Operate / Deadhead / Ferry / Cancel Semantics

- Operate 与 Deadhead 分别进入 `option_to_operating_pairings` 和 `option_to_deadhead_pairings`，Deadhead 不产生 Operating Coverage。
- Cancel 属于 base-flight candidate choice，但不进入 Aircraft、Crew、Passenger 或 Airport Movement physical coverage。
- Ferry 没有 base flight，可由 Aircraft String 覆盖，并作为真实 movement 使用 departure/arrival capacity。
- Passenger flight segment 只能引用 `operation_type == operate` 的 revenue option，不能使用 Ferry 或 Cancel。
- 同一关系中的重复引用不会被 set 静默压缩，而是抛出 duplicate-edge 错误。

## 7. Capacity Boundary Implementation

Departure 和 Arrival incidence 均使用半开区间 `[start_time, end_time)`：

- `event_time == start_time`：included；
- `event_time == end_time`：excluded；
- Operate 与 Ferry：计入 movement capacity；
- Cancel：不计入 movement capacity。

**Gate incidence intentionally deferred.** 当前项目尚未冻结恢复后 gate occupancy 事件语义，因此本次没有发明 Gate Constraint。

## 8. Benchmark001 Checked Incidence Facts

正式 regression 在构建 incidence 前先运行 `validate_scenario(...)` 和 `validate_recovery_columns(...)`，并检查：

- F2 → `FO_F2_ORIG`, `FO_F2_D50`；Ferry 不属于任何 base-flight row。
- `AS_AC1_SWAP_F10` → `FO_F1_ORIG`, `FO_F2_D50`, `FO_F10_D20`。
- `AS_AC4_SWAP_F3_ORIG` → `FO_F3_ORIG`, `FO_F11_D10`, `FO_F12_ORIG`。
- `CP_C1_RECOVERY` operating → `FO_F1_ORIG`, `FO_F2_D50`, `FO_F10_D20`。
- `CP_C4_F3_ORIG_F11_D10` operating → `FO_F3_ORIG`, `FO_F11_D10`。
- benchmark deadhead incidence 全部为空。
- `PI_P4_REACCOM_F8` 只使用 `FO_F8_ORIG`。
- B `[09:30,10:30)` departure bucket 包含 `FO_F5_ORIG`、`FO_F8_ORIG`，排除恰在右边界 10:30 起飞的 `FO_F2_D50`。
- Maintenance row 包含 AC4，且 `A_MS[AC4, AS_AC4_SWAP_F3_ORIG] = 1`。

## 9. Tests Added

新增 31 个测试，覆盖：

- JSON Schema / Pydantic unknown-field 一致性和自由 map 例外；
- OrderedIndex 顺序、双向查询、unknown/duplicate/empty/immutability；
- BinaryIncidence 双向查询、确定顺序、unknown/duplicate/immutability；
- 全部 entity-choice 和 operational incidence；
- Operate / Deadhead 分离；
- Ferry、Cancel、Maintenance；
- departure / arrival capacity 与 `[start,end)`；
- unknown option、cancel-in-string、passenger-on-ferry、duplicate edge 等负例；
- 正式 benchmark001 regression。

## 10. Pytest Result

命令：

```text
python -m pytest
```

结果：

```text
102 passed, 1 warning
```

Phase 1 原有 71 个测试全部通过，无回归。唯一 warning 是现有 FastAPI/Starlette TestClient 对 `httpx` 的 deprecation warning，与本次 Phase 2.0 实现无关。

## 11. Documentation Cleanup

已从 README、总复现计划和正式 benchmark 设计文档删除已经失效的 `data/colums/` 历史提醒。正式 benchmark 文档位置保持为：

```text
docs/benchmarks/PHASE1_BENCHMARK_001_DESIGN.md
```

## 12. Known Limitations

- Gate incidence intentionally deferred。
- Builder 只转换人工提供且已验证的 fixed columns，不生成 Flight String、Crew Pairing 或 Passenger Itinerary。
- 未定义 seat-capacity contract；该工作属于后续 PRM 阶段。
- `RecoveryExpected` 继续只作为 Oracle / Reference Fixture；本次未实现真正 solver result contract。
- 未引入 NumPy / SciPy sparse matrix；当前以可审计的不可变关系结构为主。
- 未实现任何 Solver 或数学模型。

## 13. Acceptance

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
