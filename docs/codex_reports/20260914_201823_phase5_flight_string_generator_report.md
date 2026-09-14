# Phase 5 Flight String Generator 实施报告

生成时间：2026-09-14 20:18:23（Asia/Shanghai）

## 1. Phase 4 Closeout

Phase 4 semantic original resolver 已加严，不再只比较主要业务航段序列：

- Aircraft original string 不允许夹带额外 FERRY / positioning leg；
- Crew original pairing 不允许夹带额外 DEADHEAD / ground / rest recovery segment；
- Passenger original itinerary 不允许夹带 surface 或其他 recovery-only segment；
- 0 个或多个语义匹配继续显式报错，不依赖候选 ID 命名猜测。

README 与 assumptions 中有关 Integrated Oracle、Solver 和前端 Solve 边界的过时表述已同步清理。Phase 4 至此正式关闭。

## 2. Modified Files

核心实现：

```text
backend/config/string_generation.py
backend/config/__init__.py
backend/core/flight_network.py
backend/core/string_generator.py
backend/core/scope.py
backend/core/__init__.py
```

配置与数据资产：

```text
data/config/phase5_test_string_generation_v1.json
data/examples/toy_case_007_string_generator.json
data/columns/toy_case_007_string_generator_columns.json
```

测试：

```text
tests/conftest.py
tests/unit/test_scope.py
tests/unit/test_flight_network.py
tests/unit/test_string_generator.py
tests/regression/test_phase5_string_generator_oracle.py
tests/regression/test_phase5_benchmark_001.py
```

文档：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
docs/chatgpt_review/PHASE4_CLOSEOUT_AND_PHASE5_FLIGHT_STRING_GENERATOR_PLAN.md
```

## 3. Generator Input / Output

输入合同：

```text
Scenario
existing Sequence[FlightOption]
RecoveryScope | None
FlightStringGenerationConfig
```

输出为现有 `backend.schemas.columns.AircraftString`，没有引入不兼容列 Schema。`generate_aircraft_strings` 返回确定性排序的 String tuple；`generate_aircraft_strings_with_metrics` 同时返回网络与生成诊断。

Phase 5 不自动创建 Flight Options。合法性与完整性只相对于调用方提供的 existing Flight Option universe 成立。

## 4. Flight Network

`backend/core/flight_network.py` 为每架 aircraft 构建确定性的 aircraft-local DAG：

```text
start node → eligible Flight Option nodes → terminal node
```

节点排序使用航班出发时间、到达时间和 option ID；连接边只在不同 base flight、站点连续且满足显式 Turn Time 时建立。网络统计包含 start/terminal nodes 及其边，并保存按原因分类的候选拒绝计数。

Airport capacity、gate capacity、passenger seat capacity 和 crew legality 没有被错误塞入单机网络，仍由相应 Integrated Model 约束负责。

## 5. Legality Rules

Flight Option eligibility 和完整 String validator 覆盖：

- Aircraft ownership 与 equipment compatibility；
- CANCEL exclusion；
- OPERATE / existing FERRY support；
- 已知机场、合法时间与 block time；
- start station、相邻 station continuity、required terminal station；
- 相邻 leg timing 与 Turn Time；
- revenue flight Max Delay 与 declared delay 一致性；
- Recovery Horizon；
- curfew 与最小 hard airport-local restriction tokens；
- duplicate option / duplicate base-flight exclusion；
- maintenance terminal proxy。

生成结果必须再次通过独立 pure legality validator，不能以“由 Generator 产生”替代验证。

## 6. Turn Time Contract

新增 immutable、版本化的 `FlightStringGenerationConfig`。测试 profile：

```text
profile_id = phase5_test_string_generation_v1
default_min_turn_minutes = 15
equipment_overrides.E1 = 0
source = test_fixture
```

E1 的 0 分钟 override 仅用于兼容 Phase 1 benchmark 已冻结的零间隔人工 Strings；它不是生产级业务标准。代码中没有 Turn Time magic number。

## 7. Maintenance / Terminal Semantics

当前 Schema 不具备 maintenance task、duration、due time 或 maintenance capacity。Phase 5 延续既有 validator 可证明的最小语义：

- `maintenance_required=false`：生成列标记 `maintenance_satisfied=true`；
- `maintenance_required=true`：required terminal 必须属于 `maintenance_stations`；
- 所有输出仍必须到达 `required_station_at_T_end`。

这是 terminal proxy，不声称真实维修任务已经排程和执行。

## 8. Smart Generator

Smart Generator 使用 Flight Network + DFS 进行剪枝后的显式全路径枚举。它：

- 从 aircraft 初始站点出发；
- 只沿合法 successor arc 扩展；
- 防止重复 option 与重复 base flight；
- 在满足 terminal / maintenance 时输出路径；
- 使用 `aircraft_id + ordered leg_option_ids` 的 SHA-256 派生稳定 String ID；
- 为合法原地等待生成显式零 leg idle String；
- deterministic 且无重复。

提供 Scope 时，只对 scoped aircraft 执行枚举；out-of-scope aircraft 只保留经语义解析和 legality validator 确认的 original String。`scope=None` 对全部 aircraft 全量生成。

## 9. Brute-force Oracle

新增小规模 exhaustive permutation Oracle：对每架 aircraft 的所有 option 排列长度 0..n 完整枚举，再使用同一个独立单 String legality predicate 过滤。

Brute-force Oracle 与 Smart Generator 不共享 path generation 算法，只共享应被验证的 legality contract；并设置最多 8 个 options 的保护边界，仅用于 toy correctness proof。

## 10. Toy Oracle Comparison

新增 `toy_case_007_string_generator`，覆盖合法原计划、Turn Time violation、FERRY、CANCEL、idle、多 aircraft ownership 与 terminal 条件。

结果：

```text
Aircraft count = 3
Flight Option count = 7
Network nodes = 24
Network edges = 22
Generated Strings = 6
  AC1 = 3
  AC2 = 1
  AC3 = 2

Smart legal key set = Brute-force legal key set
```

AC1 的三条合法路径为：idle、original revenue rotation、existing FERRY + terminal revenue leg。Turn Time 不足路径和 CANCEL 均被排除。

## 11. Benchmark Generated Strings

在 `phase1_benchmark_001` 的 22 个 existing Flight Options 上执行 full enumeration：

```text
Aircraft count = 4
Scoped Aircraft count = 4
Flight Option count = 22
Network nodes = 80
Network edges = 188
Generated Strings = 77
  AC1 = 10
  AC2 = 27
  AC3 = 13
  AC4 = 27
```

网络级拒绝计数：

```text
cancel_excluded = 16
same_base_flight = 48
station_mismatch = 840
turn_time_violation = 188
```

一次代表性本地执行的生成耗时约 0.006 秒；该数值仅用于规模观察，不作为性能承诺或稳定断言。

## 12. Manual Key-string Coverage

比较使用语义 key，而非候选 ID：

```text
aircraft_id
ordered leg_option_ids
start_station
end_station
maintenance_satisfied
```

Phase 1 benchmark 的 11 条人工 Aircraft Strings 全部在生成集合中找到语义等价列：

```text
manual key coverage = 11 / 11
missing = 0
```

## 13. Integrated Oracle Result

使用原 flight options、生成的 77 条 aircraft strings、原 crew pairings 和原 passenger itineraries 重建 Recovery Columns，并重新运行 Phase 3 Integrated Oracle：

```text
Solver = Gurobi
Status = OPTIMAL
Objective with manual Strings = 18080
Objective with generated Strings = 18080
Independent local/cross-model/objective audits = PASS
```

因此生成列没有遗漏当前 fixed-column optimum 所需关键 String，也没有产生使目标异常下降的非法列。

## 14. Tests

新增测试覆盖 Phase 4 resolver 负例、配置版本与不可变性、网络 eligibility/arc、curfew/capacity 边界、确定性、独立 legality validator、idle、maintenance、FERRY、Scope、去重、Smart-vs-Brute-force Oracle、benchmark key coverage 和 Integrated Oracle 回归。

最终全量回归结果：

```text
309 passed
0 failed
0 skipped
1 existing StarletteDeprecationWarning
```

## 15. New Assumptions

`assumptions.md` 新增：

- A-062：Aircraft Turn Time test profile；
- A-063：Airport-local restriction eligibility boundary；
- A-064：Maintenance terminal proxy；
- A-065：Explicit idle String；
- A-066：Existing-option full enumeration，不做 Pricing。

同时更新 A-060，明确 original candidates 不得夹带 recovery-only segments。

## 16. Known Limitations

- 不生成新的 delay、route-change、cancel 或 FERRY Flight Options；
- 不实现 tail-specific 生产 compatibility rules；
- 不实现真实 maintenance scheduling；
- hard weather restriction taxonomy 仅覆盖已登记的最小 tokens；
- Airport/gate/seat shared capacity 仍由 Integrated Model 处理；
- 不生成 Crew Pairings 或 Passenger Itineraries；
- 不读取 dual、不计算 reduced cost，不实现 Pricing、Column Generation 或 Benders；
- DFS 显式全量枚举用于当前小规模 correctness stage，不承诺大规模生产性能。

## 17. Acceptance Checklist

- [x] Phase 4 original resolver 加严且有负例测试；
- [x] 旧文档表述清理；
- [x] deterministic Flight Network；
- [x] existing-option Aircraft String Generator；
- [x] Station / timing / explicit Turn Time / Max Delay / Horizon；
- [x] airport-local restriction boundary；
- [x] maintenance / terminal / CANCEL / FERRY / original / idle；
- [x] Scope-aware generation；
- [x] 独立 legality validator；
- [x] Smart Generator 与 brute-force Oracle 对齐；
- [x] benchmark 11/11 人工 key coverage；
- [x] Generated Strings 重跑 Integrated Oracle，objective 保持 18080；
- [x] full pytest 0 failed、0 skipped；
- [x] 未进入 Pricing / CG / Benders。

## 18. Final Decision

**Phase 5 PASS。**

Phase 4 closeout 与 Phase 5 existing-option Flight String Generator 的全部验收门槛均已满足。下一建议阶段为：

```text
Phase 6 Crew Pairing Generator
```
