from __future__ import annotations

import json
import sys
import time
from typing import Any

from backend.application.solve_service import solve_request
from backend.schemas.result import SolveRequest
from backend.schemas.workbench import JobStatus, RunEvent, utc_now

from .storage import WorkbenchStore


def execute_run(run_id: str) -> int:
    store = WorkbenchStore()
    started = time.perf_counter()

    def emit(payload: dict[str, Any]) -> None:
        event = RunEvent(
            run_id=run_id,
            seq=store.next_event_sequence(run_id),
            emitted_at=utc_now(),
            elapsed_seconds=max(0.0, time.perf_counter() - started),
            stage=str(payload.get("stage", "worker")),
            event_type=str(payload.get("type", "message")),
            message=str(payload.get("message", "")),
            lower_bound=payload.get("lower_bound"),
            upper_bound=payload.get("upper_bound"),
            absolute_gap=payload.get("absolute_gap"),
            relative_gap=payload.get("relative_gap"),
            metrics={
                **dict(payload.get("metrics") or {}),
                **(
                    {"iteration": payload["iteration"]}
                    if "iteration" in payload
                    else {}
                ),
                **(
                    {"schedule": payload["schedule"]}
                    if "schedule" in payload
                    else {}
                ),
            },
            artifact_refs=list(payload.get("artifact_refs") or []),
        )
        store.append_event(event)

    last_cancel_check = 0.0
    cancel_cached = False

    def cancelled() -> bool:
        nonlocal last_cancel_check, cancel_cached
        now = time.monotonic()
        if now - last_cancel_check >= 0.2:
            cancel_cached = store.get_run(run_id).cancel_requested
            last_cancel_check = now
        return cancel_cached

    try:
        run = store.get_run(run_id)
        if run.cancel_requested:
            store.update_run_status(
                run_id, JobStatus.CANCELLED, optimization_status="aborted"
            )
            emit({"stage": "queue", "type": "run_cancelled", "message": "Run cancelled before start."})
            return 0
        store.update_run_status(run_id, JobStatus.PREPARING)
        emit({"stage": "preparing", "type": "stage_started", "message": "Loading immutable solve snapshot."})
        snapshot = store.get_snapshot(run.snapshot_id)
        runtime_profile = store.get_runtime_profile(run.runtime_profile_id)
        request = SolveRequest.model_validate(snapshot.solve_request)
        store.update_run_status(run_id, JobStatus.RUNNING)
        emit({"stage": "optimization", "type": "run_started", "message": "Solver worker started."})
        result = solve_request(
            request,
            event_sink=emit,
            cancel_check=cancelled,
            run_id=run_id,
            runtime_controls=runtime_profile.parameters.model_dump(mode="json"),
        )
        result_payload = result.model_dump(mode="json")
        if cancelled():
            store.update_run_status(
                run_id,
                JobStatus.CANCELLED,
                optimization_status="aborted",
                result=result_payload,
            )
            emit({"stage": "worker", "type": "run_cancelled", "message": "Cancellation acknowledged."})
        else:
            store.update_run_status(
                run_id,
                JobStatus.COMPLETED,
                optimization_status=result.status.value,
                result=result_payload,
            )
            emit(
                {
                    "stage": "worker",
                    "type": "run_completed",
                    "message": f"Run completed: {result.status.value}.",
                    "lower_bound": result.diagnostics.lower_bound,
                    "upper_bound": result.diagnostics.upper_bound,
                    "absolute_gap": result.diagnostics.gap,
                }
            )
        return 0
    except Exception as exc:  # isolated process must persist a structured failure
        store.update_run_status(
            run_id,
            JobStatus.FAILED,
            error={
                "code": "solver_worker_failed",
                "message": str(exc),
                "exception_type": type(exc).__name__,
                "retryable": False,
            },
        )
        emit({"stage": "worker", "type": "run_failed", "message": str(exc)})
        return 1


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "run_id argument required"}))
        return 2
    return execute_run(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
