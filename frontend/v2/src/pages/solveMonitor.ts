import type { JsonObject, RunEvent, RunRecord } from "../types";

export interface TracePoint {
  seq: number;
  elapsed_seconds: number;
  lower_bound?: number | null;
  upper_bound?: number | null;
  relative_gap?: number | null;
  event_type: string;
}

export function tracePoints(events: RunEvent[]): TracePoint[] {
  const points: TracePoint[] = [];
  for (const event of events) {
    if (event.lower_bound == null && event.upper_bound == null) continue;
    const previous=points.at(-1);
    if (previous && previous.lower_bound===event.lower_bound && previous.upper_bound===event.upper_bound) continue;
    points.push({ seq:event.seq,elapsed_seconds:event.elapsed_seconds,lower_bound:event.lower_bound,
      upper_bound:event.upper_bound,relative_gap:event.relative_gap,event_type:event.event_type });
  }
  return points;
}

export function incumbentChanges(points: TracePoint[]) {
  const values: Array<TracePoint & { delta: number | null }> = [];
  let previous: number | null = null;
  points.forEach((point) => {
    if (point.upper_bound == null || point.upper_bound===previous) return;
    values.push({ ...point,delta:previous==null ? null : point.upper_bound-previous });
    previous=point.upper_bound;
  });
  return values.slice(-5).reverse();
}

export function latestMetric(events: RunEvent[], key: string): unknown {
  for (let index=events.length-1;index>=0;index-=1) {
    const value=events[index].metrics[key];
    if (value!==undefined && value!==null) return value;
  }
  return null;
}

function resultMetadata(run: RunRecord): JsonObject {
  return ((run.result?.run_metadata as JsonObject | undefined) ?? {});
}

function objectiveTotal(run: RunRecord): number | null {
  const value=(run.result?.objective as JsonObject | undefined)?.total;
  return typeof value==="number" ? value : null;
}

export function comparableRuns(runs: RunRecord[], current: RunRecord | null, events: RunEvent[]) {
  if (!current) return [];
  const signature=String(latestMetric(events,"study_signature") ?? resultMetadata(current).study_signature ?? "");
  return runs.filter((run) => {
    if (run.run_id===current.run_id || run.job_status!=="completed" || objectiveTotal(run)==null) return false;
    const other=String(resultMetadata(run).study_signature ?? "");
    return signature ? other===signature : run.input_hash===current.input_hash;
  }).sort((a,b) => b.created_at.localeCompare(a.created_at)).slice(0,5).map((run) => ({
    run,total:objectiveTotal(run)!,delta:null as number | null,
  }));
}

export function withCurrentDeltas(rows: ReturnType<typeof comparableRuns>, currentBest: number | null) {
  return rows.map((row) => ({ ...row,delta:currentBest==null ? null : currentBest-row.total }));
}
