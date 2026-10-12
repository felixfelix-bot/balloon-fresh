"""Dump the quote-page form structure and locate the Dimensions inputs."""
import json, sys
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

PROBE = r"""
(() => {
  const out = {title: document.title, url: location.href};
  out.inputs = [...document.querySelectorAll('input')].map(e => ({
     type:e.type, id:e.id, name:e.name, cls:e.className,
     ph:e.placeholder, val:(e.value||'').slice(0,40),
     vis: !!(e.offsetParent||e.getClientRects().length),
     rect: (()=>{const r=e.getBoundingClientRect(); return [Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)];})()
  }));
  out.selects = [...document.querySelectorAll('select')].map(e => ({
     id:e.id, name:e.name, cls:e.className, val:(e.value||'').slice(0,40),
     opts:[...e.options].map(o=>o.text), vis:!!(e.offsetParent||e.getClientRects().length)
  }));
  // Any element whose text is exactly 'Dimensions' plus nearby inputs
  const hits = [];
  document.querySelectorAll('*').forEach(e=>{
     if (e.children.length===0 && e.textContent.trim()==='Dimensions') {
        let p = e; let hops=0; let blk=null;
        while (p && hops<5) { p = p.parentElement; hops++;
           if (p && p.querySelectorAll('input').length) { blk=p; break; } }
        hits.push({tag:e.tagName, cls:e.className, rect:(()=>{const r=e.getBoundingClientRect();return [Math.round(r.x),Math.round(r.y)];})(),
                   blockHtml: blk? blk.outerHTML.slice(0,1200):null});
     }
  });
  out.dimHits = hits;
  return out;
})()
"""
with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    d = pg.evaluate(PROBE)
    print("INPUTS:")
    for i in d["inputs"]:
        print(" ", json.dumps(i))
    print("SELECTS:")
    for s in d["selects"]:
        print(" ", json.dumps(s))
    print("DIM HITS:")
    for h in d["dimHits"]:
        print(" ", json.dumps(h)[:1500])
