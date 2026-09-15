# Phase 5 Closeout + Phase 6 Crew Pairing Generator Plan

> 用途：供 Codex 完成 Phase 5 极简收尾，并实施 Phase 6 Crew Pairing Generator。
> 原则：Phase 5 不再改核心算法；Phase 6 第一版只生成合法 Crew Pairings，不做 Pricing、Column Generation 或 Benders。

## 1. Phase 5 极简收尾

### 1.1 冻结 Scope 重算规则

正式写入 `assumptions.md` / `reproduction_notes.md`：

> 任何 Candidate Universe 发生变化后，都必须重新构建 Recovery Scope。

例如：

```text
manual columns
→ initial scope
→ Flight String Generator
→ new aircraft-string universe
→ rebuild scope
→ next generator / solver
```

禁止直接沿用旧 Scope。新生成的 Aircraft Strings、Crew Pairings、Passenger Itineraries 可能建立新的资源和航班依赖，使旧 Scope 不再闭合。

### 1.2 清理少量旧文档

删除或修正仍存在的过时表述，例如：

```text
Integrated Objective 尚未完成
后端 Solver 尚不存在
```

统一为当前状态：

```text
Phase 3 Integrated Oracle 已完成
Phase 4 Scope Limiting 已完成
Phase 5 Flight String Generator 已完成
前端 Solve API / Recovered UI 尚未接入
```

完成后 Phase 5 正式关闭。

## 2. Phase 6 目标

Phase 6 实现：

```text
Crew Pairing Generator
```

目标：

> 基于 Scenario、现有 Flight Options、Phase 5 生成后的 Candidate Universe 和最新 Recovery Scope，自动生成合法 Crew Pairings，替代当前人工编写的 Crew Pairings。

Phase 6 v1 只做：

```text
合法 Pairing 生成
+
独立 legality validation
+
小规模 brute-force oracle
+
Integrated Oracle 回归
```

不做：

```text
Crew Pairing Pricing
Reduced Cost
Column Generation
Benders
Crew Rostering
真实排班规则全集
```

## 3. 输入与输出

建议新增：

```text
backend/core/crew_network.py
backend/core/pairing_generator.py
```

输入至少包括：

```text
Scenario
Flight Options
Aircraft Strings / current column universe
RecoveryScope
CrewPairingGenerationConfig
```

输出：

```text
list[CrewPairing]
```

必须继续使用现有：

```text
backend.schemas.columns.CrewPairing
```

不得新建不兼容 Schema。

## 4. Phase 6 开始前重新构建 Scope

Phase 5 已改变 Aircraft String universe，因此 Phase 6 开始前必须：

```text
Scenario
+ current Flight Options
+ generated Aircraft Strings
+ existing Crew Pairings
+ existing Passenger Itineraries
→ rebuild Recovery Scope
```

Phase 6 Generator 使用这个最新 Scope。

Phase 6 生成新的 Crew Pairings 后，在进入 Phase 7 或下一次 Solver 前再次：

```text
rebuild Recovery Scope
```

## 5. Scope 使用原则

Scoped Crew：生成完整 candidate Crew Pairings。

Out-of-scope Crew：只保留 original Crew Pairing。

同时支持：

```text
scope=None
```

用于小规模 full-enumeration oracle。

## 6. Crew Network

建议 `crew_network.py` 构建确定性 crew-local network。

节点可表示：

```text
Crew start state
Flight Option / duty leg
Crew terminal state
```

允许的 leg 类型至少包括：

```text
OPERATE
DEADHEAD
```

边表示某 Crew 执行完一个 leg 后，可以合法衔接下一个 leg。

至少检查：

```text
station continuity
time continuity
crew qualification
recovery horizon
terminal/base requirement
```

不要把以下全局约束塞进 Crew Network：

```text
Airport capacity
Gate capacity
Passenger seat capacity
Aircraft-string selection
```

这些继续由 Integrated Oracle 处理。

## 7. OPERATE 与 DEADHEAD 语义

### OPERATE

Crew 作为执行机组。

必须满足：

```text
crew qualification
station continuity
timing
duty legality
```

并继续承担：

```text
operating coverage = selected Flight Option
```

### DEADHEAD

Crew 作为旅客调位。

必须满足：

```text
对应 Flight Option 可供 deadhead
时间与位置连续
```

在 Integrated Oracle 中继续满足：

```text
selected pairing deadhead option
→ corresponding x_o = 1
```

DEADHEAD 不能计入 operating coverage。

## 8. Crew Qualification

只使用 Scenario / Schema 中已有的 qualification 信息。

如果当前 crew 数据支持：

```text
aircraft type
equipment qualification
role / rank
```

则严格检查。

如果当前数据不支持某项真实业务规则，不得虚构；应在 `assumptions.md` 明确 Phase 6 v1 的 qualification boundary。

## 9. 时间与连接规则

任意相邻 Crew legs 至少要求：

```text
previous.destination == next.origin
```

以及：

```text
previous.arr_time + min_connection
<=
next.dep_time
```

如果当前项目还没有正式 Crew Connection / Sit Time，建议新增版本化配置：

```text
data/config/phase6_test_crew_pairing_generation_v1.json
```

至少包含：

```text
profile_id
default_min_connection_minutes
source
notes
```

禁止 Magic Number。

测试值必须标记为：

```text
IMPLEMENTATION ASSUMPTION
```

## 10. Duty Time / Rest

Phase 6 v1 只实现当前数据能够可靠支持的 duty legality。

如果 Schema 已具备：

```text
max_duty_minutes
min_rest_minutes
```

则正式使用。

如果没有，不得自行发明真实航司机组值。可在 test config 中加入最小工程参数，但必须版本化、有 source / notes，并写入 assumptions。

第一版优先保证：

```text
duty start
duty end
total duty duration
```

可计算并可审计。

若跨 duty / overnight rest 当前数据无法可靠表达：

```text
Phase 6 v1 不实现
```

## 11. Pairing 起点与终点

每个 Crew Pairing 必须有明确：

```text
start station
end station
```

起点应与 Crew 当前起始位置字段一致。

终点应满足现有 CRM 已冻结的：

```text
terminal / ownership rule
```

不得生成后再依赖 Solver 排除明显非法 Pairing。

## 12. Original Pairing

每个 Crew 应保留一个合法 original pairing。

必须通过 Phase 4 已加严的 semantic resolver 验证：

```text
OPERATE sequence == Crew.original_pairing
无额外 DEADHEAD
无 recovery-only segment
```

如果 original pairing 在当前 disruption 后仍合法，必须进入 generated set。

如果因 Scenario 已明确不合法，可以不生成，但必须记录原因。

## 13. Idle / No-duty Pairing

如当前模型允许 Crew 在恢复窗口内不执行任何航班，应显式定义：

```text
idle / no-duty pairing
```

仅在 start station、terminal requirement、duty semantics 允许时生成。

不能通过 0 个 Pairing 被选表达 idle，因为当前 CRM 语义是：

```text
one pairing per crew
```

## 14. Pairing Enumeration

Phase 6 v1 不做 Pricing。

建议使用：

```text
DFS / DAG path enumeration
```

从 Crew start state 开始扩展合法：

```text
OPERATE
DEADHEAD
```

路径，直到 Recovery Horizon 或合法 terminal state。

必须保证：

```text
deterministic
stable ordering
无重复 Pairing
```

建议 canonical key：

```text
crew_id
+
ordered (leg_type, flight_option_id)
```

## 15. 剪枝原则

允许基于确定性 legality 做剪枝：

```text
station mismatch
time infeasible
qualification mismatch
duty-time violation
recovery horizon violation
terminal impossible
```

禁止基于：

```text
当前 Solver dual
Reduced Cost
人为成本阈值
```

做剪枝，因为 Phase 6 不是 Pricing。

## 16. 独立 Pairing Legality Validator

建议新增 pure function：

```text
validate_generated_crew_pairing(...)
```

至少独立复算：

```text
crew ownership
known Flight Options
OPERATE / DEADHEAD legality
station continuity
time continuity
qualification
duty duration
rest rule（若已实现）
recovery horizon
terminal/base requirement
```

Generator 输出后必须重新经过 validator。

## 17. Smart Generator vs Brute-force Oracle

必须增加一个很小的：

```text
toy_case_008_crew_pairing_generator
```

规模足够小，使 brute-force 可以枚举所有可能的 `(leg_type, Flight Option)` 序列。

验证：

```text
smart generator legal set
==
brute-force legal set
```

Oracle 与 Generator 可以共享 single-pairing legality predicate，但不能共享 pairing enumeration algorithm。

建议：

```text
Smart Generator
= network + DFS + pruning

Oracle
= exhaustive sequence enumeration
```

## 18. 与人工 Crew Pairings 比较

在：

```text
phase1_benchmark_001
```

上运行 Generator。

至少检查当前 Manual Reference / Phase 2 CRM 所需关键 Pairings 是否都能在 generated set 中找到语义等价 Pairing。

比较：

```text
crew_id
ordered OPERATE / DEADHEAD legs
start station
end station
```

不要只比较 Pairing ID。

Generator 生成更多合法 Pairings允许。

## 19. Generated Pairings 回灌 Integrated Oracle

构造新的 Recovery Columns：

```text
existing Flight Options
+
Phase 5 generated Aircraft Strings
+
Phase 6 generated Crew Pairings
+
existing Passenger Itineraries
```

然后：

```text
重新 build Recovery Scope
```

再运行：

```text
Phase 3 Full Integrated Oracle
```

必要时同时运行：

```text
Phase 4 Scope-limited Oracle
```

## 20. Objective 比较

比较：

```text
OBJ_manual_pairings
vs
OBJ_generated_pairings
```

规则：

- 相等：自动 Pairing universe 至少保留当前 fixed-column optimum；
- 更低：不自动判错，需确认新 Pairing 完全合法且改善来自人工列漏列；
- 更高或 infeasible：优先判断 Generator 是否漏掉关键合法 Pairing，Phase 6 不得 PASS。

## 21. Scope 与 Candidate Universe 再闭包

Phase 6 生成新 Crew Pairings 后必须：

```text
rebuild Recovery Scope
```

正式流水线：

```text
Phase 5 generated Strings
→ rebuild Scope
→ Phase 6 generated Pairings
→ rebuild Scope
→ Phase 7
```

不得继续沿用旧 Scope。

## 22. Phase 6 Metrics

至少输出：

```text
Crew count
Scoped Crew count
Flight Option count
Crew-network node count
Crew-network edge count
Generated Pairing count by Crew
OPERATE leg count
DEADHEAD leg count
Rejected candidate count by reason
Generation runtime
```

Benchmark 还应输出：

```text
manual Pairing count
generated Pairing count
manual key-pairing coverage
Integrated objective before / after
```

## 23. 推荐测试

建议新增：

```text
tests/unit/test_crew_network.py
tests/unit/test_pairing_generator.py
tests/regression/test_phase6_pairing_generator_oracle.py
tests/regression/test_phase6_benchmark_001.py
```

至少覆盖：

```text
station mismatch rejected
time overlap rejected
min connection rejected
qualification mismatch rejected
duty-time violation rejected
recovery horizon rejected
terminal mismatch rejected
illegal OPERATE rejected
illegal DEADHEAD rejected
DEADHEAD not counted as OPERATE
original pairing retained
idle pairing legality
duplicate pairing removed
scope limits generation
deterministic output
```

以及：

```text
smart generator == brute-force oracle
```

## 24. 与 CRM / Integrated Audit 对齐

Generated Pairings 必须继续通过当前 CRM / Integrated audit。

不得为了适配 Generator 修改已冻结的：

```text
Operating coverage
Non-required operating prohibition
Deadhead schedule consistency
Crew ownership
Terminal
Crew reassignment cost
Deadhead cost
```

如果 Generator 与现有 CRM semantics 冲突，优先定位 Generator 问题。

## 25. Assumptions

新增前读取最新 `assumptions.md` 编号。

至少明确：

```text
Candidate Universe change → Scope rebuild
Crew min connection test profile
Crew duty/rest boundary
Crew qualification boundary
Idle pairing rule
DEADHEAD generation rule
Phase 6 uses existing Flight Options
Phase 6 does not perform Pricing
```

继续区分：

```text
Paper-defined
Implementation Assumption
Airline-specific Extension
```

## 26. Phase 6 明确不做

不得实现：

```text
Crew Pairing Pricing
Reduced Cost
Dual-driven generation
Column Generation
Benders
Crew Rostering
Bidline / monthly roster
真实 FAR/CCAR duty rule 全集
真实 reserve crew system
真实 qualification database
Passenger Itinerary Generator
```

Phase 6 是：

```text
explicit legal candidate Pairing Generator
```

不是：

```text
optimization pricing subproblem
```

## 27. 文档同步

完成后更新：

```text
README.md
assumptions.md
reproduction_notes.md
docs/AIR_HTML_Python_Reproduction_Plan.md
```

明确：

```text
Phase 6 = explicit/full Crew Pairing generation
not Pricing / Column Generation
```

若 generated Pairings 改善 Integrated Objective，必须记录原因。

## 28. Codex Report

新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase6_crew_pairing_generator_report.md
```

至少包含：

```text
1. Phase 5 Closeout
2. Modified Files
3. Scope Rebuild Rule
4. Generator Input / Output
5. Crew Network
6. OPERATE / DEADHEAD Semantics
7. Qualification / Timing / Duty Rules
8. Smart Generator
9. Independent Legality Validator
10. Brute-force Oracle
11. Toy Oracle Comparison
12. Benchmark Generated Pairings
13. Manual Key-pairing Coverage
14. Integrated Oracle Result
15. Tests
16. New Assumptions
17. Known Limitations
18. Acceptance Checklist
19. Final Decision
```

最终明确：

```text
Phase 6 PASS
```

或：

```text
Phase 6 NOT PASS
```

## 29. Phase 6 Acceptance Criteria

- [ ] Phase 5 Scope 重算规则已正式写入
- [ ] Phase 5 旧文档已清理
- [ ] Crew Network 已实现
- [ ] Crew Pairing Generator 已实现
- [ ] 使用现有 Flight Options，不静默扩大 Flight Option universe
- [ ] Scope 限制生成范围
- [ ] Station continuity 正确
- [ ] Time continuity 正确
- [ ] Min connection 使用显式配置
- [ ] Qualification 规则仅使用已有数据
- [ ] Duty / Rest 不超出现有数据与已登记 assumption
- [ ] Recovery Horizon 正确
- [ ] Terminal / Base 规则正确
- [ ] OPERATE / DEADHEAD 语义正确
- [ ] DEADHEAD 不计入 operating coverage
- [ ] Original / idle pairing 语义正确
- [ ] Generator deterministic 且无重复
- [ ] Generated Pairing 通过独立 legality validator
- [ ] Smart Generator 与 brute-force oracle 对齐
- [ ] Benchmark 人工关键 Pairings 未遗漏
- [ ] Generated Pairings 可重新运行 Integrated Oracle
- [ ] 新 Pairings 生成后重新构建 Scope
- [ ] 若 objective 改善，有明确合法原因
- [ ] 若 objective 变差或 infeasible，Phase 6 不得 PASS
- [ ] full pytest 0 failed
- [ ] full pytest 0 skipped
- [ ] Phase 3 / 4 / 5 regression 无回归
- [ ] 未进入 Pricing / CG / Benders

Phase 6 PASS 后进入：

```text
Phase 7 Passenger Itinerary Generator
```
