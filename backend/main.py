from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.examples import router as examples_router
from backend.api.validate import router as validate_router

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="AIR Recovery Data Workbench",
    version="0.1.0",
    description="Phase 0 schema validation and toy-case data editor. No optimization model is enabled.",
)
app.include_router(validate_router)
app.include_router(examples_router)
app.mount("/static", StaticFiles(directory=FRONTEND_ROOT), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "index.html")


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "0"}

