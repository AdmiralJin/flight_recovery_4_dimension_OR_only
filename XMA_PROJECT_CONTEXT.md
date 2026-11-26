# 项目介绍与目录索引

## 任务与发布版本

本项目研究航班受扰后的恢复。Workbench v3 是数据、配置、求解和结果分析的操作台；原 AIR、厦航、公开基准采用不同模型，不能混为同一个问题。本次只复现**厦航 HiGHS 首解**。

- GitHub 分支：`feature/xma-highs-first-solution`。
- 发布基准：`8927c2811a7c7001ef319a8ea6c99d9dfd40a800`。
- 数学模型：航班执行／取消、同机型飞机时空网络流、整数人数账本与改签；天池评分；机组和维修关闭。
- 候选域：30 分钟基础网格补规则边界，国内／国际最长延误 24／36 小时，恢复截止北京时间 2017-05-10 21:40。
- 目标：先取得全部 2364 班、142 架飞机的完整可行方案，并通过独立审计，再改善目标。

## clone 后的主要目录

```text
flight_recovery/
├─ README.md                         项目总说明（Git 已有）
├─ assumptions.md                    实现假设与边界（Git 已有）
├─ reproduction_notes.md             原有复现说明（Git 已有）
├─ requirements.txt                  Python 依赖（Git 已有）
├─ backend/
│  ├─ business/xma/                  厦航合同、导入、规则、构模、搜索和审计
│  ├─ benchmarks/xma_first_solution.py  校准、冻结与串行批次守护
│  └─ workbench/                     工作台快照与运行管理
├─ scripts/xma_first_solution.py     厦航首解 CLI
├─ scripts/validation_campaign.py    Windows 进程树资源守护
├─ data/厦航-天池比赛数据/data/        工作簿、JAR、评分源码（Git 已有）
├─ data/config/、data/costs/          规则／算法与研究成本（Git 已有）
├─ frontend/v3/                      v3 源码；依赖与页面构建需重建
├─ docs/user_guides/                 操作、模型和数据说明
├─ docs/codex_reports/               计划、实验、发布与整理记录
└─ .public_benchmarks/
   └─ xma-first-solution-v3-20261120/  本补充包提供的完整历史批次
```

## 历史批次内部结构

| 路径 | 用途 |
|---|---|
| `manifest.json`、`groups.json`、`calibration.json` | 冻结来源、输入哈希、分组、资源政策与原机校准 |
| `inputs/Q1.json`、`H1.json`、`FULL.json` | 完整规范化求解输入，包含各组全部业务数据 |
| `boundaries/`、`drafts/` | 条件子集边界与工作台草稿 |
| `source/` | 原实验完整源码／资料快照；用于验证旧证据，不能替换 clone 源码 |
| `jobs/<分组>/result.json` | 分组摘要，不包含全部方案 |
| `jobs/<分组>/attempt_*/checkpoint.json` | 完整业务方案及独立审计证据 |
| 同一 attempt 的 `flights.csv`、`events.jsonl`、`worker.log` | 航班恢复表、事件和原始日志 |
| `summary.json`、`runs.csv` | 三组最终汇总；含失败和未取得方案的情况 |

| 分组 | 航班／飞机 | 审计通过的目标值 | 状态 |
|---|---:|---:|---|
| Q1 | 598／36 | 263121.9146990741 | 完整可行；内存受限；未证明最优 |
| H1 | 1176／71 | 517919.79027777776 | 完整可行；内存受限；未证明最优 |
| FULL | 2364／142 | 无 | 尚无完整可行方案 |

Q1/H1 是完整机尾条件子集，外部进港按原计划冻结，外部出港影响排除，源机场限制不缩放且不扣除外部占用；不能拼接为全量方案，也不应直接用总成本比较算法优劣。

## 建议阅读入口

1. [简要复现说明](XMA_REPRODUCE_README.md)。
2. [原始首解详细计划](docs/codex_reports/20261119_170417_xma_highs_first_solution_detailed_plan.md)与[首解操作说明](docs/user_guides/XMA_HIGHS_FIRST_SOLUTION.md)：由 Git 提供。
3. [v3 技术路线、数据与模型全景](docs/user_guides/WORKBENCH_V3_TECHNICAL_ROUTES_DATA_AND_MODELS_20261114.md)：由 Git 提供。
4. [三类模型数学表述与数据合同](docs/user_guides/WORKBENCH_V3_THREE_MODELS_FORMULATION_AND_DATA_CONTRACTS_20261122.md)：本包补充；覆盖当前更广工作区，后续历史导入等描述不意味着其应用代码已在首解分支发布。
5. [批次结束核查](docs/codex_reports/20261120_091552_xma_campaign_completion_check.md)与[分支发布记录](docs/codex_reports/20261123_173438_xma_highs_branch_published.md)：本包补充。

本包另附一份 ROADEF 旅客冻结 JSON，仅用于模型说明中的链接和口径参考；没有打包其他公开数据全集，本次厦航求解不依赖它们。

## 对新机 Codex 的边界提示

旧 manifest、启动器和部分结果路径含旧机绝对位置；保留原样作为历史证据。新机先改 clone 中的资源配置，重新 pilot 和 prepare；不要改旧快照或用旧校准冒充新机校准。复制业务检查点不等于恢复 HiGHS 搜索树，也不会自动成为新实验热启动。

`XMA_TRANSFER_MANIFEST.json` 记录包内逐文件 SHA-256，以及需由 Git clone 提供的数据文件对象 ID；`VERIFY_XMA_TRANSFER.py` 仅检查文件和版本，不启动求解。未包含 `.git`、conda 环境、许可证、当前工作台数据库或工作区未发布应用代码。
