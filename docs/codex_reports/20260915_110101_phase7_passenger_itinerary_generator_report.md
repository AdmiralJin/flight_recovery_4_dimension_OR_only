# Phase 7 Passenger Itinerary Generator 实施报告

生成时间：2026-09-15 11:01:01（Asia/Shanghai）  
实施分支：`feature/phase-7`

## 1. Baseline / Phase 6 Status

Phase 7 从本地 `main` 的 Phase 6 收尾提交 `ce770e9` 创建。开始前确认 Phase 5 Aircraft String、Phase 6 Crew Pairing、Scope、PRM 与 Integrated Oracle 公共接口完整，基线全量测试为：

```text
329 passed
0 failed
0 skipped
1 existing StarletteDeprecationWarning
```

## 2. Modified Files

核心实现：

```text
backend/config/itinerary_generation.py
backend/config/__init__.py
backend/core/passenger_network.py
backend/core/itinerary_generator.py
backend/core/__init__.py
```

数据与配置：

```text
data/config/phase7_test_itinerary_generation_v1.json
data/examples/toy_case_009_passenger_itinerary_generator.json
data/columns/toy_case_009_passenger_itinerary_generator_columns.json
```

测试：

```text
tests/conftest.py
tests/unit/test_passenger_network.py
tests/unit/test_itinerary_generator.py
tests/regression/test_phase7_itinerary_generator_oracle.py
tests/regression/test_phase7_itinerary_generator_benchmark.py
```

文档：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/chatgpt_review/PHASE7_PASSENGER_ITINERARY_GENERATOR_PLAN.md
docs/codex_reports/20260915_110101_phase7_passenger_itinerary_generator_report.md
```

稳定的 `backend/core/prm.py`、`backend/core/integrated_oracle.py` 和 `backend/schemas/columns.py` 无需修改。

## 3. Implemented Features

- 版本化、immutable Passenger Itinerary generation config；
- deterministic passenger-local revenue-flight DAG；
- TRANSPORTED FLIGHT-only DFS 路径枚举；
- 每组显式 UNSERVED candidate；
- public semantic key 与 SHA-256 稳定 ID；
- independent itinerary legality validator；
- tiny ordered-permutation brute-force Oracle；
- Scope-aware generation 与 out-of-scope original-only；
- `replace_passenger_itineraries(...)` 安全替换 helper；
- generation/network/rejection/runtime metrics；
- PRM、Full Integrated、Scope-limited Integrated 回归。

## 4. Config Contract

公共接口：

```text
PassengerItineraryGenerationConfig
PassengerItineraryGenerationConfigError
ItineraryGenerationSource
load_passenger_itinerary_generation_config(...)
```

Benchmark profile：

```text
schema_version = 1.0.0
profile_id = phase7_test_itinerary_generation_v1
default_mct_minutes = 0
max_flight_legs = 3
allow_unserved = true
allow_surface = false
source = test_fixture
```

Config 使用 strict integer、`extra="forbid"`、`frozen=true`，拒绝重复 JSON key。MCT 与最大航段数没有散落为算法 magic number。

## 5. Passenger Network Rules

`PassengerFlightNetwork` 仅包含 existing revenue `OPERATE` options。CANCEL/FERRY 使用 `not_revenue_operate_option` 拒绝；route/time/airport、Recovery Horizon 由单 leg eligibility 检查。

Start node 要求 option origin 等于 passenger origin，且 departure 不早于 passenger original departure；terminal node 要求 option destination 等于 passenger destination。

Successor arc 检查：

```text
different base flight
station continuity
no time overlap/reversal
left.arrival + versioned MCT <= right.departure
```

Seat Capacity 不进入 passenger-local network。

## 6. Itinerary Generation Rules

Smart Generator 使用 passenger-local DAG + deterministic DFS，并维护 path、used option IDs、used base Flight IDs 与 flight-leg count。到达 passenger destination 后立即输出且不继续扩展。

TRANSPORTED candidate 只生成 FLIGHT segments，真实 route/time 由 referenced Flight Option 解析。Arrival delay 使用：

```text
max(0, actual arrival - passenger scheduled arrival)
```

每个 scoped Passenger Group 始终生成显式 UNSERVED；out-of-scope group 只保留语义 original itinerary。所有输出按 semantic key 排序，ID 只由 passenger/status/option sequence 派生，与输入 option 顺序无关。

## 7. Known Implementation Assumptions

新增 assumptions：

- A-072：Passenger Generator 是论文外的工程扩展；
- A-073：Phase 7 MCT 与 maximum-leg 测试 profile；
- A-074：单 itinerary legality 与全局 seat capacity 分离；
- A-075：Original、UNSERVED、Surface 与 Scope 语义。

Benchmark 的零分钟 MCT 用于兼容已冻结的零间隔人工 itinerary；toy case 独立使用 30 分钟验证 MCT。完整性严格表述为：

```text
full explicit enumeration within the Phase 7 v1 generation profile
```

## 8. Known Limitations

- 只消费已有 Flight Options，不生成新 option；
- 不生成 SURFACE segment；
- 不实现真实机场/航站楼/国内国际 MCT；
- 不处理舱位、票价舱、联盟/他航、超售、旅客偏好或酒店补偿；
- Passenger Group 保持不可拆分 binary choice；
- Generator 不用 seat capacity 做局部剪枝；
- 不实现 Passenger Pricing、Reduced Cost、Column Generation 或 Benders。

## 9. toy_case_009 Design

`toy_case_009_passenger_itinerary_generator` 使用 A/B/C/D/E 网络，包含：

```text
A → D direct
A → B → D, exact 30-minute MCT
A → B → D, MCT minus 1 minute
A → C → D
same-base reroute option
CANCEL
FERRY
```

测试同时通过 candidate mutation 覆盖 station mismatch、time overlap、outside horizon、duplicate option/base Flight、max legs、arrival mismatch、surface disabled、stranded passenger 与 Scope original-only。

## 10. Smart-vs-Brute-force Oracle Result

Toy profile：30 分钟 MCT、最多 2 legs、UNSERVED enabled。

```text
Passenger groups = 2
Flight Options = 9
Network nodes = 18
Network edges = 19
Generated itineraries = 7
  transported = 5
  unserved = 2
  S9_P1 = 4
  S9_P2 = 3

S9_P1 Smart semantic set = Brute-force semantic set = 4
```

除 semantic keys 外，arrival time 与 arrival delay payload 也完全一致。故意把合法 candidate 的 delay 改为 999 后，独立 validator 正确报告 `arrival_delay_mismatch`。

## 11. Manual Benchmark Semantic Coverage

比较 key：

```text
pax_group_id
status
ordered (segment_type, flight_option_id)
```

结果：

```text
manual semantic keys = 17
covered manual keys = 17
coverage = 17 / 17
missing = 0
```

8 个 Passenger Groups 的 original itinerary 均被解析为 legal 并存在于生成集合。Benchmark 不含需要 Phase 7 v1 自动生成的 SURFACE manual candidate。

## 12. Generated Itinerary Counts

```text
Passenger groups = 8
Scoped passenger groups = 8
Flight Options = 22
Network nodes = 152
Network edges = 345
Generated itineraries = 55
Transported = 47
Unserved = 8

P1 = 10
P2 = 11
P3 = 8
P4 = 8
P5 = 7
P6 = 5
P7 = 4
P8 = 2
```

拒绝统计：

```text
candidate/max_flight_legs_exceeded = 12
candidate/not_revenue_operate_option = 40
edge/same_base_flight = 96
edge/station_mismatch = 1488
edge/time_overlap = 312
```

一次代表性本地 generation runtime 约 0.004 秒，只作当前小规模观察。

## 13. Scope Metrics Before/After

Phase 7 前使用 77 generated Strings、374 generated Pairings、17 manual Itineraries 构造 canonical Scope；生成 55 Itineraries 后再次 rebuild 并通过 `validate_recovery_scope(...)`。

```text
                         before   after
Flights scoped/total     12/12    12/12
Aircraft scoped/total      4/4      4/4
Crew scoped/total           5/5      5/5
Passenger groups scoped     8/8      8/8
Passenger candidates       17       55
Free passenger candidates  17       55
Total binary candidates   489      527
Free binary candidates    489      527
Fixed binary candidates     0        0
Scope iterations             2        2
```

主 benchmark 的共享耦合图继续合法闭包为 Full Scope；没有通过删除 itinerary 人工维持旧 Scope 大小。

## 14. PRM Regression Result

在 Phase 1 Manual Reference schedule 和 test/residual capacity profile 上回灌 55 条 generated Itineraries：

```text
Solver = Gurobi 13.0.3
Status = OPTIMAL
Objective = 18000
Capacity violations = 0
All PRM constraints satisfied = true
```

每个 Passenger Group 恰选一条 itinerary，schedule consistency、seat capacity、delay/unserved cost 和 independent objective recomputation 均通过。

## 15. Integrated Oracle Result

完整 candidate universe：

```text
21 schedule x candidates
77 generated Aircraft Strings
374 generated Crew Pairings
55 generated Passenger Itineraries
```

结果：

```text
Full Integrated status = OPTIMAL
Full Integrated objective = 18080
Scope-limited status = OPTIMAL
Scope-limited objective = 18080
```

## 16. Objective Before/After

```text
Previous Phase 6 Integrated objective = 18080
Phase 7 generated-universe objective = 18080
Difference = 0
```

自动生成的 passenger universe 没有遗漏人工 optimum 所需路径，也没有在当前 schedule/resource/capacity coupling 下产生更低的合法整体目标。当前人工 passenger candidates 已覆盖当前 optimum 所需路径。

## 17. Independent Audit Result

```text
Generated-column semantic validation = PASS
Canonical Scope validation = PASS
PRM local audit = PASS
PRM objective recomputation = PASS
Integrated local constraints = PASS
Integrated cross-model linking = PASS
Integrated seat/schedule linking = PASS
Integrated objective recomputation = PASS
Scope fix audit = PASS
```

不能仅以 Solver `OPTIMAL` 作为验收依据；上述独立检查均已在 regression 中断言。

## 18. Full Test Result

最终执行：

```text
pytest -q
python -m compileall -q backend
python -m black --check <7 Phase 7 Python files>
git diff --check
```

结果：

```text
353 passed
0 failed
0 skipped
24 Phase 7 tests added over 329-test baseline
compileall PASS
Black check PASS (7 files)
git diff --check PASS
1 existing StarletteDeprecationWarning
```

环境未安装 Ruff，因此未运行 Ruff。

## 19. Deferred Work

```text
Passenger Pricing / Reduced Cost
真实 MCT 与 Surface network
Cabin/fare-class inventory
Passenger splitting
Alliance/interline reaccommodation
Fixed-Column Benders
Column Generation
Benders + Column Generation
UI Solve workflow
```

## 20. Next Recommended Step

**Phase 7 PASS。**

下一阶段：

```text
Phase 8 — Fixed-Column Benders
```

第一验收目标：

```text
OBJ_Benders == OBJ_Integrated_Oracle
```

在 Fixed-column Benders 与 Integrated Oracle 对齐前，不进入 Column Generation。
