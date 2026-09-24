/* Audience hook, injected by server.py into the public deck (not the presenter link).
   Clicking a question row checks it off as "seen" for this viewer only. It shares its
   check marks with the phone page (/follow) in the same browser, and marks what the
   presenter has shown live with a "Shown" badge. Nothing is sent to the server. */
(function(){
if(window.__AUD) return; window.__AUD=true;
const MK="bis-follow-mine-v1";
const getMine=()=>{ try{ return JSON.parse(localStorage.getItem(MK)||"{}")||{}; }catch(e){ return {}; } };
let SHOWN=new Set();
function fromMine(){ const m=getMine(), o={}; Object.keys(m).forEach(q=>{ if(/^Q\d{1,2}$/.test(q)) o[q]=true; }); try{ DONE=o; }catch(e){} }
function toMine(){ const o={}; try{ Object.keys(DONE).forEach(q=>{ if(DONE[q]) o[q]=1; }); }catch(e){} try{ localStorage.setItem(MK,JSON.stringify(o)); }catch(e){} }
function relabel(){
  document.querySelectorAll("#stage .chreq .r[data-req]").forEach(r=>{
    const q=r.dataset.req, g=r.querySelector(".go"), done=r.classList.contains("done");
    if(g && !/live/.test(g.className)) g.textContent=done?"Seen \u2713":"Mark as seen";
    r.classList.toggle("lshown",SHOWN.has(q));
  });
  document.querySelectorAll("#stage [data-chprog]").forEach(el=>{ el.textContent=el.textContent.replace(/shown/g,"seen"); });
}
try{ const _r=refreshDemo; refreshDemo=function(){ const x=_r.apply(this,arguments); toMine(); relabel(); return x; }; }catch(e){}
addEventListener("storage",e=>{ if(e.key===MK){ fromMine(); try{ refreshDemo(); }catch(_){} } });
/* ---- follow the presenter's slide ---- */
let FOLLOW=true, lastSlide=null, auto=false;
try{ const _g=go; go=function(i){ const x=_g.apply(this,arguments);
  if(!auto && FOLLOW && lastSlide!=null && i!==lastSlide){ FOLLOW=false; paintPill(); }     // viewer browsed away
  return x; }; }catch(e){}
function follow(){ if(lastSlide==null) return; try{ if(lastSlide<els.length && lastSlide!==cur){ auto=true; go(lastSlide); auto=false; } }catch(e){ auto=false; } }
const pill=document.createElement("button"); pill.id="fpill"; pill.type="button";
pill.onclick=()=>{ FOLLOW=!FOLLOW; paintPill(); if(FOLLOW) follow(); };
function paintPill(){ pill.hidden=lastSlide==null; pill.className=FOLLOW?"on":"";
  pill.innerHTML=FOLLOW?"<i></i>Following the presenter":"Jump to the presenter\u2019s slide"; }
async function poll(){
  try{ const s=await (await fetch("/api/state",{cache:"no-store",credentials:"same-origin"})).json();
    const n=new Set(s.done||[]); if([...n].join()!==[...SHOWN].join()){ SHOWN=n; relabel(); }
    const sl=(typeof s.slide==="number")?s.slide:null;
    if(sl!==lastSlide){ lastSlide=sl; paintPill(); if(FOLLOW) follow(); }
  }catch(e){}
}
fromMine(); try{ refreshDemo(); }catch(e){}
setInterval(poll,1000); poll(); document.body.appendChild(pill); paintPill();
const st=document.createElement("style");
st.textContent=`.chreq .r[data-req]{cursor:pointer}
.chreq .r[data-req].lshown .qn::after{content:"Shown";display:block;margin-top:4px;font-size:9.5px;font-weight:800;letter-spacing:.06em;
  text-transform:uppercase;color:#fff;background:#0068BE;border-radius:99px;padding:1px 6px;text-align:center;width:max-content}
.chfoot .nextch{display:none!important}
#fpill{position:fixed;right:22px;bottom:64px;z-index:2147482000;display:flex;align-items:center;gap:9px;border:0;cursor:pointer;
  font:600 14px 'Plus Jakarta Sans',-apple-system,'Segoe UI',sans-serif;padding:10px 16px;border-radius:99px;
  background:#0068BE;color:#fff;box-shadow:0 10px 28px rgba(13,38,58,.25)}
#fpill.on{background:#fff;color:#0D263A}
#fpill i{width:9px;height:9px;border-radius:50%;background:#00968C;box-shadow:0 0 0 4px rgba(0,206,195,.25);animation:fpl 1.6s ease-in-out infinite}
@keyframes fpl{50%{box-shadow:0 0 0 7px rgba(0,206,195,.08)}}
#fpill[hidden]{display:none}`;
document.head.appendChild(st);
})();
