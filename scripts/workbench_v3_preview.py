"""Local UI acceptance preview using existing APIs and a separate WorkbenchStore.

This adapter changes only test storage/worker entry points in its own processes.
No backend source, production records, or validation campaign is modified.
"""
from __future__ import annotations
import argparse
import atexit
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8013)
    parser.add_argument("--folder", type=Path, default=ROOT / ".workbench/v3_acceptance/preview_store")
    parser.add_argument("--worker")
    args = parser.parse_args()
    folder = args.folder.resolve()
    permitted = (ROOT / ".workbench/v3_acceptance").resolve()
    if not folder.is_relative_to(permitted):
        raise ValueError("Preview storage must stay inside .workbench/v3_acceptance")
    from backend.workbench.storage import WorkbenchStore
    if args.worker:
        from backend.workbench import worker
        worker.WorkbenchStore = lambda: WorkbenchStore(folder)
        raise SystemExit(worker.execute_run(args.worker))
    if not folder.exists():
        fixtures = json.loads((permitted / "api-fixtures.json").read_text(encoding="utf-8"))
        source = Path(fixtures["isolation"]["store"]).resolve()
        if not source.is_relative_to(permitted) or source == folder:
            raise ValueError("Fixture source must be an independent acceptance store")
        shutil.copytree(source, folder)
    store = WorkbenchStore(folder)
    from backend.workbench.run_manager import RunManager

    class PreviewManager(RunManager):
        def _launch(self, run_id):
            self._active_run_id = run_id
            self._cancel_seen_at = None
            self._active = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--folder", str(folder), "--worker", run_id],
                                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    manager = PreviewManager(store)
    from backend.api import workbench_v2, xma
    workbench_v2.get_workbench_store = lambda: store
    workbench_v2.get_run_manager = lambda: manager
    xma.get_workbench_store = lambda: store
    from backend.main import app
    atexit.register(manager.stop)
    import uvicorn
    print(f"Isolated v3 preview: http://127.0.0.1:{args.port}/static/workbench-v3/index.html#/prepare", flush=True)
    print(f"Test store: {folder}; production .workbench/workbench.sqlite3 is untouched.", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
