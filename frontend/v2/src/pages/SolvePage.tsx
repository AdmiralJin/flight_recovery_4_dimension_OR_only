import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleStop, Clock3, Play, RefreshCw } from "lucide-react";
import type { EChartsOption } from "echarts";
import { api } from "../api";
import { Chart } from "../components/Chart";
import { useWorkbench } from "../store";
import type { RunEvent, RunRecord } from "../types";
import { PageHead } from "./DataStudio";

const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);

export function SolvePage() {
  const state = useWorkbench();
  const query = useQueryClient();
  const source = useRef<EventSource | null>(null);
  const [runtimeProfile, setRuntimeProfile] = useState("default-exact");
  const start = useMutation({ mutationFn: async () => {
    if (!state.draft) throw new Error("请先选择草稿");
    const preview = await api.compile(state.draft.draft_id);
    state.set({ preview });
    if (!preview.valid) throw new Error("编译未通过，不能创建求解快照");
    const snapshot = await api.snapshot(state.draft, `Run created ${new Date().toISOString()}`);
    return api.createRun(snapshot.snapshot_id, runtimeProfile);
  }, onSuccess: (run) => { state.selectRun(run); query.invalidateQueries({ queryKey: ["runs"] }); state.set({ message: { tone: "success", text: "不可变快照已入队；刷新或断线不会终止运行。" } }); }, onError: (error) => state.set({ message: { tone: "error", text: error instanceof Error ? error.message : "无法启动运行" } }) });
  const cancel = useMutation({ mutationFn: () => api.cancelRun(state.run!.run_id), onSuccess: (run) => state.set({ run, message: { tone: "warning", text: "已请求协作式取消；超时会终止隔离进程并保留 Trace。" } }) });

  useEffect(() => {
    const run = state.run;
    source.current?.close();
    if (!run || terminal.has(run.job_status)) return;
    const stream = new EventSource(`/api/v2/runs/${run.run_id}/events`);
    source.current = stream;
    stream.onmessage = (message) => state.addEvent(JSON.parse(message.data) as RunEvent);
    const eventTypes = ["run_queued", "stage_started", "stage_completed", "benders_iteration", "run_started", "run_completed", "run_failed", "run_cancelled"];
    eventTypes.forEach((type) => stream.addEventListener(type, (message) => state.addEvent(JSON.parse((message as MessageEvent).data) as RunEvent)));
    const poll = window.setInterval(async () => {
      const current = await api.run(run.run_id);
      state.set({ run: current });
      if (terminal.has(current.job_status)) {
        stream.close(); window.clearInterval(poll); query.invalidateQueries({ queryKey: ["runs"] });
        const [comparison, audit] = await Promise.all([api.comparison(current.run_id), api.audit(current.run_id)]);
        state.set({ comparison, audit });
      }
    }, 700);
    return () => { stream.close(); window.clearInterval(poll); };
  }, [state.run?.run_id, state.run?.job_status]);

  const points = state.events.filter((item) => item.lower_bound !== null || item.upper_bound !== null);
  const option: EChartsOption = useMemo(() => ({
    animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", valueFormatter: (value) => typeof value === "number" ? value.toLocaleString() : String(value) },
    legend: { top: 2, textStyle: { color: "#a8bcc9" } },
    grid: { left: 64, right: 28, top: 46, bottom: 48 },
    xAxis: { type: "category", name: "事件序号", data: points.map((item) => item.seq), axisLabel: { color: "#8096a5" }, axisLine: { lineStyle: { color: "#2b4352" } } },
    yAxis: { type: "value", name: "目标值", axisLabel: { color: "#8096a5" }, splitLine: { lineStyle: { color: "#193442" } } },
    series: [
      { name: "Lower bound", type: "line", step: "end", showSymbol: true, connectNulls: true, data: points.map((item) => item.lower_bound), lineStyle: { color: "#20c7a6", width: 2 }, itemStyle: { color: "#20c7a6" } },
      { name: "Incumbent UB", type: "line", step: "end", showSymbol: true, connectNulls: true, data: points.map((item) => item.upper_bound), lineStyle: { color: "#f2b84b", width: 2 }, itemStyle: { color: "#f2b84b" } },
    ],
  }), [points]);
  const latest = points.at(-1);
  return <div className="page solve-page"><PageHead eyebrow="03 / SOLVE" title="实时求解" description="显示真实阶段、界、Gap、割、列和节点事件；不伪造百分比进度。"><label className="compact-select"><span className="sr-only">运行 Profile</span><select value={runtimeProfile} onChange={(event) => setRuntimeProfile(event.target.value)}>{(state.capabilities?.runtime_profiles ?? []).map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.name}</option>)}</select></label><button className="button primary" type="button" disabled={!state.draft || start.isPending || state.run?.job_status === "running"} onClick={() => start.mutate()}><Play />{start.isPending ? "创建快照…" : "创建快照并求解"}</button>{state.run && !terminal.has(state.run.job_status) && <button className="button danger" type="button" disabled={cancel.isPending} onClick={() => cancel.mutate()}><CircleStop />取消</button>}</PageHead>
    <section className="metric-row"><Metric label="Job" value={state.run?.job_status ?? "idle"} /><Metric label="Optimization" value={state.run?.optimization_status ?? "—"} /><Metric label="Lower bound" value={format(latest?.lower_bound)} /><Metric label="Upper bound" value={format(latest?.upper_bound)} /><Metric label="Relative gap" value={latest?.relative_gap == null ? "—" : `${(latest.relative_gap * 100).toFixed(3)}%`} /></section>
    <div className="visual-layout"><section className="visual-card"><div className="card-head"><div><span>核心视觉</span><h2>LB / UB 收敛轨迹</h2></div><span className={`live-indicator ${state.run?.job_status === "running" ? "is-live" : ""}`}>{state.run?.job_status === "running" ? "LIVE" : "TRACE"}</span></div>{points.length ? <Chart option={option} label="求解上下界收敛图" height={430} /> : <div className="empty-state chart-empty"><Clock3 /><h3>等待真实求解事件</h3><p>入队后，Phase 11/12 的界与迭代会从隔离进程写入这里。</p></div>}</section><aside className="detail-panel event-panel"><div className="panel-title"><h2>结构化事件</h2><span>{state.events.length}</span></div><div className="event-stream">{state.events.length ? [...state.events].reverse().map((event) => <article key={event.seq}><span className="event-seq">{String(event.seq).padStart(3, "0")}</span><div><strong>{event.event_type}</strong><p>{event.message || event.stage}</p><small>{event.elapsed_seconds.toFixed(2)}s · {event.stage}</small></div>{event.absolute_gap != null && <code>gap {format(event.absolute_gap)}</code>}</article>) : <div className="empty-note">事件流支持 Last-Event-ID 续传。</div>}</div></aside></div>
    <section className="run-history"><div className="section-title"><div><span>不可变记录</span><h2>运行历史</h2></div><button className="icon-button" title="刷新" aria-label="刷新运行历史" type="button" onClick={() => query.invalidateQueries({ queryKey: ["runs"] })}><RefreshCw /></button></div><div className="run-list">{state.runs.map((run) => <button type="button" key={run.run_id} className={state.run?.run_id === run.run_id ? "is-selected" : ""} onClick={async () => { state.selectRun(run); if (terminal.has(run.job_status)) { const [comparison, audit] = await Promise.all([api.comparison(run.run_id), api.audit(run.run_id)]); state.set({ comparison, audit }); } }}><span className={`run-dot tone-${run.job_status}`} /><strong>{run.run_id.slice(0, 8)}</strong><span>{run.job_status}</span><span>{run.optimization_status ?? "—"}</span><code>{run.input_hash.slice(0, 8)}</code></button>)}</div></section>
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) { return <article className="metric"><span>{label}</span><strong>{value}</strong></article>; }
function format(value: unknown) { return typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "—"; }
