# Phase 1 中等规模验证数据设计：`phase1_benchmark_001`

## 1. 定位

本案例用于 `docs/AIR_HTML_Python_Reproduction_Plan.md` 的 **Phase 1：人工建立标准 Toy Case + Expected Solution**。

建议保留现有 `toy_case_001.json` 作为最小 smoke test，不替换。

新增：

```text
data/examples/phase1_benchmark_001.json
data/expected/phase1_benchmark_001_expected.json
```

现有 `toy_case_002` / `toy_case_003` 名称继续留给开发计划后面定义的“必须取消”和“旅客容量冲突”回归案例，避免语义冲突。

---

## 2. 数据规模

| 对象 | 数量 | 设计目的 |
|---|---:|---|
| Airport | 4 | A/B/C/D，足以形成多个 OD，又可人工画图 |
| Flight | 12 | 4 架飞机 × 每架 3 段 |
| Aircraft | 4 | 其中 AC4 有 maintenance 要求 |
| Equipment type | 1 | 只用 E1，避免过早引入机型替代复杂度 |
| Crew | 5 | 包含跨 aircraft 的 crew connection |
| Passenger groups | 8 | 单段和两段联程都有 |
| Airport capacity interval | 4 | B 为核心受扰容量桶，其余机场用于完整展示 |
| Disruption | 1 | B 机场出港容量下降 |
| Recovery window | 8 h | 08:00–16:00 UTC |

该规模比当前 3 airport / 6 flight toy case 明显丰富，但仍可以人工逐条检查。

---

# 3. 核心结构

## 3.1 Aircraft rotations

```text
AC1: F1 A→B → F2 B→C → F3 C→A
AC2: F4 C→B → F5 B→D → F6 D→C
AC3: F7 D→B → F8 B→A → F9 A→D
AC4: F10 C→A → F11 A→D → F12 D→C
```

AC4：

```text
maintenance_required = true
maintenance_stations = [C]
```

且原 rotation 最终回到 C。

---

## 3.2 Crew pairings

```text
C1: F1 → F2 → F10
C2: F4 → F5 → F6
C3: F7 → F8 → F9
C4: F3 → F11
C5: F12
```

最关键的是：

```text
F2 属于 AC1
F10 属于 AC4
但二者都由 C1 连续执行
```

因此 F2 的实际延误可以通过 **crew connection** 传播到另一架飞机 AC4。

同样：

```text
F3 属于 AC1
F11 属于 AC4
但由 C4 连续执行
```

这让案例真正包含 integrated recovery 的资源耦合，而不是 4 条互不相关的数据表。

---

# 4. 扰动设计

B 机场：

```text
09:30–10:30 UTC
departure_capacity_reduction
actual dep_capacity = 2
```

原计划在 `[09:30, 10:30)` 内共有：

```text
F2 09:40 B→C
F5 09:50 B→D
F8 10:00 B→A
```

即：

```text
3 departures / capacity 2
```

至少 1 个航班必须离开该容量桶。

---

# 5. 为什么参考解选择 F2 延误

三个直接受扰航班均设置为：

```text
strategic_flag = true
```

目的：这个 Phase 1 benchmark 主要验证 **delay + propagation**，不希望第一标准案例先被 cancellation 分支干扰。

最大允许延误：

```text
F2 max_delay = 60
F5 max_delay = 20
F8 max_delay = 20
```

要离开 `[09:30, 10:30)`：

```text
departure >= 10:30
```

因此：

```text
F5 最晚 10:10 → 仍在容量桶
F8 最晚 10:20 → 仍在容量桶
F2 可以 10:30 → 可以离开容量桶
```

所以在“所有战略航班继续执行、且不取消”的 Phase 1 behavioral oracle 下：

```text
F2 必须至少延误 50 min
```

这比依靠任意 cost coefficient 来决定“延误谁”更适合作为人工测试基准。

---

# 6. 预期传播链

## Step 1：直接容量冲突

```text
B capacity
3 / 2
↓
F2 +50 min
```

恢复后：

```text
F2
09:40 → 10:30 departure
10:40 → 11:30 arrival
```

---

## Step 2：Aircraft propagation

AC1：

```text
F1 → F2 → F3
```

F3 原计划：

```text
11:00 C→A
```

但延误后的 F2：

```text
11:30 才到 C
```

因此：

```text
F3 至少 +30 min
```

恢复：

```text
11:30–12:30
```

---

## Step 3：Crew propagation 到另一架飞机

C1：

```text
F1 → F2 → F10
```

F10 属于 AC4，原计划：

```text
11:10 C→A
```

C1 随 F2 到 11:30 才到 C，因此：

```text
F10 至少 +20 min
```

恢复：

```text
11:30–12:30
```

这一步是本案例最重要的设计点：

```text
airport disruption
→ F2
→ crew C1
→ F10
→ another aircraft AC4
```

---

## Step 4：F11 再受 AC4 + Crew C4 双重约束

F11：

```text
12:20 A→D
```

但恢复后的：

```text
F10 到 A = 12:30  （同 aircraft AC4）
F3  到 A = 12:30  （crew C4 的上一航班）
```

因此 F11 同时被：

```text
Aircraft AC4
Crew C4
```

约束，至少：

```text
F11 +10 min
```

恢复：

```text
12:30–13:30
```

F12 原计划 13:40 从 D 起飞，仍然可执行，所以传播在这里停止。

---

# 7. 最小延误无取消参考解

| Flight | Delay |
|---|---:|
| F1 | 0 |
| **F2** | **50 min** |
| **F3** | **30 min** |
| F4 | 0 |
| F5 | 0 |
| F6 | 0 |
| F7 | 0 |
| F8 | 0 |
| F9 | 0 |
| **F10** | **20 min** |
| **F11** | **10 min** |
| F12 | 0 |

总 flight delay：

```text
110 min
```

注意：

**110 min 目前只是这个 behavioral reference 的总延误，不是 AIR objective。**

在 SRM/ARM/CRM/PRM 具体 cost coefficients 写入代码之前：

```json
"expected_objective": null
```

不要写一个虚假的目标函数值。

---

# 8. Passenger groups

```text
P1  30 pax: F1 → F2
P2  24 pax: F4 → F5
P3  20 pax: F7 → F8
P4  15 pax: F2 → F3
P5  18 pax: F3 → F11
P6  12 pax: F10 → F11
P7  25 pax: F9
P8  16 pax: F12
```

参考 arrival delay：

| Group | Arrival delay |
|---|---:|
| P1 | 50 |
| P2 | 0 |
| P3 | 0 |
| P4 | 30 |
| P5 | 10 |
| P6 | 10 |
| P7 | 0 |
| P8 | 0 |

当前 Schema 没有 minimum connection time 字段。

因此 Phase 1 参考解只按当前项目已有的时间不重叠语义处理：

```text
previous arrival <= next departure
```

例如恢复后：

```text
P4:
F2 arrive C 11:30
F3 depart C 11:30
```

在当前验证语义下合法。

未来如果增加 MCT，必须新建独立测试案例，不要偷偷改变这个 benchmark 的 oracle。

---

# 9. 为什么只用一个 Equipment Type

本案例全部：

```text
E1
```

原因：

Phase 1 的目标是先验证：

```text
airport capacity
→ flight delay
→ aircraft propagation
→ crew propagation
→ passenger propagation
```

如果同时加入：

```text
E1/E2 substitution
fleet incompatibility
multiple crew ratings
```

人工枚举 flight strings / pairings 会明显复杂化。

机型替代应放到后续独立 case。

---

# 10. 为什么加入一架 Maintenance aircraft

AC4：

```text
maintenance_required = true
maintenance_stations = [C]
required_station_at_T_end = C
```

目的：

在不增加第二种机型的情况下，为后续 ARM 提供一个最简单的 maintenance-compatible string 验证点。

当前参考 rotation：

```text
C → A → D → C
```

天然满足回 C 的要求。

---

# 11. 与现有 toy_case_001 的关系

不要删除或覆盖：

```text
toy_case_001.json
```

建议测试分层：

```text
toy_case_001
    ↓
最小 smoke test
3 airports / 6 flights

phase1_benchmark_001
    ↓
中等规模人工 oracle
4 airports / 12 flights
cross-aircraft crew propagation
maintenance
8 passenger groups
```

后续开发计划中：

```text
toy_case_002 = 必须取消
toy_case_003 = 旅客容量冲突
```

继续保留原语义。

---

# 12. Phase 1 手工列建议

当前仓库尚未定义正式的：

```text
FlightString Schema
CrewPairing candidate Schema
Passenger alternative-itinerary Schema
```

因此本次**不要提前发明 `columns.json` 格式**。

正确顺序：

1. 先把 `phase1_benchmark_001.json` 加入仓库；
2. `/api/validate` 必须通过；
3. 确认 Phase 1 candidate-column 数据结构；
4. 再基于本案例人工建立：
   - 约 8–15 个 Flight Strings；
   - 约 8–15 个 Crew Pairings；
   - Passenger 原 itinerary + 少量明确 alternative itineraries；
5. 最后写入 `phase1_benchmark_001_columns.json`。

这样不会因为“为了先有一个 JSON”而提前锁死后续 OR 列的数据结构。

---

# 13. Phase 1 人工验收要点

## Scenario

- [ ] 4 airports
- [ ] 12 flights
- [ ] 4 aircraft
- [ ] 5 crew
- [ ] 8 passenger groups
- [ ] 1 disruption
- [ ] `/api/validate` PASS

## Original schedule

- [ ] 所有 aircraft rotation 机场连续
- [ ] 所有 aircraft rotation 时间不重叠
- [ ] 所有 crew pairing 机场连续
- [ ] 所有 crew pairing 时间不重叠
- [ ] 所有 passenger itinerary OD 连续

## Disruption

- [ ] F2/F5/F8 位于 B `[09:30,10:30)` 出港容量桶
- [ ] 原计划 departures = 3
- [ ] dep_capacity = 2
- [ ] F5/F8 max_delay=20，无法移出容量桶
- [ ] F2 max_delay=60，可通过 +50 移出容量桶

## Behavioral oracle

- [ ] F2 = +50
- [ ] F3 = +30 via AC1
- [ ] F10 = +20 via C1
- [ ] F11 = +10 via AC4 + C4
- [ ] F12 不需要继续延误
- [ ] cancellation = 0
- [ ] AC4 最终回 C，满足 maintenance station

## Passenger

- [ ] P1 arrival +50
- [ ] P4 arrival +30
- [ ] P5 arrival +10
- [ ] P6 arrival +10
- [ ] 其余 reference arrival delay = 0
- [ ] 不把 exposed flight 自动等同于 actual passenger delay

---

# 14. Codex 添加此案例时的要求

建议给 Codex 的任务：

```text
保留 data/examples/toy_case_001.json 不变。

新增：
- data/examples/phase1_benchmark_001.json
- data/expected/phase1_benchmark_001_expected.json

更新 docs/AIR_HTML_Python_Reproduction_Plan.md 的 Phase 1：
说明 toy_case_001 是最小 smoke test，
phase1_benchmark_001 是中等规模人工 integration oracle。

为 phase1_benchmark_001 添加 regression/schema validation test。

当前不要：
- 实现 solver；
- 自动生成 Flight Strings；
- 自动生成 Crew Pairings；
- 定义新的 objective cost；
- 把 expected_objective 猜成数值；
- 修改 toy_case_002 / toy_case_003 的既定用途。
```

---

# 15. 本案例要验证的核心链

最终人工能够明确解释：

```text
B airport departure capacity reduction
        ↓
F2 forced +50
        ├───────────────┐
        ↓               ↓
Aircraft AC1         Crew C1
        ↓               ↓
F3 +30             F10 +20
        ↓               ↓
Crew C4            Aircraft AC4
        └──────┬────────┘
               ↓
            F11 +10
               ↓
           F12 unchanged
```

这是一个适合作为 Phase 1 中等 benchmark 的规模：

**已经能体现 integrated recovery，但仍然可以拿纸笔完整核对。**
