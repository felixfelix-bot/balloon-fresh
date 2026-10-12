"""Probe the JLCPCB quote page: auth state, spec form fields, manual-dimension option."""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, is_authed, _goto
from jlcpcb_client.selectors import QUOTE_URL

PROBE = r"""
(() => {
  const out = {title: document.title, url: location.href};
  const ins = [...document.querySelectorAll('input')].map(e => ({
     tag:'input', type:e.type, id:e.id, name:e.name, cls:e.className,
     ph:e.placeholder, val:(e.value||'').slice(0,40),
     vis: !!(e.offsetParent||e.getClientRects().length)
  }));
  const sels = [...document.querySelectorAll('select')].map(e => ({
     tag:'select', id:e.id, name:e.name, cls:e.className,
     val:(e.value||'').slice(0,40), opts:[...e.options].map(o=>o.text).slice(0,12),
     vis: !!(e.offsetParent||e.getClientRects().length)
  }));
  out.inputs = ins; out.selects = sels;
  out.fileInputs = [...document.querySelectorAll('input[type=file]')].map(e=>({id:e.id,cls:e.className,acc:e.accept}));
  return out;
})()
"""

with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    print("URL:", pg.url)
    print("AUTH:", is_authed(pg))
    t = pg.evaluate("document.body.innerText||''")
    print("--- BODYTEXT (" + str(len(t)) + " chars) ---")
    print(t[:3000])
    print("--- STRUCTURE ---")
    print(json.dumps(pg.evaluate(PROBE), indent=1)[:6000])
