# AIR Workbench 浏览器界面中文化报告

- 完成时间：2026-09-20 15:14:03（Asia/Shanghai）
- 工作分支：`feature/air-workbench-data-ui-improvements`
- 任务范围：将 AIR Workbench 浏览器中的用户可见文案科学、严谨地翻译为中文，并保留不宜直译的专业术语与专有名词。

## 完成内容

1. 中文化主页面、Case 选择器、工作流、操作栏、五个功能视图及页脚。
2. 中文化 Scenario 数据编辑器的分区、字段、表头、空状态、输入校验和无障碍标签。
3. 中文化可视化视图的模式、图例、航班详情、影响说明、容量热力图、提示与无障碍文本。
4. 中文化 Recovery 视图的结果摘要、航班/飞机/机组/旅客表格、排序、状态及算法诊断指标。
5. 中文化 Costs 视图的成本含义、单位、来源类型、说明、覆盖值校验和状态提示。
6. 中文化 Constraints 视图的约束名称、分类、实现状态、说明、预检查摘要、容量配置说明及导航。
7. 中文化 8 个内置可检验 Case 的展示名称、类别、说明和标签；Case ID、文件路径与期望结果结构保持不变。
8. 中文化请求失败、初始化、导入、重置、求解就绪性、过期结果等动态状态与错误提示。
9. 更新前端缓存版本标识为 `case-workbench-zh-20260920-1`。

## 术语处理原则

以下内容为避免歧义而保留英文或采用“中文 + 英文”形式：

- AIR、Case、Scenario、Solve、Recovery、Audit、Solve Bundle、Flight Option
- SRM、ARM、CRM、PRM、MIP、LP、LB、UB、Gap、Benders、Branch-and-Price（B&P）
- OPERATE、DEADHEAD、UTC、O-D、ID、JSON、Schema、API、MCT
- 数据字段名、约束 ID、公式、算法标识与接口内部状态值

## 主要修改文件

- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/api.js`
- `frontend/js/case-state.js`
- `frontend/js/tables.js`
- `frontend/js/results.js`
- `frontend/js/visualization.js`
- `frontend/js/recovery.js`
- `frontend/js/costs.js`
- `frontend/js/constraints.js`
- `data/cases/catalog.json`
- 相关 API 与前端自动化测试

## 验证结果

- 所有前端 JavaScript 文件均通过 `node --check`。
- `node --test tests/frontend/*.test.mjs`：19 项全部通过。
- `pytest -q`：全量测试全部通过。

本次仅完成本地代码与测试修改，未提交、未合并，也未部署。
