import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, FileJson, Layers3, Plane, Plus } from "lucide-react";
import { api } from "./api";
import { Button, Field, JsonDetails, Message, Modal } from "./components";
import { blankDocument } from "./data";
import { execute, notify, object, selectDraft, useWb } from "./state";
import { parseJson } from "./json";
import type { DraftDocument, JsonObject } from "./types";

export function ImportDialog({ onClose }: { onClose: () => void }) {
  const [mode, setMode] = useState("case");
  const [selection, setSelection] = useState("fixed");
  const [scale, setScale] = useState("20");
  const [seed, setSeed] = useState("20261106");
  const [file, setFile] = useState<File | null>(null);
  const [jsonFile, setJsonFile] = useState<File | null>(null);
  const [name, setName] = useState("新研究草稿");
  const [preview, setPreview] = useState<{ preview: JsonObject; document: DraftDocument } | null>(null);
  const busy = useWb(s => s.busy);
  const cases = useQuery({ queryKey: ["wb3", "cases"], queryFn: api.cases });
  const cache = useQueryClient();
  const create = (job: () => Promise<import("./types").Draft>) => execute("正在创建草稿", async () => {
    const draft = await job(); selectDraft(draft); await cache.invalidateQueries({ queryKey: ["wb3", "drafts"] }); notify(`已创建草稿「${draft.name}」。`, "success"); onClose();
  });
  const requestPreview = () => execute("正在读取厦航数据", async () => {
    if (scale && (!Number.isInteger(Number(scale)) || Number(scale) < 1)) throw new Error("目标航班数必须为正整数。");
    if (seed && (!Number.isInteger(Number(seed)) || Number(seed) < 0)) throw new Error("随机种子必须为非负整数。");
    const params = new URLSearchParams({ selection_mode: selection });
    if (scale) params.set("target_flights", scale);
    if (selection === "random" && seed) params.set("selection_seed", seed);
    const response = await fetch(`/api/v2/xma/import-preview?${params}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file ?? "bundled" });
    const value = await parseJson<{ preview: JsonObject; document: DraftDocument; detail?: { message?: string } }>(await response.text());
    if (!response.ok) throw new Error(String(value.detail?.message ?? "厦航预览生成失败。"));
    setPreview(value);
  });
  return <Modal title="新建或导入研究草稿" onClose={() => !busy && onClose()} wide>
    <p className="muted">选择数据来源，创建可编辑副本。导入后，在数据准备中统一检查和保存。</p>
    <div className="segmented import-tabs" aria-label="数据来源">{[["case", "Case 库", Layers3], ["xma", "厦航数据", Plane], ["json", "JSON 导入", FileJson], ["blank", "空白草稿", Plus]].map(([id, label, Icon]) => <Button key={String(id)} aria-pressed={mode === id} disabled={!!busy} onClick={() => setMode(String(id))}>{typeof Icon !== "string" && <Icon size={16}/>} {String(label)}</Button>)}</div>
    {mode === "case" && <div className="case-grid">{cases.isPending && <p>正在读取 Case 库…</p>}{cases.isError && <Message tone="error">Case 库读取失败。<Button onClick={() => cases.refetch()}>重试</Button></Message>}{cases.data?.map(item => <article className="case-card" key={item.case_id}><span className="eyebrow">{item.category}</span><h3>{item.label}</h3><p>{item.description}</p><div className="tag-row">{item.tags.slice(0, 4).map(tag => <span className="tag" key={tag}>{tag}</span>)}</div><Button disabled={!!busy} onClick={() => create(() => api.createDraft(item.case_id))}>克隆为草稿 <ArrowRight size={15}/></Button></article>)}</div>}
    {mode === "xma" && <div className="stack"><div className="form-grid">
      <Field label="抽样方式"><select value={selection} onChange={e => { setSelection(e.target.value); setPreview(null); }}><option value="fixed">固定子集</option><option value="random">随机抽样（保留完整机尾）</option></select></Field>
      <Field label="目标航班数" hint="实际数量以完整机尾选取结果为准"><select value={["20", "100", "500", ""].includes(scale) ? scale : "custom"} onChange={e => { setScale(e.target.value === "custom" ? "50" : e.target.value); setPreview(null); }}><option value="20">约 20 班</option><option value="100">约 100 班</option><option value="500">约 500 班</option><option value="">全量</option><option value="custom">自定义</option></select></Field>
      {selection === "random" && <><Field label="随机目标航班数"><input type="number" min="1" value={scale} onChange={e => { setScale(e.target.value); setPreview(null); }}/></Field><Field label="随机种子" hint="保留种子便于复现样本"><input type="number" min="0" value={seed} onChange={e => { setSeed(e.target.value); setPreview(null); }}/></Field></>}
      <Field label="工作簿来源" hint={file ? file.name : "未上传时使用项目现有数据"}><input type="file" accept=".xlsx" onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); }}/></Field>
    </div><div className="actions"><Button disabled={!!busy} onClick={requestPreview}>{busy || "生成导入预览"}</Button>{file && <Button variant="quiet" disabled={!!busy} onClick={() => { setFile(null); setPreview(null); }}>改用项目数据</Button>}</div>
    {preview && <div className="import-preview"><h3>样本已就绪</h3><div className="metric-grid"><div><span>实际航班</span><strong>{String(object(preview.preview.counts).flights ?? "—")}</strong></div><div><span>飞机</span><strong>{String(object(preview.preview.counts).aircraft ?? "—")}</strong></div><div><span>随机种子</span><strong>{String(object(preview.preview.selection).seed ?? "固定子集")}</strong></div></div><p>旅客数与评分按此研究子问题计算；时间使用北京时间。</p><JsonDetails summary="样本来源与 hash" value={preview.preview}/><Button variant="primary" disabled={!!busy} onClick={() => create(() => api.importDraft(preview.document))}>使用预览创建草稿 <ArrowRight size={16}/></Button></div>}</div>}
    {mode === "json" && <div className="stack"><Field label="草稿 JSON 文件" hint="使用 Workbench 2.0.0 草稿格式"><input type="file" accept=".json,application/json" onChange={e => setJsonFile(e.target.files?.[0] ?? null)}/></Field><Button variant="primary" disabled={!!busy || !jsonFile} onClick={() => create(async () => api.importDraft(await parseJson<DraftDocument>(await jsonFile!.text())))}>导入为新草稿</Button></div>}
    {mode === "blank" && <div className="stack"><Field label="草稿名称"><input value={name} onChange={e => setName(e.target.value)}/></Field><Message>空白草稿需要补充资源、恢复窗口与候选。可通过高级数据 JSON 编辑，校验通过后才能运行。</Message><Button variant="primary" disabled={!!busy || !name.trim()} onClick={() => create(() => api.importDraft({ ...blankDocument(), name: name.trim() }))}>创建空白草稿</Button></div>}
  </Modal>;
}
