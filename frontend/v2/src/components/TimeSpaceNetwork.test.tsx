import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimeSpaceNetwork } from "./TimeSpaceNetwork";

describe("TimeSpaceNetwork", () => {
  it("renders risk exposure without inventing a recovery decision", () => {
    const select = vi.fn();
    const { container } = render(
      <TimeSpaceNetwork
        label="impact network"
        flights={[{
          flight_id: "F1",
          origin: "AAA",
          destination: "BBB",
          sched_dep: "2026-01-01T01:00:00Z",
          sched_arr: "2026-01-01T02:00:00Z",
        }]}
        impacts={[{
          flight_id: "F1",
          status: "direct",
          direct_rule_ids: ["R1"],
          propagation_sources: [],
        }]}
        onSelect={select}
      />,
    );
    const line = container.querySelector(".state-direct");
    expect(line).toBeInTheDocument();
    expect(container.querySelector(".state-cancelled")).not.toBeInTheDocument();
    fireEvent.click(line!);
    expect(select).toHaveBeenCalledWith("F1");
    expect(screen.getByRole("group", { name: "impact network" })).toBeInTheDocument();
  });

  it("keeps an arrival-only delay in the canonical time-changed view", () => {
    const { container } = render(
      <TimeSpaceNetwork
        label="delta network"
        flights={[{
          flight_id: "F2",
          original: { origin: "AAA", destination: "BBB", sched_dep: "2026-01-01T01:00:00Z", sched_arr: "2026-01-01T02:00:00Z" },
          effective: {},
          impact: { flight_id: "F2", status: "normal", direct_rule_ids: [], propagation_sources: [] },
          recovered: { status: "operated", recovered_origin: "AAA", recovered_destination: "BBB", recovered_dep: "2026-01-01T01:00:00Z", recovered_arr: "2026-01-01T02:10:00Z" },
          changed: true,
          change_flags: ["time_changed"],
          primary_change: "time_changed",
        }]}
      />,
    );
    expect(container.querySelector(".state-time_changed")).toBeInTheDocument();
    expect(container.querySelector(".is-ghost")).toBeInTheDocument();
  });
});
