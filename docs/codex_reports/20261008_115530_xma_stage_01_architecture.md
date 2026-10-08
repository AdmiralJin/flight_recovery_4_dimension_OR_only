# 厦航接入阶段总结 01_architecture

2026-10-08 11:55:30 北京时间

梳理旧 HTML/React 入口、约束注册表、实际联合模型、工作台编译/快照/运行流程。形成 docs/models/XMA_RECOVERY.md 架构图、原四模块与厦航差异表。判断为“原始Excel保留，适配层负责数据映射；实际座位、人数拆分、机场与机队业务约束必须扩展模型”。旧AIR合同不改。

原成本复现参数与 data/costs/phase2_test_costs_v1.json 核对。新 AIR 线性目标作用于厦航航段账本，明确不冒充旧不可拆分OD模型。
