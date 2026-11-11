import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { editDocument, editRaw, execute, isDirty, loadDraft, materialize, mergeEvents, patchDocument, saveAndValidate, saveOnly, selectDraft, startBlockers, startRun, statusLabel, undoDocument, useWb } from "./state";
import { blankDocument, entityRows, replaceRow, replaceRowImmutable } from "./data";
import { globalTrace } from "./monitor";
import type { CompilePreview, Draft, RunEvent, RunRecord } from "./types";

const document = blankDocument();
const draft: Draft = { draft_id: "d1", name: "test", working_hash: "h1", revision_count: 1, origin_kind: "document", source_case_id: null, created_at: "2026-11-06T00:00:00Z", updated_at: "2026-11-06T00:00:00Z", document };
const preview: CompilePreview = { valid: true, draft_hash: "h1", solve_request: { valid: true }, candidate_counts: {}, issues: [], capacity_changes: [], flight_impacts: [] };
const run = { run_id: "r1", draft_id: "d1", job_status: "completed", optimization_status: "optimal" } as RunRecord;
const event = (seq: number, type = "solve_bounds", extra = {}) => ({ seq, run_id: "r1", event_type: type, elapsed_seconds: seq, emitted_at: "", stage: "solve", message: "", metrics: {}, artifact_refs: [], ...extra }) as RunEvent;
beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  useWb.setState({ run: null, events: [], busy: "", notice: null, runtimeEdits: null, runtimeProfile: "default-exact" }); selectDraft(structuredClone(draft));
});
describe("saved inputs and immutable runs", () => {
  it("requires an actual valid solve request and a matching input hash", () => {
    expect(startBlockers()).toContain("请先保存并校验当前数据和配置");
    useWb.setState({ preview, checkedProfile: "default-exact" }); expect(startBlockers()).toEqual([]);
    useWb.setState({ preview: { ...preview, solve_request: null } }); expect(startBlockers().join()).toContain("缺少可求解输入");
  });
  it("invalidates validation immediately, and supports scoped undo/redo", () => {
    useWb.setState({ preview, checkedProfile: "default-exact" });
    editDocument(doc => { doc.name = "edit"; }); expect(isDirty()).toBe(true); expect(useWb.getState().preview).toBeNull();
    undoDocument(); expect(useWb.getState().document?.name).toBe(document.name); expect(isDirty()).toBe(false);
    undoDocument(true); expect(useWb.getState().document?.name).toBe("edit");
  });
  it("preserves advanced JSON edits and rejects invalid outer contracts", () => {
    editRaw("{"); expect(isDirty()).toBe(true); expect(materialize).toThrow(); expect(startBlockers().join()).toContain("未保存");
    editRaw('{"schema_version":"wrong"}'); expect(materialize).toThrow("草稿 JSON");
  });
  it("preserves local data on a 409 version conflict", async () => {
    editDocument(doc => { doc.name = "local"; });
    vi.spyOn(api, "saveDraft").mockRejectedValue(new ApiError(409, "conflict", { code: "draft_hash_conflict" }));
    expect(await execute("save", saveAndValidate)).toBe(false);
    expect(useWb.getState().document?.name).toBe("local"); expect(useWb.getState().conflict).toBe(true); expect(isDirty()).toBe(true);
  });
  it("does not allow an old draft fetch to replace a newer selection", async () => {
    let resolve!: (draft: Draft) => void;
    vi.spyOn(api, "draft").mockImplementation(() => new Promise(done => { resolve = done; }));
    const pending = loadDraft("d1"); selectDraft({ ...draft, draft_id: "d2" }); resolve(draft); await pending;
    expect(useWb.getState().draft?.draft_id).toBe("d2");
  });
  it("a save reply keeps edits made while the request was pending", async () => {
    editDocument(doc => { doc.name = "first"; }); let resolve!: (draft: Draft) => void;
    vi.spyOn(api, "saveDraft").mockImplementation(() => new Promise(done => { resolve = done; }));
    const pending = saveAndValidate(); editDocument(doc => { doc.name = "second"; });
    resolve({ ...draft, working_hash: "h2", document: { ...document, name: "first" } });
    await expect(pending).rejects.toThrow("新的修改"); expect(useWb.getState().document?.name).toBe("second"); expect(useWb.getState().draft?.working_hash).toBe("h2"); expect(isDirty()).toBe(true);
  });
  it("discards a compile reply for an edited input", async () => {
    let resolve!: (p: CompilePreview) => void;
    vi.spyOn(api, "compile").mockImplementation(() => new Promise(done => { resolve = done; }));
    const pending = saveAndValidate(); editDocument(doc => { doc.name = "new"; }); resolve(preview); await pending;
    expect(useWb.getState().preview).toBeNull();
  });
  it("prevents double submissions and preserves a single created run", async () => {
    useWb.setState({ preview, checkedProfile: "default-exact" });
    vi.spyOn(api, "snapshot").mockResolvedValue({ snapshot_id: "s1" } as never);
    const create = vi.spyOn(api, "createRun").mockResolvedValue({ ...run, job_status: "running" });
    await Promise.all([execute("start", startRun), execute("start", startRun)]);
    expect(create).toHaveBeenCalledTimes(1); expect(startBlockers().join()).toContain("尚未结束");
  });
  it("does not submit after inputs change during snapshot creation", async () => {
    useWb.setState({ preview, checkedProfile: "default-exact" });
    let resolve!: (value: never) => void;
    vi.spyOn(api, "snapshot").mockImplementation(() => new Promise(done => { resolve = done; }));
    const create = vi.spyOn(api, "createRun"); const pending = startRun(); editDocument(doc => { doc.name = "new"; }); resolve({ snapshot_id: "s1" } as never);
    await expect(pending).rejects.toThrow("发生变化"); expect(create).not.toHaveBeenCalled();
  });
  it("deduplicates recovered events and sorts by sequence", () => {
    expect(mergeEvents([event(3), event(1)], [event(2), event(3)]).map(e => e.seq)).toEqual([1, 2, 3]);
  });
  it("does not turn a completed job into a claim of optimality", () => {
    expect(statusLabel({ ...run, optimization_status: "not_converged" })).toBe("未收敛");
    expect(statusLabel({ ...run, optimization_status: null })).toContain("执行完成");
    expect(statusLabel({ ...run, optimization_status: "infeasible" })).toBe("认证不可行");
  });
  it("never presents nested MIP or branch node bounds as global Benders bounds", () => {
    const events = [event(1, "mip_progress", { lower_bound: 999 }), event(2, "branch_node", { lower_bound: 500 }), event(3, "benders_iteration", { lower_bound: 10 }), event(4, "solve_bounds", { upper_bound: 20 })];
    expect(globalTrace(events, run).map(e => e.seq)).toEqual([3, 4]);
  });
  it("maps AIR and XMA row edits to their original input locations", () => {
    const air = structuredClone(document); air.scenario.flights = [{ flight_id: "f1", max_delay: 60 }];
    replaceRow(air, "flights", 0, { flight_id: "f1", max_delay: 120 }); expect(entityRows(air, "flights")[0].max_delay).toBe(120);
    const xma = structuredClone(document); xma.solve_bundle = { schema_version: "xma-solve-1.0", dataset: { flights: [{ flight_id: "x1" }], scenes: [{ scene_id: "s1" }] } };
    replaceRow(xma, "disruptions", 0, { scene_id: "s2" }); expect(entityRows(xma, "disruptions")[0].scene_id).toBe("s2");
  });
  it("shares unchanged large resources without modifying the saved input or undo history", () => {
    const original = useWb.getState().document!;
    patchDocument(["name"], "first");
    const first = useWb.getState().document!;
    patchDocument(["name"], "second");
    expect(original.name).toBe(document.name);
    expect(first.name).toBe("first");
    expect(useWb.getState().document?.scenario).toBe(original.scenario);
    expect(useWb.getState().document?.manual_flight_options).toBe(original.manual_flight_options);
    undoDocument(); expect(useWb.getState().document).toBe(first); expect(isDirty()).toBe(true);
    undoDocument(); expect(useWb.getState().document).toBe(original); expect(isDirty()).toBe(false);
    undoDocument(true); expect(useWb.getState().document).toBe(first); expect(isDirty()).toBe(true);
  });
  it("does not invalidate validation or add undo entries for an unchanged field", () => {
    useWb.setState({ preview, checkedProfile: "default-exact" });
    patchDocument(["name"], document.name);
    expect(useWb.getState().preview).toBe(preview); expect(useWb.getState().past).toHaveLength(0); expect(isDirty()).toBe(false);
  });
  it("recognizes the saved version after editing and undoing without comparing full JSON", async () => {
    patchDocument(["name"], "saved");
    vi.spyOn(api, "saveDraft").mockResolvedValue({ ...draft, working_hash: "h2", document: { ...document, name: "saved" } });
    vi.spyOn(api, "compile").mockResolvedValue({ ...preview, draft_hash: "h2" });
    await saveAndValidate(); expect(isDirty()).toBe(false);
    const saved = useWb.getState().document;
    patchDocument(["name"], "other"); undoDocument();
    expect(useWb.getState().document).toBe(saved); expect(isDirty()).toBe(false);
  });
  it("edits nested AIR and XMA rows without changing other rows or the saved document", () => {
    const air = structuredClone(document); air.scenario.flights = [{ flight_id: "f1", max_delay: 60 }, { flight_id: "f2" }];
    const changed = replaceRowImmutable(air, "flights", 0, { flight_id: "f1", max_delay: 120 });
    expect(entityRows(air, "flights")[0].max_delay).toBe(60);
    expect(entityRows(changed, "flights")[0].max_delay).toBe(120);
    expect(entityRows(changed, "flights")[1]).toBe(entityRows(air, "flights")[1]);
    expect(changed.scenario.aircraft).toBe(air.scenario.aircraft);
    const xma = { ...document, solve_bundle: { schema_version: "xma-solve-1.0", dataset: { flights: [{ flight_id: "x1" }], scenes: [{ scene_id: "s1" }] } } };
    const updated = replaceRowImmutable(xma, "disruptions", 0, { scene_id: "s2" });
    expect(entityRows(xma, "disruptions")[0].scene_id).toBe("s1");
    expect(entityRows(updated, "disruptions")[0].scene_id).toBe("s2");
    expect(entityRows(updated, "flights")).toBe(entityRows(xma, "flights"));
  });
  it("keeps the event array stable when a delta poll brings no new events", () => {
    const events = [event(1), event(2)]; expect(mergeEvents(events, [])).toBe(events);
  });
  it("saves without generating candidates and still blocks an unvalidated run", async () => {
    patchDocument(["name"], "quick save");
    const save = vi.spyOn(api, "saveDraft").mockResolvedValue({ ...draft, working_hash: "h2", document: { ...document, name: "quick save" } });
    const compile = vi.spyOn(api, "compile");
    await saveOnly();
    expect(save).toHaveBeenCalledTimes(1); expect(compile).not.toHaveBeenCalled(); expect(isDirty()).toBe(false);
    expect(startBlockers()).toContain("请先保存并校验当前数据和配置");
  });
});
