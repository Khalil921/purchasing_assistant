import {useEffect,useRef,type ReactNode} from 'react';
export default function Modal({title,onClose,children,variant=''}:{title:string;onClose:()=>void;children:ReactNode;variant?:string}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const dialog=ref.current!;dialog.showModal();return()=>dialog.close()},[]);
 return <dialog ref={ref} className={`layer-dialog ${variant}`} aria-label={title} onCancel={e=>{e.preventDefault();onClose()}} onClick={e=>{if(e.target===e.currentTarget){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose()}}}>{children}</dialog>
}
