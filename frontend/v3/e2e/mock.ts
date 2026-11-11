import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Page } from "@playwright/test";
import type { Draft, RunRecord } from "../src/types";

export const fixture = JSON.parse(readFileSync(resolve(process.cwd(), "../.workbench/v3_acceptance/api-fixtures.json"), "utf8"));
const clone = <T>(value: T): T => structuredClone(value);
export async function mockApi(page: Page, empty = false) {
  const state = {
    drafts: empty ? [] as Draft[] : [clone(fixture.air.draft) as Draft, clone(fixture.xma.draft) as Draft],
    runs: empty ? [] as RunRecord[] : [clone(fixture.air.run) as RunRecord, clone(fixture.xma.run) as RunRecord],
    creates: 0, saves: 0, compiles: 0, conflict: false, networkSave: false, autoComplete: true, failList: false,
    draftDelay: "", runDelay: "", statusOverride: "", polls: new Map<string, number>(),
  };
  const family = (draftId: string) => state.drafts.find(d => d.draft_id === draftId)?.document.solve_bundle?.schema_version === "xma-solve-1.0" ? fixture.xma : fixture.air;
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url()); const path = url.pathname; const method = route.request().method();
    const body = route.request().postDataJSON.bind(route.request());
    const reply = (value: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
    if (path === "/api/cases") return reply({ cases: fixture.cases });
    if (path === "/api/v2/capabilities") return reply(fixture.capabilities);
    if (path.includes("/profiles/")) return reply({ profile_id: path.endsWith("/clone") ? body().profile_id : path.split("/").at(-1) }, method === "POST" ? 201 : 200);
    if (path === "/api/v2/xma/import-preview") return reply(fixture.xma_import);
    if (path === "/api/v2/drafts" && method === "GET") return state.failList ? route.abort("failed") : reply({ items: state.drafts });
    if (path === "/api/v2/drafts" && method === "POST" || path === "/api/v2/imports/draft") {
      const doc = path.includes("imports") ? body() : clone(fixture.air.draft.document);
      const draft = { ...clone(fixture.air.draft), draft_id: `draft-new-${state.drafts.length}`, name: doc.name, document: doc, working_hash: `h-new-${state.drafts.length}` } as Draft;
      state.drafts.unshift(draft); return reply(draft, 201);
    }
    const draftMatch = path.match(/^\/api\/v2\/drafts\/([^/]+)(.*)$/);
    if (draftMatch) {
      const [, id, suffix] = draftMatch; const draft = state.drafts.find(item => item.draft_id === id);
      if (!draft) return reply({ message: "Unknown draft" }, 404);
      if (!suffix) { if (state.draftDelay === id) await new Promise(resolve => setTimeout(resolve, 700)); return reply(draft); }
      if (suffix === "/working-copy") {
        if (state.networkSave) return route.abort("failed");
        if (state.conflict) return reply({ code: "draft_hash_conflict", message: "Another editor saved a version" }, 409);
        const value = body(); state.saves++; Object.assign(draft, { document: value.document, name: value.document.name, working_hash: `saved-${state.saves}`, revision_count: draft.revision_count + 1 }); return reply(draft);
      }
      if (suffix === "/compile") {
        state.compiles++;
        const valid = !!draft.document.name && draft.document.scenario !== null;
        return reply({ ...clone(family(id).compile), valid, draft_hash: draft.working_hash, issues: valid ? [] : [{ severity: "error", code: "invalid", message: "草稿名称不能为空", path: "name" }] });
      }
      if (suffix === "/snapshots") return reply({ ...clone(family(id).snapshot), draft_id: id, draft_document: draft.document, content_hash: draft.working_hash }, 201);
      if (suffix === "/visualization") return reply({ ...clone(family(id).draftVisualization), draft_id: id, source_id: id, working_hash: draft.working_hash });
    }
    if (path === "/api/v2/runs" && method === "GET") return reply({ items: state.runs });
    if (path === "/api/v2/runs" && method === "POST") {
      state.creates++;
      const selected = state.drafts[0];
      const run = { ...clone(family(selected.draft_id).run), run_id: `run-new-${state.creates}`, draft_id: selected.draft_id, job_status: "running", optimization_status: null, result: null, created_at: new Date().toISOString(), started_at: new Date().toISOString(), finished_at: null } as RunRecord;
      state.runs.unshift(run); return reply(run, 201);
    }
    const runMatch = path.match(/^\/api\/v2\/runs\/([^/]+)(.*)$/);
    if (runMatch) {
      const [, id, suffix] = runMatch; const run = state.runs.find(item => item.run_id === id); if (!run) return reply({ message: "Unknown run" }, 404);
      const reference = family(run.draft_id);
      if (!suffix) {
        if (state.runDelay === id) await new Promise(resolve => setTimeout(resolve, 700));
        state.polls.set(id, (state.polls.get(id) ?? 0) + 1);
        if (state.autoComplete && run.job_status === "running" && state.polls.get(id)! >= 2) Object.assign(run, { job_status: "completed", optimization_status: state.statusOverride || "optimal", result: clone(reference.run.result), finished_at: new Date().toISOString() });
        return reply(run);
      }
      if (suffix === "/cancel") { run.job_status = "cancelled"; run.cancel_requested = true; return reply(run); }
      if (suffix === "/events") return route.fulfill({ status: 200, contentType: "text/event-stream", body: ": keep-alive\n\n" });
      if (suffix === "/event-history") return reply({ items: clone(reference.events).slice(0, run.job_status === "running" ? 3 : undefined).filter((event: Record<string, unknown>) => Number(event.seq) > Number(url.searchParams.get("after") ?? 0)).map((event: Record<string, unknown>) => ({ ...event, run_id: id })) });
      if (suffix === "/visualization") {
        const model = { ...clone(reference.visualization), run_id: id, draft_id: run.draft_id, source_id: id, optimization_status: run.optimization_status };
        if (run.optimization_status === "infeasible") { model.mode_availability.recovered = { available: false, reason: "该运行已认证不可行" }; model.mode_availability.delta = { available: false, reason: "该运行没有恢复方案" }; }
        return reply(model);
      }
      if (suffix === "/comparison") return reply(reference.comparison);
      if (suffix === "/audit") return reply(reference.audit);
      if (suffix === "/export") return route.fulfill({ status: 200, contentType: "application/json", headers: { "Content-Disposition": 'attachment; filename="audit.json"' }, body: JSON.stringify(reference.audit) });
    }
    if (path.match(/\/api\/v2\/xma\/runs\/.+\/csv$/)) return route.fulfill({ contentType: "text/csv", headers: { "Content-Disposition": 'attachment; filename="xma.csv"' }, body: fixture.xma.csv });
    throw new Error(`Unmocked backend access: ${method} ${path}`);
  });
  return state;
}

export const entry = "/static/workbench-v3/#/prepare";
