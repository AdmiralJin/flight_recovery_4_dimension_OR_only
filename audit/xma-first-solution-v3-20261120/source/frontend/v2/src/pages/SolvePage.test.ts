import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { useWorkbench } from "../store";
import type { RunEvent, RunRecord } from "../types";
import { hydrateRunEvidence } from "./runEvidence";
import { comparableRuns, incumbentChanges, tracePoints } from "./solveMonitor";

const run: RunRecord = {
  run_id: "run-history",
  snapshot_id: "snapshot",
  draft_id: "draft",
  input_hash: "a".repeat(64),
  job_status: "completed",
  optimization_status: "optimal",
  trace_level: "detailed",
  runtime_profile_id: "default-exact",
  cancel_requested: false,
  created_at: "2026-01-01T00:00:00Z",
};

const event: RunEvent = {
  run_id: run.run_id,
  seq: 2,
  emitted_at: "2026-01-01T00:00:01Z",
  elapsed_seconds: 1,
  stage: "optimization",
  event_type: "solve_bounds",
  message: "done",
  lower_bound: 10,
  upper_bound: 10,
  metrics: {},
  artifact_refs: [],
};

describe("historical run evidence", () => {
  beforeEach(() => {
    useWorkbench.setState({ run, events: [], comparison: null, audit: null });
    vi.restoreAllMocks();
  });

  it("hydrates persisted events together with comparison and audit", async () => {
    vi.spyOn(api, "comparison").mockResolvedValue({ recovered_available: true } as never);
    vi.spyOn(api, "audit").mockResolvedValue({ events: [event] });
    vi.spyOn(api, "runEvents").mockResolvedValue([event]);
    await hydrateRunEvidence(run.run_id);
    expect(useWorkbench.getState().events).toEqual([event]);
    expect(useWorkbench.getState().audit).toEqual({ events: [event] });
  });

  it("does not overwrite a newer run selection", async () => {
    vi.spyOn(api, "comparison").mockResolvedValue({ recovered_available: true } as never);
    vi.spyOn(api, "audit").mockResolvedValue({});
    vi.spyOn(api, "runEvents").mockImplementation(async () => {
      useWorkbench.setState({ run: { ...run, run_id: "newer" } });
      return [event];
    });
    await hydrateRunEvidence(run.run_id);
    expect(useWorkbench.getState().events).toEqual([]);
  });
});

describe("solve monitor derivations", () => {
  it("deduplicates identical final bounds and keeps elapsed time", () => {
    const final={ ...event,seq:3,elapsed_seconds:2,event_type:"run_completed" };
    const points=tracePoints([event,final]);
    expect(points).toHaveLength(1);
    expect(points[0].elapsed_seconds).toBe(1);
  });

  it("computes recent incumbent changes", () => {
    const points=tracePoints([
      { ...event,seq:1,upper_bound:20,lower_bound:5 },
      { ...event,seq:2,elapsed_seconds:2,upper_bound:15,lower_bound:8 },
    ]);
    expect(incumbentChanges(points)[0].delta).toBe(-5);
  });

  it("compares only matching study signatures", () => {
    const current={ ...run,run_id:"current",result:null };
    const old={ ...run,run_id:"old",result:{ objective:{ total:12 },run_metadata:{ study_signature:"same" } } };
    const other={ ...old,run_id:"other",result:{ objective:{ total:9 },run_metadata:{ study_signature:"different" } } };
    const context={ ...event,event_type:"study_context",metrics:{ study_signature:"same" },lower_bound:null,upper_bound:null };
    expect(comparableRuns([old,other],current,[context]).map((row) => row.run.run_id)).toEqual(["old"]);
  });
});
