"""TDD regression test for the P0.2 remediation (kanban t_19807e87).

P0.2 (commit 12167cb, "remove redundant CLR_ERR + CLR_FIFO from the ESP32 TX
hot loop") was right to take those two writes OFF the happy path, but a cold
cross-family review of the diff found three defects that its own evidence could
not detect:

  1. The timeout-recovery branch cleared the sticky error register only when
     `irqStatus & 0x00030000` was already set.  rfClearIrq() (which runs at the
     top of the NEXT packet) discards the error IRQ *flags* without touching the
     error register, so by the time the test ran the word was clean and the
     error stayed latched for the rest of the burst.  The guard was dead code
     that read as correct.
  2. Recovery did not clear the IRQ latch, so the following packet's poll could
     read a stale TX_DONE left by the packet that had just timed out.
  3. P0.2 silently dropped the machine-parseable `TX_DONE_STATS` burst summary
     and the per-250 progress line — the only logged accounting behind its own
     "0 timeouts" claim.  docs/flrc-rx-verified-results-2026-07-16.md and
     docs/P4.1-DMA-CHAINING-ZERO-COPY.md both quote `TX_DONE_STATS: fired=1000
     timeout=0`, so host harnesses parse that marker.

These are source-level invariants: they are exactly the kind of thing a
human/agent reading the diff must not have to re-derive.  No board needed.

The happy path must stay free of per-packet SPI traffic, so every assertion
below is scoped to the recovery branch or to the burst summary — a regression
that reintroduces per-packet clears has to fail too.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The file under test. Overridable so the suite can be pointed at a mutated
# copy to prove that a negative control actually FAILS (a test that cannot fail
# is not a test).
ESP32_TX = os.environ.get("P02_TX_SRC") or os.path.join(
    REPO_ROOT, "mesh-stack", "flrc-bench-espidf", "main", "esp32_raw_tx.cpp"
)

# ── region extraction ────────────────────────────────────────────────────────
# The two blocks below are located by BRACE MATCHING, never by a lazy `.*?`
# pattern.  The first revision of this suite used
# `for (...i++) \{(?P<body>.*?)\n\s*\}` and `if (!txDone) \{(?P<body>.*?)\}`:
# a lazy match stops at the FIRST closing brace at that indent, which is the
# brace of the DIO9 poll's inner `if`, so the "hot loop" region ended BEFORE the
# poll and before the recovery branch.  A regression that re-added
# rfClearErrors()/rfClearTxFifo() after the poll therefore passed the very test
# written to catch it (round-1 review finding 1).  Anchoring the recovery block
# on its trailing `if (i < 5)` debug block was brittle in the same way — moving
# that unrelated print made all four recovery assertions fail with a misleading
# "could not locate" error (round-1 review finding 6).  A region the test cannot
# reach is not a region the test guards, so the span is now explicit and is
# itself asserted (see test_hot_loop_region_reaches_past_the_poll).
RE_FOR_LOOP = re.compile(
    r"for\s*\(int\s+i\s*=\s*0;\s*i\s*<\s*TX_PKT_COUNT;\s*i\+\+\s*\)"
)
RE_RECOVERY_GUARD = re.compile(r"if\s*\(\s*!\s*txDone\s*\)")
RE_TX_DONE_STATS = re.compile(r'TX_DONE_STATS:\s*fired=%lu\s+timeout=%lu')
RE_PROGRESS_250 = re.compile(r"\(i\s*\+\s*1\)\s*%\s*250\s*==\s*0")


def _src():
    with open(ESP32_TX, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _strip_comments(text):
    """Drop // and /* */ comments so prose about a call is not read as a call.

    String- and character-literal aware: a naive `re.sub("//[^\\n]*")` also eats
    the tail of any literal containing `//` (e.g. a future "http://" in a format
    string), which silently changes what the invariants below are asserted
    against (round-1 review finding 5).
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        two = text[i:i + 2]
        if two == "//":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif two == "/*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif ch == '"' or ch == "'":
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                if text[i] == "\\":            # escaped char inside the literal
                    out.append(text[i:i + 2])
                    i += 2
                    continue
                out.append(text[i])
                if text[i] == quote:
                    i += 1
                    break
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _brace_span(text, open_idx):
    """Index of the `}` matching the `{` at `open_idx` (comment/string aware)."""
    assert text[open_idx] == "{", "brace matching must start on a `{`"
    depth = 0
    i, n = open_idx, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == "//":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if two == "/*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        ch = text[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise AssertionError("unbalanced braces in esp32_raw_tx.cpp")


def _block_body(text, pattern, what):
    """Comment-free body of the brace-delimited block opened after `pattern`."""
    m = pattern.search(text)
    assert m, (
        f"could not locate {what} in esp32_raw_tx.cpp — the P0.2 invariant test "
        "needs it to exist"
    )
    open_idx = text.index("{", m.end())
    return _strip_comments(text[open_idx + 1:_brace_span(text, open_idx)])


def _hot_loop_body():
    """The WHOLE per-packet `for` body: prologue, DIO9 poll, recovery branch."""
    return _block_body(_src(), RE_FOR_LOOP, "the TX packet loop")


def _hot_loop_happy_path():
    """The per-packet body MINUS the timeout-recovery branch.

    The recovery branch legitimately calls rfClearErrors()/rfClearTxFifo(); only
    the happy path must stay free of them. This is the view the P0.2 assertions
    below are scoped to (while the region test above guarantees the view spans
    the entire loop, so a clear added after the poll cannot hide).
    """
    body = _hot_loop_body()
    recovery = _recovery_body()
    assert recovery and recovery in body, (
        "the timeout-recovery branch is not contained in the extracted hot-loop "
        "region — the region extraction regressed"
    )
    happy = body.replace(recovery, "")
    # Removing the recovery text must not have removed the happy-path prologue.
    for call in ("rfClearIrq()", "rfWriteTxFifo(", "rfSetTx()"):
        assert call in happy, (
            f"{call} vanished when the recovery branch was cut out of the "
            "hot-loop region — the extraction is wrong"
        )
    return happy


def _recovery_body():
    """The `if (!txDone) { ... }` timeout-recovery branch."""
    return _block_body(_src(), RE_RECOVERY_GUARD, "the `if (!txDone) { ... }` "
                                                 "timeout-recovery block")


class TestP02RecoveryBranch:
    """The timeout path must actually recover, not merely look like it does."""

    def test_clear_errors_is_unconditional(self):
        """Finding 1: no `irqStatus & 0x00030000` guard may gate rfClearErrors()."""
        body = _recovery_body()
        assert "rfClearErrors()" in body, (
            "timeout recovery no longer clears the error register at all"
        )
        assert not re.search(r"if\s*\([^)]*0x00030000[^)]*\)", body), (
            "rfClearErrors() is gated on `irqStatus & 0x00030000` again — that "
            "guard is dead code: rfClearIrq() clears the error IRQ flags on the "
            "next packet while the error register stays latched (P0.2 review, "
            "finding 1). Clear the error state unconditionally on failure."
        )

    def test_recovery_clears_irq_latch(self):
        """Finding 2: a timed-out packet's TX_DONE must not be reused."""
        body = _recovery_body()
        assert "rfClearIrq()" in body, (
            "timeout recovery does not clear the IRQ latch, so the next packet's "
            "poll can read a stale TX_DONE from the packet that just timed out "
            "(P0.2 review, finding 2)"
        )

    def test_recovery_clears_tx_fifo(self):
        """A write overlapping the previous packet's flight may be partial."""
        assert "rfClearTxFifo()" in _recovery_body(), (
            "timeout recovery no longer clears the TX FIFO; a partially written "
            "packet would prepend residue to the next one"
        )

    def test_recovery_records_failure_evidence(self):
        """A non-zero timeout count must be diagnosable without a scope."""
        body = _recovery_body()
        assert "txLastFailIrq" in body and "txLastFailDio9" in body, (
            "timeout recovery does not capture the failing packet's IRQ word and "
            "DIO9 level, so a timeout count cannot be diagnosed offline"
        )


class TestP02HotLoopStaysLean:
    """The point of P0.2: no per-packet clears. Remediation must not undo it."""

    def test_hot_loop_region_reaches_past_the_poll(self):
        """Guard the guard: the extracted region must cover the WHOLE loop body.

        Regression test for round-1 review finding 1. The first revision matched
        the loop with a lazy `.*?` and stopped at the poll's inner brace, so the
        assertions below could not see a re-added per-packet clear. Assert the
        region's own extent explicitly.
        """
        body = _hot_loop_body()
        assert "PIN_DIO9" in body and "txDone" in body, (
            "the extracted hot-loop region does not even contain the DIO9 poll — "
            "the region extraction regressed and the P0.2 assertions below are "
            "once again invisible to the code they claim to guard"
        )
        assert "rfSetTx()" in body, (
            "the extracted hot-loop region ends before rfSetTx()"
        )
        # The region must span from the prologue to (at least) the recovery
        # branch, i.e. everything that runs once per packet.
        assert body.index("rfClearIrq()") < body.index("PIN_DIO9") , (
            "hot-loop region is ordered wrongly: rfClearIrq() must precede the poll"
        )
        assert body.index("PIN_DIO9") < body.index("if (!txDone)"), (
            "the extracted hot-loop region stops before the timeout-recovery "
            "branch, so a per-packet clear added after the poll would pass"
        )

    def test_hot_loop_does_not_clear_errors_or_fifo_per_packet(self):
        happy = _hot_loop_happy_path()
        assert "rfClearErrors()" not in happy, (
            "rfClearErrors() is back on the per-packet happy path — that is the "
            "P0.2 optimisation being undone"
        )
        assert "rfClearTxFifo()" not in happy, (
            "rfClearTxFifo() is back on the per-packet happy path — that is the "
            "P0.2 optimisation being undone"
        )

    def test_hot_loop_keeps_clear_irq_before_write(self):
        """rfClearIrq() must stay, and stay ordered before the FIFO write."""
        happy = _hot_loop_happy_path()
        order = []
        for call in ("rfClearIrq()", "rfWriteTxFifo(", "rfSetTx()"):
            idx = happy.find(call)
            assert idx >= 0, f"{call} missing from the TX hot loop"
            order.append(idx)
        assert order == sorted(order), (
            "hot-loop command order regressed: rfClearIrq() must precede "
            "rfWriteTxFifo() and rfSetTx() so TX_DONE is cleared per packet"
        )

    def test_hot_loop_has_exactly_one_clear_irq_and_no_other_clear(self):
        """One rfClearIrq() per packet on the happy path; every other clear is
        confined to the recovery branch (round-1 review finding 1, again)."""
        happy = _hot_loop_happy_path()
        assert happy.count("rfClearIrq()") == 1, (
            "expected exactly one rfClearIrq() per packet outside the recovery "
            f"branch, found {happy.count('rfClearIrq()')}"
        )
        for call in ("rfClearErrors()", "rfClearTxFifo()"):
            assert call not in happy, (
                f"{call} is on the happy path again — that is P0.2 undone"
            )


class TestP02HeaderMatchesCode:
    """The header comment must describe the loop that is actually there."""

    def test_header_does_not_claim_an_irq_bit_poll(self):
        """Round-1 review finding 2: the header said "poll TX_DONE (DIO9 + IRQ
        bit 19)" while the rewritten loop polls DIO9 only — a reader would have
        believed an IRQ-status poll that does not exist."""
        head = _src().split("static const char *TAG")[0]
        assert "IRQ bit 19" not in head and not re.search(r"IRQ\s+bit\s*19", head), (
            "the file header again advertises an IRQ-bit-19 poll; the hot loop "
            "polls DIO9 only (round-1 review finding 2)"
        )
        # ...and the loop itself must really poll DIO9.
        body = _hot_loop_body()
        assert "PIN_DIO9" in body and "txDone" in body, (
            "the hot loop no longer polls DIO9 at all — TX completion has no "
            "detection path left"
        )


class TestP02ExtractionHelpers:
    """The helpers the invariants depend on must not silently mis-parse.

    Round-1 review findings 1 and 5: the first revision's region extraction
    stopped at the poll's inner brace, and its comment stripper also ate the tail
    of any string literal containing `//`. Both defects made assertions pass on
    code they could not actually see.
    """

    def test_strip_comments_keeps_string_literals_intact(self):
        src = 'const char *u = "http://x/y"; // trailing\nchar c = \'/\';\n'
        out = _strip_comments(src)
        assert '"http://x/y"' in out, (
            "the comment stripper corrupted a string literal containing `//`"
        )
        assert "trailing" not in out, "the stripper left a // comment in place"
        assert "char c = '/';" in out, (
            "the stripper mishandled a char literal holding a slash"
        )

    def test_strip_comments_handles_block_comments_and_escapes(self):
        src = '/* a */ x(); /* b\nb2 */ "a\\"//b"\n'
        out = _strip_comments(src)
        assert "a" not in out.split("x();")[0], "block comment was not removed"
        assert "x();" in out and '"a\\"//b"' in out, (
            "block-comment removal or escaped-quote handling regressed"
        )
        assert "b2" not in out, "multi-line block comment was not removed"

    def test_brace_span_ignores_braces_in_comments_and_literals(self):
        src = '{ a(); // }\n b(); /* } */ c(); "}" } tail'
        end = _brace_span(src, 0)
        assert src[end] == "}", "brace matcher returned a non-brace index"
        assert src[end + 1:].strip() == "tail", (
            "brace matcher closed early on a brace inside a comment or a literal"
        )


class TestP02BurstSummaryRestored:
    """Finding 3: the marker the host harnesses parse must exist and parse."""

    def test_tx_done_stats_marker_present(self):
        body = _strip_comments(_src())
        assert RE_TX_DONE_STATS.search(body), (
            "the `TX_DONE_STATS: fired=%lu timeout=%lu` burst summary is gone — "
            "docs/flrc-rx-verified-results-2026-07-16.md and "
            "docs/P4.1-DMA-CHAINING-ZERO-COPY.md parse that marker, and it is the "
            "logged accounting behind any '0 timeouts' claim (P0.2 review, "
            "finding 3)"
        )

    def test_tx_done_stats_reports_failure_detail(self):
        body = _strip_comments(_src())
        assert "fail_irq=" in body and "fail_dio9=" in body, (
            "TX_DONE_STATS does not carry fail_irq/fail_dio9, so a timeout count "
            "arrives with no diagnostic attached"
        )

    def test_progress_line_every_250_packets_restored(self):
        assert RE_PROGRESS_250.search(_strip_comments(_src())), (
            "the per-250-packet progress log (dropped by P0.2) was not restored"
        )

    def test_reset_tx_result_marker_present(self):
        body = _strip_comments(_src())
        assert "RESULT_TX," in body, (
            "the machine-parseable RESULT_TX line is gone; host sweep harnesses "
            "parse it"
        )
