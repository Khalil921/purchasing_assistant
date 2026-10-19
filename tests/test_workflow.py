from fastapi.testclient import TestClient
from backend.main import app

def test_confirmations_persist_and_invalidate():
    c=TestClient(app);t=c.post('/api/samples/A').json();url=f"/api/tasks/{t['id']}"
    assert c.post(url+'/confirm-review').status_code==400
    assert c.post(url+'/confirm-fields').json()['field_confirmation']
    audited=c.post(url+'/audit').json();assert audited['field_confirmation']
    assert c.post(url+'/confirm-review').json()['review_confirmation']
    assert c.get(url).json()['review_confirmation']
    d=t['documents'][0]
    updated=c.put(url+'/documents/'+d['id'],json=d['data']).json()
    assert not updated.get('field_confirmation') and not updated.get('review_confirmation') and not updated['result']

def test_pending_issues_block_final_confirmation():
    c=TestClient(app);t=c.post('/api/samples/B').json();url=f"/api/tasks/{t['id']}"
    c.post(url+'/confirm-fields');t=c.post(url+'/audit').json()
    assert c.post(url+'/confirm-review').status_code==400
    for issue in t['result']['issues']:
        c.put(url+'/issues/'+issue['id'],json={'status':'已确认','note':'人工确认问题仍存在'})
    done=c.post(url+'/confirm-review').json()
    assert done['review_confirmation'] and done['result']['status']=='发现异常'
    changed=c.post(url+'/audit').json();assert not changed.get('review_confirmation')

def test_incomplete_fields_cannot_confirm():
    c=TestClient(app);t=c.post('/api/tasks',json={'name':'未完成材料'}).json()
    assert c.post(f"/api/tasks/{t['id']}/confirm-fields").status_code==409

def test_backend_enforces_stage_order_and_replacement_requires_resubmission():
    c=TestClient(app);t=c.post('/api/tasks',json={'name':'阶段顺序测试'}).json();url=f"/api/tasks/{t['id']}"
    for endpoint in ['extract','submit-materials','confirm-fields','audit']:
        assert c.post(url+'/'+endpoint).status_code==409
    assert c.get(url+'/report').status_code==409
    t=c.post('/api/samples/A').json();url=f"/api/tasks/{t['id']}"
    assert c.post(url+'/audit').status_code==409
    assert c.post(url+'/confirm-fields').status_code==200
    assert c.post(url+'/audit').status_code==200
    assert c.get(url+'/report').status_code==200
    t=c.delete(url+'/documents/'+t['documents'][0]['id']).json()
    assert not t.get('materials_submission') and not t.get('field_confirmation') and not t.get('result')
    assert c.post(url+'/audit').status_code==409

def test_demo_skip_log_is_task_scoped():
    c=TestClient(app);t=c.post('/api/samples/A').json();other=c.post('/api/samples/A').json()
    url=f"/api/tasks/{t['id']}";response=c.post(url+'/extract')
    assert response.headers['x-request-id']
    events=c.get(url+'/calls').json()
    assert len(events)==3 and all(e['event']=='model.skipped' and e['reason']=='demo_data' for e in events)
    assert all(e['request_id']==response.headers['x-request-id'] for e in events)
    assert c.get(f"/api/tasks/{other['id']}/calls").json()==[]
