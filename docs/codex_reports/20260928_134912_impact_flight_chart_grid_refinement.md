# Workbench v2 Impact 航班时空图坐标与网格优化

## 修改范围

- 仅调整 `frontend/v2/src/visualization/chartOptions.ts` 中 Impact 模式的航班时空图。
- 未修改 Original、Recovered、Delta 模式，未修改其他可视化、数据合同或业务逻辑。
- 未执行 Git 提交。

## 视觉调整

- 明确标注“机场”和“时间（UTC）”坐标轴。
- 提高机场标签、时间标签、轴线和刻度的对比度。
- 增加时间主网格线、次网格线以及对应的主/次刻度。
- 增强机场泳道横向分隔线，并使用克制的交替底纹帮助沿行对齐。
- 适当增加图表边距，避免坐标标题和标签拥挤。

## 验证

- `npm run typecheck`：通过。
- `npm test -- --run`：6/6 通过。
- `npm run build`：通过。
- 构建仅保留既有 ECharts chunk size warning。

