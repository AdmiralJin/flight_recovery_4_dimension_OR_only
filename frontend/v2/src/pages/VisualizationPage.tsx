import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Eye, Filter, GitBranch, Plane, RefreshCw } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Chart, type ChartClickEvent } from "../components/Chart";
import { PanelToggle, useDetailPanel } from "../components/PanelToggle";
import { useWorkbench } from "../store";
import { useTheme, type ThemeMode } from "../theme";
import type { JsonObject, VisualizationFlight, VisualizationMode, VisualizationModel, VisualizationView } from "../types";
import {
  capacityOption,
  costOption,
  delayOption,
  flightNetworkOption,
  ganttOption,
  propagationOption,
} from "../visualization/chartOptions";
import { PageHead } from "./DataStudio";

const modes: Array<{ key: VisualizationMode; label: string }> = [
  { key: "original", label: "Original" },
  { key: "impact", label: "Impact" },
  { key: "recovered", label: "Recovered" },
  { key: "delta", label: "Delta" },
];

const views: Array<{ key: VisualizationView; label: string }> = [
  { key: "flights", label: "航班时空图" },
  { key: "aircraft", label: "飞机甘特" },
  { key: "crew", label: "机组甘特" },
  { key: "passengers", label: "旅客行程" },
  { key: "capacity", label: "容量热力图" },
  { key: "propagation", label: "传播链" },
  { key: "cost", label: "成本" },
  { key: "delay", label: "延误" },
];

const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);

export function VisualizationPage() {
  const state = useWorkbench();
  const { theme } = useTheme();
  const detailPanel = useDetailPanel();
  const [params, setParams] = useSearchParams();
  const [view, setView] = useState<VisualizationView>(() => validView(params.get("view")));
  const [scope, setScope] = useState<"all" | "changed" | "unchanged">((params.get("scope") as "all") || "all");
  const [airport, setAirport] = useState(params.get("airport") ?? "all");
  const [exposure, setExposure] = useState<"all" | "direct" | "downstream" | "normal">((params.get("exposure") as "all") || "all");
  const [movement, setMovement] = useState<"departure" | "arrival">((params.get("movement") as "departure") || "departure");
  const runSource = state.run && terminal.has(state.run.job_status) ? state.run : null;
  const modelQuery = useQuery({
    queryKey: ["visualization", runSource?.run_id ?? state.draft?.draft_id],
    queryFn: () => runSource ? api.visualization(runSource.run_id) : api.draftVisualization(state.draft!.draft_id),
    enabled: Boolean(runSource || state.draft),
  });
  const model = modelQuery.data;
  const mode = state.mode as VisualizationMode;

  useEffect(() => {
    if (!model) return;
    const requested = params.get("mode") as VisualizationMode | null;
    const preferred = requested && model.mode_availability[requested]?.available ? requested : model.mode_availability.delta.available ? "delta" : model.mode_availability.impact.available ? "impact" : "original";
    if (!model.mode_availability[mode]?.available || (requested && requested !== mode)) state.set({ mode: preferred });
  }, [model?.source_id]);

  useEffect(() => {
    const next = new URLSearchParams(params);
    next.set("view", view); next.set("mode", mode); next.set("scope", scope); next.set("exposure", exposure); next.set("movement", movement);
    if (airport === "all") next.delete("airport"); else next.set("airport", airport);
    if (state.selectedEntity) { next.set("selectedType", state.selectedEntity.type); next.set("selected", state.selectedEntity.id); }
    else { next.delete("selectedType"); next.delete("selected"); }
    if (next.toString() !== params.toString()) setParams(next, { replace: true });
  }, [view, mode, scope, exposure, movement, airport, state.selectedEntity?.type, state.selectedEntity?.id]);

  useEffect(() => {
    const id = params.get("selected"); const type = params.get("selectedType");
    if (id && ["flight", "aircraft", "crew", "passenger", "capacity"].includes(type ?? "") && !state.selectedEntity) {
      state.set({ selectedEntity: { type: type as "flight", id }, selectedId: type === "flight" ? id : null });
    }
  }, [model?.source_id]);

  if (!state.draft && !runSource) return <div className="page"><PageHead eyebrow="04 / VISUALIZE" title="运营可视化" description="请先选择草稿或历史运行。" /></div>;
  if (modelQuery.isLoading) return <div className="page"><PageHead eyebrow="04 / VISUALIZE" title="运营可视化" description="正在构建与输入 hash 绑定的规范化可视化模型。" /><div className="empty-state large"><RefreshCw /><h2>加载可视化模型…</h2></div></div>;
  if (!model || modelQuery.isError) return <div className="page"><PageHead eyebrow="04 / VISUALIZE" title="运营可视化" description="无法加载可视化模型。" /><div className="empty-note" role="alert">{modelQuery.error instanceof Error ? modelQuery.error.message : "可视化数据不可用"}</div></div>;

  const airports = [...new Set(model.flights.flatMap((item) => [String(item.original.origin), String(item.original.destination)]))];
  const entityChoices = choicesForView(model as unknown as JsonObject, view);
  const filteredFlights = model.flights.filter((item) =>
    (scope === "all" || (scope === "changed" ? item.changed : !item.changed))
    && (airport === "all" || item.original.origin === airport || item.original.destination === airport || item.recovered?.recovered_origin === airport || item.recovered?.recovered_destination === airport)
    && (exposure === "all" || item.impact.status === exposure));
  const selected = findSelected(model as unknown as JsonObject, state.selectedEntity);
  const unavailable = viewUnavailable(model.layer_availability, view, mode);
  const viewModel = filterVisualizationModel(model, filteredFlights, airport);
  const chart = unavailable ? null : buildChart(viewModel, view, mode, filteredFlights, state.selectedId, movement, theme);
  const selectFromChart = (event: ChartClickEvent) => {
    const data = event.data as { entityId?: string; entityType?: string } | undefined;
    if (!data?.entityId || !data.entityType) return;
    const type = normalizeEntityType(data.entityType);
    state.set({ selectedEntity: { type, id: data.entityId }, selectedId: type === "flight" ? data.entityId : null });
  };

  return <div className="page visualization-page">
    <PageHead eyebrow="04 / VISUALIZE" title="运营可视化" description="在同一时间轴上核对原计划、扰动暴露、恢复方案和差异；传播风险是规则证据，不是决策因果解释。">
      <label className="compact-select"><span className="sr-only">可视化数据源</span><select value={runSource?.run_id ?? "draft"} onChange={(event) => {
        if (event.target.value === "draft") state.selectRun(null);
        else { const run = state.runs.find((item) => item.run_id === event.target.value); if (run) state.selectRun(run); }
      }}><option value="draft">当前草稿 / 编译预览</option>{state.runs.filter((item) => terminal.has(item.job_status)).map((run) => <option key={run.run_id} value={run.run_id}>{run.run_id.slice(0, 8)} · {run.optimization_status ?? run.job_status}</option>)}</select></label>
    </PageHead>

    <section className="viz-command" aria-label="可视化控制">
      <div className="segmented" role="tablist" aria-label="计划语义模式">{modes.map((item) => <button key={item.key} type="button" role="tab" aria-selected={mode === item.key} disabled={!model.mode_availability[item.key].available} title={model.mode_availability[item.key].reason ?? item.label} onClick={() => state.set({ mode: item.key })}>{item.label}</button>)}</div>
      <div className="viz-filters"><label><Eye /><span>实体</span><select aria-label="选择联动实体" value={state.selectedEntity ? `${state.selectedEntity.type}:${state.selectedEntity.id}` : ""} onChange={(event) => { const choice = entityChoices.find((item) => `${item.type}:${item.id}` === event.target.value); state.set({ selectedEntity: choice ? { type: choice.type, id: choice.id } : null, selectedId: choice?.type === "flight" ? choice.id : null }); }}><option value="">未选择</option>{entityChoices.map((item) => <option key={`${item.type}:${item.id}`} value={`${item.type}:${item.id}`}>{item.id}</option>)}</select></label><label><Filter /><span>机场</span><select value={airport} onChange={(event) => setAirport(event.target.value)}><option value="all">全部</option>{airports.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><label><span>范围</span><select value={scope} onChange={(event) => setScope(event.target.value as typeof scope)}><option value="all">全部</option><option value="changed">Changed</option><option value="unchanged">Unchanged</option></select></label><label><span>暴露</span><select value={exposure} onChange={(event) => setExposure(event.target.value as typeof exposure)}><option value="all">全部</option><option value="direct">直接</option><option value="downstream">传播</option><option value="normal">正常</option></select></label>{view === "capacity" && <label><span>容量方向</span><select value={movement} onChange={(event) => setMovement(event.target.value as typeof movement)}><option value="departure">起飞</option><option value="arrival">到达</option></select></label>}</div>
    </section>

    <nav className="entity-tabs visualization-tabs" role="tablist" aria-label="可视化类型">{views.map((item) => <button key={item.key} type="button" role="tab" aria-selected={view === item.key} onClick={() => setView(item.key)}>{item.label}</button>)}</nav>

    <section className="viz-summary" aria-label="可视化数据摘要"><div><span>数据源</span><strong>{model.source_type === "run" ? `Run ${model.run_id?.slice(0, 8)}` : "Working copy"}</strong></div><div><span>输入 hash</span><code>{(model.input_hash ?? model.compiled_hash ?? model.working_hash)?.slice(0, 12) ?? "—"}</code></div><div><span>UTC 范围</span><strong>{shortUtc(model.time_range.start)} – {shortUtc(model.time_range.end)}</strong></div><div><span>当前航班</span><strong>{filteredFlights.length} / {model.flights.length}</strong></div></section>

    <div className={`visual-layout visualization-stage ${detailPanel.open ? "" : "is-panel-collapsed"}`}><section className="visual-card"><div className="card-head"><div><span>核心视觉 · {mode.toUpperCase()}</span><h2>{views.find((item) => item.key === view)?.label}</h2></div><div className="card-head-tools"><div className="viz-legend"><span className="swatch direct">直接扰动</span><span className="swatch downstream">传播风险</span><span className="swatch recovered">恢复计划</span><span className="swatch ghost">原计划 ghost</span></div><PanelToggle open={detailPanel.open} onToggle={() => detailPanel.setOpen(!detailPanel.open)} label="证据栏" /></div></div>{unavailable ? <div className="empty-state chart-empty"><AlertTriangle /><h3>当前图层不可用</h3><p>{unavailable}</p></div> : chart ? <Chart option={chart} label={`${mode} ${views.find((item) => item.key === view)?.label}`} theme={theme} height={Math.max(480, Math.min(760, chartHeight(model, view)))} onClick={selectFromChart} /> : <div className="empty-state chart-empty"><Eye /><h3>没有可绘制的数据</h3></div>}</section>{detailPanel.open && <EvidencePanel selected={selected} model={model as unknown as JsonObject} />}</div>
  </div>;
}

function buildChart(model: VisualizationModel, view: VisualizationView, mode: VisualizationMode, flights: VisualizationFlight[], selectedId: string | null, movement: "departure" | "arrival", theme: ThemeMode) {
  if (view === "flights") return flightNetworkOption(model, mode, flights, selectedId, theme);
  if (view === "aircraft" || view === "crew" || view === "passengers") return ganttOption(model, view, mode, theme);
  if (view === "capacity") return capacityOption(model, mode, movement, theme);
  if (view === "propagation") return propagationOption(model, selectedId, theme);
  if (view === "cost") return costOption(model, theme);
  return delayOption(model, theme);
}

function EvidencePanel({ selected, model }: { selected: JsonObject | null; model: JsonObject }) {
  return <aside className="detail-panel evidence-panel"><h2>实体证据</h2>{selected ? <><div className="evidence-identity"><Plane /><div><span>{String(selected.flight_id ?? selected.aircraft_id ?? selected.crew_id ?? selected.pax_group_id ?? "实体")}</span><strong>{String(selected.primary_change ?? selected.status ?? "已选择")}</strong></div></div><dl>{evidenceRows(selected).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl><details><summary>规范化数据</summary><pre className="json-block">{JSON.stringify(selected, null, 2)}</pre></details></> : <div className="empty-note"><GitBranch />选择图中的航班、资源、旅客或容量区间，查看跨图一致的原计划、暴露和恢复证据。</div>}<div className="evidence-boundary"><AlertTriangle /><p>扰动暴露和资源传播仅表示可核对的风险证据，不声明其导致了某项恢复决策。</p></div><details><summary>图层可用性</summary><pre className="json-block">{JSON.stringify(model.layer_availability, null, 2)}</pre></details></aside>;
}

function evidenceRows(item: JsonObject): Array<[string, string]> {
  const impact = item.impact as JsonObject | undefined;
  const resources = item.resources as JsonObject | undefined;
  return [
    ["Changed", String(item.changed ?? "—")],
    ["变化标签", Array.isArray(item.change_flags) ? item.change_flags.join(", ") : "—"],
    ["暴露", String(impact?.status ?? "—")],
    ["直接规则", Array.isArray(impact?.direct_rule_ids) ? impact.direct_rule_ids.join(", ") || "—" : "—"],
    ["原飞机", String(resources?.original_aircraft ?? item.equipment_type ?? "—")],
    ["恢复飞机", String(resources?.recovered_aircraft ?? item.actual_final_station ?? "—")],
    ["原机组", String(resources?.original_crew ?? item.rating ?? "—")],
    ["恢复机组", String(resources?.recovered_crew ?? "—")],
  ];
}

function findSelected(model: JsonObject, selected: { type: string; id: string } | null): JsonObject | null {
  if (!selected) return null;
  const mapping: Record<string, [string, string]> = { flight: ["flights", "flight_id"], aircraft: ["aircraft", "aircraft_id"], crew: ["crew", "crew_id"], passenger: ["passengers", "pax_group_id"] };
  const target = mapping[selected.type];
  if (!target) return null;
  return ((model[target[0]] as JsonObject[]) ?? []).find((item) => String(item[target[1]]) === selected.id) ?? null;
}

function viewUnavailable(layers: Record<string, { available: boolean; reason?: string | null }>, view: VisualizationView, mode: VisualizationMode) {
  const layer = view === "flights" ? "flights" : view === "passengers" ? "passengers" : view;
  if (!layers[layer]?.available) return layers[layer]?.reason ?? "图层不可用";
  if (["recovered", "delta"].includes(mode) && ["aircraft", "crew", "passengers"].includes(view)) {
    const detail = layers[`${view === "passengers" ? "passenger" : view}_recovered_detail`];
    if (detail && !detail.available) return detail.reason ?? "恢复明细不可用";
  }
  return null;
}

function chartHeight(model: VisualizationModel, view: VisualizationView) {
  const rows = view === "aircraft" ? model.aircraft.length : view === "crew" ? model.crew.length : view === "passengers" ? model.passengers.length : 6;
  return rows * 54 + 150;
}

function normalizeEntityType(value: string): "flight" | "aircraft" | "crew" | "passenger" | "capacity" {
  if (value === "aircraft" || value === "crew" || value === "passenger" || value === "capacity") return value;
  return "flight";
}

function filterVisualizationModel(model: VisualizationModel, flights: VisualizationFlight[], airport: string): VisualizationModel {
  const ids = new Set(flights.map((item) => item.flight_id));
  const referencesFlight = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(referencesFlight);
    if (!value || typeof value !== "object") return false;
    const item = value as JsonObject;
    return (typeof item.flight_id === "string" && ids.has(item.flight_id)) || Object.values(item).some(referencesFlight);
  };
  const noFlightFilter = ids.size === model.flights.length;
  return {
    ...model,
    flights,
    aircraft: model.aircraft.filter((item) => noFlightFilter || referencesFlight(item)),
    crew: model.crew.filter((item) => noFlightFilter || referencesFlight(item)),
    passengers: model.passengers.filter((item) => noFlightFilter || referencesFlight(item)),
    propagation_edges: model.propagation_edges.filter((item) => ids.has(String(item.source_flight_id)) && ids.has(String(item.target_flight_id))),
    capacity: Object.fromEntries(Object.entries(model.capacity).map(([key, rows]) => [key, rows.filter((row) => airport === "all" || row.airport_id === airport)])),
    delay_distribution: model.delay_distribution.filter((item) => ids.has(String(item.flight_id))),
  };
}

function choicesForView(model: JsonObject, view: VisualizationView): Array<{ type: "flight" | "aircraft" | "crew" | "passenger" | "capacity"; id: string }> {
  if (view === "aircraft") return ((model.aircraft as JsonObject[]) ?? []).map((item) => ({ type: "aircraft", id: String(item.aircraft_id) }));
  if (view === "crew") return ((model.crew as JsonObject[]) ?? []).map((item) => ({ type: "crew", id: String(item.crew_id) }));
  if (view === "passengers") return ((model.passengers as JsonObject[]) ?? []).map((item) => ({ type: "passenger", id: String(item.pax_group_id) }));
  return ((model.flights as JsonObject[]) ?? []).map((item) => ({ type: "flight", id: String(item.flight_id) }));
}

function validView(value: string | null): VisualizationView { return views.some((item) => item.key === value) ? value as VisualizationView : "flights"; }
function shortUtc(value: unknown) { const parsed = Date.parse(String(value ?? "")); return Number.isFinite(parsed) ? new Date(parsed).toISOString().slice(5, 16).replace("T", " ") : "—"; }
