"""Frozen-source, resource-bounded validation campaigns with CMD dashboards."""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
GIB = 1024 ** 3
TERMINAL = {"passed", "failed", "completed", "inconclusive", "input_limit",
            "license_limited", "resource_limited", "timed_out", "cancelled",
            "not_run_budget", "interrupted", "error", "dependency_limited",
            "blocked_by_correctness"}
LANES = [
    ("01-regression", "01 Regression - unit API regression", "既有回归与接口"),
    ("02-air-cases", "02 AIR - expected solutions", "AIR 预期方案与微型案例"),
    ("03-aircraft-cg", "03 AIR - Aircraft column generation", "飞机列生成对拍与耗时"),
    ("04-crew-cg", "04 AIR - Crew column generation", "机组列生成对拍与耗时"),
    ("05-air-oracle", "05 AIR - Benders BP vs integrated", "AIR 联合 Oracle 与 Benders/BP"),
    ("06-stop-conflict", "06 Conflicts - cancellation and limits", "冲突、取消、节点及停止"),
    ("07-xma-oracle", "07 XMA - four algorithms two objectives", "厦航四算法、双目标及不可行"),
    ("08-xma-arc", "08 XMA - joint arc flow", "厦航直接联合：对照与压力"),
    ("09-xma-benders", "09 XMA - Benders joint", "厦航 Benders 联合追索：对照与压力"),
    ("10-xma-cg-bp", "10 XMA - Benders CG BP", "厦航 Benders 列生成分支定价：对照与压力"),
    ("11-air-stress", "11 AIR - P1 P2 P3 P4 P5 stress", "AIR 五档规模压力"),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
        handle.write(value)
        temporary = Path(handle.name)
    try:
        for attempt in range(10):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        raise PermissionError(str(path))
    finally:
        temporary.unlink(missing_ok=True)


def build_jobs(profile="long"):
    scale = {"long": (7200, 24), "default": (1800, 12), "short": (300, 3)}
    heavy, hours = scale[profile]
    jobs = []
    counters = collections.Counter()

    def add(lane, name, kind, config=None, *, wall=300, solver=60,
            memory=1.5, exclusive=False, priority=10, requires=(), blocks=None):
        counters[lane] += 1
        jobs.append({
            "id": f"{lane}-{counters[lane]:03d}", "lane": lane, "name": name,
            "kind": kind, "config": config or {}, "wall_seconds": min(wall, heavy),
            "solver_seconds": min(solver, heavy), "memory_gib": memory,
            "exclusive": exclusive, "priority": priority, "requires": list(requires),
            "blocks": list(requires if blocks is None else blocks),
            "phase": "correctness" if priority < 20 else "performance" if priority < 40 else "stress",
        })

    display_only = {"test_api", "test_workbench_js", "test_visualization_js",
                    "test_workbench_comparison", "test_visualization"}
    for path in sorted((ROOT / "tests").glob("* /test_*.py".replace(" ", ""))):
        if path.parent.name not in ("unit", "api", "regression"):
            continue
        if path.stem == "test_validation_campaign":
            continue  # infrastructure acceptance runs before the scientific campaign
        scopes = ["xma"] if "xma" in path.stem else [] if path.stem in display_only else ["air"]
        add("01-regression", path.relative_to(ROOT).as_posix(), "pytest",
            {"paths": [path.relative_to(ROOT).as_posix()]}, wall=900,
            blocks=scopes)

    catalog = read_json(ROOT / "data/cases/catalog.json")
    for case in catalog["cases"]:
        add("02-air-cases", case["case_id"], "air_case",
            {"case_id": case["case_id"]}, wall=180, requires=("air",))
    manifest = read_json(ROOT / "data/validation_suite/manifest.json")
    for entry in manifest["entries"]:
        if entry.get("source_type") != "artifact":
            continue
        add("02-air-cases", entry["case_id"], "air_micro",
            {"path": "data/validation_suite/" + entry["relative_path"],
             "expected": entry["expected"]}, wall=180)
        jobs[-1].update(requires=["air"], blocks=["air"])
    add("06-stop-conflict", "Capacity/candidates/order metamorphic properties",
        "metamorphic", wall=300, requires=("air", "xma"))

    for owner, lane, toy in (
        ("aircraft", "03-aircraft-cg", "toy_case_011_aircraft_string_column_generation"),
        ("crew", "04-crew-cg", "toy_case_012_crew_pairing_column_generation"),
    ):
        for case in (toy, "phase1_benchmark_001"):
            add(lane, f"{owner}: full LP vs CG / {case}", "air_cg",
                {"owner": owner, "case": case, "repeats": 3, "warmups": 1},
                wall=600, exclusive=True, priority=20, requires=("air",))
    for case_id in ("benchmark-disruption-recovery", "crew-recovery-integrality"):
        add("05-air-oracle", f"Integrated vs Benders BP / {case_id}", "air_oracle",
            {"case_id": case_id, "repeats": 3}, wall=600,
            exclusive=True, priority=21, requires=("air",))
    add("06-stop-conflict", "Immediate cancellation and conflicting XMA instance",
        "stop_controls", wall=180, requires=("air", "xma"))

    for objective in ("tianchi_2017", "air_linear_v1"):
        for variant in ("normal", "delay", "overflow", "split", "branch"):
            add("07-xma-oracle", f"Four algorithms / {objective} / {variant}",
                "xma_micro", {"objective": objective, "variant": variant},
                wall=180, solver=30, requires=("xma",))
    add("07-xma-oracle", "Official JAR fixture revalidation (existing runtime only)", "jar",
        wall=180, requires=("xma",))

    algorithms = ["joint_arc_flow", "benders_joint", "benders_cg_bp"]
    lanes = dict(zip(algorithms, ("08-xma-arc", "09-xma-benders", "10-xma-cg-bp")))
    datasets = [("fixed", 20, None), ("fixed", 100, None),
                ("random", 20, 20261106), ("random", 20, 20261107),
                ("random", 100, 20261106), ("random", 100, 20261107)]
    for index, (mode, target, seed, objective) in enumerate(
        (mode, size, seed, objective) for mode, size, seed in datasets
        for objective in ("tianchi_2017", "air_linear_v1")
    ):
        order = algorithms[index % 3:] + algorithms[:index % 3]
        for rank, algorithm in enumerate(order):
            add(lanes[algorithm], f"Timing / {mode} target={target} seed={seed} / {objective} / {algorithm}",
                "xma_timing", {"mode": mode, "size": target, "seed": seed,
                              "algorithm": algorithm, "objective": objective, "step": 60, "delay": 120},
                wall=600, solver=90, memory=2.5, exclusive=True,
                priority=22 + index + rank / 10, requires=("xma",))

    for index, profile_id in enumerate(
        ["P1-seconds", "P2-tens-seconds", "P3-minutes", "P4-tens-minutes", "P5-hours"]
    ):
        seconds = min(heavy, [60, 180, 600, 1800, 7200][index])
        add("11-air-stress", profile_id, "air_stress",
            {"path": f"data/validation_suite/frozen/stress/{profile_id}.json"},
            wall=seconds, solver=max(1, seconds - 10), memory=[1.5, 1.5, 2.5, 4, 4][index],
            exclusive=True, priority=[40, 41, 44, 48, 52][index], requires=("air",))

    for size in (100, 500, 2364):
        for algorithm in algorithms:
            seconds = min(heavy, {100: 300, 500: 3600, 2364: 7200}[size])
            add(lanes[algorithm], f"Stress / {algorithm} / fixed target={size} / grid60 max120",
                "xma_scale", {"size": size, "mode": "fixed", "step": 60,
                              "delay": 120, "algorithm": algorithm},
                wall=seconds, solver=max(1, seconds - 30),
                memory=2.5 if size == 100 else 4,
                exclusive=True, priority={100: 42, 500: 46, 2364: 54}[size],
                requires=("xma",))
    for size in (100, 500):
        for algorithm in algorithms:
            seconds = min(heavy, 900 if size == 100 else 7200)
            add(lanes[algorithm], f"Stress / {algorithm} / fixed target={size} / grid30 max1440",
                "xma_scale", {"size": size, "mode": "fixed", "step": 30,
                              "delay": 1440, "algorithm": algorithm},
                wall=seconds, solver=max(1, seconds - 30), memory=2.5 if size == 100 else 4,
                exclusive=True, priority=45 if size == 100 else 50, requires=("xma",))
    add("08-xma-arc", "Full 2364 fine grid: candidate readiness and size gate",
        "xma_scale", {"size": 2364, "mode": "fixed", "step": 30,
                      "delay": 1440, "algorithm": "joint_arc_flow", "precheck_only": True,
                      "max_assignments": 100000},
        wall=300, memory=2.5, exclusive=True, priority=49, requires=("xma",))
    return jobs, hours


def deduplicate_cases(jobs):
    """One solve per identical normalized request; retain every reference contract."""
    sys.path.insert(0, str(ROOT))
    from backend.application.case_service import load_case
    from backend.schemas.result import SolveRequest
    seen, kept, aliases = {}, [], []
    for job in jobs:
        if job["kind"] not in ("air_case", "air_micro"):
            kept.append(job)
            continue
        config = job["config"]
        if job["kind"] == "air_case":
            payload = load_case(config["case_id"])
            bundle, expected = payload["solve_bundle"], payload["case"]["expected"]
            if not expected["solve_ready"]:
                kept.append(job)
                continue
        else:
            bundle, expected = read_json(ROOT / config["path"]), config["expected"]
        normalized = SolveRequest.model_validate(bundle).model_dump(mode="json")
        key = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        job["input_hash"] = key
        if key in seen:
            owner = seen[key]
            alias = {"name": job["name"], "owner_job_id": owner["id"], "input_hash": key,
                     "expected": expected, "source": config}
            owner["config"].setdefault("additional_expectations", []).append(expected)
            owner.setdefault("aliases", []).append(job["name"])
            aliases.append(alias)
        else:
            seen[key] = job
            kept.append(job)
    return kept, aliases


def snapshot_sources(destination):
    """Copy source/data, never hardlink live inputs or include the live workbench."""
    destination.mkdir(parents=True)
    ignore = shutil.ignore_patterns("node_modules", "__pycache__", "*.pyc",
                                   ".pytest_cache", "*.tsbuildinfo", "test-results",
                                   "playwright-report")
    for name in ("backend", "data", "schemas", "tests", "scripts", "frontend"):
        shutil.copytree(ROOT / name, destination / name, ignore=ignore)
    for name in ("pyproject.toml", "requirements.txt", "README.md", "assumptions.md",
                 "reproduction_notes.md", "AGENTS.md"):
        shutil.copy2(ROOT / name, destination / name)
    # Some tests/documentation fixtures refer to the non-generated documentation.
    for name in ("models", "benchmarks", "user_guides"):
        source = ROOT / "docs" / name
        if source.is_dir():
            shutil.copytree(source, destination / "docs" / name, ignore=ignore)
    fixture = ROOT / "docs/codex_reports/xma_jar_validation_20261008"
    if fixture.is_dir():
        shutil.copytree(fixture, destination / fixture.relative_to(ROOT), ignore=ignore)
    records = {}
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            records[path.relative_to(destination).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return records


def environment():
    import psutil
    versions = {}
    for package in ("gurobipy", "highspy", "scipy", "numpy", "pytest", "psutil", "pywin32", "openpyxl"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    git = {}
    for label, command in (("commit", ["git", "rev-parse", "HEAD"]),
                           ("status", ["git", "status", "--porcelain=v1"])):
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=10)
            git[label] = result.stdout.decode("utf-8", errors="replace").strip()
        except (OSError, subprocess.SubprocessError):
            git[label] = None
    return {"python": sys.executable, "python_version": sys.version, "git": git,
            "packages": versions, "logical_cpus": psutil.cpu_count(),
            "total_memory": psutil.virtual_memory().total,
            "available_memory_at_launch": psutil.virtual_memory().available}


def write_monitors(folder, manifest):
    monitor_dir = folder / "monitors"
    monitor_dir.mkdir(exist_ok=True)
    for lane, title, _label in [("00-overview", "00 Validation campaign overview", "总览"), *LANES]:
        batch = (
            "@echo off\r\nchcp 65001 >nul\r\n"
            f"title {title} [{folder.name}]\r\n:refresh\r\ncls\r\n"
            f'type "{folder / (lane + ".txt")}"\r\n'
            f'if exist "{folder / (lane + ".done")}" goto finished\r\n'
            "echo.\r\necho Auto-refresh: 300 seconds. Ctrl+C closes this monitor only.\r\n"
            "timeout /t 300 /nobreak >nul\r\ngoto refresh\r\n"
            ":finished\r\necho.\r\necho This lane has finished. Results are preserved.\r\n"
        )
        (monitor_dir / (lane + ".cmd")).write_bytes(batch.encode("utf-8"))
    atomic_json(folder / "monitor_manifest.json",
                {"refresh_seconds": 300, "windows": len(LANES) + 1,
                 "files": [str(p) for p in monitor_dir.glob("*.cmd")]})


def open_monitors(folder):
    pids = []
    for path in sorted((folder / "monitors").glob("*.cmd")):
        child = subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/k", str(path)],
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
        pids.append(child.pid)
        time.sleep(0.15)
    atomic_json(folder / "monitor_pids.json", pids)


def start_supervisor(folder):
    ensure_idle(folder)
    script = folder / "source/scripts/validation_campaign.py"
    log = (folder / "supervisor.log").open("ab", buffering=0)
    child = subprocess.Popen(
        [sys.executable, "-u", str(script), "supervise", "--folder", str(folder)],
        cwd=folder / "source", stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    log.close()
    atomic_json(folder / "supervisor_pid.json", {"pid": child.pid, "started_at": now()})
    return child.pid


def ensure_idle(folder):
    """Check before launch/resume changes state; the supervisor also owns this mutex."""
    import win32api
    import win32event
    manifest = read_json(folder / "manifest.json")
    if not manifest:
        raise SystemExit(f"Missing campaign manifest: {folder}")
    workspace = manifest.get("live_repository", str(folder))
    handle = win32event.CreateMutex(None, False, "Local\\FlightValidation_" + hashlib.sha256(workspace.encode()).hexdigest()[:24])
    busy = win32api.GetLastError() == 183
    win32api.CloseHandle(handle)
    if busy:
        raise SystemExit("A supervisor for this workspace is already alive; use status or monitors.")


HARNESS_FILES = ("scripts/validation_campaign.py", "scripts/validation_jobs.py", "scripts/validation_defer.py",
                 "tests/unit/test_validation_campaign.py", "docs/user_guides/ALGORITHM_VALIDATION_CAMPAIGN.md")


def resource_policy(no_resource_wait=False):
    """Admission policy only; Windows Job memory and wall limits always apply."""
    return {"resource_wait": not no_resource_wait,
            "startup_memory_gib": 0 if no_resource_wait else 6,
            "reserve_memory_gib": 0 if no_resource_wait else 1.5,
            "emergency_available_gib": 0 if no_resource_wait else 1}


def continuation_jobs(manifest, state):
    if state.get("status") != "finished":
        raise ValueError("Continuation requires a finished parent; use resume for an interrupted campaign")
    selected, carried_ids = [], []
    for original in manifest["jobs"]:
        status = state["jobs"][original["id"]]["status"]
        if status in ("passed", "completed"):
            carried_ids.append(original["id"])
        else:
            job = json.loads(json.dumps(original))
            job["previous_status"] = status
            selected.append(job)
    return selected, carried_ids


def snapshot_continuation(parent_folder, parent_manifest, destination):
    """Reuse the exact prior algorithm/data, overlaying the explicitly listed harness files."""
    verify_source(parent_folder, parent_manifest)
    original = Path(parent_manifest["source_root"])
    destination.mkdir(parents=True)
    for relative in parent_manifest["source_hashes"]:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original / relative, target)
    for relative in HARNESS_FILES:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(destination.rglob("*")) if p.is_file()}


def full_replay_jobs(items):
    """Repair replay includes completed-but-unconverged work and inherited jobs."""
    jobs=[]
    seen=set()
    for item in items:
        job=json.loads(json.dumps(item["job"]))
        if job["id"] in seen:
            raise ValueError("Duplicate baseline job: "+job["id"])
        seen.add(job["id"])
        job["baseline_status"]=item["status"]
        jobs.append(job)
    return jobs


def prepare(args):
    if sys.platform != "win32":
        raise SystemExit("The visible CMD dashboards and memory guards require Windows.")
    import win32job  # noqa: F401
    parent_folder = getattr(args, "continue_from", None)
    repair_folder = getattr(args, "repair_from", None)
    if parent_folder and repair_folder:
        raise ValueError("--repair-from and --continue-from are mutually exclusive")
    parent_manifest, carried = None, []
    baseline_items=[]
    if repair_folder:
        from scripts.validation_watch import collect
        repair_folder=Path(repair_folder).resolve()
        ensure_idle(repair_folder)
        parent_manifest=read_json(repair_folder/"manifest.json")
        baseline_state=read_json(repair_folder/"state.json")
        if baseline_state.get("status")!="finished":
            raise ValueError("Repair replay requires a finished baseline")
        baseline_items=collect(repair_folder,parent_manifest,baseline_state)
        jobs=full_replay_jobs(baseline_items)
        hours={"long":24,"default":12,"short":3}[args.profile]
        aliases=parent_manifest.get("deduplicated_aliases",[])
        for relative,expected in parent_manifest["source_hashes"].items():
            if relative.startswith(("data/","schemas/","docs/codex_reports/xma_jar_validation_")):
                path=ROOT/relative
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                    raise ValueError("Baseline input changed; use an explicitly separate experiment: "+relative)
        tested={path for job in jobs if job["kind"]=="pytest" for path in job["config"]["paths"]}
        for path in sorted((ROOT/"tests").glob("*/test_*.py")):
            relative=path.relative_to(ROOT).as_posix()
            if path.parent.name not in ("unit","api","regression") or relative in tested or path.stem=="test_validation_campaign":
                continue
            jobs.append({"id":f"01-regression-repair-{len(jobs)+1:03d}","lane":"01-regression","name":relative,
                         "kind":"pytest","config":{"paths":[relative]},"wall_seconds":900,"solver_seconds":60,
                         "memory_gib":1.5,"exclusive":False,"priority":10,"requires":[],"blocks":["air","xma"],"phase":"correctness"})
    elif parent_folder:
        parent_folder = Path(parent_folder).resolve()
        ensure_idle(parent_folder)
        parent_manifest = read_json(parent_folder / "manifest.json")
        jobs, carried_ids = continuation_jobs(parent_manifest, read_json(parent_folder / "state.json"))
        hours = {"long": 24, "default": 12, "short": 3}[args.profile]
        aliases = parent_manifest.get("deduplicated_aliases", [])
        carried = list(parent_manifest.get("carried_forward_results", []))
        for ident in carried_ids:
            path = parent_folder / "jobs" / ident / "result.json"
            result = read_json(path)
            if not result:
                raise ValueError(f"Cannot carry forward missing evidence: {ident}")
            carried.append({"id": ident, "verdict": result["verdict"], "path": str(path),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    else:
        jobs, hours = build_jobs(args.profile)
        jobs, aliases = deduplicate_cases(jobs)
    java = getattr(args, "java_executable", None)
    if java:
        java = Path(java).resolve()
        if not java.is_file():
            raise ValueError(f"Java executable does not exist: {java}")
        for job in jobs:
            if job["kind"] == "jar":
                job["config"]["java_executable"] = str(java)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "_repair" if repair_folder else "_continue" if parent_folder else ""
    folder = (args.folder or ROOT / ".workbench/validation_campaigns" / (stamp + suffix)).resolve()
    if folder.exists():
        raise SystemExit(f"Refusing to replace an existing campaign: {folder}")
    folder.mkdir(parents=True)
    hashes = (snapshot_continuation(parent_folder, parent_manifest, folder / "source") if parent_folder
              else snapshot_sources(folder / "source"))
    live_root = parent_manifest.get("live_repository", str(ROOT)) if parent_manifest else str(ROOT)
    policy = resource_policy(getattr(args, "no_resource_wait", False))
    manifest = {"schema_version": "1.3", "created_at": now(), "profile": args.profile,
                "campaign_hours": hours, "max_parallel": 2, **policy,
                "source_root": str(folder / "source"),
                "live_repository": live_root, "source_hashes": hashes,
                "temporary_root": str(Path(live_root) / ".workbench/vtmp"),
                "environment": environment(), "lanes": LANES, "jobs": jobs,
                "deduplicated_aliases": aliases,
                "validation_suite_coverage": read_json(ROOT / "data/validation_suite/manifest.json"),
                "seeds": [20261106, 20261107],
                "candidate_grids": {"coarse": [60, 120], "fine": [30, 1440], "oracle_path_limit": 100000},
                "performance_rule": "exclusive; one solver thread; paired identical inputs; 3 repetitions",
                "stop_rule": ("campaign budget starts immediately; no system-memory admission or emergency floor; "
                              "STOP file; strict wall/commit-memory guards" if not policy["resource_wait"] else
                              "campaign budget starts after 6GiB startup gate; STOP file; strict wall/commit-memory guards")}
    if parent_folder:
        manifest.update(continuation_of=str(parent_folder), carried_forward_results=carried,
                        parent_manifest_sha256=hashlib.sha256((parent_folder / "manifest.json").read_bytes()).hexdigest(),
                        harness_overlay=list(HARNESS_FILES),
                        provenance="Same frozen algorithm/data; new campaign budget, parent evidence preserved")
    if repair_folder:
        manifest.update(repair_of=str(repair_folder), carried_forward_results=[],
                        baseline_manifest_sha256=hashlib.sha256((repair_folder/"manifest.json").read_bytes()).hexdigest(),
                        baseline_results=[{"id":i["job"]["id"],"status":i["status"],"path":i["result_path"],
                                           "sha256":i["result_sha256"]} for i in baseline_items],
                        changed_sources=[p for p,h in hashes.items() if parent_manifest["source_hashes"].get(p)!=h],
                        provenance="Full repair replay; fresh frozen implementation, unchanged baseline inputs and budgets; no results carried forward")
    atomic_json(folder / "manifest.json", manifest)
    atomic_json(folder / "manifest.sha256.json", {
        "sha256": hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()})
    initial = {j["id"]: {"status": "pending", "name": j["name"], "lane": j["lane"]} for j in jobs}
    atomic_json(folder / "state.json", {"status": "prepared", "jobs": initial, "updated_at": now()})
    for lane, title, label in [("00-overview", "Overview", "总览"), *LANES]:
        atomic_text(folder / (lane + ".txt"),
                    f"{title}\n{label}\nCampaign: {folder}\nPreparing scheduler; refresh every 5 minutes.\n")
    write_monitors(folder, manifest)
    return folder, manifest


def launch(args):
    if args.folder and (args.folder / "manifest.json").is_file():
        folder = args.folder.resolve()
        manifest = read_json(folder / "manifest.json")
    else:
        folder, manifest = prepare(args)
    if args.prepare_only:
        print(json.dumps({"folder": str(folder), "jobs": len(manifest["jobs"]), "status": "prepared"}, ensure_ascii=False))
        return
    pid = start_supervisor(folder)
    ready_by = time.monotonic() + 15
    while time.monotonic() < ready_by:
        state = read_json(folder / "state.json", {})
        if state.get("supervisor_pid") == pid or state.get("status") == "interrupted":
            break
        time.sleep(0.1)
    if not args.no_windows:
        open_monitors(folder)
    print(json.dumps({"folder": str(folder), "jobs": len(manifest["jobs"]), "supervisor_pid": pid,
                      "monitor_windows": 0 if args.no_windows else len(LANES) + 1,
                      "campaign_hours": manifest["campaign_hours"],
                      "status": read_json(folder / "state.json", {}).get("status")}, ensure_ascii=False))


def process_memory(process):
    import psutil
    rss = 0
    try:
        for proc in [psutil.Process(process.pid), *psutil.Process(process.pid).children(recursive=True)]:
            try:
                rss += proc.memory_info().rss
            except psutil.Error:
                pass
    except psutil.Error:
        pass
    return rss


class GuardedChild:
    """Assign the suspended process to a bounded Windows job BEFORE it executes."""
    def __init__(self, command, *, cwd, env, log, memory_gib):
        import msvcrt
        import win32api
        import win32job
        import win32process
        self.pid = None
        self.returncode = None
        self.process_handle = None
        self.guard = win32job.CreateJobObject(None, "")
        limits = win32job.QueryInformationJobObject(self.guard, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] = (
            win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY)
        limits["JobMemoryLimit"] = int(memory_gib * GIB)
        win32job.SetInformationJobObject(self.guard, win32job.JobObjectExtendedLimitInformation, limits)
        null = open(os.devnull, "rb")
        output_handle = msvcrt.get_osfhandle(log.fileno())
        input_handle = msvcrt.get_osfhandle(null.fileno())
        os.set_handle_inheritable(output_handle, True)
        os.set_handle_inheritable(input_handle, True)
        thread_handle = None
        try:
            startup = win32process.STARTUPINFO()
            startup.dwFlags |= 0x100  # STARTF_USESTDHANDLES
            startup.hStdOutput = startup.hStdError = output_handle
            startup.hStdInput = input_handle
            process, thread_handle, pid, _tid = win32process.CreateProcess(
                None, subprocess.list2cmdline([str(x) for x in command]), None, None, True,
                0x08000000 | 0x00000004 | 0x00000400, env, str(cwd), startup)
            self.process_handle, self.pid = process, pid
            win32job.AssignProcessToJobObject(self.guard, process)
            win32process.ResumeThread(thread_handle)
        except Exception:
            if self.process_handle is not None:
                win32api.TerminateProcess(self.process_handle, 143)
            self.close()
            raise
        finally:
            if thread_handle is not None:
                win32api.CloseHandle(thread_handle)
            os.set_handle_inheritable(output_handle, False)
            os.set_handle_inheritable(input_handle, False)
            null.close()

    def poll(self):
        import win32process
        if self.returncode is None:
            code = win32process.GetExitCodeProcess(self.process_handle)
            if code != 259:
                self.returncode = code
        return self.returncode

    def wait(self, timeout=15):
        import win32event
        if win32event.WaitForSingleObject(self.process_handle, int(timeout * 1000)) == 258:
            raise TimeoutError(f"PID {self.pid} did not exit")
        return self.poll()

    def kill(self):
        import win32job
        win32job.TerminateJobObject(self.guard, 143)
        return self.wait()

    def peak_commit(self):
        import win32job
        return win32job.QueryInformationJobObject(
            self.guard, win32job.JobObjectExtendedLimitInformation).get("PeakJobMemoryUsed", 0)

    def close(self):
        import win32api
        for name in ("guard", "process_handle"):
            handle = getattr(self, name, None)
            if handle is not None:
                win32api.CloseHandle(handle)
                setattr(self, name, None)


def stop_process(active):
    active["process"].kill()


def finish_process(job, active, states, folder, override=None):
    result_path = active["folder"] / "result.json"
    result = read_json(result_path, {})
    status = override or result.get("verdict")
    code = active["process"].returncode
    if not status:
        status = "resource_limited" if code in (3221225495, -1073741801) or (
            active["process"].peak_commit() >= job["memory_gib"] * GIB * 0.98) else "error"
        result = {"verdict": status, "reason": "worker exited without a complete result",
                  "returncode": code}
    result.update(supervisor_wall_seconds=time.monotonic() - active["started"],
                  process_tree_peak_rss_bytes=active["peak_rss"], returncode=code,
                  process_tree_peak_commit_bytes=active["process"].peak_commit(),
                  attempt_folder=str(active["folder"]))
    if override:
        result.update(verdict=override, reason=active.get("stop_reason", override),
                      partial_progress=read_json(result_path.parent / "progress.json", {}))
    atomic_json(result_path, result)
    atomic_json(folder / "jobs" / job["id"] / "result.json", result)
    states[job["id"]].update(status=status, finished_at=now(), result=str(result_path),
                            wall_seconds=result["supervisor_wall_seconds"],
                            peak_rss_bytes=active["peak_rss"],
                            summary=result.get("summary", result.get("reason", "")),
                            blocked_scopes=result.get("blocked_scopes", []))
    active["log"].close()
    active["process"].close()


def dashboard(folder, manifest, states, active, available, status):
    counts = collections.Counter(x["status"] for x in states.values())
    clock = read_json(folder / "state.json", {})
    elapsed = (time.time() - clock["started_epoch"]) if clock.get("started_epoch") else 0
    header = [
        "FLIGHT RECOVERY - UNATTENDED VALIDATION",
        "更新时间: " + datetime.now().astimezone().isoformat(timespec="seconds"),
        f"总状态: {status} | 总任务 {len(states)} | 运行 {len(active)} | 待运行 {counts['pending']}",
        "状态计数: " + json.dumps(dict(counts), ensure_ascii=False),
        f"可用物理内存 {available / GIB:.2f} GiB | 最大并行 2 | 性能实验独占",
        f"整批 {manifest['campaign_hours']} 小时 / 重型单例最多 2 小时 / 一线程 / 每 300 秒刷新",
        f"整批已用 {elapsed / 3600:.2f} 小时 | 原始截止 epoch {clock.get('deadline_epoch')}",
        (f"启动门槛: {manifest.get('startup_memory_gib', 6)} GiB；waiting_for_memory 时尚未开始整批计时"
         if manifest.get("resource_wait", True) else
         "按用户要求不等待系统可用内存，不启用低内存停测；单例墙钟和进程树内存上限仍有效"),
        "若更新时间持续不变，请查看 supervisor_error.txt；可显式 resume",
        "终止本批: 在本目录建立 STOP 文件；关闭监控窗不会终止计算",
        "结果目录: " + str(folder), "",
    ]
    if manifest.get("continuation_of"):
        header.extend([f"续测: 上轮已完成并保留证据 {len(manifest['carried_forward_results'])} 项；本轮 {len(states)} 项",
                       "上轮: " + manifest["continuation_of"], ""])
    lines = []
    for job in manifest["jobs"]:
        state = states[job["id"]]
        line = f"[{state['status']}] {job['id']} | {job['name']}"
        if job["id"] in active:
            entry = active[job["id"]]
            elapsed = time.monotonic() - entry["started"]
            progress = read_json(entry["folder"] / "progress.json", {})
            detail = (f"  用时 {elapsed:.0f}/{job['wall_seconds']}s | PID {entry['process'].pid}"
                      f" | RSS {process_memory(entry['process']) / GIB:.2f} GiB"
                      f" | sampled peak RSS {entry['peak_rss'] / GIB:.2f} GiB"
                      f" | peak commit {entry['process'].peak_commit() / GIB:.2f}/{job['memory_gib']} GiB")
            line += "\n" + detail + "\n  " + json.dumps(progress, ensure_ascii=False)
        elif state.get("reason"):
            line += "\n  " + state["reason"]
        elif state.get("summary"):
            line += "\n  " + str(state["summary"])[:500]
        config = job.get("config", {})
        line += "\n  配置: " + json.dumps(config, ensure_ascii=False)
        lines.append((job["lane"], line))
    overview = []
    for lane, title, label in manifest["lanes"]:
        values = [states[j["id"]] for j in manifest["jobs"] if j["lane"] == lane]
        overview.append(title + " / " + label + " | " + json.dumps(dict(collections.Counter(s["status"] for s in values))))
    atomic_text(folder / "00-overview.txt", "\n".join(header + overview + ["", "ACTIVE TASKS:"] +
                [line for lane, line in lines if line.startswith("[running]")]) + "\n")
    for lane, title, label in manifest["lanes"]:
        lane_jobs = [j for j in manifest["jobs"] if j["lane"] == lane]
        counts = collections.Counter(states[j["id"]]["status"] for j in lane_jobs)
        current = [line for key, line in lines if key == lane and line.startswith("[running]")]
        pending = [line for key, line in lines if key == lane and line.startswith("[pending]")]
        done = [line for key, line in lines if key == lane and not line.startswith(("[pending]", "[running]"))]
        atomic_text(folder / (lane + ".txt"),
                    "\n".join([title + " / " + label, *header, "本窗口状态: " + json.dumps(dict(counts)),
                               "CURRENT:", *current, "NEXT (first 3):", *pending[:3],
                               "RECENT RESULTS (last 3):", *done[-3:]]) + "\n")
        if all(states[j["id"]]["status"] in TERMINAL for j in lane_jobs):
            (folder / (lane + ".done")).touch()


def summarize(folder, manifest, states, status):
    results = []
    for job in manifest["jobs"]:
        state = states[job["id"]]
        result = read_json(folder / "jobs" / job["id"] / "result.json", {})
        results.append({"job": job, "state": state, "result": result})
    atomic_json(folder / "summary.json", {"status": status, "generated_at": now(), "items": results,
                                         "continuation_of": manifest.get("continuation_of"),
                                         "carried_forward_results": manifest.get("carried_forward_results", [])})
    rows = ["# 自动验证执行汇总", "", "本文件为任务执行汇总；科学结论仍需结合 Oracle、审计、可比性及原始日志复核。", "",
            "| 测试 | 状态 | 耗时秒 | 结果 |", "|---|---|---:|---|"]
    if manifest.get("continuation_of"):
        rows[2:2] = [f"续测来源：`{manifest['continuation_of']}`；另保留 {len(manifest['carried_forward_results'])} 项历史完成证据。", ""]
    for item in results:
        state, result, job = item["state"], item["result"], item["job"]
        text = str(result.get("summary", result.get("reason", ""))).replace("|", "/").replace("\n", " ")[:350]
        rows.append(f"| {job['id']} {job['name']} | {state['status']} | {state.get('wall_seconds', 0):.1f} | {text} |")
    atomic_text(folder / "SUMMARY.md", "\n".join(rows) + "\n")
    comparisons = collections.defaultdict(list)
    for item in results:
        if item["job"]["kind"] != "xma_timing":
            continue
        for record in item["result"].get("records", []):
            if record.get("comparison_key") and record.get("repetition", -1) >= 0:
                comparisons[record["comparison_key"]].append(record)
    comparison_rows = []
    import statistics
    for key, records in comparisons.items():
        by_method = collections.defaultdict(list)
        for record in records:
            by_method[record["method"]].append(record)
        objectives = [r["objective"] for r in records if r.get("optimization_status") == "optimal"]
        quality_agrees = bool(objectives) and all(
            abs(x - objectives[0]) <= max(1e-6, abs(objectives[0]) * 1e-8) for x in objectives)
        eligible = {method: values for method, values in by_method.items()
                    if len(values) == 3 and all(v.get("optimization_status") == "optimal" and v.get("audit_valid") for v in values)}
        comparison_rows.append({
            "comparison_key": key, "observed_methods": sorted(by_method),
            "certified_objectives_agree": quality_agrees,
            "all_methods_have_3_certified_runs": len(eligible) == 3 and quality_agrees,
            "methods": {method: {"observed_statuses": [r["optimization_status"] for r in values],
                         "times": [r["seconds"] for r in values],
                         "median_seconds": statistics.median(r["seconds"] for r in values),
                         "range_seconds": [min(r["seconds"] for r in values), max(r["seconds"] for r in values)]}
                        for method, values in by_method.items()},
            "speedups_vs_direct": {
                method: statistics.median(x["seconds"] for x in eligible["joint_arc_flow"]) /
                        statistics.median(x["seconds"] for x in values)
                for method, values in eligible.items() if method != "joint_arc_flow"
                and "joint_arc_flow" in eligible and quality_agrees},
            "note": "Only identical problem key, 3 optimal audited results, and equal objectives admit a speedup."
        })
    atomic_json(folder / "performance_comparisons.json", comparison_rows)
    import xml.etree.ElementTree as ET
    suite = ET.Element("testsuite", name="validation_campaign", tests=str(len(results)))
    for item in results:
        state, result, job = item["state"], item["result"], item["job"]
        case = ET.SubElement(suite, "testcase", classname=job["lane"], name=job["name"],
                             time=str(state.get("wall_seconds", 0)))
        if state["status"] in ("failed", "error"):
            ET.SubElement(case, "failure", message=result.get("summary", state["status"])).text = json.dumps(result, ensure_ascii=False)
        elif state["status"] not in ("passed", "completed"):
            ET.SubElement(case, "skipped", message=state["status"])
    ET.ElementTree(suite).write(folder / "campaign.junit.xml", encoding="utf-8", xml_declaration=True)
    import csv
    with (folder / "summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["job_id", "lane", "name", "status", "wall_seconds", "peak_rss_bytes", "summary"])
        for item in results:
            j, s, r = item["job"], item["state"], item["result"]
            writer.writerow([j["id"], j["lane"], j["name"], s["status"], s.get("wall_seconds"),
                             s.get("peak_rss_bytes"), r.get("summary", r.get("reason", ""))])


def choose_job(jobs, states, active, available, reserve, *, resource_wait=True):
    """One admission decision; reserve unused limits of already running workers."""
    if len(active) >= 2:
        return None
    index = {j["id"]: j for j in jobs}
    if any(index[key]["exclusive"] for key in active):
        return None
    pending = sorted((j for j in jobs if states[j["id"]]["status"] == "pending"),
                     key=lambda j: (j["priority"], j["id"]))
    phases = {"correctness": 0, "performance": 1, "stress": 2}
    unfinished = [index[key] for key, state in states.items()
                  if state["status"] in ("pending", "running")]
    if not unfinished:
        return None
    phase = min(phases[j["phase"]] for j in unfinished)
    unspent = sum(max(0, index[key]["memory_gib"] * GIB - entry.get("rss", 0))
                  for key, entry in active.items())
    for job in pending:
        if phases[job["phase"]] != phase:
            continue
        if job["exclusive"] and active:
            return None
        if any(index[key]["lane"] == job["lane"] for key in active):
            continue
        if resource_wait and available - unspent < (job["memory_gib"] + reserve) * GIB:
            continue
        return job
    return None


def verify_source(folder, manifest):
    inventory = read_json(folder / "manifest.sha256.json")
    if inventory and hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest() != inventory["sha256"]:
        raise ValueError("Frozen task manifest changed; prepare a new campaign")
    root = Path(manifest["source_root"]).resolve()
    for relative, expected in manifest.get("source_hashes", {}).items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Invalid source inventory path")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen source changed: {relative}; prepare a new campaign")
    for entry in manifest.get("carried_forward_results", []):
        path = Path(entry["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Carried-forward result changed: {entry['id']}")


def spawn_job(folder, manifest, job, state):
    target = folder / "jobs" / job["id"] / f"attempt_{state.get('attempt', 0) + 1:03d}"
    target.mkdir(parents=True, exist_ok=True)
    atomic_json(target / "job.json", job)
    log = (target / "worker.log").open("ab", buffering=0)
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONHASHSEED="0")
    if manifest.get("temporary_root"):
        env["FLIGHT_VALIDATION_TEMP_ROOT"] = manifest["temporary_root"]
    source = Path(manifest["source_root"])
    command = [sys.executable, "-u", str(source / "scripts/validation_jobs.py"),
               "--job", str(target / "job.json"), "--output", str(target)]
    started = time.monotonic()
    try:
        proc = GuardedChild(command, cwd=source, env=env, log=log, memory_gib=job["memory_gib"])
    except Exception:
        log.close()
        raise
    state.update(status="running", pid=proc.pid, started_at=now(), reason="",
                 attempt=state.get("attempt", 0) + 1, attempt_folder=str(target))
    return {"process": proc, "started": started, "peak_rss": 0,
            "rss": 0, "log": log, "folder": target}


def supervise(args):
    import psutil
    import win32api
    import win32event
    folder = args.folder.resolve()
    manifest = read_json(folder / "manifest.json")
    workspace = manifest.get("live_repository", str(folder))
    mutex = win32event.CreateMutex(None, False, "Local\\FlightValidation_" + hashlib.sha256(workspace.encode()).hexdigest()[:24])
    if win32api.GetLastError() == 183:
        raise SystemExit("This campaign already has a supervisor.")
    state = read_json(folder / "state.json")
    states = state["jobs"]
    for entry in states.values():
        if entry["status"] == "running":
            entry.update(status="interrupted", reason="previous supervisor ended")
    started_epoch = state.get("started_epoch")
    deadline = started_epoch + manifest["campaign_hours"] * 3600 if started_epoch else None
    active = {}
    stopping = False
    final_status = "running"
    index = {j["id"]: j for j in manifest["jobs"]}
    low_memory_since = None
    resource_wait = manifest.get("resource_wait", True)
    try:
        verify_source(folder, manifest)
        while True:
            available = psutil.virtual_memory().available
            stop_reason = ("user_stop" if (folder / "STOP").exists() else
                           "campaign_budget" if deadline is not None and time.time() >= deadline else None)
            if stop_reason:
                stopping = True
                for job in manifest["jobs"]:
                    entry = states[job["id"]]
                    if entry["status"] == "pending":
                        entry.update(status="cancelled" if stop_reason == "user_stop" else "not_run_budget",
                                     reason=stop_reason, finished_at=now())
            if started_epoch is None and not stopping:
                if not resource_wait or available >= manifest.get("startup_memory_gib", 6) * GIB:
                    started_epoch = time.time()
                    deadline = started_epoch + manifest["campaign_hours"] * 3600
                else:
                    final_status = "waiting_for_memory"
            if resource_wait and available < manifest["emergency_available_gib"] * GIB and active:
                low_memory_since = low_memory_since or time.monotonic()
            else:
                low_memory_since = None
            emergency_job = None
            if low_memory_since and time.monotonic() - low_memory_since >= 10:
                emergency_job = max(active, key=lambda key: active[key]["rss"])
            for job in manifest["jobs"]:
                entry = active.get(job["id"])
                if entry is None:
                    continue
                proc = entry["process"]
                entry["rss"] = process_memory(proc)
                entry["peak_rss"] = max(entry["peak_rss"], entry["rss"])
                override = None
                job_stop_reason = None
                if proc.poll() is None:
                    if stopping:
                        override = "cancelled" if stop_reason == "user_stop" else "timed_out"
                        job_stop_reason = stop_reason
                    elif time.monotonic() - entry["started"] >= job["wall_seconds"]:
                        override = "timed_out"
                        job_stop_reason = "strict wall limit, including build and serialization"
                    elif job["id"] == emergency_job:
                        override = "resource_limited"
                        job_stop_reason = "system available memory below emergency floor for 10 seconds"
                    if override:
                        entry["stop_reason"] = job_stop_reason
                        stop_process(entry)
                if proc.poll() is not None:
                    finish_process(job, entry, states, folder, override)
                    del active[job["id"]]
            blocked = {scope for item in states.values() if item["status"] == "failed"
                       for scope in item.get("blocked_scopes", [])}
            for job in manifest["jobs"]:
                entry = states[job["id"]]
                if entry["status"] == "pending" and job["phase"] != "correctness" and blocked.intersection(job.get("requires", [])):
                    entry.update(status="blocked_by_correctness", reason="Failed prerequisite scopes: " +
                                 ", ".join(sorted(blocked.intersection(job["requires"]))), finished_at=now())
            if not stopping and started_epoch is not None:
                while True:
                    job = choose_job(manifest["jobs"], states, active, available, manifest["reserve_memory_gib"],
                                     resource_wait=resource_wait)
                    if job is None:
                        break
                    try:
                        active[job["id"]] = spawn_job(folder, manifest, job, states[job["id"]])
                    except Exception as exc:
                        failure_status = ("resource_limited" if isinstance(exc, MemoryError) or
                                          getattr(exc, "winerror", None) in (8, 14, 1450, 1455) else "error")
                        previous = states[job["id"]]
                        target = folder / "jobs" / job["id"] / f"attempt_{previous.get('attempt', 0) + 1:03d}"
                        failure = {"verdict": failure_status, "reason": traceback.format_exc(), "phase": "worker_spawn"}
                        atomic_json(target / "result.json", failure)
                        atomic_json(folder / "jobs" / job["id"] / "result.json", failure)
                        previous.update(status=failure_status, reason=failure["reason"], finished_at=now(),
                                        attempt=previous.get("attempt", 0) + 1, attempt_folder=str(target))
                    available = psutil.virtual_memory().available
            final_status = ("finished" if all(x["status"] in TERMINAL for x in states.values()) else
                            "waiting_for_memory" if started_epoch is None else "running")
            for entry in states.values():
                if entry["status"] == "pending":
                    entry["reason"] = (f"WAIT_STARTUP_MEMORY: need {manifest.get('startup_memory_gib', 6)} GiB; clock not started"
                                       if started_epoch is None else
                                       "QUEUED: correctness prerequisites, exclusive timing slot, or reserved memory"
                                       if resource_wait else
                                       "QUEUED: correctness prerequisites or exclusive timing slot; no system-memory wait")
            state = {"status": final_status, "started_epoch": started_epoch, "deadline_epoch": deadline,
                     "updated_at": now(), "supervisor_pid": os.getpid(), "jobs": states}
            atomic_json(folder / "state.json", state)
            dashboard(folder, manifest, states, active, available, final_status)
            if final_status == "finished":
                break
            time.sleep(1)
    except BaseException:
        final_status = "interrupted"
        atomic_text(folder / "supervisor_error.txt", traceback.format_exc())
        for job_id, entry in active.items():
            if entry["process"].poll() is None:
                stop_process(entry)
            entry["stop_reason"] = "supervisor exception"
            finish_process(index[job_id], entry, states, folder, "interrupted")
        atomic_json(folder / "state.json", {"status": "interrupted", "jobs": states, "updated_at": now(),
                                           "started_epoch": started_epoch, "deadline_epoch": deadline})
        dashboard(folder, manifest, states, {}, psutil.virtual_memory().available, "interrupted")
        raise
    finally:
        summarize(folder, manifest, states, final_status)
        if final_status == "finished":
            (folder / "00-overview.done").touch()
        win32api.CloseHandle(mutex)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "launch", "supervise", "monitors", "status", "stop", "resume", "defer"])
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--profile", choices=["short", "default", "long"], default="long")
    parser.add_argument("--continue-from", type=Path, help="New batch for unfinished/failed work, reusing frozen algorithm/data")
    parser.add_argument("--repair-from", type=Path, help="Full replay of all unique baseline jobs with current repaired source; never carry forward results")
    parser.add_argument("--java-executable", type=Path, help="Use an existing local Java runtime without installing one")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--no-windows", action="store_true")
    parser.add_argument("--no-resource-wait", action="store_true",
                        help="New batches: skip available-memory waiting and emergency floor; retain per-job hard limits")
    args = parser.parse_args()
    if args.action == "prepare":
        args.prepare_only = True
        launch(args)
    elif args.action == "launch":
        launch(args)
    elif not args.folder:
        parser.error("--folder is required")
    elif args.action == "supervise":
        supervise(args)
    elif args.action == "monitors":
        open_monitors(args.folder.resolve())
    elif args.action == "stop":
        (args.folder / "STOP").touch()
        print("Stop requested; the supervisor will stop workers and preserve evidence.")
    elif args.action == "defer":
        from validation_defer import start
        pid = start(args.folder)
        print(f"Defer controller PID: {pid}; current workers remain protected until completion." if pid else
              "Campaign already finished; existing defer evidence is unchanged.")
    elif args.action == "resume":
        ensure_idle(args.folder.resolve())
        state = read_json(args.folder / "state.json")
        for entry in state["jobs"].values():
            if entry["status"] in ("running", "interrupted", "cancelled"):
                if entry.get("attempt_folder"):
                    previous = Path(entry["attempt_folder"]) / "result.json"
                    if not previous.exists():
                        atomic_json(previous, {"verdict": "interrupted", "reason": "Previous supervisor ended; explicit resume",
                                               "last_persisted_state": entry.copy(), "recorded_at": now()})
                entry.update(status="pending", reason="explicitly resumed")
        atomic_json(args.folder / "state.json", state)
        for path in args.folder.glob("*.done"):
            path.unlink()
        for name in ("STOP", "supervisor_error.txt"):
            path = args.folder / name
            if path.exists():
                if name.endswith(".txt"):
                    shutil.copy2(path, path.with_name(f"previous_supervisor_error_{time.time_ns()}.txt"))
                path.unlink()
        print(start_supervisor(args.folder.resolve()))
    else:
        print((args.folder / "00-overview.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
