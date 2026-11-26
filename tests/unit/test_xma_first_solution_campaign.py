import builtins
from pathlib import Path

import pytest

from backend.benchmarks import xma_first_solution as campaign
from backend.benchmarks.common import write_json, read_json, file_hash
from backend.business.xma.importer import load_workbook, select_tail_subset, validate_dataset
from backend.business.xma.service import study_signature
from test_xma_first_solution import sample


@pytest.fixture(scope='module')
def workbook():return load_workbook()


def test_balanced_whole_tail_partition_and_boundary_ledger(workbook):
    groups=campaign.balanced_groups(workbook)
    assert groups==campaign.balanced_groups(workbook)
    assert [len(v) for v in groups.values()]==[36,35,36,35]
    all_tails=[tail for group in groups.values() for tail in group]
    assert len(all_tails)==len(set(all_tails))==142
    assert next(f.original_aircraft for f in workbook.flights if f.flight_id=='73') in groups['Q1']
    q=select_tail_subset(workbook,groups['Q1'])
    half=select_tail_subset(workbook,groups['Q1']+groups['Q2'])
    assert not validate_dataset(q) and not validate_dataset(half)
    ids={f.flight_id for f in q.flights}
    assert ids<{f.flight_id for f in half.flights}
    assert {f.flight_id for f in workbook.flights}=={fid for a in workbook.aircraft for fid in a.original_rotation}
    assert [t for t in workbook.transfers if t.outbound in ids]==q.transfers
    assert set(q.boundary_flights)=={t.inbound for t in q.transfers if t.inbound not in ids}
    assert all(a in ids and b in ids for a,b in q.connected_pairs)


@pytest.mark.parametrize('settings,seconds,aircraft,hard_limit', [
    ({}, [21600,43200,86400], [36,71,142], 6),
    ({'only':'FULL','memory_gib':40}, [86400], [142], 40),
])
def test_prepare_freezes_selected_jobs_and_detects_tampering(tmp_path,monkeypatch,workbook,settings,seconds,aircraft,hard_limit):
    from backend.benchmarks import campaign as existing
    def snapshot(folder):
        p=folder/'source'/'frozen.py';p.parent.mkdir();p.write_text('# frozen')
        return {'frozen.py':file_hash(p)}
    monkeypatch.setattr(existing,'snapshot_sources',snapshot)
    monkeypatch.setattr(existing,'environment',lambda:{'test':True})
    calibration=tmp_path/'calibration.json'
    write_json(calibration,dict(passed=True,calibration_factor=1,sources={}))
    folder=tmp_path/'batch'
    result=campaign.prepare(folder,calibration,**settings)
    m=campaign.verify(folder)
    assert result['status']=='prepared_not_started'
    assert [j['seconds'] for j in m['jobs']]==seconds
    assert [j['scale']['aircraft'] for j in m['jobs']]==aircraft
    assert all(job['memory_gib']==hard_limit for job in m['jobs'])
    assert m['policy']['admission_bytes']==int(hard_limit*1024**3*0.70)
    assert m['recovery_end']=='2017-05-10T21:40:00+08:00'
    assert ' run ' in (folder/'start_xma.cmd').read_text(encoding='utf-8')
    assert not (folder/'jobs').exists()
    request=read_json(folder/'inputs/FULL.json')
    assert request['maximum_delay_minutes'] is None and request['max_assignment_options'] is None
    assert request['first_solution_search'] and request['solver_backend']=='highs'
    (folder/'boundaries/FULL.json').write_text('{}')
    with pytest.raises(ValueError,match='boundary changed'):campaign.verify(folder)


def test_no_worker_is_started_before_enter(tmp_path,monkeypatch):
    write_json(tmp_path/'state.json',dict(status='prepared_not_started',jobs={},active=None))
    monkeypatch.setattr(campaign,'verify',lambda p:{'jobs':[]})
    def no_enter(prompt):raise EOFError('closed without Enter')
    monkeypatch.setattr(builtins,'input',no_enter)
    from scripts import validation_campaign
    monkeypatch.setattr(validation_campaign,'GuardedChild',lambda *a,**k:pytest.fail('worker started without Enter'))
    with pytest.raises(EOFError):campaign.run(tmp_path)
    assert read_json(tmp_path/'window.json')['status']=='waiting_for_enter'
    assert read_json(tmp_path/'state.json')['status']=='prepared_not_started'
    assert not (tmp_path/'jobs').exists()


def test_explicit_start_now_skips_enter_and_records_authorization(tmp_path,monkeypatch):
    from contextlib import nullcontext
    write_json(tmp_path/'state.json',dict(status='prepared_not_started',jobs={},active=None))
    monkeypatch.setattr(campaign,'verify',lambda p:dict(jobs=[],live_root=str(tmp_path)))
    monkeypatch.setattr(campaign,'file_lock',lambda *a,**k:nullcontext())
    monkeypatch.setattr(campaign,'report',lambda p:dict(done=True))
    monkeypatch.setattr(builtins,'input',lambda *a:pytest.fail('explicit start must not wait for input'))
    assert campaign.run(tmp_path,start_now=True)==dict(done=True)
    assert read_json(tmp_path/'window.json')['start_method']=='explicit_start_now'
    assert read_json(tmp_path/'state.json')['status']=='completed'


def test_worker_saves_and_reaudits_checkpoint_and_csv(tmp_path):
    request=sample()
    path=tmp_path/'input.json';write_json(path,request)
    job=dict(id='test',input='input.json',input_sha256=file_hash(path),study_signature=study_signature(request))
    write_json(tmp_path/'manifest.json',dict(jobs=[job]))
    target=tmp_path/'attempt_001'
    result=campaign.worker(tmp_path,'test',target)
    assert result['certified_optimal'] and result['audit_pass']
    assert result['first_checkpoint_seconds'] is not None
    assert result['first_audited_solution_seconds']<=result['first_checkpoint_seconds']
    assert (target/'flights.csv').exists() and (target/'retained_audit.json').exists()
    recovered=campaign.restore_checkpoint(tmp_path,job,target,dict(status='timed_out',certified_optimal=False))
    assert recovered['audit_pass'] and recovered['complete_decisions']
    assert recovered['lower_bound'] is None and not recovered['certified_optimal']
    saved=read_json(target/'checkpoint.json')
    saved['business_decisions'].pop()
    write_json(target/'checkpoint.json',saved)
    with pytest.raises(ValueError,match='re-audit failed'):campaign.restore_checkpoint(tmp_path,job,target,{})


@pytest.mark.parametrize('official_score,status',[(123.5,'passed'),(124.5,'failed')])
def test_official_checker_parses_prefixed_score_and_checks_agreement(tmp_path,monkeypatch,official_score,status):
    from types import SimpleNamespace
    data=tmp_path/'source/data';data.mkdir(parents=True)
    (data/'XMAEvaluation.jar').touch();(data/'XMAE_data.xlsx').touch()
    monkeypatch.setattr(campaign.shutil,'which',lambda name:'java.exe')
    monkeypatch.setattr(campaign.subprocess,'run',lambda *a,**k:SimpleNamespace(
        returncode=0,stdout=f'选手最终得分为：{official_score}\n'.encode(),stderr=b''))
    result=campaign.verify_official(tmp_path,tmp_path/'flights.csv',123.5)
    assert result['status']==status
    assert result['official_certification']==(status=='passed')
