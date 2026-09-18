# AIR 航空公司综合恢复复现项目

本项目分阶段复现 Petersen et al. (2010) 的航空公司综合恢复模型 **AIR — An Optimization Approach to Airline Integrated Recovery**，并为后续真实航空公司大面积延误恢复项目保留工程扩展接口。

当前项目采用：

```text
HTML / Vanilla JavaScript
        ↓ JSON / HTTP
FastAPI + Pydantic
        ↓
Integrated Oracle / Benders / Column Generation / Branch-and-Price + Gurobi
```

贯穿 Phase 0–13 的研发原则是：

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
| Phase 2.3 | ✅ 完成 | Fixed-column ARM、外生 schedule contract、Aircraft Strings、Ferry/Maintenance、独立诊断 |
| Phase 2.4 | ✅ 完成 | Fixed-column CRM、canonical schedule handoff、Crew Pairings、Operating/Deadhead、独立诊断 |
| Phase 2.5 | ✅ 完成 | Fixed-column PRM、外生 Seat Capacity、Passenger Itineraries、delay/unserved cost、独立诊断 |
| 审计工作台 | ✅ 完成 | Costs override、统一 Constraint Registry、deterministic precheck 与 Costs/Constraints 视图 |
| Phase 3 | ✅ 完成 | Full Integrated Fixed-column Oracle、x/y/z/w 联合 MIP、五类 linking、统一目标与独立审计 |
| Phase 4 | ✅ 完成 | Direct disruption seed、fixed-point Scope closure、Scope 外原计划冻结、Full-vs-Scope Oracle |
| Phase 5 | ✅ 完成 | Existing-option Flight Network、Turn Time、Aircraft String 全量生成、brute-force Oracle |
| Phase 6 | ✅ 完成 | Crew-local Network、OPERATE/DEADHEAD、Crew Pairing 显式生成、brute-force Oracle |
| Phase 7 | ✅ 完成 | Passenger-local Network、MCT、TRANSPORTED/UNSERVED Itinerary 显式生成、brute-force Oracle |
| Phase 8 | ✅ 完成 | Logic-based Fixed-column Benders、exact-schedule cuts、LB/UB 与 Integrated audit |
| Phase 9 | ✅ 完成 | Fixed-schedule Aircraft String Full LP、Phase I/II Column Generation、DAG Pricing、穷举终止审计 |
| Phase 10 | ✅ 完成 | Fixed-schedule Crew Pairing All-Pairings LP、Phase I/II Column Generation、OPERATE/DEADHEAD Pricing |
| Phase 11 | ✅ 完成 | Schedule Benders + Aircraft/Crew CG、certified LP cuts、binary incumbent、Integrated audit |
| Phase 12 | ✅ 完成 | Aircraft/Crew exact Branch-and-Price、typed branching、Schedule exact-recourse cuts |
| Phase 13 | ✅ 完成 | 稳定 Solve API、独立复算的 RecoveredResult、Recovery 对比视图与 JSON 导出 |
| Business Migration | 📌 后续 | 真实航司数据映射、业务规则扩展、规模与性能工程；不属于新增核心算法 Phase |

Phase 1 证明数据、候选列和人工 Oracle 在当前规则下语义一致；它不证明 AIR 恢复目标的数学全局最优性。

Phase 3 已将 Schedule、Aircraft、Crew、Passenger 的 `x/y/z/w` 放入同一 MIP，以显式 linking constraints 取代 Phase 2 的外生 schedule handoff。`phase1_benchmark_001` 的 Manual Reference 通过完整联合审计，Integrated optimum 为 `18080`，与该候选上界相等；`toy_case_004/005` 分别验证 Aircraft 与 Passenger 对 schedule choice 的反向耦合。

Phase 4 在完整 fixed-column universe 上从受支持的直接 departure disruption 自动构造确定性 fixed-point scope。Scope 内 owner 保持自由，Scope 外 Flight / Aircraft / Crew / Passenger owner 通过语义解析固定到唯一原计划 candidate；完整 Phase 3 约束和变量均保留。`toy_case_006_scope` 的 Full 与 Scope objective 均为 `2040`，自由 binary candidates 从 `14` 降至 `10`。主 benchmark 的严格共享耦合闭包会安全扩展为 Full Scope，因此用于验证无遗漏，而不作为缩减样例。

Phase 5 使用已有 Flight Options 建立 aircraft-local DAG，并通过显式 Turn Time profile、Station/Timing/Horizon/Curfew/Equipment/Maintenance/Terminal 规则执行 DFS 全量枚举。`toy_case_007_string_generator` 与独立全排列 Oracle 的合法路径集合完全一致；主 benchmark 从 11 条人工 Aircraft Strings 扩展为 77 条生成 Strings，覆盖全部人工关键列，Integrated optimum 保持 `18080`。

Phase 6 使用最新候选宇宙重建 Scope 后，以 existing revenue `OPERATE` Flight Options 建立 crew-local DAG，并执行 **full explicit enumeration within the Phase 6 v1 generation profile**。每个 option 可形成 OPERATE 或 DEADHEAD leg；仅 OPERATE 检查现有 `Crew.rating`，DEADHEAD 不计 operating coverage。`toy_case_008_crew_pairing_generator` 的 DFS 与独立 brute-force 集合一致；主 benchmark 生成 374 条 Pairings，覆盖 10/10 人工关键列，再次重建 Scope 后 Full 与 Scope-limited Integrated objective 均为 `18080`。

Phase 7 使用 existing revenue Flight Options 建立 passenger-local DAG，并执行 **full explicit enumeration within the Phase 7 v1 generation profile**。Generator 处理 O-D、时间、MCT、Recovery Horizon、最大航段数、Original 与显式 UNSERVED；seat capacity 仍由 PRM/Integrated Oracle 统一处理。`toy_case_009` 的 Smart 与 brute-force 集合一致；主 benchmark 生成 55 条 Itineraries，覆盖人工候选 17/17，PRM objective 保持 `18000`，Full 与 Scope-limited Integrated objective 均保持 `18080`。

Phase 8 在固定候选宇宙上复用 SRM/ARM/CRM/PRM，实现 correctness-first Logic-Based Benders。binary recourse 采用 exact schedule no-good feasibility cuts 与 owner-specific conditional exact-recourse cuts，不冒充 classical LP-dual Benders。`toy_case_010` 在 4 轮收敛到 `220`；主 benchmark 在 8 轮、17 个 unique cuts 后达到 `LB = UB = Integrated Oracle = 18080`，最终 Integrated diagnostics 全通过。

Phase 9 在固定 Schedule 下实现独立 Aircraft String LP Column Generation。Full-column LP 保留现有 ARM selection、coverage、terminal 与 maintenance 行语义；RMP 每轮重建，Phase I 使用显式人工变量恢复可行性，Phase II 使用 aircraft reassignment/ferry owner cost。正式 DAG pricer 只读取 Flight Options、dual 与当前列，不调用 Phase 5 全量枚举；Phase 5 full pool 仅用于独立 Oracle/audit。`toy_case_011` 从目标 `300` 的 ferry 列改进到 `0`，主 benchmark 使用 77 条 full strings 对拍，CG 仅保留 15 条列且满足 `OBJ_CG_LP = OBJ_FULL_COLUMN_LP = 0`。

Phase 10 在固定 Schedule 下实现独立 Crew Pairing LP Column Generation。All-Pairings LP 保留 CRM 的 pairing selection、required OPERATE coverage、nonrequired OPERATE/DEADHEAD prohibition 与 terminal rows；typed-DAG pricer 区分 OPERATE/DEADHEAD，并执行 qualification、MCT、duty、deadhead 与 duplicate resource checks。`toy_case_012` 从目标 `300` 的长航段 deadhead 池改进到 `150`；主 benchmark 的 374 条 full pairings 与 34 条 CG pairings 均得到目标 `0`，340 条遗漏列最小 reduced cost 为 `0`。

Phase 11 将 SRM Schedule Master 与 Phase 9/10 CG 组合，但不复用 Phase 8 固定列 cuts。Aircraft/Crew 仅以 pricing-certified full-LP objective 生成下界 cut；CG 返回列上的 binary ARM/CRM 只形成安全 incumbent 上界，Passenger 继续使用 exact PRM。`toy_case_013` 依次访问 Aircraft infeasible、Passenger 高成本与 integrated-optimal 三个 Schedule，并收敛到 `LB = UB = 220`；主 benchmark 在 8 个 Master 轮次后达到 `LB = UB = Full Explicit Integrated Oracle = 18080`。正式入口拒绝预生成 Aircraft/Crew 全列与动态 Scope，无法闭合 LP/整数 gap 时返回 `INTEGRALITY_REQUIRED`。

Phase 12 在每个 branch node 内重新完成受分支约束的 CG：Aircraft 优先按 tail-option assignment 分支并以 exact String 为兜底；Crew 优先按 crew-local typed follow-on 分支，再以 typed leg / exact Pairing 兜底。`toy_case_015` 的 Crew root LP 为 `195`、整数最优为 `200`，B&P 以 9 个节点闭合；`toy_case_016` 上 Phase 11 返回 `INTEGRALITY_REQUIRED (LB=95195, UB=95200)`，Phase 12 通过 exact schedule recourse cut 达到 `LB = UB = Full Explicit Integrated Oracle = 95200`。主 benchmark 保持 `18080`。Passenger 仍为固定显式 Itinerary exact MIP，v1 仍只支持 `scope=None`。

Phase 13 将 Phase 12 exact solver 接入版本化 `POST /api/solve`。输入必须是完整 Solve Bundle（Scenario、已有 Flight Options、显式 Passenger Itineraries、座位容量、成本与算法 profile）；`POST /api/solve/precheck` 只判断输入就绪，不承诺优化可行。结果使用 `RecoveredResult` 独立复算选择、覆盖、目标分量与指标，提供 Original / Disrupted / Recovered / Difference 对比、诊断及 JSON 导出。API 回归：主 benchmark `18080`、`toy_case_016` `95200`，并覆盖 invalid / infeasible / not_converged。正式求解不调用 Aircraft/Crew full enumerators，仅支持 `scope=None`，且不生成新的 Flight Options。**Core AIR reproduction / research workbench v1 complete**；这不等于真实航司生产就绪。

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

Workbench v1.1 的 Example selector 由后端目录与可用求解 fixtures 驱动，并按 `Solve-ready examples` / `Scenario-only examples` 分组。`phase1_benchmark_001` 与 `toy_case_016_benders_branch_and_price` 必须保持 solve-ready；其他案例只有在 Scenario、Recovery Columns、Passenger Capacity 和当前算法 profile 能组成通过 precheck 的完整 Solve Bundle 时才进入 solve-ready 组，否则作为 scenario-only 展示。

点击 `Solve` 调用同步 exact solver，并在 `Recovery` 中查看四种对比及导出结果。一次 Solve 会锁定输入操作、显示 elapsed time，并将返回结果绑定到启动时的输入 revision；输入已变化的旧结果会被丢弃。`Reset Changes` 恢复当前 case 的加载基线（包括该 case 自带的成本 override），`Reload Example` 则从服务端重新读取所选示例。

Import 支持 Scenario JSON、完整 Solve Bundle JSON 和 `workbench_snapshot_v1`。导入 Scenario JSON 时保持 Scenario-only 语义，不会根据同名仓库 fixture 静默补齐为 Solve Bundle；需要求解时应显式选择 solve-ready Example 或导入完整 Solve Bundle。Export Snapshot 提供对应可再导入的工作台快照。程序化调用可先 `GET /api/solve/examples` 获取目录，再取 `GET /api/solve/example-bundle/{case_id}` 并送至 `POST /api/solve/precheck` / `POST /api/solve`。

---

# Workbench 视图与边界

页面提供五个一级视图：

```text
Data
Visualization
Recovery
Costs
Constraints
```

Costs 读取后端提供的 canonical `phase2_test_costs_v1`，可在浏览器内设置非负有限数值 override，并分别显示 Baseline 与 Effective。Override 只覆盖 coefficient 的 `value`，不修改 owner、unit、source 或 source reference，也不会写回 canonical JSON。

Constraints 从后端统一 registry 展示当前 SRM / ARM / CRM / PRM 的 20 个真实约束 ID、公式摘要、来源、assumption 和相关输入。`Run Precheck` 只执行确定性输入检查：

```text
PRECHECK != MIP FEASIBILITY
```

它不会调用 solver，也不承担 Phase 3 Integrated Oracle 的求解或验收。PRM 页面中的容量为只读的 `TEST / RESIDUAL CAPACITY`，不是 aircraft physical capacity。

`Export Scenario`、`Export Solve Bundle` 与 `Export Snapshot` 分别导出对应层级；Snapshot 可再导入，并保留 Scenario / Solve Bundle / cost overrides 工作台状态。

工作台的 `Load Case` 会把当前 case 的 Scenario、Recovery Columns、Passenger Capacity 与成本覆盖一并应用。Constraints 和 Capacity 不会再回退显示 benchmark 数据；导入或加载 Scenario-only case 时会清空不匹配的输入并明确降级。

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
- Import Scenario；
- Export Scenario；
- Export Workbench Config；
- Validate。

人工编辑后的 Scenario 保存在当前浏览器页面内存状态中。

---

# Visualization

同一工作台提供五个一级视图：

```text
Data
Visualization
Recovery
Costs
Constraints
```

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

求解后的恢复方案已在独立的 Recovery 视图中提供；本节的 Visualization 仍只表示输入暴露与传播风险，不把风险标记当成优化动作。

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

Phase 2 fixed-column test cost contract 已覆盖 SRM 的 delay、cancellation、route-change
成本，以及 ARM 的 aircraft reassignment、ferry 成本；这些系数使用
`abstract_cost_units`，用于可审计的模型测试，不代表真实航空公司的生产成本。
CRM 的 crew reassignment、deadhead 成本与 PRM 的 passenger delay、unserved passenger
成本也已分别进入独立固定列模型；这一段记录 Phase 2 时的状态。Phase 3 起已实现完整 SRM/ARM/CRM/PRM 联合目标。

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
├── capacities/
│   ├── phase2_test_seat_capacity_v1.json
│   └── toy_case_003_capacity.json
├── examples/
│   ├── toy_case_001.json
│   ├── toy_case_003.json
│   └── phase1_benchmark_001.json
├── columns/
│   ├── phase1_benchmark_001_columns.json
│   └── toy_case_003_columns.json
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
GET  /api/solve/examples
POST /api/validate
POST /api/solve/precheck
POST /api/solve
GET  /api/solve/example-bundle/{case_id}
```

其中：

- `/api/validate`：执行 Scenario 结构与跨实体一致性校验；
- `/api/solve/precheck`：检查完整 Solve Bundle 的输入就绪状态，不判断数学可行性；
- `/api/solve`：调用 Phase 12 exact solver，返回版本化、独立审计的 `RecoveredResult`；
- `/api/solve/examples`：返回前端 case selector 的示例元数据；
- `/api/solve/example-bundle/{case_id}`：提供显式演示输入。健康检查标明 `solver_enabled=true`、`production_ready=false`、`scope_mode=full_only`、`flight_option_generation=false`。

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

# Phase 4 Scope Limiting

核心入口：

```text
backend/core/scope.py
build_recovery_scope(...)
solve_integrated_fixed_column_oracle(..., scope=scope)
```

当前 Scope 仅对已验证的 fixed Recovery Columns 保证闭包；传播包含 resource candidates、passenger itineraries、airport capacity rows、gate checkpoints 与 shared seat usage。`scope=None` 继续执行原 Phase 3 Full Oracle。

---

# Phase 5 Flight String Generator

核心入口：

```text
backend/core/flight_network.py
backend/core/string_generator.py
data/config/phase5_test_string_generation_v1.json
```

Phase 5 只从 existing Flight Options 生成显式 Aircraft Strings，并通过独立 legality validator 与小规模 brute-force permutation oracle 验收。它不是 Pricing 或 Column Generation，不生成新的 Flight Options。

---

# Phase 6 Crew Pairing Generator

核心入口：

```text
backend/config/pairing_generation.py
backend/core/crew_network.py
backend/core/pairing_generator.py
data/config/phase6_test_crew_pairing_generation_v1.json
```

Phase 6 v1 只生成单 duty 的显式 Pairings，检查 ownership、qualification、Station/Timing、版本化 Min Connection、Duty Time、Recovery Horizon、Terminal、Original/Idle 与 DEADHEAD 规则。它不生成 Flight Options，不实现真实 FAR/CCAR duty/rest 全集，也不进入 Pricing、Reduced Cost、Column Generation 或 Benders。

任何 Aircraft String、Crew Pairing 或 Passenger Itinerary 候选宇宙变化后，必须先针对新 `RecoveryColumns` 重新调用 `build_recovery_scope(...)`，禁止沿用旧 Scope。

---

# Phase 7 Passenger Itinerary Generator

核心入口：

```text
backend/config/itinerary_generation.py
backend/core/passenger_network.py
backend/core/itinerary_generator.py
data/config/phase7_test_itinerary_generation_v1.json
```

Phase 7 v1 只从已有 revenue OPERATE Flight Options 生成 FLIGHT-only transported paths，并为每个 Passenger Group 生成显式 UNSERVED candidate。它检查 passenger ownership、O-D/时间连续性、版本化 MCT、Recovery Horizon、最大航段数、重复 option/base flight、arrival/delay、original 与 Scope；不以 seat capacity 做局部剪枝，也不生成 SURFACE 或新 Flight Options。

---

# Phase 8 Fixed-Column Benders

核心入口：

```text
backend/config/benders.py
backend/core/benders.py
data/config/phase8_test_benders_v1.json
```

Phase 8 v1 以 SRM `x` 为 Master，并使用现有 ARM/CRM/PRM binary MIP 作为 exact recourse。可行性 cut 仅排除一个 canonical schedule；最优性 cut 只在被访问 schedule 上令 `theta` tight，Big-M 从当前 scope-restricted owner candidates 计算。每次求解冻结 candidate universe，并以现有 Integrated diagnostics 独立复算最终 `x/y/z/w`、linking、scope 与 objective。

---

# 后续：Business Migration

核心复现路线图已冻结。下一条独立工程路线是：

```text
M1 — 真实航司数据映射
Flight Option generation / screening
成本标定与航司特定运行规则
大规模 runtime / stability 与业务运行验证
```

研究工作台 v1 的核心复现链路已经闭合。下一步不再扩展本轮数学模型，而是先验证真实数据的字段映射、Flight Option 来源、运行时限、业务规则与结果解释；当前 API 和 UI 明确标记 `production_ready=false`。

完整开发路线见：

```text
docs/AIR_HTML_Python_Reproduction_Plan.md
```

论文内容与实现补充的区别见：

```text
assumptions.md
reproduction_notes.md
```
