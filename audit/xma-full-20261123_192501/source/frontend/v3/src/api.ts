import { ApiError } from "../../v2/src/api";
import { parseJson, stringifyJson } from "./json";
import type { Capabilities, CaseSummary, Comparison, CompilePreview, Draft, DraftDocument, JsonObject, RunEvent, RunRecord, Snapshot, VisualizationModel } from "./types";
export { ApiError };

// Same v2 endpoints and contracts; large JSON encoding/decoding runs off the UI thread.
async function request<T>(path: string, init?: RequestInit, value?: unknown): Promise<T> {
  const body = value === undefined ? init?.body : await stringifyJson(value);
  const response = await fetch(path, { ...init, body, headers: { "Content-Type": "application/json", ...init?.headers } });
  const text = await response.text();
  let data: JsonObject;
  try { data = await parseJson<JsonObject>(text); }
  catch { if (response.ok) throw new Error("服务器返回的数据不是有效 JSON，请重试。"); data = {}; }
  if (init?.signal?.aborted) throw new DOMException("请求已取消", "AbortError");
  if (!response.ok) {
    const detail = (data.detail ?? data) as JsonObject;
    throw new ApiError(response.status, String(detail.message ?? `HTTP ${response.status}`), detail);
  }
  return data as T;
}
const idPath = (id: string) => encodeURIComponent(id);
export const api = {
  capabilities: () => request<Capabilities>("/api/v2/capabilities"),
  cases: async () => (await request<{ cases: CaseSummary[] }>("/api/cases")).cases,
  drafts: async () => (await request<{ items: Draft[] }>("/api/v2/drafts")).items,
  draft: (id: string) => request<Draft>(`/api/v2/drafts/${idPath(id)}`),
  createDraft: (sourceCaseId: string) => request<Draft>("/api/v2/drafts", { method: "POST" }, { source_case_id: sourceCaseId }),
  importDraft: (document: DraftDocument) => request<Draft>("/api/v2/imports/draft", { method: "POST" }, document),
  saveDraft: (id: string, baseHash: string, document: DraftDocument) => request<Draft>(`/api/v2/drafts/${idPath(id)}/working-copy`, { method: "PUT" }, { base_hash: baseHash, document }),
  compile: (id: string) => request<CompilePreview>(`/api/v2/drafts/${idPath(id)}/compile`, { method: "POST", body: "{}" }),
  draftVisualization: (id: string) => request<VisualizationModel>(`/api/v2/drafts/${idPath(id)}/visualization`),
  snapshot: (draft: Draft, note = "") => request<Snapshot>(`/api/v2/drafts/${idPath(draft.draft_id)}/snapshots`, { method: "POST" }, { base_hash: draft.working_hash, note }),
  runs: async (draftId?: string) => (await request<{ items: RunRecord[] }>(`/api/v2/runs${draftId ? `?draft_id=${idPath(draftId)}` : ""}`)).items,
  run: (id: string, signal?: AbortSignal) => request<RunRecord>(`/api/v2/runs/${idPath(id)}`, { signal }),
  runEvents: async (id: string, after = 0, signal?: AbortSignal) => (await request<{ items: RunEvent[] }>(`/api/v2/runs/${idPath(id)}/event-history?after=${after}`, { signal })).items,
  createRun: (snapshotId: string, runtimeProfileId = "default-exact") => request<RunRecord>("/api/v2/runs", { method: "POST" }, { snapshot_id: snapshotId, trace_level: "detailed", runtime_profile_id: runtimeProfileId }),
  cancelRun: (id: string) => request<RunRecord>(`/api/v2/runs/${idPath(id)}/cancel`, { method: "POST", body: "{}" }),
  comparison: (id: string) => request<Comparison>(`/api/v2/runs/${idPath(id)}/comparison`),
  visualization: (id: string) => request<VisualizationModel>(`/api/v2/runs/${idPath(id)}/visualization`),
  audit: (id: string) => request<JsonObject>(`/api/v2/runs/${idPath(id)}/audit`),
};
export async function writeProfile(base: string, parameters: Record<string, unknown>) {
  const id = `wb3-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  await request(`/api/v2/profiles/${idPath(base)}/clone`, { method: "POST" }, { profile_id: id, name: "Workbench v3 自定义运行参数" });
  await request(`/api/v2/profiles/${id}`, { method: "PUT" }, { name: "Workbench v3 自定义运行参数", parameters });
  return id;
}
