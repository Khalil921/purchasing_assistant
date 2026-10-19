import asyncio
import copy
import io
import json
import httpx
import pytest
from docx import Document
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import main, extract
from backend.intelligence import validate_analysis

def ready(c):
    t=c.post('/api/samples/A').json();url='/api/tasks/'+t['id']
    c.post(url+'/confirm-fields')
    return c.post(url+'/audit').json(),url

def output(t):
    d=t['documents'][0];b=d['blocks'][0]
    evidence=dict(document_id=d['id'],quote=b['text'],location=b['location'])
    return dict(summary='请核实交付基准事件。',summary_evidence=[evidence],findings=[dict(title='交付基准待核实',category='交付语义',severity='低',explanation='需要人工核对业务基准。',suggestion='与业务方确认。',evidence=[evidence],related_issue_ids=[])],limitations=['建议需人工判断，原文存在不等于语义正确。'])

def test_delete_owns_uploads_but_preserves_shared_samples_and_other_tasks():
    c=TestClient(main.app);t,url=ready(c);other,_=ready(c)
    shared=main.Path(t['documents'][0]['path']);owned=main.UPLOAD/(t['id']+'.docx');owned.write_bytes(b'owned')
    t['documents'].append(dict(id='owned',path=str(owned)));main.save(t)
    result=c.delete(url);assert result.status_code==200 and result.json()['deleted_uploads']==1
    assert not owned.exists() and shared.exists()
    assert c.get(url).status_code==404 and c.delete(url).status_code==404
    assert c.get('/api/tasks/'+other['id']).status_code==200
    with pytest.raises(HTTPException) as exc:main.save(t)
    assert exc.value.status_code==404 and c.get(url).status_code==404

def test_delete_never_unlinks_outside_upload_directory():
    c=TestClient(main.app);t,url=ready(c);outside=main.DATA/'protected.txt';outside.write_text('preserve')
    t['documents'].append(dict(id='outside',path=str(outside)));main.save(t)
    assert c.delete(url).json()['deleted_uploads']==0 and outside.exists()

def test_delete_shared_upload_reference_and_authentication():
    c=TestClient(main.app);t,url=ready(c);other,other_url=ready(c)
    owned=main.UPLOAD/(t['id']+'.docx');owned.write_bytes(b'shared')
    for task in [t,other]:
        task['documents'].append(dict(id='shared',path=str(owned)));main.save(task)
    assert c.delete(url).json()['deleted_uploads']==0 and owned.exists()
    c.cookies.clear();assert c.delete(other_url).status_code==401
    assert owned.exists()
    authorized=TestClient(main.app)
    assert authorized.delete(other_url).json()['deleted_uploads']==1 and not owned.exists()

def test_ai_evidence_schema_and_issue_references_are_validated():
    c=TestClient(main.app);t,_=ready(c);data=output(t)
    assert validate_analysis(data,t)['findings'][0]['status']=='待处理'
    for change in ['quote','location','document_id']:
        invalid=copy.deepcopy(data);invalid['findings'][0]['evidence'][0][change]='fabricated'
        with pytest.raises(ValueError):validate_analysis(invalid,t)
    invalid=copy.deepcopy(data);invalid['findings'][0]['related_issue_ids']=['imaginary']
    with pytest.raises(ValueError):validate_analysis(invalid,t)
    with pytest.raises(ValueError):validate_analysis({'summary':'no citations'},t)

def test_real_adapter_mocked_ai_review_and_human_confirmation(monkeypatch):
    c=TestClient(main.app);t,url=ready(c);data=output(t)
    class Client:
        def __init__(self,**kwargs):assert kwargs['timeout']==40
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,address,**kwargs):
            payload=kwargs['json'];assert payload['response_format']=={'type':'json_object'}
            assert 'rule_result' in json.loads(payload['messages'][1]['content'])
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(data)}}]})
    monkeypatch.setenv('MODEL_API_KEY','unit-test-key');monkeypatch.setattr(extract.httpx,'AsyncClient',Client)
    result=c.post(url+'/ai-analysis').json()
    assert result['result']['status']=='通过' and result['ai_analysis']['status']=='已完成'
    assert c.post(url+'/confirm-review').status_code==400
    f=result['ai_analysis']['findings'][0]
    assert c.put(url+'/ai-findings/'+f['id'],json={'status':'已确认','note':'人工复核记录'}).status_code==200
    assert c.post(url+'/confirm-review').status_code==200
    paragraphs='\n'.join(p.text for p in Document(io.BytesIO(c.get(url+'/report').content)).paragraphs)
    assert 'AI 语义复核' in paragraphs and '人工复核记录' in paragraphs and data['summary'] in paragraphs
    events=c.get(url+'/calls').json();assert all(e['purpose']=='semantic_review' for e in events)
    d=t['documents'][0]
    changed=c.put(url+'/documents/'+d['id'],json=d['data']).json()
    assert not changed.get('ai_analysis') and not changed['result']

def test_missing_key_is_explicit_failure_and_preserves_rules():
    c=TestClient(main.app);t,url=ready(c)
    result=c.post(url+'/ai-analysis').json()
    assert result['result']==t['result'] and result['ai_analysis']['status']=='失败'
    assert '未配置模型密钥' in result['ai_analysis']['error']
    assert result['ai_analysis']['findings']==[]
    empty=c.post('/api/tasks',json={'name':'incomplete'}).json()
    assert c.post('/api/tasks/'+empty['id']+'/ai-analysis').status_code==409

def test_model_fabricated_citation_is_failure_not_an_adopted_finding(monkeypatch):
    c=TestClient(main.app);t,url=ready(c);data=output(t)
    data['findings'][0]['evidence'][0]['quote']='unseen fabricated evidence'
    original=extract.httpx.AsyncClient
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(data)}}]}))
    monkeypatch.setenv('MODEL_API_KEY','unit-test-key')
    monkeypatch.setattr(extract.httpx,'AsyncClient',lambda **kwargs:original(transport=transport,**kwargs))
    result=c.post(url+'/ai-analysis').json()
    assert result['ai_analysis']['status']=='失败' and result['ai_analysis']['findings']==[]
    assert '证据校验失败' in result['ai_analysis']['error']
    assert result['result']==t['result']

@pytest.mark.parametrize('action',['edit','delete'])
def test_inflight_analysis_does_not_overwrite_changed_or_deleted_task(monkeypatch,action):
    c=TestClient(main.app);t,url=ready(c)
    async def racing(task):
        if action=='delete':main.delete_task(task['id'])
        else:
            current=main.get(task['id']);current['name']='changed';main.save(current)
        return dict(status='已完成',findings=[])
    monkeypatch.setattr(main,'analyze',racing)
    assert c.post(url+'/ai-analysis').status_code==(404 if action=='delete' else 409)
    if action=='edit':assert c.get(url).json()['name']=='changed' and not c.get(url).json().get('ai_analysis')
