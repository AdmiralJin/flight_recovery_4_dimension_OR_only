import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/examples", tags=["examples"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@router.get("/{scenario_id}")
def get_example(scenario_id: str) -> JSONResponse:
    if not scenario_id.replace("_", "").isalnum():
        raise HTTPException(status_code=404, detail="Example not found")
    path = PROJECT_ROOT / "data" / "examples" / f"{scenario_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Example not found")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

