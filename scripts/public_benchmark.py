"""Public Workbench v3 benchmarks. Run --help for the reproducible workflow."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.benchmarks.common import discover, read_json, write_json, source_ref, utc_now
from backend.benchmarks.model import PublicSolveRequest, build


def inventory(data_root, output):
    from backend.benchmarks.roadef import instance_paths
    import h5py
    roots = discover(data_root)
    manifest = {"schema_version": "public-source-inventory-1.0", "created_at": utc_now(), "datasets": {}}
    kinds = {"ROADEF_2009": "historical_upper_bounds_and_native_checkers",
             "TU_Delft_2019_Results": "publisher_results_without_paired_inputs",
             "TU_Delft_370_Disruptions": "raw_inputs_without_verified_370_partition_or_paired_answers"}
    for name, folder in roots.items():
        files = [source_ref(p, folder, bytes=p.stat().st_size) for p in sorted(folder.rglob("*")) if p.is_file()]
        data = {"answer_kind": kinds[name], "root": str(folder.resolve()), "files": files}
        if name == "ROADEF_2009":
            data["instances"] = [i for i, _ in instance_paths(folder)]
        if name == "TU_Delft_370_Disruptions":
            data["table_rows"] = {}
            for p in (folder / "extracted/data").glob("*.h5"):
                with h5py.File(p) as f:
                    data["table_rows"][p.name] = len(f["csv/table"])
        manifest["datasets"][name] = data
    write_json(output, manifest)
    return {"inventory": str(output), "files": sum(len(d["files"]) for d in manifest["datasets"].values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inventory"); p.add_argument("--data-root"); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("convert"); p.add_argument("dataset", choices=["roadef", "delft"])
    p.add_argument("--data-root"); p.add_argument("--instance", default="A01")
    p.add_argument("--start", default="2015-01-01T06:00:00+00:00"); p.add_argument("--hours", type=int, default=12)
    p.add_argument("--target", type=int, default=12); p.add_argument("--seed", type=int, default=0)
    p.add_argument("--step", type=int, default=30); p.add_argument("--max-delay", type=int, default=120)
    p.add_argument("--model", choices=["aircraft", "aircraft_passenger"], default="aircraft")
    p.add_argument("--connections", action="store_true"); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("precheck"); p.add_argument("input", type=Path)
    p = sub.add_parser("run"); p.add_argument("input", type=Path); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--algorithm", default="air_bp", choices=list(PublicSolveRequest.model_fields["algorithm"].annotation.__args__))
    p.add_argument("--backend", choices=["highs", "gurobi"], default="highs"); p.add_argument("--seconds", type=float, default=120)
    p = sub.add_parser("results2019"); p.add_argument("--data-root"); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("draft"); p.add_argument("input", type=Path); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("external"); p.add_argument("input", type=Path); p.add_argument("--evidence", type=Path)
    p.add_argument("--data-root"); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("prepare"); p.add_argument("--data-root"); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--budget-hours", type=float, default=24); p.add_argument("--profile", choices=["pilot", "full"], default="full")
    p.add_argument("--prior-campaign", type=Path, help="carry consumed total and phase budgets from a finished superseded campaign")
    p = sub.add_parser("campaign"); p.add_argument("folder", type=Path); p.add_argument("--background", action="store_true")
    p = sub.add_parser("report"); p.add_argument("folder", type=Path)
    p = sub.add_parser("analyze"); p.add_argument("folder", type=Path); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("refreeze"); p.add_argument("previous", type=Path); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--reason", required=True)
    p = sub.add_parser("_job"); p.add_argument("folder", type=Path); p.add_argument("job_id")
    args = parser.parse_args()
    if args.command == "inventory":
        result = inventory(args.data_root, args.output)
    elif args.command == "convert":
        roots = discover(args.data_root)
        if args.dataset == "roadef":
            from backend.benchmarks.roadef import load
            raw = load(roots["ROADEF_2009"], args.instance)
        else:
            from backend.benchmarks.delft import load, connection_records
            at = datetime.fromisoformat(args.start)
            if at.tzinfo is None:
                parser.error("--start requires an explicit UTC offset")
            raw = load(roots["TU_Delft_370_Disruptions"], at, args.hours)
            if args.connections:
                raw["raw_tables"]["connections"] = list(connection_records(roots["TU_Delft_370_Disruptions"],
                    [f for f in raw["flights"] if raw["start"] <= f["dep"] < raw["end"]]))
        request = build(raw, target=args.target, seed=args.seed, step=args.step, max_delay=args.max_delay, model_type=args.model)
        write_json(args.output, request)
        result = {"instance": request.instance_id, "problem_sha256": request.problem_sha256, "output": str(args.output)}
    elif args.command in ("precheck", "run", "draft", "external"):
        request = PublicSolveRequest.model_validate(read_json(args.input))
        if args.command == "precheck":
            from backend.benchmarks.solve import precheck
            result = precheck(request)
        elif args.command == "run":
            from backend.benchmarks.solve import execute
            request = request.model_copy(update={"algorithm": args.algorithm, "backend": args.backend})
            args.output.mkdir(parents=True, exist_ok=False)
            write_json(args.output / "input.json", request)
            def event(data):
                from backend.benchmarks.common import clean
                with (args.output / "events.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(clean(data), ensure_ascii=False)+"\n")
            result = execute(request, seconds=args.seconds, event_sink=event,
                             checkpoint_sink=lambda data: write_json(args.output / "checkpoint.json", data))
            write_json(args.output / "evidence.json", result)
            result = {k: v for k, v in result.items() if k in ("status", "objective", "certified_optimal", "gap", "runtime_seconds")}
        elif args.command == "draft":
            from backend.benchmarks.workbench import make_document
            write_json(args.output, make_document(request))
            result = {"draft": str(args.output)}
        else:
            from backend.benchmarks.external import export, check
            export(request, read_json(args.evidence) if args.evidence else None, args.output)
            result = check(discover(args.data_root)["ROADEF_2009"], args.output)
            result = {"passed": result["passed"], "historical_comparison_eligible": result["historical_comparison_eligible"],
                      "violation_files": len(result.get("violations", {})), "missing_reports": result.get("missing_reports", [])}
    elif args.command == "results2019":
        from backend.benchmarks.results2019 import extract
        result = extract(discover(args.data_root)["TU_Delft_2019_Results"], args.output)["counts"]
    elif args.command == "analyze":
        from backend.benchmarks.analysis import analyze
        result = analyze(args.folder, args.output)
    elif args.command == "refreeze":
        from backend.benchmarks.campaign import refreeze
        result = refreeze(args.previous, args.output, reason=args.reason)
    else:
        from backend.benchmarks.campaign import prepare, supervise, report, worker, launch
        if args.command == "prepare":
            result = prepare(args.output, data_root=args.data_root, budget_hours=args.budget_hours, profile=args.profile,
                             prior_campaign=args.prior_campaign)
        elif args.command == "campaign":
            result = launch(args.folder) if args.background else supervise(args.folder)
        elif args.command == "report":
            result = report(args.folder)
        else:
            result = worker(args.folder, args.job_id)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
