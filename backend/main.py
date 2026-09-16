from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.examples import router as examples_router
from backend.api.config import router as config_router
from backend.api.model_constraints import router as constraints_router
from backend.api.validate import router as validate_router
from backend.api.solve import router as solve_router

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

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
app.mount("/static", StaticFiles(directory=FRONTEND_ROOT), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "index.html")


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "solver_enabled": True,
        "algorithm": "benders_branch_and_price_v1",
        "scope_mode": "full_only",
        "flight_option_generation": False,
        "production_ready": False,
    }
