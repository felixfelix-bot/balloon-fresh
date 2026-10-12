"""Find the spec rows by smallest element whose innerText startsWith the heading."""
import json, sys
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

JS = r"""
() => {
  const out = {};
  const headingEl = (h) => {
    let best=null;
    document.querySelectorAll('*').forEach(e=>{
      const t=(e.innerText||'').trim();
      if(!t.startsWith(h)) return;
      if(t.length>120) return;                 // keep it row-sized
      if(!best || t.length < (best.innerText||'').trim().length) best=e;
    });
    return best;
  };
  ['Layers','PCB Thickness','Different Design','PCB Qty','Dimensions','Outer Copper Weight','Via Covering','Surface Finish','Delivery Format','Base Material'].forEach(h=>{
    const e = headingEl(h);
    if(!e){ out[h]={err:'NOT FOUND'}; return; }
    // climb until the block also contains siblings/options
    let p=e;
    for(let i=0;i<3&&p;i++) p=p.parentElement;
    out[h] = {tag:e.tagName, cls:e.className, txt:(e.innerText||'').trim(), block:(p?p.outerHTML.slice(0,2200):'')};
  });
  return out;
}
"""
with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    d = pg.evaluate(JS)
    for k,v in d.items():
        print("=====", k, json.dumps({kk:vv for kk,vv in v.items() if kk!='block'}))
        print(v.get('block','')[:2000])
        print()
