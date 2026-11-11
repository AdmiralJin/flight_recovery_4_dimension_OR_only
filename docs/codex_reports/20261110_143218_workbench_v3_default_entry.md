# 默认首页切换到 Workbench v3

时间：2026-11-10（北京时间）。

- 后端 `/` 优先以 HTTP 307 跳转到 `/static/workbench-v3/index.html#/prepare`；缺少 v3 构建时保留原回退行为，v2 独立入口继续可用。
- 更新 v3 使用指南：启动 Uvicorn 后点击终端的根地址进入 v3；已有后端进程需重启以加载改动。
- 更新首页兼容性检查，`python -m pytest tests/api/test_api.py -q` 全部 5 项通过，包含 v3 跳转、静态页面及 v2 入口。
- 未操作现有服务或后台计算任务。
