# AIR 航空公司综合恢复复现项目

本项目分阶段复现 Petersen 等人（2010）的论文《An Optimization Approach to Airline Integrated Recovery》。当前已完成 Phase 0.5。

Phase 0 提供严格的场景数据 Schema、跨实体一致性校验、稳定的 toy case，以及基于浏览器的 JSON 数据编辑器；Phase 0.5 在同一页面增加确定性场景可视化。这两个阶段都不包含优化模型。

## 数据编辑入口

显式的 HTML 页面位于：

```text
frontend/index.html
```

请不要直接双击该文件打开，因为加载示例、数据校验等功能依赖 FastAPI 后端。应按下面的方式启动项目，然后在浏览器中编辑数据。

## 安装与启动

在项目根目录运行：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

启动成功后访问：

```text
http://127.0.0.1:8000
```

页面提供以下数据页签：

- Scenario
- Airports
- Flights
- Aircraft
- Crew
- Passengers
- Airport Capacity
- Disruptions

可以直接在表格单元格中编辑数据，并使用 Add Row、Duplicate Row、Delete Row 和 Reset 管理记录。页面顶部提供：

- `Load Example`：载入 `toy_case_001`；
- `Import JSON`：导入本地场景 JSON；
- `Export JSON`：导出当前编辑结果；
- `Validate`：调用后端检查数据并显示准确的错误位置。

原始示例数据也可以直接编辑：

```text
data/examples/toy_case_001.json
```

但日常录入和调试建议使用浏览器页面。

## Visualization 可视化

同一页面提供 `Data Editor` 与 `Visualization` 两种一级视图。进入 Visualization 时，系统会先校验当前内存中的场景数据；校验失败则拒绝绘图并显示错误位置。

当前可视化展示原始航班计划、已知扰动覆盖、沿原飞机/机组链传播的风险，以及机场容量时间桶中的计划流量。它不展示恢复结果，也不会计算实际延误、取消、资源改派或旅客改签；Phase 0.5 仍不包含优化模型。

## 运行测试

```powershell
python -m pytest
```

## API

- `GET /api/health`：查询服务状态和当前阶段；
- `GET /api/examples/toy_case_001`：读取稳定的示例场景；
- `POST /api/validate`：执行结构与跨实体一致性校验；
- `POST /api/solve`：Phase 0 安全闸门；拒绝错误数据，合法数据暂时返回 HTTP 501。

校验失败时会返回类似 `flights[0].origin` 的机器可读错误位置，以及错误代码和说明。校验成功时会返回标准化后的 JSON，用于稳定的导入、导出和前后端往返。

论文未明确规定的实现选择记录在 [assumptions.md](assumptions.md)，论文内容与当前代码范围的对应关系记录在 [reproduction_notes.md](reproduction_notes.md)。
