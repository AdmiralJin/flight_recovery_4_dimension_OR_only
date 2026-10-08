import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { useWorkbench } from "../store";
import type { Draft } from "../types";
import { XmaPanel, XmaResult } from "./XmaPanel";

function draft(): Draft {
  return { draft_id: "xma", name: "厦航", working_hash: "old", revision_count: 1, created_at: "", updated_at: "",
    document: { schema_version: "2.0.0", name: "厦航", capacity_semantics: "effective_legacy", scenario: {},
      solve_bundle: { schema_version: "xma-solve-1.0", objective_profile: "tianchi_2017", algorithm: "joint_arc_flow",
        delay_step_minutes: 60, maximum_delay_minutes: 120, time_limit_seconds: 30, max_assignment_options: 100000,
        air_objective: { flight_cancellation: 25000 } },
      typed_disruptions: [], candidate_policy: {}, manual_flight_options: [], manual_passenger_itineraries: [], notes: [] } };
}

beforeEach(() => useWorkbench.getState().selectDraft(draft()));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("saves the chosen objective and keeps its independent AIR coefficients", async () => {
  const save = vi.spyOn(api, "saveDraft").mockImplementation(async (_id, _hash, document) => ({ ...draft(), document, working_hash: "new" }));
  render(<XmaPanel />);
  expect(screen.getByLabelText("厦航求解算法").querySelectorAll("option")).toHaveLength(4);
  fireEvent.change(screen.getByLabelText("厦航目标函数"), { target: { value: "air_linear_v1" } });
  await waitFor(() => expect(save).toHaveBeenCalled());
  const bundle = useWorkbench.getState().draft!.document.solve_bundle!;
  expect(bundle.objective_profile).toBe("air_linear_v1");
  expect(bundle.air_objective).toEqual({ flight_cancellation: 25000 });
});

it("reads the bundled workbook and shows a readable import preview", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    preview: { counts: { flights: 30, aircraft: 2, connected_pairs: 6 } }, document: draft().document,
  }) }));
  render(<XmaPanel />);
  fireEvent.click(screen.getByRole("button", { name: "读取项目厦航数据" }));
  expect(await screen.findByText(/航班 30 班/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "创建厦航研究草稿" })).toBeInTheDocument();
  vi.unstubAllGlobals();
});

it("keeps ordinary AIR results outside the XMA result view", () => {
  render(<XmaResult />);
  expect(screen.queryByText("厦航恢复与旅客分配")).not.toBeInTheDocument();
});
