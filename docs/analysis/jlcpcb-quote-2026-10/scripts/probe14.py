"""Open the PCB Qty dropdown and list the preset quantities available."""
import json, sys, time
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    r = pg.evaluate(r"""() => {
      const row = document.getElementById('QtyDom');
      if(!row) return 'no QtyDom';
      const el = row.querySelector('input');
      const bb = el.getBoundingClientRect();
      return {x: bb.x+bb.width/2, y: bb.y+bb.height/2, html: row.outerHTML.slice(-900)};
    }""")
    print("RECT:", json.dumps({k:v for k,v in r.items() if k!='html'}))
    print("TAIL:", r['html'][-700:])
    pg.mouse.click(r['x'], r['y']); time.sleep(3)
    print("--- dropdown items ---")
    print(json.dumps(pg.evaluate(r"""() => {
      const out=[];
      document.querySelectorAll('.el-select-dropdown__item, li, .el-dropdown-menu__item').forEach(e=>{
        const t=(e.innerText||'').trim();
        if(t && t.length<12 && e.offsetParent) out.push(t);
      });
      return [...new Set(out)].slice(0,60);
    }"""), indent=0))
