"""Drain an immutable campaign supervisor without changing its frozen source."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import psutil

try:
    from .validation_campaign import GIB, atomic_json, read_json
except ImportError:
    from validation_campaign import GIB, atomic_json, read_json


def stamp():
    return datetime.now(timezone.utc).isoformat()


def start(folder: Path):
    folder = folder.resolve()
    previous = read_json(folder / "defer.json", {})
    if read_json(folder / "state.json", {}).get("status") == "finished":
        return 0  # An idempotent defer must not overwrite the original evidence.
    if previous.get("status") in {"starting", "draining", "finalizing"} and previous.get("controller_pid"):
        try:
            command = psutil.Process(previous["controller_pid"]).cmdline()
            if str(Path(__file__).resolve()).casefold() in [arg.casefold() for arg in command] and str(folder).casefold() in [arg.casefold() for arg in command]:
                return previous["controller_pid"]
        except psutil.Error:
            pass
    log = (folder / "defer.log").open("ab", buffering=0)
    try:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--folder", str(folder)],
                                 stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        log.close()
    return child.pid


def drain(folder: Path):
    import win32api
    import win32con
    import win32job
    import win32event
    import hashlib

    folder = folder.resolve()
    mutex = win32event.CreateMutex(None, False, "Local\\ValidationDefer_" + hashlib.sha256(str(folder).encode()).hexdigest()[:24])
    if win32event.WaitForSingleObject(mutex, 0) != win32event.WAIT_OBJECT_0:
        raise RuntimeError("A defer controller already owns this campaign")
    parent = None
    guardian = None
    suspended = False
    record = {"requested_at": stamp(), "controller_pid": os.getpid(), "status": "starting", "worker_observations": {}}
    try:
        state = read_json(folder / "state.json")
        if state.get("status") == "finished":
            record.update(status="finished", reason="Campaign already finished")
            return
        candidate = psutil.Process(state["supervisor_pid"])
        command = candidate.cmdline()
        if "supervise" not in command or str(folder).casefold() not in [x.casefold() for x in command]:
            raise RuntimeError("Supervisor identity mismatch")
        parent = candidate
        # If this controller dies (including an external hard kill), Windows closes
        # this handle and terminates the suspended supervisor and its guarded jobs.
        guardian = win32job.CreateJobObject(None, "")
        limits = win32job.QueryInformationJobObject(guardian, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(guardian, win32job.JobObjectExtendedLimitInformation, limits)
        handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, parent.pid)
        try:
            win32job.AssignProcessToJobObject(guardian, handle)
        finally:
            win32api.CloseHandle(handle)
        parent.suspend()
        suspended = True
        state = read_json(folder / "state.json")
        manifest = read_json(folder / "manifest.json")
        index = {j["id"]: j for j in manifest["jobs"]}
        workers = {}
        # Inventory real children as well as persisted rows: suspension can land
        # between spawn_job and the supervisor's next atomic state write.
        for child in parent.children(recursive=True):
            try:
                args = child.cmdline()
                if not any("validation_jobs.py" in value for value in args):
                    continue
                candidates = [Path(value) for value in args if "attempt_" in value and str(folder).casefold() in value.casefold()]
                if not candidates:
                    continue
                target = candidates[-1]
                attempt = target if target.is_dir() else target.parent
                job_id = attempt.parent.name
                if job_id not in index:
                    continue
                workers[job_id] = {"pid": child.pid, "created": child.create_time(), "attempt_folder": str(attempt), "peak_rss": 0}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        for job_id, row in state["jobs"].items():
            if row["status"] == "running" and job_id not in workers and psutil.pid_exists(row["pid"]):
                child = psutil.Process(row["pid"])
                if child.ppid() == parent.pid:
                    workers[job_id] = {"pid": child.pid, "created": child.create_time(), "attempt_folder": row["attempt_folder"], "peak_rss": 0}
        record.update(status="draining", supervisor_pid=parent.pid, original_deadline=state.get("deadline_epoch"),
                      workers=json.loads(json.dumps(workers)), queued_at_defer=[key for key, row in state["jobs"].items() if row["status"] == "pending"])
        low_since = None
        while workers:
            available = psutil.virtual_memory().available
            low_since = (low_since or time.monotonic()) if available < manifest["emergency_available_gib"] * GIB else None
            for job_id, info in list(workers.items()):
                try:
                    worker = psutil.Process(info["pid"])
                    if worker.create_time() != info["created"] or not worker.is_running():
                        del workers[job_id]
                        continue
                    tree = [worker, *worker.children(recursive=True)]
                    rss = sum(p.memory_info().rss for p in tree if p.is_running())
                    info.update(rss=rss, peak_rss=max(info["peak_rss"], rss), elapsed_seconds=time.time() - info["created"])
                    record["worker_observations"][job_id] = dict(info)
                    reason = ("campaign_budget" if state.get("deadline_epoch") and time.time() >= state["deadline_epoch"] else
                              "strict wall limit during deferred drain" if info["elapsed_seconds"] >= index[job_id]["wall_seconds"] else
                              "process tree memory limit during deferred drain" if rss > index[job_id]["memory_gib"] * GIB else
                              "system emergency memory floor" if low_since and time.monotonic() - low_since >= 10 else None)
                    if reason:
                        result_path = Path(info["attempt_folder"]) / "result.json"
                        if not result_path.exists():
                            atomic_json(result_path, {"verdict": "resource_limited" if "memory" in reason else "timed_out", "reason": reason,
                                                     "defer_controller": True, "recorded_at": stamp()})
                        for process in reversed(tree):
                            try:
                                process.kill()
                            except psutil.NoSuchProcess:
                                pass
                        info["stop_reason"] = reason
                        record["worker_observations"][job_id] = dict(info)
                except psutil.NoSuchProcess:
                    del workers[job_id]
            record.update(updated_at=stamp(), active_workers=workers.copy())
            atomic_json(folder / "defer.json", record)
            time.sleep(0.5)
        # STOP is observed before the original supervisor's admission loop.
        (folder / "STOP").touch()
        parent.resume()
        suspended = False
        record.update(status="finalizing", updated_at=stamp())
        atomic_json(folder / "defer.json", record)
        try:
            parent.wait(45)
        except psutil.TimeoutExpired:
            raise RuntimeError("Original supervisor failed to finalize within 45 seconds")
        final = read_json(folder / "state.json")
        if final.get("status") != "finished":
            raise RuntimeError("Supervisor ended without a finished state")
        record.update(status="finished", finished_at=stamp(), reason="Current workers drained; dispatch stopped; original evidence finalized")
    except BaseException:
        record.update(status="error", finished_at=stamp(), error=traceback.format_exc())
        (folder / "STOP").touch()
        if parent and parent.is_running():
            try:
                if suspended:
                    parent.resume()
                    suspended = False
                parent.wait(10)
            except (psutil.TimeoutExpired, psutil.Error):
                try:
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
        raise
    finally:
        atomic_json(folder / "defer.json", record)
        if guardian is not None:
            win32api.CloseHandle(guardian)
        win32api.CloseHandle(mutex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True, type=Path)
    drain(parser.parse_args().folder)
