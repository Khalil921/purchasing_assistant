import {useEffect,useState,type ReactNode,type FormEvent} from 'react';
import {ShieldCheck,ArrowRight,Eye,EyeOff,LockKeyhole,UserRound,Loader2,FileCheck2} from 'lucide-react';
import './login.css';
export default function AuthGate({children}:{children:(username:string,logout:()=>Promise<void>)=>ReactNode}){
 const [checking,setChecking]=useState(true),[user,setUser]=useState<string|null>(null),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[visible,setVisible]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{
  let active=true;
  fetch('/api/auth/session').then(async r=>{if(!r.ok)throw Error('无法连接登录服务');return r.json()}).then(x=>{if(active)setUser(x.authenticated?x.username:null)}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setChecking(false)});
  const expire=()=>{setUser(null);setPassword('');setError('登录已失效，请重新登录')};
  window.addEventListener('caihe:unauthorized',expire);
  return()=>{active=false;window.removeEventListener('caihe:unauthorized',expire)};
 },[]);
 async function login(event:FormEvent){
  event.preventDefault();setBusy(true);setError('');
  try{
   const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});
   const data=await r.json();if(!r.ok)throw Error(data.detail||'登录失败，请重试');
   setPassword('');setUser(data.username);
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 async function logout(){
  try{const r=await fetch('/api/auth/logout',{method:'POST'});if(!r.ok)throw Error('退出登录失败，请重试');setUser(null);setPassword('');setError('')}
  catch(e){window.alert((e as Error).message)}
 }
 if(checking)return <div className="session-loading"><Loader2 className="spin"/>正在检查登录状态…</div>;
 if(user)return <>{children(user,logout)}</>;
 return <main className="login-page"><section className="login-story"><a className="login-brand" href="/"><span><ShieldCheck size={28}/></span><div>采核助手<small>PROCUREMENT REVIEW</small></div></a><div className="login-story-content"><span className="login-kicker">让采购审核更清晰</span><h1>每一份材料，<br/>每一步审核，<br/><em>都有据可循。</em></h1><p>从需求、报价到合同，集中核对关键信息。<br/>让发现问题、追溯证据和人工确认连接起来。</p><div className="login-flow"><span>提交材料</span><ArrowRight size={16}/><span>交叉核对</span><ArrowRight size={16}/><span>确认与导出</span></div><div className="login-document"><FileCheck2 size={27}/><div><strong>采购审核工作空间</strong><small>文档抽取 · 规则核对 · 原文证据</small></div><ShieldCheck size={23}/></div></div><p className="login-story-foot">采核助手 · 每个结论，都有依据</p></section><section className="login-form-area"><div className="login-form-card"><div className="login-lock"><LockKeyhole size={25}/></div><span className="login-kicker">WELCOME BACK</span><h2>登录采核助手</h2><p>登录后进入你的采购审核工作台</p><form onSubmit={login}><label htmlFor="login-username">账号</label><div className="login-input"><UserRound size={19}/><input id="login-username" autoComplete="username" autoFocus placeholder="请输入账号" value={username} maxLength={100} onChange={e=>setUsername(e.target.value)} required disabled={busy}/></div><label htmlFor="login-password">密码</label><div className="login-input"><LockKeyhole size={19}/><input id="login-password" type={visible?'text':'password'} autoComplete="current-password" placeholder="请输入密码" value={password} maxLength={256} onChange={e=>setPassword(e.target.value)} required disabled={busy}/><button className="password-toggle" type="button" aria-label={visible?'隐藏密码':'显示密码'} aria-pressed={visible} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={19}/>:<Eye size={19}/>}</button></div>{error&&<div className="login-error" role="alert">{error}</div>}<button className="primary login-submit" disabled={busy||!username||!password} type="submit">{busy?<><Loader2 className="spin" size={18}/>正在登录…</>:<>登录工作台 <ArrowRight size={18}/></>}</button></form><div className="login-tip"><ShieldCheck size={16}/><span>使用已配置的账号登录，退出后将结束当前会话。</span></div></div><p className="login-footer">采购材料审核与交叉核对系统</p></section></main>
}
