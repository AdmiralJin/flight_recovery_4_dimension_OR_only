from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.examples import router as examples_router
from backend.api.config import router as config_router
from backend.api.model_constraints import router as constraints_router
from backend.api.validate import router as validate_router
from backend.api.solve import router as solve_router
from backend.api.cases import router as cases_router
from backend.api.workbench_v2 import WorkbenchProblem, router as workbench_v2_router
from backend.schemas.workbench import ProblemDetails, ProblemIssue
from backend.solver import GurobiAdapter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
V2_DIST_ROOT = FRONTEND_ROOT / "dist"

app = FastAPI(
    title="AIR Recovery Workbench",
    version="0.4.0",
    description="AIR research recovery workbench with a synchronous exact Phase 12 solver; not production-ready.",
)
app.include_router(validate_router)
app.include_router(examples_router)
app.include_router(config_router)
app.include_router(constraints_router)
app.include_router(solve_router)
app.include_router(cases_router)
app.include_router(workbench_v2_router)
app.mount("/static", StaticFiles(directory=FRONTEND_ROOT), name="static")
if V2_DIST_ROOT.is_dir():
    app.mount(
        "/workbench-v2/assets",
        StaticFiles(directory=V2_DIST_ROOT / "assets"),
        name="workbench-v2-assets",
    )


@app.exception_handler(WorkbenchProblem)
async def workbench_problem_handler(_request: Request, exc: WorkbenchProblem):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.details.model_dump(mode="json"),
    )


@app.exception_handler(RequestValidationError)
async def workbench_validation_handler(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith("/api/v2/"):
        return await request_validation_exception_handler(request, exc)
    issues = [
        ProblemIssue(
            code=str(item.get("type", "validation_error")),
            path=".".join(str(part) for part in item.get("loc", ())),
            message=str(item.get("msg", "Invalid request")),
        )
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ProblemDetails(
            code="invalid_request",
            message="The v2 request does not satisfy its schema.",
            issues=issues,
            retryable=False,
        ).model_dump(mode="json"),
    )


@app.middleware("http")
async def disable_workbench_asset_cache(request, call_next):
    response = await call_next(request)
    if (
        request.url.path in {"/", "/legacy", "/workbench-v2"}
        or request.url.path.startswith("/static/")
        or request.url.path.startswith("/workbench-v2/")
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    v2_index = V2_DIST_ROOT / "index.html"
    return FileResponse(v2_index if v2_index.is_file() else FRONTEND_ROOT / "index.html")


@app.get("/legacy", include_in_schema=False)
def legacy_index() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "index.html")


@app.get("/workbench-v2", include_in_schema=False)
@app.get("/workbench-v2/{route:path}", include_in_schema=False)
def workbench_v2(route: str = "") -> FileResponse:
    index_file = V2_DIST_ROOT / "index.html"
    if not index_file.is_file():
        return FileResponse(FRONTEND_ROOT / "index.html", status_code=503)
    return FileResponse(index_file)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str | bool | None]:
    solver_enabled, solver_reason = GurobiAdapter.availability()
    return {
        "status": "ok",
        "solver_enabled": solver_enabled,
        "solver_reason": solver_reason,
        "algorithm": "benders_branch_and_price_v1",
        "scope_mode": "full_only",
        "flight_option_generation": False,
        "production_ready": False,
    }
