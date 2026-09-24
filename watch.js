/* Watch-live view, injected by server.py into /watch (not the presenter link).
   The slides move with the presenter and the questions tick off as the presenter
   shows them. Nothing to click. Browsing away pauses following; one click resumes.
   The editable copy lives at /follow ("My checklist"). */
(function(){
if(window.__WATCH) return; window.__WATCH=true;
let SHOWN="", FOLLOW=true, lastSlide=null, auto=false;
function mirror(list){ const o={}; (list||[]).forEach(q=>{ if(/^Q\d{1,2}$/.test(q)) o[q]=true; });
  try{ DONE=o; refreshDemo(); }catch(e){} }
try{ const _g=go; go=function(i){ const x=_g.apply(this,arguments);
  if(!auto && FOLLOW && lastSlide!=null && i!==lastSlide){ FOLLOW=false; paint(); }
  return x; }; }catch(e){}
function follow(){ if(lastSlide==null) return; try{ if(lastSlide<els.length && lastSlide!==cur){ auto=true; go(lastSlide); auto=false; } }catch(e){ auto=false; } }
const bar=document.createElement("div"); bar.id="wbar";
bar.innerHTML='<button type="button" id="wpill"></button><a id="wmine" href="/follow" target="_blank" rel="noopener">My checklist &#8599;</a>';
function paint(){ const p=bar.querySelector("#wpill"); p.className=FOLLOW?"on":"";
  p.innerHTML=lastSlide==null?"<i></i>Waiting for the presenter":(FOLLOW?"<i></i>Following the presenter":"Jump to the presenter\u2019s slide"); }
bar.addEventListener("click",e=>{ if(e.target.closest("#wpill")&&lastSlide!=null){ FOLLOW=!FOLLOW; paint(); if(FOLLOW) follow(); } });
async function poll(){
  try{ const s=await (await fetch("/api/state",{cache:"no-store",credentials:"same-origin"})).json();
    const sig=(s.done||[]).join(); if(sig!==SHOWN){ SHOWN=sig; mirror(s.done); }
    const sl=(typeof s.slide==="number")?s.slide:null;
    if(sl!==lastSlide){ lastSlide=sl; paint(); if(FOLLOW) follow(); }
  }catch(e){}
}
const st=document.createElement("style");
st.textContent=`.chreq .r[data-req]{pointer-events:none}.chreq .r[data-req] .go,.chfoot .nextch{display:none!important}
#wbar{position:fixed;right:22px;bottom:64px;z-index:2147482000;display:flex;gap:10px;align-items:center;font:600 14px 'Plus Jakarta Sans',-apple-system,'Segoe UI',sans-serif}
#wbar>*{display:flex;align-items:center;gap:9px;border:0;cursor:pointer;font:inherit;padding:10px 16px;border-radius:99px;text-decoration:none;box-shadow:0 10px 28px rgba(13,38,58,.25)}
#wpill{background:#0068BE;color:#fff}#wpill.on{background:#fff;color:#0D263A}
#wmine{background:#0D263A;color:#fff}
#wpill i{width:9px;height:9px;border-radius:50%;background:#00968C;box-shadow:0 0 0 4px rgba(0,206,195,.25);animation:wpl 1.6s ease-in-out infinite}
@keyframes wpl{50%{box-shadow:0 0 0 7px rgba(0,206,195,.08)}}`;
document.head.appendChild(st); document.body.appendChild(bar); paint();
mirror([]); setInterval(poll,1000); poll();
})();
