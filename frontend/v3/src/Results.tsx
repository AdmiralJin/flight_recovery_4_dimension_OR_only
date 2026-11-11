import { memo, useCallback, useDeferredValue, useMemo, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { useQuery } from "@tanstack/react-query";
import { Download, Filter, RefreshCw } from "lucide-react";
import { api } from "./api";
import { Button, Card, DataTable, Empty, JsonDetails, JsonView, LazyDetails, Message, Modal } from "./components";
import { Chart } from "./Chart";
import { chooseRun, download, downloadFile, execute, isDirty, object, rows, statusLabel, useWb } from "./state";
import { numberText } from "./Run";
import type { JsonObject, VisualizationMode, VisualizationModel, VisualizationView } from "./types";
import { analysisOption, chartLegend } from "./analysisCharts";
import { Term, Help } from "./Help";

const modes: Array<[VisualizationMode, string]> = [["original", "原计划"], ["impact", "扰动影响"], ["recovered", "恢复方案"], ["delta", "变化对比"]];
const sections = [["resources", "航班与资源"], ["passengers", "旅客与容量"], ["cost", "成本与延误"], ["audit", "审计与导出"]];
export const Results = memo(function Results() {
  const state = useWb(useShallow(s => ({ draft: s.draft, document: s.document, rawText: s.rawText, runtimeEdits: s.runtimeEdits, run: s.run, busy: s.busy, theme: s.theme })));
  const [source, setSource] = useState("run");
  const [section, setSection] = useState("resources");
  const [wantedMode, setMode] = useState<VisualizationMode>("original");
  const [view, setView] = useState<VisualizationView>("flights");
  const [filter, setFilter] = useState("");
  const query = useDeferredValue(filter.trim().toLowerCase());
  const searchCache = useRef(new WeakMap<object, string>());
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [airport, setAirport] = useState("");
  const [scope, setScope] = useState("all");
  const [exposure, setExposure] = useState("all");
  const [movement, setMovement] = useState<"departure" | "arrival">("departure");
  const [selected, setSelected] = useState<string | null>(null);
  const selectFlight = useCallback((row: JsonObject) => setSelected(String(row.flight_id)), []);
  const history = useQuery({ queryKey: ["wb3", "runs"], queryFn: () => api.runs() });
  const useRun = source === "run" && !!state.run;
  const id = useRun ? state.run?.run_id : state.draft?.draft_id;
  const modelQuery = useQuery({ queryKey: ["wb3", "visualization", useRun ? "run" : "draft", id, useRun ? state.run?.job_status : state.draft?.working_hash], queryFn: () => useRun ? api.visualization(id!) : api.draftVisualization(id!), enabled: !!id });
  const comparison = useQuery({ queryKey: ["wb3", "comparison", id, state.run?.job_status], queryFn: () => api.comparison(id!), enabled: useRun && !!id && section === "resources" && comparisonOpen });
  const audit = useQuery({ queryKey: ["wb3", "audit", id, state.run?.job_status], queryFn: () => api.audit(id!), enabled: useRun && !!id && section === "audit" });
  const model = modelQuery.data;
  const mode = model?.mode_availability[wantedMode]?.available ? wantedMode : "original";
  const flights = useMemo(() => (model?.flights ?? []).filter(item => {
    if (airport && ![item.original.origin, item.original.destination, item.recovered?.recovered_origin, item.recovered?.recovered_destination].includes(airport) || scope !== "all" && item.changed !== (scope === "changed") || exposure !== "all" && item.impact.status !== exposure) return false;
    if (!query) return true;
    let text = searchCache.current.get(item);
    if (text === undefined) { text = JSON.stringify(item).toLowerCase(); searchCache.current.set(item, text); }
    return text.includes(query);
  }), [model, query, airport, scope, exposure]);
  const airportChoices = useMemo(() => [...new Set((model?.flights ?? []).flatMap(item => [String(item.original.origin), String(item.original.destination), ...[item.recovered?.recovered_origin, item.recovered?.recovered_destination].filter(Boolean).map(String)]))].sort(), [model]);
  const flightIds = useMemo(() => new Set(flights.map(item => item.flight_id)), [flights]);
  const reduced = useMemo(() => model ? filteredModel(model, flightIds, !!(query || airport || scope !== "all" || exposure !== "all"), airport) : null, [model, flightIds, query, airport, scope, exposure]);
  const activeView = section === "cost" ? "cost" : section === "passengers" ? view === "capacity" ? "capacity" : "passengers" : view;
  const selectedEntity = useMemo(() => {
    if (!model || !selected) return null;
    for (const source of [model.flights, model.aircraft, model.crew, model.passengers, ...Object.values(model.capacity)]) {
      const found = source.find(row => ["flight_id", "aircraft_id", "crew_id", "pax_group_id"].some(key => (row as unknown as JsonObject)[key] === selected));
      if (found) return found;
    }
    return null;
  }, [model, selected]);
  const timezone = model?.time_range.timezone === "Asia/Shanghai" || /\+08:00$/.test(model?.time_range.start ?? "") || (useRun && state.run?.result?.schema_version === "xma-result-1.0") ? "Asia/Shanghai" : "UTC";
  const timeLabel = timezone === "Asia/Shanghai" ? "北京时间 UTC+8" : "UTC";
  const objective = object(model?.objective);
  const unit = objective.profile === "tianchi_2017" ? "天池评分（分）" : "AIR 研究成本";
  const unavailable = model ? unavailableReason(model, activeView, mode) : null;
  const option = useMemo(() => reduced && !unavailable && section !== "audit" ? analysisOption(model!, activeView, mode, state.theme, selected, movement, flightIds, airport, timezone) : null, [reduced, model, unavailable, section, activeView, mode, state.theme, selected, movement, timezone, flightIds, airport]);
  const delay = useMemo(() => reduced && section === "cost" ? analysisOption(model!, "delay", mode, state.theme, selected, movement, flightIds, airport, timezone) : null, [reduced, model, section, mode, state.theme, selected, movement, flightIds, airport, timezone]);
  const tableRows = useMemo(() => flights.map(item => mode === "delta" ? ({ flight_id: item.flight_id, original_dep: formatTime(item.original.sched_dep, timezone), recovered_dep: item.recovered ? formatTime(item.recovered.recovered_dep, timezone) : "—", original_tail: item.original.original_aircraft, recovered_tail: item.recovered?.aircraft_id, departure_delay_minutes: item.recovered?.departure_delay_minutes, primary_change: item.primary_change }) : ({ flight_id: item.flight_id, origin: mode === "recovered" ? item.recovered?.recovered_origin : item.original.origin, destination: mode === "recovered" ? item.recovered?.recovered_destination : item.original.destination, sched_dep: formatTime(mode === "recovered" ? item.recovered?.recovered_dep : item.original.sched_dep, timezone), sched_arr: formatTime(mode === "recovered" ? item.recovered?.recovered_arr : item.original.sched_arr, timezone), changed: item.changed, primary_change: item.primary_change })), [flights, mode, timezone]);
  const allocations = useMemo(() => useRun ? rows(state.run?.result?.passenger_allocations).filter(row => flightIds.has(String(row.flight_id))) : [], [useRun, state.run?.result, flightIds]);
  return <div className="workspace stack" aria-busy={query !== filter.trim().toLowerCase()}>
    <header className="page-head"><div><span className="eyebrow">03 / ANALYZE</span><h1>结果分析</h1><p>以同一视角检查原计划、扰动影响与恢复方案。</p></div><div className="actions"><Button variant="quiet" disabled={!id} onClick={() => modelQuery.refetch()}><RefreshCw size={16}/>刷新</Button><Button disabled={!model} onClick={() => download("visualization.json", model)}><Download size={16}/>导出当前模型</Button></div></header>
    <Card className="source-card"><div className="result-source"><div className="inline-field"><label><span>分析来源</span><select aria-label="分析来源" value={useRun ? "run" : "draft"} onChange={e => { setSource(e.target.value); setSelected(null); }}><option value="draft" disabled={!state.draft}>当前草稿 · 最近保存的输入</option><option value="run" disabled={!state.run}>运行快照 · 历史结果</option></select></label><Help term="分析来源"/></div>{useRun && <div className="inline-field"><label><span>运行记录</span><select aria-label="分析运行记录" value={state.run!.run_id} onChange={e => { const run = history.data?.find(item => item.run_id === e.target.value); if (run) { chooseRun(run); setSelected(null); } }}>{[...(history.data ?? []).filter(item => item.run_id !== state.run!.run_id), state.run!].map(record => <option key={record.run_id} value={record.run_id}>{new Date(record.created_at).toLocaleString("zh-CN")} · {statusLabel(record)} · {record.run_id.slice(0, 8)}</option>)}</select></label><Help term="运行记录"/></div>}<span className="tag">{useRun ? statusLabel(state.run) : "可编辑草稿的保存版本"}</span></div></Card>
    {!id ? <Card><Empty title="暂无可分析的数据">先准备草稿，或在配置与运行中选择历史记录。</Empty></Card> : modelQuery.isPending ? <Card><div className="quiet-state">正在读取分析模型…</div></Card> : modelQuery.isError ? <Message tone="error">分析数据读取失败。<Button onClick={() => modelQuery.refetch()}>重试</Button></Message> : model && <>
      {!useRun && isDirty(state) && <Message tone="warning">当前显示最近保存的输入；本地未保存修改不包含在图表中。</Message>}
      <div className="segmented mode-switch" aria-label="方案模式">{modes.map(([key, label]) => <span className="mode-entry" key={key}><Button aria-pressed={mode === key} disabled={!model.mode_availability[key]?.available} title={model.mode_availability[key]?.reason ?? undefined} onClick={() => setMode(key)}>{label}</Button><Help term={label}/></span>)}</div>
      {modes.some(([key]) => !model.mode_availability[key]?.available) && <details className="mode-reasons"><summary>方案可用性说明</summary>{modes.filter(([key]) => !model.mode_availability[key]?.available).map(([key, label]) => <p key={key}>{label}：{model.mode_availability[key]?.reason ?? "当前数据暂未提供"}</p>)}</details>}
      <nav className="section-tabs" aria-label="分析视图">{sections.map(([key, label]) => <button key={key} aria-current={section === key ? "page" : undefined} onClick={() => { setSection(key); setView(key === "passengers" ? "passengers" : "flights"); }}>{label}</button>)}</nav>
      <div className="metric-grid overview-metrics"><div><span><Term>当前航班 / 总数</Term></span><strong>{flights.length} <small>/ {model.flights.length}</small></strong></div><div><span><Term>发生变化</Term></span><strong>{flights.filter(item => item.changed).length}</strong></div><div><span><Term>直接受扰 / 下游风险</Term></span><strong>{flights.filter(item => item.impact.status === "direct").length} <small>/ {flights.filter(item => item.impact.status === "downstream").length}</small></strong></div><div><span>{unit} · 运行结果</span><strong>{numberText(objective.total)}</strong></div></div>
      {section === "audit" ? !useRun ? <Card><Empty title="审计需要一个运行快照">在配置与运行中选择记录，或切换分析来源。</Empty></Card> : <Card title="审计与复现" note="证据来自本次运行的不可变快照；执行完成与证明最优分别判断。" actions={<Button variant="primary" disabled={!!state.busy} onClick={() => execute("正在导出审计包", () => downloadFile(`/api/v2/runs/${id}/export`, `run-${id}.audit.json`))}>导出完整审计包 <Download size={16}/></Button>}>
        {audit.isPending ? <div className="quiet-state">正在读取审计证据…</div> : audit.isError ? <Message tone="error">审计加载失败。<Button onClick={() => audit.refetch()}>重试</Button></Message> : <div className="stack inset"><Message>{String(audit.data?.evidence_boundary ?? "以保存的审计证据、全局上下界和独立检查为准。")}</Message><div className="metric-grid"><div><span><Term>期望状态对拍</Term></span><strong className="metric-text">{object(audit.data?.expected_check).status_matches === true ? "一致" : object(audit.data?.expected_check).status_matches === false ? "不一致" : "未提供"}</strong></div><div><span><Term>期望目标对拍</Term></span><strong className="metric-text">{object(audit.data?.expected_check).objective_matches === true ? "一致" : object(audit.data?.expected_check).objective_matches === false ? "不一致" : "未提供"}</strong></div></div>{[["输入快照", audit.data?.solve_request], ["决策与恢复动作", { selected: audit.data?.selected, recovery_actions: audit.data?.recovery_actions }], ["目标与上下界", { objective: audit.data?.objective, bounds: audit.data?.bounds }], ["约束独立审计", audit.data?.integrated_audit ?? state.run?.result?.independent_audit], ["诊断与运行环境", { diagnostics: audit.data?.diagnostics, metadata: audit.data?.run_metadata }], ["事件历史", audit.data?.events]].map(([label, data]) => <JsonDetails key={String(label)} summary={<Term>{String(label)}</Term>} value={data}/>)}<Button onClick={() => download("audit.json", audit.data)}>导出审计 JSON</Button></div>}
      </Card> : <>
        <Card className="filter-card"><div className="filter-toolbar"><Filter size={17} aria-hidden="true"/><div className="inline-field"><label><span>筛选</span><input aria-label="筛选分析航班" placeholder="航班 / 机尾 / 旅客…" value={filter} onChange={e => setFilter(e.target.value)}/></label><Help term="筛选"/></div><div className="inline-field"><label><span>机场</span><select aria-label="机场" value={airport} onChange={e => setAirport(e.target.value)}><option value="">全部机场</option>{airportChoices.map(item => <option key={item}>{item}</option>)}</select></label><Help term="机场"/></div><div className="inline-field"><label><span>变化</span><select aria-label="变化" value={scope} onChange={e => setScope(e.target.value)}><option value="all">全部航班</option><option value="changed">发生变化</option><option value="unchanged">没有变化</option></select></label><Help term="变化"/></div><div className="inline-field"><label><span>扰动暴露</span><select aria-label="扰动暴露" value={exposure} onChange={e => setExposure(e.target.value)}><option value="all">全部</option><option value="direct">直接受扰</option><option value="downstream">下游风险</option><option value="normal">正常</option></select></label><Help term="扰动暴露"/></div><Button variant="quiet" onClick={() => { setFilter(""); setAirport(""); setScope("all"); setExposure("all"); setSelected(null); }}>重置</Button></div></Card>
        <Card title={section === "cost" ? "恢复成本构成" : section === "passengers" ? activeView === "capacity" ? "机场容量利用" : "旅客行程" : "航班与资源联动"} note={`${modes.find(([key]) => key === mode)?.[1]} · ${timeLabel} · 点击图表或表格查看证据`} actions={section === "resources" ? <div className="inline-field"><label><span>图层</span><select aria-label="资源图层" value={view} onChange={e => setView(e.target.value as VisualizationView)}>{[["flights", "航班时空"], ["aircraft", "飞机甘特"], ["crew", "机组甘特"], ["propagation", "扰动传播"]].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><Help term="图层"/></div> : section === "passengers" ? <div className="actions"><div className="inline-field"><label><span>图层</span><select aria-label="旅客容量图层" value={activeView} onChange={e => setView(e.target.value as VisualizationView)}><option value="passengers">旅客行程</option><option value="capacity">机场容量</option></select></label><Help term="图层"/></div>{activeView === "capacity" && <select aria-label="容量方向" value={movement} onChange={e => setMovement(e.target.value as "departure" | "arrival")}><option value="departure">起飞</option><option value="arrival">到达</option></select>}</div> : undefined}>
          {chartLegend(activeView, state.theme).length > 0 && <div className="chart-legend" aria-label="图例">{chartLegend(activeView, state.theme).map(item => <span key={item.key}><i style={{ borderColor: item.color, borderTopStyle: item.dashed ? "dashed" : "solid" }}/>{item.label}</span>)}</div>}{unavailable ? <div className="quiet-state">{unavailable}</div> : option && <Chart viewportKey={`${useRun ? "run" : "draft"}:${id}:${model.input_hash ?? model.working_hash}:${activeView}`} option={option} label={`${modes.find(([key]) => key === mode)?.[1]} ${activeView} ${timeLabel}`} onSelect={setSelected} height={Math.min(620, Math.max(340, activeView === "aircraft" ? reduced!.aircraft.length * 46 + 140 : 360))}/>}
        </Card>
        {section === "cost" && <Card title="航班延误（分钟）" note="扰动影响仅表示风险暴露；实际延误来自恢复方案。">{unavailableReason(model, "delay", mode) ? <div className="quiet-state">{unavailableReason(model, "delay", mode)}</div> : <Chart viewportKey={`${id}:delay`} option={delay!} label="航班起飞与到达延误"/>}<DataTable rows={reduced!.delay_distribution}/></Card>}
        {section === "passengers" && allocations.length > 0 && useRun && <Card title="厦航旅客与座位分配" actions={<Button disabled={!!state.busy} onClick={() => execute("正在导出 CSV", () => downloadFile(`/api/v2/xma/runs/${id}/csv`, `xma-${id}.csv`))}>导出天池 11 列结果</Button>}><DataTable rows={allocations}/></Card>}
        <Card title="航班明细" note="与上方筛选一致；点击航班查看原计划、扰动和恢复证据。"><DataTable rows={tableRows} onSelect={selectFlight}/></Card>
        {section === "resources" && useRun && <LazyDetails summary="方案对比与资源汇总" onOpen={() => setComparisonOpen(true)}>{() => comparison.isPending ? <p className="muted">正在读取方案对比…</p> : comparison.isError ? <Message tone="error">方案对比加载失败。<Button onClick={() => comparison.refetch()}>重试</Button></Message> : <JsonView value={comparison.data}/>}</LazyDetails>}
        <JsonDetails summary="来源、可用图层与完整模型" value={{ source_type: model.source_type, source_id: model.source_id, snapshot_id: model.snapshot_id, input_hash: model.input_hash, time_range: model.time_range, layers: model.layer_availability, modes: model.mode_availability, issues: model.issues }}/>
      </>}
    </>}
    {selected && <Modal title={`实体证据 · ${selected}`} onClose={() => setSelected(null)} wide><p className="muted">扰动传播表示可核查的风险关联；具体恢复决策以运行快照和审计为准。</p><EntityEvidence entity={selectedEntity as unknown as JsonObject | null} timezone={timezone}/><JsonDetails summary="完整实体 JSON" value={selectedEntity ?? { entity_id: selected, note: "查看对应图层或完整模型了解此实体。" }}/><Button onClick={() => setSelected(null)}>返回分析</Button></Modal>}
  </div>;
});

function EntityEvidence({ entity, timezone }: { entity: JsonObject | null; timezone: string }) {
  if (!entity) return <p className="muted">在对应图层或完整模型中查看此实体。</p>;
  const original = object(entity.original); const recovered = object(entity.recovered); const impact = object(entity.impact);
  if (entity.flight_id && entity.original) return <div className="evidence-grid"><section><h3>原计划</h3><dl><dt>航线</dt><dd>{String(original.origin)} → {String(original.destination)}</dd><dt>起飞 / 到达</dt><dd>{formatTime(original.sched_dep, timezone)} / {formatTime(original.sched_arr, timezone)}</dd><dt>机尾</dt><dd>{String(original.original_aircraft ?? "—")}</dd></dl></section><section><h3>扰动影响</h3><dl><dt>暴露状态</dt><dd>{{ direct: "直接受扰", downstream: "下游风险", normal: "正常" }[String(impact.status)] ?? "—"}</dd><dt>直接规则</dt><dd>{Array.isArray(impact.direct_rule_ids) && impact.direct_rule_ids.length ? impact.direct_rule_ids.join("、") : "无"}</dd></dl></section><section><h3>恢复方案</h3>{Object.keys(recovered).length ? <dl><dt>状态</dt><dd>{recovered.status === "cancelled" ? "取消" : "执行"}</dd><dt>起飞 / 到达</dt><dd>{formatTime(recovered.recovered_dep, timezone)} / {formatTime(recovered.recovered_arr, timezone)}</dd><dt>起飞延误</dt><dd>{numberText(recovered.departure_delay_minutes)} 分钟</dd><dt>机尾</dt><dd>{String(recovered.aircraft_id ?? "—")}</dd></dl> : <p className="muted">当前输入没有恢复明细。</p>}</section></div>;
  const segments = [...rows(entity.original_segments), ...rows(entity.recovered_segments)];
  return <div className="stack"><p>实体 {String(entity.aircraft_id ?? entity.crew_id ?? entity.pax_group_id ?? "")}</p>{segments.length > 0 && <DataTable rows={segments}/>}</div>;
}

function filteredModel(model: VisualizationModel, ids: Set<string>, filtering: boolean, airport: string): VisualizationModel {
  if (!filtering) return model;
  const filterSegments = (source: JsonObject[]) => source.map(row => ({ ...row,
    original_segments: rows(row.original_segments).filter(segment => !segment.flight_id || ids.has(String(segment.flight_id))),
    recovered_segments: rows(row.recovered_segments).filter(segment => !segment.flight_id || ids.has(String(segment.flight_id))),
    original_duties: rows(row.original_duties).map(duty => ({ ...duty, segments: rows(duty.segments).filter(segment => !segment.flight_id || ids.has(String(segment.flight_id))) })),
    recovered_duties: rows(row.recovered_duties).map(duty => ({ ...duty, segments: rows(duty.segments).filter(segment => !segment.flight_id || ids.has(String(segment.flight_id))) })),
  }));
  return { ...model, flights: model.flights.filter(row => ids.has(row.flight_id)), aircraft: filterSegments(model.aircraft), crew: filterSegments(model.crew), passengers: filterSegments(model.passengers), capacity: Object.fromEntries(Object.entries(model.capacity).map(([key, data]) => [key, data.filter(row => !airport || row.airport_id === airport)])), delay_distribution: model.delay_distribution.filter(row => ids.has(String(row.flight_id))), propagation_edges: model.propagation_edges.filter(row => ids.has(String(row.source_flight_id)) || ids.has(String(row.target_flight_id))) };
}
function unavailableReason(model: VisualizationModel, view: VisualizationView, mode: VisualizationMode) {
  if (["cost", "delay"].includes(view) && mode === "impact") return "扰动影响表示风险暴露，不产生恢复成本或实际延误。";
  if (["cost", "delay"].includes(view) && mode === "original") return null;
  const layer = model.layer_availability[view];
  if (!layer?.available) return layer?.reason ?? "后端未提供此图层。";
  if (["recovered", "delta"].includes(mode) && ["aircraft", "crew", "passengers"].includes(view)) {
    const detail = model.layer_availability[`${view === "passengers" ? "passenger" : view}_recovered_detail`];
    if (detail && !detail.available) return detail.reason ?? "该运行没有恢复明细。";
  }
  return null;
}
const timeFormatters = new Map<string, Intl.DateTimeFormat>();
export function formatTime(value: unknown, timezone: string) {
  const date = new Date(String(value));
  if (Number.isNaN(date.valueOf())) return "—";
  let formatter = timeFormatters.get(timezone);
  if (!formatter) { formatter = new Intl.DateTimeFormat("zh-CN", { timeZone: timezone, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }); timeFormatters.set(timezone, formatter); }
  return formatter.format(date);
}
