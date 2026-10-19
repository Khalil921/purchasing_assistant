"""Build an allowlisted distribution without credentials or user data."""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tomllib
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from backend.samples import sample
from backend.rules import audit,KINDS
from backend.extract import parse,validate_evidence

tag=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
delivery=ROOT/'deliverables'
delivery.mkdir(exist_ok=True)
bundle=delivery/f'采核助手_交付_{tag}'
bundle.mkdir(exist_ok=False)
project=bundle/'采核助手项目';project.mkdir()
materials=bundle/'演示材料';materials.mkdir()

def copy_file(src,relative):
    dest=project/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dest)

root_files=['.gitignore','.env.example','config.toml','config.local.example.toml','auth.local.example.toml','requirements.txt','requirements-lock.txt','pytest.ini','start.ps1','README.md','VALIDATION.md','EXPECTED_ISSUES.md']
for name in root_files:
    if name!='config.toml':copy_file(ROOT/name,name)
for directory in ['backend','tests','scripts','frontend/src','frontend/e2e','frontend/dist']:
    for file in sorted((ROOT/directory).rglob('*')):
        if not file.is_file() or '__pycache__' in file.parts or file.suffix in ['.pyc','.pyo','.map']:continue
        if file.name.startswith('~$'):continue
        copy_file(file,file.relative_to(ROOT))
for name in ['package.json','package-lock.json','tsconfig.json','vite.config.ts','playwright.config.ts','index.html']:
    copy_file(ROOT/'frontend'/name,Path('frontend')/name)

# Write public configuration explicitly instead of copying possible local edits.
public=tomllib.loads((ROOT/'config.toml').read_text(encoding='utf-8-sig')).get('model',{})
defaults={'provider':'deepseek','api_base':'https://api.deepseek.com','name':'deepseek-flash','timeout_seconds':40,'max_attempts':2,'max_tokens':8192}
settings={k:public.get(k,v) for k,v in defaults.items()}
(project/'config.toml').write_text('# Public model settings; add your own key to config.local.toml.\n[model]\n'+'\n'.join(f'{k} = {json.dumps(v,ensure_ascii=False)}' for k,v in settings.items())+'\n',encoding='utf-8')

for group,title in [('A','A组_信息一致'),('B','B组_包含异常')]:
    folder=materials/title;folder.mkdir()
    docs=[]
    for kind in KINDS:
        path,data=sample(group,kind,folder)
        blocks=parse(path);validate_evidence(data,blocks)
        docs.append({'id':f'{group}-{kind}','kind':kind,'name':path.name,'status':'已抽取','data':data})
    result=audit(docs)
    if group=='A':assert result['status']=='通过' and not result['issues']
    else:assert {'ITEM-001','ITEM-002','MATH-001','DATE-001','FIELD-001','BASIS-001'}<={i['rule'] for i in result['issues']}
shutil.copy2(ROOT/'EXPECTED_ISSUES.md',materials/'预期问题清单.md')
(materials/'演示材料使用说明.md').write_text('''# 演示材料使用说明

本目录是独立演示材料包，不包含任何真实采购文件或 API Key。

- A组_信息一致：采购需求、供应商报价单、采购合同各一份，预期规则核对通过。
- B组_包含异常：同样三份，含型号不一致、数量差异、分项运算错误、交付冲突、缺失税费口径；共 9 条问题，详见预期问题清单。

## 方式一 无密钥演示

登录项目后点击右上角“演示中心”，在弹窗中载入 A/B 组。样例使用明确标注的预设抽取，确认字段后执行代码核对，不产生模型调用或费用。预设结果不代表模型真实准确率。AI 语义复核需单独执行，会真实请求 API，没有密钥时不可执行。

## 方式二 真实接口演示

自行在项目的 config.local.toml 中配置自己的 DeepSeek Key；新建任务，从同一组上传三份 DOCX，依次提交材料、提取、人工核对字段、交叉核对、人工处理问题和导出报告。上传文件不会套用预设结果；请在调用记录中确认真实 API 事件，必要时修正模型抽取。

每个文件上传时选择对应类型，请勿混用 A/B 两组。B 组的税费字段是故意缺失的，没有原句时应保留 null，不要人工补成已知口径。
''',encoding='utf-8')

guide=r'''# 采核助手交付包

本包包含干净项目和独立演示材料。没有原电脑的 API Key、登录凭据、采购上传文件、任务数据库或历史记录。

## 首次启动 Windows PowerShell

进入「采核助手项目」目录。已包含构建好的前端页面，直接演示需要 Python 3.11+ 与联网安装后端依赖；修改前端才需要 Node.js 20.19+。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt -i https://pypi.org/simple
.venv/Scripts/python -m backend.auth --username OS-HUBU
```

按提示输入两次你自己设置的登录密码，终端不会回显。原电脑的 auth.local.toml 没有打包。

然后启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

浏览器访问 http://127.0.0.1:8000，使用上面配置的账号密码登录。若 8000 已被其他项目占用，先停止该服务。

## 配置自己的模型密钥 可选

```powershell
Copy-Item config.local.example.toml config.local.toml
```

在新文件 [model] 下填写 api_key。默认模型地址和型号见 config.toml。无 Key 时仍能通过界面的内置样例完成演示；上传的真实文件不会被套用预设结果。

## 演示材料

「演示材料」目录含 A/B 两组共六份 DOCX、预期问题清单和使用步骤。A 组一致，B 组覆盖型号、数量、金额、交期和必要字段缺失。该目录也单独打成 ZIP 方便分发。

## 包含与排除

包含前后端源码、已构建前端页面、依赖清单、测试、说明和无密钥配置模板。不含 .venv、node_modules、缓存、测试输出、日志、数据库、真实上传、.env、config.local.toml、auth.local.toml。原电脑的文件没有被删除或改写。

详细结构与功能见项目 README；其中“本地已配置账号”等描述指原开发环境，分发包必须按本说明创建自己的登录配置。此包是项目分发包，不包含离线 Python/npm 依赖。
'''
(bundle/'开始使用.md').write_text(guide,encoding='utf-8')
(project/'交付启动说明.md').write_text(guide,encoding='utf-8')

# Read live credentials only in memory for comparison; never print or export them.
secrets=set()
for file in [ROOT/'config.local.toml',ROOT/'config.toml']:
    if file.exists():
        value=tomllib.loads(file.read_text(encoding='utf-8-sig')).get('model',{}).get('api_key','')
        if isinstance(value,str) and value.strip():secrets.add(value.strip().encode())
env=dotenv_values(ROOT/'.env') if (ROOT/'.env').exists() else {}
for name in ['MODEL_API_KEY','DEEPSEEK_API_KEY']:
    for value in [os.getenv(name),env.get(name)]:
        if value:secrets.add(value.encode())

forbidden_dirs={'.venv','node_modules','__pycache__','.pytest_cache','test-results','data','.git','.vite'}
forbidden_names={'.env','config.local.toml','auth.local.toml'}
def check_payload(payload):
    for value in secrets:
        if value in payload:raise RuntimeError('Secret detected: package creation aborted')
    if re.search(rb'\bsk-[A-Za-z0-9_-]{20,}\b',payload):raise RuntimeError('Possible API credential detected: package creation aborted')
def inspect_file(path):
    relative=path.relative_to(bundle)
    assert not forbidden_dirs.intersection(relative.parts) and path.name not in forbidden_names
    assert path.suffix not in ['.pyc','.pyo','.db','.log','.tsbuildinfo']
    content=path.read_bytes();check_payload(content)
    if path.suffix=='.docx':
        with zipfile.ZipFile(io.BytesIO(content)) as inner:
            for item in inner.infolist():check_payload(inner.read(item))
for file in bundle.rglob('*'):
    if file.is_file():inspect_file(file)

manifest={'files':[{'path':str(f.relative_to(bundle)).replace('\\','/'),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size} for f in sorted(bundle.rglob('*')) if f.is_file()],
          'api_key_included':False,'private_login_included':False,'user_data_included':False,'sample_documents':6}
(bundle/'文件清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

archives=[]
for label,source in [('完整项目与演示材料',bundle),('项目源码',project),('演示材料',materials)]:
    archive=delivery/f'采核助手_{label}_{tag}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in sorted(source.rglob('*')):
            if file.is_file():z.write(file,Path(source.name)/file.relative_to(source))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for item in z.infolist():
            check_payload(z.read(item))
            assert not forbidden_dirs.intersection(Path(item.filename).parts) and Path(item.filename).name not in forbidden_names
    archives.append({'name':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
(delivery/f'打包检查_{tag}.json').write_text(json.dumps({'folder':str(bundle.relative_to(ROOT)),'archives':archives,'secret_scan':'passed','excluded_paths_check':'passed','zip_integrity':'passed','sample_A':'passed','sample_B':'6 expected rule types detected'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'folder':str(bundle),'archives':archives,'files':len(manifest['files']),'sample_documents':6,'checks':'passed'},ensure_ascii=False))
