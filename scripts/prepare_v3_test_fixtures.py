"""Exercise existing API contracts using an independent store; record UI fixtures."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.api import workbench_v2, xma
    from backend.workbench import worker
    from backend.workbench.storage import WorkbenchStore
    from backend.schemas.workbench import CompilePreview

    output = ROOT / ".workbench/v3_acceptance"
    output.mkdir(exist_ok=True)
    isolated_folder = Path(tempfile.mkdtemp(prefix="contract_", dir=output))
    store = WorkbenchStore(isolated_folder)
    workbench_v2.get_workbench_store = lambda: store
    xma.get_workbench_store = lambda: store
    worker.WorkbenchStore = lambda: store
    client = TestClient(app)

    def checked(method, url, expected=200, **kwargs):
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == expected, (url, response.status_code, response.text[:1000])
        return response.json()

    result = {"cases": checked("get", "/api/cases")["cases"], "capabilities": checked("get", "/api/v2/capabilities"),
              "isolation": {"store": str(isolated_folder), "production_store_used": False}}
    for name in ("air", "xma"):
        if name == "air":
            draft = checked("post", "/api/v2/drafts", expected=201, json={"source_case_id": "benchmark-disruption-recovery"})
        else:
            imported = checked("post", "/api/v2/xma/import-preview?selection_mode=random&target_flights=20&selection_seed=20261106", content=b"bundled")
            imported["document"]["solve_bundle"].update(delay_step_minutes=60, maximum_delay_minutes=120, time_limit_seconds=30)
            result["xma_import"] = imported
            draft = checked("post", "/api/v2/imports/draft", expected=201, json=imported["document"])
        url = f"/api/v2/drafts/{draft['draft_id']}"
        # A real save and version conflict verify the UI's base_hash contract.
        document = draft["document"]
        document["name"] += " · v3 验收"
        draft = checked("put", url + "/working-copy", json={"base_hash": draft["working_hash"], "document": document})
        checked("put", url + "/working-copy", expected=409, json={"base_hash": "stale", "document": document})
        preview = checked("post", url + "/compile")
        assert preview["valid"] and preview["solve_request"]
        snapshot = checked("post", url + "/snapshots", expected=201, json={"base_hash": draft["working_hash"], "note": "isolated v3 frontend contract acceptance"})
        run = store.create_run(store.get_snapshot(snapshot["snapshot_id"]), "detailed")
        assert worker.execute_run(run.run_id) == 0
        prefix = f"/api/v2/runs/{run.run_id}"
        done = checked("get", prefix)
        assert done["job_status"] == "completed" and done["result"]
        result[name] = {"draft": draft, "compile": preview, "snapshot": snapshot, "run": done,
                        "events": checked("get", prefix + "/event-history")["items"],
                        "visualization": checked("get", prefix + "/visualization"),
                        "draftVisualization": checked("get", url + "/visualization"),
                        "comparison": checked("get", prefix + "/comparison"), "audit": checked("get", prefix + "/audit")}
        if name == "xma":
            response = client.get(f"/api/v2/xma/runs/{run.run_id}/csv")
            assert response.status_code == 200 and response.text.strip()
            result[name]["csv"] = response.text
        assert result[name]["visualization"]["mode_availability"]["recovered"]["available"]
    path = output / "api-fixtures.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"fixture": str(path), "store": str(isolated_folder), "air_status": result["air"]["run"]["optimization_status"], "xma_status": result["xma"]["run"]["optimization_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    prepare()
