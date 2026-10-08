"""Reproducible, candidate-scoped XMA experiments; original workbook is untouched."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from threading import Event, Thread
from time import perf_counter
from datetime import datetime

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.business.xma.importer import load_workbook, select_subset
from backend.business.xma.schema import XmaSolveRequest
from backend.business.xma.service import precheck, solve


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sizes',default='20,100,500,2364')
    parser.add_argument('--algorithms',default='joint_arc_flow,benders_joint,benders_cg_bp')
    parser.add_argument('--seconds',type=float,default=30)
    parser.add_argument('--step',type=int,default=60)
    parser.add_argument('--delay',type=int,default=120)
    parser.add_argument('--objective',default='tianchi_2017')
    parser.add_argument('--max-assignments',type=int,default=100000)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    folder=args.output or Path('docs/codex_reports')/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_xma_experiments')
    folder.mkdir(parents=True,exist_ok=True)
    data=load_workbook()
    rows=[]
    for size in map(int,args.sizes.split(',')):
        for algorithm in args.algorithms.split(','):
            request=XmaSolveRequest(dataset=select_subset(data,size),algorithm=algorithm,time_limit_seconds=args.seconds,
                delay_step_minutes=args.step,maximum_delay_minutes=args.delay,objective_profile=args.objective,
                max_assignment_options=args.max_assignments)
            readiness=precheck(request)
            row={'requested_flights':size,'flights':len(request.dataset.flights),'tails':len(request.dataset.aircraft),
                'algorithm':algorithm,'objective_profile':args.objective,'step_minutes':args.step,'max_delay_minutes':args.delay,
                'source_sha256':data.source_sha256,'readiness':readiness}
            key=f'{size}_{algorithm}'
            (folder/(key+'_input.json')).write_text(request.model_dump_json(),encoding='utf-8')
            peak=[None]
            stop=Event()
            def sample():
                try:
                    import psutil
                    process=psutil.Process(os.getpid())
                    while not stop.wait(0.05):
                        rss=process.memory_info().rss
                        peak[0]=max(peak[0] or 0,rss)
                except ImportError:
                    pass
            monitor=Thread(target=sample,daemon=True); monitor.start()
            started=perf_counter()
            try:
                if readiness['solve_ready']:
                    result=solve(request)
                    row.update(status=result['status'],objective=result['objective'],diagnostics=result['diagnostics'],
                        valid=(result['independent_audit'] or {}).get('valid'))
                    (folder/(key+'_result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                    if result.get('tianchi_csv'):
                        (folder/(key+'_result.csv')).write_text(result['tianchi_csv'],encoding='utf-8')
                else:
                    row['status']='input_limit'
            except Exception as exc:
                row.update(status='error',error=f'{type(exc).__name__}: {exc}')
            finally:
                stop.set(); monitor.join()
                row.update(wall_seconds=perf_counter()-started,process_peak_rss_bytes=peak[0])
            rows.append(row)
            (folder/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:row.get(k) for k in ('flights','algorithm','status','wall_seconds','error')},ensure_ascii=False),flush=True)
    print(folder.resolve(),flush=True)


if __name__=='__main__':
    main()
