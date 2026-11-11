import { api } from "../api";
import { useWorkbench } from "../store";

export async function hydrateRunEvidence(runId: string) {
  const [comparison, audit, events] = await Promise.all([
    api.comparison(runId),
    api.audit(runId),
    api.runEvents(runId),
  ]);
  const current = useWorkbench.getState();
  if (current.run?.run_id === runId) current.set({ comparison, audit, events });
}
