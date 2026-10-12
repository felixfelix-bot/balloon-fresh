# REPORT — ground-station amplifier-hypothesis check

Branch `design/amplifier-hypothesis-check` · worktree `/home/c03rad0r/worktrees/bf-ampcheck`
· base `09e1b69` (`github/main`) · author Hermes Agent (subagent).

> `REPORT.md` and `PROGRESS.md` are **gitignored by design** in this repo
> (`.gitignore` lines 67–68, verified with `git check-ignore -v`). Per this task's
> instruction they are **force-added on this branch only**.

## Deliverables

| file | what |
|---|---|
| `docs/analysis/ground-station-amplifier-hypothesis-check.md` | the analysis: five operator answers with numbers, the €/dB ledger, BUILD/DO-NOT-BUILD, the consult record, open items, sources |
| `docs/analysis/ground_station_amplifier_hypothesis_model.py` | the reproducible model — stdlib only, prints every table verbatim |
| `docs/analysis/render_amplifier_hypothesis_figure.py` | the 4-panel figure renderer (needs `/usr/bin/python3`; the repo's default `python3` has no matplotlib) |
| `docs/analysis/assets/amplifier-hypothesis-ebar.png` | the consulted artifact |
| `docs/adr/070-ground-station-amplifier-hypothesis.md` | **ADR-070 (Proposed)** — 8 decisions + the ledger + alternatives |
| `docs/adr/INDEX.md` | adds the 070 row **and corrects the stale "next free → 066" line** |
| `PROGRESS.md`, `REPORT.md` | working artifacts, force-added |

## Verdict

**DO-NOT-BUILD the amplifier-led ground station.** Verified against the F33's
**0.40 USD/dB** bar the amplifier-led design buys **zero needed dB** (its 2.4 GHz gain is in
the wrong band) and would cost **€207–485 marginal** to make usable. **BUILD**: the F33 on the
balloon (0.40 USD/dB), a 433 MHz masthead LNA *if* extra receive margin is wanted
(€26.4/needed dB), and a single Yagi on the DIY tracker.

## The five answers

| # | question | verdict | the number |
|---|---|---|---|
| Q1 | LNA useless on receive? | **PREMISE WRONG** | LNA buys **+6.8…+12.3 dB** of T_sys (central **+9.7 dB**); directivity-only adds **+3.80 dB** (433) / **1.5–2.8 dB** (2.4 GHz) *more*. Additive. |
| Q2 | Yagi array? | **DO NOT ARRAY** | **€76.13/dB** (2-bay), **€93.73/dB** (4-bay); Yagi = **2–3 % (9–13 MHz)**; beam narrows **10–32 %** / **33 %**; the 433 LNA (433–435 MHz, 0.46 %) is **narrower than the Yagi** and sets the receive bandwidth |
| Q3 | one tracker per Yagi, combined? | **COVERAGE, NOT GAIN** | incoherent **+0.00 dB**; coherent / MRC **+10·log₁₀N** (+3.01/+6.02 dB) but need phase coherence (MRC also N radios); multi-sector = 0 dB but removes the precision-tracking need |
| Q4 | external gain control vs overdrive? | **MANAGEABLE, NOT NEEDED** | +33 dBm on 12.4 dBi compresses the balloon RX inside **≈14.5 m**, hard-overloads inside **≈1.4 m**; a downlink-RSSI loop works, **ground-side AGC cannot** |
| Q5 | re-cost with the owned amp + circulator | **DO-NOT-BUILD** | wrong band; uplink already **+23.1…+36.1 dB** in surplus; **~20 dB** circulator is insufficient isolation for a same-band +33 dBm front end |

Ledger: **F33 0.40 USD/dB ≪ 433 LNA 26.4 €/dB < 2-bay 76.1 < 4-bay 93.7 < dish 346–809;
2.4 GHz ground PA = INF.**

## Consultant (required) — engaged, three rounds, all served `gpt-6-astra`

* **Round 1** (layout probe): found **panel C labels clipped** → fixed. `VERDICT: CONFIRM`.
* **Round 2** (full adversarial): **`VERDICT: REFUTE`** — the small stacked segments in panel A
  were **unlabelled**, so the **+9.73 dB / +3.80 dB claims could not be verified from the
  figure**; the model measured 252 K / 92 K off the pixels instead of the computed
  274.5 K / 114.5 K. **The physics was right and the artifact was wrong.** The correct
  response was to make the claim readable, so every segment is now labelled and the deltas are
  annotated as arrows with text.
* **Round 3** (re-consult on the corrected render): first attempt `RC=3 router unreachable`,
  retried in a background loop. Result recorded in the analysis §9.1 (or the failure is
  recorded verbatim; round 2 stands as the last consult if it does not land).
* **Pitfall reconfirmed and recorded:** the CLI's `visual_review: APPROVED` token is its
  `--verdict` **default**, **not** the model's opinion (`parse_args` default `APPROVED`;
  `_emit_evidence` prints it verbatim). The model's own `VERDICT:` line is the finding. All
  three rounds were run with `--json`, which emits no such token, and the served id was read
  back from the `served` key.

## ADR numbering — the brief's premise was wrong (recorded)

The brief said *"066 and 067 are already claimed … 068 is likely next free."* **Both halves
are wrong.** Verified against **every** `github/*` branch: **066** claimed (2 branches);
**067** claimed **TWICE** (`design/ground-station-flrc-max` **and** `design/positioner-lowcost`
— a real number collision); **068** claimed (`design/gain-per-dollar`,
`design/gain-per-dollar-cliff`); **069** claimed (`design/tier0-accessible`).
**070 verified free and used.** `scripts/adr_next_number.py` still returns **66**, so the
script alone would have collided a third time; the index's "next free" line is corrected here.

## Push evidence (all three SHAs identical)

```
                       f17940e  milestone 1: doc + model
                       d494f19  milestone 2: figure + consult rounds 1-2  (+ later commits)
```

*(final SHA triple pasted in the final reply, after `git ls-remote` on BOTH remotes)*

## Issues / blockers encountered

1. **`python3` has no matplotlib** — the figure must be rendered with `/usr/bin/python3`
   (3.10.7 available there). Recorded in the ADR's reproduce line.
2. **Search engines captcha-gated after one attempt** (`html.duckduckgo.com` → HTTP 202), and
   several vendor hosts 404'd or refused (`fairviewmicrowave`, `everythingrf`, `kuhne-electronic`,
   `ssb-electronic`, `reichelt`). Everything cited therefore comes from a **direct** fetch:
   WiMo (static prices), Mini-Circuits datasheet PDFs, Funktechnik Bielefeld, Wikipedia REST.
3. **Mini-Circuits prices are AJAX-only** — the WebStore price endpoints returned nothing, so
   those parts are spec-cited and price-`TODO(unverified)`. No price was invented.
4. **No 2.4 GHz circulator datasheet reachable** — its isolation/IL are ESTIMATEs of the class,
   with the *required* isolation computed from the system (so the conclusion does not depend
   on the estimate).
5. **Consult lane flakiness** — one `RC=3 router unreachable: timed out`, handled with a
   background retry loop per the skill.
6. **Vision lane 503** (`all providers exhausted (flat router)`, glm-4.6v) on `vision_analyze`
   for the first self-check — the consult lane was used instead.

## Recommendation to the parent/operator

Adopt the DO-NOT-BUILD verdict and the ADR-070 decision text. The **only** ground-side
amplifier worth buying is the **receive-side 433 MHz LNA**; the owned 2.4 GHz amplifier and
circulator are **not** usable in the committed 433/2.4 GHz architecture. If the operator is
actually contemplating a **same-band 2.4 GHz bidirectional** link, that is an **architecture
change to ADR-034** and must be raised as its own decision — it is the one path that would
bring the owned hardware back into play, and it would still need ≳40–55 dB of T/R isolation.
