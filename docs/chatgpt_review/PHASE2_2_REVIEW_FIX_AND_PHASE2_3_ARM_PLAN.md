# Phase 2.2 Review Fix + Phase 2.3 Fixed-Column ARM Plan

> 用途：供 Codex 在当前 `main` 基础上继续工作。  
> 顺序：**先完成 Phase 2.2 review fix 并留痕，再进入 Phase 2.3 ARM。**  
> 本文件不包含 HTML / Frontend 修改。

---

# 1. Phase 2.2 审核结论

Phase 2.2 主体实现可保留，不需要结构性返工。

已确认：

- `SRM-C01 ~ SRM-C06` 已进入模型；
- Flight Coverage / Strategic / Arrival Capacity / Departure Capacity 实现方向正确；
- Gate 明确标为 provisional/generated；
- Market-seat 明确标为 proxy/generated；
- SRM 只收取 SRM-owned cost；
- Ferry 未混入 SRM；
- `ModelSolveResult` 保持 single-model 语义；
- Benchmark 有独立 constraint/objective audit；
- 最新报告记录测试全部通过且 Gurobi 实际执行。

当前需要先处理 1 个必改项，并建议补 2 个低风险增强项。

---

# 2. Phase 2.2 必改：Gate Capacity 边界语义

## 2.1 当前问题

当前 Gate checkpoint builder 同时采用：

```text
AirportInterval = [start_time, end_time)
```

以及把 interval `end_time` 加入 checkpoint。

因此在以下正常场景：

```text
08:00-12:00 gate_capacity = 4
12:00-16:00 gate_capacity = 3
recovery_end = 16:00
```

`16:00` 不属于任何 `[start,end)` interval。

若不同 interval 的 gate capacity 不一致，当前 fallback 可能 fail fast，即：

> 数据完整覆盖到 recovery horizon，但仅因为 terminal boundary 不属于半开区间而错误失败。

---

## 2.2 修改要求

明确冻结以下规则：

### Internal boundary

若：

```text
t = interval_i.end_time = interval_j.start_time
```

则：

```text
t 属于 interval_j
```

严格遵守：

```text
[start_time, end_time)
```

### Recovery terminal boundary

对：

```text
t == recovery_window.end
```

不能按普通 `[start,end)` lookup。

推荐定义：

```text
terminal gate checkpoint
```

使用**最后一个以 recovery_end 为 end_time 的有效 interval 的 gate_capacity**进行终点库存检查。

该规则只用于：

```text
recovery_end terminal inventory audit
```

不得解释为该 interval 在 recovery_end 之后仍有效。

如果不存在唯一、可解释的 terminal capacity source，则 fail fast。

---

## 2.3 测试要求

至少新增：

```text
test_gate_internal_boundary_uses_next_interval
test_gate_terminal_boundary_accepts_varying_capacities
test_gate_terminal_boundary_rejects_ambiguous_capacity
```

必须覆盖：

```text
连续 intervals
+
不同 gate_capacity
+
recovery_end == final interval.end_time
```

---

## 2.4 Assumption 留痕

更新 `assumptions.md` 中 Gate 相关条目，优先修改/补充现有：

```text
A-029
A-030
```

不要重复创建表达同一规则的新 assumption。

必须明确记录：

```text
internal boundary -> right interval
terminal boundary -> explicit terminal convention
```

以及：

```text
该规则属于 implementation assumption / generated provisional
```

---

# 3. Phase 2.2 建议增强

## 3.1 Benchmark regression 固定 Objective

当前固定数据组合：

```text
phase1_benchmark_001
+
phase2_test_costs_v1
```

建议增加：

```text
objective == 70
```

作为 regression baseline。

不要盲目固定完整 solution vector。

如果要固定：

```text
FO_F10_D20
```

必须先确认该选择在当前 fixed-column SRM 下不存在等价 optimum；若存在等价解，应继续按 invariant / objective 比较。

---

## 3.2 Gurobi skip 可见性

当前部分测试在 Gurobi unavailable 时可 `skip`。

建议增加一个明确的 solver integration gate，使正式 Phase 2 验收能够区分：

```text
pytest passed
```

和：

```text
Gurobi integration actually executed
```

Codex Report 必须继续单独记录：

```text
passed
failed
skipped
Gurobi version
```

此项不要求重构 SolverAdapter。

---

# 4. Phase 2.2 Review Fix 验收

完成以下项目后，正式冻结 Phase 2.2：

- [ ] Gate internal boundary test PASS；
- [ ] Gate recovery-end boundary test PASS；
- [ ] varying gate-capacity case PASS；
- [ ] `assumptions.md` 已更新；
- [ ] benchmark objective regression 已增加或明确说明为何暂不固定；
- [ ] full pytest PASS；
- [ ] Gurobi integration 实际执行；
- [ ] 在 `docs/codex_reports/` 新增 review-fix 报告。

建议报告名：

```text
YYYYMMDD_HHMMSS_phase2_2_review_fix_report.md
```

报告只需简要说明：

```text
1. Review finding
2. Code changes
3. Assumption changes
4. Tests added
5. Full pytest result
6. Gurobi result
7. Phase 2.2 final status
```

最终明确：

```text
Phase 2.2 FINAL PASS
```

或：

```text
Phase 2.2 NOT PASS
```

---

# 5. Phase 2.3 目标

Phase 2.3 实现：

```text
Fixed-Column ARM
Aircraft Recovery Model
```

对应当前总计划中的论文：

```text
(3.8) - (3.12)
```

本阶段只验证：

> 给定需要执行的 Flight Options，现有人工 Aircraft Strings 能否以最低 ARM-owned cost 完成飞机恢复。

不得在 Phase 2.3：

- 动态生成 Aircraft Strings；
- 修改 SRM 数学模型；
- 重新选择取消/延误方案；
- 引入 Crew；
- 引入 Passenger；
- 做 Integrated Oracle；
- 做 Benders；
- 做 Column Generation；
- 修改 HTML。

---

# 6. Phase 2.3 输入边界

继续使用：

```text
Scenario
RecoveryColumns.flight_options
RecoveryColumns.aircraft_strings
FixedColumnCostConfig
SolverAdapter
```

ARM 还需要一个明确的：

```text
required_operated_option_ids
```

表示：

> 当前 schedule 层已经决定必须实际执行的 revenue Flight Options。

建议建立显式 input contract，而不是让 `arm.py` 偷偷读取某个 SRM 全局变量。

例如：

```text
AircraftRecoveryRequest
- scenario_id
- required_operated_option_ids
```

或等价轻量 immutable structure。

---

# 7. required_operated_option_ids 来源

Phase 2.3 必须支持两种测试来源：

### Unit test

测试代码直接给：

```text
required_operated_option_ids
```

### Benchmark

优先使用 Phase 2.2 SRM 的 selected operated options 作为 ARM 输入，形成：

```text
SRM result
    ↓
selected operated Flight Options
    ↓
ARM
```

但必须保持：

```text
SRM 和 ARM 仍是两个独立模型
```

此流程只是测试顺序，不是 Phase 3 Integrated Oracle。

如果 SRM optimum 无法被现有 Aircraft Strings 覆盖：

```text
ARM = INFEASIBLE
```

这是合法结果，不得为了让 ARM 通过而静默修改 SRM solution 或 Columns。

---

# 8. Phase 2.3 变量

对每个 Aircraft String：

```text
y_s ∈ {0,1}
```

其中每个 string 已绑定：

```text
aircraft_id
leg_option_ids
start_station
end_station
maintenance_satisfied
```

Phase 2.3 使用**现有人工 fixed columns**。

不生成新 string。

---

# 9. 建议稳定 Constraint IDs

建议：

```text
ARM-C01-AIRCRAFT-STRING-SELECTION
ARM-C02-FLIGHT-OPTION-COVERAGE
ARM-C03-TERMINAL-STATION
ARM-C04-MAINTENANCE
ARM-C05-STRING-FEASIBILITY
```

论文 `(3.8)-(3.12)` 与具体 ID 的一一映射，必须在编码前根据论文和现有项目符号再次核对，并在 Codex Report 中写清。

禁止只凭名称猜论文公式编号。

---

# 10. ARM-C01 Aircraft String Selection

对每架 aircraft：

```text
sum(y_s for s belonging to aircraft a) = 1
```

含义：

> 每架参与恢复的飞机必须选择一条完整 Aircraft String。

需要明确：

- 同一 `string_id` 只能属于一个 aircraft；
- 每架 aircraft 至少有一个候选 string；
- 不允许一架 aircraft 同时选择两条路径。

如果未来需要 aircraft idle string，应显式作为一条合法 String 提供，而不是允许“0 条”。

---

# 11. ARM-C02 Required Flight Option Coverage

Phase 2.0 已计划/构建：

```text
A_FS
Flight Option - Aircraft String incidence
```

必须复用或扩展现有 incidence，而不是在 ARM 中重复临时扫描出另一套不一致逻辑。

对每个：

```text
required operated revenue option o
```

要求：

```text
sum(A_FS[o,s] * y_s) = 1
```

即：

> 每个必须执行的 Flight Option 恰好由一架飞机覆盖一次。

---

## 11.1 不应覆盖的 option

以下不进入 revenue flight coverage：

```text
cancel
```

Ferry：

```text
可以作为 Aircraft String leg
```

但没有 base flight，因此：

```text
不进入 revenue-flight exactly-one coverage
```

它的存在由选中的 String 自然决定。

---

# 12. 非 selected revenue option 防泄漏

这是 Phase 2.3 易错点。

如果 SRM 要求：

```text
FO_F2_D50
```

但某 Aircraft String 同时包含：

```text
FO_F3_D30
```

而当前 schedule 要求的是：

```text
FO_F3_ORIG
```

该 String 不应被 ARM 允许选择。

因此 ARM 不仅要保证：

```text
required options 被覆盖
```

还必须保证：

> 选中的 Aircraft Strings 不得执行任何与当前 schedule choice 冲突的额外 revenue Flight Option。

推荐做法：

构建：

```text
allowed_operated_option_ids
=
required_operated_option_ids
```

对所有不在 required set 中的 revenue `operate` option：

```text
sum(A_FS[o,s] * y_s) = 0
```

或在建模前直接过滤包含冲突 revenue options 的 strings。

优先选择**约束可审计性更强**的实现。

Ferry 不受该禁止规则影响。

---

# 13. ARM-C03 Terminal Station

Scenario 已有：

```text
Aircraft.required_station_at_T_end
```

Aircraft String 已有：

```text
end_station
```

建议在进入模型前构建：

```text
terminal_compatible[string_id]
```

要求被选择 String：

```text
end_station == aircraft.required_station_at_T_end
```

不 compatible 的 string：

```text
y_s = 0
```

或预过滤。

必须有 negative test：

```text
所有候选 strings terminal 不匹配
→ INFEASIBLE
```

---

# 14. ARM-C04 Maintenance

Scenario 已有：

```text
maintenance_required
maintenance_stations
```

Aircraft String 已有：

```text
maintenance_satisfied
```

Phase 2.3 第一版建议保持 fixed-column 语义：

若：

```text
aircraft.maintenance_required == true
```

则选中的 String 必须：

```text
maintenance_satisfied == true
```

同时必须检查该 flag 的可信度：

- String 的 `maintenance_satisfied` 不能引用未知 aircraft；
- 若现有 validator 已对 station/path 做过检查，应复用；
- Phase 2.3 不重新发明 maintenance scheduling。

如果当前 String Schema 无法证明更细粒度 maintenance timing，则登记 assumption：

```text
Phase 2.3 trusts validated fixed-column maintenance_satisfied
```

不能声称实现真实航司完整维修规则。

---

# 15. ARM-C05 String Feasibility

Aircraft String 在进入 MIP 前必须通过已有 semantic validation。

至少：

```text
start_station == aircraft.initial_station_at_t
station continuity
time continuity
all leg_option_ids exist
cancel option not present
aircraft_id valid
terminal fields valid
maintenance fields valid
```

当前项目时间连续规则仍按现有 assumption：

```text
previous_arrival <= next_departure
```

Phase 2.3 不应未经单独假设升级就突然加入 aircraft minimum turn time。

若决定本阶段加入 minimum turn：

> 必须先新增正式 input/assumption/test，再实施。

默认本计划不加入。

---

# 16. Ferry 处理

Phase 2.3 是 Ferry 的第一个正式 owner。

规则：

```text
operation_type = ferry
base_flight_id = null
```

Ferry：

- 可以出现在 Aircraft String；
- 不属于 SRM schedule coverage；
- 不属于 revenue flight coverage；
- 被选 String 含 Ferry 时才产生 ferry cost。

Ferry cost 使用 Phase 2.1 canonical：

```text
ferry_per_minute
```

建议：

```text
ferry_cost
=
block_minutes * ferry_per_minute
```

若论文原成本维度与当前字段不同，继续明确标记：

```text
Implementation Assumption
```

不得在 `arm.py` 加 Magic Number。

---

# 17. Aircraft Reassignment Cost

现有 Assumption 已冻结：

> 如果某 aircraft string 覆盖了原计划属于另一架飞机的 base flight，则表示 aircraft reassignment。

因此对选中 string：

逐个 revenue operate leg：

```text
base_flight.original_aircraft
vs
string.aircraft_id
```

不一致则计：

```text
aircraft_reassignment
```

当前 test profile：

```text
aircraft_reassignment = 0
```

但逻辑仍必须真正实现并测试。

必须有 unit test 使用临时 non-zero coefficient，例如：

```text
aircraft_reassignment = 100
```

验证 objective 会响应。

---

# 18. ARM Objective

Phase 2.3 只能收取 ARM-owned cost：

```text
aircraft reassignment
ferry
```

Objective：

```text
min Σ string_arm_cost(s) * y_s
```

其中：

```text
string_arm_cost
=
reassignment cost
+
ferry cost
```

不得重复计入：

```text
flight delay
flight cancellation
origin/destination change
crew reassignment
deadhead
passenger delay
unserved passenger
```

这些属于其他 canonical owner。

---

# 19. Cost 计算位置

不要信任 Columns JSON 中：

```text
cost_components
```

作为最终真源。

继续遵守：

```text
FixedColumnCostConfig
=
global canonical source
```

建议新增：

```text
aircraft_string_cost(...)
```

或等价 pure function。

输入：

```text
scenario
flight_options
aircraft_string
cost_config
```

输出至少：

```text
total
reassignment_count
reassignment_cost
ferry_minutes
ferry_cost
```

便于独立复算。

---

# 20. ARM Result Diagnostics

继续返回：

```text
ModelSolveResult
```

并固定：

```text
model = ARM
single_model_only = true
```

diagnostics 至少包含：

```text
selected_string_by_aircraft
covered_required_options
uncovered_required_options
duplicate_coverage
unexpected_revenue_options
ferry_legs
ferry_minutes
aircraft_reassignment_count
terminal_status
maintenance_status
objective_breakdown
```

求解后必须独立复算。

不得只依据：

```text
solver_status == OPTIMAL
```

判定业务正确。

---

# 21. 新 Assumptions

执行前先读取最新 `assumptions.md`，从下一个空闲编号继续。

建议至少记录：

### ARM Fixed-Column Input Boundary

```text
Phase 2.3 接收外生 required_operated_option_ids；
ARM 不重新决定 schedule。
```

### One String per Aircraft

如果论文到当前 Schema 的映射需要说明，则登记。

### Fixed-Column Maintenance Trust

```text
maintenance_satisfied
```

是人工候选 String 已验证属性，不是完整 maintenance scheduling。

### Ferry Cost Mapping

当前：

```text
ferry_per_minute * block_minutes
```

属于 implementation assumption。

### ARM Single-Model Result Boundary

ARM feasible/optimal：

> 只说明当前 schedule 在现有 Aircraft Strings 下的 aircraft recovery 子模型结果。

不代表 Crew / Passenger / Integrated Recovery 可行。

---

# 22. Unit Tests

至少包括：

## String selection

```text
1 aircraft / 2 strings
→ exactly one
```

## Flight coverage

```text
required option covered once → feasible
required option no string covers → infeasible
two selected strings would duplicate option → prohibited
```

## Schedule consistency

```text
String contains non-required conflicting revenue option
→ string cannot be selected
```

这是必须重点测试的逻辑。

## Terminal

```text
compatible → feasible
all incompatible → infeasible
```

## Maintenance

```text
maintenance_required=false → normal
maintenance_required=true + satisfied string → feasible
maintenance_required=true + no satisfied string → infeasible
```

## Reassignment

用非零 test coefficient 验证：

```text
reassignment count
cost
objective
```

## Ferry

验证：

```text
ferry accepted as string leg
not counted as revenue coverage
ferry minutes correct
ferry cost correct
```

## Invalid input

至少：

```text
unknown required option
cancel option listed as required operated option
duplicate string_id
unknown aircraft_id
unknown leg option
string contains cancel
```

现有 validator 已覆盖的内容可复用，不必重复实现 validation engine，但 ARM entry point 应 fail fast。

---

# 23. Benchmark Regression

使用：

```text
phase1_benchmark_001
phase1_benchmark_001_columns
phase2_test_costs_v1
```

流程建议：

```text
1. solve SRM
2. 提取 selected operated revenue options
3. 作为 ARM required_operated_option_ids
4. solve ARM
5. independent audit
```

当前 SRM 已知 baseline：

```text
objective = 70
F2 -> FO_F2_D50
F10 -> FO_F10_D20
```

ARM regression 不应强制与 Phase 1 Manual Reference 的完整 Aircraft assignment 完全一致，除非唯一性已证明。

重点检查：

```text
- 每架飞机 exactly one string
- required revenue options exactly once
- no unexpected revenue option
- terminal satisfied
- maintenance satisfied
- objective 独立复算一致
```

如果当前 SRM selection 在人工 Aircraft Strings 下无法覆盖：

```text
记录 ARM INFEASIBLE
```

然后分析是否属于：

```text
fixed-column coverage不足
```

而不是直接修改算法使其“通过”。

若确实缺少合理 fixed column，应：

1. 记录原因；
2. 单独新增人工 Aircraft String；
3. 更新 Columns validator tests；
4. 不修改 SRM Objective 来迁就 ARM。

---

# 24. 建议实现文件

建议：

```text
backend/core/arm.py
```

如成本/审计逻辑复杂，可拆：

```text
backend/core/aircraft_cost.py
```

或保持在现有 cost module 中，只要 canonical ownership 清晰。

测试：

```text
tests/unit/test_arm.py
tests/regression/test_phase2_arm_benchmark_001.py
```

若现有 Phase 2 命名方式不同，按仓库既有风格统一。

---

# 25. Phase 2.3 Acceptance Criteria

只有以下全部满足，Phase 2.3 才能 PASS：

- [ ] 论文 `(3.8)-(3.12)` 与实现约束映射已核对并写入报告；
- [ ] 使用 fixed `aircraft_strings`；
- [ ] 不动态生成 String；
- [ ] ARM 不重新决定 SRM schedule；
- [ ] 每架 aircraft exactly one String；
- [ ] required revenue option exactly one aircraft coverage；
- [ ] non-required conflicting revenue option 不得泄漏；
- [ ] Ferry 正确进入 Aircraft String 且不进入 revenue coverage；
- [ ] Terminal constraint 生效；
- [ ] Maintenance constraint 生效；
- [ ] Reassignment cost 真正实现；
- [ ] Ferry cost 真正实现；
- [ ] ARM 只收取 ARM-owned cost；
- [ ] objective 可独立复算；
- [ ] Normal / Infeasible / Negative tests 完整；
- [ ] benchmark regression 存在；
- [ ] full pytest PASS；
- [ ] Gurobi tests 实际运行；
- [ ] assumptions 已登记；
- [ ] README / reproduction plan / Codex Report 状态同步；
- [ ] 未修改 HTML；
- [ ] 未进入 CRM / PRM / Integrated Oracle / Benders / CG。

---

# 26. Phase 2.3 Codex Report

完成后新增：

```text
docs/codex_reports/YYYYMMDD_HHMMSS_phase2_3_fixed_column_arm_report.md
```

至少包含：

```text
1. Modified Files
2. Paper (3.8)-(3.12) Mapping
3. ARM Input Contract
4. Constraint Mapping Table
5. Cost Ownership
6. New Assumptions
7. Unit / Negative Tests
8. Benchmark Result
9. Objective Audit
10. Terminal / Maintenance Audit
11. Ferry / Reassignment Audit
12. Full Pytest Result
13. Gurobi Result
14. Known Limitations
15. Acceptance Checklist
16. Next Recommended Step
```

最终明确：

```text
Phase 2.3 PASS
```

或：

```text
Phase 2.3 NOT PASS
```

不得只写 `Done`。

---

# 27. Phase 2.3 完成后的下一步

只有 Phase 2.3 PASS 后再进入：

```text
Phase 2.4 Fixed-Column CRM
```

即：

```text
Crew Pairing selection
Crew Flight Option coverage
Crew reassignment
Deadhead
Terminal / pairing feasibility
论文 (3.13)-(3.15)
```

不要在 Phase 2.3 顺手提前实现。
