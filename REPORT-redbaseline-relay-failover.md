# REPORT — RED pytest baseline for relay-failover tests

Task: Capture the verbatim RED baseline that the publisher scaffolding must satisfy.

## Summary / headline finding

The relay-failover suite for `verdict_transport.py` is **already GREEN at the
current HEAD** — the implementation commit (`658ac8b1`) landed *after* the RED
test-authoring commit (`522c001e`) and is already pushed. So the *live* worktree
cannot reproduce RED.

The authored RED state is the parent commit `522c001e` ("test(e80): Gate1 RED
suite for verdict_transport publish_verdict contract"): the test file exists,
the module does not, and pytest dies in collection with `ModuleNotFoundError`.
I reproduced that state exactly in an isolated worktree and captured the
verbatim output below.

- Current HEAD: `658ac8b1` (pr/pcb-drc-scorecard) — 50 passed (GREEN)
- Authored RED commit: `522c001e` — 1 collection error (RED)
- Both commits are already on `origin/pr/pcb-drc-scorecard` and
  `origin/worker-heavy/failover-relays-absence`, `origin/worker-heavy/fake-relay-double`.
- No source file was modified for this task (capture only).

## (a) Exact grep command

Tree note: `firmware/e80-stm32-bench/tools/tests/` does NOT exist, so the grep
covers the tools dir only. `-I` skips the `__pycache__/*.pyc` binary noise.

```bash
cd /home/c03rad0r/repos/balloon-e80bench
grep -rn -I -e failover -e relay -e 1059 firmware/e80-stm32-bench/tools/
```

The relay-failover suite is `firmware/e80-stm32-bench/tools/test_verdict_transport.py`
(sibling of `verdict_transport.py`). Relevant hits:

```
firmware/e80-stm32-bench/tools/verdict_transport.py:2:"""verdict_transport.py — NIP-59 gift-wrapped verdict transport w/ relay failover.
firmware/e80-stm32-bench/tools/verdict_transport.py:109:KIND_GIFT_WRAP = 1059
firmware/e80-stm32-bench/tools/verdict_transport.py:120:#: Ordered relay failover set — EXACTLY these five bare hostnames, in order.
firmware/e80-stm32-bench/tools/verdict_transport.py:1254:    """Publish a verdict payload as a gift-wrapped kind-1059 event (failover).
firmware/e80-stm32-bench/tools/test_verdict_transport.py:21:    ``KIND_GIFT_WRAP == 1059``      NIP-59 outer wrap kind
firmware/e80-stm32-bench/tools/test_verdict_transport.py:1158:# RELAY — the exact five-host failover set, in order, dead host absent
```

## (b) Exact pytest commands

RED capture (isolated worktree at the authored RED commit — never in /tmp):

```bash
git -C /home/c03rad0r/repos/balloon-e80bench worktree add --detach \
    /home/c03rad0r/worktrees/e80-redbaseline 522c001e
cd /home/c03rad0r/worktrees/e80-redbaseline
python3 -m pytest -q firmware/e80-stm32-bench/tools/test_verdict_transport.py
```

Same, relay-subset selector (mirrors the suite's own `-k` contract):

```bash
python3 -m pytest -q firmware/e80-stm32-bench/tools/test_verdict_transport.py \
    -k "wrap or leak or key or relay"
```

GREEN control at current HEAD (for contrast):

```bash
cd /home/c03rad0r/repos/balloon-e80bench
python3 -m pytest -q firmware/e80-stm32-bench/tools/test_verdict_transport.py
```

Toolchain: python3 = 3.11.15 (uv cpython), pytest 9.1.1, pluggy 1.6.0,
plugins cov-7.1.0 + timeout-2.4.0. rootdir config = `pytest.ini`.

## (c) Complete RED output, pasted verbatim

From `/home/c03rad0r/worktrees/e80-redbaseline` @ `522c001e`:

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/c03rad0r/worktrees/e80-redbaseline
configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)
plugins: cov-7.1.0, timeout-2.4.0
collected 0 items / 1 error

==================================== ERRORS ====================================
__ ERROR collecting firmware/e80-stm32-bench/tools/test_verdict_transport.py ___
ImportError while importing test module '/home/c03rad0r/worktrees/e80-redbaseline/firmware/e80-stm32-bench/tools/test_verdict_transport.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
../../.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
firmware/e80-stm32-bench/tools/test_verdict_transport.py:93: in <module>
    import verdict_transport as vt  # noqa: E402,F401  the whole file collects
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'verdict_transport'
=========================== short test summary info ============================
ERROR firmware/e80-stm32-bench/tools/test_verdict_transport.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.34s ===============================
EXIT=2
```

Identical RED from the relay-subset selector (also 1 collection error, exit 2):

```
collected 0 items / 1 error

==================================== ERRORS ====================================
__ ERROR collecting firmware/e80-stm32-bench/tools/test_verdict_transport.py ___
ImportError while importing test module '/home/c03rad0r/worktrees/e80-redbaseline/firmware/e80-stm32-bench/tools/test_verdict_transport.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
../../.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
firmware/e80-stm32-bench/tools/test_verdict_transport.py:93: in <module>
    import verdict_transport as vt  # noqa: E402,F401  the whole file collects
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'verdict_transport'
=========================== short test summary info ============================
ERROR firmware/e80-stm32-bench/tools/test_verdict_transport.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.21s ===============================
```

## GREEN control at current HEAD (658ac8b1), for contrast

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/c03rad0r/repos/balloon-e80bench
configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)
plugins: cov-7.1.0, timeout-2.4.0
collected 50 items

firmware/e80-stm32-bench/tools/test_verdict_transport.py ............... [ 30%]
...................................                                      [100%]

============================== 50 passed in 0.14s ==============================
```

Relay subset at HEAD:

```
collected 50 items / 36 deselected / 14 selected
firmware/e80-stm32-bench/tools/test_verdict_transport.py ..............  [100%]
====================== 14 passed, 36 deselected in 0.07s ======================
```

## Interpretation for the publisher scaffolding card

The suite is the spec: it pins `publish_verdict(payload_serializer, *,
transport=None, env=None, created_at=None, log=None) -> PublishResult`,
`KIND_GIFT_WRAP == 1059`, and the exact five-host ordered failover set
(`nostr.mom, relay.primal.net, nos.lol, relay2.contextvm.org, relay.nostr.band`
with `relay.contextvm.org` named in `DEAD_RELAYS`). The RED evidence to cite for
"scaffolding must satisfy" is the `522c001e` collection error above. Any future
scaffolding change must not regress the 50-passed GREEN control at HEAD.

No source files were modified in this task.
