import { api } from "./api";
import { useWorkbench } from "./store";
import type { Draft, DraftDocument, JsonObject } from "./types";

export const xmaConfigKeys = [
  "objective_profile",
  "algorithm",
  "delay_step_minutes",
  "maximum_delay_minutes",
  "time_limit_seconds",
  "max_assignment_options",
] as const;

export function readXmaConfig(bundle: JsonObject): JsonObject {
  return Object.fromEntries(xmaConfigKeys.map((key) => [key, bundle[key]]));
}

export function applyXmaConfig(document: DraftDocument, values: JsonObject): DraftDocument {
  const next = structuredClone(document);
  if (!next.solve_bundle || next.solve_bundle.schema_version !== "xma-solve-1.0") {
    throw new Error("当前草稿不是厦航研究草稿");
  }
  const ranges: Record<string, [number, number]> = {
    delay_step_minutes: [1, 360], maximum_delay_minutes: [0, 2160],
    time_limit_seconds: [1, 86400], max_assignment_options: [1, 10_000_000],
  };
  xmaConfigKeys.forEach((key) => {
    const range = ranges[key];
    if (!range) { next.solve_bundle![key] = values[key]; return; }
    const value = Number(values[key]);
    if (!Number.isInteger(value) || value < range[0] || value > range[1]) throw new Error(`${key} 超出允许范围`);
    next.solve_bundle![key] = value;
  });
  return next;
}

export async function persistPendingXmaConfig(): Promise<Draft | null> {
  const state = useWorkbench.getState();
  const draft = state.draft;
  const edits = state.xmaConfigEdits;
  if (!draft || !edits || edits.draftId !== draft.draft_id) return draft;
  const saved = await api.saveDraft(draft.draft_id, edits.baseHash, applyXmaConfig(draft.document, edits.values));
  useWorkbench.getState().selectDraft(saved);
  return saved;
}
