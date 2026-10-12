"""Dump the PCB Thickness row and PCB Qty input; also the pristine default selections."""
import json, sys
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

JS = r"""
() => {
  const out = {};
  // every element whose own text is exactly 'PCB Thickness'
  out.hits = [];
  document.querySelectorAll('*').forEach(e=>{
    const t=(e.innerText||'').trim();
    if(t==='PCB Thickness'){
      out.hits.push({tag:e.tagName, cls:e.className, outer:e.outerHTML.slice(0,200)});
      // climb 3 up and show
      let p=e; const chain=[];
      for(let i=0;i<4&&p;i++){ p=p.parentElement; if(p) chain.push(p.className+' :: '+(p.innerText||'').replace(/\s+/g,' ').slice(0,150)); }
      out.chain = chain;
    }
  });
  // find the block with buttons whose text contains 'mm'
  const blocks=[];
  document.querySelectorAll('div').forEach(d=>{
    const btns=[...d.querySelectorAll('button')];
    if(btns.length>=5 && btns.some(b=>/^1\.6mm$/.test((b.innerText||'').trim()))){
      blocks.push({cls:d.className, txt:(d.innerText||'').replace(/\s+/g,' ').slice(0,200),
                   btns:btns.map(b=>b.innerText.trim().replace(/\s+/g,' ')), html:d.outerHTML.slice(0,900)});
    }
  });
  out.thicknessBlocks = blocks.slice(-3);
  // qty input
  const qh=[]; document.querySelectorAll('*').forEach(e=>{
    if((e.innerText||'').trim()==='PCB Qty'){
      let p=e; for(let i=0;i<4&&p;i++){p=p.parentElement;
        if(p && p.querySelector('input')) { qh.push({cls:p.className, html:p.outerHTML.slice(0,700)}); break; } }
    }});
  out.qty = qh.slice(0,2);
  return out;
}
"""
JS_SEL = r"""
() => {
  const res={};
  [...document.querySelectorAll('div.main-btn-group')].forEach(r=>{
    const lab=r.querySelector('label'); if(!lab) return;
    const h=(lab.innerText||'').trim().split('\n')[0];
    const cur=r.querySelector('button.cur'); if(cur) res[h]=cur.innerText.trim();
  });
  return res;
}
"""
with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    d = pg.evaluate(JS)
    print(json.dumps(d, indent=1)[:5000])
    print("=== PRISTINE SELECTED ===")
    print(json.dumps(pg.evaluate(JS_SEL), indent=1))
