import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Play } from "lucide-react";
import { api } from "../api";
import { Chart, type ChartClickEvent } from "../components/Chart";
import { PanelToggle, useDetailPanel } from "../components/PanelToggle";
import { useWorkbench } from "../store";
import { useTheme } from "../theme";
import { flightNetworkOption } from "../visualization/chartOptions";
import { PageHead } from "./DataStudio";

export function ImpactPage() {
  const state = useWorkbench();
  const { theme } = useTheme();
  const detailPanel = useDetailPanel();
  const modelQuery = useQuery({
    queryKey: ["impact-visualization", state.draft?.draft_id, state.draft?.working_hash],
    queryFn: () => api.draftVisualization(state.draft!.draft_id),
    enabled: Boolean(state.draft && state.preview),
  });
  const compile = useMutation({ mutationFn: () => api.compile(state.draft!.draft_id), onSuccess: (preview) => state.set({ preview, message: { tone: preview.valid ? "success" : "warning", text: preview.valid ? "编译通过：有效容量与候选输入已绑定到当前 hash。" : "编译发现阻断问题，请按路径修复。" } }), onError: (error) => state.set({ message: { tone: "error", text: error instanceof Error ? error.message : "编译失败" } }) });
  if (!state.draft) return <div className="page"><PageHead eyebrow="02 / IMPACT" title="扰动影响" description="请先克隆或选择草稿。" /></div>;
  const preview = state.preview;
  const model = modelQuery.data;
  const chart = model ? flightNetworkOption(model, "impact", model.flights, state.selectedId, theme) : null;
  const selectFromChart = (event: ChartClickEvent) => {
    const data = event.data as { entityId?: string; entityType?: string } | undefined;
    if (data?.entityType === "flight" && data.entityId) state.set({ selectedId: data.entityId, selectedEntity: { type: "flight", id: data.entityId } });
  };
  const direct = preview?.flight_impacts.filter((item) => item.status === "direct").length ?? 0;
  const downstream = preview?.flight_impacts.filter((item) => item.status === "downstream").length ?? 0;
  return <div className="page impact-page">
    <PageHead eyebrow="02 / IMPACT" title="扰动影响" description="以编译后的有效输入为准，展示容量变化与风险暴露；此处不使用任何恢复决策样式。"><button className="button primary" type="button" disabled={compile.isPending} onClick={() => compile.mutate()}><Play />{compile.isPending ? "编译中…" : "编译并预览"}</button></PageHead>
    <section className="metric-row" aria-label="编译摘要"><Metric label="编译状态" value={preview ? (preview.valid ? "Ready" : "Blocked") : "Not compiled"} tone={preview?.valid ? "good" : "neutral"} /><Metric label="直接暴露" value={String(direct)} /><Metric label="传播风险" value={String(downstream)} /><Metric label="容量区间变化" value={String(preview?.capacity_changes.length ?? 0)} /></section>
    <div className={`visual-layout ${detailPanel.open ? "" : "is-panel-collapsed"}`}><section className="visual-card"><div className="card-head"><div><span>核心视觉 · IMPACT</span><h2>有效输入时空网络</h2></div><div className="card-head-tools"><div className="viz-legend"><span className="swatch direct">直接扰动</span><span className="swatch downstream">传播风险</span><span className="swatch recovered">恢复计划</span><span className="swatch ghost">原计划 ghost</span></div><PanelToggle open={detailPanel.open} onToggle={() => detailPanel.setOpen(!detailPanel.open)} label="编译证据" /></div></div>{chart ? <Chart option={chart} label="Impact 航班时空图" theme={theme} height={560} onClick={selectFromChart} /> : <div className="empty-state chart-empty"><AlertTriangle /><h3>{modelQuery.isLoading ? "正在构建可视化模型" : "请先编译当前草稿"}</h3><p>编译后将按可视化页的统一语义显示航班箭头、扰动时域和风险暴露。</p></div>}</section><aside className="detail-panel" hidden={!detailPanel.open}><h2>编译证据</h2>{preview ? <><dl><div><dt>草稿 hash</dt><dd><code>{preview.draft_hash.slice(0, 12)}</code></dd></div><div><dt>求解输入 hash</dt><dd><code>{preview.compiled_hash?.slice(0, 12) ?? "—"}</code></dd></div>{Object.entries(preview.candidate_counts).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl><div className="issue-list">{preview.issues.length ? preview.issues.map((issue, index) => <button key={`${issue.code}-${index}`} type="button" className={`issue tone-${issue.severity}`}><AlertTriangle /><span><strong>{issue.code}</strong>{issue.message}<code>{issue.path}</code></span></button>) : <div className="pass-note"><CheckCircle2 />没有阻断问题</div>}</div></> : <div className="empty-note">运行编译后显示字段级问题、候选规模和容量变化。</div>}</aside></div>
  </div>;
}

function Metric({ label, value, tone = "" }: { label: string; value: string; tone?: string }) { return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong></article>; }
