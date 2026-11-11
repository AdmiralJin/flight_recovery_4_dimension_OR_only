import { afterEach, describe, expect, it, vi } from "vitest";
import type { JsonTask } from "./json";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
describe("background JSON codec", () => {
  it("retains data and rejects invalid JSON when workers are unavailable", async () => {
    vi.resetModules(); vi.stubGlobal("Worker", undefined);
    const { parseJson, stringifyJson } = await import("./json");
    const input = { name: "厦航", rows: Array.from({ length: 3000 }, (_, i) => ({ flight_id: `f${i}`, cost: i + .5, cancelled: false, tail: null })) };
    const text = await stringifyJson(input, 2);
    expect(await parseJson(text)).toEqual(input);
    await expect(parseJson("{" + " ".repeat(140000))).rejects.toThrow();
  });
  it("matches concurrent worker replies to the right request", async () => {
    vi.resetModules();
    class FakeWorker {
      onmessage?: (event: { data: unknown }) => void;
      terminate() {}
      postMessage(task: JsonTask) {
        setTimeout(() => this.onmessage?.({ data: { id: task.id, value: task.kind === "parse" ? JSON.parse(task.value as string) : JSON.stringify(task.value, null, task.space) } }), task.id === 1 ? 10 : 0);
      }
    }
    vi.stubGlobal("Worker", FakeWorker);
    const { parseJson, stringifyJson } = await import("./json");
    const [first, second] = await Promise.all([stringifyJson({ first: true }), parseJson('"' + "x".repeat(140000) + '"')]);
    expect(first).toBe('{"first":true}'); expect(second).toBe("x".repeat(140000));
  });
  it("falls back after worker startup fails without dropping a pending save", async () => {
    vi.resetModules();
    class FailedWorker {
      onerror?: () => void;
      terminate() {}
      postMessage() { queueMicrotask(() => this.onerror?.()); }
    }
    vi.stubGlobal("Worker", FailedWorker);
    const { stringifyJson } = await import("./json");
    expect(await stringifyJson({ saved: true })).toBe('{"saved":true}');
    expect(await stringifyJson({ next: true })).toBe('{"next":true}');
  });
});
