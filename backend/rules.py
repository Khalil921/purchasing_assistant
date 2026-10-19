import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from itertools import combinations

KINDS = ['采购需求', '供应商报价单', '采购合同']
LABELS={'buyer':'采购方','supplier':'供应商','subject':'采购事项','total':'总金额','currency':'币种','tax':'税费口径','delivery':'交付要求','name':'产品名称','model':'型号','quantity':'数量','unit':'单位','price':'单价','amount':'分项金额'}

def norm(v):
    return re.sub(r'[\s\-_/（）()]', '', str(v or '')).casefold()

def number(v):
    try:
        if len(str(v))>80: return None
        n = Decimal(str(v).replace(',', ''))
        return n if n.is_finite() and n >= 0 and n <= Decimal('1e24') and n.as_tuple().exponent >= -12 else None
    except (InvalidOperation, ValueError):
        return None

def date_range(text):
    text = text or ''
    m = re.search(r'(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})', text)
    if not m: return None
    try: d = date(*map(int, m.groups()))
    except ValueError: return None
    if re.search(r'最晚|不晚于|之前|前交|截至', text): return (date.min, d)
    if re.search(r'后|内|工作日', text): return None
    return (d, d)

def matching(a, b):
    am, bm = a['model']['value'], b['model']['value']
    an, bn = a['name']['value'], b['name']['value']
    if am and bm and norm(am) == norm(bm): return '可靠'
    if an and bn and norm(an) == norm(bn): return '可靠'
    return '待确认'

def audit(documents, tolerance='0.01'):
    with localcontext() as ctx:
        ctx.prec=80
        return _audit(documents,tolerance)

def _audit(documents, tolerance='0.01'):
    tol = number(tolerance)
    if tol is None: raise ValueError('金额误差必须为非负有限数值')
    issues, checks = [], []
    def add(rule, typ, fields, refs, explanation, severity='高'):
        issues.append(dict(id=f'I{len(issues)+1:03}', rule=rule, type=typ, severity=severity,
            fields=fields, evidence=refs, explanation=explanation,
            suggestion='请核对原文并联系采购经办人或供应商确认，修正后重新审核。', status='待处理', note=''))
    def ev(d, field, obj=None):
        f = (obj or d['data'])[field]
        return dict(document_id=d['id'], document=d['name'], field=field, **f)
    for kind in KINDS:
        ds = [d for d in documents if d['kind']==kind]
        if not ds: add('DOC-001','材料缺项',[kind],[],f'未上传{kind}')
    ready = [d for d in documents if d['status']=='已抽取' and d.get('data')]
    for d in documents:
        if d not in ready:
            checks.append(dict(rule='EXT-001',status='抽取失败' if d['status']=='抽取失败' else '未检查',detail=f"{d['name']}：{d.get('error') or d['status']}；该文档字段和交叉检查未完成"))
    for d in ready:
        x=d['data']
        required=['buyer','subject','delivery'] + ([] if d['kind']=='采购需求' else ['supplier','total','currency','tax'])
        for f in required:
            if not x[f]['value']: add('FIELD-001','字段缺失',[f],[ev(d,f)],f"{d['kind']}未获取必要字段：{LABELS[f]}")
        if not x['items']: add('FIELD-001','字段缺失',['items'],[],f"{d['name']}未获取商品条目")
        for item in x['items']:
            for f in ['name','model','quantity','unit'] + ([] if d['kind']=='采购需求' else ['price','amount']):
                if not item[f]['value']: add('FIELD-001','字段缺失',[f],[ev(d,f,item)],f"{d['name']}商品必要字段 {LABELS[f]} 未获取")
            if d['kind']=='采购需求': continue
            q,p,a=[number(item[f]['value']) for f in ['quantity','price','amount']]
            if None in (q,p,a):
                checks.append(dict(rule='MATH-001',status='未检查',detail=f"{d['name']}分项数值缺失或无效"))
            elif abs(q*p-a)>tol: add('MATH-001','金额计算错误',['quantity','price','amount'],[ev(d,f,item) for f in ['quantity','price','amount']],f'数量 × 单价 = {q*p}，分项金额为 {a}，误差超过 {tol}')
        if d['kind']!='采购需求':
            amounts=[number(i['amount']['value']) for i in x['items']]; total=number(x['total']['value'])
            if amounts and None not in amounts and total is not None:
                if abs(sum(amounts)-total)>tol: add('MATH-002','金额计算错误',['total'],[ev(d,'total')]+[ev(d,'amount',i) for i in x['items']],f'分项合计 {sum(amounts)} 与总金额 {total} 不一致')
            else: checks.append(dict(rule='MATH-002',status='未检查',detail=f"{d['name']}金额缺失或无效"))
    for a,b in combinations(ready,2):
        if a['kind']==b['kind']: continue
        x,y=a['data'],b['data']
        if a['kind']!='采购需求' and b['kind']!='采购需求':
            if x['supplier']['value'] and y['supplier']['value'] and norm(x['supplier']['value'])!=norm(y['supplier']['value']): add('PARTY-001','供应商差异',['supplier'],[ev(a,'supplier'),ev(b,'supplier')],'报价和合同的供应商不同')
            units_a=[norm(i['unit']['value']) for i in x['items']]
            units_b=[norm(i['unit']['value']) for i in y['items']]
            basis=all(x[f]['value'] and y[f]['value'] and norm(x[f]['value'])==norm(y[f]['value']) for f in ['currency','tax']) and units_a and units_b and all(units_a) and sorted(units_a)==sorted(units_b)
            va,vb=number(x['total']['value']),number(y['total']['value'])
            if basis and va is not None and vb is not None and abs(va-vb)>tol:
                add('TOTAL-001','金额差异',['total'],[ev(a,'total'),ev(b,'total'),ev(a,'currency'),ev(b,'currency'),ev(a,'tax'),ev(b,'tax')],'同口径报价与合同总金额不一致')
        da,db=date_range(x['delivery']['value']),date_range(y['delivery']['value'])
        if da and db:
            if max(da[0],db[0])>min(da[1],db[1]): add('DATE-001','交付冲突',['delivery'],[ev(a,'delivery'),ev(b,'delivery')],'交付日期约束无交集')
        else:
            add('DATE-002','待复核',['delivery'],[ev(a,'delivery'),ev(b,'delivery')],'相对交期缺少明确基准或日期未获取，需人工确认','中')
        used=set()
        for item in x['items']:
            candidates=[(idx,j) for idx,j in enumerate(y['items']) if matching(item,j)=='可靠']
            if len(candidates)!=1 or candidates[0][0] in used:
                add('MATCH-001','匹配待确认',['name','model'],[ev(a,'name',item)]+[ev(b,'name',j) for j in y['items']], '无法唯一可靠匹配商品，未强行关联；对应商品检查未完成','中'); continue
            idx,j=candidates[0];used.add(idx)
            for f,rule,typ in [('model','ITEM-001','型号不一致'),('quantity','ITEM-002','数量差异'),('unit','ITEM-003','单位差异')]:
                v,w=item[f]['value'],j[f]['value']
                equal=(number(v)==number(w)) if f=='quantity' and number(v) is not None and number(w) is not None else norm(v)==norm(w)
                if v and w and not equal: add(rule,typ,[f],[ev(a,f,item),ev(b,f,j)],f'{a["kind"]}与{b["kind"]}的{LABELS[f]}不一致')
            if a['kind']!='采购需求' and b['kind']!='采购需求':
                refs=[ev(a,'currency'),ev(b,'currency'),ev(a,'tax'),ev(b,'tax'),ev(a,'unit',item),ev(b,'unit',j)]
                comparable=all(x[f]['value'] and y[f]['value'] and norm(x[f]['value'])==norm(y[f]['value']) for f in ['currency','tax']) and item['unit']['value'] and norm(item['unit']['value'])==norm(j['unit']['value'])
                if not comparable: add('BASIS-001','待复核',['currency','tax','unit'],refs,'币种、单位或税费口径不明或不一致，未直接比较金额','中')
                else:
                    for f in ['price','amount']:
                        v,w=number(item[f]['value']),number(j[f]['value'])
                        if v is None or w is None: checks.append(dict(rule='PRICE-001',status='未检查',detail='金额未获取或无效'))
                        elif abs(v-w)>tol: add('PRICE-001','金额差异',[f],[ev(a,f,item),ev(b,f,j)],f'同口径的{LABELS[f]}不同')
        if len(used)<len(y['items']):
            add('MATCH-001','匹配待确认',['name','model'],[ev(b,'name',j) for idx,j in enumerate(y['items']) if idx not in used],f"{b['name']}存在未匹配商品；该商品交叉检查未完成，需人工确认",'中')
            checks.append(dict(rule='MATCH-001',status='未检查',detail=f"{b['name']}存在未匹配商品，需人工确认"))
    incomplete=len(ready)!=3 or len(set(d['kind'] for d in ready))!=3 or bool(checks) or any(i['type'] in ['待复核','匹配待确认'] for i in issues)
    state='发现异常' if issues else ('未检查' if incomplete else '通过')
    if documents and not ready and any(d['status']=='抽取失败' for d in documents): state='抽取失败'
    checks.append(dict(rule='SUMMARY',status=state,detail='数值、必要字段、商品及交付核对；仅覆盖已成功抽取的文档'))
    return dict(status=state,issues=issues,checks=checks,tolerance=str(tol))
