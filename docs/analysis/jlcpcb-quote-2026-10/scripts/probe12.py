"""Locate the PCB Qty input precisely."""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL
JS = r"""
() => {
  const out = {hits: []};
  document.querySelectorAll('*').forEach(e=>{
    const t=(e.innerText||'').trim();
    if(t.startsWith('PCB Qty') && t.length<40){
      let p=e, chain=[];
      for(let i=0;i<5&&p;i++){
        p=p.parentElement; if(!p) break;
        const inp=p.querySelector('input');
        chain.push({cls:p.className, hasInput:!!inp,
                    input: inp?{name:inp.name,cls:inp.className,val:inp.value,ph:inp.placeholder}:null,
                    txt:(p.innerText||'').replace(/\s+/g,' ').slice(0,80)});
      }
      out.hits.push({tag:e.tagName, cls:e.className, txt:t, chain});
    }
  });
  out.allInputs = [...document.querySelectorAll('input')].map(e=>({name:e.name,cls:e.className,
      val:e.value, ph:e.placeholder, vis:!!(e.offsetParent||e.getClientRects().length)}));
  // any element text exactly '5' with class containing qty
  out.qtyish = [...document.querySelectorAll('*')].filter(e=>/qty/i.test(e.className||'')).slice(0,10)
      .map(e=>({tag:e.tagName,cls:e.className,txt:(e.innerText||'').trim().slice(0,30)}));
  return out;
}
"""
with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    print(json.dumps(pg.evaluate(JS), indent=1)[:4000])
