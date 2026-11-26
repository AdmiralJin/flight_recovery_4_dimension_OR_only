# 微型案例人工验算卡

## 综合恢复人工基准 (`micro-integrated-benchmark`)

- 导入方式：`solve_bundle`
- 类别：综合算法
- 规模：{"airports": 4, "flights": 12, "aircraft": 4, "crew": 5, "passengers": 8, "airport_intervals": 4, "disruptions": 1}
- 重点约束：SRM-C01-FLIGHT-COVERAGE, SRM-C02-STRATEGIC-FLIGHT, SRM-C03-ARRIVAL-CAPACITY, SRM-C04-DEPARTURE-CAPACITY, SRM-C05-GATE-INVENTORY, SRM-C06-MARKET-SEAT, ARM-C01-AIRCRAFT-STRING-SELECTION, ARM-C02-FLIGHT-OPTION-COVERAGE, ARM-C03-TERMINAL-STATION, ARM-C04-MAINTENANCE, ARM-C05-STRING-FEASIBILITY, CRM-C01-CREW-PAIRING-SELECTION, CRM-C02-FLIGHT-OPTION-COVERAGE, CRM-C03-NONREQUIRED-REVENUE-PROHIBITION, CRM-C04-CREW-FEASIBILITY, CRM-C05-TERMINAL-OR-OWNERSHIP, PRM-C01-PASSENGER-GROUP-SELECTION, PRM-C02-SCHEDULE-CONSISTENCY, PRM-C03-SEAT-CAPACITY, PRM-C04-ITINERARY-FEASIBILITY
- 算法机制：integrated, benders, column_generation
- 预期：`{"status": "optimal", "objective_total": 18080.0}`
- 人工核验：3 个航班延误共 80 分钟，旅客加权延误 1800，目标值 18080。

## 机组整数性与分支定价 (`micro-crew-integrality`)

- 导入方式：`solve_bundle`
- 类别：机组
- 规模：{"airports": 3, "flights": 6, "aircraft": 3, "crew": 3, "passengers": 0, "airport_intervals": 7, "disruptions": 0}
- 重点约束：CRM-C01-CREW-PAIRING-SELECTION, CRM-C02-FLIGHT-OPTION-COVERAGE, CRM-C03-NONREQUIRED-REVENUE-PROHIBITION, CRM-C04-CREW-FEASIBILITY, CRM-C05-TERMINAL-OR-OWNERSHIP
- 算法机制：branch_and_price, crew_integrality
- 预期：`{"status": "optimal", "objective_total": 95200.0}`
- 人工核验：根节点 LP 存在整数缺口，9 个机组分支节点闭合到 95200。

## 旅客余座容量绑定 (`micro-passenger-capacity-binding`)

- 导入方式：`solve_bundle`
- 类别：旅客
- 规模：{"airports": 2, "flights": 1, "aircraft": 1, "crew": 1, "passengers": 1, "airport_intervals": 2, "disruptions": 0}
- 重点约束：PRM-C01-PASSENGER-GROUP-SELECTION, PRM-C02-SCHEDULE-CONSISTENCY, PRM-C03-SEAT-CAPACITY, PRM-C04-ITINERARY-FEASIBILITY
- 算法机制：passenger_recovery
- 预期：`{"status": "optimal", "objective_total": 1010.0}`
- 人工核验：原始候选余座为 0，10 人旅客组迫使航班延误 10 分钟。

## 旅客容量单变量放宽 (`micro-passenger-capacity-relaxed`)

- 导入方式：`solve_bundle`
- 类别：旅客
- 规模：{"airports": 2, "flights": 1, "aircraft": 1, "crew": 1, "passengers": 1, "airport_intervals": 2, "disruptions": 0}
- 重点约束：PRM-C03-SEAT-CAPACITY
- 算法机制：sensitivity
- 预期：`{"status": "optimal", "objective_total": 0.0}`
- 人工核验：仅把原始候选余座从 0 改为 10，最优目标从 1010 降为 0。

## 延误与未承运成本权衡 (`micro-delay-unserved-tradeoff`)

- 导入方式：`solve_bundle`
- 类别：成本
- 规模：{"airports": 2, "flights": 1, "aircraft": 1, "crew": 1, "passengers": 1, "airport_intervals": 2, "disruptions": 0}
- 重点约束：PRM-C01-PASSENGER-GROUP-SELECTION, PRM-C02-SCHEDULE-CONSISTENCY, PRM-C03-SEAT-CAPACITY
- 算法机制：cost_sensitivity
- 预期：`{"status": "optimal", "objective_total": 25000.0}`
- 人工核验：提高航班延误单价后，保留原计划并承担 10 人未承运成本。

## 输入就绪但优化不可行 (`micro-solve-ready-infeasible`)

- 导入方式：`solve_bundle`
- 类别：边界
- 规模：{"airports": 3, "flights": 6, "aircraft": 3, "crew": 3, "passengers": 0, "airport_intervals": 7, "disruptions": 0}
- 重点约束：SRM-C01-FLIGHT-COVERAGE, ARM-C02-FLIGHT-OPTION-COVERAGE, CRM-C02-FLIGHT-OPTION-COVERAGE
- 算法机制：feasibility
- 预期：`{"status": "infeasible", "objective_total": null}`
- 人工核验：结构和配置完整，但候选集合无法形成联合可行恢复。

## 最小有效 Scenario (`micro-scenario-only-minimal`)

- 导入方式：`scenario`
- 类别：输入校验
- 规模：{"airports": 3, "flights": 6, "aircraft": 2, "crew": 2, "passengers": 4, "airport_intervals": 1, "disruptions": 1}
- 重点约束：SRM-C03-ARRIVAL-CAPACITY, SRM-C04-DEPARTURE-CAPACITY
- 算法机制：validation
- 预期：`{"scenario_valid": true, "solve_ready": false}`
- 人工核验：Scenario 有效，但没有候选、容量和算法配置，因此不能求解。

## 无效机场引用 (`micro-invalid-missing-airport`)

- 导入方式：`scenario`
- 类别：输入校验
- 规模：{"airports": 1, "flights": 1, "aircraft": 1, "crew": 1, "passengers": 0, "airport_intervals": 1, "disruptions": 0}
- 重点约束：Scenario 结构/引用校验
- 算法机制：negative_validation
- 预期：`{"scenario_valid": false, "error_code": "unknown_airport"}`
- 人工核验：航班引用未声明机场，必须在求解前被拒绝。

## 多实体 Scenario 校验 (`micro-scenario-validation-rich`)

- 导入方式：`scenario`
- 类别：输入校验
- 规模：{"airports": 5, "flights": 12, "aircraft": 6, "crew": 6, "passengers": 8, "airport_intervals": 8, "disruptions": 1}
- 重点约束：Scenario 结构/引用校验
- 算法机制：validation, visualization
- 预期：`{"scenario_valid": true, "solve_ready": false}`
- 人工核验：5 机场、12 航班、6 飞机、6 机组和 8 旅客组的结构校验样例。

## 编辑器与传播基础样例 (`micro-basic-editor`)

- 导入方式：`scenario`
- 类别：输入校验
- 规模：{"airports": 3, "flights": 6, "aircraft": 2, "crew": 2, "passengers": 4, "airport_intervals": 1, "disruptions": 1}
- 重点约束：Scenario 结构/引用校验
- 算法机制：validation, visualization
- 预期：`{"scenario_valid": true, "solve_ready": false}`
- 人工核验：用于导入、编辑、导出和扰动传播的最小综合 Scenario。

## 飞机对计划选择的反向耦合 (`micro-aircraft-coupling`)

- 导入方式：`solve_bundle`
- 类别：飞机
- 规模：{"airports": 2, "flights": 1, "aircraft": 1, "crew": 1, "passengers": 1, "airport_intervals": 2, "disruptions": 0}
- 重点约束：ARM-C01-AIRCRAFT-STRING-SELECTION, ARM-C02-FLIGHT-OPTION-COVERAGE, ARM-C03-TERMINAL-STATION, ARM-C04-MAINTENANCE, ARM-C05-STRING-FEASIBILITY
- 算法机制：aircraft_recovery, integrated
- 预期：`{"status": "optimal"}`
- 人工核验：比较原计划与延误候选，观察动态飞机列如何限制计划选择。

## 恢复范围闭包 (`micro-scope-closure`)

- 导入方式：`solve_bundle`
- 类别：计划
- 规模：{"airports": 5, "flights": 3, "aircraft": 2, "crew": 2, "passengers": 2, "airport_intervals": 6, "disruptions": 1}
- 重点约束：SRM-C01-FLIGHT-COVERAGE, ARM-C02-FLIGHT-OPTION-COVERAGE, CRM-C02-FLIGHT-OPTION-COVERAGE, PRM-C02-SCHEDULE-CONSISTENCY
- 算法机制：scope, integrated
- 预期：`{"status": "optimal", "objective_total": 2040.0}`
- 人工核验：受扰组件需要两班各延误 20 分钟，独立组件保持原计划。

## 飞机路径生成 (`micro-aircraft-string-generation`)

- 导入方式：`solve_bundle`
- 类别：飞机
- 规模：{"airports": 5, "flights": 5, "aircraft": 3, "crew": 3, "passengers": 0, "airport_intervals": 5, "disruptions": 0}
- 重点约束：ARM-C01-AIRCRAFT-STRING-SELECTION, ARM-C02-FLIGHT-OPTION-COVERAGE, ARM-C03-TERMINAL-STATION, ARM-C04-MAINTENANCE, ARM-C05-STRING-FEASIBILITY
- 算法机制：aircraft_string_generation
- 预期：`{"status": "optimal", "objective_total": 0.0}`
- 人工核验：覆盖机型、衔接、终到站、维修和调机路径边界。

## 旅客行程生成 (`micro-passenger-itinerary-generation`)

- 导入方式：`solve_bundle`
- 类别：旅客
- 规模：{"airports": 5, "flights": 6, "aircraft": 4, "crew": 4, "passengers": 2, "airport_intervals": 5, "disruptions": 0}
- 重点约束：PRM-C01-PASSENGER-GROUP-SELECTION, PRM-C02-SCHEDULE-CONSISTENCY, PRM-C03-SEAT-CAPACITY, PRM-C04-ITINERARY-FEASIBILITY
- 算法机制：passenger_itinerary_generation
- 预期：`{"status": "optimal", "objective_total": 0.0}`
- 人工核验：覆盖直达、中转、最小衔接、最大航段和未承运行程。

## 固定列 Benders 行为 (`micro-fixed-column-benders`)

- 导入方式：`solve_bundle`
- 类别：算法
- 规模：{"airports": 2, "flights": 1, "aircraft": 1, "crew": 1, "passengers": 1, "airport_intervals": 2, "disruptions": 0}
- 重点约束：SRM-C01-FLIGHT-COVERAGE, PRM-C03-SEAT-CAPACITY
- 算法机制：benders
- 预期：`{"status": "optimal"}`
- 人工核验：保留用于观察 Benders 可行割和最优割；最终动态列入口可能得到更低目标。

## 飞机列生成定价 (`micro-aircraft-column-generation`)

- 导入方式：`solve_bundle`
- 类别：飞机
- 规模：{"airports": 6, "flights": 2, "aircraft": 2, "crew": 2, "passengers": 0, "airport_intervals": 6, "disruptions": 0}
- 重点约束：ARM-C01-AIRCRAFT-STRING-SELECTION, ARM-C02-FLIGHT-OPTION-COVERAGE, ARM-C03-TERMINAL-STATION, ARM-C04-MAINTENANCE, ARM-C05-STRING-FEASIBILITY
- 算法机制：aircraft_column_generation
- 预期：`{"status": "optimal", "objective_total": 0.0}`
- 人工核验：初始调机列成本为 300，负约化成本列把飞机子问题降为 0。

## 机组列生成定价 (`micro-crew-column-generation`)

- 导入方式：`solve_bundle`
- 类别：机组
- 规模：{"airports": 2, "flights": 2, "aircraft": 2, "crew": 3, "passengers": 0, "airport_intervals": 2, "disruptions": 0}
- 重点约束：CRM-C01-CREW-PAIRING-SELECTION, CRM-C02-FLIGHT-OPTION-COVERAGE, CRM-C03-NONREQUIRED-REVENUE-PROHIBITION, CRM-C04-CREW-FEASIBILITY, CRM-C05-TERMINAL-OR-OWNERSHIP
- 算法机制：crew_column_generation
- 预期：`{"status": "optimal", "objective_total": 150.0}`
- 人工核验：定价加入更便宜机组任务，正式综合入口的总目标为 150。

## Benders 与列生成组合 (`micro-benders-column-generation`)

- 导入方式：`solve_bundle`
- 类别：算法
- 规模：{"airports": 2, "flights": 1, "aircraft": 1, "crew": 1, "passengers": 1, "airport_intervals": 3, "disruptions": 0}
- 重点约束：SRM-C01-FLIGHT-COVERAGE, SRM-C02-STRATEGIC-FLIGHT, SRM-C03-ARRIVAL-CAPACITY, SRM-C04-DEPARTURE-CAPACITY, SRM-C05-GATE-INVENTORY, SRM-C06-MARKET-SEAT, ARM-C01-AIRCRAFT-STRING-SELECTION, ARM-C02-FLIGHT-OPTION-COVERAGE, ARM-C03-TERMINAL-STATION, ARM-C04-MAINTENANCE, ARM-C05-STRING-FEASIBILITY, CRM-C01-CREW-PAIRING-SELECTION, CRM-C02-FLIGHT-OPTION-COVERAGE, CRM-C03-NONREQUIRED-REVENUE-PROHIBITION, CRM-C04-CREW-FEASIBILITY, CRM-C05-TERMINAL-OR-OWNERSHIP, PRM-C01-PASSENGER-GROUP-SELECTION, PRM-C02-SCHEDULE-CONSISTENCY, PRM-C03-SEAT-CAPACITY, PRM-C04-ITINERARY-FEASIBILITY
- 算法机制：benders, column_generation
- 预期：`{"status": "optimal", "objective_total": 220.0}`
- 人工核验：三个计划候选分别对应资源不可行、旅客高成本和综合最优，最优为 220。

## 机组根节点整数缺口 (`micro-crew-root-integrality`)

- 导入方式：`solve_bundle`
- 类别：机组
- 规模：{"airports": 3, "flights": 6, "aircraft": 3, "crew": 3, "passengers": 0, "airport_intervals": 3, "disruptions": 0}
- 重点约束：CRM-C01-CREW-PAIRING-SELECTION, CRM-C02-FLIGHT-OPTION-COVERAGE, CRM-C03-NONREQUIRED-REVENUE-PROHIBITION, CRM-C04-CREW-FEASIBILITY, CRM-C05-TERMINAL-OR-OWNERSHIP
- 算法机制：crew_integrality, branch_and_price
- 预期：`{"status": "optimal"}`
- 人工核验：专用机组子问题根 LP 为 195、整数最优为 200；综合入口用于结构导入检查。

## 完整 Branch-and-Price (`micro-branch-and-price`)

- 导入方式：`solve_bundle`
- 类别：算法
- 规模：{"airports": 3, "flights": 6, "aircraft": 3, "crew": 3, "passengers": 0, "airport_intervals": 7, "disruptions": 0}
- 重点约束：SRM-C01-FLIGHT-COVERAGE, SRM-C02-STRATEGIC-FLIGHT, SRM-C03-ARRIVAL-CAPACITY, SRM-C04-DEPARTURE-CAPACITY, SRM-C05-GATE-INVENTORY, SRM-C06-MARKET-SEAT, ARM-C01-AIRCRAFT-STRING-SELECTION, ARM-C02-FLIGHT-OPTION-COVERAGE, ARM-C03-TERMINAL-STATION, ARM-C04-MAINTENANCE, ARM-C05-STRING-FEASIBILITY, CRM-C01-CREW-PAIRING-SELECTION, CRM-C02-FLIGHT-OPTION-COVERAGE, CRM-C03-NONREQUIRED-REVENUE-PROHIBITION, CRM-C04-CREW-FEASIBILITY, CRM-C05-TERMINAL-OR-OWNERSHIP, PRM-C01-PASSENGER-GROUP-SELECTION, PRM-C02-SCHEDULE-CONSISTENCY, PRM-C03-SEAT-CAPACITY, PRM-C04-ITINERARY-FEASIBILITY
- 算法机制：benders, column_generation, branch_and_price
- 预期：`{"status": "optimal", "objective_total": 95200.0}`
- 人工核验：必须通过机组分支闭合整数缺口，最终目标 95200。
