# Workbench v2 用户指南编写工作总结

## 完成时间

2026-10-15 11:26:58 Asia/Shanghai

## 本次工作内容

- 阅读项目 README、FastAPI 入口、Workbench v2 React 页面、前端 API 客户端和后端 v2 路由，确认当前默认界面和实际功能边界。
- 核对 `frontend/index.html` 与当前路由关系，确认该 HTML 是 `/legacy` 兼容界面，默认入口在前端构建后进入 React Workbench v2。
- 参考旧版浏览器指南中仍然有效的启动、状态、求解边界和审计概念，未照搬已经被 v2 草稿、hash、快照和异步运行机制替代的操作。
- 新建面向最终用户的 `AIR_WORKBENCH_V2_USER_GUIDE.md`，包含环境准备、启动方式、六步页面工作流、逐步操作、厦航专项流程、状态与指标、导入导出区别、常见问题、旧版兼容说明和结果核验清单。
- 明确说明研究工具边界、风险证据边界、编译 Ready 与优化可行性的区别、Job 与 Optimization 双层状态、不可变快照和 Input hash 的使用方法。

## 交付文件

- `docs/user_guides/AIR_WORKBENCH_V2_USER_GUIDE.md`
- `docs/codex_reports/20261015_112658_workbench_v2_user_guide_report.md`

## 验证范围

- 对照当前前端按钮、页面标签、数据流和 API 路径完成内容核验。
- 检查新文档的 Markdown 标题结构、内部术语和关键命令。
- 本次只新增文档，未修改应用代码或运行模型求解测试。
