#!/usr/bin/env python3
"""Layout gate for docs/v9-system-diagram.svg.

Renders the SVG in headless Chromium only to *measure* it: every <text> element's
real getBBox() is compared against the panel/card rectangle it sits in.  This is
the mechanical substitute for "look at the picture" on a headless worker, and it
catches the three defects that actually happen when hand-authoring a diagram:

  1. OVER_RIGHT / OVER_BOTTOM  - a label runs past the edge of its own box
  2. OFFCANVAS                 - a label runs off the canvas
  3. RECT_OVERLAP              - two boxes collide (nesting is allowed)
  4. TEXT_OVERLAP              - two labels collide on different baselines

Usage:
    python3 scripts/check_v9_diagram_layout.py [svg] [--w 1900] [--h 1472]
Exit status: 0 = clean, 1 = defects found, 2 = could not measure.

Requires: chromium on PATH. If it is absent the script exits 2 and says so -
it never silently passes.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_SVG = os.path.join(REPO, "docs", "v9-system-diagram.svg")

PROBE = r"""
<script><![CDATA[
window.addEventListener('load', function(){
  var texts=[].slice.call(document.querySelectorAll('text'));
  var rects=[].slice.call(document.querySelectorAll('rect')).map(function(r){
    return {x:+r.getAttribute('x'),y:+r.getAttribute('y'),
            w:+r.getAttribute('width'),h:+r.getAttribute('height')};});
  var out={over:[],rectoverlap:[],textoverlap:[]}, boxes=[];
  texts.forEach(function(t){
    var b=t.getBBox(), x=+t.getAttribute('x'), y=+t.getAttribute('y');
    var encl=rects.filter(function(r){return r.x<=x&&x<=r.x+r.w&&r.y<=y&&y<=r.y+r.h;});
    encl.sort(function(a,b){return a.w*a.h-b.w*b.h;});
    var rc=encl[0], flag='';
    if(b.x<-0.5||b.x+b.width>__W__-2||b.y<-0.5||b.y+b.height>__H__-2) flag+='OFFCANVAS ';
    if(rc){ if(b.x+b.width>rc.x+rc.w-2) flag+='OVER_RIGHT@'+Math.round(rc.x+rc.w)+' ';
            if(b.y+b.height>rc.y+rc.h-1) flag+='OVER_BOTTOM@'+Math.round(rc.y+rc.h)+' '; }
    if(flag) out.over.push({txt:(t.textContent||'').slice(0,54),x:Math.round(b.x),
      right:Math.round(b.x+b.width),bot:Math.round(b.y+b.height),flag:flag.trim()});
    boxes.push({t:(t.textContent||'').slice(0,30),x:b.x,y:b.y,w:b.width,h:b.height});
  });
  var i,j;
  for(i=0;i<rects.length;i++) for(j=i+1;j<rects.length;j++){
    var a=rects[i],b=rects[j];
    if(a.x<=b.x&&b.x+b.w<=a.x+a.w&&a.y<=b.y&&b.y+b.h<=a.y+a.h) continue;
    if(b.x<=a.x&&a.x+a.w<=b.x+b.w&&b.y<=a.y&&a.y+a.h<=b.y+b.h) continue;
    var ox=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x);
    var oy=Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y);
    if(ox>1&&oy>1) out.rectoverlap.push({a:[a.x,a.y,a.w,a.h],b:[b.x,b.y,b.w,b.h]});
  }
  for(i=0;i<boxes.length;i++) for(j=i+1;j<boxes.length;j++){
    var p=boxes[i],q=boxes[j];
    if(Math.abs(p.y-q.y)<6) continue;
    var ox2=Math.min(p.x+p.w,q.x+q.w)-Math.max(p.x,q.x);
    var oy2=Math.min(p.y+p.h,q.y+q.h)-Math.max(p.y,q.y);
    if(ox2>2&&oy2>2) out.textoverlap.push({a:p.t,b:q.t});
  }
  document.documentElement.setAttribute('data-probe', JSON.stringify(out));
});
]]></script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg", nargs="?", default=DEFAULT_SVG)
    ap.add_argument("--w", type=int, default=1900)
    ap.add_argument("--h", type=int, default=1472)
    a = ap.parse_args()

    chrome = shutil.which("chromium") or shutil.which("chromium-browser") \
        or shutil.which("google-chrome")
    if not chrome:
        print("CANNOT MEASURE: no chromium/chromium-browser/google-chrome on PATH.")
        return 2

    probe = PROBE.replace("__W__", str(a.w)).replace("__H__", str(a.h))
    src = open(a.svg, encoding="utf-8").read()
    tmp = tempfile.mktemp(suffix=".svg")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(src.replace("</svg>", probe + "</svg>"))
    try:
        dom = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--virtual-time-budget=5000", "--dump-dom", "file://" + tmp],
            capture_output=True, text=True, timeout=240).stdout
    finally:
        os.unlink(tmp)

    m = re.search(r'data-probe="([^"]*)"', dom)
    if not m:
        print("CANNOT MEASURE: probe produced no result (dom=%d bytes)" % len(dom))
        return 2

    d = json.loads(html.unescape(m.group(1)))
    bad = 0
    for key, label in (("over", "TEXT OVERFLOW"), ("rectoverlap", "RECT OVERLAP (non-nested)"),
                       ("textoverlap", "TEXT-vs-TEXT OVERLAP")):
        rows = d[key]
        bad += len(rows)
        print("== %s: %d" % (label, len(rows)))
        for r in rows:
            print("   ", r)
    print("%s: %d defect(s) in %s" % ("FAIL" if bad else "PASS", bad, a.svg))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
