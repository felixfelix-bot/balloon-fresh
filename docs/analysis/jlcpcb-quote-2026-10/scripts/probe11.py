"""Focused: after Layers=2 and Surface Finish=LeadFree HASL, is 0.6mm enabled?  (fresh loads)"""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

FINDRECT = r"""
([h,l]) => { let row=null;
  document.querySelectorAll('div.main-btn-group').forEach(r=>{
    const lab=r.querySelector('label');
    if(lab && (lab.innerText||'').trim().startsWith(h)) row=r; });
  if(!row) return {err:'no row'};
  const norm=b=>(b.innerText||'').trim().replace(/\s+/g,' ');
  const t=[...row.querySelectorAll('button')].find(b=>norm(b)===l);
  if(!t) return {err:'no option', have:[...row.querySelectorAll('button')].map(norm)};
  if(t.disabled) return {err:'DISABLED', heading:h, option:l};
  const bb=t.getBoundingClientRect();
  return {x:bb.x+bb.width/2, y:bb.y+bb.height/2}; }
"""
SETIN = r"""
([sel,v]) => { const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  const el=document.querySelector(sel); if(!el) return 'MISSING';
  el.focus(); s.call(el,String(v)); el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true})); el.blur(); return el.value; }
"""
def thick(pg):
    return pg.evaluate(r"""
    () => { let row=null;
      document.querySelectorAll('div.main-btn-group').forEach(r=>{
        const lab=r.querySelector('label');
        if(lab && (lab.innerText||'').trim().startsWith('PCB Thickness')) row=r; });
      return row?[...row.querySelectorAll('button')].map(b=>b.innerText.trim()+(b.disabled?'(X)':'')+(/cur/.test(b.className)?'*':'')):null; }""")
def cur(pg,h):
    return pg.evaluate(r"""
    (h) => { let row=null;
      document.querySelectorAll('div.main-btn-group').forEach(r=>{
        const lab=r.querySelector('label');
        if(lab && (lab.innerText||'').trim().startsWith(h)) row=r; });
      const c=row?row.querySelector('button.cur'):null; return c?c.innerText.trim().replace(/\s+/g,' '):null; }""",h)
def click(pg,h,l):
    r=pg.evaluate(FINDRECT,[h,l])
    if 'err' in r: return r
    pg.mouse.click(r['x'],r['y']); time.sleep(3)
    return {"clicked":l,"now":cur(pg,h)}

with browser(headless=True) as pg0:
    ctx=pg0.context
    for x in (89, 100, 103):
        pg=ctx.new_page(); pg.set_viewport_size({"width":1500,"height":1600})
        _goto(pg,QUOTE_URL,settle=18); time.sleep(2)
        rec={"dims":x}
        rec["set_x"]=pg.evaluate(SETIN,["input[name=stencilLength]",x]); time.sleep(1)
        rec["set_y"]=pg.evaluate(SETIN,["input[name=stencilWidth]",x]); time.sleep(3)
        rec["layers_click"]=click(pg,"Layers","2")
        rec["surf_click"]=click(pg,"Surface Finish","LeadFree HASL")
        time.sleep(3)
        rec["layers"]=cur(pg,"Layers"); rec["surf"]=cur(pg,"Surface Finish")
        rec["thick"]=thick(pg)
        print(json.dumps(rec))
        pg.close()
