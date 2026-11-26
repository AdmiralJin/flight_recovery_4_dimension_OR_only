import { act, cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { useRunMonitor } from "./monitor";
import { chooseRun, useWb } from "./state";
import type { RunEvent, RunRecord } from "./types";

const record = { run_id: "r1", job_status: "running", result: null, error: null, cancel_requested: false } as RunRecord;
const event = (seq: number, event_type = "solver_heartbeat") => ({ seq, run_id: "r1", event_type, elapsed_seconds: seq, message: "progress", metrics: {} }) as RunEvent;
class Source {
  static instances: Source[] = [];
  listeners = new Map<string, EventListener>();
  close = vi.fn();
  constructor() { Source.instances.push(this); }
  addEventListener(type: string, handler: EventListener) { this.listeners.set(type, handler); }
  receive(item: RunEvent) { this.listeners.get(item.event_type)?.(new MessageEvent(item.event_type, { data: JSON.stringify(item) })); }
}
function Monitor() { useRunMonitor(); return null; }
function mount() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Monitor/></QueryClientProvider>); }
beforeEach(() => {
  vi.useFakeTimers(); vi.stubGlobal("EventSource", Source); Source.instances = [];
  useWb.setState({ run: null, events: [], connection: "" }); chooseRun(record);
  vi.spyOn(api, "run").mockResolvedValue(record);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
describe("incremental run monitoring", () => {
  it("batches SSE updates and fetches deltas from the history cursor, preserving unknown event types", async () => {
    const history = vi.spyOn(api, "runEvents").mockResolvedValueOnce([event(1), event(2)]).mockResolvedValueOnce([event(3), event(4, "new_backend_event")]);
    await act(async () => { mount(); });
    const before = useWb.getState().events;
    act(() => { Source.instances[0].receive(event(3)); });
    expect(useWb.getState().events).toBe(before);
    await act(async () => { await vi.advanceTimersByTimeAsync(250); });
    expect(useWb.getState().events.map(e => e.seq)).toEqual([1, 2, 3]);
    await act(async () => { await vi.advanceTimersByTimeAsync(3750); });
    expect(history.mock.calls[1][1]).toBe(2);
    expect(useWb.getState().events.map(e => e.seq)).toEqual([1, 2, 3, 4]);
  });
  it("retrieves the final events after observing terminal status and then stops polling", async () => {
    vi.mocked(api.run).mockResolvedValueOnce(record).mockResolvedValueOnce({ ...record, job_status: "completed" });
    const history = vi.spyOn(api, "runEvents").mockResolvedValueOnce([event(1)]).mockResolvedValueOnce([]).mockResolvedValueOnce([event(2, "run_completed")]);
    await act(async () => { mount(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
    expect(history.mock.calls.map(call => call[1])).toEqual([0, 1, 1]);
    expect(useWb.getState().events.at(-1)?.event_type).toBe("run_completed");
    expect(useWb.getState().connection).toBe("历史事件已同步");
    expect(Source.instances[0].close).toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(20000); });
    expect(api.run).toHaveBeenCalledTimes(2);
  });
  it("aborts an old request and ignores its reply after switching runs", async () => {
    let finish!: (value: RunRecord) => void;
    vi.mocked(api.run).mockImplementation(id => id === "r1" ? new Promise(resolve => { finish = resolve; }) : Promise.resolve({ ...record, run_id: id }));
    vi.spyOn(api, "runEvents").mockResolvedValue([]);
    await act(async () => { mount(); });
    const signal = vi.mocked(api.run).mock.calls[0][1];
    await act(async () => { chooseRun({ ...record, run_id: "r2" }); });
    await act(async () => { finish({ ...record, job_status: "completed" }); });
    expect(signal?.aborted).toBe(true);
    expect(useWb.getState().run?.run_id).toBe("r2");
    expect(useWb.getState().run?.job_status).toBe("running");
  });
});
