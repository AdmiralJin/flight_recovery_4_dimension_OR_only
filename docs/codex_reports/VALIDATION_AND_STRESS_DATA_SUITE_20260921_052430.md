# 验证、演示与压力数据套件实施报告

时间：2026-09-21 05:24:30（Asia/Shanghai）

## 本次完成内容

1. 新增确定性数据生成模块 `backend/data_generation/validation_suite.py`，将语义案例、固定随机种子和当前 HTML 导入适配分离。
2. 新增命令 `python scripts/generate_validation_suite.py`，可重复生成全部冻结资产、SHA-256、预期结果、覆盖矩阵和说明文档。
3. 在 `data/validation_suite/frozen/micro/` 生成 20 个微型案例：
   - 复用已有 Scenario、Oracle toy case 和 Case catalog；
   - 分为 Scenario 与完整 Solve Bundle 两种导入类型；
   - 覆盖有效、未就绪、不可行、最优、容量/成本敏感性、Benders、列生成和 Branch-and-Price；
   - 20 项 SRM/ARM/CRM/PRM 约束均至少映射到一个案例。
4. 在 `data/validation_suite/frozen/stress/` 生成 P1–P5 五档压力数据：
   - P1：12 航班、22 航班候选、55 旅客行程；
   - P2：12 航班、36 航班候选、42 旅客行程；
   - P3：20 航班、60 航班候选、102 旅客行程；
   - P4：40 航班、160 航班候选、412 旅客行程；
   - P5：72 航班、360 航班候选、1764 旅客行程。
5. 压力生成器包含枢纽容量下降、航班延误/取消候选、飞机轮转、机组任务、直达/中转旅客、余座绑定、战略和市场航班以及维修终到要求。
6. 新增机器可读文件：
   - `manifest.json`；
   - `expectations.json`；
   - `constraint_coverage.json`；
   - `scale_profiles.json`；
   - `calibration_results.json`。
7. 新增人工材料：
   - `MICRO_CASE_CARDS.md`；
   - `CONSTRAINT_COVERAGE.md`；
   - `STRESS_PROFILES.md`；
   - `docs/user_guides/VALIDATION_DATA_GUIDE.md`。
8. README 已增加数据位置、生成方式、导入类型和校准边界说明。

## 接口处理原则

未把 25 个案例硬编码进正在修改的 HTML 页面或 Case selector。冻结文件直接遵守当前 Scenario / Solve Bundle 导入契约；以后页面包装结构变化时，只修改生成器的适配输出，不修改语义案例和随机种子。

## 实测结果

参考环境：Windows、Intel Core i7-12700H、15.7 GiB RAM、Gurobi 13.0.3 restricted size-limited non-production license。

- P1：本次代表性运行 1.308 秒，状态 `optimal`，目标值 18080，上下界相等，集成审计通过；此前探测约 1.5–1.7 秒。
- P2：70.074 秒预算后受控返回 `aborted`，`LB=120`、`UB=600`、终止原因为 `phase11_aborted`。该案例用于压力与终止行为，不冒充已完成最优演示。
- P3–P5：本次只完成确定性生成、Schema、语义和求解就绪性验证，没有运行数分钟至数小时的校准。
- P4–P5 在正式规模运行前需要匹配的非 size-limited 求解器许可证。

## 自动化验证

新增 `tests/unit/test_validation_data_suite.py`，覆盖：

- 20 个微型案例和 5 个压力案例数量；
- 20 项约束无遗漏；
- 冻结文件 SHA-256；
- Scenario 与 Solve Bundle 导入契约；
- 全部压力数据的 Schema、语义和 solve readiness；
- 固定种子生成确定性；
- P1 目标值 18080 和 integrated audit。

验证结果：

- 新增数据及相关 API/Validator 定向测试：28 项全部通过；
- 全量 `pytest -q`：全部通过；
- `python -m compileall -q backend/data_generation scripts`：通过。

测试仅出现既有 Starlette `httpx` 兼容性弃用警告，无失败。

## 使用入口

```bash
python scripts/generate_validation_suite.py
pytest tests/unit/test_validation_data_suite.py -q
```

导入前查看 `data/validation_suite/manifest.json` 的 `import_kind`；人工验证参考 `MICRO_CASE_CARDS.md`，压力边界参考 `STRESS_PROFILES.md` 和 `calibration_results.json`。
