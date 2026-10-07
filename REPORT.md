# REPORT — Brief 5 re-dispatch

## Outcome
Delivered `docs/SOLAR-PIN-REGULATORY.md` with all four sourced number-sets.

## Answers (tight)

1. **ADR-006 array verdict**: YES — 120 cm² / 2.4 W covers the average load (63× the 1 %
   duty avg) and recharges one 20 J burst in **15.9 s rigid / 35 s thin-film** (< 60 s).
2. **Panel area**: average 1 % duty = **1.91 cm² rigid / 4.20 cm² thin**; recharge one
   burst = **31.8 cm² rigid (~3.2 cells) / 70.0 cm² thin (~7.1 cells)**. Derate 0.35.
3. **C3 vs S3**: C3-WROOM-02 exposes **15 GPIOs**; a 3-radio basic design needs **18**,
   PA variant **24**. **C3 does NOT fit → S3 (or expander/mux) REQUIRED.** Strap pins
   GPIO2/8/9 conflict as stated (GPIO8 has no ADC).
4. **2nd harmonic**: 433 × 2 = **866 MHz, inside 868 band** (863–870 MHz) — the reason
   ADR-034 forbids 433-TX/868-RX and pairs 433-TX with 2.4 GHz RX.
5. **433 MHz legality**: **2 W is NOT legal licence-free** (10 mW ERP cap, integral
   antenna); 2 W needs an amateur licence. DE licence-free 433 MHz RC use ended 2008.
6. **Cutdown mass**: ~0.5 g/channel (MOSFET 0.02 g + nichrome + tether); released mass
   beats mechanism mass.
7. **UNVERIFIED**: exact cell η (0.22/0.10 typical), ERC 70-03 Annex 1 duty-cycle
   (current revision), ballast-jettison airlaw (unknown), arm-gate + shot/sand masses.

## SHAs
See final reply (observed via `git ls-remote`, not assumed).
