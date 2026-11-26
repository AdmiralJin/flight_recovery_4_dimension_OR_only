import { memo, useEffect, useState } from "react";
import { terminal } from "./state";
import type { RunEvent, RunRecord } from "./types";
import { Term } from "./Help";

export function elapsedSeconds(run: RunRecord, event: RunEvent | undefined, now: number): number | null {
  const start = Date.parse(run.started_at || run.created_at);
  const finish = run.finished_at ? Date.parse(run.finished_at) : NaN;
  if (Number.isFinite(start) && (!terminal(run) || Number.isFinite(finish))) return Math.max(0, ((terminal(run) ? finish : now) - start) / 1000);
  // Historic records without a finish timestamp must not keep ticking forever.
  return event && Number.isFinite(event.elapsed_seconds) ? Math.max(0, event.elapsed_seconds + (!terminal(run) && Number.isFinite(Date.parse(event.emitted_at)) ? Math.max(0, (now - Date.parse(event.emitted_at)) / 1000) : 0)) : null;
}

export const RunClock = memo(function RunClock({ run, event }: { run: RunRecord; event?: RunEvent }) {
  const [now, setNow] = useState(Date.now());
  const active = !terminal(run);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active, run.run_id]);
  const seconds = elapsedSeconds(run, event, Math.max(now, Date.now()));
  const label = !run.started_at && active ? "排队耗时" : "运行耗时";
  return <span className="run-clock"><Term text="从后台开始时间计算的墙钟时间，每秒更新；结束后固定，不依赖运行事件。排队阶段从提交时间计时。">{label}</Term><time data-testid="run-clock" title={seconds == null ? "缺少可靠时间记录" : `${seconds.toFixed(1)} 秒`}>{seconds == null ? "—" : `${Math.floor(seconds / 3600).toString().padStart(2, "0")}:${Math.floor(seconds / 60 % 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`}</time></span>;
});
