from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from zipfile import BadZipFile

from backend.business.xma.importer import load_workbook, preview, select_subset
from backend.business.xma.schema import Decision, XmaSolveRequest
from backend.business.xma.service import make_document, precheck, solve
from backend.business.xma.evaluator import evaluate, export_csv
from backend.workbench.storage import get_workbench_store, WorkbenchNotFoundError

router=APIRouter(prefix="/api/v2/xma",tags=["xma-research"])


class EvaluationRequest(BaseModel):
    request: XmaSolveRequest
    decisions: list[Decision]


@router.post("/import-preview")
async def import_preview(request: Request,target_flights: int | None=Query(default=None,ge=1)):
    try:
        raw=await request.body()
        dataset=load_workbook() if not raw or raw==b"bundled" else load_workbook(raw)
        dataset=select_subset(dataset,target_flights)
        bundle=XmaSolveRequest(dataset=dataset)
        return {"preview":preview(dataset),"document":make_document(bundle).model_dump(mode="json")}
    except (ValueError,KeyError,OSError,BadZipFile,IndexError) as exc:
        raise HTTPException(422,detail={"code":"xma_import_failed","message":str(exc)}) from exc


@router.post("/precheck")
def readiness(request: XmaSolveRequest):
    return precheck(request)


@router.post("/solve")
def solve_bundle(request: XmaSolveRequest):
    try:
        return solve(request)
    except ValueError as exc:
        raise HTTPException(422,detail={"code":"invalid_xma_input","message":str(exc)}) from exc


@router.post("/evaluate")
def evaluation(data: EvaluationRequest):
    return evaluate(data.request,data.decisions)


@router.post("/export-csv",response_class=PlainTextResponse)
def csv_export(data: EvaluationRequest):
    return export_csv(data.request,data.decisions)


@router.get("/runs/{run_id}/csv",response_class=PlainTextResponse)
def run_csv(run_id: str):
    try:
        run=get_workbench_store().get_run(run_id)
    except WorkbenchNotFoundError as exc:
        raise HTTPException(404,detail="run not found") from exc
    result=run.result or {}
    if result.get("schema_version")!="xma-result-1.0" or not result.get("tianchi_csv"):
        raise HTTPException(409,detail="no XMA incumbent available for export")
    return PlainTextResponse(result["tianchi_csv"],headers={"Content-Disposition":f'attachment; filename="xma_{run_id}.csv"'})
