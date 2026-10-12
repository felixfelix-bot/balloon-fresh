"""Measure JLCPCB quotes for the v9 hub board at 103x103 vs 89x89 under isolated options.

Method: the quote page accepts MANUAL dimensions (input[name=stencilLength]/[stencilWidth])
so no gerber upload is needed and there is no file-derived state to leak.  Each measurement is
taken from a FRESH page navigation (new tab in the same context) to isolate option state, and the
widget toggles use a real mouse click at the element's bounding-box centre (element.click() is
silently ignored by the Vue components).
"""
import json, os, sys, time, datetime
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

OUT = os.path.expanduser("~/quote-scratch/measurements")
os.makedirs(OUT, exist_ok=True)

# ---- helpers injected into the page -------------------------------------------------------
ROW_FOR = r"""
(h) => {
  const rows = [...document.querySelectorAll('div.main-btn-group')];
  for (const r of rows) {
    const lab = r.querySelector('label');
    if (lab && (lab.innerText||'').trim().startsWith(h)) return r;
  }
  return null;
}
"""

JS_SELECTED = r"""
() => {
  const res = {};
  const rows = [...document.querySelectorAll('div.main-btn-group')];
  for (const r of rows) {
    const lab = r.querySelector('label');
    if (!lab) continue;
    const h = (lab.innerText||'').trim().split('\n')[0];
    const cur = r.querySelector('button.cur');
    if (cur) res[h] = cur.innerText.trim().replace(/\s+/g,' ');
  }
  const dels = [...document.querySelectorAll('div.main-btn-group')].map(r=>{
    const lab=r.querySelector('label'); if(!lab) return null;
    const h=(lab.innerText||'').trim().split('\n')[0];
    return [h, [...r.querySelectorAll('button')].map(b=>b.innerText.trim().replace(/\s+/g,' '))];
  }).filter(Boolean);
  return {selected: res, allRows: dels};
}
"""

JS_TEXT = r"() => document.body.innerText || ''"

def fill_dims(pg, x, y):
    return pg.evaluate(r"""
    ([x, y]) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      const xi = document.querySelector('input[name=stencilLength]');
      const yi = document.querySelector('input[name=stencilWidth]');
      if (!xi || !yi) return 'MISSING';
      for (const [el,v] of [[xi,x],[yi,y]]) {
        el.focus(); setter.call(el, String(v));
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
        el.blur();
      }
      return 'ok';
    }""", [x, y])

def set_qty(pg, q):
    """PCB Qty is a plain number input next to the 'PCB Qty' label."""
    return pg.evaluate(r"""
    (q) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      let target=null;
      document.querySelectorAll('*').forEach(e=>{
        if(target) return;
        if(e.children.length===0 && (e.textContent||'').trim()==='PCB Qty'){
          let p=e; for(let i=0;i<4&&p;i++){p=p.parentElement;
            const i2 = p && p.querySelector('input.el-input__inner');
            if(i2){target=i2;break;}}
        }
      });
      if(!target) return 'MISSING';
      target.focus(); setter.call(target, String(q));
      target.dispatchEvent(new Event('input',{bubbles:true}));
      target.dispatchEvent(new Event('change',{bubbles:true}));
      target.blur();
      return 'ok';
    }""", q)

def click_option(pg, heading, label):
    """Find the option button by exact text inside the row that has the heading; real mouse click."""
    r = pg.evaluate(r"""
    ([h, l]) => {
      const rows = [...document.querySelectorAll('div.main-btn-group')];
      let row=null;
      for (const rr of rows) {
        const lab = rr.querySelector('label');
        if (lab && (lab.innerText||'').trim().startsWith(h)) { row=rr; break; }
      }
      if(!row) return {err:'no row', heading:h};
      const btns=[...row.querySelectorAll('button')];
      let t=null;
      for (const b of btns) {
        const s=(b.innerText||'').trim().replace(/\s+/g,' ');
        if (s===l) { t=b; break; }
      }
      if(!t) return {err:'no option', heading:h, have:btns.map(b=>b.innerText.trim())};
      const bb=t.getBoundingClientRect();
      return {x: bb.x+bb.width/2, y: bb.y+bb.height/2, tag:t.tagName, cls:t.className};
    }""", [heading, label])
    if "err" in r:
        return r
    pg.mouse.click(r["x"], r["y"])
    return r

def read_quote(pg):
    t = pg.evaluate(JS_TEXT)
    lines = [l.strip() for l in t.split("\n")]
    out = {"raw_len": len(t)}
    # charge lines: label then value on following line(s)
    def val_after(lbl, n=3):
        for i,l in enumerate(lines):
            if l == lbl:
                for j in range(i+1, min(i+1+n, len(lines))):
                    if lines[j].startswith("$"):
                        return lines[j]
        return None
    out["engineering"] = val_after("Engineering fee")
    out["board"] = val_after("Board")
    out["via_covering"] = val_after("Via Covering")
    out["surface_finish"] = val_after("Surface Finish")
    out["deburring"] = val_after("Deburring")
    for i,l in enumerate(lines):
        if l == "Calculated Price":
            out["calculated_price"] = lines[i+1] if i+1 < len(lines) else None
        if l == "Shipping Estimate":
            out["shipping"] = lines[i+1] if i+1 < len(lines) else None
        if l == "Weight":
            out["weight"] = lines[i+1] if i+1 < len(lines) else None
    return out, t

def fresh_page(ctx):
    pg = ctx.new_page()
    pg.set_viewport_size({"width": 1500, "height": 1500})
    _goto(pg, QUOTE_URL, settle=18)
    return pg

def measure(ctx, name, x, y, layers, thickness, qty=5, extra=None):
    pg = fresh_page(ctx)
    log = {"name": name, "dims": [x, y], "layers": layers, "thickness": thickness, "qty": qty,
           "extra": extra, "at": datetime.datetime.now().isoformat(timespec="seconds")}
    time.sleep(3)
    log["qty_before"] = set_qty(pg, qty)
    time.sleep(2)
    log["fill"] = fill_dims(pg, x, y)
    time.sleep(2)
    # thickness BEFORE layers (per report, set explicitly, order independent but log both)
    log["click_thickness"] = click_option(pg, "PCB Thickness", thickness)
    time.sleep(3)
    log["click_layers"] = click_option(pg, "Layers", layers)
    time.sleep(6)
    if extra:
        for (h, l) in extra:
            log[f"click_{h}={l}"] = click_option(pg, h, l)
            time.sleep(5)
    sel = pg.evaluate(JS_SELECTED)
    log["selected_rows"] = sel["selected"]
    q, t = read_quote(pg)
    log["quote"] = q
    # verification: dims inputs still hold the values?
    log["dims_input"] = pg.evaluate(r"""( () => {
        const xi=document.querySelector('input[name=stencilLength]');
        const yi=document.querySelector('input[name=stencilWidth]');
        return xi&&yi ? [xi.value, yi.value] : null; })()""")
    with open(f"{OUT}/{name}.txt","w") as fh: fh.write(t)
    with open(f"{OUT}/{name}.json","w") as fh: json.dump(log, fh, indent=2)
    pg.close()
    print(json.dumps(log, indent=1))
    return log

if __name__ == "__main__":
    cfgs = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    with browser(headless=True) as pg0:
        ctx = pg0.context
        for c in cfgs:
            measure(ctx, c["name"], c["x"], c["y"], c["layers"], c["thickness"],
                    qty=c.get("qty",5), extra=[tuple(e) for e in c.get("extra",[])])
