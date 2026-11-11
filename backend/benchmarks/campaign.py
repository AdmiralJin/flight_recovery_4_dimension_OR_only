"""Frozen, resumable experiments with bounded Windows process trees."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
import traceback

from .common import ROOT, BASELINE, clean, digest, file_hash, read_json, write_json, discover, utc_now
from .model import PublicSolveRequest, build

TERMINAL = {"completed", "passed", "failed", "inconclusive", "error", "license_limited", "resource_limited",
            "timed_out", "unsupported_input", "input_limit", "not_run_budget", "blocked_by_correctness", "cancelled", "interrupted"}
PHASE_HOURS = {"correctness": 2, "comparison": 8, "stability": 6, "stress": 8}
ALGORITHMS = ["integrated_oracle", "fixed_benders", "air_cg", "air_bp", "xma_joint_arc_flow",
              "xma_joint_path_oracle", "xma_benders_joint", "xma_benders_cg_bp"]


def correctness_gate(manifest, state):
    """Stage advancement requires complete paired micro evidence, not just no crash."""
    problems = defaultdict(list)
    reasons = []
    for job in manifest["jobs"]:
        if job["phase"] != "correctness":
            continue
        result = state["jobs"].get(job["id"], {})
        if job["kind"] in ("pytest", "workbench", "components", "external") and result.get("verdict") != "passed":
            reasons.append(dict(job=job["id"], reason="regression_or_workbench_not_passed"))
        if job["kind"] == "solve" and (str(job["instance"]).startswith("micro-") or job["instance"] == "roadef-pax") and not job.get("backend_override"):
            problems[job["instance"]].append((job, result))
    for instance, runs in problems.items():
        values = [r.get("objective") for _, r in runs if r.get("certified_optimal")]
        expected = 3 if instance == "roadef-pax" else len(ALGORITHMS)
        all_optimal = len(runs) == expected and len(values) == len(runs)
        all_infeasible = len(runs) == expected and all(r.get("certified_infeasible") for _, r in runs)
        if not (all_optimal and max(values)-min(values) <= 1e-5 or all_infeasible):
            reasons.append(dict(instance=instance, reason="incomplete_or_inconsistent_micro_certificates",
                unresolved=[j["algorithm"] for j, r in runs if not (r.get("certified_optimal") or r.get("certified_infeasible"))]))
    for job in manifest["jobs"]:
        if job["phase"] == "correctness" and state["jobs"].get(job["id"], {}).get("verdict") in ("error", "failed"):
            reasons.append(dict(job=job["id"], reason="correctness_execution_failed"))
    return dict(passed=bool(problems) and not reasons, issues=reasons,
                micro_instances=len(problems), policy="all_registered_routes_have_matching_complete_micro_certificates")


def recover_interrupted_budget(state, *, now=None):
    """Charge interrupted active work conservatively; never reset its budget on resume."""
    active, started = state.get("active"), state.get("active_started_at")
    if not active or not started:
        return
    elapsed = ((now or datetime.now(timezone.utc))-datetime.fromisoformat(started)).total_seconds()
    cap = 600 if active["kind"] == "pytest" else active["seconds"]+45
    charge = min(cap, max(0., elapsed))
    state["elapsed_seconds"] = state.get("elapsed_seconds", 0)+charge
    state["phase_elapsed"][active["phase"]] = state["phase_elapsed"].get(active["phase"], 0)+charge
    state.setdefault("interruption_charges", []).append(dict(job=active["id"], seconds=charge,
        reason="conservative_active_job_wall_time_after_supervisor_interruption"))
    state["active"], state["active_started_at"] = None, None


def environment():
    import psutil
    versions = {}
    for name in ("highspy", "gurobipy", "numpy", "h5py", "pydantic", "openpyxl"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": sys.version, "executable": sys.executable, "versions": versions,
            "logical_cpus": psutil.cpu_count(), "physical_memory_bytes": psutil.virtual_memory().total}


def snapshot_sources(folder):
    target = folder / "source"
    paths = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\x00"))
    # Newly implemented files may not have been committed when preparing a pilot.
    for name in ("backend", "scripts", "tests"):
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / name).rglob("*.py"))
    # The v3 distribution is intentionally gitignored but is part of the live
    # HTTP serving contract and must accompany source-isolated API regressions.
    for distribution in ("frontend/dist", "frontend/workbench-v3"):
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / distribution).rglob("*") if p.is_file())
    records = {}
    for relative in sorted(paths):
        if not relative or not (ROOT / relative).is_file() or "__pycache__" in relative:
            continue
        if not (relative.startswith(("backend/", "scripts/", "tests/", "data/", "schemas/", "frontend/", "docs/models/", "docs/benchmarks/", "docs/user_guides/", "docs/codex_reports/xma_jar_validation_20261008/"))
                or relative in ("pyproject.toml", "requirements.txt", "README.md", "assumptions.md", "AGENTS.md", "reproduction_notes.md")):
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
        records[relative] = file_hash(destination)
    return records


def prepare(folder, *, data_root=None, budget_hours=24, profile="full", prior_campaign=None):
    if not 0 < budget_hours <= 24:
        raise ValueError("first campaign budget must be >0 and <=24 hours")
    for distribution in ("frontend/dist", "frontend/workbench-v3"):
        if not (ROOT / distribution / "index.html").exists():
            raise ValueError("build both frontend distributions before freezing: npm run build; npm run build:v3")
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    prior_budget = None
    if prior_campaign is not None:
        prior_folder = Path(prior_campaign).resolve()
        prior_state, prior_manifest = read_json(prior_folder / "state.json"), read_json(prior_folder / "manifest.json")
        if prior_state["status"] != "completed":
            raise ValueError("prior campaign must finish before carrying its consumed budget forward")
        prior_budget = dict(campaign=str(prior_folder), manifest_sha256=prior_manifest["manifest_sha256"],
            state_sha256=file_hash(prior_folder / "state.json"), elapsed_seconds=prior_state["elapsed_seconds"],
            phase_elapsed=prior_state["phase_elapsed"])
        write_json(folder / "prior_budget.json", prior_budget)
    from . import roadef, delft
    from .solve import precheck
    from .workbench import make_document
    roots = discover(data_root)
    inputs, registry, conversion_failures = {}, [], []

    def save(raw, name, **kwargs):
        try:
            normalize_start = time.perf_counter()
            request = build(raw, **kwargs)
            normalization_seconds = time.perf_counter()-normalize_start
            key = name
            path = folder / "inputs" / (key+".json")
            write_json(path, request)
            entry = dict(id=key, path=path.relative_to(folder).as_posix(), sha256=file_hash(path),
                problem_sha256=request.problem_sha256, source=request.source["dataset"],
                source_instance=request.source["source_instance"], model=request.model_type,
                block=f"{request.source['dataset']}:{request.source['source_instance']}",
                actual_flights=len(request.scenario.flights), actual_aircraft=len(request.scenario.aircraft),
                candidate_count=len(request.recovery_columns.flight_options), precheck=precheck(request))
            entry["normalization_and_candidates_seconds"] = normalization_seconds
            entry["fingerprints"] = dict(scenario=digest(request.scenario),
                candidates=digest(request.recovery_columns), configs=digest(request.configs),
                costs=digest(request.costs), capacity=digest(request.capacity_profile))
            registry.append(entry)
            inputs[key] = request
            return request
        except Exception as exc:
            conversion_failures.append(dict(id=name, selection=kwargs, error=str(exc), type=type(exc).__name__,
                                            source=raw["source"], source_instance=raw["source_instance"], source_files=raw["source_files"]))
            return None

    micro_ids = []
    for i, case in enumerate(["A01", "A02", "A03", "A04", "B01", "B02"]):
        raw = roadef.load(roots["ROADEF_2009"], case)
        name = f"micro-roadef-{case}"
        request = save(raw, name, target=[2, 4, 6, 8, 10, 12][i], seed=[0, 17, 42][i%3], capability_filter=True)
        if request is not None:
            micro_ids.append(name)
        if i == 0:
            save(raw, "roadef-pax", target=6, seed=0, model_type="aircraft_passenger")
            for grid in (60, 30, 15):
                save(raw, f"grid-roadef-{grid}", target=2, seed=0, step=grid)
    delft_raw = {}
    for i, day in enumerate(["2015-01-01", "2015-01-02", "2015-01-04", "2015-01-08", "2015-02-01", "2015-03-01"]):
        raw = delft.load(roots["TU_Delft_370_Disruptions"], datetime.fromisoformat(day+"T06:00:00+00:00"))
        delft_raw[day] = raw
        name = "micro-delft-"+day
        request = save(raw, name, target=[2, 4, 6, 8, 10, 12][i], seed=[0, 17, 42][i%3], capability_filter=True)
        if request is not None:
            micro_ids.append(name)
    # Connection observations are evaluation-only; one full 12h window is frozen
    # separately instead of duplicating 2.4 million rows into every micro input.
    write_json(folder / "source_connections.json", list(delft.connection_records(
        roots["TU_Delft_370_Disruptions"], [f for f in delft_raw["2015-01-01"]["flights"]
          if delft_raw["2015-01-01"]["start"] <= f["dep"] < delft_raw["2015-01-01"]["end"]])))
    from .results2019 import extract
    from .external import historical_references
    reference2019 = extract(roots["TU_Delft_2019_Results"], folder / "reference-2019")
    write_json(folder / "source_references.json", dict(roadef=historical_references(roots["ROADEF_2009"]),
        delft2019=reference2019, delft2020="no_verified_original_370_partition_or_per_instance_answers"))
    if profile == "full":
        for source, raw in [("roadef", roadef.load(roots["ROADEF_2009"], "A01")),
                            ("delft", delft_raw["2015-01-01"])]:
            for n in (20, 50, 100):
                for seed in (0, 17, 42):
                    save(raw, f"scale-{source}-{n}-{seed}", target=n, seed=seed)
            save(raw, f"stress-{source}-500", target=500, seed=0)
        for case, _ in roadef.instance_paths(roots["ROADEF_2009"]):
            save(roadef.load(roots["ROADEF_2009"], case), "full-roadef-"+case, target=10**9, seed=0)
        save(delft_raw["2015-01-01"], "full-delft-12h", target=10**9, seed=0)
    jobs = []
    def add(kind, phase, instance=None, algorithm=None, **kwargs):
        job = dict(id=f"J{len(jobs)+1:04d}", kind=kind, phase=phase, instance=instance, algorithm=algorithm,
                   backend="highs", seconds=120 if phase == "correctness" else 1800 if phase == "stress" else 300,
                   memory_gib=6, repeat=None, warmup=False)
        job.update(kwargs)
        jobs.append(job)
        return job["id"]
    add("pytest", "correctness")
    for name in micro_ids:
        for algorithm in ALGORITHMS:
            add("solve", "correctness", name, algorithm)
        add("solve", "correctness", name, "integrated_oracle", backend_override="gurobi")
        add("components", "correctness", name)
    if "roadef-pax" in inputs:
        for algorithm in ("integrated_oracle", "fixed_benders", "air_bp"):
            add("solve", "correctness", "roadef-pax", algorithm)
    if micro_ids:
        add("external", "correctness", micro_ids[0])
        add("workbench", "correctness", micro_ids[0], "air_bp")
    for name in inputs:
        if name.startswith("scale-"):
            for algorithm in ("air_bp", "xma_joint_arc_flow", "xma_benders_joint", "xma_benders_cg_bp"):
                add("solve", "comparison", name, algorithm, warmup=True, repeat=-1)
                for repeat in range(3):
                    add("solve", "comparison", name, algorithm, repeat=repeat)
        if name.startswith("grid-"):
            add("solve", "stability", name, "air_bp")
    for name in micro_ids[:1]+micro_ids[6:7]:
        for repeat in range(3):
            add("solve", "stability", name, "air_bp", repeat=repeat)
    for name in micro_ids[3:4]+micro_ids[9:10]:
        for limit in ("cancel", "nodes", "iterations", "time"):
            add("stop", "stability", name, "air_bp", stop_kind=limit)
    for name in inputs:
        if name.startswith(("full-", "stress-")):
            solve_job = add("solve", "stress", name, "air_bp")
            if name.startswith("full-roadef-"):
                add("external", "stress", name, evidence_from_job=solve_job)
    for failed in conversion_failures:
        add("conversion_failure", "stress" if failed["id"].startswith(("full-", "stress-")) else "correctness", failed["id"])
    order = {name: i for i, name in enumerate(PHASE_HOURS)}
    jobs.sort(key=lambda job: (order[job["phase"]], job["id"]))
    write_json(folder / "registry.json", registry)
    write_json(folder / "conversion_failures.json", conversion_failures)
    for name in micro_ids[:1]+micro_ids[6:7]:
        write_json(folder / "drafts" / (name+".json"), make_document(inputs[name]))
    source_manifest = snapshot_sources(folder)
    # Registry and all model/config snapshots are immutable campaign inputs.
    for entry in registry:
        source_manifest["../"+entry["path"]] = entry["sha256"]
    for name in ("source_connections.json", "conversion_failures.json", "source_references.json",
                 "reference-2019/summary.json", "reference-2019/rows.jsonl"):
        source_manifest["../"+name] = file_hash(folder / name)
    if prior_budget:
        source_manifest["../prior_budget.json"] = file_hash(folder / "prior_budget.json")
    manifest = dict(schema_version="public-campaign-1.0", created_at=utc_now(), baseline=BASELINE,
        git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        environment=environment(), profile=profile, budget_hours=budget_hours,
        phase_budgets_seconds={k: v*3600*budget_hours/24 for k, v in PHASE_HOURS.items()},
        resource_policy=dict(threads=1, max_concurrency=1, heavy_exclusive=True, process_tree_memory_gib=6,
                             no_silent_fallback=True, no_automatic_grid_or_demand_reduction=True),
        jobs=jobs, sources=source_manifest, registry_sha256=file_hash(folder / "registry.json"),
        prior_budget=prior_budget,
        source_roots={k: str(v.resolve()) for k, v in roots.items()},
        sample_freeze="before any campaign algorithm outcomes; seeds 0,17,42; complete tail/window scope")
    manifest["manifest_sha256"] = digest(manifest)
    write_json(folder / "manifest.json", manifest)
    write_json(folder / "state.json", dict(status="prepared", jobs={},
        phase_elapsed=prior_budget["phase_elapsed"] if prior_budget else {},
        elapsed_seconds=prior_budget["elapsed_seconds"] if prior_budget else 0))
    report(folder)
    return dict(campaign=str(folder), jobs=len(jobs), inputs=len(inputs), conversion_failures=len(conversion_failures),
                budget_hours=budget_hours, manifest_sha256=manifest["manifest_sha256"])


def _verify(folder, manifest):
    copy = dict(manifest)
    expected = copy.pop("manifest_sha256")
    if digest(copy) != expected:
        raise ValueError("campaign manifest changed after freeze")
    if file_hash(folder / "registry.json") != manifest["registry_sha256"]:
        raise ValueError("frozen registry changed")
    for path, expected in manifest["sources"].items():
        if file_hash(folder / "source" / path) != expected:
            raise ValueError("frozen source or instance changed: "+path)


def refreeze(previous, folder, *, reason):
    """Replace code/environment while preserving every previously frozen sample and task."""
    previous, folder = previous.resolve(), folder.resolve()
    old, consumed = read_json(previous / "manifest.json"), read_json(previous / "state.json")
    if consumed["status"] != "completed":
        raise ValueError("stop the prior campaign before refreezing its immutable inputs")
    _verify(previous, old)
    for distribution in ("frontend/dist", "frontend/workbench-v3"):
        if not (ROOT / distribution / "index.html").exists():
            raise ValueError("build both frontend distributions before refreezing")
    folder.mkdir(parents=True, exist_ok=False)
    for name in ("inputs", "drafts", "reference-2019"):
        shutil.copytree(previous / name, folder / name)
    names = ["registry.json", "conversion_failures.json", "source_connections.json", "source_references.json"]
    for name in names:
        shutil.copy2(previous / name, folder / name)
    prior = dict(campaign=str(previous), manifest_sha256=old["manifest_sha256"],
                 state_sha256=file_hash(previous / "state.json"), elapsed_seconds=consumed["elapsed_seconds"],
                 phase_elapsed=consumed["phase_elapsed"])
    write_json(folder / "prior_budget.json", prior)
    sources = snapshot_sources(folder)
    registry = read_json(folder / "registry.json")
    for entry in registry:
        sources["../"+entry["path"]] = entry["sha256"]
    for name in names+["prior_budget.json", "reference-2019/summary.json", "reference-2019/rows.jsonl"]:
        sources["../"+name] = file_hash(folder / name)
    manifest = {**old, "created_at": utc_now(), "environment": environment(), "sources": sources,
                "prior_budget": prior, "refrozen_from_manifest": old["manifest_sha256"], "refreeze_reason": reason,
                "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    manifest.pop("manifest_sha256")
    manifest["manifest_sha256"] = digest(manifest)
    write_json(folder / "manifest.json", manifest)
    write_json(folder / "state.json", dict(status="prepared", jobs={}, phase_elapsed=prior["phase_elapsed"],
                                          elapsed_seconds=prior["elapsed_seconds"]))
    report(folder)
    return dict(campaign=str(folder), inputs=len(registry), jobs=len(manifest["jobs"]),
                manifest_sha256=manifest["manifest_sha256"], carried_budget_seconds=prior["elapsed_seconds"])


def worker(folder, job_id):
    folder = folder.resolve()
    manifest = read_json(folder / "manifest.json")
    job = next(j for j in manifest["jobs"] if j["id"] == job_id)
    target = folder / "jobs" / job_id
    target.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    write_json(target / "started.json", dict(at=utc_now(), job=job, environment=environment()))
    def events(data):
        with (target / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(clean(data), ensure_ascii=False, allow_nan=False)+"\n")
    try:
        entry = next((r for r in read_json(folder / "registry.json") if r["id"] == job["instance"]), None)
        public = PublicSolveRequest.model_validate(read_json(folder / entry["path"])) if entry else None
        if public:
            public = public.model_copy(update={"algorithm": job["algorithm"] or "air_bp", "backend": job.get("backend_override") or job["backend"]})
            write_json(target / "input.json", public)
            if len(public.recovery_columns.flight_options)*len(public.scenario.aircraft) > 1000000:
                result = dict(verdict="input_limit", reason="more_than_1000000_option_tail_pairs", scale=entry)
                write_json(target / "result.json", result)
                return result
        if job["kind"] == "pytest":
            run = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "tests/api", "tests/regression",
                                  "-q", "--tb=short"], cwd=Path(__file__).resolve().parents[2],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (target / "pytest.log").write_bytes(run.stdout)
            result = dict(verdict="passed" if run.returncode == 0 else "failed", returncode=run.returncode)
        elif job["kind"] == "conversion_failure":
            failure = next(r for r in read_json(folder / "conversion_failures.json") if r["id"] == job["instance"])
            result = dict(verdict="unsupported_input", reason="conversion_failed", details=failure)
        elif job["kind"] == "components":
            from .solve import execute
            from .components import execute as component_execute
            oracle = execute(public.model_copy(update={"algorithm": "integrated_oracle"}), seconds=job["seconds"])
            if oracle.get("certified_optimal"):
                evidence = component_execute(public, oracle["selected"]["flight_options"], job["seconds"])
                result = dict(verdict=evidence["status"])
            else:
                evidence = oracle
                result = dict(verdict="inconclusive", reason="no_certified_feasible_schedule_for_component_comparison")
            write_json(target / "evidence.json", evidence)
        elif job["kind"] == "workbench":
            from .workbench import make_document
            from backend.workbench.compiler import compile_draft
            from backend.workbench.storage import WorkbenchStore
            from backend.workbench import worker as workbench_worker
            from backend.schemas.workbench import RuntimeProfileParameters, JobStatus
            from unittest.mock import patch
            document = make_document(public)
            preview = compile_draft(document)
            if not preview.valid:
                raise ValueError(str(preview.issues))
            store = WorkbenchStore(target / "workbench-state")
            draft = store.create_draft(document, "file_import")
            snapshot = store.create_snapshot(draft.draft_id, draft.working_hash, preview)
            store.clone_runtime_profile("default-exact", "public-review", "Public benchmark review")
            store.update_runtime_profile("public-review", "Public benchmark review",
                RuntimeProfileParameters(time_limit_seconds=job["seconds"]))
            run = store.create_run(snapshot, "detailed", "public-review")
            with patch.object(workbench_worker, "WorkbenchStore", lambda: store):
                code = workbench_worker.execute_run(run.run_id)
            done = store.get_run(run.run_id)
            if code or done.job_status != JobStatus.COMPLETED:
                raise ValueError(str(done.error))
            write_json(target / "evidence.json", done.result)
            write_json(target / "events.json", store.list_events(run.run_id))
            result = dict(verdict="passed", draft_id=draft.draft_id, snapshot_id=snapshot.snapshot_id,
                          run_id=run.run_id, state_root=str(store.state_root))
        elif job["kind"] == "external":
            from .solve import execute
            from .external import export, check
            previous = folder / "jobs" / str(job.get("evidence_from_job")) / "evidence.json"
            evidence = read_json(previous) if job.get("evidence_from_job") and previous.exists() else (
                {} if job.get("evidence_from_job") else execute(public, seconds=job["seconds"]))
            if (evidence.get("audit") or {}).get("pass"):
                export(public, evidence, target / "native")
                native = check(Path(manifest["source_roots"]["ROADEF_2009"]), target / "native")
                write_json(target / "evidence.json", native)
                # A rejected research solution is an expected boundary result.
                result = dict(verdict="passed", native_feasible=native["passed"], historical_eligible=native["historical_comparison_eligible"])
            else:
                result = dict(verdict="inconclusive", reason="no_audited_solution_for_native_export")
        else:
            from .solve import execute
            seconds, node_limit, iteration_limit = job["seconds"], None, None
            if job["kind"] == "stop":
                if job["stop_kind"] == "time": seconds = .02
                if job["stop_kind"] == "nodes": node_limit = 1
                if job["stop_kind"] == "iterations": iteration_limit = 1
            evidence = execute(public, seconds=seconds,
                cancel_check=(lambda: time.perf_counter()-started > .2) if job.get("stop_kind") == "cancel" else None,
                node_limit=node_limit, iteration_limit=iteration_limit, event_sink=events,
                checkpoint_sink=lambda value: write_json(target / "checkpoint.json", value))
            write_json(target / "evidence.json", evidence)
            verdict = "unsupported_input" if evidence["status"] == "unsupported_input" else "completed"
            if evidence.get("objective") is not None and not (evidence.get("audit") or {}).get("pass"):
                verdict = "failed"
            result = dict(verdict=verdict, optimization_status=evidence["status"],
                objective=evidence.get("objective"), lower_bound=evidence.get("lower_bound"), upper_bound=evidence.get("upper_bound"),
                certified_optimal=evidence.get("certified_optimal", False), audit_pass=(evidence.get("audit") or {}).get("pass"),
                certified_infeasible=evidence.get("certified_infeasible", False),
                problem_sha256=public.problem_sha256, algorithm=public.algorithm, backend=public.backend,
                preprocessing_only=evidence.get("preprocessing_only", False),
                solver_runtime_seconds=evidence.get("runtime_seconds"))
    except Exception as exc:
        verdict = "license_limited" if getattr(exc, "errno", None) == 10010 else "error"
        from .audit import EnumerationLimit
        from backend.solver.runtime import SolveStopped
        if isinstance(exc, EnumerationLimit): verdict = "input_limit"
        if isinstance(exc, SolveStopped): verdict = "inconclusive"
        result = dict(verdict=verdict, error=str(exc), exception_type=type(exc).__name__, traceback=traceback.format_exc())
    result.update(job_id=job_id, elapsed_seconds=time.perf_counter()-started, finished_at=utc_now())
    write_json(target / "result.json", result)
    return result


def launch(folder):
    folder = folder.resolve()
    script = folder / "source/scripts/public_benchmark.py"
    # Popen creates no visible window and redirects every handle. The supervisor
    # and all child processes continue writing durable status/report files.
    with (folder / "supervisor.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, str(script), "campaign", str(folder)], cwd=folder / "source",
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    write_json(folder / "supervisor.json", dict(pid=process.pid, started_at=utc_now()))
    return dict(pid=process.pid, campaign=str(folder), report=str(folder / "report.md"))


def supervise(folder):
    from scripts.validation_campaign import GuardedChild, process_memory
    import psutil
    folder = folder.resolve()
    manifest = read_json(folder / "manifest.json")
    _verify(folder, manifest)
    lock = folder / "supervisor.lock"
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        pid = int(lock.read_text())
        if psutil.pid_exists(pid):
            raise ValueError(f"campaign is already running as PID {pid}")
        lock.unlink()
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(handle, str(os.getpid()).encode()); os.close(handle)
    state = read_json(folder / "state.json")
    interrupted = state.get("active")
    recover_interrupted_budget(state)
    if interrupted and interrupted["id"] not in state["jobs"] and not (folder / "jobs" / interrupted["id"] / "result.json").exists():
        state["jobs"][interrupted["id"]] = dict(verdict="interrupted", reason="supervisor_interrupted_during_job")
    state.update(status="running", supervisor_pid=os.getpid(), updated_at=utc_now())
    job_start = time.monotonic()
    prior_elapsed = state.get("elapsed_seconds", 0)
    try:
        for job in manifest["jobs"]:
            if job["id"] in state["jobs"]:
                continue
            # Recover completed worker output after a supervisor interruption.
            result_path = folder / "jobs" / job["id"] / "result.json"
            if result_path.exists():
                state["jobs"][job["id"]] = read_json(result_path)
                continue
            elapsed = prior_elapsed+time.monotonic()-job_start
            phase_used = state["phase_elapsed"].get(job["phase"], 0)
            remaining = min(manifest["budget_hours"]*3600-elapsed,
                            manifest["phase_budgets_seconds"][job["phase"]]-phase_used)
            if (folder / "cancel.request").exists():
                verdict = "cancelled"
            elif remaining <= 0:
                verdict = "not_run_budget"
            elif job["phase"] != "correctness" and not correctness_gate(manifest, state)["passed"]:
                verdict = "blocked_by_correctness"
            else:
                verdict = None
            if verdict:
                state["jobs"][job["id"]] = dict(verdict=verdict, elapsed_seconds=0)
                continue
            target = folder / "jobs" / job["id"]
            target.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                       MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
            command = [sys.executable, str(folder / "source/scripts/public_benchmark.py"), "_job", str(folder), job["id"]]
            phase_start = time.monotonic()
            state["active"] = job
            state["active_started_at"] = utc_now()
            write_json(folder / "state.json", state)
            with (target / "worker.log").open("ab") as log:
                process = GuardedChild(command, cwd=folder / "source", env=env, log=log, memory_gib=job["memory_gib"])
                peak_rss, override = 0, None
                try:
                    wall = min(remaining, job["seconds"]+45 if job["kind"] != "pytest" else 600)
                    while process.poll() is None:
                        peak_rss = max(peak_rss, process_memory(process))
                        if (folder / "cancel.request").exists():
                            override = "cancelled"
                        elif time.monotonic()-phase_start > wall:
                            override = "timed_out"
                        elif process.peak_commit() >= job["memory_gib"]*1024**3*.99:
                            override = "resource_limited"
                        if override:
                            process.kill()
                            break
                        time.sleep(.25)
                    peak_commit = process.peak_commit()
                    result = read_json(result_path) if result_path.exists() else dict(verdict="error", reason="worker_exited_without_result")
                    if override:
                        result.update(verdict=override)
                    checkpoint = target / "checkpoint.json"
                    if checkpoint.exists() and not result.get("audit_pass"):
                        saved = read_json(checkpoint)
                        if (saved.get("audit") or {}).get("pass"):
                            result.update(retained_incumbent=True, audit_pass=True, objective=saved["objective"],
                                upper_bound=saved["objective"], lower_bound=saved.get("lower_bound"),
                                certified_optimal=False, optimization_status="aborted" if override == "cancelled" else "not_converged")
                    if not result_path.exists() and (process.poll() or 0) != 0 and peak_commit > job["memory_gib"]*1024**3*.8:
                        result.update(verdict="resource_limited")
                    result.update(peak_rss_bytes=peak_rss, peak_process_tree_commit_bytes=peak_commit,
                                  worker_returncode=process.poll(), wall_seconds=time.monotonic()-phase_start)
                finally:
                    process.close()
            state["jobs"][job["id"]] = result
            state["phase_elapsed"][job["phase"]] = phase_used+time.monotonic()-phase_start
            state.update(active=None, active_started_at=None, elapsed_seconds=prior_elapsed+time.monotonic()-job_start, updated_at=utc_now())
            write_json(folder / "state.json", state)
            report(folder)
        state.update(status="completed", active=None, elapsed_seconds=prior_elapsed+time.monotonic()-job_start, updated_at=utc_now())
        write_json(folder / "state.json", state)
        return report(folder)
    finally:
        lock.unlink(missing_ok=True)


def report(folder):
    folder = folder.resolve()
    manifest, state = read_json(folder / "manifest.json"), read_json(folder / "state.json")
    registry = {r["id"]: r for r in read_json(folder / "registry.json")}
    counts = Counter(r["verdict"] for r in state["jobs"].values())
    rows, grouped = [], defaultdict(list)
    for job in manifest["jobs"]:
        result = state["jobs"].get(job["id"], {})
        row = {**{k: job.get(k) for k in ("id", "kind", "phase", "instance", "algorithm", "backend", "repeat", "warmup")},
               "actual_flights": registry.get(job["instance"], {}).get("actual_flights"),
               "block": registry.get(job["instance"], {}).get("block"),
               **{k: result.get(k) for k in ("verdict", "optimization_status", "objective", "lower_bound", "upper_bound",
                    "certified_optimal", "certified_infeasible", "preprocessing_only", "retained_incumbent", "audit_pass", "elapsed_seconds", "solver_runtime_seconds", "peak_rss_bytes", "error")}}
        row["verdict"] = row["verdict"] or "pending"
        rows.append(row)
        if row["certified_optimal"] and not job["warmup"]:
            grouped[(job["instance"], job["algorithm"])].append(row)
    comparisons = []
    for instance in registry:
        certified = [r for r in rows if r["instance"] == instance and r["certified_optimal"]]
        objectives = [r["objective"] for r in certified]
        if objectives:
            comparisons.append(dict(instance=instance, certified_runs=len(certified), min_objective=min(objectives),
                                    max_objective=max(objectives), consistent=max(objectives)-min(objectives) <= 1e-5))
    performance = []
    for (instance, algorithm), runs in grouped.items():
        times = [r["solver_runtime_seconds"] for r in runs if r["solver_runtime_seconds"] is not None]
        if times:
            performance.append(dict(instance=instance, algorithm=algorithm, n=len(times), median_seconds=statistics.median(times),
                                    min_seconds=min(times), max_seconds=max(times),
                                    stdev_seconds=statistics.stdev(times) if len(times) > 1 else None,
                                    objective_min=min(r["objective"] for r in runs), objective_max=max(r["objective"] for r in runs)))
    rates, speedups = [], []
    for algorithm in ALGORITHMS:
        selected = [r for r in rows if r["kind"] == "solve" and r["algorithm"] == algorithm and not r["warmup"]]
        if selected:
            rates.append(dict(algorithm=algorithm, registered=len(selected),
                executed=sum(r["verdict"] not in ("pending", "not_run_budget", "blocked_by_correctness") for r in selected),
                audited_feasible=sum(r["audit_pass"] is True for r in selected),
                certified_optimal=sum(bool(r["certified_optimal"]) for r in selected),
                denominator="all registered non-warmup tasks, including unsuccessful and undispatched tasks"))
    for instance in registry:
        paired = {algorithm: [r for r in rows if r["instance"] == instance and r["algorithm"] == algorithm
                             and r["phase"] == "comparison" and not r["warmup"]] for algorithm in ALGORITHMS}
        reference = paired["xma_joint_arc_flow"]
        for algorithm, runs in paired.items():
            combined = reference+runs
            if algorithm == "xma_joint_arc_flow" or len(reference) != 3 or len(runs) != 3:
                continue
            if not all(r["certified_optimal"] and r["audit_pass"] for r in combined):
                continue
            if max(r["objective"] for r in combined)-min(r["objective"] for r in combined) > 1e-5:
                continue
            elapsed = statistics.median(r["solver_runtime_seconds"] for r in runs)
            if elapsed > 0:
                speedups.append(dict(instance=instance, algorithm=algorithm, reference="xma_joint_arc_flow",
                    certified_median_speedup=statistics.median(r["solver_runtime_seconds"] for r in reference)/elapsed))
    grid = []
    for instance in sorted(k for k in registry if k.startswith("grid-")):
        certified = [r for r in rows if r["instance"] == instance and r["certified_optimal"]]
        if certified:
            grid.append(dict(instance=instance, step=int(instance.rsplit("-", 1)[-1]), objective=certified[0]["objective"]))
    grid.sort(key=lambda r: -r["step"])
    grid_check = dict(certified=grid, comparable_pairs=len(grid)-1 if grid else 0,
        monotone=all(b["objective"] <= a["objective"]+1e-5 for a, b in zip(grid, grid[1:])) if len(grid) > 1 else None,
        scope="nested grids, same raw records, tail selection, source boundaries and delay limit; certified optima only")
    with (folder / "runs.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["id"])
        writer.writeheader(); writer.writerows(rows)
    false_comparisons = [r for r in comparisons if not r["consistent"]]
    summary = dict(status=state["status"], jobs_total=len(rows), jobs_finished=len(state["jobs"]), verdicts=dict(counts),
        correctness_gate=correctness_gate(manifest, state),
        certified_optimal=sum(bool(r["certified_optimal"]) for r in rows), audit_pass=sum(r["audit_pass"] is True for r in rows),
        inconsistent_objectives=false_comparisons, comparisons=comparisons, performance=performance,
        registered_task_rates=rates, paired_certified_speedups=speedups, candidate_grid_check=grid_check,
        elapsed_seconds=state["elapsed_seconds"], phase_elapsed=state["phase_elapsed"],
        campaign_finished=state["status"] == "completed",
        acceptance_passed=state["status"] == "completed" and correctness_gate(manifest, state)["passed"] and not false_comparisons,
        original_rule_scores_not_inferred_from_research_objective=True)
    write_json(folder / "summary.json", summary)
    text = ["# Workbench v3 公开数据验证运行报告", "",
            f"状态：{state['status']}；任务 {len(state['jobs'])}/{len(rows)}；计算预算上限 {manifest['budget_hours']} 小时。", "",
            f"基线 `{BASELINE[:7]}`；清单 `{manifest['manifest_sha256']}`。所有失败、限时及未执行任务均在 runs.csv 中保留。", "",
            "|任务结果|数量|", "|---|---:|"]
    text += [f"|{key}|{value}|" for key, value in sorted(counts.items())]
    text += ["", f"正确性阶段门槛：{'通过' if summary['correctness_gate']['passed'] else '未通过或尚未完成'}；运行完成不等于验收通过。缺口见 summary.json.correctness_gate。"]
    text += ["", f"认证模型内最优运行：{summary['certified_optimal']}；通过独立方案审计：{summary['audit_pass']}；认证目标不一致：{len(false_comparisons)}。", "",
             "研究模型关闭 CRM，仅使用原始公开飞机及可完整映射的旅客组。机场容量、舱等、旅客拆分、ROADEF 原成本等差异见各输入 rule_mapping。", "",
             "Delft 使用明确标注的静态派生扰动与 12 小时窗口；未声称复现原 370 组。2019 工作簿仅作为发布者结果资料。", "",
             "历史成绩只能关联 native/checker-evidence.json 中通过原规则检查及成本检查的方案。研究目标和 original optimal 标签不能替代这些证据。", "",
             "同日窗口和 ROADEF 同网络变体属于相关样本。当前输出描述统计；没有把重复运行当作独立样本，也未对超时案例删除分母。", "",
             "详细资料：manifest.json、registry.json、runs.csv、summary.json、jobs/<ID>/input.json、evidence.json、events.jsonl、checkpoint.json。", ""]
    (folder / "report.md").write_text("\n".join(text), encoding="utf-8")
    return {k: summary[k] for k in ("status", "jobs_total", "jobs_finished", "verdicts", "certified_optimal", "elapsed_seconds")}
