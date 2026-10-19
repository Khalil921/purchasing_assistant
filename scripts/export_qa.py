from pathlib import Path
import os
import json
import tempfile
import secrets
from fastapi.testclient import TestClient
from backend.auth import hash_password

out=Path('test-results');out.mkdir(exist_ok=True)
storage=tempfile.TemporaryDirectory(prefix='caihe-artifact-qa-')
folder=Path(storage.name);password=secrets.token_urlsafe(24)
(folder/'config.toml').write_text('[model]\n',encoding='utf-8')
(folder/'auth.toml').write_text('[auth]\nusername="qa-user"\npassword_hash='+json.dumps(hash_password(password)),encoding='utf-8')
os.environ.update(DATA_DIR=storage.name,CAIHE_CONFIG_FILE=str(folder/'config.toml'),CAIHE_AUTH_FILE=str(folder/'auth.toml'),MODEL_API_KEY='',DEEPSEEK_API_KEY='')
from backend.main import app
c=TestClient(app)
c.post('/api/auth/login',json={'username':'qa-user','password':password}).raise_for_status()
for group in ['A','B']:
    t=c.post('/api/samples/'+group).json()
    c.post(f"/api/tasks/{t['id']}/confirm-fields")
    c.post(f"/api/tasks/{t['id']}/audit")
    (out/f'report-{group}.docx').write_bytes(c.get(f"/api/tasks/{t['id']}/report").content)
    import zipfile,io
    z=zipfile.ZipFile(io.BytesIO(c.get(f'/api/samples/{group}/download').content))
    z.extractall(out/group)
print('Generated sample files and reports for visual QA')
import logging
logging.shutdown()
storage.cleanup()
