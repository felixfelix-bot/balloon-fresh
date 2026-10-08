# REPORT — ground-station internet-gateway RF shopping list + duplex architecture

**Branch:** `design/rf-shopping-list` (off `github/main` @ `09e1b69`)
**Worktree:** `/home/c03rad0r/worktrees/bf-shoplist`
**Tip (github == ngit):** `33304dc2880afe3fcd6d3406118ede9820c97a21`
*Gitignored in balloon-fresh; committed with `git add -f` on this branch only.*

## Deliverables

| File | What |
|---|---|
| `docs/analysis/rf-shopping-list-and-duplex-architecture.md` | Main deliverable: TASK 0 duplex verdict first, then sourced parts + one shopping-list table with OWNED marked + totals. |
| `docs/analysis/rf_shopping_list_model.py` | Reproducible model (stdlib, exit 0) — prints every number quoted. |
| `docs/adr/070-ground-station-duplex-t-r-architecture.md` | ADR: two band antennas, no circulator; DSA not PA. **Proposed.** |
| `docs/adr/INDEX.md` | Regenerated to include 070. |

## Answers delivered

1. **TASK 0 — circulator? NO.** TX 2.45 GHz / RX 433 MHz are 5.65× apart; a narrowband
   circulator cannot duplex two bands. Two band antennas give **≈68 dB** isolation vs a
   circulator's ~20 dB at one band only. Deletes the purchase. Residual own-TX→own-RX
   leakage = **−56 dBm** at the LNA input (78 dB below the LNA's +22 dBm CW rating). Fix =
   **433 MHz BPF before the LNA** (+ optional €5–10 limiter).
2. **TASK 1 — PA with gain control.** Under the ISM EIRP/PSD ceiling (14.26 dBm EIRP at
   FLRC-max BW) the conducted need with an 11.1 dBi antenna is **+3.2 dBm** → the LR2021 HF
   PA (+12 dBm) must be turned **down ~9 dB**: **buy a 0–31.75 dB DSA (PE43711-class, €18.89)**,
   not a PA. FEMs with control: **SKY66112-11** (CTX/CRX/CHL pins; +13…+21 dBm via VCC2 ≈ 8 dB);
   discrete RF2126 module €7.69 + DSA; **no integrated PA+circulator exists at this scale**.
   Closed-loop range needed ≈ 40–45 dB.
3. **TASK 2 — circulator (conditional).** Cheapest 2.4 GHz part WG2020X-1 €33.79. Key rule:
   isolation > P_TX − LNA_max_input. **A 20 dB circulator alone does not protect a typical
   LNA** (residual +0…+13 dBm vs P1dB ≈ −10 dBm) — only the rugged TQP3M9037 survives.
4. **TASK 3 — Red Pitaya.** Analog BW **DC–60 MHz** → **cannot** test XR-613 at 433/2.4 GHz
   (buy a **LiteVNA 62**, €166.99) and **cannot** generate FLRC (DAC ≤ 60 MHz). FLRC =
   **GMSK + proprietary FEC** (not "chirp" — brief premise corrected); no public PHY
   reverse-engineering like gr-lora → **not economical**. Valuable only behind a downconverter.
5. **TASK 4/5/6** — 433 RX antenna (A-430S15R €74.50), 2.4 GHz TX antenna (Sirio SLP-17
   €59.00), coax (Airborne 10, 0.76/1.92 dB per 10 m at 433/2.4 GHz), BPFs, limiter,
   shopping list with **OWNED** (TQP3M9037, XR-613, mixer, Red Pitaya) and roll-ups
   (**cheapest ≈ €160**, **recommended ≈ €453** incl. LiteVNA).

## Evidence / hygiene
- Every price carries a URL, marked CONFIRMED (page read this session) / **"from"** (AliExpress
  search listing) / `TODO(unverified)`. Nothing invented; nothing ordered.
- `scripts/param_ssot_check.py` → **PASS (exit 0)**; `git diff --check` clean; model `exit 0`.
- github pushed FIRST, ngit SEPARATELY; both `git ls-remote` == local HEAD.
- No push to main/master; no force-push; `AGENTS.md` untouched.

## Open items (see analysis §8)
XR-613 identity; unmarked mixer specs; RF2126 control pin; nRF21540 gains; Airborne-10 price
discrepancy (€4.30 this session vs €6.50 in the sibling BOM); A-430S10R unverified; AliExpress
"from" prices; DE amateur 2.4 GHz power limits; cheap circulator isolation figures.
