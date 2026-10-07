"""Dump the price panel structure (labels -> values) so we can read charge lines reliably."""
import json, sys, time, re
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

JS = r"""
(() => {
  // find the container that holds 'Calculated Price'
  let node = null;
  document.querySelectorAll('*').forEach(e=>{
    if(!node && e.children.length===0 && (e.textContent||'').trim()==='Calculated Price'){
       let p=e; for(let i=0;i<6&&p;i++){p=p.parentElement; if(p&&p.querySelectorAll('.pull-right').length>=3){node=p;break;}}
    }
  });
  if(!node) return {err:'no panel'};
  const rows = [...node.querySelectorAll('.pull-right')].map(v=>{
    // walk back to find the label text in the same row
    let row=v.parentElement, lab='';
    for(let i=0;i<4&&row;i++){
      const t=(row.innerText||'').trim();
      if(t && t.length<200){ lab=t; break; }
      row=row.parentElement;
    }
    return {value:(v.textContent||'').trim(), label:lab.replace(/\n/g,' | ')};
  });
  return {html: node.outerHTML.slice(0,4000), rows};
})()
"""

with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    d = pg.evaluate(JS)
    print("ROWS:")
    for r in d.get("rows",[]):
        print("  ", json.dumps(r))
    print("--- HTML ---")
    print(d.get("html","")[:4000])
