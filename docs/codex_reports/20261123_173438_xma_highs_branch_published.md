# 厦航 HiGHS 首解分支发布

- 已确认并使用现有远程仓库：`https://github.com/AdmiralJin/flight_recovery_4_dimension_OR_only`，未创建新仓库。
- 已推送并建立上游跟踪：`feature/xma-highs-first-solution`。
- 发布提交：`8927c2811a7c7001ef319a8ea6c99d9dfd40a800`；远端 `ls-remote` 与本地提交号一致。
- 基于首解实现 `33ab4c9`，补交原实验实际采用的 4 GiB 启动门槛；运行器从冻结 manifest 读取门槛，并同步操作说明。
- 验证：首解及批次相关 21 项回归检查通过；提交前 `git diff --check` 通过；推送前试运行和推送后远端校验通过。
- 范围：独立 worktree 操作，已清理；主工作区仍在 `feature/v3-visualization-optimization`，既有 49 个已跟踪修改保留，未混入此次提交。
- 数据澄清：实际核实远端 `feature/air-workbench-data-ui-improvements` 的 `fa293d3` 已包含厦航原件历史及相同四个文件。本次没有新增原件或实验数据；发布分支仍包含已有原件，`.public_benchmarks` 和 `.workbench` 运行记录仍未上传。
- 资源边界：仍保留 6 GiB 进程树硬上限及内部 4.8 GiB 预测准入线，本次没有实施大内存适配或启动正式求解。

新电脑拉取：

```powershell
git clone --branch feature/xma-highs-first-solution --single-branch https://github.com/AdmiralJin/flight_recovery_4_dimension_OR_only.git flight_recovery
```

拉取后 `git rev-parse HEAD` 应为上述完整提交号。旧实验结果另行离线迁移；新机实际运行应新建批次、重新校准，并先处理需要扩大的内存限制。
