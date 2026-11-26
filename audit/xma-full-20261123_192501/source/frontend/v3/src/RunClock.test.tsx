import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RunClock, elapsedSeconds } from "./RunClock";
import type { RunEvent, RunRecord } from "./types";

const start = Date.parse("2026-11-10T08:00:00Z");
const run = { run_id: "clock", started_at: new Date(start).toISOString(), created_at: new Date(start - 10000).toISOString(), job_status: "running" } as RunRecord;
afterEach(() => { cleanup(); vi.useRealTimers(); });
it("ticks every second with zero progress events, freezes at finish and cleans up its timer", () => {
  vi.useFakeTimers(); vi.setSystemTime(start);
  const view = render(<RunClock run={run}/>);
  expect(screen.getByTestId("run-clock").textContent).toBe("00:00:00");
  act(() => { vi.advanceTimersByTime(5000); });
  expect(screen.getByTestId("run-clock").textContent).toBe("00:00:05");
  view.rerender(<RunClock run={{ ...run, job_status: "completed", finished_at: new Date(start + 5000).toISOString() }}/>);
  act(() => { vi.advanceTimersByTime(10000); });
  expect(screen.getByTestId("run-clock").textContent).toBe("00:00:05");
  expect(vi.getTimerCount()).toBe(0);
});
it("recovers elapsed wall time on reload and separates queued time", () => {
  expect(elapsedSeconds(run, undefined, start + 119540)).toBe(119.54);
  expect(elapsedSeconds({ ...run, started_at: null, job_status: "queued" }, undefined, start)).toBe(10);
});
it("uses only recorded elapsed evidence for historic runs lacking a finish time", () => {
  const historic = { ...run, job_status: "completed", finished_at: null } as RunRecord;
  const event = { elapsed_seconds: 125 } as RunEvent;
  expect(elapsedSeconds(historic, event, start + 86400000)).toBe(125);
  expect(elapsedSeconds(historic, undefined, start + 86400000)).toBeNull();
});
