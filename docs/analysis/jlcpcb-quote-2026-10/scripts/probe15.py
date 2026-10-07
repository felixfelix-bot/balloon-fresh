"""Open the qty preset control via the visible value element and list presets."""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    info = pg.evaluate(r"""() => {
      const row = document.getElementById('QtyDom');
      const out = {desc: [], html: row.outerHTML.slice(0,2500)};
      row.querySelectorAll('*').forEach(e=>{
        const t=(e.innerText||'').trim();
        const r=e.getBoundingClientRect();
        if(t && t.length<8) out.desc.push({tag:e.tagName, cls:e.className, txt:t,
            rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
            vis:!!(e.offsetParent||e.getClientRects().length)});
      });
      return out;
    }""")
    print("DESC:", json.dumps(info['desc'][:25], indent=0))
    print("HTML:", info['html'][:1200])
    # click the visible element that shows the number
    r = pg.evaluate(r"""() => {
      const row = document.getElementById('QtyDom');
      for (const e of row.querySelectorAll('*')) {
        const t=(e.innerText||'').trim();
        const b=e.getBoundingClientRect();
        if (/^\d+$/.test(t) && b.width>0 && e.children.length===0) return {x:b.x+b.width/2,y:b.y+b.height/2,t};
      }
      return null;
    }""")
    print("VALUE EL:", r)
    if r:
        pg.mouse.click(r['x'], r['y']); time.sleep(3)
        print("ITEMS:", json.dumps(pg.evaluate(r"""() => {
          const out=[];
          document.querySelectorAll('*').forEach(e=>{
            if(e.children.length===0){
              const t=(e.innerText||'').trim();
              const b=e.getBoundingClientRect();
              if(/^\d{1,6}$/.test(t) && b.width>0 && b.x>0) out.push(t);
            }
          });
          return [...new Set(out)].slice(0,80);
        }""")))
