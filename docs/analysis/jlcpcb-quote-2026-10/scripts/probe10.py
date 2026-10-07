"""Probe when each PCB Thickness option is ENABLED, as a function of (layers, surface finish, dims)."""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

FINDRECT = r"""
([h, l]) => {
  let row=null;
  document.querySelectorAll('div.main-btn-group').forEach(r=>{
    const lab=r.querySelector('label');
    if(lab && (lab.innerText||'').trim().startsWith(h)) row=r;
  });
  if(!row) return {err:'no row'};
  const btns=[...row.querySelectorAll('button')];
  const norm=b=>(b.innerText||'').trim().replace(/\s+/g,' ');
  const t=btns.find(b=>norm(b)===l);
  if(!t) return {err:'no option', have:btns.map(norm)};
  if(t.disabled) return {err:'DISABLED'};
  const bb=t.getBoundingClientRect();
  return {x: bb.x+bb.width/2, y: bb.y+bb.height/2};
}
"""
SETIN = r"""
([sel,v]) => { const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  const el=document.querySelector(sel); if(!el) return 'MISSING';
  el.focus(); s.call(el,String(v));
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true})); el.blur(); return el.value; }
"""
def thick_states(pg):
    return pg.evaluate(r"""
    () => { let row=null;
      document.querySelectorAll('div.main-btn-group').forEach(r=>{
        const lab=r.querySelector('label');
        if(lab && (lab.innerText||'').trim().startsWith('PCB Thickness')) row=r; });
      if(!row) return null;
      return [...row.querySelectorAll('button')].map(b=>({t:b.innerText.trim(),
              dis:b.disabled, cur:/cur/.test(b.className)})); }""")
def cur(pg,h):
    return pg.evaluate(r"""
    (h) => { let row=null;
      document.querySelectorAll('div.main-btn-group').forEach(r=>{
        const lab=r.querySelector('label');
        if(lab && (lab.innerText||'').trim().startsWith(h)) row=r; });
      const c = row?row.querySelector('button.cur'):null;
      return c?c.innerText.trim().replace(/\s+/g,' '):null; }""", h)
def click(pg,h,l):
    r = pg.evaluate(FINDRECT,[h,l])
    if 'err' in r: return r
    pg.mouse.click(r['x'],r['y']); time.sleep(3)
    return {"clicked": l, "now": cur(pg,h)}

def newpg(ctx, x, y):
    pg = ctx.new_page(); pg.set_viewport_size({"width":1500,"height":1600})
    _goto(pg, QUOTE_URL, settle=18); time.sleep(2)
    pg.evaluate(SETIN,["input[name=stencilLength]",x]); time.sleep(1)
    pg.evaluate(SETIN,["input[name=stencilWidth]",y]); time.sleep(3)
    return pg

report = []
with browser(headless=True) as pg0:
    ctx = pg0.context
    for (x, lay, surf) in [(89,None,None),(89,"2","LeadFree HASL"),(89,"4","ENIG"),
                           (103,"2","LeadFree HASL"),(103,"4","ENIG"),
                           (103,"2","HASL(with lead)"),(103,"4","HASL(with lead)"),
                           (103,"2",None),(103,"4",None)]:
        pg = newpg(ctx,x,x)
        rec = {"dims":x,"target_layers":lay,"target_surf":surf,
               "pristine_layers":cur(pg,"Layers"),"pristine_surf":cur(pg,"Surface Finish"),
               "pristine_thick":thick_states(pg)}
        if surf: rec["set_surf"] = click(pg,"Surface Finish",surf)
        if lay:  rec["set_layers"] = click(pg,"Layers",lay)
        time.sleep(3)
        rec["after_surf"] = cur(pg,"Surface Finish")
        rec["after_layers"] = cur(pg,"Layers")
        rec["thick_states"] = thick_states(pg)
        report.append(rec)
        print(json.dumps(rec))
        pg.close()
json.dump(report, open("/home/c03rad0r/quote-scratch/probe10_report.json","w"), indent=2)
