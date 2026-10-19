"""Single-account authentication with server-side sessions and hashed credentials."""
import getpass
import hashlib
import hmac
import json
import os
import secrets
import time
import tomllib
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Request
from fastapi.responses import JSONResponse

COOKIE='caihe_session'
ROOT=Path(__file__).resolve().parents[1]

def hash_password(password):
    salt=secrets.token_hex(16);rounds=260000
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),rounds).hex()
    return f'pbkdf2_sha256${rounds}${salt}${digest}'

def auth_config():
    try:
        raw=tomllib.loads(Path(os.getenv('CAIHE_AUTH_FILE',str(ROOT/'auth.local.toml'))).read_text(encoding='utf-8-sig'))['auth']
        username=raw['username'];encoded=raw['password_hash'];hours=raw.get('session_hours',8)
        algorithm,rounds,salt,digest=encoded.split('$')
        if not isinstance(username,str) or not 1<=len(username)<=100 or algorithm!='pbkdf2_sha256' or not 200000<=int(rounds)<=1000000 or len(salt)!=32 or len(digest)!=64 or type(hours) is not int or not 1<=hours<=24:raise ValueError()
        bytes.fromhex(salt);bytes.fromhex(digest)
        return username,encoded,hours
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        raise ValueError('登录配置不可用，请检查 auth.local.toml') from None

def fingerprint(username,encoded):return hashlib.sha256((username+'\0'+encoded).encode()).hexdigest()
def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()

def session_user(request,db):
    token=request.cookies.get(COOKIE,'')
    if not token or len(token)>200:return None
    try:username,encoded,_=auth_config()
    except ValueError:return None
    with db() as con:
        row=con.execute('SELECT username,expires,credential FROM sessions WHERE token_hash=?',(token_hash(token),)).fetchone()
    if row and row['expires']>time.time() and hmac.compare_digest(row['credential'],fingerprint(username,encoded)):
        return row['username']
    return None

def same_origin(request):
    origin=request.headers.get('origin')
    if not origin:return True
    try:
        url=urlsplit(origin)
        return url.scheme==request.url.scheme and url.netloc==request.url.netloc
    except ValueError:return False

def install_auth(app,db):
    with db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, username TEXT, expires REAL, credential TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS login_attempts (address TEXT PRIMARY KEY, count INTEGER, expires REAL)')

    @app.get('/api/health')
    def health():return {'status':'ok','service':'caihe-assistant'}

    @app.get('/api/auth/session')
    def current(request:Request):
        username=session_user(request,db)
        return {'authenticated':bool(username),'username':username}

    @app.post('/api/auth/login')
    async def login(request:Request):
        if not same_origin(request):return JSONResponse({'detail':'请求来源无效'},403)
        address=request.client.host if request.client else 'local'
        with db() as con:
            row=con.execute('SELECT count,expires FROM login_attempts WHERE address=?',(address,)).fetchone()
        if row and row['expires']>time.time() and row['count']>=5:
            return JSONResponse({'detail':'登录尝试过于频繁，请 5 分钟后重试'},429)
        try:
            body=await request.body()
            if len(body)>4096:raise ValueError()
            data=json.loads(body);user=data['username'];password=data['password']
            if not isinstance(user,str) or not isinstance(password,str) or len(user)>100 or len(password)>256:raise ValueError()
        except (ValueError,KeyError,TypeError):return JSONResponse({'detail':'请输入有效的账号和密码'},400)
        try:expected,encoded,hours=auth_config()
        except ValueError as exc:return JSONResponse({'detail':str(exc)},503)
        _,rounds,salt,digest=encoded.split('$')
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),int(rounds)).hex()
        valid=hmac.compare_digest(actual,digest) and hmac.compare_digest(user.encode(),expected.encode())
        if not valid:
            count=row['count']+1 if row and row['expires']>time.time() else 1
            with db() as con:con.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)',(address,count,time.time()+300))
            return JSONResponse({'detail':'账号或密码错误'},401)
        token=secrets.token_urlsafe(32);expires=time.time()+hours*3600
        with db() as con:
            con.execute('DELETE FROM login_attempts WHERE address=?',(address,))
            con.execute('DELETE FROM sessions WHERE expires<=?',(time.time(),))
            old=request.cookies.get(COOKIE)
            if old:con.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(old),))
            con.execute('INSERT INTO sessions VALUES (?,?,?,?)',(token_hash(token),expected,expires,fingerprint(expected,encoded)))
        response=JSONResponse({'authenticated':True,'username':expected})
        response.set_cookie(COOKIE,token,max_age=hours*3600,httponly=True,samesite='strict',secure=request.url.scheme=='https',path='/')
        response.headers['Cache-Control']='no-store'
        return response

    @app.post('/api/auth/logout')
    def logout(request:Request):
        if not same_origin(request):return JSONResponse({'detail':'请求来源无效'},403)
        token=request.cookies.get(COOKIE)
        if token:
            with db() as con:con.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(token),))
        response=JSONResponse({'authenticated':False});response.delete_cookie(COOKIE,path='/');return response

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Configure the local login account')
    parser.add_argument('--username',required=True);args=parser.parse_args()
    password=getpass.getpass('Password: ')
    if not password or password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords must match and cannot be empty')
    target=Path(os.getenv('CAIHE_AUTH_FILE',str(ROOT/'auth.local.toml')))
    target.write_text('[auth]\nusername = '+json.dumps(args.username)+'\npassword_hash = '+json.dumps(hash_password(password))+'\nsession_hours = 8\n',encoding='utf-8')
    print('Local authentication configuration saved. Existing sessions will expire.')
