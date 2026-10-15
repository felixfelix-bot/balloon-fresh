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
| **SX1280 RF matching + harmonic filter** | `tb_rf_filter.cir` | 4 | ✅ **COVERED** |
| **Supercap balance divider** (`R_BAL1`/`R_BAL2`) | `tb_scap_balance.cir` | 3 | ✅ **COVERED** |
| **VSCAP monitor divider** (`R_DIV1`/`R_DIV2`) | `tb_vscap_monitor.cir` | 4 | ✅ **COVERED** |

**16 criteria, 59 regression checks.** Each catches a distinct, plausible error:

| id | asserts | catches |
|---|---|---|
| `NTC-25C` | tap = 1.65 V ± 0.05 at +25 °C | wrong resistor ratio |
| `NTC-MONO` | tap falls strictly as temperature rises | **divider legs swapped** — invisible to ERC |
| `NTC-COLD` | tap < 3.25 V at −40 °C | railed high, no resolution at cold end |
| `NTC-HOT` | tap > 0.05 V at +85 °C | railed low, no resolution at hot end |
| `RAIL` | the 3.3 V rail measures 3.3 V | a gate that cannot see the rail is measuring nothing |
| `RF-CURVE` | sweep is REAL: >100 samples, >1 GHz span, >50 distinct values | **an instrument that is not actually sweeping** |
| `RF-LOSS` | **0.461 dB** insertion loss at 2.4 GHz | a detuned or lossy match |
| `RF-REJ2` | **29.97 dB** rejection at 4.8 GHz | unfiltered 2nd harmonic |
| `RF-REJ3` | **30.48 dB** rejection at 7.2 GHz | unfiltered 3rd harmonic |
| `BAL-HALF` | supercap midpoint at exactly 2.70 V | unbalanced stack — one cap ages out first |
| `BAL-CURR` | balance current = 270 µA | **night-budget regression from a value change** |
| `BAL-LINR` | halving the stack halves the midpoint | clipped or non-linear divider |
| `MON-TAP` | monitor tap = 2.70 V at a 5.4 V stack | wrong divider ratio |
| `MON-ADC` | tap < 3.30 V at max stack | **ADC over-voltage — a dead part, unrecoverable in firmware** |
| `MON-MONO` | tap rises strictly with stack voltage | flat or inverted sense path |
| `MON-NIGHT` | divider current < 5 µA (measured 2.7 µA) | a divider that flattens the supercap overnight |

### The RF deck — and three measurement errors it took to get it right

The RF block was the hardest, and **every wrong version produced a plausible number**:

| version | reported | the fault |
|---|---|---|
| v1 | 2.3 dB harmonic rejection | **transposed topology** — `C4` modelled as a shunt to ground. Zooming into Figure 15-1 showed `C4` is **in parallel with `L2`**. Corrected: rejection rose **2.3 dB → 29 dB**. |
| v2 | −6.5 dB "insertion loss" | **unit error** — `db(v(ant))` measures *voltage*, and a 1 V source through 50 Ω into a 50 Ω load reads **0.5 V = −6.02 dB** as a BASELINE. A perfect match reads −6.02 dB, not 0 dB. |
| v3 | `rej = 0.000` | **ngspice control-language failure** — `alterparam` in `foreach`, `$&PARAM` expansion, and scalar `let` across runs silently did nothing, returning three *identical* readings. |

**Design consequence, now enforced:** `RF-CURVE` exists specifically to catch v3-class failures — it
asserts the sweep is **real** (>100 samples, >1 GHz span, >50 distinct values). And the deck now writes
a **curve file** with all arithmetic done in Python, keeping ngspice's control language out of the
critical path. **The three decks that worked first time were all single-`.param` + `alter` + `print`.**

**A sign error the regression suite caught:** `RF-LOSS` was written `g − BASELINE`, which turns a real
3 dB loss into −3 dB and **silently passes a <1 dB limit.** The perturbation test caught it; the correct
form is `BASELINE − g`.

### NOT COVERED (stated, not omitted)

| block | why not |
|---|---|
| SX1280 radio, ESP32-S3, regulators | **no SPICE models.** Vendor models required. |
| **TVS clamp (`D_CLAMP`)** | **THE PART IS NOT CHOSEN** — its schematic value is literally `"TVS clamp (set point TODO(unverified))"`. Simulating an unchosen part asserts nothing. See below. |

### The TVS block — five failed attempts, recorded so they are not repeated

**Every version produced a plausible-looking number while measuring the wrong thing:**

| attempt | reported | the actual fault |
|---|---|---|
| v1 | 8.5 V | **wrong method** — a voltage pulse through a source resistance cannot reach the limit: `V = (Vin·Rd + Vclamp·Rs)/(Rs+Rd)`. TVS specs quote Vclamp **at a defined Ipp**. |
| v2 | 3.3 V ×6 | a 3.3 V source on the same node **absorbed all the current**, so the clamp never conducted. Six identical values was the tell. |
| v3 | 3.3 V ×3 | same fault via a 0 V source — **a 0 V source still forces its nodes equal.** |
| v4 | 0.83 V | **diode oriented backwards** — forward-biased at 0.8 V, never reaching breakdown; acting as a rectifier, not a clamp. |
| v5 | 9.99e+08 V | rail "disconnected" by a 1e9 resistor left **nothing to sink current**, so the node rose without limit. |

**The deeper lesson: `Vbrk` is not a breakdown parameter of ngspice's stock `D` model — it is silently
ignored.** So the clamp never conducted in *any* version, and each fix addressed a symptom while the
core model stayed inert. **A real TVS needs a vendor subcircuit, not a stock diode.**

**To close this block:** (1) **choose the TVS part** (`D_CLAMP`'s standoff is a TODO), and (2) **obtain
its vendor SPICE model**. Only then does a deck assert anything real. **Recorded so the absence is
visible rather than assumed safe.**

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
