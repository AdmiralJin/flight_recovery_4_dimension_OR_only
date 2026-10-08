"""Compare an incumbent with the bundled official evaluator (Java required)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.business.xma.importer import load_workbook
from backend.business.xma.schema import XmaSolveRequest
from backend.business.xma.service import solve


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--java',default='java')
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=30)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    request=XmaSolveRequest(dataset=load_workbook(args.workbook),delay_step_minutes=60,maximum_delay_minutes=120,time_limit_seconds=args.seconds)
    result=solve(request)
    (args.output/'request.json').write_text(request.model_dump_json(),encoding='utf-8')
    (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if not result.get('tianchi_csv'):
        raise RuntimeError('No incumbent to verify; see result.json')
    csv=args.output/'result.csv'; csv.write_text(result['tianchi_csv'],encoding='utf-8')
    jar=next((Path(__file__).resolve().parents[1]/'data').rglob('XMAEvaluation.jar'))
    command=[args.java,'-Duser.timezone=Asia/Shanghai','-jar',str(jar.resolve()),str(args.workbook.resolve()),str(csv.resolve())]
    completed=subprocess.run(command,capture_output=True)
    (args.output/'jar_stdout.txt').write_bytes(completed.stdout)
    (args.output/'jar_stderr.txt').write_bytes(completed.stderr)
    text=completed.stdout.decode('utf-8',errors='replace')
    matches=re.findall(r'(-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)\s*$',text)
    score=float(matches[-1]) if matches else None
    expected=result['independent_audit']['score']
    checked={'official_score':score,'independent_score':expected,'difference':None if score is None else score-expected,
        'independent_valid':result['independent_audit']['valid'],'exit_code':completed.returncode,
        'passed':score is not None and not completed.stderr and abs(score-expected)<=max(1e-6,abs(expected)*1e-8)}
    (args.output/'verification.json').write_text(json.dumps(checked,indent=2),encoding='utf-8')
    print(json.dumps(checked),flush=True)
    if not checked['passed']:
        raise SystemExit(1)


if __name__=='__main__': main()
