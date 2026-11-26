from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

from backend.schemas.workbench import JobStatus

from .storage import WorkbenchStore, get_workbench_store


ROOT = Path(__file__).resolve().parents[2]
TERMINAL = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.INTERRUPTED,
}


class RunManager:
    """Single-concurrency local process supervisor for exact solves."""

    def __init__(self, store: WorkbenchStore | None = None) -> None:
        self.store = store or get_workbench_store()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._active: subprocess.Popen[str] | None = None
        self._active_run_id: str | None = None
        self._cancel_seen_at: float | None = None
        self._initialized = False

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if not self._initialized:
                self.store.mark_running_interrupted()
                self._initialized = True
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="air-workbench-run-supervisor",
                daemon=True,
            )
            self._thread.start()

    def wake(self) -> None:
        self.start()

    def stop(self) -> None:
        self._stop.set()
        process = self._active
        if process and process.poll() is None:
            process.terminate()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._observe_active()
            if self._active is None:
                queued = self.store.next_queued_run()
                if queued is not None:
                    self._launch(queued.run_id)
            self._stop.wait(0.2)

    def _launch(self, run_id: str) -> None:
        self._active_run_id = run_id
        self._cancel_seen_at = None
        self._active = subprocess.Popen(
            [sys.executable, "-m", "backend.workbench.worker", run_id],
            cwd=ROOT,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0
            ),
        )

    def _observe_active(self) -> None:
        process = self._active
        run_id = self._active_run_id
        if process is None or run_id is None:
            return
        code = process.poll()
        if code is not None:
            run = self.store.get_run(run_id)
            if run.job_status not in TERMINAL:
                self.store.update_run_status(
                    run_id,
                    JobStatus.FAILED,
                    error={
                        "code": "worker_exit",
                        "message": f"Solver worker exited with code {code}.",
                        "retryable": True,
                    },
                )
            self._active = None
            self._active_run_id = None
            self._cancel_seen_at = None
            return
        run = self.store.get_run(run_id)
        if not run.cancel_requested:
            return
        if self._cancel_seen_at is None:
            self._cancel_seen_at = time.monotonic()
        elif time.monotonic() - self._cancel_seen_at >= 5.0:
            process.terminate()
            self.store.update_run_status(
                run_id,
                JobStatus.CANCELLED,
                optimization_status="aborted",
                error={
                    "code": "cancel_escalated",
                    "message": "The isolated solver process was terminated after the cooperative cancellation deadline.",
                    "retryable": True,
                },
            )


_MANAGER: RunManager | None = None


def get_run_manager() -> RunManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = RunManager()
    return _MANAGER
