"""Read the full tooltip text attached to the PCB Thickness options."""
import json, sys, re
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

JS = r"""
() => {
  const out = {};
  // The thickness row: div.main-btn-group whose label startsWith 'PCB Thickness'
  let row=null;
  document.querySelectorAll('div.main-btn-group').forEach(r=>{
    const lab=r.querySelector('label');
    if(lab && (lab.innerText||'').trim().startsWith('PCB Thickness')) row=r;
  });
  if(!row) return {err:'no row'};
  out.rowText = row.innerText.replace(/\s+/g,' ');
  out.opts = [...row.querySelectorAll('button')].map(b=>({
      txt: b.innerText.trim(), disabled: b.disabled, cls: b.className
  }));
  // all tooltips anywhere whose text mentions mm size limits
  out.notes = [];
  document.querySelectorAll('*').forEach(e=>{
    if(e.children.length>0) return;
    const t=(e.textContent||'').trim();
    if(/maximum PCB size|does not support|doesn't support|only accept/i.test(t)) out.notes.push(t.replace(/\s+/g,' '));
  });
  out.notes = [...new Set(out.notes)];
  // the whole thickness label tooltip content
  const lab = row.querySelector('label');
  const pop = lab.querySelector('.pcb-faq-content');
  out.labelTooltip = pop ? pop.innerText.replace(/\s+/g,' ') : null;
  return out;
}
"""
with browser(headless=True) as pg:
    _goto(pg, QUOTE_URL, settle=20)
    print(json.dumps(pg.evaluate(JS), indent=1))
