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
ESP32_TX = os.path.join(
    REPO_ROOT, "mesh-stack", "flrc-bench-espidf", "main", "esp32_raw_tx.cpp"
)

# The timeout-recovery block, from its `if (!txDone)` guard to the closing brace
# of that if-statement.  Anchored on the failure counters written afterwards so
# the match cannot silently grow to swallow the rest of the burst.
RE_RECOVERY = re.compile(
    r"if\s*\(\s*!\s*txDone\s*\)\s*\{(?P<body>.*?)\n\s*\}\n(?=\s*\n\s*if\s*\(i\s*<\s*5\))",
    re.S,
)
# The hot-loop prologue: rfClearIrq -> rfWriteTxFifo -> rfSetTx, one per packet.
RE_HOT_LOOP = re.compile(
    r"for\s*\(int\s+i\s*=\s*0;\s*i\s*<\s*TX_PKT_COUNT;\s*i\+\+\s*\)\s*\{(?P<body>.*?)\n\s*\}",
    re.S,
)
RE_TX_DONE_STATS = re.compile(r'TX_DONE_STATS:\s*fired=%lu\s+timeout=%lu')
RE_PROGRESS_250 = re.compile(r"\(i\s*\+\s*1\)\s*%\s*250\s*==\s*0")


def _src():
    with open(ESP32_TX, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _strip_comments(text):
    """Drop // and /* */ comments so prose about a call is not read as a call."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _recovery_body():
    m = RE_RECOVERY.search(_src())
    assert m, (
        "could not locate the `if (!txDone) { ... }` timeout-recovery block in "
        "esp32_raw_tx.cpp — the P0.2 invariant test needs it to exist"
    )
    return _strip_comments(m.group("body"))


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

    def test_hot_loop_does_not_clear_errors_or_fifo_per_packet(self):
        m = RE_HOT_LOOP.search(_src())
        assert m, "could not locate the TX packet loop in esp32_raw_tx.cpp"
        body = _strip_comments(m.group("body"))
        assert "rfClearErrors()" not in body, (
            "rfClearErrors() is back in the per-packet hot loop — that is the "
            "P0.2 optimisation being undone"
        )
        assert "rfClearTxFifo()" not in body, (
            "rfClearTxFifo() is back in the per-packet hot loop — that is the "
            "P0.2 optimisation being undone"
        )

    def test_hot_loop_keeps_clear_irq_before_write(self):
        """rfClearIrq() must stay, and stay ordered before the FIFO write."""
        m = RE_HOT_LOOP.search(_src())
        assert m, "could not locate the TX packet loop in esp32_raw_tx.cpp"
        body = _strip_comments(m.group("body"))
        order = []
        for call in ("rfClearIrq()", "rfWriteTxFifo(", "rfSetTx()"):
            idx = body.find(call)
            assert idx >= 0, f"{call} missing from the TX hot loop"
            order.append(idx)
        assert order == sorted(order), (
            "hot-loop command order regressed: rfClearIrq() must precede "
            "rfWriteTxFifo() and rfSetTx() so TX_DONE is cleared per packet"
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
