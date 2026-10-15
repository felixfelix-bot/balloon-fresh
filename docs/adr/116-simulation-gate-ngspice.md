# ADR-116: Simulation Gate — ngspice Testbenches as a Blocking Pre-Order Check

**Date:** 2026-10-14
**Status:** Accepted
**Decision Maker:** Felix (operator), directive 2026-10-14 (*"please integrate this in your workflow
and please make an ADR for this and please make a git hook for it. Please make sure that it gets
merged to the default branch"*)
**Related:** ADR-051 (order gates), ADR-052 (review gates), ADR-113 (DRC-to-blockers tool),
ADR-114 (SKiDL netlist authoring)

## Context

Every gate this campaign built checks **structure**: ERC (are pins connected), DRC (do tracks clear),
netlist integrity (do declared parts equal placed parts), order-package consistency. **None of them
checks whether a circuit WORKS.**

The operator raised this directly: KiCad ERC cannot see an unstable feedback loop, a wrong bias point,
or a swapped divider leg. Those pass every gate we have and fail on the bench — or in the air.

Three fabricated-green incidents already occurred in this campaign (grading DRC before refilling
zones, a stale packaged board, a `Reference`-scoped DRC rule that measured inert). Each was a check
that reported nothing and read as a pass. **A simulation gate must be built so that failure is the
default state and passing requires evidence.**

## Decision

Adopt **ngspice** as the simulation engine, driven headless from the repo, with three parts:

### 1. `tracker/hardware/sim/tb_*.cir` — testbenches

Plain SPICE decks, one per simulated block, each carrying `.control` blocks that **print named
vectors**. Physics modelled from the board's own topology, not invented.

### 2. `tracker/hardware/sim/check_sim_gate.py` — the gate

Runs each deck with `ngspice -b`, **parses the printed numbers into floats**, and compares them to
limits declared in `CRITERIA`. Exit 1 when any criterion is out of range.

**It never greps for words.** The widely-circulated pattern `if "v(out) < 4.9" in stdout` **can never
match**, because ngspice prints *values*, not *expressions* — a gate written that way passes forever
and proves nothing.

### 3. `tracker/hardware/tests/test_sim_gate.py` — regression suite (23 checks)

Proves the gate is trustworthy. It does not ask "does the gate pass?"; it asks **"can I make it fail,
and does it then say so?"** Each criterion is fed synthetic data that must violate it and must return
FAIL, and nominal data that must return PASS. It also fails on **orphan testbenches** (a `.cir` that
asserts nothing) and on **ADR-vs-code drift** (a block the ADR claims is simulated but which has no
deck).

### 4. `.githooks/pre-push` — enforcement

Blocks a push when the sim gate or its regression suite fails.

## The honest limit — read before trusting this

**`kicad-cli sch export netlist --format spice` DOES work, but the exported board netlist is NOT
simulatable.** Measured: every IC and connector exports as a bare one-node stub:

```
U1 __U1
U2 __U2
U4 __U4
U7 __U7
```

KiCad's SPICE exporter emits elements only for parts that carry SPICE models. The ESP32-S3, the
SX1280, the regulators and every connector have none, so they become **dangling placeholders**. The
passives (`R_DIV1`, `R_BAL1/2`, `R_F1`) export correctly.

**Consequence, stated plainly:** "simulate the board" is **not achievable today**. The achievable and
still-valuable thing is **per-block simulation of the modelable subcircuits**, each with a real
topology and a real assertion. This ADR claims exactly that and no more.

**Corollary:** a gate that silently skipped un-modelled blocks would be worthless, so
`test_sim_gate.py` asserts that every deck on disk is registered and asserts something. Blocks that
CANNOT yet be simulated are listed below as **NOT COVERED**, not quietly omitted.

## Coverage

| block | deck | criteria | status |
|---|---|---|---|
| **NTC temperature divider** (`R_NTC1`/`TH_NTC1`) | `tb_ntc_divider.cir` | 5 | ✅ **COVERED** |

The NTC criteria, chosen because each catches a real and likely error:

| id | asserts | catches |
|---|---|---|
| `NTC-25C` | tap = 1.65 V ± 0.05 at +25 °C | wrong resistor ratio |
| `NTC-MONO` | tap falls strictly as temperature rises | **divider legs swapped** — invisible to ERC |
| `NTC-COLD` | tap < 3.25 V at −40 °C | railed high, no resolution at cold end |
| `NTC-HOT` | tap > 0.05 V at +85 °C | railed low, no resolution at hot end |
| `RAIL` | the 3.3 V rail measures 3.3 V | a gate that cannot see the rail is measuring nothing |

### NOT COVERED (stated, not omitted)

| block | why not |
|---|---|
| SX1280 radio, ESP32-S3, regulators | **no SPICE models.** Vendor models required before these can be simulated. |
| RF matching / filter network | **component values do not exist yet** (Figure 15-1 prints designators only). Cannot simulate an undetermined network. |
| Supercap balance divider, `VSCAP` monitor | passives export fine; **decks not yet written.** Next increment. |
| TVS clamp transient (`D_CLAMP`) | needs the TVS vendor SPICE model. |

**Adding a modelable block is now cheap:** write the deck, register its criteria, and
`test_sim_gate.py` immediately enforces that the criteria can fail.

## Consequences

- **Pre-order sequence gains a stage:** ERC → **sim gate** → DRC → CPL/BOM → order.
- A wrong bias point, a swapped divider, or an out-of-range tap is caught **before** fabrication.
- The gate costs no inference: ngspice is deterministic and local.
- Blocks without models are **explicitly listed**, so absence is visible rather than assumed safe.
- `ngspice` must be installed (`apt-get install ngspice`); the suite **fails** rather than skips when
  it is absent, because a silently-skipped gate is the failure mode this ADR exists to prevent.

## Alternatives considered

- **LTspice** — rejected: needs wine on Ubuntu, breaks headless automation.
- **Xyce** — rejected for now: heavier, parallel-oriented, no benefit at this circuit size. Revisit
  if a large multi-block simulation is ever needed.
- **Grep-based checking of ngspice output** — rejected, and called out above: the common documented
  pattern can never match, so it is a gate that cannot fail.
