# Phase 7 Final Review & Merge

## 1. Review Conclusion

**Phase 7 — Passenger Itinerary Generator: PASS，允许合并至 `main`。**

本阶段已完成 Passenger candidate universe 的显式自动生成，并保持 Phase 3–6 已冻结的模型、Schema 与 Integrated Oracle 接口稳定。

关键验收结果：

```text
Manual passenger semantic coverage = 17 / 17

Generated passenger itineraries = 55
  TRANSPORTED = 47
  UNSERVED = 8

PRM objective = 18000
PRM audit = PASS

Full Integrated objective = 18080
Scope-limited Integrated objective = 18080
Previous Phase 6 objective = 18080

Smart vs brute-force Oracle = PASS
Canonical Scope validation = PASS
Integrated local constraints = PASS
Integrated cross-model linking = PASS
Integrated objective recomputation = PASS

pytest = 353 passed
0 failed
0 skipped
compileall = PASS
Black = PASS
git diff --check = PASS
```

因此，自动生成的 Passenger Itineraries：

- 覆盖全部现有人工 Passenger semantic candidates；
- 未遗漏当前 integrated optimum 所需路径；
- 未通过非法新路径改变当前 integrated optimum；
- 能重新进入 PRM、Scope 与 Full Integrated Oracle；
- 已通过 independent validator 与 tiny brute-force Oracle；
- 未要求修改稳定的 `prm.py`、`integrated_oracle.py` 或 Recovery Columns Schema。

---

## 2. Accepted Phase 7 Boundary

以下内容属于已知且可接受的 Phase 7 v1 边界，不阻塞合并：

```text
Flight Options 仍为 existing options
Passenger Group 不拆分
自动 itinerary 仅生成 FLIGHT segment
SURFACE 不自动生成
真实机场/航站楼 MCT 未建模
Cabin / fare class / alliance / interline 未建模
Passenger Pricing / Reduced Cost 未实现
Column Generation 未实现
Benders 未实现
```

特别注意：

```text
phase7_test_itinerary_generation_v1:
default_mct_minutes = 0
```

该值仅用于兼容已冻结 benchmark 中存在的零间隔人工 itinerary，属于 test profile，不代表真实航司 MCT。

MCT 逻辑本身已通过 `toy_case_009` 的 30 分钟边界测试验证。

---

## 3. Merge 前最后检查

在 `feature/phase-7` 上执行：

```bash
git status
pytest -q
python -m compileall -q backend
git diff --check
```

要求：

```text
working tree clean
353 passed
0 failed
0 errors
```

同时确认以下 Phase 7 文件均已提交：

```text
backend/config/itinerary_generation.py
backend/core/passenger_network.py
backend/core/itinerary_generator.py

data/config/phase7_test_itinerary_generation_v1.json
data/examples/toy_case_009_passenger_itinerary_generator.json
data/columns/toy_case_009_passenger_itinerary_generator_columns.json

tests/unit/test_passenger_network.py
tests/unit/test_itinerary_generator.py
tests/regression/test_phase7_itinerary_generator_oracle.py
tests/regression/test_phase7_itinerary_generator_benchmark.py

docs/codex_reports/20260915_110101_phase7_passenger_itinerary_generator_report.md
```

并确认以下文档已把 Phase 7 标记为完成、下一阶段指向 Phase 8：

```text
README.md
docs/AIR_HTML_Python_Reproduction_Plan.md
assumptions.md
reproduction_notes.md
```

---

## 4. Merge

执行：

```bash
git switch main
git pull

git merge --no-ff feature/phase-7
```

若无冲突，再执行完整回归：

```bash
pytest -q
python -m compileall -q backend
git diff --check
```

要求 merge 后仍为：

```text
353 passed
0 failed
0 errors
```

随后：

```bash
git push origin main
```

确认 GitHub `main` 中已经存在 Phase 7 核心文件、测试、配置和实施报告后，可删除开发分支：

```bash
git branch -d feature/phase-7
git push origin --delete feature/phase-7
```

---

## 5. Phase 7 Freeze

合并后冻结以下 Phase 7 contract：

```text
Passenger-local revenue-flight network
Versioned MCT / max-leg profile
Deterministic DFS itinerary generation
Explicit UNSERVED candidate
Passenger itinerary semantic key
SHA-256 deterministic ID
Independent legality validator
Brute-force toy Oracle
Scope-aware generation
Out-of-scope original-only
Seat capacity remains global optimization logic
```

后续 Phase 8 不应为了实现 Benders 随意修改这些已验证语义。

若必须改变 Phase 7 contract，应新增独立 regression 并重新验证：

```text
Passenger Generator
→ PRM
→ Recovery Scope
→ Integrated Oracle
```

---

## 6. Phase 7 Closed

Phase 7 合并后项目状态应更新为：

```text
Phase 5  Aircraft String Generator       COMPLETE
Phase 6  Crew Pairing Generator          COMPLETE
Phase 7  Passenger Itinerary Generator   COMPLETE
```

下一阶段：

```text
Phase 8 — Fixed-Column Benders
```

Phase 8 第一核心验收标准：

```text
OBJ_Benders == OBJ_Integrated_Oracle
```

在 Fixed-Column Benders 与现有 Integrated Oracle 完全对齐之前，不进入 Column Generation。
