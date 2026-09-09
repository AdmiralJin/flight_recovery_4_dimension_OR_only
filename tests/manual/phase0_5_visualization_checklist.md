# Phase 0.5 Visualization 验收清单

验收日期：2026-09-09  
测试环境：Microsoft Edge（Chromium，无头模式），FastAPI 本地服务  
结果：全部通过。故意构造重复 `flight_id` 时产生的 HTTP 422 为预期校验响应，无未捕获 JavaScript 错误。

## A. Phase 0 回归

- [x] Load、Edit、Add、Duplicate、Delete、Reset 正常。
- [x] Import、Export、Validate pass/fail 正常。
- [x] `phase0_frontend_checklist.md` 无回归。

## B. 一级视图与校验闸门

- [x] Data Editor 与 Visualization 可双向切换。
- [x] 切换不丢失人工修改，也不重置当前数据 section。
- [x] Visualization 使用当前内存 state。
- [x] 重复 `flight_id` 时拒绝绘图并显示原校验错误；修复后可进入。

## C. 时空网络与影响覆盖

- [x] 显示 A、B、C 三条机场 lane 和 F1–F6 六条航班。
- [x] 时间轴范围为 08:00–16:00 UTC，航班方向可识别且可点击。
- [x] B 09:00–11:00 显示扰动区域。
- [x] F2、F5 为 direct；F3、F6 为 downstream；F1、F4 为 normal。
- [x] Recovered Plan 存在但禁用，页面未伪造延误或取消结果。

## D. 资源详情

- [x] 点击 F2 显示 B→C、AC1、C1、P1（28 pax）和直接暴露原因。
- [x] 点击 F3 显示 AC1 与 C1 两个传播来源，并显示 P3。
- [x] Rotation、pairing 和 itinerary chip 可反向切换主图选中航班。

## E. 容量热力图

- [x] Departures：B 09:00–11:00 为 2 / 1，状态 over capacity。
- [x] Arrivals：B 09:00–11:00 为 2 / 2，状态 at capacity。
- [x] 显示 gate capacity，但不伪造 gate utilization。
- [x] 未使用 `capacity_change` 反推原容量。

## F. 响应式与稳定性

- [x] 桌面布局正常。
- [x] 390px 下 body 无整体横向溢出，network/heatmap 在组件内滚动，detail 位于主图下方。
- [x] 浏览器 console 无未捕获错误。
