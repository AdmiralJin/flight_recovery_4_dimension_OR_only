from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from backend.application.case_service import CaseCatalogError, load_case
from backend.application.solve_service import default_profile_ids
from backend.schemas.workbench import (
    DraftCreateRequest,
    DraftDocument,
    DraftUpdateRequest,
    JobStatus,
    ProblemDetails,
    ProblemIssue,
    RunCreateRequest,
    RuntimeProfileCloneRequest,
    RuntimeProfileUpdateRequest,
    SnapshotCreateRequest,
)
from backend.solver import GurobiAdapter
from backend.workbench.comparison import build_audit, build_comparison
from backend.workbench.compiler import compile_draft, draft_from_case_payload
from backend.workbench.run_manager import get_run_manager
from backend.workbench.storage import (
    WorkbenchConflictError,
    WorkbenchNotFoundError,
    get_workbench_store,
)


router = APIRouter(prefix="/api/v2", tags=["workbench-v2"])
TERMINAL = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.INTERRUPTED,
}


class WorkbenchProblem(Exception):
    def __init__(self, status_code: int, details: ProblemDetails) -> None:
        super().__init__(details.message)
        self.status_code = status_code
        self.details = details


def problem(
    status: int,
    code: str,
    message: str,
    *,
    issues: list[ProblemIssue] | None = None,
    run_id: str | None = None,
    retryable: bool = False,
) -> WorkbenchProblem:
    return WorkbenchProblem(
        status,
        ProblemDetails(
            code=code,
            message=message,
            issues=issues or [],
            run_id=run_id,
            retryable=retryable,
        ),
    )


@router.get("/capabilities")
def capabilities() -> dict[str, Any]:
    available, reason = GurobiAdapter.availability()
    return {
        "schema_version": "2.0.0",
        "solver": {
            "name": "Gurobi",
            "available": available,
            "reason": reason,
            "max_concurrent_runs": 1,
        },
        "algorithm": "benders_branch_and_price_v1",
        "full_scope_only": True,
        "candidate_generation": {
            "unchanged": True,
            "cancel": True,
            "delay_grid": True,
            "automatic_reroute": False,
            "automatic_ferry": False,
        },
        "profiles": default_profile_ids().model_dump(mode="json"),
        "runtime_profiles": [
            item.model_dump(mode="json")
            for item in get_workbench_store().list_runtime_profiles()
        ],
    }


@router.get("/profiles")
def list_profiles():
    return {"items": get_workbench_store().list_runtime_profiles()}


@router.post("/profiles/{base_profile_id}/clone", status_code=201)
def clone_profile(base_profile_id: str, data: RuntimeProfileCloneRequest):
    try:
        return get_workbench_store().clone_runtime_profile(
            base_profile_id, data.profile_id, data.name
        )
    except WorkbenchNotFoundError as exc:
        raise problem(404, "profile_not_found", str(exc)) from exc
    except WorkbenchConflictError as exc:
        raise problem(409, "profile_conflict", str(exc)) from exc


@router.put("/profiles/{profile_id}")
def update_profile(profile_id: str, data: RuntimeProfileUpdateRequest):
    try:
        return get_workbench_store().update_runtime_profile(
            profile_id, data.name, data.parameters
        )
    except WorkbenchNotFoundError as exc:
        raise problem(404, "profile_not_found", str(exc)) from exc
    except WorkbenchConflictError as exc:
        raise problem(409, "profile_read_only", str(exc)) from exc


@router.get("/drafts")
def list_drafts():
    return {"items": get_workbench_store().list_drafts()}


@router.post("/drafts", status_code=201)
def create_draft(data: DraftCreateRequest):
    if data.document is not None:
        document = data.document.model_copy(
            update={"name": data.name or data.document.name}
        )
    elif data.source_case_id:
        try:
            document = draft_from_case_payload(
                load_case(data.source_case_id), name=data.name
            )
        except CaseCatalogError as exc:
            raise problem(404, "case_not_found", str(exc)) from exc
    else:
        raise problem(
            422,
            "draft_source_required",
            "Provide a source_case_id or a complete draft document.",
        )
    return get_workbench_store().create_draft(document)


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str):
    try:
        return get_workbench_store().get_draft(draft_id)
    except WorkbenchNotFoundError as exc:
        raise problem(404, "draft_not_found", str(exc)) from exc


@router.put("/drafts/{draft_id}/working-copy")
def update_draft(draft_id: str, data: DraftUpdateRequest):
    try:
        return get_workbench_store().update_draft(
            draft_id, data.base_hash, data.document
        )
    except WorkbenchNotFoundError as exc:
        raise problem(404, "draft_not_found", str(exc)) from exc
    except WorkbenchConflictError as exc:
        raise problem(409, "draft_hash_conflict", str(exc), retryable=True) from exc


@router.post("/drafts/{draft_id}/compile")
def compile_preview(draft_id: str):
    try:
        draft = get_workbench_store().get_draft(draft_id)
    except WorkbenchNotFoundError as exc:
        raise problem(404, "draft_not_found", str(exc)) from exc
    return compile_draft(draft.document)


@router.post("/drafts/{draft_id}/snapshots", status_code=201)
def create_snapshot(draft_id: str, data: SnapshotCreateRequest):
    store = get_workbench_store()
    try:
        draft = store.get_draft(draft_id)
        if draft.working_hash != data.base_hash:
            raise WorkbenchConflictError("draft hash changed; compile again")
        preview = compile_draft(draft.document)
        if not preview.valid:
            raise problem(
                422,
                "compile_invalid",
                "The draft cannot be snapshotted until all blocking issues are fixed.",
                issues=[
                    ProblemIssue(
                        code=item.code,
                        path=item.path,
                        entity_id=item.entity_id,
                        message=item.message,
                        severity=item.severity,
                    )
                    for item in preview.issues
                ],
            )
        return store.create_snapshot(draft_id, data.base_hash, preview, data.note)
    except WorkbenchNotFoundError as exc:
        raise problem(404, "draft_not_found", str(exc)) from exc
    except WorkbenchConflictError as exc:
        raise problem(409, "draft_hash_conflict", str(exc), retryable=True) from exc


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    try:
        return get_workbench_store().get_snapshot(snapshot_id)
    except WorkbenchNotFoundError as exc:
        raise problem(404, "snapshot_not_found", str(exc)) from exc


@router.post("/imports/draft", status_code=201)
def import_draft(document: DraftDocument):
    return get_workbench_store().create_draft(document)


@router.get("/drafts/{draft_id}/export")
def export_draft(draft_id: str):
    return get_draft(draft_id)


@router.get("/runs")
def list_runs(draft_id: str | None = None):
    return {"items": get_workbench_store().list_runs(draft_id)}


@router.post("/runs", status_code=202)
def create_run(data: RunCreateRequest):
    available, reason = GurobiAdapter.availability()
    if not available:
        raise problem(
            503,
            "solver_unavailable",
            reason or "The configured solver is unavailable.",
            retryable=True,
        )
    store = get_workbench_store()
    try:
        snapshot = store.get_snapshot(data.snapshot_id)
    except WorkbenchNotFoundError as exc:
        raise problem(404, "snapshot_not_found", str(exc)) from exc
    try:
        record = store.create_run(
            snapshot, data.trace_level, data.runtime_profile_id
        )
    except WorkbenchNotFoundError as exc:
        raise problem(422, "runtime_profile_not_found", str(exc)) from exc
    store.append_event(
        _queued_event(record.run_id)
    )
    get_run_manager().wake()
    return record


def _queued_event(run_id: str):
    from backend.schemas.workbench import RunEvent, utc_now

    return RunEvent(
        run_id=run_id,
        seq=1,
        emitted_at=utc_now(),
        elapsed_seconds=0,
        stage="queue",
        event_type="run_queued",
        message="Run queued for the single local solver slot.",
    )


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    try:
        return get_workbench_store().get_run(run_id)
    except WorkbenchNotFoundError as exc:
        raise problem(404, "run_not_found", str(exc)) from exc


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str):
    store = get_workbench_store()
    try:
        run = store.get_run(run_id)
        if run.job_status in TERMINAL:
            raise problem(409, "run_already_terminal", "The run is already terminal.")
        return store.request_cancel(run_id)
    except WorkbenchNotFoundError as exc:
        raise problem(404, "run_not_found", str(exc)) from exc


@router.get("/runs/{run_id}/events")
async def run_events(
    request: Request,
    run_id: str,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    after: int = Query(default=0, ge=0),
):
    try:
        start_after = max(after, int(last_event_id or 0))
        get_workbench_store().get_run(run_id)
    except ValueError as exc:
        raise problem(400, "invalid_last_event_id", str(exc)) from exc
    except WorkbenchNotFoundError as exc:
        raise problem(404, "run_not_found", str(exc)) from exc

    async def stream():
        cursor = start_after
        while True:
            if await request.is_disconnected():
                break
            store = get_workbench_store()
            events = store.list_events(run_id, cursor)
            for event in events:
                cursor = event.seq
                payload = event.model_dump(mode="json")
                yield (
                    f"id: {event.seq}\n"
                    f"event: {event.event_type}\n"
                    f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                )
            run = store.get_run(run_id)
            if run.job_status in TERMINAL and not events:
                break
            if not events:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.35)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/result")
def run_result(run_id: str):
    run = get_run(run_id)
    if run.result is None:
        raise problem(409, "result_not_ready", "The run has no result yet.", run_id=run_id, retryable=True)
    return run.result


@router.get("/runs/{run_id}/comparison")
def run_comparison(run_id: str):
    store = get_workbench_store()
    run = get_run(run_id)
    return build_comparison(store.get_snapshot(run.snapshot_id), run.result)


@router.get("/runs/{run_id}/audit")
def run_audit(run_id: str):
    store = get_workbench_store()
    run = get_run(run_id)
    snapshot = store.get_snapshot(run.snapshot_id)
    events = [item.model_dump(mode="json") for item in store.list_events(run_id)]
    return build_audit(snapshot, run.result, events)


@router.get("/runs/{run_id}/export")
def export_run(run_id: str):
    store = get_workbench_store()
    run = get_run(run_id)
    snapshot = store.get_snapshot(run.snapshot_id)
    return JSONResponse(
        {
            "schema_version": "2.0.0",
            "artifact_type": "air_recovery_audit_package",
            "run": run.model_dump(mode="json"),
            "snapshot": snapshot.model_dump(mode="json"),
            "comparison": build_comparison(snapshot, run.result),
            "audit": build_audit(
                snapshot,
                run.result,
                [
                    item.model_dump(mode="json")
                    for item in store.list_events(run_id)
                ],
            ),
        },
        headers={
            "Content-Disposition": f'attachment; filename="air-recovery-{run_id}.json"'
        },
    )
