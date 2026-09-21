import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Activity, BarChart3, Database, FileCheck2, GitCompareArrows, History, Menu, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { useWorkbench } from "../store";

const nav = [
  { to: "/data", label: "数据设计", short: "数据", icon: Database },
  { to: "/impact", label: "扰动影响", short: "影响", icon: Activity },
  { to: "/solve", label: "求解", short: "求解", icon: BarChart3 },
  { to: "/compare", label: "方案对比", short: "对比", icon: GitCompareArrows },
  { to: "/audit", label: "审计", short: "审计", icon: FileCheck2 },
];

export function Shell() {
  const navigate = useNavigate();
  const state = useWorkbench();
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities, staleTime: 30_000 });
  const cases = useQuery({ queryKey: ["cases"], queryFn: api.cases, staleTime: Infinity });
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: api.drafts, refetchInterval: 10_000 });
  const runs = useQuery({ queryKey: ["runs", state.draft?.draft_id], queryFn: () => api.runs(state.draft?.draft_id), refetchInterval: 1500 });

  useEffect(() => state.set({ capabilities: capabilities.data ?? null }), [capabilities.data]);
  useEffect(() => state.set({ cases: cases.data ?? [] }), [cases.data]);
  useEffect(() => {
    const values = drafts.data ?? [];
    state.set({ drafts: values });
    if (!state.draft && values.length) {
      api.draft(values[0].draft_id).then((draft) => state.selectDraft(draft)).catch((error) => {
        state.set({ message: { tone: "error", text: error instanceof Error ? error.message : "无法加载草稿" } });
      });
    }
  }, [drafts.data]);
  useEffect(() => state.set({ runs: runs.data ?? [] }), [runs.data]);

  const solver = state.capabilities?.solver;
  const runStatus = state.run?.job_status ?? "未运行";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">AR</span><span><strong>AIR Recovery</strong><small>Research Workbench</small></span></div>
        <nav aria-label="工作流导航">
          {nav.map((item, index) => <NavLink key={item.to} to={item.to} className={({ isActive }) => isActive ? "is-active" : ""} aria-label={item.label}><item.icon aria-hidden="true" /><span className="step-index">0{index + 1}</span><span className="nav-label">{item.label}</span><span className="nav-short">{item.short}</span></NavLink>)}
        </nav>
        <div className="sidebar-foot"><ShieldCheck aria-hidden="true" /><span>单机 · 可复现 · UTC</span></div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="draft-switcher">
            <label htmlFor="draft-select">当前草稿</label>
            <select id="draft-select" value={state.draft?.draft_id ?? ""} onChange={async (event) => {
              const draft = await api.draft(event.target.value);
              state.selectDraft(draft);
              navigate("/data");
            }}>
              {!state.drafts.length && <option value="">尚无草稿</option>}
              {state.drafts.map((draft) => <option key={draft.draft_id} value={draft.draft_id}>{draft.name}</option>)}
            </select>
            {state.draft && <code title={state.draft.working_hash}>{state.draft.working_hash.slice(0, 8)}</code>}
          </div>
          <div className="status-strip" aria-label="工作台状态">
            <Status label="校验" value={state.preview ? (state.preview.valid ? "通过" : "有错误") : "待编译"} tone={state.preview?.valid ? "ok" : "neutral"} />
            <Status label="求解器" value={solver?.available ? "可用" : "不可用"} tone={solver?.available ? "ok" : "error"} />
            <Status label="运行" value={runStatus} tone={state.run?.job_status === "running" ? "live" : "neutral"} />
          </div>
          <button className="icon-button mobile-menu" type="button" aria-label="打开运行历史" title="运行历史" onClick={() => navigate("/solve")}><History /></button>
        </header>
        {state.message && <div className={`global-message tone-${state.message.tone}`} role="status"><span>{state.message.text}</span><button type="button" onClick={() => state.set({ message: null })}>关闭</button></div>}
        <main id="main-content" className="main-content"><Outlet /></main>
      </div>
    </div>
  );
}

function Status({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className={`status-item tone-${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}
