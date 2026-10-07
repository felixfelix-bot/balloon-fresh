"""Try a manual-dimension quote with NO upload. Does a price render signed-out?"""
import json, sys, time, re
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

FILL = r"""
([x, y]) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  const xi = document.querySelector('input[name=stencilLength]');
  const yi = document.querySelector('input[name=stencilWidth]');
  for (const [el,v] of [[xi,x],[yi,y]]) {
    if(!el) return 'missing';
    el.focus(); setter.call(el, String(v));
    el.dispatchEvent(new Event('input',{bubbles:true}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
    el.blur();
  }
  return 'ok';
}
"""

def dollars(pg):
    return pg.evaluate(r"""(() => {
      const out=[];
      document.querySelectorAll('*').forEach(e=>{
        if(e.children.length===0){
          const t=(e.textContent||'').trim();
          if(/^\$[0-9,]+(\.[0-9]{2})?$/.test(t)) out.push(t+' @ '+(e.className||''));
        }
      });
      return out.slice(0,20);
    })()""")

with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    print("before fill $:", dollars(pg))
    print("fill 103:", pg.evaluate(FILL, [103, 103]))
    time.sleep(6)
    t = pg.evaluate("document.body.innerText||''")
    print("has Calculated Price:", "Calculated Price" in t)
    print("has Detected:", "Detected" in t)
    print("$ after fill:", dollars(pg))
    # any text mentioning price/quote
    for ln in t.split("\n"):
        if "alcu" in ln or "$" in ln or "TOTAL" in ln.upper():
            print("LINE:", ln)
