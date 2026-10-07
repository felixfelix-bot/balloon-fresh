"""Dump HTML of the Layers / PCB Thickness / Different Design / PCB Qty rows."""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

JS = r"""
() => {
  const out = {};
  const findHeading = (h) => {
    let hit=null;
    document.querySelectorAll('*').forEach(e=>{
      if(hit) return;
      if(e.children.length===0){
        const t=(e.textContent||'').trim();
        if(t===h || t.startsWith(h)) hit=e;
      }
    });
    if(!hit) return null;
    // climb to the row that contains clickable options
    let p=hit;
    for(let i=0;i<6&&p;i++){ p=p.parentElement;
      if(p && p.innerText && p.innerText.replace(/\s+/g,' ').length < 200) { }
      if(p && p.className && /form|row|item|spec/i.test(p.className)) break;
    }
    return hit;
  };
  ['Layers','PCB Thickness','Different Design','PCB Qty','Dimensions'].forEach(h=>{
    const e = findHeading(h);
    if(!e){ out[h]='NOT FOUND'; return; }
    let p=e; for(let i=0;i<4&&p;i++) p=p.parentElement;
    out[h] = {own: e.outerHTML.slice(0,300), block: (p?p.outerHTML.slice(0,2500):'')};
  });
  return out;
}
"""
with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    d = pg.evaluate(JS)
    for k,v in d.items():
        print("=====", k)
        if isinstance(v,str): print(v); continue
        print("OWN:", v["own"])
        print("BLOCK:", v["block"])
