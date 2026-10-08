from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import workbench_v2, xma
from backend.main import app
from backend.business.xma.importer import load_workbook, select_subset
from backend.business.xma.schema import XmaSolveRequest
from backend.business.xma.service import make_document
from backend.schemas.workbench import CompilePreview
from backend.workbench import worker
from backend.workbench.storage import WorkbenchStore


@pytest.fixture()
def business_client(tmp_path: Path,monkeypatch):
    store=WorkbenchStore(tmp_path/'.workbench')
    monkeypatch.setattr(workbench_v2,'get_workbench_store',lambda:store)
    monkeypatch.setattr(xma,'get_workbench_store',lambda:store)
    monkeypatch.setattr(worker,'WorkbenchStore',lambda:store)
    return TestClient(app),store


def test_xma_snapshot_worker_export_and_visualization(business_client):
    client,store=business_client
    request=XmaSolveRequest(dataset=select_subset(load_workbook(),20),delay_step_minutes=60,maximum_delay_minutes=120,time_limit_seconds=30)
    document=make_document(request).model_dump(mode='json')
    draft=client.post('/api/v2/drafts',json={'document':document}).json()
    url=f"/api/v2/drafts/{draft['draft_id']}"
    compiled=client.post(url+'/compile')
    assert compiled.status_code==200 and compiled.json()['valid']
    visual=client.get(url+'/visualization')
    assert visual.status_code==200
    snapshot=store.create_snapshot(draft['draft_id'],draft['working_hash'],CompilePreview.model_validate(compiled.json()))
    run=store.create_run(snapshot,'detailed')
    assert worker.execute_run(run.run_id)==0
    done=store.get_run(run.run_id)
    assert done.result['independent_audit']['valid']
    assert done.result['status']=='optimal'
    assert done.solution_artifact_hash
    exported=client.get(f'/api/v2/xma/runs/{run.run_id}/csv')
    assert exported.status_code==200
    assert len(exported.text.splitlines())==30
    assert all(len(row.split(','))==11 for row in exported.text.splitlines())
    recovered=client.get(f'/api/v2/runs/{run.run_id}/visualization')
    assert recovered.status_code==200
    assert recovered.json()['mode_availability']['recovered']['available']
    changed=document.copy()
    changed['solve_bundle']={**document['solve_bundle'],'objective_profile':'air_linear_v1'}
    updated=client.put(url+'/working-copy',json={'base_hash':draft['working_hash'],'document':changed})
    assert updated.status_code==200
    new_preview=client.post(url+'/compile').json()
    assert new_preview['compiled_hash']!=snapshot.content_hash


def test_import_and_evaluation_errors_are_structured(business_client):
    client,_=business_client
    assert client.post('/api/v2/xma/import-preview',content=b'not-an-xlsx').status_code==422
    assert client.post('/api/v2/xma/evaluate',json={}).status_code==422
    assert client.post('/api/v2/xma/export-csv',json={}).status_code==422
    assert client.get('/api/v2/xma/runs/missing/csv').status_code==404
