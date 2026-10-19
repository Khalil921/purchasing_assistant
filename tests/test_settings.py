import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.settings import load_settings

@pytest.fixture
def files(tmp_path,monkeypatch):
    p=tmp_path/'config.toml';p.write_text('[model]\n',encoding='utf-8')
    monkeypatch.setenv('CAIHE_CONFIG_FILE',str(p))
    return p,p.with_name('config.local.toml')

def test_local_file_and_public_config_never_exposes_key(files):
    base,local=files
    base.write_text('[model]\nname="deepseek-flash"\ntimeout_seconds=55\n',encoding='utf-8')
    local.write_text('[model]\napi_key="local-secret-for-test"\n',encoding='utf-8-sig')
    settings=load_settings()
    assert settings.configured and settings.timeout_seconds==55
    assert 'local-secret-for-test' not in repr(settings)
    r=TestClient(app).get('/api/config');assert r.status_code==200
    assert r.json()['provider']=='deepseek' and r.json()['configured']
    assert 'local-secret-for-test' not in r.text and 'api_key' not in r.text

def test_environment_precedence(files,monkeypatch):
    _,local=files;local.write_text('[model]\napi_key="local-key"\n',encoding='utf-8')
    monkeypatch.setenv('MODEL_API_KEY','legacy-key')
    monkeypatch.setenv('DEEPSEEK_API_KEY','preferred-key')
    monkeypatch.setenv('MODEL_NAME','alternate-model')
    s=load_settings();assert s.api_key.get_secret_value()=='preferred-key';assert s.name=='alternate-model'

def test_config_edits_apply_without_restart(files):
    _,local=files;assert not load_settings().configured
    local.write_text('[model]\napi_key="test-key"\n',encoding='utf-8')
    assert load_settings().configured

@pytest.mark.parametrize('text',[
    '[model]\napi_key="sensitive-test-key"\nmax_attempts=99',
    '[model]\napi_key="sensitive-test-key',
    '[model]\napi_key="sensitive-test-key"\napi_base="https://user:password@api.deepseek.com"',
    '[model]\napi_key="sensitive-test-key"\nunknown_field=true',
])
def test_invalid_configuration_redacts_content(files,text):
    _,local=files;local.write_text(text,encoding='utf-8')
    with pytest.raises(ValueError) as exc:load_settings()
    assert 'sensitive-test-key' not in str(exc.value) and 'password' not in str(exc.value)
    r=TestClient(app).get('/api/config')
    assert r.json()['mode']=='配置错误' and 'sensitive-test-key' not in r.text
