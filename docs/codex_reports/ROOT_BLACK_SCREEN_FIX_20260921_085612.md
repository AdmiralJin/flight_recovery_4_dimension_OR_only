# 根路径黑屏问题定位与修复报告

时间：2026-09-21 08:56:12（Asia/Shanghai）

## 问题现象

运行：

```bash
python -m uvicorn backend.main:app --reload
```

访问 `http://127.0.0.1:8000/` 时，Chrome 和 Edge 只显示深色背景，没有工作台内容。

## 根因

后端根路径 `/` 直接返回了 React v2 的 `dist/index.html`，但前端使用：

```tsx
<BrowserRouter basename="/workbench-v2">
```

浏览器地址仍为 `/`，不属于 `/workbench-v2` basename。React Router 因而拒绝渲染任何路由，`#root` 保持空节点。浏览器控制台复现信息为：

```text
<Router basename="/workbench-v2"> is not able to match the URL "/" ...
```

JS 和 CSS 静态资源均返回 200，因此表现为“资源正常但页面黑屏”。

## 修复

1. 当 v2 构建存在时，后端 `/` 返回 HTTP 307，跳转到规范入口 `/workbench-v2/data`。
2. 如果 v2 构建不存在，继续回退到旧版 `frontend/index.html`。
3. 新增 API 回归，检查根路径 307 和 `Location`。
4. 新增 Playwright 回归，从 `/` 进入并确认：
   - 地址最终为 `/workbench-v2/data`；
   - “数据设计”页面可见；
   - 控制台没有 basename warning。

修复过程中曾使用 `FileResponse | RedirectResponse` 作为返回类型标注，FastAPI 会将其错误识别为响应模型，导致热重载子进程启动失败。已移除该联合返回类型标注；`--reload` 随后成功重新启动应用子进程。

## 验证结果

- 实际 8000 端口：`/api/health` 返回 200；
- `GET /`：返回 307，`Location: /workbench-v2/data`；
- Edge 内核实测：最终 URL 正确，`.app-shell` 已渲染，`#root` 非空；
- 浏览器控制台：无 warning/error；
- 网络请求：无失败；
- `pytest tests/api/test_api.py -q`：5 项通过；
- 全量 `pytest -q`：全部通过；
- `npm run e2e`：3 项 Playwright 测试全部通过，包括桌面、390px 移动端和根路径黑屏回归。

## 修改文件

- `backend/main.py`
- `tests/api/test_api.py`
- `frontend/e2e/workbench.spec.ts`

修复曾在实际 8000 服务和独立 8001 验证服务上成功加载。连续代码修改和回归测试后，原 8000 的 Windows `--reload` supervisor 再次失去应用子进程；需要在原终端按 `Ctrl+C`，重新执行一次启动命令。重新启动后访问根地址会自动进入 v2 数据设计页面。
