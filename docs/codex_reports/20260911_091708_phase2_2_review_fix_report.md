# Phase 2.2 Review Fix 报告

- 时间：2026-09-11 09:17:08（Asia/Shanghai）
- 依据：`docs/chatgpt_review/PHASE2_2_REVIEW_FIX_AND_PHASE2_3_ARM_PLAN.md`

## 1. Review finding

原 Gate builder 同时采用 `[start,end)` 和 interval `end_time` checkpoint。在完整连续但 gate capacity 变化的 intervals 中，recovery terminal boundary 不属于任何普通半开区间，可能被误判为 capacity source 不明确。

## 2. Code changes

- internal boundary 继续严格使用右侧 interval；
- recovery end 新增为显式 terminal checkpoint；
- terminal checkpoint 优先使用唯一以 recovery end 结尾的 interval；
- 该 source 只用于 terminal inventory audit，不外推 interval 有效期；
- 对现有不完整 benchmark，只有机场全部已声明 gate capacities 相同时才允许原有 provisional fallback；
- 多个 terminal intervals 或 varying capacities 且无 terminal source 时 fail fast；
- `phase1_benchmark_001 + phase2_test_costs_v1` 固定回归目标 `objective == 70`。

## 3. Assumption changes

更新 A-029，没有创建重复 assumption。现已明确记录：

```text
internal boundary -> right interval
terminal boundary -> explicit terminal convention
```

规则继续标记为 `implementation_assumption + generated_provisional`。

## 4. Tests added

- `test_gate_internal_boundary_uses_next_interval`
- `test_gate_terminal_boundary_accepts_varying_capacities`
- `test_gate_terminal_boundary_rejects_ambiguous_capacity`
- SRM benchmark `objective == 70` regression assertion

覆盖连续 intervals、不同 gate capacity 和 `recovery_end == final interval.end_time`。

## 5. Full pytest result

```text
161 passed
0 failed
0 skipped
1 existing StarletteDeprecationWarning
```

## 6. Gurobi result

```text
available = true
integration actually executed = true
version = 13.0.3
SRM benchmark status = OPTIMAL
SRM benchmark objective = 70
```

## 7. Phase 2.2 final status

```text
Phase 2.2 FINAL PASS
```
