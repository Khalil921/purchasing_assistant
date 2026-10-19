import asyncio
import httpx
import pytest
from backend import extract as module
from backend.models import Extraction

class FakeClient:
    replies=[]
    calls=0
    last_request=None
    def __init__(self,**kwargs): assert kwargs['timeout']==40
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def post(self,*args,**kwargs):
        FakeClient.calls+=1
        FakeClient.last_request=(args,kwargs)
        assert kwargs['json']['messages'][0]['role']=='system'
        r=FakeClient.replies.pop(0)
        if isinstance(r,Exception):raise r
        return r

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','unit-test-not-real-key');monkeypatch.setattr(module.httpx,'AsyncClient',FakeClient)
    FakeClient.calls=0
    return FakeClient

def test_valid_json_output(client):
    data=Extraction().model_dump();data['buyer']=dict(value='采购方',quote='采购方',location='PDF 第 1 页')
    import json
    client.replies=[httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(data)}}]})]
    out=asyncio.run(module.extract([{'location':'PDF 第 1 页','text':'采购方'}]));assert out['buyer']['value']=='采购方'
    args,kwargs=client.last_request
    assert args[0]=='https://api.deepseek.com/chat/completions'
    assert kwargs['json']['model']=='deepseek-flash'
    assert kwargs['json']['response_format']=={'type':'json_object'}
    assert kwargs['json']['max_tokens']==8192
    assert kwargs['headers']['Authorization']=='Bearer unit-test-not-real-key'

def test_bad_schema_never_falls_back(client):
    client.replies=[httpx.Response(200,json={'choices':[{'message':{'content':'{"items":"invalid"}'}}]})]
    with pytest.raises(ValueError,match='结构或原文证据'): asyncio.run(module.extract([]))

def test_limited_retry_without_disclosing_key(client):
    client.replies=[httpx.Response(503),httpx.Response(503)]
    with pytest.raises(ValueError,match='HTTP 503') as exc: asyncio.run(module.extract([]))
    assert client.calls==2;assert 'unit-test' not in str(exc.value)

def test_timeout_twice(client):
    client.replies=[httpx.ReadTimeout('timeout'),httpx.ReadTimeout('timeout')]
    with pytest.raises(ValueError,match='超时或连接失败'):asyncio.run(module.extract([]))
    assert client.calls==2

def test_truncated_output_is_failure(client):
    client.replies=[httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]})]
    with pytest.raises(ValueError,match='长度上限'):asyncio.run(module.extract([]))

def test_malformed_upstream_is_failure(client):
    client.replies=[httpx.Response(200,json={'choices':[]})]
    with pytest.raises(ValueError,match='响应格式无效'):asyncio.run(module.extract([]))

def test_unauthorized_does_not_retry_or_leak(client):
    client.replies=[httpx.Response(401,text='unit-test-not-real-key')]
    with pytest.raises(ValueError,match='HTTP 401') as exc:asyncio.run(module.extract([]))
    assert client.calls==1 and 'unit-test' not in str(exc.value)

def test_metadata_logging_and_no_sensitive_bodies(client):
    import json
    from backend.observability import task_calls,log_dir
    private='private-procurement-original-text'
    data=Extraction().model_dump();data['buyer']=dict(value=private,quote=private,location='PDF 第 1 页')
    client.replies=[httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(data)}}],'usage':{'prompt_tokens':120,'completion_tokens':80,'total_tokens':200,'untrusted':private}})]
    asyncio.run(module.extract([{'text':private,'location':'PDF 第 1 页'}],task_id='logging-test',document_id='test-doc'))
    events=task_calls('logging-test');assert [e['event'] for e in events]==['model.started','model.request','model.response','model.completed']
    assert len({e['call_id'] for e in events})==1
    assert events[2]['usage']['total_tokens']==200 and events[-1]['validation']=='passed'
    text=(log_dir()/'api.jsonl').read_text(encoding='utf-8')
    assert private not in text and 'unit-test-not-real-key' not in text

def test_unexpected_exception_is_not_logged_raw(client,monkeypatch):
    from backend.observability import task_calls
    async def fail(*args,**kwargs):raise ValueError('sensitive-internal-exception')
    monkeypatch.setattr(client,'post',fail)
    with pytest.raises(ValueError) as exc:asyncio.run(module.extract([],task_id='internal-error-test'))
    assert 'sensitive-internal' not in str(exc.value)
    assert task_calls('internal-error-test')[-1]['error']=='internal_error'
