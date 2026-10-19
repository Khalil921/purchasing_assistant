import {defineConfig} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pbkdf2Sync,randomBytes} from 'node:crypto';
const root=resolve(process.cwd(),'..');
const storage=resolve(root,'test-results',`e2e-${Date.now()}`);
mkdirSync(storage,{recursive:true});
writeFileSync(resolve(storage,'config.toml'),'[model]\n');
const salt=randomBytes(16).toString('hex');
const digest=pbkdf2Sync('e2e-only-password',salt,260000,32,'sha256').toString('hex');
writeFileSync(resolve(storage,'auth.local.toml'),`[auth]\nusername="OS-HUBU"\npassword_hash="pbkdf2_sha256$260000$${salt}$${digest}"\n`);
export default defineConfig({
 testDir:'./e2e',workers:1,
 use:{baseURL:'http://127.0.0.1:8001',viewport:{width:1366,height:900}},
 webServer:{command:`"${resolve(root,'.venv/Scripts/python.exe')}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8001`,cwd:root,url:'http://127.0.0.1:8001/api/health',reuseExistingServer:false,timeout:30000,stdout:'ignore',stderr:'ignore',env:{DATA_DIR:storage,CAIHE_AUTH_FILE:resolve(storage,'auth.local.toml'),CAIHE_CONFIG_FILE:resolve(storage,'config.toml'),MODEL_API_KEY:'',DEEPSEEK_API_KEY:''}},
});
