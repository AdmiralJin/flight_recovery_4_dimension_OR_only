import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, CopyPlus, Download, Redo2, Save, Undo2, Upload } from "lucide-react";
import { api } from "../api";
import { VirtualTable } from "../components/VirtualTable";
import { useWorkbench } from "../store";
import type { DraftDocument, JsonObject } from "../types";

const entities = [
  ["flights", "航班计划", "flight_id"], ["airports", "机场", "airport_id"], ["aircraft", "飞机", "tail_id"],
  ["crew", "机组", "crew_id"], ["passengers", "旅客", "pax_group_id"], ["disruptions", "旧扰动", "disruption_id"],
  ["typed_disruptions", "类型化扰动", "rule_id"], ["flight_options", "Flight Options", "option_id"],
  ["passenger_itineraries", "Passenger Itineraries", "itinerary_id"], ["capacity", "剩余容量", "option_id"],
  ["costs", "成本", "key"], ["profiles", "Profiles", "key"],
] as const;

function nested(value: unknown, key: string): JsonObject[] {
  if (!value || typeof value !== "object") return [];
  const found = (value as JsonObject)[key];
  return Array.isArray(found) ? (found as JsonObject[]) : [];
}

function rowsFor(document: DraftDocument, key: string): JsonObject[] {
  const scenario = document.scenario;
  const bundle = document.solve_bundle as JsonObject | null | undefined;
  const columns = bundle?.recovery_columns as JsonObject | undefined;
  if (["flights", "airports", "aircraft", "crew", "passengers", "disruptions"].includes(key)) return nested(scenario, key);
  if (key === "typed_disruptions") return document.typed_disruptions;
  if (key === "flight_options" || key === "passenger_itineraries") return nested(columns, key);
  if (key === "capacity") {
    const profile = bundle?.capacity_profile as JsonObject | undefined;
    const values = (profile?.seat_capacity_by_option_id ?? {}) as Record<string, number>;
    return Object.entries(values).map(([option_id, residual_seats]) => ({ option_id, residual_seats }));
  }
  if (key === "costs") return Object.entries((bundle?.cost_overrides ?? {}) as JsonObject).map(([name, value]) => ({ key: name, value }));
  if (key === "profiles") return Object.entries((bundle?.profile_ids ?? {}) as JsonObject).map(([name, value]) => ({ key: name, value }));
  return [];
}

export function DataStudio() {
  const state = useWorkbench();
  const query = useQueryClient();
  const [tab, setTab] = useState("flights");
  const [selected, setSelected] = useState<JsonObject | null>(null);
  const [editor, setEditor] = useState("");
  const [libraryOpen, setLibraryOpen] = useState(!state.draft);
  const history = useRef<string[]>([]);
  const future = useRef<string[]>([]);
  const active = entities.find(([key]) => key === tab) ?? entities[0];
  useEffect(() => {
    if (state.draft) setLibraryOpen(false);
  }, [state.draft?.draft_id]);
  const rows = useMemo(() => state.draft ? rowsFor(state.draft.document, tab) : [], [state.draft, tab]);

  const clone = useMutation({ mutationFn: api.createDraft, onSuccess: async (draft) => {
    state.selectDraft(draft); setLibraryOpen(false); await query.invalidateQueries({ queryKey: ["drafts"] });
    state.set({ message: { tone: "success", text: `已克隆为草稿“${draft.name}”。内置 Case 保持只读。` } });
  }});
  const save = useMutation({ mutationFn: async () => {
    if (!state.draft || !selected) throw new Error("没有选中记录");
    const parsed = JSON.parse(editor) as JsonObject;
    const document = structuredClone(state.draft.document);
    const idKey = active[2];
    const replace = (values: JsonObject[]) => values.map((item) => String(item[idKey]) === String(selected[idKey]) ? parsed : item);
    if (["flights", "airports", "aircraft", "crew", "passengers", "disruptions"].includes(tab)) {
      (document.scenario as JsonObject)[tab] = replace(nested(document.scenario, tab));
    } else if (tab === "typed_disruptions") document.typed_disruptions = replace(document.typed_disruptions);
    else if (tab === "flight_options" || tab === "passenger_itineraries") {
      const bundle = document.solve_bundle as JsonObject;
      const columns = bundle.recovery_columns as JsonObject;
      columns[tab] = replace(nested(columns, tab));
    } else if (tab === "capacity") {
      const bundle = document.solve_bundle as JsonObject;
      const profile = bundle.capacity_profile as JsonObject;
      const values = profile.seat_capacity_by_option_id as Record<string, number>;
      const previous = String(selected.option_id);
      const next = String(parsed.option_id);
      if (previous !== next) delete values[previous];
      values[next] = Number(parsed.residual_seats);
    } else if (tab === "costs") {
      const bundle = document.solve_bundle as JsonObject;
      const values = bundle.cost_overrides as Record<string, number>;
      const previous = String(selected.key);
      const next = String(parsed.key);
      if (previous !== next) delete values[previous];
      values[next] = Number(parsed.value);
    } else if (tab === "profiles") {
      const bundle = document.solve_bundle as JsonObject;
      const values = bundle.profile_ids as Record<string, string>;
      const previous = String(selected.key);
      const next = String(parsed.key);
      if (previous !== next) delete values[previous];
      values[next] = String(parsed.value);
    } else throw new Error("该视图请通过高级导入修改");
    return api.saveDraft(state.draft.draft_id, state.draft.working_hash, document);
  }, onSuccess: async (draft) => { state.selectDraft(draft); setSelected(null); await query.invalidateQueries({ queryKey: ["drafts"] }); state.set({ message: { tone: "success", text: "工作副本已原子保存；派生编译状态已失效。" } }); }, onError: (error) => state.set({ message: { tone: "error", text: error instanceof Error ? error.message : "保存失败" } }) });

  const choose = (row: JsonObject) => { history.current = []; future.current = []; const value = JSON.stringify(row, null, 2); setSelected(row); setEditor(value); };
  const changeEditor = (value: string) => { history.current.push(editor); if (history.current.length > 50) history.current.shift(); future.current = []; setEditor(value); };
  const undo = () => { const value = history.current.pop(); if (value !== undefined) { future.current.push(editor); setEditor(value); } };
  const redo = () => { const value = future.current.pop(); if (value !== undefined) { history.current.push(editor); setEditor(value); } };
  const exportDraft = () => { if (!state.draft) return; const blob = new Blob([JSON.stringify(state.draft.document, null, 2)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${state.draft.name}.draft.json`; link.click(); URL.revokeObjectURL(link.href); };

  return (
    <div className="page data-page">
      <PageHead eyebrow="01 / DATA DESIGN" title="数据设计" description="完整检查 Scenario、候选、容量、成本与求解 Profile；所有派生状态绑定内容 hash。">
        <button className="button secondary" type="button" onClick={() => setLibraryOpen(true)}><CopyPlus />克隆内置 Case</button>
        <label className="button ghost file-button"><Upload />导入草稿<input type="file" accept="application/json" onChange={async (event) => { const file = event.target.files?.[0]; if (!file) return; const draft = await api.importDraft(JSON.parse(await file.text())); state.selectDraft(draft); query.invalidateQueries({ queryKey: ["drafts"] }); }} /></label>
        <button className="button ghost" type="button" disabled={!state.draft} onClick={exportDraft}><Download />导出</button>
      </PageHead>
      {!state.draft ? <div className="empty-state large"><DatabaseEmpty /><h2>先选择一个内置 Case</h2><p>内置 Case 只读；克隆后才能设计和保存。</p><button className="button primary" type="button" onClick={() => setLibraryOpen(true)}>打开 Case 库</button></div> : <>
        <div className="entity-tabs" role="tablist" aria-label="数据实体">{entities.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => { setTab(key); setSelected(null); }}>{label}<span>{rowsFor(state.draft!.document, key).length}</span></button>)}</div>
        <div className="split-workspace">
          <VirtualTable rows={rows} idKey={active[2]} selectedId={selected ? String(selected[active[2]] ?? "") : null} onSelect={choose} />
          <aside className="inspector" aria-label="记录检查器">
            <div className="inspector-head"><div><span>记录检查器</span><strong>{selected ? String(selected[active[2]] ?? "未命名") : "未选择"}</strong></div><div className="icon-group"><button title="撤销" aria-label="撤销" type="button" disabled={!history.current.length} onClick={undo}><Undo2 /></button><button title="重做" aria-label="重做" type="button" disabled={!future.current.length} onClick={redo}><Redo2 /></button></div></div>
            {selected ? <><textarea value={editor} onChange={(event) => changeEditor(event.target.value)} spellCheck={false} aria-label="选中记录 JSON" /><button className="button primary full" type="button" disabled={save.isPending} onClick={() => save.mutate()}><Save />{save.isPending ? "保存中…" : "保存工作副本"}</button></> : <div className="empty-note">选择一行查看字段。桌面端可编辑；保存时会重新执行 Schema 校验。</div>}
          </aside>
        </div>
      </>}
      {libraryOpen && <div className="drawer-backdrop" onMouseDown={() => state.draft && setLibraryOpen(false)}><aside className="case-drawer" onMouseDown={(event) => event.stopPropagation()} aria-label="内置 Case 库"><div className="drawer-head"><div><span>只读 Case 库</span><h2>选择研究基线</h2></div><button type="button" onClick={() => setLibraryOpen(false)} aria-label="关闭">×</button></div><div className="case-list">{state.cases.map((item) => <article key={item.case_id}><div><span className="case-category">{item.category}</span><h3>{item.label}</h3><p>{item.description}</p><div className="tag-row">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div></div><button className="button secondary" type="button" disabled={clone.isPending} onClick={() => clone.mutate(item.case_id)}>{clone.isPending ? "克隆中…" : "克隆为草稿"}</button></article>)}</div></aside></div>}
    </div>
  );
}

function PageHead({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) { return <header className="page-head"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div><div className="page-actions">{children}</div></header>; }
function DatabaseEmpty() { return <div className="empty-symbol" aria-hidden="true"><Check /></div>; }
export { PageHead };
