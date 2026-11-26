import { Component, lazy, Suspense, useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Activity, ArrowUpRight, Check, ChevronRight, Database, FlaskConical, Moon, Play, Sun, X } from "lucide-react";
import { api } from "./api";
import { Term } from "./Help";
import { Button, DirtyGuard, Message, OperationProgress, useGuard } from "./components";
import { isDirty, lastSelection, loadDraft, notify, remember, statusLabel, terminal, useWb } from "./state";
import { useRunMonitor } from "./monitor";
const Prepare = lazy(() => import("./Prepare").then(module => ({ default: module.Prepare })));
const Run = lazy(() => import("./Run").then(module => ({ default: module.Run })));
const Results = lazy(() => import("./Results").then(module => ({ default: module.Results })));

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <div className="workspace"><Message tone="error">页面显示遇到问题。已保存的数据和后台运行仍可通过工作台重新载入。<Button onClick={() => window.location.reload()}>重新载入页面</Button></Message></div> : this.props.children; }
}
export function App() { return <HashRouter><DirtyGuard><Workbench/></DirtyGuard></HashRouter>; }
function Workbench() {
  const state = useWb(useShallow(s => ({ draft: s.draft, theme: s.theme, busy: s.busy, run: s.run, notice: s.notice, previewValid: s.preview?.valid, dirty: isDirty(s) })));
  const guard = useGuard();
  const attempted = useRef(false);
  const drafts = useQuery({ queryKey: ["wb3", "drafts"], queryFn: api.drafts, refetchInterval: 30000 });
  useRunMonitor();
  useEffect(() => {
    document.documentElement.dataset.wb3Theme = state.theme;
    document.documentElement.style.colorScheme = state.theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", getComputedStyle(document.documentElement).getPropertyValue("--bg").trim());
    remember("theme", state.theme);
  }, [state.theme]);
  useEffect(() => {
    if (attempted.current || !drafts.data || useWb.getState().draft) return;
    attempted.current = true;
    const last = lastSelection();
    const id = drafts.data.find(item => item.draft_id === last.draft)?.draft_id ?? drafts.data[0]?.draft_id;
    if (id) void loadDraft(id).catch(error => notify(error.message, "error"));
  }, [drafts.data]);
  useEffect(() => {
    let disposed = false;
    const id = lastSelection().run;
    if (id) void api.run(id).then(run => { if (!disposed && !useWb.getState().run) useWb.setState({ run, events: [] }); }).catch(() => { /* A deleted historic run does not block the current draft. */ });
    return () => { disposed = true; };
  }, []);
  const dirty = state.dirty;
  return <div className="wb3-app">
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById("main-content")?.focus(); }}>跳到主要内容</a>
    <aside className="sidebar"><a href="#/prepare" className="brand" aria-label="Flight Recovery v3 首页"><span className="brand-mark"><FlaskConical size={21}/></span><span><strong>Flight Recovery</strong><small>RESEARCH WORKBENCH <b>v3</b></small></span></a>
      <div className="sidebar-label">研究工作区</div><nav className="main-nav" aria-label="主要工作区">{[["prepare", "数据准备", "创建、编辑与校验", Database], ["run", "配置与运行", "算法、求解与历史", Play], ["results", "结果分析", "对比、图表与审计", Activity]].map(([path, label, description, Icon], index) => <NavLink key={String(path)} to={`/${path}`} className={({ isActive }) => isActive ? "active" : ""}>{typeof Icon !== "string" && <Icon size={19}/>}<span><strong>{String(label)}</strong><small>{String(description)}</small></span><span className="nav-step">0{index + 1}</span></NavLink>)}</nav>
      <div className="sidebar-footer"><div className="version-note"><span className="status-dot success"/><span>独立 v3 工作区</span></div><p>数据有来源<br/>运行有快照<br/>结论有证据</p><a href="/workbench-v2/data" target="_blank" rel="noreferrer">打开 Workbench v2 <ArrowUpRight size={14}/></a></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="draft-control"><span className="topbar-caption"><Term>当前草稿</Term></span><select aria-label="当前草稿" value={state.draft?.draft_id ?? ""} disabled={!!state.busy} onChange={e => { const id = e.currentTarget.value; guard(() => { void loadDraft(id).catch(error => notify(error.message, "error")); }); }}><option value="" disabled>{drafts.isPending ? "读取中…" : "选择研究草稿"}</option>{drafts.data?.map(item => <option key={item.draft_id} value={item.draft_id}>{item.name}</option>)}</select><ChevronRight size={14} className="draft-chevron" aria-hidden="true"/></div>
      <div className="topbar-actions"><span className={`save-state ${dirty ? "dirty" : ""}`}>{!state.draft ? "未选择草稿" : dirty ? <><span className="status-dot warning"/>未保存修改</> : state.previewValid ? <><Check size={14}/>已保存 · 校验通过</> : "已保存 · 待校验"}</span><Button variant="quiet" aria-label={state.theme === "light" ? "切换深色主题" : "切换浅色主题"} onClick={() => useWb.setState({ theme: state.theme === "light" ? "dark" : "light" })}>{state.theme === "light" ? <Moon size={19}/> : <Sun size={19}/>}</Button></div>
    </header>
    {state.run && !terminal(state.run) && <div className="persistent-run"><span className="status-dot live"/><strong>{statusLabel(state.run)}</strong><span>运行 {state.run.run_id.slice(0, 8)} · 切换工作区可继续监控</span><NavLink to="/run">查看进度</NavLink></div>}
    <main id="main-content" tabIndex={-1}>
      {drafts.isError && <div className="global-notice"><Message tone="error">草稿列表读取失败，请检查连接。<Button onClick={() => drafts.refetch()}>重试</Button></Message></div>}
      {state.notice && <div className="global-notice"><Message tone={state.notice.tone}>{state.notice.text}</Message><Button variant="quiet" aria-label="关闭提示" onClick={() => useWb.setState({ notice: null })}><X size={16}/></Button></div>}
      <OperationProgress/>
      <Boundary><Suspense fallback={<div className="quiet-state">正在载入工作区…</div>}><Routes><Route path="/prepare" element={<Prepare/>}/><Route path="/run" element={<Run/>}/><Route path="/results" element={<Results/>}/><Route path="*" element={<Navigate to="/prepare" replace/>}/></Routes></Suspense></Boundary>
    </main><footer className="page-footer"><span>Flight Recovery / Workbench v3</span><span>研究输入 → 不可变运行 → 可追溯结果</span></footer></div>
  </div>;
}
