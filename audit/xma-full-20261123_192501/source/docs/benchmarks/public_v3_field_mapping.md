# 公开资料到研究模型的字段映射

原始资料不修改。输入 JSON 的 `source.records`、`source.raw_tables`、`source.files` 和 `fixed_context` 是原字段追溯入口；`scenario`、`recovery_columns`、`capacity_profile`、`costs`、`configs` 是实际求解输入。保留原字段不等于已在模型中施加该规则。

|来源字段/文件|规范化位置|采用的语义或限制|
|---|---|---|
|ROADEF `config.csv` 恢复起止日期、时间|`scenario.recovery_window`|GMT 作为 UTC；日期和显式跨日偏移一起解析|
|`flights.csv` 航班号、起讫机场、起降时刻；`rotations.csv` 日期和飞机|`scenario.flights`、`source.records`|按日期展开，标识如 `R147_20060107`，不能仅按航班号关联|
|`aircraft.csv` 机尾、机型、逐舱座位、过站时间|`scenario.aircraft`、`capacity_profile`、飞机串配置|保留原机型和舱位配置；研究设备键包含机型、座位配置和过站分钟；运力合为单舱|
|`aircraft.csv` 家族、航程、运营成本、旅客过站、维护等其他字段|`source.raw_tables`|不自动转成研究成本；维护语义未接入，相关实例预检拒绝|
|`alt_aircraft.csv` 机尾及不可用起止|`scenario.aircraft[].unavailable`|候选执行区间不得与不可用区间重叠；保留源记录|
|`alt_flights.csv` 日期航班及延误/取消|`fixed_delay`、`strategic_flag`、`cancel_required`、`earliest_departure`|固定执行航班禁止取消/换机/再改时；原取消必须取消；范围外的固定延误预检拒绝|
|`airports.csv`、`alt_airports.csv`|`source.raw_tables`|原机场小时容量及容量扰动暂不进入统一研究子模型；原规则检查另行执行|
|`itineraries.csv` 旅客组人数及带日期航段|`scenario.passengers`、旅客候选|只使用完整落入已选航班的原始整组；没有拆分或补充虚构需求|
|`itineraries.csv` 原票价、旅客类别、舱等|`source.raw_tables`、排除旅客上下文|原值保留；当前 PRM 不使用原票价/舱等计分；连接时间使用冻结研究配置，非原规则逐项复现|
|`position(s).csv`、`groundTranspCom.csv`、航班串字段|`source.raw_tables`|终端按研究机尾硬边界；原机型/配置软惩罚、地面交通、联程规则交由外评检查|
|固定窗口外原轮转与源扰动|`fixed_context.flights`；飞机 `ready_at`、`available_until` 和显式边界标记|不作为可调整航段；保留回接条件，不创建虚拟机组或虚拟调机|
|Delft HDF 分类块及分类字典|`source.records[].raw` 的业务字符串|恢复机场、机尾、事件类型，底层分类码不是业务 ID；不反序列化可执行 pickle|
|计划航班 `FLIGHT_NO`、计划起飞、起讫机场|`source.records`、组合匹配键|派生 ID 为 `D<原始HDF行>`；相同航班号的不同日期/航线不能混连|
|计划起降时刻|`scenario.flights` 的计划时刻和飞行时长|保持计划飞行时长，不用实际到达观测生成可变飞行时长|
|`Disruptions` 的 `Delay` 与 `DEPARTURE_DELAY`|最早起飞界及源时间边界候选|公开派生静态模型：正起飞延误为下界；负值保留但不生成提前候选；不宣称重现动态信息过程|
|真正的 `ARRIVAL_DELAY`|固定前缀的观测到达上下文|带尾部空格的同名列另行保留；不覆盖真正列，不将字符串 `nan` 当作数值|
|`AC Unavailable` 或机尾不一致事件|`precheck_issues`、源事件原文|没有可核验事件区间语义时拒绝，不假设机场关闭|
|`ACType.csv`、`TAT.csv`|机型、公布座位及机型最小过站分钟|使用机型辅助表；计划 HDF 中的其他 `TAT` 原值仍保留，不混用未确认的单位/定义|
|`PAX_ECONOMY`、`PAX_BUSINESS`|源记录、事后逐航段人数暴露|不当作完整 OD 行程，不构造 Delft PRM 需求|
|`Connections` 的两航班号、计划时刻、三机场、人数|`source_connections.json`；事后连接评价|两个航段分别按组合键匹配；保留窗口外标记；缺少上下文/最小连接时间时标为未知|
|`Airports.csv` 的 `min_connection`|事后连接影响评价|使用公布分钟值并核对原文件哈希；不将连接人数直接算作独立旅客人数|
|Delft 2019 文件、表、Iteration、run、单元格|`reference-2019/rows.jsonl`|每条观测可回溯；汇总/辅助行保留并单独分类|
|2019 公式、缓存值、CV、发布者状态|公式/缓存/错误列及 `eligible_reference`|CV 非零、公式错误或缓存缺失不进入合法参考分布；发布者状态不是我方认证|
|2019 runtime、iterationtime、setup、time-to-best/optimal|事后分表时间分布|不同定义的时间分别统计，不混合成同一种求解时长，不与我方不同输入直接算加速比|

统一研究成本冻结在 `public_air_linear_v1`，沿用 v3 测试系数作为明确的实现假设。飞机、旅客组件开关分别保存；CRM 永久关闭于公开入口。每项研究最优结论只覆盖实际候选域及上述研究规则，不能自动推广到保留但未施加的原规则。
