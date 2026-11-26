# 厦航 HiGHS：补充包与简要复现

## 1. 放到哪里

先 clone 已发布分支：

```powershell
git clone --branch feature/xma-highs-first-solution --single-branch https://github.com/AdmiralJin/flight_recovery_4_dimension_OR_only.git flight_recovery
```

基准提交为 `8927c2811a7c7001ef319a8ea6c99d9dfd40a800`。把本 ZIP **直接解压到 `flight_recovery` 根目录**；不要再套一个包名文件夹。ZIP 中的 `.public_benchmarks/` 与 `docs/` 均为项目相对路径。

Git 已有的文件不重复收录。厦航工作簿、评估 JAR、评分源码、91 个数据／配置文件，以及常规项目文档由 clone 提供；补充包提供本机历史实验、尚未发布的模型说明和必要实验记录。包中 `source/` 是旧实验不可变快照的一部分，不覆盖项目应用源码。

激活 Python 后，在项目根目录检查文件完整性：

```powershell
python VERIFY_XMA_TRANSFER.py
```

## 2. 交给新电脑 Codex 的任务

> 请先阅读本文件和 `XMA_PROJECT_CONTEXT.md`，运行文件校验。保持 HiGHS、joint_arc_flow、tianchi_2017、30 分钟网格、国内／国际 1440／2160 分钟业务延误上限及北京时间 2017-05-10 21:40 恢复截止。依据本机硬件，统一调整外层进程树内存上限和内部首解搜索准入额度；不要只改 manifest 或启动门槛。完成短校准后创建全新实验，先取得 FULL 的 2364 班／142 架完整独立审计通过方案，再改善目标。旧实验只作证据对照，不修改或覆盖。

当前发布分支仍有 **6 GiB 硬上限、4.8 GiB 预测准入线**，启动门槛为 4 GiB；更大内存不会自动放开限制。当前 CLI 没有 `--memory-gib` 或 `--only FULL`，由新机 Codex 根据需要适配。守护器依赖 Windows；其他操作系统需另行适配。

## 3. 环境和命令顺序

原实验使用 64 位 Python 3.12.4、HiGHS 1.15.1、gurobipy 13.0.3。安装仓库依赖，仍须保证 gurobipy 建模环境可启动；显式使用 HiGHS 优化。

```powershell
conda create -n flight_recovery python=3.12.4 pip -y
conda activate flight_recovery
python -m pip install -r requirements.txt
python -m pip check
```

**完成内存适配后**，采用全新且未存在的目录名运行：

```powershell
python scripts/xma_first_solution.py pilot --output .public_benchmarks/xma-pilot-newpc
python scripts/xma_first_solution.py prepare --output .public_benchmarks/xma-first-solution-newpc --calibration .public_benchmarks/xma-pilot-newpc/calibration.json
python scripts/xma_first_solution.py verify .public_benchmarks/xma-first-solution-newpc
python scripts/xma_first_solution.py run .public_benchmarks/xma-first-solution-newpc --start-now
```

先确认 pilot 的 `passed=true`。默认串行 Q1 6 小时、H1 12 小时、FULL 24 小时；若调整为仅 FULL，应显式实现并记录任务选择。防止系统睡眠，保留系统内存和磁盘余量。求解不要求网页常开。

需要 Workbench v3 时，在 `frontend` 执行 `npm ci`、`npm run build`、`npm run build:v3`，再回项目根目录执行 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`。入口为 <http://127.0.0.1:8000/static/workbench-v3/index.html>。发布分支不包含后来尚未发布的本机实验导入和可视化改进，不应假设页面已有这些入口。

## 4. 怎样判断有解

检查新实验 `summary.json` 的 `full_solution=true`，以及 FULL 的 `audit_pass=true`、`complete_decisions=true` 和完整检查点／航班表。`state.status=completed` 只表示调度结束。未证明最优时不能称为最优；缺失下界／Gap 不填 0。Java 可用于后续官方 JAR 交叉核验，缺 Java 时独立审计仍单独保留。

旧批次 `.public_benchmarks/xma-first-solution-v3-20261120/`：Q1、H1 已有完整审计通过方案；FULL 无完整方案。**不要运行旧 `start_xma.cmd` 或把旧目录当新机续算目录**，其中保留旧机路径、完成状态和已消耗预算；业务检查点也不是可恢复的求解器搜索树。

补充包保留旧文件原样及其哈希；目录索引、已有结果与详细阅读入口见 [XMA_PROJECT_CONTEXT.md](XMA_PROJECT_CONTEXT.md)。
