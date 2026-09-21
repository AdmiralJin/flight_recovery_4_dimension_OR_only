# 浏览器用户手册补充工作报告

- 时间：2026-09-20 13:18:04（Asia/Shanghai）
- 分支：`feature/air-workbench-data-ui-improvements`

## 完成内容

1. 新建 `docs/user_guides` 目录。
2. 新增面向使用者的 `AIR_WORKBENCH_BROWSER_USER_GUIDE.md`。
3. 手册详细说明：
   - 服务启动与浏览器访问；
   - Current Case 与顶部五类状态；
   - Case 加载、Scenario validation、Solve readiness、Solve 和 Recovery/Audit；
   - Data、Visualization、Recovery、Costs、Constraints 五个视图；
   - revision / STALE result 生命周期；
   - Reset、Import Scenario、Import Solve Bundle 和三个 Export 功能；
   - 八个可检验 Case 的位置、源数据、Expected、API 获取和文件导入方法；
   - 常见误区与问题处理。
4. 明确说明八个 Case 的统一入口为 `data/cases/catalog.json`，Case 由源 Scenario、Columns、Capacity 和 catalog override 动态组装，而不是八份重复目录。

## 代码影响

本次仅新增文档和工作报告，未修改应用代码、测试或验证数据，因此未重新运行完整测试集。
