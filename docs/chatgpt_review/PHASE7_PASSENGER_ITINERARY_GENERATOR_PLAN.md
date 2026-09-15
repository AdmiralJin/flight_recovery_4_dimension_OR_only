# Phase 7 — Passenger Itinerary Generator 实施计划

## 1. 阶段定位

Phase 6 已完成并合入 `main`。当前系统已经具备：

- Scenario / Recovery Columns 数据契约与语义校验；
- Fixed-column SRM / ARM / CRM / PRM；
- Full Integrated Fixed-column Oracle；
- Recovery Scope fixed-point closure；
- Phase 5 Aircraft String Generator；
- Phase 6 Crew Pairing Generator；
- 独立 legality validator、toy brute-force Oracle、benchmark regression 与 Integrated Oracle audit。

Phase 7 的唯一核心目标是：

> **从现有 Flight Options 自动、确定性地生成 Passenger Itineraries，并在小规模实例上证明生成结果完整、合法、可复算，随后接入现有 PRM 与 Integrated Oracle。**

Phase 7 是显式候选生成阶段，不是 Passenger Pricing、Column Generation 或 Benders。

---

## 2. Phase 7 完成后的目标链路

```text
Scenario
+
Existing Flight Options
+
Passenger Groups
+
Passenger Itinerary Generation Config
+
RecoveryScope | None
        ↓
Passenger-local Flight Network
        ↓
Explicit Itinerary Enumeration
        ↓
Independent Itinerary Legality Validator
        ↓
Generated Passenger Itineraries
        ↓
Rebuild Recovery Scope
        ↓
PRM / Integrated Oracle
        ↓
Independent diagnostics / regression
```

本阶段不得生成新的 Flight Option。

---

## 3. 开始前必须完成的基线检查

Codex 开始 Phase 7 前先检查当前 `main`，不得直接假设仓库状态。

### 3.1 Phase 6 基线

至少确认以下内容存在并正常导出：

```text
backend/core/crew_network.py
backend/core/pairing_generator.py
backend/config/pairing_generation.py
tests/unit/test_crew_network.py
tests/unit/test_pairing_generator.py
```

并确认 `backend/core/__init__.py` 已导出 Phase 6 公共接口。

### 3.2 全量回归

先运行当前完整测试：

```bash
pytest -q
```

要求：

```text
0 failed
0 errors
```

若 Phase 7 开始前已有失败，先记录并判断是否为既有问题，不得把既有失败混入 Phase 7 修改。

### 3.3 文档状态同步

当前 README / 总计划中的 Phase 状态可能仍停留在 Phase 5/6 前。Phase 7 完成时统一更新：

```text
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

不要在开发中途反复改状态。

---

# 4. Phase 7 边界

## 4.1 本阶段必须实现

1. Passenger itinerary generation 配置契约；
2. Passenger-local flight network；
3. 显式 transported itinerary 枚举；
4. 每个 Passenger Group 的 explicit UNSERVED candidate；
5. Minimum Connection Time；
6. O-D continuity；
7. 时间连续性；
8. Recovery Horizon；
9. 最大 flight-leg 数限制；
10. 禁止重复 Flight Option；
11. 禁止同一 base flight 在同一 itinerary 中重复；
12. 独立 legality validator；
13. deterministic semantic key；
14. deterministic itinerary ID；
15. tiny-case brute-force Oracle；
16. Scope-aware generation；
17. benchmark 人工 itinerary semantic coverage；
18. 生成列回灌 PRM；
19. 生成列回灌 Integrated Oracle；
20. 独立 diagnostics / objective audit；
21. 测试、文档和 Codex report。

## 4.2 明确不做

Phase 7 禁止引入：

```text
Passenger Pricing
Reduced Cost
Dual Variables
Column Generation
Benders
新的 Flight Option 自动生成
真实航司 MCT 表
舱位等级
票价舱
旅客拆分
超售
联程保护优先级
联盟/他航改签
酒店/餐食/补偿
真实地面交通网络
复杂旅客偏好
UI Solve 流程
```

这些全部后移。

---

# 5. 论文与实现边界

Passenger Itinerary Generation 并非当前 AIR 复现中已有完整可直接照搬的生成算法，因此必须明确标记：

```text
Implementation Assumption / Extension
```

必须更新：

```text
assumptions.md
reproduction_notes.md
```

说明：

- Phase 7 generator 是工程扩展；
- MCT profile 是测试/实现假设，不是南航真实业务规则；
- 最大联程段数是组合规模控制参数；
- Seat Capacity 仍由 PRM / Integrated Oracle 处理；
- Phase 7 generator 只判断单条 itinerary 的局部时空合法性；
- 多 Passenger Group 之间的容量竞争属于全局优化问题。

不得把测试 MCT、测试容量或生成规则描述为真实航空公司生产规则。

---

# 6. 数据契约原则

## 6.1 优先复用现有 Schema

优先复用：

```text
backend/schemas/columns.py
```

现有：

```python
PassengerItinerary
PassengerSegment
PassengerItineraryStatus
PassengerSegmentType
```

已经能够表达：

```text
TRANSPORTED
UNSERVED
FLIGHT
SURFACE
final_destination
arrival_time
arrival_delay_minutes
```

**除非实现过程中证明现有 Schema 无法表达 Phase 7 最小需求，否则不得修改 Recovery Columns schema_version。**

本阶段第一版自动生成器只要求：

```text
FLIGHT segments
+
UNSERVED
```

现有 `SURFACE` 保留 Schema 能力，但不作为 Phase 7 第一版自动生成内容。

---

# 7. 新增配置契约

建议新增：

```text
backend/config/itinerary_generation.py
```

公共模型：

```python
PassengerItineraryGenerationConfig
ItineraryGenerationSource
PassengerItineraryGenerationConfigError
load_passenger_itinerary_generation_config(...)
```

建议字段：

```text
schema_version: "1.0.0"
profile_id: str

default_mct_minutes: int >= 0
max_flight_legs: int >= 1

allow_unserved: bool
allow_surface: bool

source:
    implementation_assumption
    test_fixture

notes: tuple[str, ...]
```

第一版 test profile：

```text
allow_unserved = true
allow_surface = false
```

`default_mct_minutes` 必须由版本化配置提供，禁止散落硬编码。

建议测试配置：

```text
data/config/phase7_test_itinerary_generation_v1.json
```

示意：

```json
{
  "schema_version": "1.0.0",
  "profile_id": "phase7_test_itinerary_generation_v1",
  "default_mct_minutes": 30,
  "max_flight_legs": 3,
  "allow_unserved": true,
  "allow_surface": false,
  "source": "test_fixture",
  "notes": [
    "Engineering-only Phase 7 profile.",
    "MCT and leg limits are implementation assumptions, not calibrated airline rules."
  ]
}
```

具体测试数值可根据 toy case 调整，但必须写入配置文件并保持版本化。

配置对象必须：

- immutable / frozen；
- `extra="forbid"`；
- 严格类型；
- 拒绝重复 JSON key；
- deterministic load；
- 非法 profile 明确抛出专用异常。

同时更新：

```text
backend/config/__init__.py
```

导出 Phase 7 公共配置接口。

顺便确认 Phase 6 pairing-generation 配置接口是否已完整导出；如未导出，可在同一小型兼容性修改中补齐，但不得改变 Phase 6 行为。

---

# 8. Passenger-local Flight Network

建议新增：

```text
backend/core/passenger_network.py
```

## 8.1 网络对象

建议：

```python
@dataclass(frozen=True)
class PassengerFlightNetwork:
    pax_group_id: str
    min_connection_minutes: int
    option_ids: tuple[str, ...]
    start_option_ids: tuple[str, ...]
    terminal_option_ids: tuple[str, ...]
    successor_option_ids: Mapping[str, tuple[str, ...]]
    rejected_option_reasons: Mapping[str, tuple[str, ...]]
    rejected_edge_counts: Mapping[str, int]
```

网络必须：

- passenger-group local；
- deterministic；
- 基于 existing Flight Options；
- 只包含 revenue `OPERATE` options；
- 不包含 CANCEL；
- 不包含 FERRY；
- 第一版不自动加入 SURFACE arc。

---

# 9. Flight Option 对 Passenger 的局部资格

建议公共接口：

```python
validate_flight_option_for_passenger(
    scenario,
    option,
    passenger,
    config,
) -> PassengerLegEligibility
```

至少检查：

## 9.1 operation type

只允许：

```text
FlightOperationType.OPERATE
```

明确拒绝：

```text
CANCEL
FERRY
```

建议 violation/reason：

```text
not_revenue_operate_option
```

## 9.2 Route / Airport

要求：

- `origin` / `destination` 非空；
- airport 存在；
- Flight Option 自身已满足基础 schema/semantic validity。

## 9.3 时间

要求：

```text
dep_time < arr_time
```

并且 Flight Option 位于：

```text
scenario.recovery_window
```

建议 reason：

```text
outside_recovery_horizon
invalid_time_order
```

## 9.4 Passenger departure boundary

不得生成明显早于 Passenger 可开始旅行时间的第一段。

第一版建议：

```text
first flight dep_time >= passenger.original_departure
```

如果项目需要允许旅客提前改签，则必须另行形成版本化规则；Phase 7 默认不静默允许。

## 9.5 Capacity

**这里不得检查 seat capacity。**

原因：

```text
单条 itinerary 是否在时空上合法
≠
多个 passenger groups 同时选择 itinerary 后是否超容量
```

Seat Capacity 继续由：

```text
PRM-C03
INTEGRATED-L05
```

统一处理。

---

# 10. Network Edge 规则

对于两个 revenue flight options：

```text
left -> right
```

只有全部满足才建立 successor edge：

## 10.1 Station continuity

```text
left.destination == right.origin
```

否则：

```text
station_mismatch
```

## 10.2 MCT

要求：

```text
left.arr_time + MCT <= right.dep_time
```

否则：

```text
mct_violation
```

MCT 第一版采用：

```text
config.default_mct_minutes
```

不要在 Phase 7 中构造机场/航站楼/国际国内分类 MCT 表。

## 10.3 时间单调

严格防止：

```text
time overlap
time reversal
```

## 10.4 同一 base flight

若：

```text
left.base_flight_id == right.base_flight_id
```

不得连接。

原因：同一原始航班的多个 recovery options 不应在同一路径内重复使用。

reason：

```text
same_base_flight
```

---

# 11. Start / Terminal 节点

对于 Passenger Group `g`：

## Start candidate

满足：

```text
option.origin == passenger.origin
option.dep_time >= passenger.original_departure
```

## Terminal candidate

满足：

```text
option.destination == passenger.destination
```

注意：

- 不要求 terminal flight 的到达时间早于 scheduled arrival；
- 晚到通过 `arrival_delay_minutes` 计成本；
- 若早到，Passenger delay 仍按现有语义：

```text
max(0, actual_arrival - scheduled_arrival)
```

---

# 12. Itinerary Generator

建议新增：

```text
backend/core/itinerary_generator.py
```

建议核心公共接口：

```python
generate_passenger_itineraries(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
    config: PassengerItineraryGenerationConfig,
) -> tuple[PassengerItinerary, ...]
```

以及：

```python
generate_passenger_itineraries_with_metrics(...)
    -> ItineraryGenerationResult
```

---

# 13. 显式枚举算法

采用 deterministic DFS / DAG path enumeration。

对于每个 Passenger Group：

```text
Source
  ↓
Start Flight Options
  ↓
Successor Flight Options
  ↓
Destination
```

路径达到 passenger.destination 时生成 transported itinerary。

DFS state 至少维护：

```text
path option IDs
used option IDs
used base flight IDs
flight leg count
```

不得依赖 Python 非稳定集合顺序产生输出。

所有候选在最终输出前必须按 deterministic semantic key 排序。

---

# 14. 路径终止与剪枝

## 14.1 到达目的地

一旦当前 flight 到达：

```text
passenger.destination
```

即可 emit 当前 path。

第一版建议到达最终目的地后不继续搜索。

## 14.2 最大 flight legs

要求：

```text
len(path) <= config.max_flight_legs
```

超过立即剪枝。

这是显式枚举的组合规模保护，不是论文原始业务约束。

## 14.3 Duplicate option

禁止：

```text
same flight_option_id twice
```

reason：

```text
duplicate_flight_option
```

## 14.4 Duplicate base flight

禁止同一：

```text
base_flight_id
```

通过两个不同 option 重复进入同一路径。

reason：

```text
duplicate_base_flight
```

---

# 15. UNSERVED Candidate

每个 Passenger Group 必须有显式：

```text
UNSERVED
```

candidate，前提：

```text
config.allow_unserved == true
```

UNSERVED 必须：

```text
segments = []
final_destination = None
arrival_time = None
arrival_delay_minutes = None
```

不得伪造 arrival data。

即使存在 transported itinerary，也仍保留 UNSERVED，以维持 PRM / Integrated Oracle 在严重扰动下的可行性。

---

# 16. PassengerItinerary 构造

对于 transported path：

```text
FO1 -> FO2 -> ... -> FOn
```

生成：

```python
PassengerItinerary(
    itinerary_id=...,
    pax_group_id=...,
    status=TRANSPORTED,
    segments=[FLIGHT, ...],
    final_destination=passenger.destination,
    arrival_time=last_option.arr_time,
    arrival_delay_minutes=max(
        0,
        minutes_between(
            passenger.scheduled_arrival,
            last_option.arr_time,
        ),
    ),
    cost_components={},
    notes=...
)
```

Flight `PassengerSegment` 优先只写：

```text
segment_type = FLIGHT
flight_option_id = ...
origin = None
destination = None
dep_time = None
arr_time = None
```

与现有 schema / resolver 语义保持一致，由 Flight Option 解析真实 route/time。

---

# 17. Semantic Key

必须新增公开函数：

```python
itinerary_semantic_key(
    itinerary: PassengerItinerary,
) -> tuple[...]
```

建议语义：

### TRANSPORTED

```text
(
    pax_group_id,
    "transported",
    (
        ("flight", FO1),
        ("flight", FO2),
        ...
    )
)
```

### UNSERVED

```text
(
    pax_group_id,
    "unserved",
    ()
)
```

不得使用 `itinerary_id` 做 semantic equality。

用途：

- 去重；
- manual-vs-generated coverage；
- deterministic regression；
- brute-force Oracle equality。

---

# 18. Deterministic ID

参考 Phase 5 的 hash ID 方式。

建议：

```text
GEN_PI_<SAFE_PAX_GROUP>_<SHA256-prefix>
```

hash payload 必须由 semantic content 构造，例如：

```text
pax_group_id
status
segment type
flight_option_id sequence
```

同一输入无论原始 Flight Options 顺序如何，输出 ID 和顺序必须完全一致。

不得使用：

```text
list index
enumeration order
Python hash()
random UUID
timestamp
```

作为候选身份。

---

# 19. Independent Legality Validator

必须实现：

```python
validate_generated_passenger_itinerary(
    scenario,
    flight_options,
    passenger,
    candidate,
    config,
) -> ItineraryLegalityResult
```

**Validator 不得复用 generator DFS 的“路径已合法”结论。**

必须从 candidate 本身重新检查。

至少检查：

```text
passenger ownership
status shape
unknown flight option
not revenue operate option
origin mismatch
destination mismatch
station discontinuity
time overlap
MCT violation
recovery horizon violation
duplicate flight option
duplicate base flight
max flight legs exceeded
arrival time mismatch
arrival delay mismatch
UNSERVED shape
surface disabled
```

结果：

```python
@dataclass(frozen=True)
class ItineraryLegalityResult:
    valid: bool
    violations: tuple[str, ...]
```

Generator 每次 emit candidate 后必须再次调用 validator。

若 generator 产生非法 itinerary：

```text
raise PassengerItineraryGenerationError
```

不得静默过滤隐藏 bug。

---

# 20. Scope-aware Generation

接口必须接受：

```text
RecoveryScope | None
```

遵循 Phase 5/6 的既有语义。

## 20.1 scope is None

对全部 Passenger Groups 显式生成。

## 20.2 passenger group in scope

显式生成其全部 Phase 7 合法 itinerary。

## 20.3 passenger group out of scope

只保留唯一 original itinerary。

Original itinerary 必须基于业务语义解析，不能依赖 ID 命名。

建议复用或抽取当前：

```text
resolve_original_candidates(...)
```

中的 passenger original semantic resolution。

若原计划 itinerary 无法唯一解析或按当前 Phase 7 legality 已非法：

```text
raise PassengerItineraryGenerationError
```

不要偷偷改成 UNSERVED。

---

# 21. Candidate Universe 改变后的 Scope 生命周期

Passenger itineraries 生成后，旧 Scope 不再视为 canonical。

正确流程：

```text
Scenario
+
Existing Flight Options
+
Generated Aircraft Strings
+
Generated Crew Pairings
+
Generated Passenger Itineraries
        ↓
New RecoveryColumns
        ↓
build_recovery_scope(...)
        ↓
Integrated Oracle
```

不得：

```text
生成新 passenger itineraries
+
继续直接使用生成前旧 scope
```

除非仅在 generator 内把旧 scope 作为“哪些 passenger owners 需要展开”的输入。

生成结果写回完整 `RecoveryColumns` 后，必须 rebuild canonical scope。

---

# 22. 与现有 RecoveryColumns 的拼装

建议提供清晰 helper，而不是在测试中重复手工 copy。

输入：

```text
old RecoveryColumns
generated passenger itineraries
```

输出：

```text
new RecoveryColumns
```

仅替换：

```text
passenger_itineraries
```

保持：

```text
schema_version
scenario_id
time_unit
flight_options
aircraft_strings
crew_pairings
```

不变。

如果仓库已有统一 replacement helper，则复用现有 helper，不重复造工具。

---

# 23. Passenger Capacity 边界

Phase 7 generator 不以 seat capacity 剪枝。

例如一个 Flight Option：

```text
capacity = 10
```

某 Passenger Group：

```text
count = 15
```

只要路线/时间合法，该 itinerary 仍可被 generator 生成。

最终：

```text
PRM-C03
INTEGRATED-L05
```

负责使该 itinerary 在优化组合中不可选择或受容量约束。

必须新增测试证明该边界，避免以后把“单列合法性”和“全局容量可行性”混在一起。

---

# 24. Toy Oracle Case

新增专用测试案例：

```text
toy_case_009_passenger_itinerary_generator
```

建议文件：

```text
data/examples/toy_case_009_passenger_itinerary_generator.json
data/columns/toy_case_009_passenger_itinerary_generator_columns.json
```

若仓库 toy fixture 主要由 `conftest.py` 构造，则保持现有项目风格，不强制新增 JSON；但必须有明确、独立的 Phase 7 toy case。

---

# 25. toy_case_009 必须覆盖的情形

构造一个很小的 Passenger network，例如：

```text
A -> B -> D
A -> C -> D
A ------> D
```

必须显式设计：

1. 合法直达；
2. 合法一次中转；
3. 刚好满足 MCT；
4. 比 MCT 少 1 分钟；
5. station 不连续；
6. time overlap；
7. recovery horizon 外；
8. 同一 base flight 的两个不同 option；
9. 路径超过 `max_flight_legs`；
10. cancel option；
11. ferry option；
12. duplicate option；
13. early arrival，delay 应为 0；
14. delayed arrival，delay 精确复算；
15. 无任何 transported path 的 passenger；
16. UNSERVED；
17. scope 内 passenger；
18. scope 外 passenger original-only。

toy case 要控制 eligible option 数量，使 brute-force Oracle 可运行。

---

# 26. Brute-force Oracle

必须实现：

```python
brute_force_legal_passenger_itineraries(
    scenario,
    flight_options,
    passenger,
    config,
    *,
    max_options: int = ...
) -> tuple[PassengerItinerary, ...]
```

Oracle 不得调用 smart DFS。

建议使用：

```text
ordered permutations
+
independent legality validator
```

枚举长度：

```text
1 .. max_flight_legs
```

并额外加入：

```text
UNSERVED
```

若 eligible options 超过 `max_options`：

```text
raise PassengerItineraryGenerationError
```

避免测试意外爆炸。

---

# 27. Phase 7 最关键 Oracle 验收

在 `toy_case_009` 上：

```text
semantic_keys(smart_generator)
==
semantic_keys(brute_force_oracle)
```

必须集合完全一致。

不仅比较数量。

同时比较：

```text
TRANSPORTED keys
UNSERVED key
arrival_time
arrival_delay_minutes
```

必要时对 candidate payload 做 deterministic snapshot。

---

# 28. Unit Tests

建议新增：

```text
tests/unit/test_passenger_network.py
tests/unit/test_itinerary_generator.py
```

## `test_passenger_network.py`

至少覆盖：

```text
revenue OPERATE accepted
CANCEL rejected
FERRY rejected
start node rule
terminal node rule
station continuity
MCT exact boundary accepted
MCT - 1 rejected
same base flight rejected
outside horizon rejected
network deterministic under reversed input
rejection metrics deterministic
```

## `test_itinerary_generator.py`

至少覆盖：

```text
config version/frozen/duplicate key rejection
deterministic output
semantic uniqueness
original itinerary retained
UNSERVED emitted
max flight legs
duplicate option rejection
duplicate base flight rejection
origin mismatch
destination mismatch
station discontinuity
MCT violation
arrival mismatch
arrival delay mismatch
surface disabled
scope original-only behavior
capacity not used as generator-local pruning
```

---

# 29. Oracle Tests

建议新增：

```text
tests/oracle/test_phase7_itinerary_generator_oracle.py
```

或遵循仓库当前 oracle test 命名规范。

必须验证：

```text
smart enumeration == brute-force enumeration
```

同时增加至少一个故意破坏 case，证明 Oracle 测试不是“两个实现共同漏错”。

---

# 30. Phase 1 Benchmark Regression

使用：

```text
phase1_benchmark_001
```

执行：

```text
existing Flight Options
+
generated Aircraft Strings
+
generated Crew Pairings
+
generated Passenger Itineraries
```

## 30.1 Manual itinerary coverage

当前人工 passenger itineraries 必须按 semantic key 检查。

目标：

```text
manual semantic keys ⊆ generated semantic keys
```

如果第一版 generator 明确不支持现有人工 SURFACE itinerary，则：

1. 先确认 benchmark 是否实际存在 SURFACE；
2. 若存在，不能直接忽略；
3. 必须在报告中解释；
4. 要么实现最小可核验 SURFACE 规则；
5. 要么将该人工候选明确排除在 Phase 7 coverage contract 外，并证明不影响当前 Oracle benchmark。

不得用 ID 比较覆盖率。

---

# 31. Benchmark Objective 解释规则

不要硬编码要求：

```text
generated objective == 18080
```

正确规则是：

```text
OBJ_generated <= OBJ_previous_fixed_candidate_universe
```

原因：自动 itinerary generator 可能发现人工 17 条 itinerary 未包含的合法低成本路径。

## 31.1 如果 objective 不变

记录：

```text
old objective
new objective
difference = 0
```

并说明：

```text
当前人工 passenger candidates 已覆盖当前 optimum 所需路径。
```

## 31.2 如果 objective 下降

这不自动判为失败。

必须输出：

```text
old objective
new objective
objective improvement
newly selected passenger itinerary
affected passenger group
flight option sequence
arrival delay change
passenger cost change
capacity/linking consequences
```

然后检查：

```text
all local audits PASS
all linking audits PASS
objective recomputation PASS
```

若全部通过，则说明旧人工 candidate universe 不完备。

## 31.3 如果 objective 上升

默认视为错误或候选覆盖缺失。

优先检查：

```text
manual semantic itinerary missing
original itinerary missing
scope lifecycle错误
MCT rule与既有benchmark不兼容
generation pruning过强
capacity profile未覆盖新引用option
```

在解释清楚前 Phase 7 不得验收。

---

# 32. PRM Regression

生成 passenger itineraries 后，至少执行：

```text
build_fixed_column_prm
solve_fixed_column_prm
recompute_prm_diagnostics
```

验证：

```text
each passenger group exactly one itinerary
schedule consistency
seat capacity
itinerary feasibility
passenger delay cost
unserved cost
```

Generated itineraries 不得绕过现有 PRM contract。

---

# 33. Integrated Oracle Regression

构造更新后的：

```text
RecoveryColumns
```

并重新：

```text
build_recovery_scope(...)
solve_integrated_fixed_column_oracle(...)
recompute_integrated_diagnostics(...)
```

必须检查：

```text
SRM local constraints
ARM local constraints
CRM local constraints
PRM local constraints
Schedule-Aircraft linking
Schedule-Crew linking
Deadhead-Schedule linking
Passenger-Schedule linking
Seat-Schedule linking
Scope-fix constraints
Canonical owner costs
Total objective recomputation
```

不得仅检查：

```text
solver status = OPTIMAL
```

---

# 34. Passenger Capacity Profile 兼容

Generated itinerary 可能引用以前人工 itinerary 未引用的 Flight Options。

Integrated Oracle 当前要求：

```text
所有 passenger-referenced operated options
必须存在 capacity_profile.seat_capacity_by_option_id
```

因此 Phase 7 benchmark integration 时必须检查 capacity profile 是否覆盖所有 generated itinerary flight options。

处理原则：

- 不得给缺失 option 静默设无限容量；
- 不得在 generator 内删除这些 itinerary 来绕过 capacity profile；
- 测试 profile 可显式补齐；
- 所有补齐值继续标记为 test/residual capacity；
- 不得解释为 aircraft physical capacity。

---

# 35. Scope Regression

Passenger candidate universe 改变后，必须重新验证：

```text
build_recovery_scope(...)
validate_recovery_scope(...)
scope_metrics(...)
```

至少记录：

```text
total passenger groups
scoped passenger groups
total passenger itineraries
free passenger itineraries
fixed passenger itineraries
total binary candidates
free binary candidates
iteration count
```

若 benchmark scope 因新 itinerary 增大：

```text
可以接受
```

前提是 fixed-point closure 能解释传播原因。

不得为了维持旧 scope 大小而删除合法 itinerary。

---

# 36. Metrics

`ItineraryGenerationResult.metrics` 至少包括：

```text
passenger_group_count
scoped_passenger_group_count
flight_option_count

network_node_count
network_edge_count

generated_itinerary_count
generated_transported_count
generated_unserved_count

generated_itinerary_count_by_group

rejected_candidate_count_by_reason
rejected_edge_count_by_reason

manual_key_count              # benchmark helper可提供
manual_key_covered_count      # benchmark helper可提供

generation_runtime_seconds
generation_mode
```

`generation_mode` 固定清晰标记，例如：

```text
explicit_full_enumeration_without_pricing
```

不得出现容易误导为 Column Generation 的名称。

---

# 37. Determinism 要求

以下操作不得改变结果：

```text
reverse flight_options input order
rebuild dict/set insertion order
repeat execution
```

比较：

```text
model_dump(mode="json")
```

应完全一致，包括：

```text
candidate order
itinerary IDs
segments
metrics 中确定性部分
```

runtime 除外。

---

# 38. 错误处理

新增：

```python
class PassengerItineraryGenerationError(ValueError):
    ...
```

必须用于：

```text
duplicate option IDs
unknown scope passenger
no candidate for required passenger
illegal original itinerary
generator emitted illegal itinerary
semantic duplicate
brute-force input too large
invalid generation assumptions
```

错误消息必须包含：

```text
passenger group ID
相关 option/path
violation reason
```

便于 Codex report 与人工定位。

---

# 39. Public API

Phase 7 完成后，建议 `backend/core/__init__.py` 导出：

```text
PassengerFlightNetwork
PassengerLegEligibility

ItineraryGenerationResult
ItineraryLegalityResult
PassengerItineraryGenerationError

build_passenger_flight_network
validate_flight_option_for_passenger

generate_passenger_itineraries
generate_passenger_itineraries_with_metrics
validate_generated_passenger_itinerary
brute_force_legal_passenger_itineraries
itinerary_semantic_key
```

`backend/config/__init__.py` 导出：

```text
PassengerItineraryGenerationConfig
PassengerItineraryGenerationConfigError
ItineraryGenerationSource
load_passenger_itinerary_generation_config
```

公共 API 必须有稳定命名，不要让测试依赖私有 `_...` 函数。

---

# 40. 与 Phase 5 / Phase 6 的一致性

实现风格尽量保持：

```text
Phase 5:
Flight Network
→ Aircraft String Generator
→ Independent Validator
→ Brute-force Oracle

Phase 6:
Crew Network
→ Crew Pairing Generator
→ Independent Validator
→ Brute-force Oracle

Phase 7:
Passenger Network
→ Passenger Itinerary Generator
→ Independent Validator
→ Brute-force Oracle
```

不要在 Phase 7 引入新的架构范式。

优先复用：

```text
immutable config
deterministic ordering
semantic key
hash-based stable ID
scope original-only handling
with_metrics result
independent validator
tiny brute-force oracle
benchmark regression
```

---

# 41. 不要过度复用 Aircraft/Crew 的错误部分

Passenger 与 Aircraft/Crew 不同：

```text
Aircraft String:
必须满足 aircraft start/end station

Crew Pairing:
必须满足 crew start/end station、qualification、duty rules

Passenger Itinerary:
从 passenger origin 到 passenger destination
```

Passenger 不应继承：

```text
aircraft equipment constraint
crew qualification
crew duty duration
aircraft maintenance
terminal aircraft station
deadhead semantics
```

只复用工程模式，不复制业务规则。

---

# 42. Surface Segment 第一版处理

Schema 已支持：

```text
PassengerSegmentType.SURFACE
```

但 Phase 7 第一版建议：

```text
allow_surface = false
```

原因：

Surface 需要额外定义：

```text
可用 O-D
departure time
arrival time
minimum transfer
cost
capacity
业务来源
```

当前仓库没有成熟的数据来源。

因此 validator 遇到自动生成 candidate 中的 SURFACE：

```text
surface_disabled
```

后续若增加 Surface，单独形成新 profile / 新阶段扩展，不在本阶段顺手硬编码。

---

# 43. Original Itinerary 语义

Passenger Scenario 当前保存：

```text
original_itinerary: list[flight_id]
```

Generated itinerary 使用：

```text
flight_option_id
```

因此 original semantic path 应通过：

```text
base flight
→ unique original Flight Option
```

解析。

禁止假定：

```text
FO_<flight>_ORIG
```

这种 ID 文本模式。

必须使用业务字段：

```text
base_flight_id
operation_type
change_types / schedule semantics
```

解析唯一 original option。

---

# 44. Early Arrival 规则

当前 passenger delay 语义为：

```text
max(0, actual_arrival - scheduled_arrival)
```

Phase 7 必须保持一致。

因此：

```text
actual_arrival < scheduled_arrival
```

时：

```text
arrival_delay_minutes = 0
```

不要产生负 delay。

---

# 45. Passenger Group 不拆分

当前 PRM 使用每组一个 binary itinerary selection。

Phase 7 不改变这一点。

即：

```text
一个 PassengerCommodity
→ 一个完整 candidate itinerary
```

不生成：

```text
同一 group 分成两个 itinerary
```

如果未来需要 split passenger flow，应单独修改 PRM 数学模型，不能在 generator 内先行实现。

---

# 46. 推荐文件修改清单

预计新增：

```text
backend/config/itinerary_generation.py

backend/core/passenger_network.py
backend/core/itinerary_generator.py

data/config/phase7_test_itinerary_generation_v1.json

tests/unit/test_passenger_network.py
tests/unit/test_itinerary_generator.py
tests/oracle/test_phase7_itinerary_generator_oracle.py
tests/regression/test_phase7_itinerary_generator_benchmark.py
```

toy case 文件按当前 fixture 风格决定。

预计修改：

```text
backend/config/__init__.py
backend/core/__init__.py

tests/conftest.py                  # 如 toy fixture 集中定义

assumptions.md
reproduction_notes.md
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

必要时：

```text
data/config/... passenger capacity test profile
```

仅用于显式补齐 generated itineraries 引用 Flight Options 的 test/residual capacity。

原则上不要修改：

```text
backend/core/prm.py
backend/core/integrated_oracle.py
backend/schemas/columns.py
```

除非测试证明存在真正的兼容性缺陷。

若必须修改这些稳定核心文件，Codex report 中单独说明：

```text
为什么必须改
行为是否变化
现有 Oracle 是否仍一致
新增了哪些回归保护
```

---

# 47. 实施顺序

严格按以下顺序执行。

## Step 1 — Baseline

```text
检查 Phase 6 merge
运行全测试
记录 baseline
```

## Step 2 — Config

实现：

```text
itinerary_generation.py
test profile
config tests
```

## Step 3 — Passenger Network

实现：

```text
Flight Option eligibility
start nodes
terminal nodes
successor edges
MCT
determinism
network tests
```

## Step 4 — Generator

实现：

```text
DFS
max legs
duplicate prevention
TRANSPORTED
UNSERVED
semantic key
stable ID
metrics
```

## Step 5 — Independent Validator

实现完整 candidate 复验。

## Step 6 — toy_case_009

构造最小但覆盖边界的 passenger network。

## Step 7 — Brute-force Oracle

实现 permutations Oracle。

## Step 8 — Smart vs Brute Force

要求 semantic set 完全一致。

## Step 9 — Scope-aware Behavior

验证：

```text
in-scope full generation
out-of-scope original-only
```

## Step 10 — Phase 1 Benchmark

生成 benchmark passenger itineraries，检查 manual semantic coverage。

## Step 11 — Rebuild Scope

使用新完整 RecoveryColumns 重建 canonical scope。

## Step 12 — PRM Regression

运行 PRM 与 independent diagnostics。

## Step 13 — Integrated Oracle Regression

运行完整 x/y/z/w Oracle 与所有 audits。

## Step 14 — Full Test Suite

```bash
pytest -q
```

## Step 15 — Documentation

更新 assumptions、reproduction notes、README、总开发计划。

## Step 16 — Codex Report

生成 Phase 7 完成报告。

---

# 48. Phase 7 验收标准

必须全部满足。

## A. Config

- [ ] Phase 7 config versioned；
- [ ] immutable；
- [ ] duplicate JSON keys rejected；
- [ ] MCT 不硬编码在算法；
- [ ] max legs 可配置；
- [ ] source 标记明确。

## B. Network

- [ ] 仅 revenue OPERATE；
- [ ] CANCEL/FERRY 排除；
- [ ] O-D / time 合法；
- [ ] MCT；
- [ ] same-base-flight arc 排除；
- [ ] deterministic。

## C. Generator

- [ ] 每组至少一个 candidate；
- [ ] UNSERVED 显式存在；
- [ ] transported candidate 合法；
- [ ] 无 duplicate semantic keys；
- [ ] IDs deterministic；
- [ ] max-flight-legs 生效；
- [ ] output deterministic。

## D. Validator

- [ ] 独立于 DFS；
- [ ] 能识别所有核心非法情况；
- [ ] generator emitted candidate 全部再次通过 validator。

## E. Oracle

- [ ] toy_case_009 smart semantic set = brute-force semantic set；
- [ ] 至少有 negative/oracle-break test。

## F. Scope

- [ ] scope=None 全生成；
- [ ] scoped passenger 全生成；
- [ ] out-of-scope passenger original-only；
- [ ] 新 candidate universe 后 rebuild canonical scope；
- [ ] scope validation PASS。

## G. Benchmark

- [ ] manual passenger semantic keys 被覆盖，或任何例外有明确、可验证说明；
- [ ] original itinerary 每组均存在；
- [ ] PRM regression PASS；
- [ ] Integrated Oracle local audits PASS；
- [ ] linking audits PASS；
- [ ] objective independent recomputation PASS。

## H. Objective

- [ ] `OBJ_generated <= OBJ_previous_candidate_universe`；
- [ ] 若相等，记录一致性；
- [ ] 若下降，解释新增合法 itinerary 与成本变化；
- [ ] 若上升，不得验收，直到解释并修复。

## I. Tests

- [ ] Phase 7 unit tests PASS；
- [ ] Phase 7 oracle tests PASS；
- [ ] Phase 7 benchmark regression PASS；
- [ ] full `pytest -q` PASS；
- [ ] 0 failed；
- [ ] 0 errors。

---

# 49. Definition of Done

只有当以下链条全部成立，Phase 7 才允许标记 Completed：

```text
Versioned Config
        ↓
Passenger-local Network
        ↓
Deterministic Explicit Generator
        ↓
Independent Legality Validator
        ↓
toy Smart == Brute-force Oracle
        ↓
Manual Semantic Coverage
        ↓
Generated RecoveryColumns
        ↓
Rebuilt Recovery Scope
        ↓
PRM PASS
        ↓
Integrated Oracle PASS
        ↓
Independent Objective Audit PASS
        ↓
Full Test Suite PASS
```

禁止仅因为：

```text
能生成 itinerary
```

或：

```text
solver = OPTIMAL
```

就结束 Phase 7。

---

# 50. Phase 7 完成报告

在：

```text
docs/codex_reports/
```

新增：

```text
YYYYMMDD_HHMMSS_phase7_passenger_itinerary_generator_report.md
```

报告必须包括：

```text
1. Baseline / Phase 6 status
2. Modified Files
3. Implemented Features
4. Config Contract
5. Passenger Network Rules
6. Itinerary Generation Rules
7. Known Implementation Assumptions
8. Known Limitations
9. toy_case_009 Design
10. Smart-vs-Brute-force Oracle Result
11. Manual Benchmark Semantic Coverage
12. Generated Itinerary Counts
13. Scope Metrics Before/After
14. PRM Regression Result
15. Integrated Oracle Result
16. Objective Before/After
17. Independent Audit Result
18. Full Test Result
19. Deferred Work
20. Next Recommended Step
```

必须给具体数字，不写：

```text
tests passed
coverage good
oracle consistent
```

这种无数据表述。

至少报告：

```text
generated itinerary count
count by passenger group
transported count
unserved count
manual semantic key coverage
network nodes/edges
rejected reasons
old objective
new objective
scope free/total binary candidates
pytest passed/failed/skipped
```

---

# 51. Phase 7 完成后的下一步

Phase 7 完成后，下一阶段应为：

```text
Phase 8 — Fixed-Column Benders
```

进入 Phase 8 前必须保持：

```text
Flight Options                 fixed/existing
Aircraft Strings               explicitly generated
Crew Pairings                  explicitly generated
Passenger Itineraries          explicitly generated
Integrated Fixed-column Oracle retained as Ground Truth
```

Phase 8 第一验收目标：

```text
OBJ_Benders
==
OBJ_Integrated_Oracle
```

在 Fixed-column Benders 与 Integrated Oracle 对齐之前，不进入 Column Generation。

---

# 52. 最终开发原则

Phase 7 只解决：

> **Passenger candidate universe 是否可以自动、完整、确定性、可审计地构造。**

不解决：

> **如何在大规模问题中高效动态地产生 passenger columns。**

因此本阶段始终坚持：

```text
先 explicit enumeration
→ 再 independent validation
→ 再 brute-force oracle
→ 再 benchmark regression
→ 再 Integrated Oracle
→ 后续才做 decomposition / pricing / column generation
```

任何为了性能而提前牺牲可核验性的修改，均不属于 Phase 7。
