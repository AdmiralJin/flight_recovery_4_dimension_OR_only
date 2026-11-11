import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleStop, Clock3, Play, RefreshCw } from "lucide-react";
import { api } from "../api";
import { Chart } from "../components/Chart";
import { PanelToggle, useDetailPanel } from "../components/PanelToggle";
import { useWorkbench } from "../store";
import { useTheme } from "../theme";
import type { RunEvent, RunRecord } from "../types";
import { solveTraceOption } from "../visualization/chartOptions";
import { persistPendingXmaConfig } from "../xmaConfig";
import { XmaResult } from "../components/XmaPanel";
import { PageHead } from "./DataStudio";
import { hydrateRunEvidence } from "./runEvidence";
import { comparableRuns, incumbentChanges, latestMetric, tracePoints, withCurrentDeltas } from "./solveMonitor";

const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);
const stageLabels=["排队","准备输入","生成候选","构建模型","优化求解","独立审计","完成"];

export function SolvePage() {
  const state = useWorkbench();
  const { theme } = useTheme();
  const detailPanel = useDetailPanel();
  const query = useQueryClient();
  const source = useRef<EventSource | null>(null);
  const [runtimeProfile, setRuntimeProfile] = useState("default-exact");
  const [clock,setClock]=useState(Date.now());
  const start = useMutation({ mutationFn: async () => {
    if (!state.draft) throw new Error("请先选择草稿");
    const draft = await persistPendingXmaConfig() ?? state.draft;
    const preview = await api.compile(draft.draft_id);
    state.set({ preview });
    if (!preview.valid) throw new Error("编译未通过，不能创建求解快照");
    const snapshot = await api.snapshot(draft, `Run created ${new Date().toISOString()}`);
    return api.createRun(snapshot.snapshot_id, runtimeProfile);
  }, onSuccess: (run) => { state.selectRun(run); query.invalidateQueries({ queryKey: ["runs"] }); state.set({ message: { tone: "success", text: "最新配置已保存并创建不可变快照，任务已经入队。" } }); },
  onError: (error) => state.set({ message: { tone: "error", text: error instanceof Error ? error.message : "无法启动运行" } }) });
  const cancel = useMutation({ mutationFn: () => api.cancelRun(state.run!.run_id), onSuccess: (run) => state.set({ run, message: { tone: "warning", text: "已请求协作式取消；当前进度会保留。" } }) });

  useEffect(() => {
    if (!state.run || terminal.has(state.run.job_status)) return;
    const timer=window.setInterval(() => setClock(Date.now()),1000);
    return () => window.clearInterval(timer);
  },[state.run?.run_id,state.run?.job_status]);

  useEffect(() => {
    const run = state.run;
    source.current?.close();
    if (!run || terminal.has(run.job_status)) return;
    const stream = new EventSource(`/api/v2/runs/${run.run_id}/events`);
    source.current = stream;
    stream.onmessage = (message) => state.addEvent(JSON.parse(message.data) as RunEvent);
    const eventTypes = ["run_queued", "stage_started", "stage_completed", "benders_iteration", "run_started", "run_completed", "run_failed", "run_cancelled", "study_context", "candidate_generation", "building_model", "model_built", "solver_selected", "solver_fallback", "solver_heartbeat", "mip_progress", "mip_bound", "pricing_iteration", "branch_node", "audit_completed", "solve_bounds"];
    eventTypes.forEach((type) => stream.addEventListener(type, (message) => state.addEvent(JSON.parse((message as MessageEvent).data) as RunEvent)));
    const poll = window.setInterval(async () => {
      const current = await api.run(run.run_id);
      state.set({ run: current });
      if (terminal.has(current.job_status)) {
        stream.close(); window.clearInterval(poll); query.invalidateQueries({ queryKey: ["runs"] });
        await hydrateRunEvidence(current.run_id);
      }
    }, 700);
    return () => { stream.close(); window.clearInterval(poll); };
  }, [state.run?.run_id, state.run?.job_status]);

  const points=useMemo(() => tracePoints(state.events),[state.events]);
  const option=useMemo(() => solveTraceOption(points,theme),[points,theme]);
  const latest=points.at(-1);
  const changes=useMemo(() => incumbentChanges(points),[points]);
  const currentBest=latest?.upper_bound ?? null;
  const history=useMemo(() => withCurrentDeltas(comparableRuns(state.runs,state.run,state.events),currentBest),[state.runs,state.run,state.events,currentBest]);
  const latestEvent=state.events.at(-1);
  const elapsed=elapsedSeconds(state.run,latestEvent,clock);
  const stageIndex=currentStageIndex(state.events,state.run);
  const solver=String(latestMetric(state.events,"solver") ?? "—");
  const objectiveProfile=String(latestMetric(state.events,"objective_profile") ?? (state.run?.result?.run_metadata as Record<string,unknown> | undefined)?.objective_profile ?? "");
  const objectiveLabel=objectiveProfile==="tianchi_2017" ? "当前最优评分" : "当前最优成本";
  const previousChange=changes[0]?.delta ?? null;
  const variables=latestMetric(state.events,"variables");
  const constraints=latestMetric(state.events,"constraints");
  const candidates=latestMetric(state.events,"flight_options");

  return <div className="page solve-page"><PageHead eyebrow="03 / SOLVE" title="实时求解" description="显示真实阶段、耗时、模型规模、Incumbent、界与 Gap；不伪造百分比进度。"><label className="compact-select"><span className="sr-only">运行 Profile</span><select value={runtimeProfile} onChange={(event) => setRuntimeProfile(event.target.value)}>{(state.capabilities?.runtime_profiles ?? []).map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.name}</option>)}</select></label><button className="button primary" type="button" disabled={!state.draft || start.isPending || state.run?.job_status === "running"} onClick={() => start.mutate()}><Play />{start.isPending ? "保存配置并创建快照…" : "创建快照并求解"}</button>{state.run && !terminal.has(state.run.job_status) && <button className="button danger" type="button" disabled={cancel.isPending} onClick={() => cancel.mutate()}><CircleStop />取消</button>}</PageHead>
    <section className="metric-row"><Metric label="任务状态" value={state.run?.job_status ?? "idle"} /><Metric label="当前阶段" value={stageLabels[stageIndex] ?? "等待开始"} /><Metric label="已用时间" value={formatDuration(elapsed)} /><Metric label="实际求解器" value={solver} /><Metric label={objectiveLabel} value={format(currentBest)} good={currentBest!=null} /><Metric label="最优下界" value={format(latest?.lower_bound)} /><Metric label="相对 Gap" value={latest?.relative_gap == null ? "—" : `${(latest.relative_gap * 100).toFixed(3)}%`} /><Metric label="最近改进" value={previousChange==null ? "—" : signed(previousChange)} good={previousChange!=null && previousChange<0} /></section>
    <section className="solve-stage-strip" aria-label="求解阶段">{stageLabels.map((label,index) => <div key={label} className={index<stageIndex ? "is-done" : index===stageIndex && state.run ? "is-active" : ""}><span>{index+1}</span><strong>{label}</strong></div>)}</section>
    <div className={`visual-layout ${detailPanel.open ? "" : "is-panel-collapsed"}`}><section className="visual-card"><div className="card-head"><div><span>核心视觉</span><h2>最优下界 / 当前最佳解</h2></div><div className="card-head-tools"><span className={`live-indicator ${state.run?.job_status === "running" ? "is-live" : ""}`}>{state.run?.job_status === "running" ? "LIVE" : "TRACE"}</span><PanelToggle open={detailPanel.open} onToggle={() => detailPanel.setOpen(!detailPanel.open)} label="事件栏" /></div></div>{points.length ? <Chart option={option} label="求解上下界收敛图" theme={theme} height={430} /> : <ActivityEmpty run={state.run} eventCount={state.events.length} elapsed={elapsed} candidates={candidates} variables={variables} constraints={constraints} solver={solver} />}</section><aside className="detail-panel event-panel" hidden={!detailPanel.open}><div className="panel-title"><h2>结构化事件</h2><span>{state.events.length}</span></div><div className="event-stream">{state.events.length ? [...state.events].reverse().map((event) => <article key={event.seq}><span className="event-seq">{String(event.seq).padStart(3, "0")}</span><div><strong>{eventLabel(event.event_type)}</strong><p>{event.message || event.stage}</p><small>{event.elapsed_seconds.toFixed(2)}s · {event.stage}</small></div>{event.absolute_gap != null && <code>gap {format(event.absolute_gap)}</code>}</article>) : <div className="empty-note">事件流支持 Last-Event-ID 续传。</div>}</div></aside></div>
    <section className="solve-insights"><article><div className="section-title"><div><span>本次运行</span><h2>最近 Incumbent 改进</h2></div></div>{changes.length ? <div className="monitor-list">{changes.map((item) => <div key={item.seq}><span>{item.elapsed_seconds.toFixed(1)}s</span><strong>{format(item.upper_bound)}</strong><code>{item.delta==null ? "首个可行解" : signed(item.delta)}</code></div>)}</div> : <div className="empty-note">尚未找到可行解；阶段与模型规模仍会持续更新。</div>}</article><article><div className="section-title"><div><span>可比研究问题</span><h2>最近历史任务</h2></div></div>{history.length ? <div className="monitor-list">{history.map(({run,total,delta}) => <div key={run.run_id}><span>{run.run_id.slice(0,8)} · {run.optimization_status}</span><strong>{format(total)}</strong><code>{delta==null ? "—" : signed(delta)}</code></div>)}</div> : <div className="empty-note">暂无相同数据样本、目标和可行域的历史任务。</div>}</article></section>
    <section className="run-history"><div className="section-title"><div><span>不可变记录</span><h2>运行历史</h2></div><button className="icon-button" title="刷新" aria-label="刷新运行历史" type="button" onClick={() => query.invalidateQueries({ queryKey: ["runs"] })}><RefreshCw /></button></div><div className="run-list">{state.runs.map((run) => <button type="button" key={run.run_id} className={state.run?.run_id === run.run_id ? "is-selected" : ""} onClick={async () => { state.selectRun(run); if (terminal.has(run.job_status)) await hydrateRunEvidence(run.run_id); }}><span className={`run-dot tone-${run.job_status}`} /><strong>{run.run_id.slice(0,8)}</strong><span>{run.job_status}</span><span>{run.optimization_status ?? "—"}</span><code>{run.input_hash.slice(0,8)}</code></button>)}</div></section>
    <XmaResult />
  </div>;
}

function Metric({ label,value,good=false }: { label:string;value:string;good?:boolean }) { return <article className={`metric ${good ? "good" : ""}`}><span>{label}</span><strong>{value}</strong></article>; }
function format(value:unknown) { return typeof value==="number" && Number.isFinite(value) ? value.toLocaleString(undefined,{maximumFractionDigits:3}) : "—"; }
function signed(value:number) { return `${value>0 ? "+" : ""}${value.toLocaleString(undefined,{maximumFractionDigits:3})}`; }
function formatDuration(seconds:number) { const value=Math.max(0,Math.floor(seconds)); return value<60 ? `${value}s` : `${Math.floor(value/60)}m ${value%60}s`; }

function elapsedSeconds(run:RunRecord|null,event:RunEvent|undefined,clock:number) {
  if (!run) return 0;
  if (event) return event.elapsed_seconds+(terminal.has(run.job_status) ? 0 : Math.max(0,(clock-Date.parse(event.emitted_at))/1000));
  const start=run.started_at ?? run.created_at;
  const end=run.finished_at ? Date.parse(run.finished_at) : clock;
  return Math.max(0,(end-Date.parse(start))/1000);
}

function currentStageIndex(events:RunEvent[],run:RunRecord|null) {
  if (!run) return -1;
  if (terminal.has(run.job_status)) return 6;
  const type=events.at(-1)?.event_type;
  if (type==="run_queued") return 0;
  if (type==="candidate_generation") return 2;
  if (type==="building_model" || type==="model_built") return 3;
  if (["solver_selected","solver_fallback","solver_heartbeat","mip_progress","mip_bound","benders_iteration","pricing_iteration","branch_node"].includes(type ?? "")) return 4;
  if (type==="audit_completed") return 5;
  if (type==="solve_bounds" || type==="run_completed") return 6;
  return 1;
}

function ActivityEmpty({run,eventCount,elapsed,candidates,variables,constraints,solver}:{run:RunRecord|null;eventCount:number;elapsed:number;candidates:unknown;variables:unknown;constraints:unknown;solver:string}) {
  return <div className="solve-activity-empty"><Clock3 /><h3>{run && terminal.has(run.job_status) ? "该运行没有中间界事件" : eventCount ? "求解正在推进，尚无可绘制的界" : "等待任务入队"}</h3><p>{run ? `已用 ${formatDuration(elapsed)}。没有真实 Incumbent 或下界时不会绘制虚假收敛点。` : "创建快照后将显示真实阶段、模型规模与求解事件。"}</p><dl><div><dt>候选</dt><dd>{format(candidates)}</dd></div><div><dt>变量</dt><dd>{format(variables)}</dd></div><div><dt>约束</dt><dd>{format(constraints)}</dd></div><div><dt>求解器</dt><dd>{solver}</dd></div></dl></div>;
}

function eventLabel(type:string) {
  return ({ study_context:"研究问题",candidate_generation:"候选生成",building_model:"开始建模",model_built:"模型完成",solver_selected:"选择求解器",solver_fallback:"求解器降级",solver_heartbeat:"求解心跳",mip_progress:"MIP 进度",mip_bound:"MIP 界",benders_iteration:"Benders 迭代",pricing_iteration:"定价迭代",branch_node:"分支节点",audit_completed:"独立审计",solve_bounds:"最终界",run_completed:"运行完成",run_failed:"运行失败",run_cancelled:"运行取消" } as Record<string,string>)[type] ?? type;
}
