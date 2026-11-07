#!/usr/bin/env python3
"""Send an image + question to a vision lane through the market router and print
the SERVED model id plus the answer.

Why this exists: the flat router silently substitutes a non-vision model when the
requested lane is unhealthy, and an empty answer then looks like a clean review.
This script therefore
  1. quota-gates before spending,
  2. rejects any response that is empty, too short, or says it cannot see,
  3. prints the served model id from the RESPONSE (an alias is not a model),
  4. writes the full exchange to a JSON artifact for later audit.

Usage:
  consult_visual.py IMAGE "question" [--lane kimi-k3] [--out FILE]

Exit codes: 0 verdict obtained | 2 no vision lane answered | 3 quota blocked.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROUTER = os.environ.get("VISUAL_ROUTER", "http://127.0.0.1:9099/v1/chat/completions")
GATE = os.environ.get(
    "VISUAL_GATE", os.path.expanduser("~/.hermes/profiles/manager/scripts/zai-quota-gate.sh"))
# Ordered: cheapest vision-capable lanes first. Astra (gpt-6-astra) is the design
# oracle when its lane is healthy; kimi-k3 / minimax are the standing fallbacks.
DEFAULT_LANES = ["kimi-k3", "kimi-k3:cloud", "glm-4.6v", "gpt-6-astra", "minimax-m3:cloud"]
CANNOT_SEE = ("no_image", "cannot see", "can't see", "unable to see", "no image",
              "not able to view", "i don't see an image")


def quota_blocked() -> bool:
    try:
        r = subprocess.run(["bash", GATE], capture_output=True, text=True, timeout=90)
    except Exception:
        return True
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode != 0 or "BLOCK" in out


def encode(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def ask(lane: str, image_b64: str, question: str, max_tokens: int):
    body = {
        "model": lane,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
        ]}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        ROUTER, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        payload = json.loads(resp.read())
    served = payload.get("model") or ""
    msg = (payload.get("choices") or [{}])[0].get("message") or {}
    text = (msg.get("content") or "").strip()
    return served, text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("question")
    ap.add_argument("--lane", action="append", default=None,
                    help="lane to try; repeatable. Defaults to the built-in list.")
    ap.add_argument("--max-tokens", type=int, default=1800)
    ap.add_argument("--out", default=None, help="JSON artifact path")
    args = ap.parse_args()

    image = os.path.expanduser(args.image)
    if not os.path.exists(image):
        print(f"REFUSE: image not found: {image}", file=sys.stderr)
        return 2
    if quota_blocked():
        print("BLOCKED: quota gate refused", file=sys.stderr)
        return 3

    lanes = args.lane or DEFAULT_LANES
    b64 = encode(image)
    out_path = args.out or os.path.join(
        os.path.expanduser("~/reports"), "visual-consults",
        f"{time.strftime('%Y%m%dT%H%M%S')}-{os.path.basename(image)}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    attempts = []
    for lane in lanes:
        try:
            served, text = ask(lane, b64, args.question, args.max_tokens)
        except urllib.error.HTTPError as exc:
            attempts.append({"lane": lane, "error": f"HTTP {exc.code}"})
            continue
        except Exception as exc:  # timeouts, connection errors
            attempts.append({"lane": lane, "error": str(exc)[:200]})
            continue
        low = text.lower()
        blind = any(marker in low for marker in CANNOT_SEE)
        usable = bool(text) and len(text) >= 60 and not blind
        attempts.append({"lane": lane, "served_model": served, "chars": len(text),
                         "useful": usable, "answer": text})
        if usable:
            artifact = {"image": image, "question": args.question,
                        "served_model": served, "lane_requested": lane,
                        "answer": text, "attempts": attempts,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            with open(out_path, "w") as fh:
                json.dump(artifact, fh, indent=2)
            print(f"served_model: {served}")
            print(f"artifact: {out_path}")
            print("---")
            print(text)
            return 0

    with open(out_path, "w") as fh:
        json.dump({"image": image, "question": args.question, "attempts": attempts,
                   "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, fh, indent=2)
    print("NO_VISION_LANE: no usable answer; see " + out_path, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
