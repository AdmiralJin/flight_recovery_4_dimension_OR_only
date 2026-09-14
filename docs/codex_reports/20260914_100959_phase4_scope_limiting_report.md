# Phase 4 Scope Limiting 工作报告

- 时间：2026-09-14 10:09:59 +08:00
- 阶段：Phase 4 v1
- 最终决定：**Phase 4 PASS**

## 1. Paper Algorithms 3-6 Mapping

已直接检查仓库权威 PDF `An Optimization Approach to Airline Integrated Recovery.pdf` Appendix 第 30-31 页。

| Paper Algorithm | 本项目实现 | 状态 |
|---|---|---|
| Algorithm 3 Limiting Scope | `build_recovery_scope` 总控 monotone fixed-point closure | Paper-defined backbone + fixed-column extension |
| Algorithm 4 Routings | direct departure disruption seed；经 Aircraft String 扩展其候选 revenue flights | Paper mapping；当前以 fixed candidate strings 代替动态 routing extraction |
| Algorithm 5 Crew | scoped option 经 OPERATE/DEADHEAD Pairing 找 crew；scoped crew 的全部 pairings 反向扩展 flights | Paper mapping；fixed-column extension |
| Algorithm 6 Passenger Itineraries | scoped flight option 找 passenger groups；全部 candidate itineraries 扩展 additional flights/aircraft dependencies | Paper mapping；fixed itinerary universe 代替未实现的 eligible move-up generator |

为保持 Phase 3 MIP 可行域，另外传播 airport arrival/departure capacity row、aggregate gate checkpoint 与 shared seat usage。该部分不是论文伪代码的逐字实现，已登记 A-058/A-061。

## 2. Modified Files

核心实现：

- `backend/core/scope.py`
- `backend/core/integrated_oracle.py`
- `backend/core/__init__.py`

数据与测试：

- `data/examples/toy_case_006_scope.json`
- `data/columns/toy_case_006_scope_columns.json`
- `data/capacities/toy_case_006_scope_capacity.json`
- `tests/conftest.py`
- `tests/unit/test_scope.py`
- `tests/regression/test_phase4_scope_benchmark_001.py`

文档：

- `README.md`
- `assumptions.md`
- `reproduction_notes.md`
- `docs/AIR_HTML_Python_Reproduction_Plan.md`
- `docs/chatgpt_review/PHASE4_SCOPE_LIMITING_IMPLEMENTATION_PLAN.md`
- 本报告

## 3. Direct Disruption Seed

正式支持 `departure_capacity_reduction`。Seed 使用原计划 Flight：

```text
flight.origin == disruption.airport
and flight.sched_dep in [start_time, end_time)
```

多个 disruption 取并集并保持 Scenario flight ordering。未知 restriction type 抛出 `ScopeBuildError`，生产逻辑不包含 benchmark entity ID。

## 4. Scope Propagation / Fixed Point

`RecoveryScope` 为 frozen dataclass，所有集合以 input-index 顺序输出，reasons 以稳定顺序冻结。每轮传播：

1. Flight -> all options -> Aircraft/Crew/Passenger owners；
2. scoped Aircraft/Crew/Passenger -> all owned candidates -> additional revenue base flights；
3. shared arrival/departure capacity rows -> additional flights；
4. shared Gate checkpoints -> additional flights；
5. shared option seat usage -> additional passenger groups；
6. 直到四类 entity 集合不再增长。

`toy_case_006_scope` 两轮稳定；`phase1_benchmark_001` 三轮稳定。

## 5. Scope Safety Invariants

求解前检查：

- direct flights 全部属于 scope；
- scoped Aircraft Strings、Crew Pairings、Passenger Itineraries 引用的 revenue flights 全部闭包；
- entity/candidate IDs 均属于输入 universe；
- 每个 scoped entity/candidate 均有 propagation reason；
- caller-supplied scope 必须与 canonical deterministic closure 完全一致。

破坏闭包、未知 ID、缺少 reason 或非 canonical scope 均拒绝。

## 6. Original Candidate Resolver

不读取候选 ID 命名：

- Flight：OPERATE + 唯一 UNCHANGED + 原 route/times/block + zero delay；
- Aircraft：revenue options 顺序等于 `original_rotation` 的 original options；
- Crew：OPERATE options 顺序等于 `original_pairing` 的 original options；
- Passenger：FLIGHT options 顺序等于 `original_itinerary` 的 original options。

缺失或多于一个语义匹配均抛出 `ScopeBuildError`。

## 7. Scope Metrics

`toy_case_006_scope`：

```text
flights             2 / 3
aircraft            1 / 2
crew                1 / 2
passenger groups    1 / 2
free x/y/z/w        4 / 2 / 2 / 2
fixed x/y/z/w       1 / 1 / 1 / 1
free binary         10 / 14
free_binary_ratio   0.7142857143
scoped_flight_ratio 0.6666666667
iteration_count     2
```

`phase1_benchmark_001`：

```text
direct flights      F2, F5, F8
flights             12 / 12
aircraft            4 / 4
crew                5 / 5
passenger groups    8 / 8
free binary         59 / 59
iteration_count     3
```

主 benchmark 的 candidate/shared-row dependency graph 全连通，因此安全 closure 为 Full Scope；未通过遗漏 coupling 伪造缩减。

## 8. Full Oracle Result

```text
toy_case_006_scope       OPTIMAL  objective=2040
phase1_benchmark_001     OPTIMAL  objective=18080
```

## 9. Scope Oracle Result

```text
toy_case_006_scope       OPTIMAL  objective=2040
phase1_benchmark_001     OPTIMAL  objective=18080
```

两例均通过 local model audit、cross-model audit、scope-fix audit 与 independent objective recomputation。

## 10. OBJ_scope vs OBJ_full

使用项目统一 tolerance `1e-6`：

```text
toy_case_006_scope:      isclose(2040, 2040)   PASS
phase1_benchmark_001:    isclose(18080, 18080) PASS
```

不要求等价最优 assignment vector 完全一致。

## 11. Tests

新增 unit/negative/regression 覆盖 direct seed、multiple union、四类传播、shared capacity/seat、fixed point、determinism、unsupported type、semantic original uniqueness、broken closure、metrics、Scope freezing 及 Full-vs-Scope objective。

最终命令：

```text
python -m pytest
```

结果：

```text
293 passed
0 failed
0 skipped
1 StarletteDeprecationWarning (既有第三方兼容性告警)
```

## 12. New Assumptions

- A-058：论文 Algorithms 3-6 映射与 fixed-column safety extension；
- A-059：Scope 外 owner 冻结、保留完整 Phase 3 模型；
- A-060：semantic original candidate resolution；
- A-061：保守 shared-row closure 与主 benchmark connectivity。

## 13. Known Limitations

- 只对当前 validated fixed-column universe 保证；
- 不物理删除变量，缩减指标是 free candidates；
- 仅正式支持 departure capacity reduction seed；
- aggregate gate inventory 和 passenger capacity 继续沿用 Phase 2/3 provisional/test semantics；
- 主 benchmark 全连通，不能作为缩减案例；
- 尚未实现 eligible move-up generator、Flight String/Crew Pairing/Passenger Itinerary generators、Benders 或 Column Generation。

## 14. Acceptance Checklist

- [x] Paper Algorithms 3-6 已核对并映射
- [x] 独立 immutable Scope Engine
- [x] Direct seed 无硬编码 entity ID
- [x] Flight/Aircraft/Crew/Passenger fixed-point propagation
- [x] Capacity/Gate/Seat shared coupling closure
- [x] Deterministic propagation reasons
- [x] Scope safety invariants
- [x] Semantic unique original resolver
- [x] `scope=None` 保持 Phase 3 数学模型
- [x] Scope 外 decisions 固定到原计划
- [x] Scope audit、cross-model audit、objective audit PASS
- [x] `OBJ_scope == OBJ_full`
- [x] `toy_case_006_scope` 有实际缩减
- [x] Full pytest 0 failed / 0 skipped
- [x] Phase 3 regression 无回归
- [x] 文档同步
- [x] 未进入 generators/Benders/CG

## 15. Final Decision

```text
Phase 4 PASS
```

下一工程阶段：Phase 5 Flight String Generator。Phase 4 `RecoveryScope` 将作为 generator 的输入边界。
