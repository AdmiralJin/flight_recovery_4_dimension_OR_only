# AIR 航空公司综合恢复复现项目

本项目分阶段复现 Petersen et al. (2010) 的航空公司综合恢复模型 **AIR — An Optimization Approach to Airline Integrated Recovery**，并为后续真实航空公司大面积延误恢复项目保留工程扩展接口。

当前项目采用：

```text
HTML / Vanilla JavaScript
        ↓ JSON / HTTP
FastAPI + Pydantic
        ↓
后续 OR Models / Solver
```

当前重点仍然是：

> **先建立可人工核验的数据、候选列和 Oracle，再实现复杂优化算法。**

---

## 当前进度

| 阶段 | 状态 | 主要内容 |
|---|---|---|
| Phase 0 | ✅ 完成 | Scenario Schema、Validator、HTML 数据编辑器、toy case |
| Phase 0.5 | ✅ 完成 | 原计划 / 扰动 / 风险传播 / 容量可视化 |
| Phase 1 | ✅ 完成 | Benchmark、人工候选列、运行时 Schema、语义校验、指标复算与回归/负例测试 |
| Phase 2.0 | ✅ 完成 | 确定性 Index、Incidence Builder、容量边界与 benchmark 回归 |
| Phase 2.1 | ✅ 完成 | Solver Adapter、Gurobi、Cost Config、ModelSolveResult contracts |
| Phase 2.2 | ✅ 完成 | Fixed-column SRM、C01–C06、Gate Inventory proxy、Market-seat proxy、独立诊断 |
| Phase 2.3+ | ⏳ 未开始 | Fixed-column ARM / CRM / PRM、Integrated Oracle 等 |

Phase 1 证明数据、候选列和人工 Oracle 在当前规则下语义一致；它不证明 AIR 恢复目标的数学全局最优性。

---

# 数据编辑入口

前端入口：

```text
frontend/index.html
```

不要直接双击 HTML 文件。

先在项目根目录运行：

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

浏览器访问：

```text
http://127.0.0.1:8000
```

---

# Data Editor

当前页面支持：

- Scenario；
- Airports；
- Flights；
- Aircraft；
- Crew；
- Passengers；
- Airport Capacity；
- Disruptions。

表格支持：

- Add Row；
- Edit；
- Duplicate Row；
- Delete Row；
- Reset；
- Load Example；
- Import JSON；
- Export JSON；
- Validate。

人工编辑后的 Scenario 保存在当前浏览器页面内存状态中。

---

# Visualization

同一页面提供：

```text
Data Editor
Visualization
```

两种一级视图。

进入 Visualization 时，系统先校验当前 Scenario；校验失败则拒绝绘图。

当前可视化包括：

- Time-Space Network；
- Disruption Overlay；
- Direct Exposure；
- Aircraft/Crew Downstream Risk；
- Flight Resource Detail；
- Airport Capacity Heatmap。

当前 Visualization 表示：

```text
Original Plan
+
Known Disruption
+
Deterministic Risk Analysis
```

不表示：

```text
Actual Delay
Cancellation
Optimized Recovery
```

Recovered Plan 需要等后续 Solver / Expected Result 接口正式接入。

---

# `toy_case_001`

基础示例：

```text
data/examples/toy_case_001.json
```

它主要用于：

- Scenario Schema smoke test；
- Data Editor；
- Import/Export；
- Validator；
- Visualization；
- 简单传播逻辑。

它不是当前 Phase 1 主综合恢复 Oracle。

---

# Phase 1 主 Benchmark

Phase 1 主人工集成案例：

```text
data/examples/phase1_benchmark_001.json
```

设计规模：

```text
4 Airports
12 Flights
4 Aircraft
5 Crew
8 Passenger Groups
1 Airport Departure-Capacity Disruption
```

详细设计建议放在：

```text
docs/benchmarks/PHASE1_BENCHMARK_001_DESIGN.md
```

---

# Phase 1 Manual Columns

标准目录：

```text
data/columns/phase1_benchmark_001_columns.json
```

Columns v1.0.0 包含：

```text
flight_options
aircraft_strings
crew_pairings
passenger_itineraries
```

这些是**人工候选列**：

> 用有限人工列代替后续自动列生成器，先验证 Fixed-Column 模型。

它们不是未来自动 Column Generation 的最终替代品。

---

# Recovery Option 设计

原 Flight ID 始终保持不变。

例如：

```text
base flight = F2

FO_F2_ORIG
FO_F2_D50
FO_F2_CANCEL
```

而不是建立：

```text
F2_DELAY50
F2_CANCEL
```

作为新的原航班 ID。

当前接口能够表达：

- unchanged；
- delay；
- cancellation；
- origin/destination change；
- ferry；
- aircraft reassignment；
- crew reassignment；
- passenger reaccommodation；
- unserved passengers。

Schema 说明：

```text
docs/RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md
```

JSON Schema：

```text
schemas/recovery_columns_v1.schema.json
schemas/recovery_expected_v1.schema.json
```

---

# Phase 1 Manual Reference

人工参考结果：

```text
data/expected/phase1_benchmark_001_expected.json
```

当前 Reference 的关键恢复动作：

```text
F2  +50 min
F10 +20 min
F11 +10 min
```

Aircraft：

```text
AC1:
F1 → F2 → F10

AC4:
F3 → F11 → F12
```

因此包含：

```text
2 Aircraft Reassignments
```

Passenger P4：

```text
F2→F3
→
F8
```

Reference Metrics：

```text
operated_flights = 12
cancelled_flights = 0
delayed_flights = 3
total_flight_departure_delay_minutes = 80

aircraft_reassignments = 2
crew_reassignments = 0

passenger_reaccommodated_count = 15
passenger_delay_minutes_weighted = 1800
unserved_passengers = 0
```

---

# Manual Reference 不等于 Proven Optimal

当前 Expected 应理解为：

```text
reference_type = manual_reference
solution_status = feasible
```

而不是已证明的：

```text
solver_optimal
```

因为尚未正式实现/确定：

- Delay Cost；
- Cancellation Cost；
- Aircraft Reassignment Cost；
- Crew Reassignment Cost；
- Passenger Disruption Cost；
- Route Change / Ferry Cost；
- 完整 SRM/ARM/CRM/PRM Objective。

例如 80 分钟 + 2 次换机是否一定优于 110 分钟纯延误，取决于后续正式定义的成本。

因此当前 Reference 的用途是：

> **给后续模型一个可解释、可核验的人工参照，而不是提前声称全局最优。**

---

# Expected / Oracle 结构

Expected v1.0.0 分为：

```text
reference_solution
oracle_invariants
comparison_policy
objective
```

这样可以处理多个等价解。

后续 Solver 验收优先比较：

- Feasibility；
- Flight Recovery Decisions；
- Cancellation；
- Delay；
- Airport Capacity；
- Maintenance / Terminal Conditions；
- Passenger Service；
- Objective（正式定义后）。

不应无条件要求完整 Aircraft/Crew Assignment Vector 与人工 Reference 完全一致。

---

# 推荐项目数据结构

```text
data/
├── examples/
│   ├── toy_case_001.json
│   └── phase1_benchmark_001.json
├── columns/
│   └── phase1_benchmark_001_columns.json
└── expected/
    └── phase1_benchmark_001_expected.json

schemas/
├── recovery_columns_v1.schema.json
└── recovery_expected_v1.schema.json

docs/
├── AIR_HTML_Python_Reproduction_Plan.md
├── RECOVERY_COLUMNS_EXPECTED_SCHEMA_V1.md
└── benchmarks/
    └── PHASE1_BENCHMARK_001_DESIGN.md
```

---

# API

当前主要 API：

```text
GET  /api/health
GET  /api/examples/toy_case_001
POST /api/validate
POST /api/solve
```

其中：

- `/api/validate`：执行 Scenario 结构与跨实体一致性校验；
- `/api/solve`：真正 Solver 接入前仍应保持安全闸门，不应返回伪优化结果。

---

# 测试

运行：

```bash
python -m pytest
```

Phase 0/0.5 的既有测试应长期保持通过。

Phase 1 已包含：

- Recovery Columns / Expected Python/Pydantic Schema；
- Column / Oracle Semantic Validator；
- Reference Metrics 程序化复算；
- `phase1_benchmark_001` Regression；
- 按具体错误码断言的 Negative Tests。

---

# 下一步

当前下一工程任务是：

```text
Phase 2.3 Fixed-column ARM
        ↓
Fixed-column CRM
        ↓
Fixed-column PRM
        ↓
Full Integrated Fixed-column Oracle
```

完整开发路线见：

```text
docs/AIR_HTML_Python_Reproduction_Plan.md
```

论文内容与实现补充的区别见：

```text
assumptions.md
reproduction_notes.md
```
