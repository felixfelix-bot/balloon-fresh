"""Guard: the wing bypass Schottky is a >=2 A / 40 V part, not a BAT54/SOD-323.

Three documents disagreed about this part. The board and the newest ADRs agree on
SS24 / SMA; two older wrapper documents said "BAT54 family, SOD-323", which is
6x under-rated (200 mA vs the 1.2 A v9 string) and explicitly excluded because
SOD-323 cannot carry 2 A.

These tests fail if the stale claim is reintroduced, or if the board drifts away
from the part the ADRs require.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# files that must NOT re-assert the stale part as the decision
STALE_CLAIM_FILES = [
    "docs/WING-TO-HUB-SOCKET-SPEC.md",
    "docs/adr/048-v9-hub-wing-interfaces.md",
]

# files that own the current decision
CURRENT_DECISION_FILES = [
    "docs/adr/049-wing-architecture.md",
    "docs/adr/053-per-cell-bypass-diodes.md",
]


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_current_decision_files_require_2a_40v() -> None:
    """The ADRs that own the decision must still demand >=2 A / 40 V."""
    blob = "\n".join(_read(f) for f in CURRENT_DECISION_FILES)
    assert "2 A / 40 V" in blob or "2A / 40V" in blob, "the >=2 A / 40 V rating must be stated"
    assert "SS24" in blob, "SS24 must be named as the part class"
    assert "PMEG4020ER" in blob, "PMEG4020ER must be named as the alternative"


def test_sod323_is_excluded_on_carrying_capacity() -> None:
    """SOD-323 must be excluded, and for the right reason (2 A), not size."""
    blob = "\n".join(_read(f) for f in CURRENT_DECISION_FILES)
    assert "SOD-323" in blob, "the exclusion must be explicit"
    m = re.search(r"excludes\s+\*{0,2}SOD-323\*{0,2}\s+because[^.]*\.", blob)
    assert m, "the reason for excluding SOD-323 must be stated"
    assert "2 A" in m.group(0), "SOD-323 is excluded because it cannot carry 2 A"


def test_stale_claim_is_marked_stale_not_silently_reworded() -> None:
    """A record that changed its part must say so, per the repo's ADR doctrine."""
    for rel in STALE_CLAIM_FILES:
        text = _read(rel)
        if "BAT54" in text:
            low = text.lower()
            assert "stale" in low or "supersed" in low or "under-rated" in low, (
                f"{rel} still mentions BAT54 without marking it stale/superseded"
            )


def test_socket_spec_recommends_the_corrected_part() -> None:
    """The spec must RECOMMEND the rated part, not merely mention it somewhere.

    A weak version of this test passed even with the stale "BAT54 family" line
    restored, because the correction paragraph still mentioned SS24 further down.
    So this asserts on the *recommendation* line itself.
    """
    text = _read("docs/WING-TO-HUB-SOCKET-SPEC.md")
    # the recommendation line must name the rated part
    rec = [l for l in text.splitlines()
           if l.strip().startswith("- **Part:") or "Package suggestion" in l]
    assert rec, "the spec must have a part-recommendation line"
    joined = " ".join(rec)
    assert "SS24" in joined or "PMEG4020ER" in joined, (
        f"the RECOMMENDATION must name the rated part; found: {joined[:200]}"
    )
    assert "2 A" in joined or "2A" in joined, "the recommendation must state the rating"


def test_socket_spec_has_no_unqualified_bat54_recommendation() -> None:
    """A bare "BAT54 family" recommendation must not come back.

    The stale text read: 'Package suggestion: SOD-323 or SMA (BAT54 family, ...)'.
    Any line that *recommends* a package/part must therefore not propose BAT54
    without marking it stale/superseded/under-rated.
    """
    text = _read("docs/WING-TO-HUB-SOCKET-SPEC.md")
    for line in text.splitlines():
        if "BAT54" not in line:
            continue
        low = line.lower()
        # mentioning BAT54 is fine IF the same line says why it is wrong
        if any(k in low for k in ("stale", "supersed", "under-rated", "underrated", "cannot", "6x")):
            continue
        # else it must be a purely historical/negative mention
        if "package suggestion" in low or low.strip().startswith("- **part:"):
            raise AssertionError(f"unqualified BAT54 recommendation: {line.strip()[:160]}")


def test_board_carries_the_rated_part_not_the_bat54() -> None:
    """The placed footprint must be the SMA/SS24 the ADRs require."""
    out = subprocess.run(
        ["git", "show", "HEAD:tracker/hardware/hub_board_v9.kicad_pcb"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        # worktree may not have the file; fall back to the working tree
        pcb = REPO / "tracker/hardware/hub_board_v9.kicad_pcb"
        assert pcb.is_file(), "hub board must exist to verify the placed part"
        text = pcb.read_text(encoding="utf-8")
    else:
        text = out.stdout

    refs = re.findall(r'\(property "Reference" "(D_BP\d)"', text)
    assert sorted(refs) == ["D_BP1", "D_BP2", "D_BP3", "D_BP4"], (
        f"expected 4 bypass provisions, found {refs}"
    )
    assert "D_SMA" in text, "the bypass part must be the SMA package"
    assert re.search(r'\(property "Value" "SS24"', text), "the bypass value must be SS24"


def test_handover_names_both_asks_and_the_blockers() -> None:
    """The handover must carry both operator asks and the inherited blockers."""
    text = _read("docs/HANDOVER-WING-RELEASE-AND-BYPASS-DIODE.md")
    for needle in ("Bypass Schottky", "keeper", "slip-fit", "SS24", "TODO(unverified)"):
        assert needle in text, f"handover must mention {needle!r}"
    # it must warn against cutting the copper, and keep the diode hub-side
    assert "cut" in text.lower(), "the no-copper-cut rule must be present"
    assert "hub" in text.lower(), "the hub-side diode requirement must be present"
