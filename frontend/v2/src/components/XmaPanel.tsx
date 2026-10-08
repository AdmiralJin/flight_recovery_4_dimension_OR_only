import { useState } from "react";
import { api } from "../api";
import { useWorkbench } from "../store";
import type { DraftDocument, JsonObject } from "../types";
import { VirtualTable } from "./VirtualTable";

export function XmaPanel() {
  const state = useWorkbench();
  const [scale, setScale] = useState("20");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ preview: JsonObject; document: DraftDocument } | null>(null);
  const bundle = state.draft?.document.solve_bundle?.schema_version === "xma-solve-1.0" ? state.draft.document.solve_bundle : null;
  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    try { await work(); }
    catch (error) { state.set({ message: { tone: "error", text: error instanceof Error ? error.message : "操作失败" } }); }
    finally { setBusy(false); }
  };
  const load = (file?: File) => act(async () => {
    const response = await fetch(`/api/v2/xma/import-preview${scale ? `?target_flights=${scale}` : ""}`, {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file ?? "bundled",
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.detail?.message ?? "导入失败");
    setPreview(value);
  });
  const configure = (key: string, value: unknown) => act(async () => {
    if (!state.draft || !bundle) return;
    const document = structuredClone(state.draft.document);
    document.solve_bundle![key] = value;
    state.selectDraft(await api.saveDraft(state.draft.draft_id, state.draft.working_hash, document));
  });
  return <section className="audit-panel" aria-label="厦航数据接入">
    <h2>厦航数据与求解配置</h2><div className="page-actions">
      <label>研究规模 <select aria-label="厦航研究规模" value={scale} onChange={event => setScale(event.target.value)}>
        <option value="20">约 20 航班</option><option value="100">约 100 航班</option><option value="500">约 500 航班</option><option value="">全量</option>
      </select></label>
      <button className="button secondary" disabled={busy} onClick={() => load()}>读取项目厦航数据</button>
      <label className="button ghost file-button">上传厦航工作簿<input type="file" accept=".xlsx" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) load(file); event.target.value = ""; }} /></label>
    </div>
    {preview && <div><p>航班 {String((preview.preview.counts as JsonObject).flights)} 班 · 飞机 {String((preview.preview.counts as JsonObject).aircraft)} 架 · 联程 {String((preview.preview.counts as JsonObject).connected_pairs)} 对。保留整架飞机航线，外部进港中转航班按原时刻固定；子集评分仅针对该研究子问题。</p>
      <button className="button primary" disabled={busy} onClick={() => act(async () => { state.selectDraft(await api.importDraft(preview.document)); setPreview(null); })}>创建厦航研究草稿</button></div>}
    {bundle && <div className="page-actions">
      <label>目标函数 <select aria-label="厦航目标函数" disabled={busy} value={String(bundle.objective_profile)} onChange={event => configure("objective_profile", event.target.value)}>
        <option value="tianchi_2017">天池评分（数据包源码）</option><option value="air_linear_v1">AIR 线性成本（独立研究配置）</option>
      </select></label>
      <label>算法 <select aria-label="厦航求解算法" disabled={busy} value={String(bundle.algorithm)} onChange={event => configure("algorithm", event.target.value)}>
        <option value="joint_arc_flow">直接联合优化</option><option value="joint_path_oracle">显式航班串基准（小实例）</option>
        <option value="benders_joint">Benders + 联合子问题</option><option value="benders_cg_bp">Benders + 列生成 + 分支定价</option>
      </select></label>
      {([['delay_step_minutes', '延误步长（分钟）', 1, 360], ['maximum_delay_minutes', '最大延误（分钟）', 0, 2160], ['time_limit_seconds', '求解时限（秒）', 1, 86400], ['max_assignment_options', '飞机分配规模上限', 1, 10000000]] as const).map(([key, label, min, max]) => <label key={key}>{label}<input type="number" min={min} max={max} disabled={busy} key={String(bundle[key])} defaultValue={Number(bundle[key])} onBlur={event => { const value = Number(event.target.value); if (Number.isInteger(value) && value >= min && value <= max && value !== bundle[key]) configure(key, value); }} /></label>)}
      <span>机组关闭 · 座位随飞机分配 · 两套目标独立</span>
    </div>}
  </section>;
}

export function XmaResult() {
  const state = useWorkbench();
  const result = state.run?.result;
  if (result?.schema_version !== "xma-result-1.0") return null;
  const rows = (result.passenger_allocations ?? []) as JsonObject[];
  const shownRows = rows.map(row => ({ "航班": row.flight_id, "实际座位": row.physical_seats, "已占座": row.occupied_seats,
    "原旅客驻留": row.resident, "改签送出": row.sign_out, "改签接收": row.sign_in, "未服务": row.unserved,
    "进港取消": row.cancelled_in, "中转失败": row.failed_in }));
  const objective = result.objective as JsonObject | null;
  const profile=objective?.profile === "tianchi_2017" ? "天池评分" : objective?.profile === "air_linear_v1" ? "AIR 线性研究成本" : "—";
  const status=result.status === "optimal" ? "最优（当前候选范围）" : result.status === "not_converged" ? "未收敛" : result.status === "infeasible" ? "当前候选无可行解" : String(result.status);
  return <section className="audit-panel"><h2>厦航恢复与旅客分配</h2>
    <p>目标：{profile} · 成本：{String(objective?.total ?? "—")} · 状态：{status}。人数按航段评分口径展示。</p>
    <button className="button secondary" disabled={!rows.length} onClick={() => { window.location.href = `/api/v2/xma/runs/${state.run!.run_id}/csv`; }}>导出天池 11 列结果</button>
    <VirtualTable rows={shownRows} idKey="航班" onSelect={() => {}} />
    <details><summary>逐项评分与独立审计</summary><pre className="json-block">{JSON.stringify(result.independent_audit, null, 2)}</pre></details>
  </section>;
}
