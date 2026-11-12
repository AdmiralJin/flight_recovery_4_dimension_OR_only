# HiGHS 基线窗口交接

北京时间：2026-11-12 11:07:00

- 初步公开数据接入说明提交：`9461cce`；v3 优化主提交：`b93afec`，启动引号及证书检查等修正已提交。
- 正式基线冻结代码：`70b3422701bcaf1df0cace8d8cc42982837bae0c`。
- 实验目录：`.public_benchmarks/highs-direct-v3-20261112`。
- 清单 SHA-256：`c3f462857e49f958fd1e9d3e882bd128001eb8705eb8e77022c3a699a37a13c4`，已完成校验。
- 79 个输入、95 项任务：micro 32、roadef 42、delft 11、xma 10。39 个输入预检就绪，40 个保留不支持原因；没有删除失败样本。
- 单任务预算 600～14400 秒，全批登记上限约 158.83 小时（含预检不支持项；实际可提前结束）；组内串行、各组全局互斥、单线程、进程树 6 GiB 硬上限。
- 仅做开发检查，交接前正式任务结果文件数为 0。后端原有及新增回归、直接模型与 Oracle 对拍、取消保留、回车门槛和证书冲突检查通过；v3 前端 45 项及构建通过。
- 使用 `python scripts/highs_baseline.py launch .public_benchmarks/highs-direct-v3-20261112` 打开四个 CMD。每组等待用户回车后才启动；全部结束由用户通知后再检查证据。本次不代按回车。
- 详细说明：`docs/benchmarks/highs_direct_baseline_v3.md`。原始大文件及实验大制品保留本地，不提交 Git。
