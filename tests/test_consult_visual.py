#!/usr/bin/env python3
"""Tests for tools/consult_visual.py.

These exist because the failure mode this tool guards against is SILENT: the
market router substitutes a non-vision model, the answer comes back empty or
"cannot see", and a caller that only looks at exit code 0 records a review that
never happened. Each test below pins one half of that contract against a fake
router, so no real quota is spent.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "tools", "consult_visual.py")


class _Handler(BaseHTTPRequestHandler):
    """Serves one canned chat completion; records the body it received."""

    response = {}
    received = []
    status = 200

    def do_POST(self):  # noqa: N802 (http.server API)
        length = int(self.headers.get("Content-Length", 0))
        _Handler.received.append(json.loads(self.rfile.read(length)))
        payload = json.dumps(_Handler.response).encode()
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args, **kwargs):
        pass


@pytest.fixture
def router():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
    server.shutdown()


@pytest.fixture
def gate_allow(tmp_path):
    path = tmp_path / "gate-allow.sh"
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@pytest.fixture
def gate_block(tmp_path):
    path = tmp_path / "gate-block.sh"
    path.write_text("#!/bin/sh\necho 'BLOCK: exhausted'\nexit 1\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@pytest.fixture
def image(tmp_path):
    # 1x1 PNG is enough: the tool only base64-encodes the bytes.
    data = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001"
        "0d0a2db40000000049454e44ae426082")
    path = tmp_path / "board.png"
    path.write_bytes(data)
    return str(path)


def _run(router_url, gate, image_path, out, extra=()):
    env = dict(os.environ, VISUAL_ROUTER=router_url, VISUAL_GATE=gate)
    return subprocess.run(
        [sys.executable, TOOL, image_path, "Is this copper continuous?", "--out", out, *extra],
        capture_output=True, text=True, env=env, timeout=120)


def _answer(text, model="gpt-6-astra"):
    return {"model": model,
            "choices": [{"message": {"role": "assistant", "content": text}}]}


LONG = ("The stub is continuous with the pad and reaches the via annular ring; "
        "it keeps clear of the neighbouring three-pad group and shows only a "
        "small neck at the pad exit.")


def test_useful_answer_prints_served_model_and_writes_artifact(
        router, gate_allow, image, tmp_path):
    _Handler.response = _answer(LONG)
    _Handler.status = 200
    out = tmp_path / "a.json"
    result = _run(router, gate_allow, image, str(out))
    assert result.returncode == 0, result.stderr
    # The SERVED model is reported, not merely the requested alias.
    assert "served_model: gpt-6-astra" in result.stdout
    artifact = json.loads(out.read_text())
    assert artifact["served_model"] == "gpt-6-astra"
    assert artifact["answer"].startswith("The stub is continuous")
    # The image really was attached as a data URL.
    sent = _Handler.received[-1]
    parts = sent["messages"][0]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_empty_answer_is_rejected_not_recorded_as_review(
        router, gate_allow, image, tmp_path):
    _Handler.response = _answer("")
    _Handler.status = 200
    out = tmp_path / "b.json"
    result = _run(router, gate_allow, image, str(out))
    assert result.returncode == 2
    assert "NO_VISION_LANE" in result.stderr
    artifact = json.loads(out.read_text())
    assert "served_model" not in artifact  # no certified answer


def test_blind_answer_is_rejected(router, gate_allow, image, tmp_path):
    _Handler.response = _answer(
        "I cannot see any image in this request, so I cannot answer the question "
        "about copper continuity. Please attach the render.")
    _Handler.status = 200
    result = _run(router, gate_allow, image, str(tmp_path / "c.json"))
    assert result.returncode == 2
    assert "NO_VISION_LANE" in result.stderr


def test_quota_block_refuses_before_spending(router, gate_block, image, tmp_path):
    _Handler.received.clear()
    _Handler.response = _answer(LONG)
    _Handler.status = 200
    result = _run(router, gate_block, image, str(tmp_path / "d.json"))
    assert result.returncode == 3
    assert "BLOCKED" in result.stderr
    assert _Handler.received == []  # router never contacted


def test_missing_image_refuses(router, gate_allow, tmp_path):
    result = _run(router, gate_allow, str(tmp_path / "nope.png"), str(tmp_path / "e.json"))
    assert result.returncode == 2
    assert "REFUSE" in result.stderr


def test_falls_through_dead_lane_to_live_one(router, gate_allow, image, tmp_path):
    """A 503 on the first lane must not end the consult."""
    _Handler.status = 503
    _Handler.response = {"error": "unavailable"}
    calls = {"n": 0}
    original = _Handler.do_POST

    def flaky(self):
        calls["n"] += 1
        _Handler.status = 503 if calls["n"] == 1 else 200
        _Handler.response = ({"error": "unavailable"} if calls["n"] == 1
                             else _answer(LONG, model="kimi-k3"))
        original(self)

    _Handler.do_POST = flaky
    try:
        out = tmp_path / "f.json"
        result = _run(router, gate_allow, image, str(out))
    finally:
        _Handler.do_POST = original
    assert result.returncode == 0, result.stderr
    artifact = json.loads(out.read_text())
    assert artifact["served_model"] == "kimi-k3"
    assert artifact["attempts"][0]["error"].startswith("HTTP 503")
