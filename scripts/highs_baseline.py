"""Prepare and open user-started serial HiGHS direct baseline groups."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.benchmarks.direct_campaign import prepare, launch, run_group, report, worker, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    for name in ("launch", "verify", "report"):
        p = sub.add_parser(name); p.add_argument("folder", type=Path)
    p = sub.add_parser("run-group"); p.add_argument("folder", type=Path); p.add_argument("group")
    p = sub.add_parser("_job"); p.add_argument("folder", type=Path); p.add_argument("job_id"); p.add_argument("target", type=Path)
    args = parser.parse_args()
    if args.command == "prepare": result = prepare(args.output, args.previous)
    elif args.command == "launch": result = launch(args.folder)
    elif args.command == "run-group": result = run_group(args.folder, args.group)
    elif args.command == "report": result = report(args.folder)
    elif args.command == "verify":
        manifest = verify(args.folder)
        result = dict(verified=True, jobs=len(manifest["jobs"]), manifest_sha256=manifest["manifest_sha256"])
    else: result = worker(args.folder, args.job_id, args.target)
    print(json.dumps(result, ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
