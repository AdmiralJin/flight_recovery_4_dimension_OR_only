# AIR 验证与压力数据套件

本目录由 `python scripts/generate_validation_suite.py` 确定性生成。
语义源由生成器和固定种子维护，`frozen/` 下的 JSON 是供当前 HTML 直接导入的适配产物。

- `frozen/micro/`：20 个小规模、可解释案例；
- `frozen/stress/`：P1–P5 五档压力数据；
- `manifest.json`：导入类型、来源、规模、预期和 SHA-256；
- `expectations.json`：机器可读预期；
- `constraint_coverage.json`：20 项约束到案例的映射；
- `scale_profiles.json`：压力生成参数与目标时间带。
- `calibration_results.json`：参考机器的真实校准结果。

## 导入

`import_kind=scenario` 的文件使用 Scenario 导入入口；
`import_kind=solve_bundle` 的文件使用完整求解包导入入口。
HTML 契约变化后重新运行适配生成器即可，不应手工修改冻结文件。

## 边界

压力档的时间是参考机器目标带，不是跨机器承诺。P3–P5 通常需要完整求解器许可证；
生成器不会加入人工等待。未完成实机标定前，`calibration_status` 保持 `uncalibrated`。
