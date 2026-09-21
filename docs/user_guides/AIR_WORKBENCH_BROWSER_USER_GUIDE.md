# AIR Recovery Workbench 浏览器使用手册

本文面向直接使用浏览器工作台的用户，说明如何启动程序、选择 Case、检查数据、运行求解、阅读结果，以及如何正确导入和导出 JSON。

> 当前默认界面为 Workbench v2（React + TypeScript）。旧版 v1 可从 `/legacy` 打开；本文后半部分保留旧版说明，仅用于兼容参考。

## Workbench v2 快速使用

首次启动：

```powershell
cd D:\python_project\flight_recovery\frontend
npm install
npm run build
cd ..
python -m uvicorn backend.main:app --reload
```

访问 `http://127.0.0.1:8000` 或显式访问 `/workbench-v2`。推荐按左侧五步执行：

1. **数据设计**：从 Case 库克隆只读 Case；在虚拟表格中检查航班、资源、旅客、扰动、候选、剩余容量、成本和 Profile。修改工作副本后，旧编译和运行不会被冒充为当前结果。
2. **扰动影响**：点击“编译并预览”。`Ready` 只表示字段、候选和引用就绪，不承诺 MIP 可行。页面中的 direct/downstream 是暴露证据，不是恢复决策或因果结论。
3. **求解**：选择运行 Profile，创建不可变快照并入队。页面通过 SSE 展示真实 Phase 11/12 迭代、LB/UB、absolute/relative gap、割、列和节点汇总；刷新或断线不终止子进程。取消超过 5 秒未响应时会终止隔离进程并保留 Trace。
4. **方案对比**：`Original` 只显示基线，`Impact` 只显示扰动暴露，`Recovered` 仅在 optimal 且结果完整时可用，`Delta` 显示原计划 ghost 与恢复方案。航班完整划分为 changed/unchanged，并保留取消、O-D、时间、飞机和机组等多标签。
5. **审计**：查看输入 hash、选中决策、目标四分量、absolute/relative gap、约束审计、Expected 对拍、环境和完整事件；导出的审计包包含可复现快照。

本地持久化目录为 `.workbench/`，已加入 `.gitignore`。内置 Case 不会原地修改；草稿、修订、快照和运行都保留稳定 ID。桌面端支持编辑；390/768px 仅用于监控、摘要和变化航班查看。

## Workbench v2 状态语义

- Job：`queued / preparing / running / completed / failed / cancelled / interrupted`。
- Optimization：`optimal / infeasible / not_converged / aborted`。
- Current relation：当前草稿与运行输入 hash 相同为 current，否则为 stale。
- `infeasible` 和 `not_converged` 是正常优化结果，不是 HTTP 故障；求解器/license 不可用才返回结构化 503。

---

# Legacy v1 兼容参考

## 1. 工作台是什么

AIR Recovery Workbench 是一个研究与验证用途的航班恢复工作台。它围绕一个统一的 **Current Case** 工作：

```text
Current Case
├── Scenario
├── Recovery Columns（含 Flight Options 和 Passenger Itineraries）
├── Passenger Capacity
├── Cost Overrides
├── Algorithm Profiles
├── Solve Readiness
└── Recovered Result
```

Data、Visualization、Recovery、Costs、Constraints 五个页面始终读取同一个 Current Case。切换 Case 时，上述数据会作为一个整体被替换，不会把一个 Case 的 Scenario 和另一个 Case 的容量或恢复列混在一起。

> 注意：这是研究工作台，不是生产航司运行控制系统。求解是同步执行的，较复杂 Case 在求解完成前浏览器会等待。

## 2. 启动方式

在项目根目录 `D:\python_project\flight_recovery` 打开 PowerShell，执行：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

看到服务启动信息后，在浏览器访问：

```text
http://127.0.0.1:8000
```

不要直接双击 `frontend/index.html`。页面需要通过后端服务读取 Case、执行验证和调用求解器。

## 3. 页面顶部信息

顶部状态区长期显示五类状态：

| 状态 | 含义 |
|---|---|
| Case | 当前 Case 名称和当前输入 revision |
| Scenario | Scenario 是否已验证、是否被修改、Scenario ID 和记录数量 |
| Solve Input | 是否具备完整求解输入；`READY` 只代表输入就绪 |
| Solver | 求解器当前是空闲、运行中还是发生错误 |
| Result | 当前没有结果、结果有效，或结果已变为 `STALE` |

页面同时显示五步工作流：

```text
Load Case
→ Validate Scenario
→ Check Solve Readiness
→ Solve
→ Recovery / Audit
```

这些步骤不是强制向导，但可以用来判断当前进度。

## 4. 选择并加载内置 Case

页面打开后会默认加载 `Benchmark disruption recovery`。

加载其他 Case：

1. 在 `Case catalog` 下拉框中选择 Case。
2. 查看下拉框左侧的 Case 描述和标签。
3. 点击 `Load Case`。
4. 等待顶部 Case、Scenario 和 Solve Input 状态更新。

Case 按以下类别分组：

- Core Examples：主要完整案例；
- Validation Cases：成本、容量等单变量验证案例；
- Boundary Cases：非法输入或不可行边界；
- Scenario-only Cases：只有 Scenario、不具备求解输入的案例。

加载 Case 后，原来的未导出编辑和结果会被新 Case 替换。如需保留，请先使用 `Export Scenario`、`Export Current Case` 或 `Export Recovered Result`。

## 5. 推荐的完整操作流程

### 5.1 Load Case

使用 Case selector 选择内置 Case，或使用 `Import Scenario` / `Import Solve Bundle` 加载外部 JSON。

### 5.2 Validate Scenario

在 Data 页面点击 `Validate`。验证会检查 Schema 以及机场、航班、飞机、机组、旅客、时间和引用关系。

- `Valid`：Scenario 结构和跨实体语义通过；
- `Invalid`：页面底部会显示错误位置和原因；
- Scenario Valid 不等于 Solve Ready。

内置 Case 加载时会自动执行一次 Scenario validation。

### 5.3 Check Solve Readiness / Constraints

进入 Constraints 页面，点击 `Run Precheck`。

这里必须区分两个概念：

```text
PRECHECK READY != OPTIMIZATION FEASIBLE
```

Precheck 只检查输入是否完整、引用是否一致、容量和固定列是否满足确定性规则。它不会运行 MIP，也不会承诺一定存在可行优化解。内置 `Solve-ready but infeasible` Case 就专门演示这种区别。

### 5.4 Solve

当顶部 Solve Input 显示 `READY` 时，`Solve` 按钮可用。

1. 点击 `Solve`。
2. 等待同步 exact solver 完成。
3. 工作台会自动打开 Recovery 页面。
4. 查看求解状态：`optimal`、`infeasible` 或其他终止状态。

不要把 `Not solve ready` 当作不可行：前者表示输入不完整或无效，后者才是优化模型运行后的结果。

### 5.5 Recovery / Audit

Recovery 页面提供四种查看模式：

| 模式 | 内容 |
|---|---|
| Original | 原计划 |
| Disrupted / Risk | 扰动暴露和下游风险，不是求解决策 |
| Recovered | 求解器给出的恢复计划 |
| Difference | 只关注发生变化的航班 |

结果中可以查看：

- 总成本及 Schedule / Aircraft / Crew / Passenger 分量；
- 取消、延误和改航；
- 飞机轮换与调机；
- 机组 OPERATE / DEADHEAD；
- 旅客改签、延误和未服务人数；
- 算法上下界、gap、迭代、生成列和审计结果。

## 6. 五个一级视图怎么用

### Data

Data 用于查看和编辑 Scenario，包括 Scenario、Airports、Flights、Aircraft、Crew、Passengers、Airport Capacity 和 Disruptions。

表格支持添加、复制、删除、编辑和恢复当前 section。编辑 Scenario 后，Scenario validation 和 Constraints precheck 会失效，需要重新检查。

### Visualization

Visualization 展示原始计划、扰动暴露、风险传播、时空网络和机场容量。该页面展示的是 Scenario 及其风险，不是恢复求解结果。

如果 Scenario 无效，Visualization 会阻止绘制并显示验证问题。

### Recovery

Recovery 只展示 solver result。Scenario-only Case 不会自动产生 Recovery 数据。

### Costs

Costs 展示 canonical cost profile 和 Current Case 的 cost overrides。

- Baseline 是后端 canonical profile；
- Effective 是叠加 Current Case overrides 后的值；
- 修改 override 后应点击 `Validate Costs`；
- `Reset Cost Overrides` 恢复当前 Case 自带的 override，而不是一律清空。

### Constraints

Constraints 展示 SRM、ARM、CRM、PRM 的约束 registry、来源、假设和当前 Case precheck。

Passenger Capacity 是测试用 residual capacity，不是飞机物理座位数。

## 7. Result revision 和 STALE 状态

工作台用 revision 防止旧结果被误认为当前结果：

```text
输入 revision 0 → Solve → Result revision 0（有效）
修改 Scenario 或 Cost → 输入 revision 1 → 旧 Result 标为 STALE
重新 Solve → Result revision 1（重新有效）
```

结果变为 `STALE` 后：

- Recovery 仍可显示旧结果，便于比较；
- 页面会显示明显的 STALE 警告；
- `Export Recovered Result` 会被禁用；
- 必须重新 Solve 才能获得与当前输入一致的结果。

## 8. Reset 的含义

`Reset Current Case` 会恢复当前 Case 加载时的完整基线：Scenario、Recovery Columns、Passenger Capacity、Cost Overrides 和 Algorithm Profiles。

如果 Case 原本自带 cost override，Reset 后仍会保留这些值。Reset 不等于“清空所有 override”。

## 9. Import Scenario 和 Import Solve Bundle

两个按钮不能混用。

### Import Scenario

只接受原始 Scenario JSON。导入后：

- 可以进行 Data 编辑、Validation 和 Visualization；
- 不会推断或生成 Flight Options；
- 不会补 Passenger Capacity；
- 不会继承上一个 Case 的 Columns 或 profiles；
- Solve 通常保持不可用。

### Import Solve Bundle

只接受完整的 versioned `SolveRequest` JSON，至少包含：

```text
schema_version
scenario
recovery_columns
capacity_profile
cost_profile_id
cost_overrides
algorithm
profile_ids
```

有旅客时还必须显式提供 Passenger Itineraries。正式求解输入不能携带预生成 Aircraft Strings / Crew Pairings。

### 不能直接导入的文件

以下内容不能直接交给上述两个按钮：

- `data/cases/catalog.json`：它是 Case 清单，不是 Scenario 或 SolveRequest；
- `GET /api/cases/{case_id}` 的完整响应：它是带 `case / scenario / solve_bundle` 的包装对象；
- `Export Current Case` 文件：它是审计归档格式，不是原始 SolveRequest。

如需重新导入 API 返回的 Case，应提取其中的 `scenario` 或 `solve_bundle` 层。

## 10. Export 功能

### Export Scenario

只导出当前 Scenario，可再次通过 `Import Scenario` 导入。

### Export Current Case

导出审计归档，结构为：

```text
current_case
scenario
solve_input
result
```

其中包含 input revision、result revision 和结果是否 stale。该文件用于留档，不应直接作为 Solve Bundle 导入。

### Export Recovered Result

只导出求解结果。仅当结果与当前输入 revision 一致时可用。

## 11. 八个可检验 Case 在哪里

统一入口是：

```text
data/cases/catalog.json
```

Catalog 记录每个 Case 的 Case ID、分类、模式、Scenario/Columns/Capacity 来源、差异化 override 和 Expected。Case 不是简单复制成八套重复目录；后端会按 catalog 组装完整包，从而保证单变量敏感性案例只修改声明的那一个因素。

| Case ID | 类别 | 模式 | Expected | 主要源数据 |
|---|---|---|---|---|
| `benchmark-disruption-recovery` | Core | Solve Bundle | optimal / 18080 | `phase1_benchmark_001` scenario、columns、capacity |
| `crew-recovery-integrality` | Core | Solve Bundle | optimal / 95200 | `toy_case_016_benders_branch_and_price` |
| `passenger-capacity-constrained` | Validation | Solve Bundle | optimal / 1010 | `toy_case_005`，原航班余座为 0 |
| `passenger-capacity-relaxed` | Validation | Solve Bundle | optimal / 0 | 同一 `toy_case_005`，只把原航班余座改为 10 |
| `delay-cost-cancellation-tradeoff` | Validation | Solve Bundle | optimal / 25000 | 同一 `toy_case_005`，只覆盖延误单位成本 |
| `solve-ready-infeasible` | Boundary | Solve Bundle | infeasible | `toy_case_016` 的受限 Flight Option universe |
| `scenario-only-minimal` | Scenario-only | Scenario | valid / not ready | `data/examples/toy_case_001.json` |
| `invalid-missing-airport` | Boundary | Scenario | invalid / not ready | `data/cases/invalid_missing_airport.json` |

完整的底层文件分布在：

```text
data/examples/       Scenario
data/columns/        Recovery Columns
data/capacities/     Passenger Capacity
data/costs/          Canonical Cost Profile
data/config/         Algorithm Profiles
data/cases/          Case catalog 与专用负例
```

Case 组装逻辑位于：

```text
backend/application/case_service.py
```

组装时会应用 catalog 中声明的 cost/capacity overrides、Flight Option allowlist，并清空 Aircraft Strings / Crew Pairings。Benchmark Case 的 Passenger Itineraries 会按固定 profile 生成后显式放入返回的 Solve Bundle。

## 12. 八个 Case 怎么导入

### 推荐方式：直接使用 Case selector

内置八个 Case 不需要手工导入：

1. 启动服务；
2. 打开工作台；
3. 从 Case catalog 选择 Case；
4. 点击 `Load Case`。

这是最安全的方式，因为后端会一次性加载同一 Case 的所有输入。

### 通过 API 查看 Case

查看目录：

```text
http://127.0.0.1:8000/api/cases
```

查看单个 Case 的完整包装数据：

```text
http://127.0.0.1:8000/api/cases/{case_id}
```

例如：

```text
http://127.0.0.1:8000/api/cases/passenger-capacity-relaxed
```

### 下载并通过 Import Solve Bundle 重新导入

对于六个 `solve_bundle` Case，可以直接取得原始 SolveRequest：

```text
http://127.0.0.1:8000/api/solve/example-bundle/{case_id}
```

例如：

```text
http://127.0.0.1:8000/api/solve/example-bundle/crew-recovery-integrality
```

把返回 JSON 保存为文件，然后点击 `Import Solve Bundle` 选择该文件。

也可以使用 PowerShell 保存：

```powershell
$caseId = "crew-recovery-integrality"
$bundle = Invoke-RestMethod "http://127.0.0.1:8000/api/solve/example-bundle/$caseId"
$bundle | ConvertTo-Json -Depth 100 | Set-Content -Encoding utf8 ".\$caseId.solve-bundle.json"
```

### 下载 Scenario-only Case

Scenario-only 和 invalid Case 没有 Solve Bundle，需要从包装响应中提取 `scenario`：

```powershell
$caseId = "scenario-only-minimal"
$case = Invoke-RestMethod "http://127.0.0.1:8000/api/cases/$caseId"
$case.scenario | ConvertTo-Json -Depth 100 | Set-Content -Encoding utf8 ".\$caseId.scenario.json"
```

然后使用 `Import Scenario` 导入。

## 13. 常见问题

### Case 已加载但 Solve 仍不可用

检查顶部 Solve Input 和 Recovery 工具栏提示。Scenario-only Case 本来就没有 Flight Options、capacity 和 profiles，因此不会 Solve Ready。

### Precheck 已通过，为什么结果是 infeasible

这是正常且被测试覆盖的情况。Precheck 只判断输入契约和确定性条件，不运行完整优化模型。

### 修改 Costs 后为什么结果变成 STALE

Cost 是求解输入的一部分。旧结果对应旧成本，必须重新 Solve。

### 为什么不能导入 Export Current Case 文件

它是包含 metadata、input 和 result 的归档包装格式。请导入其中的 `solve_input` 层，或直接使用 `Import Solve Bundle` 所需的原始 SolveRequest。

### Case selector 和 Import 有什么区别

Case selector 读取仓库内已登记、带 Expected 的可回归 Case；Import 用于用户自己的外部 Scenario 或完整 Solve Bundle。
