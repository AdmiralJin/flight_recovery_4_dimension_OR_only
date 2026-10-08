import { useState } from "react";
import { Filter, GitCompareArrows } from "lucide-react";
import { Chart } from "../components/Chart";
import { PanelToggle, useDetailPanel } from "../components/PanelToggle";
import { TimeSpaceNetwork } from "../components/TimeSpaceNetwork";
import { VirtualTable } from "../components/VirtualTable";
import { useWorkbench } from "../store";
import { useTheme, type ThemeMode } from "../theme";
import type { ComparisonFlight, JsonObject } from "../types";
import { comparisonCapacityOption, comparisonCostOption, comparisonDelayOption } from "../visualization/chartOptions";
import { PageHead } from "./DataStudio";

const modes = ["original", "impact", "recovered", "delta"] as const;
const entities = [["flights", "航班网络"], ["aircraft", "飞机轮转"], ["crew", "机组任务"], ["passengers", "旅客行程"], ["capacity", "容量"], ["cost", "成本"], ["delay", "延误"]] as const;

export function ComparePage() {
  const state = useWorkbench();
  const { theme } = useTheme();
  const detailPanel = useDetailPanel();
  const [entity, setEntity] = useState<typeof entities[number][0]>("flights");
  const [scope, setScope] = useState<"all" | "changed" | "unchanged">("all");
  const comparison = state.comparison;
  if (!comparison) return <div className="page"><PageHead eyebrow="05 / COMPARE" title="方案对比" description="请选择一个已完成的运行；非 optimal 仍可查看 Original 与 Impact。" /><div className="empty-state large"><GitCompareArrows /><h2>尚无对比模型</h2><p>从“求解”页选择运行，服务端会生成统一语义的 canonical comparison。</p></div></div>;
  const flights = comparison.flights.filter((item) => scope === "all" || (scope === "changed" ? item.changed : !item.changed));
  const network = networkFlights(flights, state.mode);
  const selected = comparison.flights.find((item) => item.flight_id === state.selectedId);
  return <div className="page compare-page"><PageHead eyebrow="05 / COMPARE" title="方案对比" description="四种模式同步约束全页语义；风险暴露与求解决策严格分离。"><div className="segmented" role="tablist" aria-label="对比模式">{modes.map((mode) => <button key={mode} role="tab" type="button" disabled={mode === "recovered" && !comparison.recovered_available} aria-selected={state.mode === mode} onClick={() => state.set({ mode })}>{modeLabel(mode)}</button>)}</div></PageHead>
    <section className="comparison-summary"><div><span>航班总数</span><strong>{comparison.counts.total_flights}</strong></div><div className="changed"><span>Changed</span><strong>{comparison.counts.changed_flights}</strong></div><div><span>Unchanged</span><strong>{comparison.counts.unchanged_flights}</strong></div><p>{comparison.mode_semantics[state.mode]}</p></section>
    <div className="entity-tabs compare-tabs" role="tablist" aria-label="对比实体">{entities.map(([key, label]) => <button key={key} role="tab" type="button" aria-selected={entity === key} onClick={() => setEntity(key)}>{label}</button>)}</div>
    {entity === "flights" && <div className={`visual-layout ${detailPanel.open ? "" : "is-panel-collapsed"}`}><section className="visual-card"><div className="card-head"><div><span>核心视觉 · {state.mode.toUpperCase()}</span><h2>航班时空网络</h2></div><div className="card-head-tools"><label className="compact-select"><Filter /><span className="sr-only">变化筛选</span><select value={scope} onChange={(event) => setScope(event.target.value as typeof scope)}><option value="all">全部航班</option><option value="changed">仅 Changed</option><option value="unchanged">仅 Unchanged</option></select></label><PanelToggle open={detailPanel.open} onToggle={() => detailPanel.setOpen(!detailPanel.open)} label="航班证据" /></div></div><TimeSpaceNetwork flights={network.rows} impacts={network.impacts} selectedId={state.selectedId} onSelect={(selectedId) => state.set({ selectedId })} label={`${state.mode} 航班时空网络`} /></section><aside className="detail-panel" hidden={!detailPanel.open}><h2>航班证据</h2>{selected ? <FlightDetail flight={selected} mode={state.mode} /> : <div className="empty-note">选择图中的航班，查看原计划、扰动暴露、恢复结果和全部变化标签。</div>}</aside></div>}
    {entity !== "flights" && <EntityVisual entity={entity} comparison={comparison as unknown as JsonObject} theme={theme} />}
  </div>;
}

function networkFlights(flights: ComparisonFlight[], mode: string) {
  if (mode === "delta") return { rows: flights, impacts: [] };
  if (mode === "recovered") return { rows: flights.flatMap((item) => item.recovered && item.recovered.status !== "cancelled" ? [{ flight_id: item.flight_id, origin: item.recovered.recovered_origin, destination: item.recovered.recovered_destination, sched_dep: item.recovered.recovered_dep, sched_arr: item.recovered.recovered_arr }] as JsonObject[] : []), impacts: [] };
  return { rows: flights.map((item) => ({ flight_id: item.flight_id, ...item.original })), impacts: mode === "impact" ? flights.map((item) => item.impact) : [] };
}

function FlightDetail({ flight, mode }: { flight: ComparisonFlight; mode: string }) {
  return <div className="flight-detail"><div className="detail-id"><strong>{flight.flight_id}</strong><span className={`change-pill state-${flight.primary_change}`}>{flight.primary_change}</span></div><div className="tag-row">{flight.change_flags.map((flag) => <span key={flag}>{flag}</span>)}</div><dl>{mode !== "recovered" && Object.entries(flight.original).slice(0, 8).map(([key, value]) => <div key={`o-${key}`}><dt>Original · {key}</dt><dd>{String(value)}</dd></div>)}{mode === "impact" && <><div><dt>Exposure</dt><dd>{flight.impact.status}</dd></div><div><dt>Rules</dt><dd>{flight.impact.direct_rule_ids.join(", ") || "—"}</dd></div></>}{["recovered", "delta"].includes(mode) && flight.recovered && Object.entries(flight.recovered).slice(0, 10).map(([key, value]) => <div key={`r-${key}`}><dt>Recovered · {key}</dt><dd>{String(value)}</dd></div>)}</dl></div>;
}

function EntityVisual({ entity, comparison, theme }: { entity: string; comparison: JsonObject; theme: ThemeMode }) {
  if (["aircraft", "crew", "passengers"].includes(entity)) {
    const rows = (comparison[entity] as JsonObject[]) ?? [];
    return <section className="visual-card wide"><div className="card-head"><div><span>实体对比</span><h2>{entities.find(([key]) => key === entity)?.[1]}</h2></div></div><VirtualTable rows={rows} /></section>;
  }
  if (entity === "capacity") {
    const capacity = comparison.capacity as Record<string, JsonObject[]>;
    const rows = capacity?.recovered?.length ? capacity.recovered : capacity?.effective ?? [];
    const option = comparisonCapacityOption(rows, theme);
    return <section className="visual-card wide"><div className="card-head"><div><span>基线 / 有效 / 恢复</span><h2>机场容量与负荷</h2></div></div><Chart option={option} label="机场容量和负荷图" theme={theme} height={500} /></section>;
  }
  if (entity === "cost") {
    const objective = (comparison.objective ?? {}) as Record<string, number>;
    const option = comparisonCostOption(objective, theme);
    return <section className="visual-card wide"><div className="card-head"><div><span>Objective decomposition</span><h2>成本四分量</h2></div><strong>{objective.total?.toLocaleString() ?? "—"}</strong></div><Chart option={option} label="成本四分量柱状图" theme={theme} height={480} /></section>;
  }
  const rows = (comparison.delay_distribution as JsonObject[]) ?? [];
  const option = comparisonDelayOption(rows, theme);
  return <section className="visual-card wide"><div className="card-head"><div><span>Distribution</span><h2>起飞 / 到达延误</h2></div></div><Chart option={option} label="航班延误分布" theme={theme} height={500} /></section>;
}

function modeLabel(mode: string) { return ({ original: "Original", impact: "Impact", recovered: "Recovered", delta: "Delta" } as Record<string, string>)[mode]; }
