"""User-started, serial HiGHS baselines, independent of AIR decomposition gates."""
from collections import Counter
from contextlib import contextmanager
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from .common import ROOT, clean, digest, file_hash, read_json, write_json, utc_now
from backend.workbench.solve_policy import recommend_time_limit

GROUPS = ("micro", "roadef", "delft", "xma")


def prepare(folder, previous):
    from .campaign import environment, snapshot_sources
    from .model import PublicSolveRequest
    from .workbench import make_document
    from backend.business.xma.importer import load_workbook, select_subset
    from backend.business.xma.schema import XmaSolveRequest
    from backend.business.xma.rules import generate_options
    from backend.business.xma.service import precheck
    folder, previous = Path(folder).resolve(), Path(previous).resolve()
    old = read_json(previous / "manifest.json")
    old_content = dict(old)
    if digest({k: v for k, v in old_content.items() if k != "manifest_sha256"}) != old["manifest_sha256"]:
        raise ValueError("previous manifest fingerprint mismatch")
    if file_hash(previous / "registry.json") != old["registry_sha256"]:
        raise ValueError("previous registry changed")
    registry = read_json(previous / "registry.json")
    # Validate every frozen input before creating the new experiment directory.
    public_inputs = []
    for entry in registry:
        path = previous / entry["path"]
        if file_hash(path) != entry["sha256"]:
            raise ValueError("previous input changed: "+entry["id"])
        public_inputs.append((entry, PublicSolveRequest.model_validate(read_json(path))))
    folder.mkdir(parents=True, exist_ok=False)
    inputs, jobs = [], []

    def register(key, payload, source, group, scale, algorithms, prior=None, readiness=None):
        path = folder / "inputs" / (key+".json")
        write_json(path, payload)
        policy = recommend_time_limit(scale["flights"], scale["candidates"], scale["assignment_pairs"])
        entry = dict(id=key, path=path.relative_to(folder).as_posix(), sha256=file_hash(path),
                     source=source, group=group, scale=scale, time_policy=policy,
                     previous_input=prior, readiness=readiness)
        inputs.append(entry)
        for algorithm in algorithms:
            jobs.append(dict(id=f"H{len(jobs)+1:04d}", group=group, instance=key, input=entry["path"],
                input_sha256=entry["sha256"], source=source, algorithm=algorithm, backend="highs",
                seconds=policy["time_limit_seconds"], memory_gib=6, threads=1, mip_gap=0,
                watchdog_grace_seconds=120, max_variables=1000000, max_constraints=1000000,
                scale=scale, time_policy=policy))

    for entry, public in public_inputs:
        public = public.model_copy(update={"algorithm": "direct_mip", "backend": "highs"})
        micro = len(public.scenario.flights) <= 12
        group = "micro" if micro else "roadef" if entry["source"] == "roadef2009" else "delft"
        algorithms = ["direct_mip", "integrated_oracle"] if micro else ["direct_mip"]
        scale = dict(flights=len(public.scenario.flights), aircraft=len(public.scenario.aircraft),
                     airports=len(public.scenario.airports), passenger_groups=len(public.scenario.passengers),
                     passengers=sum(g.count for g in public.scenario.passengers),
                     candidates=len(public.recovery_columns.flight_options),
                     assignment_pairs=len(public.recovery_columns.flight_options)*len(public.scenario.aircraft))
        register(entry["id"], public, entry["source"], group, scale, algorithms,
                 prior=dict(campaign=str(previous), sha256=entry["sha256"], problem_sha256=public.problem_sha256),
                 readiness=entry["precheck"])
        write_json(folder / "drafts" / (entry["id"]+".json"), make_document(public))
    data = load_workbook()
    for size in (20, 50, 100, 500, len(data.flights)):
        subset = select_subset(data, size) if size < len(data.flights) else data
        for objective in ("tianchi_2017", "air_linear_v1"):
            request = XmaSolveRequest(dataset=subset, algorithm="joint_arc_flow", solver_backend="highs",
                objective_profile=objective, delay_step_minutes=30, maximum_delay_minutes=120,
                max_assignment_options=1000000, mip_gap=0)
            options = generate_options(request)
            ready = precheck(request, _options=options)
            scale = dict(flights=len(subset.flights), aircraft=len(subset.aircraft), airports=len(subset.airports),
                         passenger_groups=None, passengers=None,
                         passenger_leg_observations=sum(f.passengers for f in subset.flights),
                         candidates=len(options), assignment_pairs=ready["assignment_options"])
            policy = recommend_time_limit(scale["flights"], scale["candidates"], scale["assignment_pairs"])
            request = request.model_copy(update={"time_limit_seconds":policy["time_limit_seconds"]})
            key = f"xma-{size}-{objective}"
            register(key, request, "xma_tianchi2017", "xma", scale, ["joint_arc_flow"], readiness=ready)
            from backend.business.xma.service import make_document as xma_document
            write_json(folder / "drafts" / (key+".json"), xma_document(request))
    write_json(folder / "registry.json", inputs)
    source_files = snapshot_sources(folder)
    manifest = dict(schema_version="public-campaign-1.0", campaign_kind="highs-direct-baseline-v1",
        created_at=utc_now(), git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        live_root=str(ROOT), python=sys.executable, environment=environment(), sources=source_files,
        registry_sha256=file_hash(folder / "registry.json"), jobs=jobs,
        previous_manifest_sha256=old["manifest_sha256"], groups=list(GROUPS),
        policy=dict(user_enter_required=True, global_concurrency=1, no_decomposition_gate=True,
                    optimization_backend="highs", fallback=False, original_rule_comparison=False,
                    time_budget="per_job_size_aware; no inherited 24h campaign cap",
                    grouping_is_not_independent_sampling=True),
        exclusions=[dict(dataset="TU_Delft_2019_Results", reason="published results without paired complete inputs")])
    manifest["manifest_sha256"] = digest(manifest)
    write_json(folder / "manifest.json", manifest)
    for group in GROUPS:
        write_json(folder / "groups" / (group+".json"), dict(status="prepared_not_started", group=group, jobs={}))
        launcher = ("@echo off\r\nchcp 65001 >nul\r\n"
            f"title HiGHS baseline - {group}\r\ncd /d \"{folder / 'source'}\"\r\n"
            f"\"{sys.executable}\" -u \"{folder / 'source/scripts/highs_baseline.py'}\" run-group \"{folder}\" {group}\r\n")
        (folder / f"start_{group}.cmd").write_text(launcher, encoding="utf-8")
    return dict(folder=str(folder), inputs=len(inputs), jobs=len(jobs), groups=dict(Counter(j["group"] for j in jobs)),
                maximum_registered_hours=sum(j["seconds"] for j in jobs)/3600, status="prepared_not_started")


def verify(folder):
    folder = Path(folder).resolve()
    manifest = read_json(folder / "manifest.json")
    if manifest.get("campaign_kind") != "highs-direct-baseline-v1":
        raise ValueError("not a HiGHS direct baseline campaign")
    if digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}) != manifest["manifest_sha256"]:
        raise ValueError("baseline manifest changed")
    if file_hash(folder / "registry.json") != manifest["registry_sha256"]:
        raise ValueError("baseline registry changed")
    for relative, expected in manifest["sources"].items():
        if file_hash(folder / "source" / relative) != expected:
            raise ValueError("frozen source changed: "+relative)
    for job in manifest["jobs"]:
        if file_hash(folder / job["input"]) != job["input_sha256"]:
            raise ValueError("frozen input changed: "+job["input"])
    return manifest


def launch(folder):
    folder = Path(folder).resolve()
    manifest = verify(folder)
    existing = folder / "windows.json"
    if existing.exists():
        import psutil
        if any(psutil.pid_exists(p["pid"]) for p in read_json(existing)):
            raise ValueError("baseline windows are already open; use their existing Enter prompts")
    windows = []
    for group in manifest["groups"]:
        path = folder / f"start_{group}.cmd"
        process = subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/k", f'call "{path}"'],
            cwd=folder, creationflags=subprocess.CREATE_NEW_CONSOLE)
        windows.append(dict(group=group, pid=process.pid, launcher=str(path), launched_at=utc_now()))
    write_json(existing, windows)
    return windows


@contextmanager
def file_lock(path, waiting=None):
    """OS-owned byte locks release after crashes; no stale PID lock deletion."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0"); stream.flush()
        announced = False
        while True:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if not announced and waiting:
                    waiting(); announced = True
                time.sleep(.5)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def worker(folder, job_id, target):
    folder, target = Path(folder).resolve(), Path(target).resolve()
    manifest = read_json(folder / "manifest.json")
    job = next(j for j in manifest["jobs"] if j["id"] == job_id)
    target.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    observed = dict(first_solver_incumbent_seconds=None, first_audited_solution_seconds=None)
    def events(value):
        payload = clean(value)
        payload["worker_elapsed_seconds"] = time.perf_counter()-started
        if payload.get("upper_bound") is not None and observed["first_solver_incumbent_seconds"] is None:
            observed["first_solver_incumbent_seconds"] = payload["worker_elapsed_seconds"]
        if payload.get("type") == "incumbent_audited" and observed["first_audited_solution_seconds"] is None:
            observed["first_audited_solution_seconds"] = payload["worker_elapsed_seconds"]
        with (target / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False)+"\n")
        print(json.dumps(payload, ensure_ascii=False), flush=True)
    try:
        path = folder / job["input"]
        if file_hash(path) != job["input_sha256"]:
            raise ValueError("input changed before worker")
        data = read_json(path)
        if job["source"] == "xma_tianchi2017":
            from backend.business.xma.schema import XmaSolveRequest
            from backend.business.xma.service import solve
            request = XmaSolveRequest.model_validate(data)
            if request.solver_backend != "highs" or request.algorithm != "joint_arc_flow":
                raise ValueError("baseline requires explicit HiGHS direct solve")
            from backend.business.xma.solver import SOLVER_OUTPUT
            token = SOLVER_OUTPUT.set(True)
            try:
                raw = solve(request, event_sink=events,
                            solution_artifact_sink=lambda value: write_json(target / "checkpoint.json", value))
            finally:
                SOLVER_OUTPUT.reset(token)
            d, primal = raw["diagnostics"], raw.get("independent_audit") or {}
            lb, ub = d.get("lower_bound"), d.get("upper_bound")
            closed = lb is not None and ub is not None and math.isfinite(lb) and math.isfinite(ub) and abs(ub-lb) <= 1e-5
            evidence = dict(status=raw["status"], algorithm=job["algorithm"], backend="highs",
                objective=raw["objective"], lower_bound=lb, upper_bound=ub,
                audit={"pass":primal.get("valid", False), "violations":primal.get("violations")},
                certified_optimal=raw["status"] == "optimal" and primal.get("valid", False) and closed,
                certified_infeasible=raw["status"] == "infeasible", core=raw,
                certificate_scope="XMA supported-actions finite-grid model; objectives kept separate")
            if raw["status"] == "optimal" and not evidence["certified_optimal"]:
                raise ValueError("XMA optimal label rejected by baseline audit/bounds")
        else:
            from .model import PublicSolveRequest
            from .solve import execute
            request = PublicSolveRequest.model_validate(data).model_copy(update={"algorithm":job["algorithm"], "backend":"highs"})
            evidence = execute(request, seconds=job["seconds"], output_flag=True, event_sink=events,
                               checkpoint_sink=lambda value: write_json(target / "checkpoint.json", value))
        write_json(target / "evidence.json", evidence)
        result = dict(status=evidence["status"], objective=evidence.get("objective"), lower_bound=evidence.get("lower_bound"),
            upper_bound=evidence.get("upper_bound"), certified_optimal=evidence.get("certified_optimal", False),
            certified_infeasible=evidence.get("certified_infeasible", False), audit_pass=(evidence.get("audit") or {}).get("pass"),
            preprocessing_only=evidence.get("preprocessing_only", False), backend="highs", algorithm=job["algorithm"],
            reason=evidence.get("reason"), model_size=evidence.get("model_size"))
        result.update(observed, timings=evidence.get("timings"))
    except Exception as exc:
        from .audit import EnumerationLimit
        result = dict(status="input_limit" if isinstance(exc, EnumerationLimit) else
                      "resource_limited" if isinstance(exc, MemoryError) else "error", reason=str(exc),
                      exception_type=type(exc).__name__, traceback=traceback.format_exc(), certified_optimal=False)
    result.update(job_id=job_id, worker_seconds=time.perf_counter()-started, finished_at=utc_now())
    write_json(target / "result.json", result)
    return result


def _retained(target, result):
    path = target / "checkpoint.json"
    if path.exists():
        saved = read_json(path)
        primal = saved.get("audit") or saved.get("independent_audit") or {}
        if primal.get("pass") or primal.get("valid"):
            result.update(retained_incumbent=True, objective=saved.get("objective"), upper_bound=saved.get("objective"),
                          lower_bound=saved.get("lower_bound"), audit_pass=True, certified_optimal=False)
    return result


def run_group(folder, group):
    if group not in GROUPS:
        raise ValueError("unknown group")
    folder = Path(folder).resolve()
    manifest = read_json(folder / "manifest.json")
    jobs = [j for j in manifest["jobs"] if j["group"] == group]
    state_path = folder / "groups" / (group+".json")
    old_state = read_json(state_path)
    if old_state["status"] == "completed":
        print("This group is already completed; existing evidence will not be overwritten.", flush=True)
        return old_state
    print(f"HiGHS DIRECT baseline / {group} / {len(jobs)} serial tasks", flush=True)
    print(f"Registered time ceiling: {sum(j['seconds'] for j in jobs)/3600:.2f} hours (tasks can finish early).", flush=True)
    print("One solve at a time across all four windows. Other groups wait for the machine lock.", flush=True)
    print("No Gurobi optimization. No AIR decomposition gate. Failures remain in the report.", flush=True)
    write_json(folder / "groups" / (group+"_window.json"), dict(status="waiting_for_enter", pid=os.getpid(), at=utc_now()))
    input("Press ENTER to start this group; close the window to leave it unstarted: ")
    manifest = verify(folder)
    from scripts.validation_campaign import GuardedChild, process_memory
    machine_lock = Path(manifest["live_root"]) / ".public_benchmarks/direct-baseline-machine.lock"
    with file_lock(folder / "groups" / (group+".lock"), lambda: print("Another copy of this group is active; waiting.", flush=True)):
        state = read_json(state_path)
        state.update(status="running", started_at=utc_now(), pid=os.getpid())
        write_json(state_path, state)
        for job in jobs:
            final = folder / "jobs" / job["id"] / "result.json"
            if final.exists():
                state["jobs"][job["id"]] = read_json(final)
                continue
            if (folder / "STOP").exists():
                state.update(status="stopped", stopped_at=utc_now())
                break
            with file_lock(machine_lock, lambda: print(f"{job['id']}: waiting for another window's solve to finish.", flush=True)):
                if (folder / "STOP").exists():
                    state.update(status="stopped", stopped_at=utc_now())
                    break
                job_root = folder / "jobs" / job["id"]
                job_root.mkdir(parents=True, exist_ok=True)
                attempt = len(list(job_root.glob("attempt_*")))+1
                target = job_root / f"attempt_{attempt:03d}"
                target.mkdir()
                state.update(active=job["id"], active_attempt=attempt)
                write_json(state_path, state)
                print(f"START {job['id']} {job['instance']} {job['algorithm']} / {job['seconds']}s", flush=True)
                env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                           MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
                command = [sys.executable, str(folder / "source/scripts/highs_baseline.py"), "_job", str(folder), job["id"], str(target)]
                began = time.monotonic()
                with (target / "worker.log").open("ab") as log:
                    process = GuardedChild(command, cwd=folder / "source", env=env, log=log, memory_gib=job["memory_gib"])
                    peak_rss, override, last_notice = 0, None, began
                    try:
                        while process.poll() is None:
                            peak_rss = max(peak_rss, process_memory(process))
                            elapsed = time.monotonic()-began
                            if (folder / "STOP").exists():
                                override = "cancelled"
                            elif elapsed > job["seconds"]+job["watchdog_grace_seconds"]:
                                override = "timed_out"
                            elif process.peak_commit() >= job["memory_gib"]*1024**3*.99:
                                override = "resource_limited"
                            if override:
                                process.kill(); break
                            if time.monotonic()-last_notice >= 30:
                                print(f"  {job['id']}: {elapsed:.0f}s, peak RSS {peak_rss/1024**3:.2f} GiB; details in {target / 'worker.log'}", flush=True)
                                last_notice = time.monotonic()
                            time.sleep(.25)
                        peak_commit = process.peak_commit()
                        path = target / "result.json"
                        result = read_json(path) if path.exists() else dict(status="error", reason="worker_exited_without_result", certified_optimal=False)
                        if override:
                            result.update(status=override, certified_optimal=False, certified_infeasible=False,
                                          reason="supervisor_"+override)
                        if override or not path.exists():
                            if not override and peak_commit >= job["memory_gib"]*1024**3*.8:
                                result.update(status="resource_limited", reason="worker_exit_near_memory_limit")
                            _retained(target, result)
                        result.update(job_id=job["id"], elapsed_seconds=time.monotonic()-began,
                            peak_rss_bytes=peak_rss, peak_commit_bytes=peak_commit, worker_returncode=process.poll(),
                            evidence_directory=target.relative_to(folder).as_posix(), attempt=attempt)
                    finally:
                        process.close()
                write_json(final, result)
                state["jobs"][job["id"]] = result
                state.update(active=None, updated_at=utc_now())
                write_json(state_path, state)
                report(folder, group)
                print(f"DONE {job['id']}: {result['status']} / objective={result.get('objective')} / {result['elapsed_seconds']:.1f}s", flush=True)
        else:
            state.update(status="completed", completed_at=utc_now(), active=None)
        write_json(state_path, state)
        report(folder, group)
    print(f"GROUP {group}: {state['status']}. Results: {folder}", flush=True)
    print("When all four groups finish, tell Codex to inspect the evidence.", flush=True)
    print("\a", end="", flush=True)
    return state


def report(folder, group=None):
    folder = Path(folder).resolve()
    manifest = read_json(folder / "manifest.json")
    rows = []
    for job in manifest["jobs"]:
        if group and job["group"] != group:
            continue
        path = folder / "jobs" / job["id"] / "result.json"
        result = read_json(path) if path.exists() else dict(status="not_started")
        rows.append({**{k:job[k] for k in ("id", "group", "instance", "source", "algorithm", "backend", "seconds")},
                     **job["scale"], **result})
    summary = dict(total=len(rows), counts=dict(Counter(r["status"] for r in rows)),
                   certified_optimal=sum(bool(r.get("certified_optimal")) for r in rows),
                   generated_at=utc_now(), manifest_sha256=manifest["manifest_sha256"])
    # Paired assertions only compare certificates of exactly the same frozen problem.
    conflicts = []
    for instance in {r["instance"] for r in rows}:
        values = [r["objective"] for r in rows if r["instance"] == instance and r.get("certified_optimal")]
        if len(values) > 1 and max(values)-min(values) > 1e-5:
            conflicts.append(instance)
    summary["certified_objective_conflicts"] = conflicts
    suffix = "_"+group if group else ""
    write_json(folder / ("summary"+suffix+".json"), summary)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (folder / ("runs"+suffix+".csv")).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k:json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k,v in r.items()} for r in rows)
    return summary
