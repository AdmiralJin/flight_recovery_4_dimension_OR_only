# Case Catalog 加载故障修复报告

- 时间：2026-09-20 14:13:55（Asia/Shanghai）
- 分支：`feature/air-workbench-data-ui-improvements`

## 用户现象

- 页面持续显示 `Case / Loading catalog…`；
- Case selector 没有选项；
- 除五个一级视图切换外，其余依赖 Current Case 的操作不可用。

## 排查结论

1. 本机 `127.0.0.1:8000` 服务正常监听；
2. `/`、`/api/cases`、`/static/js/app.js`、`/static/js/case-state.js` 均返回 HTTP 200；
3. `/api/cases` 能返回 8 个 Case，VPN 不是原因；
4. 全新 Edge 浏览器上下文可以正常加载，说明主要问题是现有页面启动阶段遇到请求失败或旧静态资源缓存后，前端没有恢复入口，永久停留在 Loading 状态。

## 修复内容

1. `GET /api/cases` 和单 Case GET 改为 `cache: no-store`；
2. Catalog/Case GET 遇到短暂失败时最多自动尝试 3 次；
3. `/` 和 `/static/*` 响应增加 `Cache-Control: no-store, max-age=0` 与 `Pragma: no-cache`；
4. `app.js` URL 增加版本参数，避免浏览器继续执行旧入口模块；
5. 初始化失败时不再永久显示 Loading：
   - Case 状态显示 `Catalog unavailable`；
   - 页面显示实际错误信息；
   - `Load Case` 变为可点击的 `Retry Initialization`；
6. 单 Case 加载失败时显示 `Case load failed` 和具体错误。

## 验证

- JavaScript 语法检查通过；
- API、Case 与前端定向测试通过；
- 完整 `python -m pytest -q` 测试集 100% 通过；
- Edge 内核实际页面验证：
  - 正常启动：8 个 Case，默认 Case 加载，Solve 可用；
  - 前两次 `/api/cases` 请求失败：第 3 次自动恢复并加载 8 个 Case；
  - `/api/cases` 持续失败：显示 `Catalog unavailable` 和可点击的 `Retry Initialization`，不再假死。

## 用户侧操作

修复后的静态资源已经禁用旧缓存。保留 uvicorn CMD 窗口运行，在现有页面执行一次 `Ctrl+F5`，或重新打开 `http://127.0.0.1:8000` 即可加载新版入口。
