import { object } from "./state";
import type { DraftDocument } from "./types";

export function objectiveHelp(doc: DraftDocument | null): string {
  const bundle = object(doc?.solve_bundle);
  const xma = bundle.schema_version === "xma-solve-1.0";
  if (xma && bundle.objective_profile === "tianchi_2017") return "最小化：Z = Σ航班 wᶠ(1200·取消ᶠ + 100·延误分钟ᶠ/60) + Σ换机 wᶠκᶠ + Σ留乘人数·g(h) + Σ改签人数·r(h) + 4·未服务人数。\nκᶠ：原计划起飞不晚于调整起日16:00为15，否则为5；wᶠ为航班重要系数，h为小时。\ng(h)：h≤0为0；(0,2]为1；(2,4]为1.5；(4,8]为2；(8,36]为3；更大为10⁹。\nr(h)：先将h截为非负，h<6为h/30；h<24为h/24；h<36为h/18；h≤48为h/16；更大为10⁹。\n非可调整航班的留乘和改签延误计分按后端规则豁免；评分以运行审计及独立重算为准。";
  const coefficients = xma ? object(bundle.air_objective) : object(bundle.cost_overrides);
  const keys = xma ? ["flight_cancellation", "flight_delay_per_minute", "aircraft_reassignment", "passenger_delay_per_pax_minute", "unserved_passenger"] : ["flight_cancellation", "flight_delay_per_minute", "origin_change", "destination_change", "aircraft_reassignment", "ferry_per_minute", "crew_reassignment", "deadhead_per_minute", "passenger_delay_per_pax_minute", "unserved_passenger"];
  const names: Record<string, string> = { flight_cancellation: "取消每班", flight_delay_per_minute: "航班每延误分钟", origin_change: "更改出发机场", destination_change: "更改到达机场", aircraft_reassignment: "换机每次", ferry_per_minute: "调机每分钟", crew_reassignment: "换组每次", deadhead_per_minute: "机组置位每分钟", passenger_delay_per_pax_minute: "旅客每人每延误分钟", unserved_passenger: "未服务每人" };
  return `${xma ? "厦航 AIR 线性研究成本" : "AIR 联合恢复成本"}：\n最小化 Z = C航班 + C飞机 + ${xma ? "" : "C机组 + "}C旅客。\nC航班 = Σ(取消系数×取消 + 延误系数×延误分钟${xma ? "" : " + 出发/到达机场变更成本"})。\nC飞机 = Σ换机成本${xma ? "。" : " + 调机分钟成本。\nC机组 = Σ换组成本 + 置位分钟成本。"}\nC旅客 = Σ(人数×延误分钟×延误系数 + 未服务人数×未服务系数)。\n当前${xma ? "系数" : "覆盖系数（未覆盖项沿用基准配置）"}：\n${keys.map(key => `${names[key]}：${coefficients[key] ?? "基准配置，见审计快照"}`).join("；")}。\n不与天池评分混合比较；最终系数与目标重算以运行快照为准。`;
}

export const algorithmHelp: Record<string, string> = {
  joint_arc_flow: "直接联合优化：用航班候选、飞机网络流及旅客分配构建一个联合整数模型，由求解器进行分支定界。最优结论需有合法完整方案及闭合的全局上下界。",
  joint_path_oracle: "显式航班串 Oracle：枚举飞机可行路径，再联合优化航班与旅客。用于小实例对拍；路径数增长很快，路径上限或资源限制不等于认证不可行。",
  benders_joint: "Benders＋联合子问题：主问题选择航班计划，子问题联合检查资源与旅客；通过有效割收紧主问题。当前实现对适中规模还加入资源、旅客 LP 强化；需全局界闭合才证明最优。",
  benders_cg_bp: "Benders＋列生成 / 分支定价：主问题协调航班计划，资源子问题按需定价生成列，并通过分支处理整数性。列生成停止须有无改进列的定价证据，仅受限主问题收敛不足以证明全局最优。",
  air: "AIR Benders＋Branch & Price：主问题协调航班与旅客，飞机串及机组任务串按需定价生成，通过分支处理整数性。合法完整方案经独立审计给出 UB，定价及有效松弛给出全局 LB，容差内闭合后才证明最优。",
};
