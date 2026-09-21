import type {
  Capabilities,
  CaseSummary,
  Comparison,
  CompilePreview,
  Draft,
  DraftDocument,
  JsonObject,
  RunRecord,
  Snapshot,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: JsonObject;

  constructor(status: number, message: string, detail: JsonObject = {}) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (body.detail ?? body) as JsonObject;
    throw new ApiError(response.status, String(detail.message ?? `HTTP ${response.status}`), detail);
  }
  return body as T;
}

export const api = {
  capabilities: () => request<Capabilities>("/api/v2/capabilities"),
  cases: async () => (await request<{ cases: CaseSummary[] }>("/api/cases")).cases,
  drafts: async () => (await request<{ items: Draft[] }>("/api/v2/drafts")).items,
  draft: (id: string) => request<Draft>(`/api/v2/drafts/${id}`),
  createDraft: (sourceCaseId: string) =>
    request<Draft>("/api/v2/drafts", {
      method: "POST",
      body: JSON.stringify({ source_case_id: sourceCaseId }),
    }),
  importDraft: (document: DraftDocument) =>
    request<Draft>("/api/v2/imports/draft", {
      method: "POST",
      body: JSON.stringify(document),
    }),
  saveDraft: (id: string, baseHash: string, document: DraftDocument) =>
    request<Draft>(`/api/v2/drafts/${id}/working-copy`, {
      method: "PUT",
      body: JSON.stringify({ base_hash: baseHash, document }),
    }),
  compile: (id: string) =>
    request<CompilePreview>(`/api/v2/drafts/${id}/compile`, { method: "POST", body: "{}" }),
  snapshot: (draft: Draft, note = "") =>
    request<Snapshot>(`/api/v2/drafts/${draft.draft_id}/snapshots`, {
      method: "POST",
      body: JSON.stringify({ base_hash: draft.working_hash, note }),
    }),
  runs: async (draftId?: string) =>
    (
      await request<{ items: RunRecord[] }>(
        `/api/v2/runs${draftId ? `?draft_id=${encodeURIComponent(draftId)}` : ""}`,
      )
    ).items,
  run: (id: string) => request<RunRecord>(`/api/v2/runs/${id}`),
  createRun: (snapshotId: string, runtimeProfileId = "default-exact") =>
    request<RunRecord>("/api/v2/runs", {
      method: "POST",
      body: JSON.stringify({ snapshot_id: snapshotId, trace_level: "detailed", runtime_profile_id: runtimeProfileId }),
    }),
  cancelRun: (id: string) => request<RunRecord>(`/api/v2/runs/${id}/cancel`, { method: "POST", body: "{}" }),
  comparison: (id: string) => request<Comparison>(`/api/v2/runs/${id}/comparison`),
  audit: (id: string) => request<JsonObject>(`/api/v2/runs/${id}/audit`),
};
