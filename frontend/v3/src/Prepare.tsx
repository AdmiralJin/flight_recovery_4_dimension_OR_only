import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { ArrowRight, CheckCheck, Download, Plus, RotateCcw, Save, Undo2, Redo2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "./api";
import { Button, Card, DataTable, Empty, Field, JsonDetails, labelFor, LazyDetails, Message, Modal, useGuard } from "./components";
import { entityGroups, entityRows, isXma, replaceRowImmutable } from "./data";
import { ImportDialog } from "./ImportDialog";
import { applyRawDocument, download, editRaw, execute, isDirty, loadDraft, notify, patchDocument, saveAndValidate, saveOnly, undoDocument, updateDocument, useWb } from "./state";
import { stringifyJson } from "./json";
import type { DraftDocument, JsonObject } from "./types";

export const Prepare = memo(function Prepare() {
  const state = useWb(useShallow(s => ({ document: s.document, draft: s.draft, rawText: s.rawText, runtimeEdits: s.runtimeEdits, past: s.past, future: s.future, preview: s.preview, conflict: s.conflict, busy: s.busy })));
  const guard = useGuard();
  const [importOpen, setImportOpen] = useState(false);
  const [group, setGroup] = useState("resources");
  const [entity, setEntity] = useState("flights");
  const [selected, setSelected] = useState<number | null>(null);
  const doc = state.document;
  const xma = isXma(doc);
  const activeGroup = entityGroups.find(item => item.id === group)!;
  const entities = activeGroup.entities.filter(([key]) => !xma || ["flights", "aircraft", "disruptions", "costs"].includes(key));
  const definition = entities.find(([key]) => key === entity) ?? entities[0];
  const activeEntity = definition?.[0] ?? entity;
  const records = useMemo(() => doc ? entityRows(doc, activeEntity) : [], [doc, activeEntity]);
  const selectRecord = useCallback((_row: JsonObject, index: number) => setSelected(index), []);
  useEffect(() => setSelected(null), [state.draft?.draft_id]);
  const selectedRow = selected === null ? null : records[selected];
  const openImport = () => guard(() => setImportOpen(true));
  const exportLocal = () => execute("正在导出草稿", () => download(`${doc?.name ?? "draft"}.draft.json`, state.rawText ?? doc));
  const editRecord = (row: JsonObject) => updateDocument(target => replaceRowImmutable(target, activeEntity, selected!, row));
  const changeGroup = (id: string) => { setGroup(id); setSelected(null); setEntity(entityGroups.find(item => item.id === id)?.entities[0]?.[0] ?? "flights"); };
  return <div className="workspace stack">
    <header className="page-head"><div><span className="eyebrow">01 / PREPARE</span><h1>数据准备</h1><p>整理研究输入，让每次求解都有清楚的起点。</p></div><div className="actions"><Button onClick={openImport}><Plus size={17}/>新建 / 导入</Button>{doc && <Button variant="quiet" onClick={exportLocal}><Download size={16}/>导出草稿</Button>}<Button loading={state.busy === "正在保存草稿"} disabled={!doc || !!state.busy || !isDirty(state)} title="只保存修改，暂不生成候选或执行输入校验" onClick={() => execute("正在保存草稿", saveOnly)}><Save size={17}/>仅保存</Button><Button variant="primary" loading={state.busy === "正在保存并校验"} disabled={!doc || !!state.busy} onClick={() => execute("正在保存并校验", saveAndValidate)}><CheckCheck size={17}/>保存并校验</Button></div></header>
    {!doc ? <Card><Empty title="从一个研究草稿开始" action={<Button variant="primary" onClick={openImport}>选择数据来源 <ArrowRight size={16}/></Button>}>克隆项目 Case、读取厦航数据，或导入已有草稿。</Empty></Card> : <>
      <div className="study-summary"><div><span className="tag">{xma ? "厦航研究" : "AIR 研究"}</span><h2>{doc.name}</h2><p>{xma ? "北京时间 · 整机尾抽样 · 机组模块关闭" : "UTC · 航班、飞机、机组与旅客联合恢复"}</p></div><div className="study-counts">{[["航班", "flights"], ["飞机", "aircraft"], [xma ? "来源扰动" : "旅客组", xma ? "disruptions" : "passengers"]].map(([label, key]) => <div key={key}><strong>{entityRows(doc, key).length.toLocaleString()}</strong><span>{label}</span></div>)}</div></div>
      {state.conflict && <Message tone="error">版本冲突：本地修改已保留。<Button onClick={exportLocal}>导出本地副本</Button><Button onClick={() => guard(() => execute("重新载入中", () => loadDraft(state.draft!.draft_id)))}>重新载入服务器版本</Button></Message>}
      <div className="editor-utilities"><Field label="研究草稿名称"><input value={doc.name} disabled={!!state.busy || state.rawText !== null} onChange={e => patchDocument(["name"], e.target.value)}/></Field><div className="actions"><Button variant="quiet" aria-label="撤销数据修改" disabled={!state.past.length || !!state.busy || state.rawText !== null} onClick={() => undoDocument()}><Undo2 size={16}/></Button><Button variant="quiet" aria-label="重做数据修改" disabled={!state.future.length || !!state.busy || state.rawText !== null} onClick={() => undoDocument(true)}><Redo2 size={16}/></Button></div></div>
      <div className="prepare-layout"><nav className="group-nav" aria-label="数据分组">{entityGroups.map(item => <button key={item.id} aria-current={group === item.id ? "page" : undefined} onClick={() => changeGroup(item.id)}><span title={item.note}>{item.name}</span><small>{item.note}</small></button>)}</nav>
        <div className="stack min-zero">{group === "validation" ? <Validation/> : <Card title={activeGroup.name} note={group === "resources" ? "选择记录编辑常用字段；复杂结构可在高级数据中完整编辑。" : undefined} actions={entities.length > 0 && <label className="inline-field">数据类型<select aria-label="数据类型" value={activeEntity} disabled={state.rawText !== null} onChange={e => { setEntity(e.target.value); setSelected(null); }}>{entities.map(([key, label]) => <option value={key} key={key}>{label} · {entityRows(doc, key).length}</option>)}</select></label>}>
          {state.rawText !== null && group !== "advanced" && <Message tone="warning">完整 JSON 有待应用的编辑。请先到高级数据应用或撤销，避免覆盖。</Message>}
          {entities.length ? <DataTable rows={records} idKey={definition?.[2]} onSelect={state.rawText === null ? selectRecord : undefined}/> : <p className="inset muted">该研究类型的数据由导入工作簿和完整 JSON 管理。</p>}
          {group === "advanced" && <div className="advanced-editor"><LazyDetails summary="完整草稿 JSON · 候选 / 配置 / 高级结构">{() => <AdvancedEditor document={doc}/>}</LazyDetails></div>}
        </Card>}
        {group !== "validation" && <div className="workflow-next"><span>{isDirty(state) ? "编辑尚未保存，原校验已失效。" : state.preview?.valid ? "当前输入已通过校验。" : "完成编辑后，请保存并校验。"}</span><Link className="text-link" to="/run">配置与运行 <ArrowRight size={16}/></Link></div>}
        </div></div>
    </>}
    {importOpen && <ImportDialog onClose={() => setImportOpen(false)}/>}
    {selectedRow && <Modal title={`编辑${definition?.[1] ?? "记录"}`} onClose={() => guard(() => setSelected(null))} wide>
      <p className="muted">标识符只读。时间按原数据的 {xma ? "北京时间" : "UTC"} 解释；提交后由输入校验检查引用与约束。</p>
      <div className="form-grid">{Object.entries(selectedRow).filter(([, value]) => typeof value !== "object" || value === null).map(([key, value]) => {
        const readOnly = /(^id$|_id$|^key$)/.test(key);
        const numeric = typeof value === "number";
        const nonnegative = numeric && /(seat|capacity|cost|count|size|minute|demand)/.test(key);
        const error = nonnegative && Number(value) < 0 ? "请输入非负数" : undefined;
        return <Field key={key} label={labelFor(key)} error={error} hint={readOnly ? "标识符默认只读" : undefined}>{typeof value === "boolean" ? <select value={String(value)} onChange={e => editRecord({ ...selectedRow, [key]: e.target.value === "true" })}><option value="true">是</option><option value="false">否</option></select> : <input readOnly={readOnly} type={numeric ? "number" : "text"} min={nonnegative ? 0 : undefined} value={String(value ?? "")} onChange={e => editRecord({ ...selectedRow, [key]: numeric && e.target.value !== "" ? Number(e.target.value) : e.target.value })}/>}</Field>;
      })}</div>
      <JsonDetails summary="查看完整记录与嵌套字段" value={selectedRow}><p>复杂结构在「高级数据 → 完整草稿 JSON」中编辑。</p></JsonDetails>
      <div className="dialog-actions"><Button onClick={() => guard(() => setSelected(null))}>关闭编辑</Button><Button variant="primary" loading={state.busy === "正在保存并校验"} disabled={!!state.busy} onClick={async () => { if (await execute("正在保存并校验", saveAndValidate) && !isDirty()) setSelected(null); }}>保存并校验</Button></div>
    </Modal>}
  </div>;
});

function AdvancedEditor({ document }: { document: DraftDocument }) {
  const { rawText, busy } = useWb(useShallow(s => ({ rawText: s.rawText, busy: s.busy })));
  const [formatted, setFormatted] = useState<{ document: DraftDocument; text: string } | null>(null);
  useEffect(() => {
    let disposed = false;
    void stringifyJson(document, 2).then(text => { if (!disposed) setFormatted({ document, text }); }, error => { if (!disposed) notify(String(error), "error"); });
    return () => { disposed = true; };
  }, [document]);
  const loading = rawText === null && formatted?.document !== document;
  return <><p>保留所有 API 字段。修改后需要应用到编辑副本，再保存并校验。</p><textarea className="code-editor" aria-label="完整草稿 JSON" spellCheck={false} disabled={loading || !!busy} placeholder={loading ? "正在准备 JSON 编辑器…" : undefined} value={rawText ?? (formatted?.document === document ? formatted.text : "")} onChange={event => editRaw(event.target.value)}/><div className="actions"><Button disabled={rawText === null || !!busy} onClick={() => execute("正在应用 JSON", applyRawDocument)}>应用到编辑副本</Button><Button variant="quiet" disabled={rawText === null || !!busy} onClick={() => useWb.setState({ rawText: null })}><RotateCcw size={15}/>撤销 JSON 编辑</Button></div></>;
}

export function Validation() {
  const { preview, busy, document, draft } = useWb(useShallow(s => ({ preview: s.preview, busy: s.busy, document: s.document, draft: s.draft })));
  return <Card title="输入校验与影响预览" note="校验绑定最近保存的输入；修改数据或配置后立即失效。" actions={<Button disabled={!document || !!busy} onClick={() => execute("正在保存并校验", saveAndValidate)}>保存并校验</Button>}>
    {!preview ? <Empty title="尚无当前输入的校验结果">先保存并校验，查看引用、候选和资源约束。</Empty> : <div className="stack inset">
      <Message tone={preview.valid ? "success" : "error"}>{preview.valid ? "输入校验通过" : "输入校验未通过"}{!preview.solve_request && "；当前缺少可求解输入。"}</Message>
      {!!preview.issues.length && <ul className="issue-list">{preview.issues.map((issue, index) => <li key={index}><span className={`tag ${issue.severity}`}>{issue.severity === "error" ? "错误" : issue.severity === "warning" ? "提醒" : "信息"}</span><div><strong>{issue.message}</strong><small>{issue.path} {issue.entity_id ?? ""}</small></div></li>)}</ul>}
      <div className="metric-grid">{Object.entries(preview.candidate_counts).map(([key, count]) => <div key={key}><span>{labelFor(key)}</span><strong>{count.toLocaleString()}</strong></div>)}</div>
      <LazyDetails summary={`航班扰动影响（${preview.flight_impacts.length}）`}>{() => <DataTable rows={preview.flight_impacts as unknown as JsonObject[]}/>}</LazyDetails>
      <LazyDetails summary={`容量变化（${preview.capacity_changes.length}）`}>{() => <DataTable rows={preview.capacity_changes}/>}</LazyDetails>
      <JsonDetails summary="完整校验与可视化预览" value={preview}><Button disabled={!draft || !!busy} onClick={() => execute("读取预览中", async () => download("draft-visualization.json", await api.draftVisualization(draft!.draft_id)))}>导出数据可视化模型</Button></JsonDetails>
    </div>}
  </Card>;
}
