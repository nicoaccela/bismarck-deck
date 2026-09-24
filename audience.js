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
async function poll(){
  try{ const s=await (await fetch("/api/state",{cache:"no-store",credentials:"same-origin"})).json();
    const n=new Set(s.done||[]); if([...n].join()!==[...SHOWN].join()){ SHOWN=n; relabel(); } }catch(e){}
}
fromMine(); try{ refreshDemo(); }catch(e){}
setInterval(poll,2500); poll();
const st=document.createElement("style");
st.textContent=`.chreq .r[data-req]{cursor:pointer}
.chreq .r[data-req].lshown .qn::after{content:"Shown";display:block;margin-top:4px;font-size:9.5px;font-weight:800;letter-spacing:.06em;
  text-transform:uppercase;color:#fff;background:#0068BE;border-radius:99px;padding:1px 6px;text-align:center;width:max-content}
.chfoot .nextch{display:none!important}`;
document.head.appendChild(st);
})();
