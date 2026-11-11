import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { mergeEvents, terminal, useWb } from "./state";
import type { RunEvent, RunRecord } from "./types";

const eventTypes = ["run_queued", "stage_started", "stage_completed", "benders_iteration", "run_started", "run_completed", "run_failed", "run_cancelled", "study_context", "candidate_generation", "building_model", "model_built", "solver_selected", "solver_fallback", "solver_heartbeat", "mip_progress", "mip_bound", "pricing_iteration", "branch_node", "audit_completed", "solve_bounds"];
export function useRunMonitor() {
  const id = useWb(s => s.run?.run_id);
  const cache = useQueryClient();
  useEffect(() => {
    if (!id) return;
    let closed = false;
    let timer: ReturnType<typeof setTimeout>;
    let batchTimer: ReturnType<typeof setTimeout> | undefined;
    let stream: EventSource | null = null;
    let buffered: RunEvent[] = [];
    let historyAfter = 0;
    let polling = false;
    let refreshRequested = false;
    let finished = false;
    const controller = new AbortController();
    const current = () => !closed && useWb.getState().run?.run_id === id;
    const flush = () => {
      clearTimeout(batchTimer); batchTimer = undefined;
      const incoming = buffered; buffered = [];
      if (incoming.length && current()) useWb.setState(s => ({ events: mergeEvents(s.events, incoming) }));
    };
    const receive = (event: MessageEvent) => {
      if (!current()) return;
      try {
        const item = JSON.parse(event.data) as RunEvent;
        if (item.run_id !== id) return;
        buffered.push(item);
        batchTimer ??= setTimeout(flush, 250);
        if (["run_completed", "run_failed", "run_cancelled"].includes(item.event_type)) { clearTimeout(timer); void poll(); }
      } catch { /* Delta polling recovers malformed or unknown event types. */ }
    };
    const connect = () => {
      if (stream || !current() || terminal(useWb.getState().run!) || typeof EventSource === "undefined") return;
      stream = new EventSource(`/api/v2/runs/${id}/events?after=${useWb.getState().events.at(-1)?.seq ?? 0}`);
      stream.onmessage = receive;
      eventTypes.forEach(type => stream!.addEventListener(type, receive as EventListener));
      stream.onopen = () => { if (current()) useWb.setState({ connection: "实时事件已连接" }); };
      stream.onerror = () => { if (current()) useWb.setState({ connection: "事件连接重试中 · 使用历史轮询补全" }); };
    };
    const poll = async () => {
      if (!current() || finished) return;
      if (polling) { refreshRequested = true; return; }
      polling = true;
      try {
        const [record, events] = await Promise.all([api.run(id, controller.signal), api.runEvents(id, historyAfter, controller.signal)]);
        if (!current()) return;
        for (const event of events) historyAfter = Math.max(historyAfter, event.seq);
        // The history cursor is separate from SSE: unknown event types and gaps are recovered.
        // A final delta after observing terminal status closes the record/history race.
        if (terminal(record)) {
          stream?.close();
          const final = await api.runEvents(id, historyAfter, controller.signal);
          if (!current()) return;
          events.push(...final);
          finished = true;
        }
        flush();
        useWb.setState(s => ({ run: unchangedRun(s.run, record) ? s.run : record, events: mergeEvents(s.events, events), connection: terminal(record) ? "历史事件已同步" : s.connection }));
        cache.setQueryData(["wb3", "record", id], record);
        if (finished) { await cache.invalidateQueries({ queryKey: ["wb3", "runs"] }); return; }
        connect();
      } catch { if (current()) useWb.setState({ connection: "网络暂不可用 · 正在重试，已收到的事件保留" }); }
      finally { polling = false; }
      if (current() && !finished) { timer = setTimeout(poll, refreshRequested ? 0 : document.hidden ? 15000 : 4000); refreshRequested = false; }
    };
    const visible = () => { if (!document.hidden && !finished) { clearTimeout(timer); void poll(); } };
    document.addEventListener("visibilitychange", visible);
    void poll();
    return () => { closed = true; controller.abort(); clearTimeout(timer); clearTimeout(batchTimer); stream?.close(); document.removeEventListener("visibilitychange", visible); };
  }, [id, cache]);
}
function unchangedRun(left: RunRecord | null, right: RunRecord) {
  return left?.run_id === right.run_id && left.job_status === right.job_status && left.cancel_requested === right.cancel_requested && left.optimization_status === right.optimization_status && left.started_at === right.started_at && left.finished_at === right.finished_at && left.solution_artifact_hash === right.solution_artifact_hash && left.result === right.result && left.error === right.error;
}
export function globalTrace(events: RunEvent[], run: RunRecord | null) {
  const algorithm = String((run?.result?.run_metadata as Record<string, unknown> | undefined)?.algorithm ?? events.find(e => e.event_type === "study_context")?.metrics.algorithm ?? "");
  const direct = ["joint_arc_flow", "joint_path_oracle"].includes(algorithm);
  return events.filter(event => ["benders_iteration", "solve_bounds", "run_completed"].includes(event.event_type) || direct && ["mip_progress", "mip_bound"].includes(event.event_type)).filter(event => event.lower_bound != null || event.upper_bound != null);
}
