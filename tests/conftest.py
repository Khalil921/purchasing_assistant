import os
import tempfile
from pathlib import Path
import pytest

# Isolate all API integration writes from the user's demonstration database.
_storage = tempfile.TemporaryDirectory(prefix='caihe-tests-')
os.environ['DATA_DIR'] = _storage.name
_config=Path(_storage.name)/'config.toml'
_config.write_text('[model]\n',encoding='utf-8')
os.environ['CAIHE_CONFIG_FILE']=str(_config)
from backend.auth import hash_password
_auth=Path(_storage.name)/'auth.local.toml'
import json
_auth.write_text('[auth]\nusername="test-user"\npassword_hash='+json.dumps(hash_password('test-only-password'))+'\n',encoding='utf-8')
os.environ['CAIHE_AUTH_FILE']=str(_auth)

@pytest.fixture(autouse=True)
def authenticated_clients(monkeypatch,request):
    if request.node.path.name=='test_auth.py':return
    from fastapi.testclient import TestClient
    original=TestClient.__init__
    def init(client,*args,**kwargs):
        original(client,*args,**kwargs)
        response=client.post('/api/auth/login',json={'username':'test-user','password':'test-only-password'})
        assert response.status_code==200
    monkeypatch.setattr(TestClient,'__init__',init)

@pytest.fixture(autouse=True)
def isolated_model_environment(monkeypatch):
    for env in ['MODEL_API_KEY','DEEPSEEK_API_KEY','MODEL_API_BASE','MODEL_NAME']:
        monkeypatch.delenv(env,raising=False)

def pytest_sessionfinish(session,exitstatus):
    # Close rotating log files before Windows removes the temporary test directory.
    import logging
    logging.shutdown()
