"""Prepare a frozen XMA HiGHS campaign; launch opens a CMD awaiting Enter."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.benchmarks.xma_first_solution import prepare, verify, pilot, launch, run, worker, report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--output',type=Path,required=True);p.add_argument('--calibration',type=Path,required=True)
    p=commands.add_parser('pilot');p.add_argument('--output',type=Path,required=True)
    for name in ('verify','launch','run','report'):
        p=commands.add_parser(name);p.add_argument('folder',type=Path)
        if name in ('launch','run'):
            p.add_argument('--start-now',action='store_true',help='Start immediately under explicit user authorization')
    p=commands.add_parser('_job');p.add_argument('folder',type=Path);p.add_argument('job_id');p.add_argument('target',type=Path);p.add_argument('--seconds',type=float)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.output,args.calibration)
    elif args.command=='pilot':result=pilot(args.output)
    elif args.command=='launch':result=launch(args.folder,start_now=args.start_now)
    elif args.command=='verify':
        m=verify(args.folder);result=dict(verified=True,jobs=len(m['jobs']),manifest_sha256=m['manifest_sha256'])
    elif args.command=='run':result=run(args.folder,start_now=args.start_now)
    elif args.command=='report':result=report(args.folder)
    else:result=worker(args.folder,args.job_id,args.target,args.seconds)
    print(json.dumps(result,ensure_ascii=False,default=str),flush=True)


if __name__=='__main__':main()
