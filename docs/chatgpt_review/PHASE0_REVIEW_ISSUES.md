# Phase 0 Review Issues

## 结论
Phase 0：**PASS WITH MINOR FIXES**。完成以下收尾后，可进入 Phase 1。

## 必须修复

### 1. `minutes_between()` 精度问题
当前使用 `round()` 计算分钟数，可能把带秒时间误判为整数分钟并通过校验。

**建议：**
- 先检查时间差是否能被 60 秒整除；
- 再比较整数分钟数。

### 2. 明确机场容量语义
需在 `assumptions.md` 中固定 `AirportInterval` 的定义，包括：
- `dep_capacity` / `arr_capacity` 的时间单位；
- 容量作用于整个 interval，还是固定 time bucket；
- 时间区间边界建议统一为 `[start, end)`。

否则 Phase 1 无法唯一确定容量约束和人工标准答案。

## 建议修复

### 3. 增加 GitHub Actions CI
建议在 `push` / `pull_request` 时自动执行：

```bash
pip install -r requirements.txt
python -m pytest
```

### 4. 补一次前端完整闭环测试
至少人工验证一次：

`Load Example → Edit → Validate fail → Fix → Validate pass → Export → Import → Validate pass`

当前 API 测试不能替代浏览器端完整交互测试。

### 5. 检查 `.gitignore`
当前忽略 `docs/`，但仓库已跟踪 `docs`。建议删除该规则，或仅忽略明确不需要提交的文件。

## Phase 1 注意事项
当前 `data/expected/toy_case_001_expected.json` 只应作为 **Phase 0 数据校验 oracle**。

Phase 1 应单独增加用于 OR 验证的标准答案，例如：
- selected flight strings；
- aircraft / crew / passenger assignment；
- cancelled flights；
- delay；
- objective value；
- 关键约束 invariants。

不要把 Phase 0 的 expected 文件直接当作 Phase 1 optimization oracle。
