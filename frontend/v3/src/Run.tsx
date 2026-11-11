import { memo, useMemo, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCheck, CircleStop, Play, RefreshCw } from "lucide-react";
import { api } from "./api";
import { Button, Card, Empty, Field, JsonDetails, LazyDetails, Message } from "./components";
import { Chart } from "./Chart";
import { RunClock } from "./RunClock";
import { Term } from "./Help";
import { objectiveHelp, algorithmHelp } from "./objectiveHelp";
import { isXma } from "./data";
import { globalTrace } from "./monitor";
import { chooseRun, download, execute, object, patchDocument, saveAndValidate, startBlockers, startRun, statusLabel, terminal, useWb } from "./state";
import { solveTraceOption } from "../../v2/src/visualization/chartOptions";

export const numberText = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("zh-CN", { maximumFractionDigits: 3 }) : "—";
export const Run = memo(function Run() {
  const state = useWb(useShallow(s => ({ document: s.document, draft: s.draft, run: s.run, busy: s.busy, rawText: s.rawText, runtimeProfile: s.runtimeProfile, runtimeEdits: s.runtimeEdits, checkedProfile: s.checkedProfile, preview: s.preview, conflict: s.conflict })));
  const cache = useQueryClient();
  const caps = useQuery({ queryKey: ["wb3", "capabilities"], queryFn: api.capabilities });
  const [allHistory, setAllHistory] = useState(false);
  const historyDraftId = allHistory ? undefined : state.draft?.draft_id;
  const history = useQuery({ queryKey: ["wb3", "runs", historyDraftId ?? "all"], queryFn: () => api.runs(historyDraftId), refetchInterval: 30000 });
  const doc = state.document;
  const xma = isXma(doc);
  const bundle = object(doc?.solve_bundle);
  const policy = object(doc?.candidate_policy);
  const profile = caps.data?.runtime_profiles.find(p => p.profile_id === state.runtimeProfile);
  const runtimeValues = state.runtimeEdits ?? profile?.parameters ?? {};
  const reasons = startBlockers();
  if (!xma && caps.data?.solver.available === false) reasons.push(caps.data.solver.reason ?? "求解器不可用");
  const runs = (history.data ?? []).filter(r => allHistory || !state.draft || r.draft_id === state.draft.draft_id);
  const objective = String(bundle.objective_profile ?? "air_linear_v1");
  const setBundle = (key: string, value: unknown) => patchDocument(["solve_bundle", key], value);
  const setRuntime = (key: string, value: string) => useWb.setState(s => ({ runtimeEdits: { ...runtimeValues, [key]: value === "" ? null : Number(value) }, version: s.version + 1, preview: null, checkedProfile: null }));
  return <div className="workspace stack">
    <header className="page-head"><div><span className="eyebrow">02 / CONFIGURE & RUN</span><h1>配置与运行</h1><p>保存配置，校验输入，再从不可变快照启动求解。</p></div><div className="actions"><Button loading={state.busy === "正在保存并校验"} disabled={!doc || !!state.busy} onClick={() => execute("正在保存并校验", async () => { await saveAndValidate(); await cache.invalidateQueries({ queryKey: ["wb3", "capabilities"] }); })}><CheckCheck size={17}/>保存并校验</Button><Button variant="primary" loading={state.busy === "正在创建运行"} disabled={reasons.length > 0} aria-describedby="run-readiness" onClick={() => execute("正在创建运行", startRun)}><Play size={17}/>{state.busy === "正在创建运行" ? state.busy : "开始求解"}</Button></div></header>
    {!doc ? <Card><Empty title="请先准备研究数据" action={<Link className="text-link" to="/prepare">前往数据准备 <ArrowRight size={16}/></Link>}>创建或选择草稿后，可设置算法和求解时限。</Empty></Card> : <Card title="求解配置" note={`${doc.name} · ${xma ? "厦航研究 / 北京时间" : "AIR 联合恢复 / UTC"}`}>
      <fieldset disabled={!!state.busy || state.rawText !== null} className="config-form"><div className="form-grid">
        <Field label="目标函数" help={objectiveHelp(doc)} hint={xma && objective === "tianchi_2017" ? "天池评分（分）" : "AIR 研究成本；与天池评分分别比较"}>{xma ? <select value={String(bundle.objective_profile)} onChange={e => setBundle("objective_profile", e.target.value)}><option value="tianchi_2017">天池 2017 评分</option><option value="air_linear_v1">AIR 线性研究成本</option></select> : <input value="AIR 联合恢复成本" readOnly/>}</Field>
        <Field label="求解算法" help={algorithmHelp[xma ? String(bundle.algorithm) : "air"]} hint={xma ? "显式航班串基准适合小实例" : "后端提供固定的 Benders / 分支定价路线"}>{xma ? <select value={String(bundle.algorithm)} onChange={e => setBundle("algorithm", e.target.value)}><option value="joint_arc_flow">直接联合优化</option><option value="joint_path_oracle">显式航班串 Oracle</option><option value="benders_joint">Benders＋联合子问题</option><option value="benders_cg_bp">Benders＋列生成 / 分支定价</option></select> : <input value="Benders＋Branch & Price" readOnly/>}</Field>
        {xma ? <>{([['delay_step_minutes', '候选步长（分钟）', 1, 360], ['maximum_delay_minutes', '最大延误（分钟）', 0, 2160], ['time_limit_seconds', '求解时限（秒）', 1, 86400], ['max_assignment_options', '分配候选上限（项）', 1, 10000000]] as const).map(([key, label, min, max]) => <Field key={key} label={label} error={!Number.isInteger(Number(bundle[key])) || Number(bundle[key]) < min || Number(bundle[key]) > max ? `请输入 ${min}–${max} 的整数` : undefined}><input type="number" min={min} max={max} value={String(bundle[key] ?? "")} onChange={e => setBundle(key, e.target.value === "" ? "" : Number(e.target.value))}/></Field>)}</> : <>
          <Field label="运行参数模板" hint="自定义参数保存为独立副本，原模板保留"><select value={state.runtimeProfile} disabled={state.runtimeEdits !== null} onChange={e => useWb.setState(s => ({ runtimeProfile: e.target.value, checkedProfile: null, version: s.version + 1 }))}>{(caps.data?.runtime_profiles ?? [{ profile_id: "default-exact", name: "默认精确求解" }]).map(p => <option key={p.profile_id} value={p.profile_id}>{p.name}</option>)}</select></Field>
          {([['time_limit_seconds', '求解时限（秒）', 1, 86400], ['max_benders_iterations', 'Benders 迭代上限（次）', 1, 100000], ['max_branch_nodes', '分支节点上限（个）', 1, 1000000]] as const).map(([key, label, min, max]) => <Field key={key} label={label} hint="留空使用算法默认值" error={runtimeValues[key] != null && (Number(runtimeValues[key]) < min || Number(runtimeValues[key]) > max) ? `请输入 ${min}–${max}` : undefined}><input type="number" min={min} max={max} value={String(runtimeValues[key] ?? "")} placeholder="算法默认值" onChange={e => setRuntime(key, e.target.value)}/></Field>)}
          <Field label="重新生成航班候选"><select value={String(policy.regenerate_flight_options ?? false)} onChange={e => patchDocument(["candidate_policy", "regenerate_flight_options"], e.target.value === "true")}><option value="false">使用现有候选</option><option value="true">按延误网格重新生成</option></select></Field>
          {([['delay_step_minutes', '候选步长（分钟）', 1, 360, 10], ['maximum_delay_minutes', '最大延误（分钟）', 0, 1440, 60]] as const).map(([key, label, min, max, fallback]) => <Field key={key} label={label}><input type="number" min={min} max={max} value={String(policy[key] ?? fallback)} onChange={e => patchDocument(["candidate_policy", key], e.target.value === "" ? "" : Number(e.target.value))}/></Field>)}
        </>}
      </div></fieldset>
      <div id="run-readiness" className="readiness">{reasons.length ? <><span className="status-dot warning"/><div><strong>开始前需要处理</strong><p>{reasons.join("；")}</p></div></> : <><span className="status-dot success"/><div><strong>输入与配置已就绪</strong><p>运行使用最近保存的输入快照；后续编辑不会改变历史结果。</p></div></>}</div>
      {caps.isError && <Message tone="error">求解能力信息读取失败。<Button onClick={() => caps.refetch()}>重试</Button></Message>}
    </Card>}
    <RunProgress/>
    <Card title="运行历史" note="选择记录恢复事件和结果；历史结果与当前编辑副本分开显示。" actions={<div className="actions"><label className="check"><input type="checkbox" checked={allHistory} onChange={e => setAllHistory(e.target.checked)}/>全部草稿</label><Button variant="quiet" aria-label="刷新运行历史" onClick={() => history.refetch()}><RefreshCw size={16}/></Button></div>}>
      {history.isError ? <Message tone="error">运行历史加载失败，请刷新重试。</Message> : !runs.length ? <div className="quiet-state">{history.isPending ? "正在读取运行历史…" : "该草稿暂无运行记录。"}</div> : <div className="history-list">{runs.map(record => <button key={record.run_id} aria-pressed={record.run_id === state.run?.run_id} onClick={() => chooseRun(record)}><span><strong>{new Date(record.created_at).toLocaleString("zh-CN")}</strong><small>运行 {record.run_id.slice(0, 10)} · {record.draft_id === state.draft?.draft_id ? "当前草稿" : "其他草稿"}</small></span><span className="tag">{statusLabel(record)}</span></button>)}</div>}
    </Card>
  </div>;
});

const RunProgress = memo(function RunProgress() {
  const state = useWb(useShallow(s => ({ run: s.run, events: s.events, theme: s.theme, connection: s.connection, busy: s.busy, draftId: s.draft?.draft_id })));
  const points = useMemo(() => globalTrace(state.events, state.run), [state.events, state.run]);
  const option = useMemo(() => solveTraceOption(points, state.theme), [points, state.theme]);
  const latest = useMemo(() => {
    const reversed = [...points].reverse();
    const lower_bound = reversed.find(e => e.lower_bound != null)?.lower_bound;
    const upper_bound = reversed.find(e => e.upper_bound != null)?.upper_bound;
    const relative_gap = typeof lower_bound === "number" && typeof upper_bound === "number" ? upper_bound >= lower_bound ? (upper_bound - lower_bound) / Math.max(1, Math.abs(upper_bound)) : null : reversed.find(e => e.relative_gap != null)?.relative_gap;
    return { lower_bound, upper_bound, relative_gap };
  }, [points]);
  const evidence = useMemo(() => ({ run_id: state.run?.run_id, input_hash: state.run?.input_hash, snapshot_id: state.run?.snapshot_id, runtime_profile_id: state.run?.runtime_profile_id, events: state.events }), [state.run, state.events]);
  const last = state.events.at(-1);
  const currentBusy = state.run && !terminal(state.run);
  return (<Card title="当前运行" note={state.run ? `${state.run.draft_id === state.draftId ? "当前草稿的运行" : "另一个草稿的历史 / 正在进行的运行"} · ${state.connection}` : "页面切换不会中断运行监控"} actions={currentBusy ? <Button variant="danger" disabled={!!state.busy || state.run?.cancel_requested} onClick={() => execute("正在请求取消", async () => { const id = state.run!.run_id; const record = await api.cancelRun(id); if (useWb.getState().run?.run_id === id) useWb.setState({ run: record }); })}><CircleStop size={16}/>{state.run?.cancel_requested ? "取消已请求" : "取消运行"}</Button> : state.run && <Link className="text-link" to="/results">查看结果 <ArrowRight size={16}/></Link>}>
      {!state.run ? <Empty title="尚未启动运行">保存并校验后，使用页面顶部的“开始求解”。</Empty> : <><div className="metric-grid run-metrics"><div><span><Term>运行结论</Term></span><strong className="metric-text">{statusLabel(state.run)}</strong></div><div><span><Term>全局下界 LB</Term></span><strong>{numberText(latest?.lower_bound)}</strong></div><div><span><Term>全局可行解 UB</Term></span><strong>{numberText(latest?.upper_bound)}</strong></div><div><span><Term>相对 Gap</Term></span><strong>{latest?.relative_gap == null ? "—" : `${(latest.relative_gap * 100).toFixed(3)}%`}</strong></div></div>
        <div className="run-stage"><span className={`status-dot ${currentBusy ? "live" : "success"}`}/><strong>{last?.message || statusLabel(state.run)}</strong><RunClock run={state.run} event={last}/></div>
        {points.length ? <Chart option={option} label="全局上下界收敛轨迹"/> : <div className="quiet-state">尚无全局上下界事件。构模、定价和子问题进展显示在事件记录中。</div>}
        {state.run.error && <Message tone="error">{String(state.run.error.message ?? JSON.stringify(state.run.error))}</Message>}
        <LazyDetails className="inset" summary={`运行事件与技术证据（${state.events.length}）`}>{() => <><div className="event-log">{state.events.slice(-250).reverse().map(event => <div key={event.seq}><span>{event.elapsed_seconds.toFixed(1)}s</span><strong>{event.message || event.event_type}</strong><small>{event.stage}</small></div>)}</div><JsonDetails summary="完整事件 JSON" value={evidence}/><Button onClick={() => execute("正在导出事件", () => download("run-events.json", evidence))}>导出全部事件</Button></>}</LazyDetails>
      </>}
    </Card>);
});
