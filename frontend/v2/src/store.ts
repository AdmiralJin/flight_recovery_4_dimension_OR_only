import { create } from "zustand";
import type {
  Capabilities,
  CaseSummary,
  Comparison,
  CompilePreview,
  Draft,
  JsonObject,
  RunEvent,
  RunRecord,
} from "./types";

interface WorkbenchState {
  capabilities: Capabilities | null;
  cases: CaseSummary[];
  drafts: Draft[];
  draft: Draft | null;
  preview: CompilePreview | null;
  runs: RunRecord[];
  run: RunRecord | null;
  events: RunEvent[];
  comparison: Comparison | null;
  audit: JsonObject | null;
  mode: "original" | "impact" | "recovered" | "delta";
  selectedId: string | null;
  busy: string | null;
  message: { tone: "info" | "success" | "warning" | "error"; text: string } | null;
  set: (values: Partial<WorkbenchState>) => void;
  selectDraft: (draft: Draft | null) => void;
  selectRun: (run: RunRecord | null) => void;
  addEvent: (event: RunEvent) => void;
}

export const useWorkbench = create<WorkbenchState>((set) => ({
  capabilities: null,
  cases: [],
  drafts: [],
  draft: null,
  preview: null,
  runs: [],
  run: null,
  events: [],
  comparison: null,
  audit: null,
  mode: "delta",
  selectedId: null,
  busy: null,
  message: null,
  set: (values) => set(values),
  selectDraft: (draft) =>
    set({ draft, preview: null, run: null, events: [], comparison: null, audit: null, selectedId: null }),
  selectRun: (run) => set({ run, events: [], comparison: null, audit: null, selectedId: null }),
  addEvent: (event) =>
    set((state) =>
      state.events.some((item) => item.seq === event.seq)
        ? state
        : { events: [...state.events, event].sort((a, b) => a.seq - b.seq) },
    ),
}));
