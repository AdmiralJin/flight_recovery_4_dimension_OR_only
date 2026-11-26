import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { useWorkbench } from "../store";
import type { Draft } from "../types";
import { XmaPanel, XmaResult } from "./XmaPanel";

function draft(): Draft {
  return { draft_id: "xma", name: "厦航", origin_kind: "xma_import", working_hash: "old", revision_count: 1, created_at: "", updated_at: "",
    document: { schema_version: "2.0.0", name: "厦航", capacity_semantics: "effective_legacy", scenario: {},
      solve_bundle: { schema_version: "xma-solve-1.0", objective_profile: "tianchi_2017", algorithm: "joint_arc_flow",
        delay_step_minutes: 60, maximum_delay_minutes: 120, time_limit_seconds: 30, max_assignment_options: 100000,
        air_objective: { flight_cancellation: 25000 } },
      typed_disruptions: [], candidate_policy: {}, manual_flight_options: [], manual_passenger_itineraries: [], notes: [] } };
}

beforeEach(() => useWorkbench.getState().selectDraft(draft()));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("stages and explicitly saves the chosen objective", async () => {
  const save = vi.spyOn(api, "saveDraft").mockImplementation(async (_id, _hash, document) => ({ ...draft(), document, working_hash: "new" }));
  render(<XmaPanel />);
  expect(screen.getByLabelText("厦航求解算法").querySelectorAll("option")).toHaveLength(4);
  fireEvent.change(screen.getByLabelText("厦航目标函数"), { target: { value: "air_linear_v1" } });
  expect(save).not.toHaveBeenCalled();
  expect(screen.getByText("有未保存的求解配置")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "保存求解配置" }));
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
  expect(screen.getByRole("button", { name: "使用此预览创建新草稿" })).toBeInTheDocument();
  vi.unstubAllGlobals();
});

it("requests a reproducible random whole-tail preview", async () => {
  const fetchMock=vi.fn().mockResolvedValue({ ok:true,json:async () => ({
    preview:{ counts:{ flights:104,aircraft:7,connected_pairs:8 },selection:{ mode:"random",requested_flights:100,actual_flights:104,seed:42,selection_hash:"abcdef1234567890" } },
    document:draft().document,
  }) });
  vi.stubGlobal("fetch",fetchMock);
  render(<XmaPanel />);
  fireEvent.change(screen.getByLabelText("随机种子"),{ target:{ value:"42" } });
  fireEvent.click(screen.getByRole("button",{ name:"随机抽取" }));
  expect(await screen.findByText(/随机样本/)).toBeInTheDocument();
  expect(String(fetchMock.mock.calls[0][0])).toContain("selection_mode=random");
  expect(String(fetchMock.mock.calls[0][0])).toContain("selection_seed=42");
  fireEvent.click(screen.getByRole("button",{ name:"使用此种子重建" }));
  expect(screen.getByLabelText("随机种子")).toHaveValue(42);
  vi.unstubAllGlobals();
});

it("keeps the create action available before any preview", async () => {
  useWorkbench.getState().selectDraft(null);
  vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ ok:true,json:async () => ({ preview:{ counts:{} },document:draft().document }) }));
  const imported=vi.spyOn(api,"importDraft").mockResolvedValue(draft());
  render(<XmaPanel />);
  fireEvent.click(screen.getByRole("button",{ name:"创建厦航研究草稿" }));
  await waitFor(() => expect(imported).toHaveBeenCalled());
  vi.unstubAllGlobals();
});

it("keeps ordinary AIR results outside the XMA result view", () => {
  render(<XmaResult />);
  expect(screen.queryByText("厦航恢复与旅客分配")).not.toBeInTheDocument();
});
