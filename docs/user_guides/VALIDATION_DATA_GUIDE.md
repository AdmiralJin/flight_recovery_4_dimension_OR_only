# 验证与压力数据使用指南

## 1. 选择文件

先打开 `data/validation_suite/manifest.json`，按 `case_id` 查找案例：

- `import_kind: scenario`：只验证 Scenario、编辑和可视化，不具备求解条件；
- `import_kind: solve_bundle`：包含当前正式求解所需的候选、余座、成本和算法配置；
- `expected`：说明预期有效性、求解状态和已冻结的目标值；
- `sha256`：用于检查冻结文件是否被意外修改。

微型数据位于 `data/validation_suite/frozen/micro/`，压力数据位于
`data/validation_suite/frozen/stress/`。

## 2. 人工核验顺序

1. 导入文件并执行输入校验；
2. 核对页面显示的机场、航班、飞机、机组、旅客组和扰动数量；
3. 对照 `MICRO_CASE_CARDS.md` 检查该案例要触发的约束；
4. 完整求解包先检查求解就绪性，再运行求解；
5. 对照 `expectations.json` 检查状态、目标值和关键业务结果；
6. 不能把 Precheck 通过解释为优化一定可行，`micro-solve-ready-infeasible` 专门验证这条边界。

## 3. 推荐演示路径

领导现场演示优先使用 `P1-seconds.json`。它对应当前综合恢复基准，参考机器实测约
1.3–1.7 秒，目标值为 18080，并通过独立集成审计。

建议讲解顺序：

1. 原计划：12 个航班及其飞机、机组和旅客关系；
2. 扰动：机场离港容量下降；
3. 传播：直接受扰航班影响后续轮转和旅客；
4. 优化过程：8 个主问题轮次、7 个访问计划及动态生成资源列；
5. 结果：3 个航班延误、2 次飞机互换、1 个旅客组改签、无人未承运；
6. 审计：上下界均为 18080，Gap 为 0，集成审计通过。

`P2-tens-seconds.json` 当前用于受控终止压力验证：参考机器在 70 秒预算后得到
LB=120、UB=600，并以 `aborted` 正确结束。它不应被介绍为已完成最优求解的现场案例。

## 4. 压力测试规则

- P1 可进入普通回归测试；
- P2 使用固定预算验证进度、上下界和受控终止；
- P3 适合计划任务或夜间运行；
- P4、P5 需要正式、非 size-limited 求解器许可证后再校准；
- 每次记录 CPU、内存、求解器版本、许可证、运行时间、上下界、Gap、访问计划、生成列和分支节点；
- 不通过 sleep、前端动画或网络等待制造压力时长。

## 5. 重新生成和接口适配

运行：

```bash
python scripts/generate_validation_suite.py
pytest tests/unit/test_validation_data_suite.py -q
```

生成逻辑位于 `backend/data_generation/validation_suite.py`。语义案例、固定种子和规模配置是
稳定源；`frozen/` 下文件是当前 HTML 导入契约的适配输出。HTML 字段或包装结构变化时，
应调整生成器的输出适配，不应逐个手改冻结 JSON。
