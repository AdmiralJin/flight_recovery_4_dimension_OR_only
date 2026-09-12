# Phase 2.5 Fixed-Column PRM Report

## 1. Modified Files

实现代码：

- `backend/config/passenger_capacity.py`
- `backend/config/costs.py`
- `backend/config/__init__.py`
- `backend/core/passenger_incidence.py`
- `backend/core/prm.py`
- `backend/core/__init__.py`

数据与 Oracle：

- `data/capacities/phase2_test_seat_capacity_v1.json`
- `data/capacities/toy_case_003_capacity.json`
- `data/examples/toy_case_003.json`
- `data/columns/toy_case_003_columns.json`

测试：

- `tests/conftest.py`
- `tests/unit/test_passenger_capacity.py`
- `tests/unit/test_passenger_incidence.py`
- `tests/unit/test_prm.py`
- `tests/regression/test_phase2_prm_benchmark_001.py`

文档：

- `README.md`
- `assumptions.md`
- `reproduction_notes.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`
- `docs/RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md`

未修改 HTML / Frontend，未实现 Integrated Oracle、Benders 或 Column Generation。

## 2. Paper (3.16)-(3.18) Mapping

编码前重新打开并渲染核对了仓库论文第 12 个 PDF page（论文页码 12）及前页变量定义。

| Paper | 原文变量/系数 | Fixed-column mapping | 当前字段 |
|---|---|---|---|
| (3.16) | `z_{i,gamma}` passenger count、`s_i` unassigned count、delay 与 unassign cost | selected transported group 的 passenger-minute cost + selected UNSERVED group cost | `PassengerCommodity.count`、`arrival_delay_minutes`、两项 PRM cost coefficients |
| (3.17) | itinerary-flight incidence、equipment/string capacity 减 planned nondisrupted passengers | selected itinerary 按 group count 消耗外生 option residual capacity | `PassengerRecoveryIncidence`、`seat_capacity_by_option_id` |
| (3.18) | 每个 passenger 的 itinerary/unassigned flow conservation | 每个不可拆分 group 恰选一条 transported 或 explicit UNSERVED itinerary | binary `w[itinerary_id]`、`pax_group_id` |

论文的 `z_{i,gamma}` 与 `s_i` 是非负整数人数流。当前 binary 整组选择是显式 implementation mapping，不声称与论文变量域完全相同。

## 3. PRM Input Contract

`PassengerRecoveryRequest` 是 frozen dataclass，包含：

- `scenario_id`
- ordered unique `required_operated_option_ids`
- `capacity_profile_id`

它只接受已知 revenue OPERATE options，同一 base flight 不得出现多个 option。SRM 顺序流程复用 `extract_required_operated_option_ids`；PRM 不自行解析 SRM diagnostics，不调用 ARM，也不重新选择 schedule。

## 4. Seat Capacity Contract

新增 frozen `PassengerCapacityProfile`：

- schema version `1.0.0`
- source 仅允许 `implementation_assumption` / `test_fixture`
- units 固定为 `seats`
- capacity mapping 只读
- capacity 必须为 strict non-negative integer
- duplicate JSON keys、unknown option、CANCEL、FERRY、scenario mismatch 均 fail fast
- 每个 required operated option 必须有显式 capacity，禁止 infinite default

## 5. Capacity Provenance / Assumptions

Capacity 表示可供当前模型内 Passenger Commodities 使用的 test residual inventory，对应 (3.17) 右端 `equipment capacity - planned nondisrupted passengers` 的工程映射。它不是 `Flight.min_seats`、真实 aircraft/equipment capacity、airline inventory 或 paper value。

## 6. Passenger Itinerary Schema Reuse / Changes

复用现有 `PassengerItinerary` / `PassengerSegment` v1.0.0；未修改 Recovery Columns schema。Transported、UNSERVED、FLIGHT 与 SURFACE 已能表达本阶段需要的候选列。

## 7. Constraint Mapping Table

| ID | 类型 | 含义 | 来源 |
|---|---|---|---|
| PRM-C01-PASSENGER-GROUP-SELECTION | paper mapping | 每个 group 恰选一条 itinerary | (3.18) + A-049 |
| PRM-C02-SCHEDULE-CONSISTENCY | implementation guard | non-selected option itinerary 固定为 0 | A-047 |
| PRM-C03-SEAT-CAPACITY | paper mapping | passenger-count seat load 不超过 residual capacity | (3.17) + A-048/A-051 |
| PRM-C04-ITINERARY-FEASIBILITY | fixed-column validation | ownership、OD、time、arrival/delay、UNSERVED shape | A-050 |

未将四个工程 ID 错称为四条 paper constraints。

## 8. Passenger Group Splitting Policy

Phase 2.5 不支持 splitting。一个 group 整体选择一条 itinerary 或 unserved。独立审计另行验证每个 `w` 为 0/1，不能只依赖 group sum 排除 fractional split。

## 9. Cost Ownership

PRM 只收取：

- `passenger_delay_per_pax_minute`
- `unserved_passenger`

不重复收取 SRM flight delay，不新增 reaccommodation、surface 或 missed-connection penalty。

## 10. Passenger Cost Function

新增 pure `passenger_itinerary_cost` 与 frozen `PassengerItineraryCostBreakdown`：

- transported: `count * arrival_delay_minutes * delay coefficient`
- unserved: `count * unserved coefficient`
- 不信任 Columns `cost_components` 为真源
- 输出 weighted delay、delay cost、unserved passengers/cost 与 total

## 11. New Assumptions

新增 A-047 至 A-055：external schedule boundary、residual capacity provenance、group indivisibility、fixed itinerary feasibility、passenger-count load、PRM cost、reaccommodation metric、single-model boundary、SRM proxy / future ARM capacity coupling。

## 12. Unit / Negative / Infeasible Tests

新增 33 项 Phase 2.5 tests，覆盖：

- immutable/versioned capacity contract 与 duplicate JSON key；
- negative/bool/fraction/string capacity；
- unknown/CANCEL/FERRY capacity reference；
- deterministic immutable passenger incidence；
- unknown option 与 mismatched indices；
- passenger-minute / passenger-count cost；
- exactly-one、schedule consistency、active threshold capacity；
- alternative、UNSERVED、SURFACE；
- no-unserved infeasible；
- missing capacity、scenario/profile mismatch；
- malformed/duplicate/unknown fixed columns fail fast；
- audit rejects missing values and fractional group splitting。

## 13. toy_case_003 Result

Capacity: direct 12 seats，connection 10 seats；Passenger groups: 12 + 10。

- T3_P1 -> direct
- T3_P2 -> alternative connection
- direct/connection slacks all 0
- weighted delay = 300 pax-min
- objective = 3000 abstract cost units
- reaccommodated = 10
- unserved = 0

这是可手算且 seat constraint 真正 active 的独立 Oracle。

## 14. SRM -> PRM Handoff Result

SRM optimum objective 70 的 schedule 通过 canonical handoff 进入 PRM：

- PRM status: OPTIMAL
- PRM objective: 45000
- weighted passenger delay: 1500 pax-min
- reaccommodated passengers: 15
- unserved passengers: 12（P6 explicit UNSERVED）
- capacity violations: 0

P6 unserved 源于当前 schedule-compatible fixed itinerary shortage；未修改 SRM 或 cost 掩盖该结果。

## 15. Manual Reference -> PRM Result

Phase 1 Manual schedule 得到：

- status: OPTIMAL
- objective: 18000
- selected itinerary mapping 与 Manual Reference 完全一致
- weighted passenger delay: 1800 pax-min
- reaccommodated passengers: 15
- unserved passengers: 0

## 16. Seat Capacity Audit

Manual path 的 active zero-slack options 包括 F1、F4、F7、F8、F9、F10_D20、F11_D10、F12；全部 load 按 passenger count 复算，capacity violations = 0。SURFACE 与 UNSERVED 不消耗 flight seats。

## 17. Reaccommodation / Unserved Audit

Reaccommodation 定义为 transported itinerary 改变 base-flight sequence 或引入 SURFACE；仅 ORIG -> delayed option 且 base-flight sequence 不变不计改签。UNSERVED 不重复计 reaccommodated。

## 18. Passenger Delay Audit

Manual path：P1 `30*50=1500`、P5 `18*10=180`、P6 `12*10=120`，合计 1800 pax-min；系数 10，delay cost = 18000。

## 19. Objective Audit

每条 selected itinerary 重新调用 pure cost function，汇总 passenger delay 与 unserved 两个 owner components，并与 solver objective 使用 `1e-6` tolerance 比较。所有约束也独立复算；不以 `OPTIMAL` status 代替业务审计。

## 20. Full Pytest Result

- Command: `python -m pytest -o addopts='' -q`
- Total: 244
- Passed: 244
- Failed: 0
- Skipped: 0
- Warning: 1 existing FastAPI/Starlette deprecation warning

## 21. Gurobi Result

- Gurobi version: 13.0.3
- PRM integration executed: yes
- Manual benchmark: executed
- SRM -> PRM regression: executed
- toy_case_003 regression: executed
- skipped: 0

## 22. Known Limitations

- passenger groups are indivisible；
- capacity is external test residual inventory, not ARM-derived truth；
- no cabin/fare-class inventory；
- time continuity does not implement real MCT；
- no dynamic itinerary generation；
- reaccommodation is a diagnostic, not a standalone cost；
- SRM market-seat proxy remains provisional until Phase 3 review。

## 23. Acceptance Checklist

- [x] Paper (3.16)-(3.18) re-opened, rendered and mapped
- [x] Existing fixed Passenger Itineraries reused
- [x] Canonical operated-option handoff reused
- [x] CANCEL / FERRY prohibited
- [x] Independent test seat-capacity contract
- [x] `Flight.min_seats` not used as capacity
- [x] Passenger-count capacity load
- [x] Exactly-one group selection
- [x] Schedule-incompatible itinerary prohibited
- [x] Active threshold / alternative / unserved / surface tests
- [x] PRM-only costs and independent objective audit
- [x] Feasible and shortage regressions
- [x] toy_case_003
- [x] Full pytest pass, zero skipped, actual Gurobi execution
- [x] assumptions / README / reproduction plan / notes / schema docs synchronized
- [x] HTML unchanged
- [x] No Integrated Oracle / Benders / Column Generation

## 24. Next Recommended Step

在进入实现前先做一次 Phase 2 总审查，冻结 cross-model coupling、ARM-derived capacity source、SRM market-seat proxy 去留、四模型 cost scale/tie-breaking 与 fixed-column coverage gaps；随后开始 Phase 3 Full Integrated Fixed-Column Oracle。

**Phase 2.5 PASS**
