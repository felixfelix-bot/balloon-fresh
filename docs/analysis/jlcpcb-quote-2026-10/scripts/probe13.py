"""Find the PCB Qty input inside its own row, set it, and verify the price changes."""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

JS_FIND = r"""
() => {
  let row=null;
  document.querySelectorAll('div.main-btn-group').forEach(r=>{
    if((r.innerText||'').trim().startsWith('PCB Qty')) row=r;
  });
  if(!row) return {err:'no row'};
  const inputs=[...row.querySelectorAll('input')].map(e=>({name:e.name,cls:e.className,val:e.value,ph:e.placeholder,type:e.type}));
  return {rowCls:row.className, rowHtml:row.outerHTML.slice(0,1200), inputs};
}
"""
JS_SET = r"""
(q) => {
  const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  let row=null;
  document.querySelectorAll('div.main-btn-group').forEach(r=>{
    if((r.innerText||'').trim().startsWith('PCB Qty')) row=r;
  });
  if(!row) return 'no row';
  const el=row.querySelector('input');
  if(!el) return 'no input';
  el.focus(); setter.call(el,String(q));
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.dispatchEvent(new Event('blur',{bubbles:true})); el.blur();
  return el.value;
}
"""
def price(pg):
    t=pg.evaluate("document.body.innerText||''")
    L=[x.strip() for x in t.split("\n")]
    return [l for l in L if l.startswith("$")][:4], L[L.index("PCB Qty")+1] if "PCB Qty" in L else None

with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    print(json.dumps(pg.evaluate(JS_FIND), indent=1))
    pg.evaluate(r"([x,y])=>{const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;const a=document.querySelector('input[name=stencilLength]');const b=document.querySelector('input[name=stencilWidth]');for(const [e,v] of [[a,x],[b,y]]){e.focus();s.call(e,String(v));e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();}return 1;}",[103,103])
    time.sleep(4)
    print("qty-5 state:", pg.evaluate(r"()=>{let r=null;document.querySelectorAll('div.main-btn-group').forEach(x=>{if((x.innerText||'').trim().startsWith('PCB Qty'))r=x;});return r?(r.innerText||'').trim().replace(/\s+/g,' '):null;}"))
    print("set qty 1 ->", pg.evaluate(JS_SET, 1))
    time.sleep(6)
    print("qty read:", pg.evaluate(r"()=>{let r=null;document.querySelectorAll('div.main-btn-group').forEach(x=>{if((x.innerText||'').trim().startsWith('PCB Qty'))r=x;});return r?(r.innerText||'').trim().replace(/\s+/g,' '):null;}"))
    p,q = price(pg); print("prices:", p, "qtycell:", q)
