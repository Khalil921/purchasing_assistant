import {useEffect,useRef,useState} from 'react';
import {Activity,Clock3,ExternalLink,Loader2,Minus} from 'lucide-react';
import Modal from './Modal';
import './progress.css';
export default function ProgressWindow({label,taskName,onOpenLogs}:{label:string;taskName?:string;onOpenLogs?:()=>void}){
 const started=useRef(Date.now());
 const [visible,setVisible]=useState(false),[collapsed,setCollapsed]=useState(false),[elapsed,setElapsed]=useState(0);
 useEffect(()=>{const delay=setTimeout(()=>setVisible(true),400);const timer=setInterval(()=>setElapsed(Math.floor((Date.now()-started.current)/1000)),1000);return()=>{clearTimeout(delay);clearInterval(timer)}},[]);
 if(!visible)return null;
 const duration=`${Math.floor(elapsed/60).toString().padStart(2,'0')}:${(elapsed%60).toString().padStart(2,'0')}`;
 function logs(){setCollapsed(true);onOpenLogs?.()}
 if(collapsed)return <aside className="progress-floating" aria-label="后台处理进度"><Loader2 className="spin" size={21}/><div><strong>{label}</strong><small>已等待 {duration} · 任务仍在处理</small></div><button onClick={()=>setCollapsed(false)}>展开</button>{onOpenLogs&&<button onClick={logs}>查看调用记录</button>}</aside>;
 return <Modal title="处理进度" variant="progress-dialog" onClose={()=>setCollapsed(true)}><section className="progress-window"><div className="progress-window-top"><span><Activity size={16}/>任务处理进度</span><button aria-label="收起进度窗" title="收起窗口，任务继续处理" onClick={()=>setCollapsed(true)}><Minus size={20}/></button></div><div className="progress-emblem"><Loader2 className="spin" size={34}/></div><h2>{label}</h2>{taskName&&<p className="progress-task">{taskName}</p>}<div className="progress-timer"><Clock3 size={16}/>已等待 <strong>{duration}</strong></div><div className="progress-indeterminate" aria-hidden="true"><span/></div><p className="progress-explanation">后端正在处理当前操作，请稍候。<br/>可打开调用记录查看请求、响应与重试情况。</p>{onOpenLogs&&<button className="primary progress-log-button" onClick={logs}><ExternalLink size={17}/>查看调用记录</button>}<p className="progress-footnote">收起窗口不会中断任务，处理结束后自动关闭。</p></section></Modal>
}
