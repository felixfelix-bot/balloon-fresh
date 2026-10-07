"""Fill dims and dump the FULL body text + the main price panel HTML."""
import json, sys, time
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
PANEL = r"""
(() => {
  let best=null;
  document.querySelectorAll('*').forEach(e=>{
    if(e.children.length===0 && (e.textContent||'').trim()==='Calculated Price'){
      let p=e; for(let i=0;i<7&&p;i++){p=p.parentElement;
        if(p && /Engineering|Board/.test(p.innerText||'')){best=p;break;}}
    }
  });
  return best ? best.innerText : '(no panel with Engineering)';
})()
"""
x,y = 103,103
with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    print("fill:", pg.evaluate(FILL, [x,y]))
    time.sleep(8)
    t = pg.evaluate("document.body.innerText||''")
    print("=== FULL BODYTEXT ===")
    print(t)
    print("=== PANEL ===")
    print(pg.evaluate(PANEL))
