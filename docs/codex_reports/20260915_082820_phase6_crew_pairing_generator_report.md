# Phase 6 Crew Pairing Generator 实施报告

生成时间：2026-09-15 08:28:20（Asia/Shanghai）  
实施分支：`fature/phase-6`（仓库当前实际分支名）

## 1. Phase 5 Closeout

Phase 5 的 Aircraft String Generator 保持冻结，不修改其核心算法。本次正式补充候选宇宙与 Scope 的生命周期规则：任何 Flight Options、Aircraft Strings、Crew Pairings 或 Passenger Itineraries 发生变化后，必须针对新的 `RecoveryColumns` 重新运行 `build_recovery_scope(...)`，不得沿用旧 Scope。

README、assumptions、reproduction notes 和总复现计划中的阶段状态已同步：Phase 3 Integrated Oracle、Phase 4 Scope Limiting、Phase 5 Flight String Generator、Phase 6 Crew Pairing Generator 均已完成；前端 Solve API / recovered-result UI 仍未接入。

## 2. Modified Files

核心实现：

```text
backend/config/pairing_generation.py
backend/config/__init__.py
backend/core/crew_network.py
backend/core/pairing_generator.py
backend/core/__init__.py
```

配置与测试数据：

```text
data/config/phase6_test_crew_pairing_generation_v1.json
data/examples/toy_case_008_crew_pairing_generator.json
data/columns/toy_case_008_crew_pairing_generator_columns.json
```

测试：

```text
tests/conftest.py
tests/unit/test_crew_network.py
tests/unit/test_pairing_generator.py
tests/regression/test_phase6_pairing_generator_oracle.py
tests/regression/test_phase6_benchmark_001.py
```

文档：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/codex_reports/20260915_082820_phase6_crew_pairing_generator_report.md
```

## 3. Scope Rebuild Rule

正式流水线冻结为：

```text
manual columns
→ Phase 5 generated Aircraft Strings
→ rebuild Recovery Scope
→ Phase 6 generated Crew Pairings
→ rebuild Recovery Scope
→ Phase 7 / next Solver
```

主 benchmark 确实在 77 条生成 Strings 后构造 Phase 6 输入 Scope，并在 374 条 Pairings 生成后再次构造 Scope。两次闭包均包含 12 Flights、4 Aircraft、5 Crew、8 Passenger groups；第二次 Scope 包含全部 374 条新 Pairings。

## 4. Generator Input / Output

输入合同：

```text
Scenario
existing Sequence[FlightOption]
RecoveryScope | None
CrewPairingGenerationConfig
```

输出继续使用现有 `backend.schemas.columns.CrewPairing`，没有引入不兼容 Schema。`generate_crew_pairings(...)` 返回确定性 Pairing tuple；`generate_crew_pairings_with_metrics(...)` 额外返回 crew-local networks 与诊断指标。

Phase 6 只消费已有 Flight Options，不创建 delay、reroute、cancel、FERRY 或其他新 Flight Option。

## 5. Crew Network

`backend/core/crew_network.py` 为每个 Crew 构建确定性 DAG：

```text
crew start state
→ typed (OPERATE | DEADHEAD, Flight Option) legs
→ crew terminal state
```

Network eligibility/arc 检查 revenue option、已知 route/time、Recovery Horizon、OPERATE qualification、Station continuity、time overlap 与显式 Min Connection。Duty 总时长、重复 option/base flight 和 DEADHEAD 数量是 path-level 状态，由 DFS 剪枝和独立 validator 复核。

Airport capacity、Gate capacity、Passenger seat capacity 与 Aircraft String selection 没有塞入 crew-local network，继续由 Integrated Oracle 负责。

## 6. OPERATE / DEADHEAD Semantics

- OPERATE：Crew 执行航班，检查 `Crew.rating` 与 base Flight `original_equipment`；计入 Integrated operating coverage。
- DEADHEAD：Crew 作为旅客调位，不检查执飞机型资质；不计 operating coverage，但 Integrated `L03` 要求对应 schedule option 被选择。
- 两者都只能引用 revenue `OPERATE` Flight Option。CANCEL 和 FERRY option 不能作为 Crew flight segment。

现有 CRM/Integrated operating/deadhead incidence、coverage、no-leakage 和成本语义未被修改。

## 7. Qualification / Timing / Duty Rules

当前 Crew Schema 只支持单一 `rating`，因此 qualification 边界仅为：

```text
OPERATE base Flight.original_equipment == Crew.rating
```

版本化测试配置：

```text
profile_id = phase6_test_crew_pairing_generation_v1
default_min_connection_minutes = 0
max_duty_minutes = 480
max_deadhead_legs = 1
allow_deadhead = true
allow_idle = true
source = test_fixture
```

零分钟连接用于保留 benchmark 中已冻结的背靠背人工 Pairings；480 分钟与最多一个 DEADHEAD 均标记为 `IMPLEMENTATION ASSUMPTION`，不是 FAR/CCAR 或真实航司规则。

Phase 6 v1 每条 Pairing 恰含一个 duty，duration 为首 leg departure 至末 leg arrival。由于 Schema 缺少 duty history、reporting/sign-off、rest location 和跨日 roster 字段，本阶段不实现 multi-duty/overnight rest。

## 8. Smart Generator

Smart Generator 使用 crew-local network + DFS：

- 从 Crew 起始站扩展 OPERATE/DEADHEAD typed legs；
- 只沿时间和站点连续的 successor arc；
- path state 防止重复 option 与重复 base Flight；
- 剪除 duty-time 和 DEADHEAD-limit violation；
- 到达 required terminal 时输出候选；
- 使用 `crew_id + ordered(segment_type, flight_option_id)` 的 SHA-256 派生稳定 ID；
- deterministic、stable ordering、无语义重复。

生成完整性严格表述为 **full explicit enumeration within the Phase 6 v1 generation profile**。`scope=None` 在该 profile 内对全部 Crew 生成；提供 Scope 时只对 scoped Crew 枚举，out-of-scope Crew 只保留合法 original Pairing。

## 9. Independent Legality Validator

`validate_generated_crew_pairing(...)` 不信任 Generator 路径，独立复算：

```text
crew ownership
single-duty v1 boundary
known revenue Flight Options
OPERATE / DEADHEAD eligibility
station and time continuity
qualification
duplicate option / base Flight
min connection
duty duration
deadhead limit
recovery horizon
start / terminal station
idle legality
```

所有 Generator 输出在 emit 时再次经过该 pure validator；非法输出会显式抛出 `CrewPairingGenerationError`。

## 10. Brute-force Oracle

新增 tiny-case exhaustive oracle：

```text
all option permutations
× all OPERATE/DEADHEAD role assignments
→ independent full-pairing validator filter
```

Oracle 与 Smart Generator 只共享单 leg/full pairing legality contract，不共享 network/DFS enumeration algorithm。默认最多处理 6 个 eligible options，防止误用于大实例。

## 11. Toy Oracle Comparison

`toy_case_008_crew_pairing_generator` 覆盖 original、idle、DEADHEAD、qualification mismatch、CANCEL/FERRY exclusion、Min Connection 和重复 base Flight。

```text
Crew count = 2
Flight Option count = 6
Network nodes = 16
Network edges = 22
Generated Pairings = 8
  S8_C1 = 5
  S8_C2 = 3

S8_C1 Smart legal key set = Brute-force legal key set = 5
```

## 12. Benchmark Generated Pairings

在 `phase1_benchmark_001` 的 22 个 existing Flight Options 和 Phase 5 generated-String Scope 上运行：

```text
Crew count = 5
Scoped Crew count = 5
Flight Option count = 22
Crew-network nodes = 180
Crew-network edges = 788
Generated Pairings = 374
  C1 = 28
  C2 = 122
  C3 = 56
  C4 = 73
  C5 = 95
OPERATE leg incidences = 1094
DEADHEAD leg incidences = 288
```

代表性本地生成耗时约 0.03 秒，只作当前规模观察，不作为生产性能承诺。

未限制 DEADHEAD 数量时，同一显式 legality 边界会生成 1,187 条 Pairings，并因每个 DEADHEAD schedule-linking row 使当前 Gurobi size-limited license 报错 10010。因此 v1 测试 profile 显式限定最多一个 DEADHEAD；该限制可通过新配置版本替换，不是隐藏剪枝。

## 13. Manual Key-pairing Coverage

比较使用业务语义 key，而非 Pairing ID：

```text
crew_id
ordered (segment_type, flight_option_id)
start_station
end_station
```

结果：

```text
manual Pairings = 10
generated semantic Pairings = 374
manual key coverage = 10 / 10
missing = 0
```

## 14. Integrated Oracle Result

构造：existing Flight Options + 77 Phase 5 generated Aircraft Strings + 374 Phase 6 generated Crew Pairings + existing Passenger Itineraries；随后再次 rebuild Recovery Scope 并运行 Phase 3 Full Integrated Oracle。

```text
Solver = Gurobi 13.0.3
Status = OPTIMAL
Objective with manual Pairings = 18080
Full objective with generated Pairings = 18080
Scope-limited objective with generated Pairings = 18080
Local constraint audit = PASS
Cross-model linking audit = PASS
Scope fix audit = PASS
Objective audit = PASS
```

生成 Pairings 保留当前 fixed-column optimum，没有出现非法 objective 改善、变差或 infeasible。

## 15. Tests

新增覆盖：

```text
revenue option / CANCEL / FERRY eligibility
OPERATE qualification and DEADHEAD boundary
station mismatch / time overlap / min connection
duty-time / horizon / terminal / ownership
duplicate option / duplicate base Flight
deadhead limit and disabled deadhead
original / idle
scope-aware generation
deterministic ordering and deduplication
smart generator = brute-force oracle
manual key coverage and Integrated regression
```

最终全量结果：

```text
329 passed
0 failed
0 skipped
1 existing StarletteDeprecationWarning
```

附加检查：`python -m compileall -q backend` 通过；7 个新增 Python 文件通过 Black check；`git diff --check` 通过。环境未安装 Ruff，因此未运行 Ruff。

## 16. New Assumptions

`assumptions.md` 新增：

- A-067：Candidate Universe change 必须 rebuild Scope；
- A-068：Phase 6 connection/duty/deadhead 版本化测试 profile；
- A-069：现有 qualification 与 DEADHEAD 边界；
- A-070：single-duty 与 rest 未建模边界；
- A-071：original、idle、Scope 和 explicit-generation 语义。

## 17. Known Limitations

- 不生成新的 Flight Options；
- 不实现 multi-duty、overnight rest、Crew Rostering、reserve 或真实 FAR/CCAR duty rules；
- qualification 仅有单一 equipment rating，无 role/rank/position/fleet-family 数据库；
- 每个 Crew 仍是 aggregate single crew unit，不证明真实航班编制；
- DEADHEAD 不建模独立座位占用；
- v1 测试 profile 最多一个 DEADHEAD；
- DFS 是显式小规模 correctness stage，不承诺大规模生产性能；
- 不读取 dual、不计算 reduced cost、不实现 Pricing、Column Generation 或 Benders。

## 18. Acceptance Checklist

- [x] Phase 5 Scope 重算规则正式写入；
- [x] 阶段状态文档清理；
- [x] deterministic Crew Network；
- [x] existing-option Crew Pairing Generator；
- [x] Scope 限制生成范围；
- [x] Station / timing / Min Connection / Duty / Horizon / Terminal；
- [x] qualification 仅使用现有数据；
- [x] OPERATE / DEADHEAD 语义与 Integrated linking 一致；
- [x] DEADHEAD 不计 operating coverage；
- [x] original / idle 语义；
- [x] deterministic 且无重复；
- [x] independent legality validator；
- [x] Smart Generator 与 brute-force Oracle 对齐；
- [x] benchmark 人工 Pairings 10/10 覆盖；
- [x] generated Pairings 回灌 Integrated Oracle；
- [x] 生成后再次 rebuild Scope；
- [x] 新 Scope 下 Full 与 Scope-limited Integrated objective 相等；
- [x] objective 保持 18080；
- [x] full pytest 0 failed / 0 skipped；
- [x] Phase 3/4/5 regression 无回归；
- [x] 未进入 Pricing / CG / Benders。

## 19. Final Decision

**Phase 6 PASS。**

Phase 5 closeout 和 Phase 6 existing-option Crew Pairing Generator 的验收门槛均已满足。下一建议阶段：

```text
Phase 7 Passenger Itinerary Generator
```
