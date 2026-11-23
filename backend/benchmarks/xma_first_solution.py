"""Frozen XMA-only campaign with interactive or explicitly authorized startup."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path
import csv
import gc
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback

from .common import ROOT, clean, digest, file_hash, read_json, write_json, utc_now
from .direct_campaign import file_lock

GIB=1024**3
KIND='xma-highs-first-solution-v1'


def balanced_groups(data):
    """Four frozen whole-tail partitions; Q1 deliberately contains flight 73."""
    from backend.business.xma.rules import option_legal
    from backend.business.xma.schema import Option
    flights={f.flight_id:f for f in data.flights}
    if len(data.aircraft)!=142:
        raise ValueError('this campaign expects the original 142-aircraft XMA workbook')
    quotas=[36,35,36,35]
    groups=[[],[],[],[]]
    equipment=Counter(a.equipment for a in data.aircraft)
    affected={f.flight_id for f in data.flights if not option_legal(data,Option(option_id='original',flight_id=f.flight_id,
        cancelled=False,dep=f.sched_dep,arr=f.sched_arr,delay=0),f)}
    stats=[dict(flights=0,affected=0,equipment=Counter()) for _ in groups]
    def add(i,tail):
        groups[i].append(tail.tail_id)
        stats[i]['flights']+=len(tail.original_rotation)
        stats[i]['affected']+=sum(fid in affected for fid in tail.original_rotation)
        stats[i]['equipment'][tail.equipment]+=1
    conflict_tail=flights['73'].original_aircraft
    ordered=sorted(data.aircraft,key=lambda a:(-sum(fid in affected for fid in a.original_rotation),-len(a.original_rotation),a.tail_id))
    add(0,next(a for a in ordered if a.tail_id==conflict_tail))
    def score(i,tail):
        fraction=quotas[i]/142
        contributions=[(stats[i]['flights'],len(tail.original_rotation),len(data.flights)*fraction),
                       (stats[i]['affected'],sum(fid in affected for fid in tail.original_rotation),len(affected)*fraction),
                       (stats[i]['equipment'][tail.equipment],1,equipment[tail.equipment]*fraction)]
        return sum(((current+increment-target)**2-(current-target)**2)/max(1,target)**2
                   for current,increment,target in contributions)
    for tail in ordered:
        if tail.tail_id!=conflict_tail:
            candidates=[i for i in range(4) if len(groups[i])<quotas[i]]
            add(min(candidates,key=lambda i:(score(i,tail),i)),tail)
    return {f'Q{i+1}':group for i,group in enumerate(groups)}


def prepare(folder,calibration=None):
    from .campaign import snapshot_sources, environment
    from backend.business.xma.importer import load_workbook, select_tail_subset, preview
    from backend.business.xma.schema import XmaSolveRequest
    from backend.business.xma.service import make_document, study_signature
    folder=Path(folder).resolve()
    if folder.exists():
        raise ValueError('output exists; use verify/launch, do not overwrite a frozen campaign')
    factor=1.0
    calibration_record=None
    if calibration:
        calibration_record=read_json(calibration)
        factor=max(1.0,float(calibration_record['calibration_factor']))
        if not calibration_record.get('passed'):
            raise ValueError('pilot calibration did not pass')
        for name,sha in calibration_record['sources'].items():
            if file_hash(ROOT/name)!=sha:raise ValueError('pilot code changed; repeat short calibration: '+name)
    else:
        raise ValueError('run the short pilot and supply its calibration.json first')
    data=load_workbook()
    groups=balanced_groups(data)
    end=max(f.sched_arr+timedelta(minutes=1440 if f.domestic else 2160)
            for f in data.flights if data.adjustment_start<=f.sched_dep<=data.adjustment_end)
    selections=[('Q1',groups['Q1'],21600),('H1',groups['Q1']+groups['Q2'],43200),
                ('FULL',[a.tail_id for a in data.aircraft],86400)]
    folder.mkdir(parents=True)
    jobs=[]
    for name,tail_ids,seconds in selections:
        selected=select_tail_subset(data,tail_ids)
        request=XmaSolveRequest(dataset=selected,solver_backend='highs',algorithm='joint_arc_flow',
            objective_profile='tianchi_2017',maximum_delay_minutes=None,max_assignment_options=None,
            recovery_end=end,delay_step_minutes=30,first_solution_search=True,time_limit_seconds=seconds,mip_gap=0)
        path=folder/'inputs'/f'{name}.json'
        write_json(path,request)
        write_json(folder/'drafts'/f'{name}.json',make_document(request))
        ids={f.flight_id for f in selected.flights}
        boundary=dict(inbound_flight_ids=sorted(selected.boundary_flights),
            outgoing_transfers=[t.model_dump(mode='json') for t in data.transfers if t.inbound in ids and t.outbound not in ids],
            cross_connected_pairs=[p for p in data.connected_pairs if (p[0] in ids)!=(p[1] in ids)],
            external_airport_occupancy='not deducted; conditional subset; do not stitch')
        write_json(folder/'boundaries'/f'{name}.json',boundary)
        jobs.append(dict(id=name,input=path.relative_to(folder).as_posix(),input_sha256=file_hash(path),
            study_signature=study_signature(request),seconds=seconds,memory_gib=6,threads=1,
            scale=preview(selected)['counts'],tail_ids=tail_ids))
    write_json(folder/'groups.json',groups)
    write_json(folder/'calibration.json',calibration_record)
    sources=snapshot_sources(folder)
    manifest=dict(schema_version='public-campaign-1.0',campaign_kind=KIND,created_at=utc_now(),
        git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),live_root=str(ROOT),
        python=sys.executable,environment=environment(),sources=sources,jobs=jobs,
        groups_sha256=file_hash(folder/'groups.json'),calibration_sha256=file_hash(folder/'calibration.json'),
        boundary_sha256={f'{j["id"]}.json':file_hash(folder/'boundaries'/f'{j["id"]}.json') for j in jobs},
        memory_calibration=factor,recovery_end=end.isoformat(),policy=dict(user_enter_required_by_default=True,
        explicit_start_now_supported=True,global_concurrency=1,
        startup_available_gib=4,emergency_available_gib=1.5,emergency_seconds=10,watchdog_grace_seconds=120,
        restricted_bounds_are_local=True,optimization_backend='highs',fallback=False,subset_is_full_solution=False))
    manifest['manifest_sha256']=digest(manifest)
    write_json(folder/'manifest.json',manifest)
    write_json(folder/'state.json',dict(status='prepared_not_started',jobs={},active=None))
    launcher=('@echo off\r\nchcp 65001 >nul\r\n'
        'title XMA HiGHS first solution - Q1 H1 FULL\r\n'
        f'cd /d "{folder / "source"}"\r\n'
        f'"{sys.executable}" -u "{folder / "source/scripts/xma_first_solution.py"}" run "{folder}"\r\n')
    (folder/'start_xma.cmd').write_bytes(launcher.encode('utf-8'))
    return dict(folder=str(folder),jobs=jobs,status='prepared_not_started',launcher=str(folder/'start_xma.cmd'))


def verify(folder):
    folder=Path(folder).resolve()
    manifest=read_json(folder/'manifest.json')
    if manifest['campaign_kind']!=KIND or digest({k:v for k,v in manifest.items() if k!='manifest_sha256'})!=manifest['manifest_sha256']:
        raise ValueError('campaign manifest mismatch')
    for name,sha in manifest['sources'].items():
        if file_hash(folder/'source'/name)!=sha:raise ValueError('frozen source changed: '+name)
    for job in manifest['jobs']:
        if file_hash(folder/job['input'])!=job['input_sha256']:raise ValueError('input changed: '+job['id'])
    for filename,expected in [('groups.json',manifest['groups_sha256']),('calibration.json',manifest['calibration_sha256'])]:
        if file_hash(folder/filename)!=expected:raise ValueError('frozen metadata changed: '+filename)
    for name,sha in manifest['boundary_sha256'].items():
        if file_hash(folder/'boundaries'/name)!=sha:raise ValueError('boundary changed: '+name)
    return manifest


def worker(folder,job_id,target,seconds=None):
    from backend.business.xma.schema import XmaSolveRequest, Decision
    from backend.business.xma.service import solve
    from backend.business.xma.evaluator import evaluate, export_csv
    from backend.business.xma.solver import SOLVER_OUTPUT
    folder,target=Path(folder),Path(target)
    manifest=read_json(folder/'manifest.json')
    job=next(j for j in manifest['jobs'] if j['id']==job_id)
    started=time.monotonic()
    observed=dict(first_solver_incumbent_seconds=None,first_audited_solution_seconds=None,first_checkpoint_seconds=None)
    request=None
    def event(value):
        value=clean(value);value['worker_elapsed_seconds']=time.monotonic()-started
        scope=value.get('metrics',{}).get('bound_scope')
        if value.get('type')=='mip_progress' and scope in ('global','restricted') and value.get('upper_bound') is not None and observed['first_solver_incumbent_seconds'] is None:
            observed['first_solver_incumbent_seconds']=value['worker_elapsed_seconds']
            observed['first_solver_scope']=value.get('metrics',{}).get('search_scope',scope)
        if value.get('type')=='incumbent_audited' and observed['first_audited_solution_seconds'] is None:
            observed['first_audited_solution_seconds']=value['worker_elapsed_seconds']
        with (target/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
        print(json.dumps(value,ensure_ascii=False),flush=True)
    def save(value):
        if not value.get('checkpoint'):return
        if observed['first_audited_solution_seconds'] is None:observed['first_audited_solution_seconds']=time.monotonic()-started
        write_json(target/'checkpoint.json',value)
        if observed['first_checkpoint_seconds'] is None:observed['first_checkpoint_seconds']=time.monotonic()-started
        write_json(target/'observed.json',observed)
        try:
            atomic_text(target/'flights.csv',export_csv(request,[Decision.model_validate(d) for d in value['business_decisions']]))
        except OSError as exc:
            event(dict(type='artifact_warning',stage='checkpoint',message='Checkpoint saved; CSV export deferred: '+str(exc)))
    target.mkdir(parents=True,exist_ok=True)
    try:
        if file_hash(folder/job['input'])!=job['input_sha256']:raise ValueError('input hash mismatch')
        request=XmaSolveRequest.model_validate(read_json(folder/job['input']))
        if request.solver_backend!='highs' or request.algorithm!='joint_arc_flow':raise ValueError('HiGHS joint model required')
        if seconds is not None:request=request.model_copy(update={'time_limit_seconds':min(request.time_limit_seconds,seconds)})
        token=SOLVER_OUTPUT.set(True)
        try:
            raw=solve(request,event_sink=event,solution_artifact_sink=save,
                      cancel_check=lambda:(folder/'STOP').exists() or (target/'CANCEL').exists())
        finally:SOLVER_OUTPUT.reset(token)
        write_json(target/'evidence.json',raw)
        audit=raw.get('independent_audit')
        if raw.get('tianchi_csv'):(target/'flights.csv').write_text(raw['tianchi_csv'],encoding='utf-8')
        result=dict(status=raw['status'],reason=raw['diagnostics']['terminal_reason'],audit_pass=bool(audit and audit['valid']),
            objective=raw['objective']['total'] if raw.get('objective') else None,
            lower_bound=raw['diagnostics']['lower_bound'],upper_bound=raw['diagnostics']['upper_bound'],
            relative_gap=raw['diagnostics']['relative_gap'],model_statistics=raw['diagnostics']['statistics'],
            source_sha256=request.dataset.source_sha256,study_signature=job['study_signature'],
            flights=len(request.dataset.flights),complete_decisions=len(raw['business_decisions'])==len(request.dataset.flights),
            certified_optimal=raw['status']=='optimal' and bool(audit and audit['valid']) and raw['diagnostics']['relative_gap'] is not None and raw['diagnostics']['relative_gap']<=1e-8,
            external_evaluator='not_run',**observed)
    except Exception as exc:
        result=dict(status='resource_limited' if isinstance(exc,MemoryError) else 'error',reason=str(exc),
            exception_type=type(exc).__name__,traceback=traceback.format_exc(),certified_optimal=False,**observed)
    result=restore_checkpoint(folder,job,target,result)
    result.update(job_id=job_id,worker_seconds=time.monotonic()-started,finished_at=utc_now())
    write_json(target/'result.json',result)
    return result


def restore_checkpoint(folder,job,target,result):
    """Re-audit saved business decisions; never trust only an old `valid` flag."""
    from backend.business.xma.schema import XmaSolveRequest, Decision
    from backend.business.xma.evaluator import evaluate, export_csv
    saved=Path(target)/'checkpoint.json'
    if saved.exists():
        value=read_json(saved)
        if value.get('input_hash')!=digest_request(Path(folder)/job['input']):
            # Resumed workers may use a shorter runtime budget, which is recorded
            # separately; the business signature must remain exactly identical.
            if value.get('study_signature')!=job['study_signature']:
                raise ValueError('checkpoint belongs to a different problem')
        request=XmaSolveRequest.model_validate(read_json(Path(folder)/job['input']))
        decisions=[Decision.model_validate(d) for d in value['business_decisions']]
        audit=evaluate(request,decisions)
        if not audit['valid'] or abs(audit['objective']-value['objective'])>max(1e-6,abs(value['objective'])*1e-8):
            raise ValueError('saved checkpoint re-audit failed')
        current=result.get('objective')
        if current is None or value['objective']<current:
            result.update(objective=value['objective'],upper_bound=value['objective'],lower_bound=None,
                          relative_gap=None,certified_optimal=False)
        if current is None or value['objective']<=current:
            write_json(Path(target)/'retained_audit.json',audit)
            (Path(target)/'flights.csv').write_text(export_csv(request,decisions),encoding='utf-8')
            result['solution_evidence_directory']=str(target)
        result.update(audit_pass=True,retained_incumbent=True,complete_decisions=True,flights=len(decisions))
        observed_path=Path(target)/'observed.json'
        if observed_path.exists():
            for key,val in read_json(observed_path).items():
                if val is not None and (result.get(key) is None or key.endswith('_seconds') and val<result[key]):result[key]=val
    return result


def digest_request(path):
    from backend.business.xma.schema import XmaSolveRequest
    from backend.workbench.storage import content_hash
    return content_hash(XmaSolveRequest.model_validate(read_json(path)).model_dump(mode='json'))


def atomic_text(path,text):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(text,encoding='utf-8')
    os.replace(temporary,path)


def report(folder):
    folder=Path(folder)
    manifest=read_json(folder/'manifest.json')
    results=[]
    for job in manifest['jobs']:
        path=folder/'jobs'/job['id']/'result.json'
        results.append({'job_id':job['id'],**(read_json(path) if path.exists() else {'status':'not_started'} )})
    summary=dict(updated_at=utc_now(),jobs=results,counts=dict(Counter(r['status'] for r in results)),
        full_solution=any(r['job_id']=='FULL' and r.get('audit_pass') and r.get('complete_decisions') for r in results))
    write_json(folder/'summary.json',summary)
    columns=['job_id','status','reason','objective','lower_bound','upper_bound','relative_gap','audit_pass','certified_optimal',
             'first_solver_incumbent_seconds','first_audited_solution_seconds','first_checkpoint_seconds','elapsed_seconds','peak_commit_bytes']
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,columns,extrasaction='ignore');writer.writeheader();writer.writerows(results)
    (folder/'runs.csv').write_text(stream.getvalue(),encoding='utf-8-sig')
    return summary


def run(folder, *, start_now=False):
    import psutil
    from scripts.validation_campaign import GuardedChild, process_memory
    folder=Path(folder).resolve()
    manifest=verify(folder)
    state_path=folder/'state.json'
    state=read_json(state_path)
    if state['status']=='completed':return report(folder)
    print('XMA / HiGHS / Q1 6h -> H1 12h -> FULL 24h / serial / 6 GiB hard memory limit',flush=True)
    print('STOP file or Ctrl+C requests cancellation. Closing this window kills its worker.',flush=True)
    if not start_now:
        write_json(folder/'window.json',dict(status='waiting_for_enter',pid=os.getpid(),at=utc_now()))
        input('Press ENTER to start; close this window to leave the campaign unstarted: ')
    else:
        print('Starting now under explicit user authorization (--start-now).',flush=True)
    write_json(folder/'window.json',dict(status='started',pid=os.getpid(),at=utc_now(),
        start_method='explicit_start_now' if start_now else 'interactive_enter'))
    with file_lock(Path(manifest['live_root'])/'.public_benchmarks/direct-baseline-machine.lock',lambda:print('Waiting for machine solve lock.',flush=True)):
        state=read_json(state_path)
        state.update(status='running',started_at=utc_now())
        write_json(state_path,state)
        try:
            for job in manifest['jobs']:
                if (folder/'STOP').exists():break
                final=folder/'jobs'/job['id']/'result.json'
                if final.exists():continue
                # Startup gate is independent of wall/solver clocks.
                startup_gib=manifest['policy']['startup_available_gib']
                while psutil.virtual_memory().available<startup_gib*GIB:
                    state.update(status='waiting_for_memory',active=None);write_json(state_path,state)
                    print(f'{job["id"]}: waiting for {startup_gib:g} GiB available; task clock has not started.',flush=True)
                    if (folder/'STOP').exists():break
                    time.sleep(5)
                if (folder/'STOP').exists():break
                root=folder/'jobs'/job['id'];root.mkdir(parents=True,exist_ok=True)
                attempts=sorted(root.glob('attempt_*'))
                consumed=sum(read_json(p/'result.json').get('elapsed_seconds',0) for p in attempts if (p/'result.json').exists())
                # A crashed supervisor cannot silently give a new full budget.
                for old in attempts:
                    if not (old/'result.json').exists() and (old/'attempt.json').exists():
                        meta=read_json(old/'attempt.json')
                        consumed+=meta['seconds']
                        recovered=restore_checkpoint(folder,job,old,dict(status='interrupted',reason='supervisor_interrupted',
                            elapsed_seconds=meta['seconds'],certified_optimal=False))
                        write_json(old/'result.json',recovered)
                remaining=max(0,job['seconds']-consumed)
                if remaining<=0:
                    result=dict(status='timed_out',reason='registered_budget_consumed',certified_optimal=False)
                    for old in attempts:result=restore_checkpoint(folder,job,old,result)
                    write_json(final,result);continue
                target=root/f'attempt_{len(attempts)+1:03d}';target.mkdir()
                write_json(target/'attempt.json',dict(started_at=utc_now(),seconds=remaining))
                state.update(status='running',active=job['id'],active_attempt=str(target));write_json(state_path,state)
                env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                    OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',XMA_MEMORY_CALIBRATION=str(manifest['memory_calibration']))
                command=[manifest['python'],str(folder/'source/scripts/xma_first_solution.py'),'_job',str(folder),job['id'],str(target),'--seconds',str(remaining)]
                began=time.monotonic();stop_since=low_since=None;reason=None;peak_rss=0
                print(f'START {job["id"]}, budget {remaining/3600:.2f}h',flush=True)
                with (target/'worker.log').open('ab') as log:
                    child=GuardedChild(command,cwd=folder/'source',env=env,log=log,memory_gib=6)
                    try:
                        last_notice=0
                        while child.poll() is None:
                            now=time.monotonic();elapsed=now-began
                            peak_rss=max(peak_rss,process_memory(child))
                            low=psutil.virtual_memory().available<1.5*GIB
                            low_since=(low_since or now) if low else None
                            if (folder/'STOP').exists():reason=reason or 'user_stop'
                            if low_since and now-low_since>=10:reason=reason or 'system_memory_floor'
                            if elapsed>=remaining:reason=reason or 'time_limit'
                            if child.peak_commit()>=6*GIB*.99:reason=reason or 'process_tree_memory_limit'
                            if reason:
                                (target/'CANCEL').touch(exist_ok=True);stop_since=stop_since or now
                                if now-stop_since>=120:child.kill();break
                            if now-last_notice>=30:
                                last_notice=now
                                print(f'{job["id"]}: {elapsed:.0f}s, peak RSS {peak_rss/GIB:.2f} GiB; {target}',flush=True)
                            time.sleep(.25)
                        peak_commit=child.peak_commit();returncode=child.poll()
                    except KeyboardInterrupt:
                        (target/'CANCEL').touch();reason='user_stop'
                        try:child.wait(timeout=120)
                        except TimeoutError:child.kill()
                        peak_commit=child.peak_commit();returncode=child.poll()
                    finally:child.close()
                result=read_json(target/'result.json') if (target/'result.json').exists() else dict(status='error',reason='worker_exit_without_result',certified_optimal=False)
                if reason:
                    result.update(status='cancelled' if reason=='user_stop' else 'timed_out' if reason=='time_limit' else 'resource_limited',reason=reason,certified_optimal=False)
                elif returncode and peak_commit>=6*GIB*.8:
                    result.update(status='resource_limited',reason='worker_exit_near_memory_limit',certified_optimal=False)
                result=restore_checkpoint(folder,job,target,result)
                for old in attempts:result=restore_checkpoint(folder,job,old,result)
                result.update(elapsed_seconds=time.monotonic()-began,peak_rss_bytes=peak_rss,peak_commit_bytes=peak_commit,
                    worker_returncode=returncode,evidence_directory=str(target.relative_to(folder)))
                if job['id']=='FULL' and result.get('audit_pass'):
                    source=Path(result.get('solution_evidence_directory',target))
                    result['external_evaluator']=verify_official(folder,source/'flights.csv',result['objective'])
                    if result['external_evaluator']['status']=='failed':
                        result.update(status='error',reason='official_evaluator_mismatch',certified_optimal=False)
                write_json(target/'result.json',result);write_json(final,result)
                state['jobs'][job['id']]=result;state['active']=None;write_json(state_path,state)
                report(folder)
                print(f'DONE {job["id"]}: {result["status"]}, audited UB={result.get("upper_bound")}',flush=True)
                if result['status'] in ('error','cancelled'):break
            state.update(status='completed' if all((folder/'jobs'/j['id']/'result.json').exists() for j in manifest['jobs']) else 'stopped',active=None)
            write_json(state_path,state)
        except KeyboardInterrupt:
            state.update(status='stopped',active=None);write_json(state_path,state)
    return report(folder)


def launch(folder, *, start_now=False):
    import psutil
    folder=Path(folder).resolve();verify(folder)
    state=folder/'window.json'
    if state.exists():
        previous=read_json(state)
        if psutil.pid_exists(previous['pid']):raise ValueError('the campaign window is already open')
    if start_now:
        script=folder/'source/scripts/xma_first_solution.py'
        command=f'"{os.environ.get("COMSPEC","cmd.exe")}" /d /k ""{sys.executable}" -u "{script}" run "{folder}" --start-now"'
    else:
        command=f'"{os.environ.get("COMSPEC","cmd.exe")}" /d /k call "{folder / "start_xma.cmd"}"'
    process=subprocess.Popen(command,cwd=folder,creationflags=subprocess.CREATE_NEW_CONSOLE)
    return dict(window_pid=process.pid,launcher=str(folder/'start_xma.cmd'),
        status='launch_requested' if start_now else 'waiting_for_enter')


def verify_official(folder,csv_path,objective):
    """Optional source-authoritative cross-check after releasing the solve worker."""
    folder=Path(folder)
    java=shutil.which('java')
    if not java and os.environ.get('JAVA_HOME'):
        candidate=Path(os.environ['JAVA_HOME'])/'bin/java.exe'
        if candidate.exists():java=str(candidate)
    if not java:
        result=dict(status='not_run',reason='java_not_found',official_certification=False)
        write_json(folder/'official_verification.json',result)
        return result
    files=list((folder/'source/data').rglob('XMAEvaluation.jar'))
    workbooks=list((folder/'source/data').rglob('XMAE_data.xlsx'))
    if len(files)!=1 or len(workbooks)!=1:
        result=dict(status='not_run',reason='official_files_not_unique',official_certification=False)
        write_json(folder/'official_verification.json',result);return result
    command=[java,'-Xmx512m','-Duser.timezone=Asia/Shanghai','-jar',str(files[0]),str(workbooks[0]),str(csv_path)]
    try:
        completed=subprocess.run(command,capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (folder/'official_stdout.txt').write_bytes(completed.stdout)
        (folder/'official_stderr.txt').write_bytes(completed.stderr)
        text=completed.stdout.decode('utf-8',errors='replace')
        values=re.findall(r'(-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)\s*$',text)
        score=float(values[-1]) if values else None
        okay=completed.returncode==0 and score is not None and abs(score-objective)<=max(1e-6,abs(objective)*1e-8)
        result=dict(status='passed' if okay else 'failed',official_score=score,independent_objective=objective,
                    exit_code=completed.returncode,official_certification=okay,java=java)
    except (subprocess.TimeoutExpired,OSError) as exc:
        result=dict(status='not_run',reason=str(exc),official_certification=False)
    write_json(folder/'official_verification.json',result)
    return result


def pilot(folder):
    """Short, guarded regressions and RAM calibration; never launches formal jobs."""
    from backend.business.xma.importer import load_workbook, select_subset
    from backend.business.xma.schema import XmaSolveRequest
    from backend.business.xma.rules import generate_options
    from backend.business.xma.search import estimate_size
    from backend.business.xma.service import study_signature
    from scripts.validation_campaign import GuardedChild, process_memory
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=False)
    data=load_workbook();jobs=[]
    expected={20:11444.0,50:48412.0,100:56897.62037037037}
    for size in (20,50,100):
        req=XmaSolveRequest(dataset=select_subset(data,size),solver_backend='highs',maximum_delay_minutes=120,
            max_assignment_options=None,time_limit_seconds=30)
        job_id=f'legacy-{size}';write_json(folder/'inputs'/f'{job_id}.json',req)
        jobs.append(dict(id=job_id,input=f'inputs/{job_id}.json',input_sha256=file_hash(folder/'inputs'/f'{job_id}.json'),
            study_signature=study_signature(req),expected=expected[size],scale=estimate_size(req,generate_options(req))))
    req=XmaSolveRequest(dataset=select_subset(data,20),solver_backend='highs',maximum_delay_minutes=None,
        max_assignment_options=None,time_limit_seconds=30)
    job_id='official-range-30';write_json(folder/'inputs'/f'{job_id}.json',req)
    jobs.append(dict(id=job_id,input=f'inputs/{job_id}.json',input_sha256=file_hash(folder/'inputs'/f'{job_id}.json'),
        study_signature=study_signature(req),expected=None,scale=estimate_size(req,generate_options(req))))
    write_json(folder/'manifest.json',dict(jobs=jobs,campaign_kind='xma-first-solution-short-pilot'))
    records=[];factor=1.0;passed=True
    for job in jobs:
        target=folder/'jobs'/job['id'];target.mkdir(parents=True)
        command=[sys.executable,str(ROOT/'scripts/xma_first_solution.py'),'_job',str(folder),job['id'],str(target)]
        env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='1',
                 MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        started=time.monotonic();peak_rss=0
        with (target/'worker.log').open('ab') as log:
            child=GuardedChild(command,cwd=ROOT,env=env,log=log,memory_gib=1.5)
            try:
                while child.poll() is None:
                    peak_rss=max(peak_rss,process_memory(child))
                    if time.monotonic()-started>60:child.kill();break
                    time.sleep(.1)
                commit=child.peak_commit();code=child.poll()
            finally:child.close()
        result=read_json(target/'result.json') if (target/'result.json').exists() else dict(status='error',reason='pilot_worker_exit',returncode=code)
        okay=result.get('status') not in ('error','resource_limited')
        if job['expected'] is not None:
            okay=okay and result.get('certified_optimal',False) and abs(result['objective']-job['expected'])<=1e-5
        if result.get('objective') is not None:okay=okay and result.get('audit_pass',False)
        passed=passed and okay
        factor=max(factor,max(peak_rss,commit)*1.25/job['scale']['estimated_peak_bytes'])
        record=dict(id=job['id'],passed=okay,result=result,scale=job['scale'],peak_rss_bytes=peak_rss,
                    peak_commit_bytes=commit,elapsed_seconds=time.monotonic()-started)
        records.append(record);write_json(target/'pilot.json',record)
        print(f'PILOT {job["id"]}: {result["status"]}; audit={result.get("audit_pass")}; RAM={commit/GIB:.3f} GiB',flush=True)
    calibration=dict(passed=passed,calibration_factor=factor,created_at=utc_now(),records=records,
        sources={p.relative_to(ROOT).as_posix():file_hash(p) for p in (ROOT/'backend/business/xma').glob('*.py')},
        policy='short pilots calibrate upward; structural RAM predictions remain heuristic; OS guard mandatory')
    write_json(folder/'calibration.json',calibration)
    return dict(passed=passed,calibration_factor=factor,path=str(folder/'calibration.json'))
