# Upstream enclosure requests — index

Requests to `Amperstrand/enclosure-forge` for enclosures the project actually needs.
Plan and rationale: [`../ENCLOSURE-FORGE-APPLICABILITY.md`](../ENCLOSURE-FORGE-APPLICABILITY.md) §13.

**Hard gate (operator instruction, 2026-10-11):** a request is filed **only after its board is complete**
— layout freeze + fab set. Filing earlier asks the forge author to guess our requirements, which is the
one thing this method exists to prevent ("no dimension is typed from memory").

| Card | Target | Gating board card | Gate state | Issue |
|---|---|---|---|---|
| `t_9c79b66e` | Base station (masthead + shack) | `t_179e36f9` PCBPROG-BASE-2 fab-ready review | **chain blocked** — `t_6bdc4d64` (`triage`), `t_d7c330d8` (`blocked`) | — |
| `t_69234607` | Tracker controller | `t_a36b8060` PCBPROG-TRK-2 fab-ready review | waiting on `t_3754cf63` TRK-1 | — |
| `t_8e0f5010` | Pre-stretch bench rig | `t_f22504c6` PCBPROG-PRE-3 fab pack + review | waiting on `t_7a755a29` PRE-2 | — |
| `t_8494294f` | Auto-bootsel interposer | — (already routed) | **ready to request** — issue drafted and board tests pass | [#1](https://github.com/Amperstrand/enclosure-forge/issues/1) |

## Explicit NON-requests

Stated so the forge author does not design a case we will never print:

- **`hub_board_v9`** — mass-critical at altitude; needs a **retention frame**, not an enclosure.
- **`wing_board_v9` ×4** — same, and they are the solar carriers; the ADR-065 skeletonised frame is the
  structure.
- **`balloon_dev_case`** — ours (OpenSCAD); `REC-FIRST` re-homes it onto the forge method instead of
  asking upstream.

## Definition of done for each request

Requirements collected with provenance (13 items, §13.2) → geometry-availability matrix built → draft
pushed as a PR → operator-approved → issue opened and **read back** with its URL recorded → issue number
filled into the table above.
