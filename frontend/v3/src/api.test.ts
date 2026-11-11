import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { blankDocument } from "./data";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
describe("v3 transport preserves v2 API contracts", () => {
  it("encodes the draft and base hash without modifying the input", async () => {
    const document = blankDocument();
    const fetch = vi.fn().mockResolvedValue(new Response('{"working_hash":"h2"}', { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await api.saveDraft("d1", "h1", document);
    const [path, init] = fetch.mock.calls[0];
    expect(path).toBe("/api/v2/drafts/d1/working-copy"); expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ base_hash: "h1", document });
    expect(document.name).toBe("未命名研究草稿");
  });
  it("uses the existing history cursor and passes cancellation to fetch", async () => {
    const controller = new AbortController();
    const fetch = vi.fn().mockResolvedValue(new Response('{"items":[]}', { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    expect(await api.runEvents("run1", 72, controller.signal)).toEqual([]);
    expect(fetch.mock.calls[0][0]).toBe("/api/v2/runs/run1/event-history?after=72");
    expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
  });
  it("keeps structured 409 conflicts recognizable by the edit guard", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":{"code":"draft_hash_conflict","message":"changed"}}', { status: 409 })));
    const error = await api.saveDraft("d1", "old", blankDocument()).catch(error => error);
    expect(error).toBeInstanceOf(ApiError); expect(error.status).toBe(409); expect(error.detail.code).toBe("draft_hash_conflict");
  });
});
