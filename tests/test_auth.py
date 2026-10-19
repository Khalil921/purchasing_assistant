import time
from fastapi.testclient import TestClient
from backend.main import app,db
from backend.auth import COOKIE,token_hash

def login(c):return c.post('/api/auth/login',json={'username':'test-user','password':'test-only-password'})

def test_private_apis_require_login():
    c=TestClient(app)
    for path in ['/api/tasks','/api/config','/api/samples/A/download','/api/tasks/unknown/documents/unknown/file','/api/tasks/unknown/report','/api/tasks/unknown/calls']:
        assert c.get(path).status_code==401
    assert c.post('/api/tasks',json={'name':'unauthorized'}).status_code==401
    assert c.get('/api/auth/session').json()['authenticated'] is False
    assert c.get('/api/health').status_code==200

def test_login_cookie_reload_logout_and_stolen_token_revocation():
    c=TestClient(app);r=login(c);assert r.status_code==200
    cookie=r.headers['set-cookie'];assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    token=c.cookies.get(COOKIE)
    with db() as con:
        row=con.execute('SELECT token_hash FROM sessions WHERE token_hash=?',(token_hash(token),)).fetchone()
    assert row and row['token_hash']!=token
    assert c.get('/api/auth/session').json()['username']=='test-user'
    assert c.get('/api/tasks').status_code==200
    assert c.post('/api/auth/logout').status_code==200
    assert c.get('/api/tasks').status_code==401
    c.cookies.set(COOKIE,token)
    assert c.get('/api/tasks').status_code==401

def test_expired_session_is_rejected():
    c=TestClient(app);login(c);token=c.cookies.get(COOKIE)
    with db() as con:con.execute('UPDATE sessions SET expires=? WHERE token_hash=?',(time.time()-1,token_hash(token)))
    assert c.get('/api/tasks').status_code==401

def test_wrong_password_and_rate_limit_do_not_expose_credentials():
    c=TestClient(app)
    with db() as con:con.execute('DELETE FROM login_attempts')
    try:
        for _ in range(5):
            r=c.post('/api/auth/login',json={'username':'test-user','password':'wrong-secret'})
            assert r.status_code==401 and 'wrong-secret' not in r.text
        assert login(c).status_code==429
    finally:
        with db() as con:con.execute('DELETE FROM login_attempts')

def test_cross_origin_posts_are_rejected():
    c=TestClient(app)
    assert c.post('/api/auth/login',headers={'Origin':'https://other.example'},json={'username':'test-user','password':'test-only-password'}).status_code==403
    login(c)
    assert c.post('/api/tasks',headers={'Origin':'https://other.example'},json={'name':'csrf'}).status_code==403
    assert c.post('/api/auth/logout',headers={'Origin':'https://other.example'}).status_code==403

def test_password_change_revokes_previous_session(tmp_path,monkeypatch):
    from backend.auth import hash_password
    import json
    c=TestClient(app);login(c)
    path=tmp_path/'auth.toml';path.write_text('[auth]\nusername="test-user"\npassword_hash='+json.dumps(hash_password('different-password')),encoding='utf-8')
    monkeypatch.setenv('CAIHE_AUTH_FILE',str(path))
    assert c.get('/api/tasks').status_code==401

def test_invalid_login_body_redacts_password():
    c=TestClient(app);r=c.post('/api/auth/login',json={'username':[],'password':'private-input'})
    assert r.status_code==400 and 'private-input' not in r.text
