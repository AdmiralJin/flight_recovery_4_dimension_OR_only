# Phase 2.4 Review Fix Report

## 1. Review Finding

Phase 2.4 Fixed-Column CRM 代码与既有实现报告已经完成，但 `reproduction_notes.md` 仍错误地把 CRM 列为未实现，并把下一步写成 Phase 2.4。

## 2. reproduction_notes Changes

- 将当前子模型状态更新为 SRM + ARM + CRM；
- 将 CRM-owned crew reassignment / deadhead 标记为已实现的 Phase 2 test cost；
- 保留 PRM cost contract 已预留、PRM Model 尚未实现的边界；
- 将下一步更新为 Phase 2.5 Fixed-Column PRM；
- 重申全部成本为 `abstract_cost_units` / implementation test profile，而非生产成本。

## 3. Crew Reassignment Mapping Note

当前 crew reassignment 按 selected Crew Pairing 中、与 `base_flight.original_crew` 不同的 OPERATE flight leg 计数。该粒度是 Phase 2 implementation mapping；真实成本标定时仍需确认 crew / duty / pairing / flight-leg 的实际计费粒度。本次 review fix 未改变既有成本逻辑。

## 4. Test Result

- Command: `python -m pytest -q`
- Collected: 211
- Passed: 211
- Failed: 0
- Skipped: 0

## 5. Gurobi Integration Result

- Gurobi Python package/runtime version: 13.0.3
- Phase 2 Gurobi integration gate: executed
- CRM Gurobi benchmark regressions: executed
- Skip used: no

## 6. Phase 2.4 Final Status

`reproduction_notes.md` 已与代码、README、Phase 2.4 报告和真实测试状态同步。

**Phase 2.4 FINAL PASS**
