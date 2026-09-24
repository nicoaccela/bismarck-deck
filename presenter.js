/* Presenter hook, injected by server.py only when the deck is opened with a valid
   ?presenter= key. Mirrors the deck's "Mark shown" ticks to every phone on /follow,
   and adds the audience QR card (press L, or the Phones button in the chrome). */
(function(){
if(window.__FOLLOW_P) return; window.__FOLLOW_P=true;
const FOLLOW_URL=__FOLLOW_URL__;
const LSD="bis-demo-done-v1", EPK="bis-follow-epoch", PUB="bis-follow-publish";
const J=(k,d)=>{ try{ const v=JSON.parse(localStorage.getItem(k)||"null"); return v==null?d:v; }catch(e){ return d; } };

// keep the key out of the address bar (the projector shows it); the cookie keeps presenter mode on reload
try{ const u=new URL(location.href); if(u.searchParams.has("presenter")){ u.searchParams.delete("presenter"); history.replaceState(null,"",u.pathname+(u.search||"")+u.hash); } }catch(e){}

function readDone(){
  let d=J(LSD,null);
  if(!d||typeof d!=="object"){ try{ d=DONE; }catch(e){ d={}; } }
  return Object.keys(d||{}).filter(k=>d[k]&&/^Q\d{1,2}$/.test(k)).sort();
}
function setLocal(list){
  const o={}; list.forEach(q=>o[q]=true);
  try{ DONE=o; saveLS(); }catch(e){ try{ localStorage.setItem(LSD,JSON.stringify(o)); }catch(_){} }
  try{ refreshDemo(); }catch(e){}
}
function curCh(){ try{ const s=SCENES[cur]; return (s&&s.t==="chapter"&&typeof s.ch==="number")?s.ch:null; }catch(e){ return null; } }
function links(){
  const o={}; if(localStorage.getItem(PUB)!=="1") return o;
  try{ Object.keys(DEMO_LINKS).forEach(q=>{ if(!/^Q\d{1,2}$/.test(q)) return; const u=linkFor(q); if(/^https?:\/\//.test(u)) o[q]=u; }); }catch(e){}
  return o;
}

let epoch=null, last="", ready=false, busy=false, info={}, myRev=-1;
async function api(method,path,body){
  const r=await fetch(path,{method,cache:"no-store",credentials:"same-origin",headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});
  return {status:r.status, json:await r.json().catch(()=>({}))};
}
async function boot(){
  try{
    const {json:s}=await api("GET","/api/state");
    const known=localStorage.getItem(EPK);
    if(known!==null && +known!==s.epoch) setLocal([]);          // a reset happened since this browser last synced
    const local=readDone(), u=[...new Set([...local,...(s.done||[])])].sort();
    if(u.length!==local.length) setLocal(u);                     // never wipe the phones by opening a fresh browser
    epoch=s.epoch; localStorage.setItem(EPK,String(epoch)); info=s; ready=true; last=""; paint(); sync();
  }catch(e){ setTimeout(boot,3000); }
}
async function sync(){
  if(!ready||busy) return;
  const body={done:readDone(), ch:curCh(), slide:(typeof cur==="number"?cur:null), publish:localStorage.getItem(PUB)==="1", links:links(), epoch};
  const sig=JSON.stringify(body); if(sig===last) return;
  busy=true;
  try{
    const r=await api("POST","/api/state",body);
    if(r.status===200){ last=sig; myRev=r.json.rev; info={...info,...r.json}; paint(); }
    else if(r.status===409){ ready=false; boot(); }
    else if(r.status===403){ status("Not authorised. Reopen with ?presenter=<key>."); }
  }catch(e){ status("Offline. Retrying."); }
  busy=false;
}
async function watch(){        // notices a reset done elsewhere (curl, another tab), and the viewer count
  try{ const {json:s}=await api("GET","/api/state");
    if(ready && s.epoch!==epoch){ setLocal([]); epoch=s.epoch; localStorage.setItem(EPK,String(epoch)); last=""; }
    else if(ready && !busy && s.rev>myRev && JSON.stringify((s.done||[]).slice().sort())!==JSON.stringify(readDone())){
      myRev=s.rev; setLocal((s.done||[]).slice().sort()); }        // ticked from the presenter's phone
    info=s; paint(); }catch(e){}
}
// wrap the deck's tick redraw so a tick syncs immediately; the 1s loop is the fallback
try{ const _r=refreshDemo; refreshDemo=function(){ const x=_r.apply(this,arguments); setTimeout(sync,0); return x; }; }catch(e){}
addEventListener("storage",e=>{ if(e.key===LSD) setTimeout(sync,0); });
// every slide change goes out straight away, so computers following along move with the presenter
try{ const _g=go; go=function(){ const x=_g.apply(this,arguments); setTimeout(sync,0); return x; }; }catch(e){}
setInterval(sync,1000); setInterval(watch,1500); boot();

/* ---- QR card -------------------------------------------------------------- */
const st=document.createElement("style");
st.textContent=`
#flcard{position:fixed;left:22px;bottom:70px;z-index:2147482001;background:#fff;border-radius:18px;padding:14px;width:250px;text-align:center;
  box-shadow:0 20px 50px rgba(13,38,58,.28);font-family:'Plus Jakarta Sans',-apple-system,'Segoe UI',sans-serif;color:#0D263A;display:none}
#flcard.on{display:block;animation:flUp .4s cubic-bezier(.2,.8,.2,1)}
@keyframes flUp{from{transform:translateY(12px)}to{transform:none}}
#flcard img{width:210px;height:210px;display:block;margin:0 auto}
#flcard b{display:block;font-size:15.5px;margin-top:8px}
#flcard .u{display:block;font-size:11.5px;color:#46606F;margin-top:3px;word-break:break-all}
#flcard .s{display:block;font-size:11.5px;font-weight:700;color:#00968C;margin-top:7px;font-variant-numeric:tabular-nums}
#flcard .x{margin-top:9px;border-top:1px solid #ECF2F6;padding-top:8px;text-align:left;font-size:11.5px;color:#46606F;display:none}
#flcard.ctl .x{display:block}
#flcard .x label{display:flex;gap:7px;align-items:center;cursor:pointer;margin:2px 0 7px}
#flcard .x button{font:inherit;font-size:11px;font-weight:700;border:1px solid #C6D4DD;background:#F6F9FB;color:#0D263A;border-radius:99px;padding:4px 10px;cursor:pointer}
#flcard .x button:hover{background:#A82E1C;border-color:#A82E1C;color:#fff}
#flcard .g{position:absolute;right:8px;top:6px;border:0;background:none;color:#7A8F9C;font-size:16px;cursor:pointer;padding:2px 6px;line-height:1}
#chrome #bfl{background:rgba(0,206,195,.14);border-color:rgba(0,206,195,.45);color:#BFF3EF}`;
document.head.appendChild(st);
const card=document.createElement("div"); card.id="flcard";
const short=FOLLOW_URL.replace(/^https?:\/\//,"");
card.innerHTML=`<button class="g" title="Presenter controls" aria-label="Presenter controls">&#8943;</button>
  <img src="/follow-qr.svg" alt="QR code for the follow-along page"><b>Follow along on your phone</b><span class="u">${short}</span><span class="s" id="fls">Connecting</span>
  <div class="x"><label><input type="checkbox" id="flpub"> Show demo links on phones</label>
  <button id="flreset">Reset all ticks</button></div>`;
document.body.appendChild(card);
const pub=card.querySelector("#flpub"); pub.checked=localStorage.getItem(PUB)==="1";
pub.onchange=()=>{ localStorage.setItem(PUB,pub.checked?"1":"0"); sync(); };
card.querySelector(".g").onclick=e=>{ e.stopPropagation(); card.classList.toggle("ctl"); };
card.querySelector("#flreset").onclick=async e=>{ e.stopPropagation();
  if(!confirm("Clear every tick in the deck and on all phones?")) return;
  try{ const r=await api("POST","/api/reset",{}); if(r.status===200){ epoch=r.json.epoch; localStorage.setItem(EPK,String(epoch)); setLocal([]); last=""; sync(); } }catch(_){} };
function status(t){ const s=card.querySelector("#fls"); if(s) s.textContent=t; }
function paint(){
  const n=(info.done||[]).length, v=info.viewers;
  status(`Live · ${n} of 20 shown`+(typeof v==="number"?` · ${v} phone${v===1?"":"s"}`:"")+(info.publish?" · links on":""));
}
function toggle(){ card.classList.toggle("on"); }
document.addEventListener("keydown",e=>{
  if(e.metaKey||e.ctrlKey||e.altKey) return;
  if(e.target&&e.target.matches&&e.target.matches("input,textarea")) return;
  if(e.key==="l"||e.key==="L"){ toggle(); e.stopPropagation(); }
},true);
function addBtn(){
  const ch=document.getElementById("chrome"); if(!ch||document.getElementById("bfl")) return;
  const b=document.createElement("button"); b.id="bfl"; b.innerHTML="Phones <kbd>L</kbd>"; b.onclick=toggle;
  const ref=document.getElementById("bh"); ref?ch.insertBefore(b,ref):ch.appendChild(b);
}
addBtn(); setTimeout(addBtn,1500);

/* ---- Q&A overlay: make its audience QR lead to the follow-along page too ---- */
// The follow page links to the Q&A portal whenever that portal is publicly reachable.
function patchQA(root){
  if(!root) return;
  root.querySelectorAll('img[src$="/qr.svg"]').forEach(i=>{ if(!i.src.endsWith("/follow-qr.svg")) i.src="/follow-qr.svg"; });
  if(root.id==="qacard"){ const b=root.querySelector("b"), s=root.querySelector("span");
    if(b&&b.textContent!=="Follow along and ask") b.textContent="Follow along and ask";
    if(s&&s.textContent!==short) s.textContent=short; }
  root.querySelectorAll(".qr .url, .mini span b").forEach(el=>{ if(el.textContent!==short) el.textContent=short; });
}
const mo=new MutationObserver(()=>{ patchQA(document.getElementById("qacard")); patchQA(document.getElementById("qaov")); });
mo.observe(document.body,{childList:true,subtree:true});
})();
