# Phase 2.4 Fixed-Column CRM Implementation Report

时间：2026-09-11 10:19:49（Asia/Shanghai）

## 1. Modified Files

- 新增 `backend/core/crm.py`、`backend/core/crew_incidence.py`。
- 扩展 `backend/config/costs.py` 与 `backend/config/__init__.py`，加入 CRM pure cost contract。
- 扩展 `backend/core/__init__.py` 导出 CRM contracts。
- 更新 `backend/core/recovery_handoff.py` 及 ARM regression 的 canonical schedule handoff（Phase 2.3 review fix）。
- 更新 `assumptions.md` A-040 至 A-046、test cost source reference、README 与 reproduction plan。
- 新增 CRM unit/regression tests 与 Phase 2.3 review-fix report。
- 未修改 HTML/Frontend、Columns schema、example columns 或人工 expected；现有 schema 已明确提供 pairing ownership、OPERATE/DEADHEAD、起终点和时空路径字段，无需扩展。

## 2. Paper (3.13)-(3.15) Mapping

已重新核对仓库论文第 10–11 页：

- `(3.13)` 原式包含 crew-pairing assignment、surplus crew deadhead 与 deadhead-to-base cost。当前固定列 objective 映射为可由现有数据证明的 crew reassignment 与 pairing 内 DEADHEAD minute cost；没有伪造独立 `nu_k`。
- `(3.14)` 原式为 pairing flight incidence 减 surplus crew `s_f`，保证非取消航班有人执行。当前项目缺岗位/人数合同，采用每个 required option 恰好一个 OPERATE crew-unit 的严格固定列映射；DEADHEAD 不计入覆盖。
- `(3.15)` 原式让每名 crew 选择 pairing 或 `nu_k` 回基地。当前 schema 没有独立 return-to-base variable，因此每名 crew 恰选一条显式 pairing；idle/回基地必须由显式列表达。

以上差异在 A-041/A-042/A-045 标记为 implementation mapping assumption，不声称变量结构与论文完全相同。

## 3. CRM Input Contract

新增不可变 `CrewRecoveryRequest(scenario_id, required_operated_option_ids)`。SRM 顺序流程统一通过 `extract_required_operated_option_ids` 构造；CRM 不解析 SRM diagnostics、不重新决定 delay/cancel/route。Unknown、CANCEL、FERRY、同 base flight 冲突与重复 ID 均 fail fast。

## 4. Crew Pairing Schema / Changes

复用现有 `CrewPairing`：`pairing_id`、`crew_id`、`duties/segments`、`start_station`、`end_station`、`cost_components`。`CrewSegmentType` 已明确区分 OPERATE、DEADHEAD、GROUND_TRANSFER、REST，因此没有 schema change，也没有按命名规则猜测业务语义。

## 5. Operating vs Deadhead Semantics

- 只有 OPERATE incidence 满足 required flight coverage。
- DEADHEAD 单独形成 incidence、diagnostics 和 cost，不能满足 coverage。
- fixed pairing 的 OPERATE/DEADHEAD flight segment 必须引用 revenue OPERATE option；CANCEL/FERRY 在建模前拒绝。
- selected pairing 的 DEADHEAD 只能引用 required schedule option；non-required alternate 由零泄漏约束禁止。

## 6. Constraint Mapping Table

| ID | 实现 | 来源分类 |
|---|---|---|
| CRM-C01-CREW-PAIRING-SELECTION | 每名 crew 恰选一个 fixed pairing | paper `(3.15)` + A-041 mapping |
| CRM-C02-FLIGHT-OPTION-COVERAGE | required option 的 OPERATE coverage = 1 | paper `(3.14)` + A-042 mapping |
| CRM-C03-NONREQUIRED-REVENUE-PROHIBITION | non-required OPERATE 与 DEADHEAD presence = 0 | implementation guard A-043 |
| CRM-C04-CREW-FEASIBILITY | 复用 semantic validator 的 ownership/rating/continuity/time/start-end/CANCEL checks | fixed-column validation A-044 |
| CRM-C05-TERMINAL-OR-OWNERSHIP | 每名 crew 的 terminal-compatible pairing selection = 1 | fixed-column validation + guard A-044 |

决策变量为每条人工 pairing 的 binary `z[pairing_id]`；未动态生成 pairing。

## 7. Cost Ownership

新增 side-effect-free `crew_pairing_cost` 和 immutable `CrewPairingCostBreakdown`：

- OPERATE leg 的 `base_flight.original_crew != pairing.crew_id` 计一次 crew reassignment；
- DEADHEAD leg 按 `block_minutes * deadhead_per_minute` 计费；
- 只使用 `FixedColumnCostConfig`，不读取 Columns `cost_components` 作为真源；
- CRM 不重复收取 SRM delay/cancel/route、ARM tail/ferry 或 PRM passenger costs。

## 8. New Assumptions

- A-040 CRM external schedule boundary。
- A-041 one explicit pairing per crew 与 `(3.15)` mapping。
- A-042 single crew-unit coverage 与 `(3.14)` mapping。
- A-043 OPERATE/DEADHEAD separation 和 schedule consistency。
- A-044 fixed-column legality/terminal trust。
- A-045 CRM reassignment/deadhead cost mapping。
- A-046 CRM single-model result boundary。

## 9. Unit / Negative / Infeasible Tests

`tests/unit/test_crm.py` 共 20 项，覆盖：一 crew/两 pairing 恰选一条、required coverage、deadhead-only 不覆盖、duplicate operating coverage infeasible、non-required operating/deadhead leakage、非零 cost audit、unknown/CANCEL/FERRY/conflicting request、duplicate/unknown crew/pairing/leg、cancel leg、illegal terminal、zero pairing、ferry transport rejection、incidence immutability 和 audit unknown ID。

聚焦 CRM/handoff/benchmark：30 passed，0 failed，0 skipped。

## 10. SRM → CRM Handoff Test

- 无取消：真实 benchmark SRM OPTIMAL → canonical extractor → CRM OPTIMAL。
- 有取消：构造 `F3 -> FO_F3_CANCEL` 的合法 SRM result，extractor 排除该 option；CRM 接受 request，随后因人工 fixed pairing shortage 返回 INFEASIBLE，而不是错误地要求 crew 覆盖取消航班。
- 三航班 unit contract 另验证 F1 OPERATE、F2 CANCEL、F3 delayed OPERATE 输出严格为 F1/F3，ARM/CRM request 均接受。

## 11. Benchmark Result

### SRM optimum schedule → CRM

- SRM objective：70.0。
- CRM status：OPTIMAL；CRM objective：0.0。
- selected：C1 `CP_C1_RECOVERY`、C2 `CP_C2_ORIGINAL`、C3 `CP_C3_ORIGINAL`、C4 `CP_C4_ORIGINAL`、C5 `CP_C5_ORIGINAL`。

### Manual Reference schedule → CRM

- CRM status：OPTIMAL；CRM objective：0.0。
- selected pairing map 与人工 reference 完全一致，包括 C4 `CP_C4_F3_ORIG_F11_D10`。
- 此结论只证明 CRM 子模型，不把 Manual Reference 声称为综合全局最优。

## 12. Coverage Audit

两个可行 benchmark 均满足：全部 required options operating coverage = 1；uncovered、duplicate operating、unexpected operating 均为空；constraint violation count = 0。Deadhead-only 与 duplicate-operating 构造例均正确返回 INFEASIBLE。

## 13. Deadhead Audit

Benchmark 没有 selected deadhead，minutes = 0。专门正例选择 60 分钟 deadhead 并保留独立 leg 记录；unselected alternate deadhead 被禁止；deadhead-only 无法覆盖 required option。

## 14. Crew Reassignment Audit

Benchmark reassignment count = 0，与 manual reference 一致。临时系数正例强制 C2 执行原属 C1 的航班，独立复算 count = 1、cost = 100.0。

## 15. Objective Audit

临时非零用例同时得到 reassignment 100.0、deadhead 120.0、total 220.0；Solver objective 与 pure-function audit 一致。每个有解结果均在返回前强制比较 solver objective 与独立复算，并要求所有 constraint checks satisfied。

## 16. Full Pytest Result

命令：`pytest -q`

结果：211 passed，0 failed，0 skipped；仅有 1 条既有 Starlette/httpx deprecation warning。

## 17. Gurobi Result

CRM regression：3 passed，0 failed，0 skipped。Gurobi version：13.0.3。CRM integration executed：yes。Regression helper 对 unavailable 直接 assert failure，不使用 skip。

## 18. Known Limitations

- Aggregate single crew-unit，不含 Captain/FO/Cabin role-specific complement。
- 无真实 maximum duty、minimum rest、roster-period、reserve crew 或完整航司 legality engine；信任已验证 fixed columns。
- 无论文独立 `nu_k` deadhead-to-base variable，也未显式建 `s_f` surplus integer；必须由固定 pairing 表达。
- deadhead per minute 是项目 test mapping，非论文公布的 per-flight/return-to-base monetary calibration。
- CRM OPTIMAL 不证明 aircraft/passenger/integrated recovery feasible。

## 19. Acceptance Checklist

- [x] 核对论文 `(3.13)-(3.15)` 并记录映射。
- [x] fixed Crew Pairings；无动态生成。
- [x] canonical handoff；cancel 不进入 coverage；CRM 不改 schedule。
- [x] OPERATE/DEADHEAD 分离；coverage/leakage 生效。
- [x] ownership、fixed legality、terminal 生效。
- [x] crew reassignment/deadhead canonical costs 有非零测试与独立 audit。
- [x] normal/negative/infeasible、SRM→CRM、manual benchmark 均通过。
- [x] full pytest 与不可跳过 Gurobi CRM integration 通过。
- [x] assumptions、cost source、README、reproduction plan 同步。
- [x] 未修改 Frontend；未进入 PRM、Integrated Oracle、Benders、CG。

## 20. Next Recommended Step

进入 Phase 2.5 Fixed-Column PRM：先冻结 passenger itinerary input、seat-capacity 与 unserved/delay cost mapping，再实现独立模型与 benchmark audit。

**Phase 2.4 PASS**
