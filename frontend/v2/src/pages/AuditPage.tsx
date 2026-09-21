import { useState } from "react";
import { CheckCircle2, Download, FileJson2, ShieldAlert } from "lucide-react";
import { useWorkbench } from "../store";
import type { JsonObject } from "../types";
import { PageHead } from "./DataStudio";

const sections = ["summary", "input", "decisions", "objective", "constraints", "trace", "environment"] as const;

export function AuditPage() {
  const state = useWorkbench();
  const [section, setSection] = useState<typeof sections[number]>("summary");
  const audit = state.audit;
  if (!audit || !state.run) return <div className="page"><PageHead eyebrow="05 / AUDIT" title="审计" description="选择一个运行后查看不可变输入、决策、约束与 Trace。" /><div className="empty-state large"><FileJson2 /><h2>没有可审计的运行</h2><p>审计包独立包含输入快照、hash、结果和事件，可重新导入核验。</p></div></div>;
  const download = () => { window.location.href = `/api/v2/runs/${state.run!.run_id}/export`; };
  const expected = audit.expected_check as JsonObject | null;
  return <div className="page audit-page"><PageHead eyebrow="05 / AUDIT" title="审计与复现" description="所有证据来自本次运行的不可变快照，不与当前工作副本混用。"><button className="button primary" type="button" onClick={download}><Download />导出完整审计包</button></PageHead>
    <section className="audit-banner"><div><span>Run ID</span><code>{state.run.run_id}</code></div><div><span>Input hash</span><code>{state.run.input_hash}</code></div><div><span>状态</span><strong>{state.run.job_status} / {state.run.optimization_status ?? "—"}</strong></div></section>
    <div className="audit-layout"><nav className="audit-nav" aria-label="审计章节">{sections.map((item) => <button type="button" key={item} className={section === item ? "is-active" : ""} onClick={() => setSection(item)}>{item}</button>)}</nav><section className="audit-content"><AuditSection section={section} audit={audit} expected={expected} /></section></div>
  </div>;
}

function AuditSection({ section, audit, expected }: { section: string; audit: JsonObject; expected: JsonObject | null }) {
  if (section === "summary") return <div className="audit-summary"><h2>运行摘要</h2><div className="audit-cards"><article><span>Expected 对拍</span>{expected ? <strong className={expected.status_matches && expected.objective_matches ? "pass" : "fail"}>{expected.status_matches && expected.objective_matches ? <><CheckCircle2 />一致</> : <><ShieldAlert />存在差异</>}</strong> : <strong>未提供</strong>}</article><article><span>目标函数</span><strong>{String((audit.objective as JsonObject | null)?.total ?? "—")}</strong></article><article><span>恢复动作</span><strong>{Array.isArray(audit.recovery_actions) ? audit.recovery_actions.length : 0}</strong></article><article><span>Trace 事件</span><strong>{Array.isArray(audit.events) ? audit.events.length : 0}</strong></article></div><div className="evidence-note"><ShieldAlert /><p><strong>证据边界</strong>{String(audit.evidence_boundary)}</p></div><JsonBlock value={audit.diagnostics ?? {}} /></div>;
  const mapping: Record<string, unknown> = { input: audit.solve_request, decisions: { selected: audit.selected, recovery_actions: audit.recovery_actions }, objective: { objective: audit.objective, bounds: audit.bounds }, constraints: audit.integrated_audit ?? { note: "约束逐项明细取决于本次运行 Trace 级别。" }, trace: audit.events, environment: audit.run_metadata };
  return <div><h2>{section}</h2><JsonBlock value={mapping[section] ?? {}} /></div>;
}

function JsonBlock({ value }: { value: unknown }) { return <pre className="json-block" tabIndex={0}>{JSON.stringify(value, null, 2)}</pre>; }
