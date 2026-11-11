import { create } from "zustand";
import { api, ApiError, writeProfile } from "./api";
import { setPath } from "./immutable";
import { parseJson, stringifyJson } from "./json";
import type { CompilePreview, Draft, DraftDocument, JsonObject, RunEvent, RunRecord } from "./types";

export type Theme = "light" | "dark";
type Notice = { tone: "success" | "error" | "info"; text: string };
interface State {
  draft: Draft | null;
  document: DraftDocument | null;
  rawText: string | null;
  past: DraftDocument[];
  future: DraftDocument[];
  version: number;
  epoch: number;
  preview: CompilePreview | null;
  busy: string;
  busyStage: string;
  busyStartedAt: number | null;
  notice: Notice | null;
  conflict: boolean;
  runtimeProfile: string;
  checkedProfile: string | null;
  runtimeEdits: JsonObject | null;
  run: RunRecord | null;
  events: RunEvent[];
  connection: string;
  theme: Theme;
  set: (patch: Partial<State>) => void;
}
function preference(key: string) { try { return localStorage.getItem(`wb3.${key}`); } catch { return null; } }
export function remember(key: string, value: string) { try { localStorage.setItem(`wb3.${key}`, value); } catch { /* Private mode still works. */ } }
export const useWb = create<State>((set) => ({
  draft: null, document: null, rawText: null, past: [], future: [], version: 0, epoch: 0, preview: null, busy: "", busyStage: "", busyStartedAt: null, notice: null,
  conflict: false, runtimeProfile: "default-exact", checkedProfile: null, runtimeEdits: null, run: null, events: [], connection: "尚未连接运行",
  theme: preference("theme") === "dark" ? "dark" : "light", set,
}));
export const lastSelection = () => ({ draft: preference("draft"), run: preference("run") });
export function isDirty(state: Pick<State, "draft" | "document" | "rawText" | "runtimeEdits"> = useWb.getState()) {
  if (!state.draft || !state.document) return false;
  return state.runtimeEdits !== null || state.rawText !== null || state.document !== state.draft.document;
}
export function selectDraft(draft: Draft) {
  const state = useWb.getState();
  remember("draft", draft.draft_id);
  useWb.setState({ draft, document: draft.document, rawText: null, past: [], future: [], preview: null,
    version: state.version + 1, epoch: state.epoch + 1, conflict: false, checkedProfile: null, runtimeEdits: null,
    runtimeProfile: preference(`profile.${draft.draft_id}`) ?? "default-exact" });
}
export async function loadDraft(id: string) {
  const epoch = useWb.getState().epoch + 1;
  useWb.setState({ epoch });
  const draft = await api.draft(id);
  if (useWb.getState().epoch === epoch) selectDraft(draft);
}
export function editDocument(edit: (doc: DraftDocument) => void) {
  // Compatibility for whole-document transformations; form fields use patchDocument.
  updateDocument(source => { const document = structuredClone(source); edit(document); return document; });
}
export function updateDocument(update: (doc: DraftDocument) => DraftDocument) {
  const state = useWb.getState();
  if (!state.document) return;
  const document = update(state.document);
  if (document === state.document) return;
  useWb.setState({ document, rawText: null, preview: null, checkedProfile: null, version: state.version + 1, past: [...state.past.slice(-14), state.document], future: [] });
}
export function patchDocument(path: readonly (string | number)[], value: unknown) {
  updateDocument(document => setPath(document, path, value));
}
export function undoDocument(redo = false) {
  const state = useWb.getState();
  const from = redo ? state.future : state.past;
  if (!from.length || !state.document || state.busy) return;
  const document = from.at(-1)!;
  useWb.setState({ document, rawText: null, preview: null, checkedProfile: null, version: state.version + 1,
    past: redo ? [...state.past, state.document] : state.past.slice(0, -1), future: redo ? state.future.slice(0, -1) : [...state.future, state.document] });
}
export function editRaw(rawText: string) {
  useWb.setState(s => ({ rawText, preview: null, checkedProfile: null, version: s.version + 1 }));
}
export function discardEdits() {
  const draft = useWb.getState().draft;
  if (draft) selectDraft(draft);
}
export function notify(text: string, tone: Notice["tone"] = "info") { useWb.setState({ notice: { text, tone } }); }
export async function execute(label: string, work: () => Promise<void>) {
  if (useWb.getState().busy) return false;
  useWb.setState({ busy: label, busyStage: label, busyStartedAt: Date.now(), notice: null });
  try { await new Promise(resolve => setTimeout(resolve, 0)); await work(); return true; }
  catch (error) {
    const conflict = error instanceof ApiError && error.status === 409 && ["draft_hash_conflict", "snapshot_hash_conflict"].includes(String(error.detail.code ?? "draft_hash_conflict"));
    useWb.setState({ conflict: conflict || useWb.getState().conflict });
    const detail = error instanceof ApiError && Array.isArray(error.detail) ? error.detail.map((item: { loc?: unknown[]; msg?: string }) => `${item.loc?.join(".") ?? "输入"}：${item.msg ?? "无效"}`).join("；") : null;
    notify(conflict ? "服务器上的版本已变化，本地修改已保留。可导出本地副本，再重新载入服务器版本。" : detail || (error instanceof Error ? error.message : "操作失败，请重试。"), "error");
    return false;
  } finally { useWb.setState({ busy: "", busyStage: "", busyStartedAt: null }); }
}
function operationStage(busyStage: string) { if (useWb.getState().busy) useWb.setState({ busyStage }); }
function validDocument(doc: DraftDocument | null): DraftDocument {
  if (!doc || doc.schema_version !== "2.0.0" || !doc.scenario || !Array.isArray(doc.typed_disruptions)) throw new Error("草稿 JSON 缺少 schema_version、scenario 或 typed_disruptions，请检查高级编辑。");
  return doc;
}
export function materialize(): DraftDocument {
  const state = useWb.getState();
  const doc = state.rawText === null ? state.document : JSON.parse(state.rawText) as DraftDocument;
  return validDocument(doc);
}
export async function applyRawDocument() {
  const initial = useWb.getState();
  if (initial.rawText === null) return;
  const document = validDocument(await parseJson<DraftDocument>(initial.rawText));
  if (useWb.getState().epoch !== initial.epoch || useWb.getState().version !== initial.version) return;
  updateDocument(() => document);
}
export function saveOnly() { return persistInput(false); }
export function saveAndValidate() { return persistInput(true); }
async function persistInput(validate: boolean) {
  const initial = useWb.getState();
  if (!initial.draft) throw new Error("请先创建或选择草稿。");
  operationStage("正在准备保存数据");
  const doc = initial.rawText === null ? materialize() : validDocument(await parseJson<DraftDocument>(initial.rawText));
  let saved = initial.draft;
  if (doc !== initial.draft.document) {
    operationStage("正在保存数据");
    saved = await api.saveDraft(initial.draft.draft_id, initial.draft.working_hash, doc);
  }
  // Keep the accepted base hash even if saving a separate runtime profile fails.
  if (saved !== initial.draft && useWb.getState().epoch === initial.epoch) useWb.setState({ draft: saved });
  if (initial.runtimeEdits) operationStage("正在保存求解配置");
  const profile = initial.runtimeEdits ? await writeProfile(initial.runtimeProfile, initial.runtimeEdits) : initial.runtimeProfile;
  let current = useWb.getState();
  if (current.epoch !== initial.epoch) return;
  // A save response never overwrites edits typed while that request was pending.
  if (current.version !== initial.version) {
    useWb.setState({ draft: saved, preview: null });
    throw new Error("保存期间产生了新的修改，请再次保存并校验。");
  }
  useWb.setState({ draft: saved, document: saved.document, rawText: null, conflict: false, runtimeEdits: null, runtimeProfile: profile });
  remember(`profile.${saved.draft_id}`, profile);
  if (!validate) { notify("草稿与配置已保存；开始求解前仍需通过校验。", "success"); return; }
  operationStage("正在校验输入与生成候选");
  const preview = await api.compile(saved.draft_id);
  current = useWb.getState();
  if (current.epoch !== initial.epoch || current.version !== initial.version || current.draft?.working_hash !== saved.working_hash) return;
  useWb.setState({ preview, checkedProfile: current.runtimeProfile });
  notify(preview.valid ? "保存与校验完成，输入已就绪。" : "已保存；输入校验未通过，请处理列出的问题。", preview.valid ? "success" : "error");
}
export function startBlockers(state = useWb.getState()) {
  const reasons: string[] = [];
  if (!state.draft) reasons.push("请先创建或导入草稿");
  if (isDirty(state)) reasons.push("存在未保存修改");
  if (state.conflict) reasons.push("请先处理版本冲突");
  if (!state.preview || state.preview.draft_hash !== state.draft?.working_hash || state.checkedProfile !== state.runtimeProfile) reasons.push("请先保存并校验当前数据和配置");
  else if (!state.preview.valid) reasons.push("输入校验未通过");
  else if (!state.preview.solve_request) reasons.push("缺少可求解输入，请检查候选和资源配置");
  if (state.run && !terminal(state.run)) reasons.push("当前监控的运行尚未结束");
  if (state.busy) reasons.push(state.busy);
  return [...new Set(reasons)];
}
export function terminal(run: RunRecord) { return ["completed", "failed", "cancelled", "interrupted"].includes(run.job_status); }
export function chooseRun(run: RunRecord) {
  remember("run", run.run_id);
  useWb.setState({ run, events: [], connection: terminal(run) ? "正在读取历史事件" : "正在连接运行" });
}
export async function startRun() {
  const state = useWb.getState();
  const reasons = startBlockers({ ...state, busy: "" });
  if (reasons.length) throw new Error(reasons.join("；"));
  operationStage("正在建立并校验运行快照");
  const snapshot = await api.snapshot(state.draft!, "Workbench v3 · 已保存并校验的输入");
  if (useWb.getState().epoch !== state.epoch || useWb.getState().version !== state.version || isDirty()) throw new Error("输入在建立快照时发生变化，请重新校验后运行。");
  operationStage("正在提交后台求解");
  const run = await api.createRun(snapshot.snapshot_id, state.runtimeProfile);
  // A draft switch while submitting must not select an unrelated run afterwards.
  if (useWb.getState().epoch === state.epoch) chooseRun(run);
  notify("运行已提交，正在监控不可变输入快照。", "success");
}
export function mergeEvents(existing: RunEvent[], incoming: RunEvent[]) {
  if (!incoming.length) return existing;
  const added = [...incoming].sort((a, b) => a.seq - b.seq);
  const ordered = existing.every((event, i) => !i || existing[i - 1].seq < event.seq);
  if (ordered && (!existing.length || added[0].seq > existing.at(-1)!.seq) && added.every((event, i) => !i || added[i - 1].seq < event.seq)) return [...existing, ...added];
  return [...new Map([...existing, ...added].map(item => [item.seq, item])).values()].sort((a, b) => a.seq - b.seq);
}
export async function download(name: string, content: unknown) {
  const text = typeof content === "string" ? content : await stringifyJson(content, 2);
  const url = URL.createObjectURL(new Blob([text], { type: "application/json;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function downloadFile(path: string, name: string) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`导出失败（HTTP ${response.status}），请重试。`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a"); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const object = (value: unknown): JsonObject => value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
export const rows = (value: unknown): JsonObject[] => Array.isArray(value) ? value as JsonObject[] : [];
export function statusLabel(run: RunRecord | null) {
  if (!run) return "尚无运行";
  if (run.job_status !== "completed") return ({ queued: "排队中", preparing: "准备中", running: "求解中", failed: "执行失败", cancelled: "已取消", interrupted: "已中断" })[run.job_status] ?? run.job_status;
  const status = run.optimization_status ?? String(run.result?.status ?? "");
  return ({ optimal: "证明最优", feasible: "合法可行", infeasible: "认证不可行", not_converged: "未收敛", time_limit: "达到时限" } as Record<string, string>)[status] ?? "执行完成 · 见审计结论";
}
