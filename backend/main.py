from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.examples import router as examples_router
from backend.api.config import router as config_router
from backend.api.model_constraints import router as constraints_router
from backend.api.validate import router as validate_router

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="AIR Recovery Workbench",
    version="0.3.0",
    description="Scenario, Phase 2 cost and constraint audit workbench. Solver API remains disabled.",
)
app.include_router(validate_router)
app.include_router(examples_router)
app.include_router(config_router)
app.include_router(constraints_router)
app.mount("/static", StaticFiles(directory=FRONTEND_ROOT), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "index.html")


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "2.5-workbench"}
