# PROGRESS — cluster: FLRC-max 433 MHz downlink trade (branch design/ground-station-flrc-max)

Task: 433 downlink FIXED on FLRC at maximum throughput (LoRa rejected). Compute the
balloon-TX-power vs ground-dish-size trade, mesh viability, rate adaptation, source the
real parts, deliver a cited doc + ADR + consultant verdict.

## Milestones
- [x] M0 read prior art (branch `design/ground-station-lowpower-link` @4b90be94 incl.
      ADR-066, doc `ground-station-lowpower-link-and-shared-dish.md`; branch
      `design/ground-station-bom` @283cad72, doc `ground-station-bom-candidates.md`).
      Not re-derived.
- [x] M1 worktree `/home/c03rad0r/worktrees/bf-flrc` off `github/main` 09e1b69.
- [x] M2 model `docs/analysis/ground_station_flrc_max_model.py` (trade table,
      rate-vs-range, mesh wind, F33 cost, hole rule) — runs, prints every table.
      Note: needs `/usr/bin/python3` for matplotlib; plain `python3` in this shell is
      `/home/c03rad0r/.local/bin/python3` and has NO matplotlib.
- [x] M3 doc `docs/analysis/ground-station-flrc-max-throughput.md` + commit + push
      (github then ngit). Commit `daa57a4`.
- [x] M4 external sourcing, all fetched this session HTTP 200: RF Hamdesign mesh-dish
      pages 1.0/1.2/1.5/1.9/2.4/3.0/4.5 m + Oct-2026 price list PDF + SPID BIG-RAS
      spec sheet PDF; Gibertini OP100SE vendor wind load (91 kg @ 120 km/h);
      jaera.de welded-mesh category (hole+wire+Durchlass); metal-market.eu
      (hole+wire+price); drahtgewebe-shop.de (hole+wire table). Bing RSS endpoint was the
      only working search surface (DDG/Mojeek/Google/Bing-HTML are bot-walled).
- [x] M5 consultant round 1: served model **gpt-6-astra**, answer verdict **REFUTE** with
      a real finding (the 3.00 m mesh bar sits AT the 1.00x rating line, which
      contradicted the loose framing in my question). Artifact fixed (orange bar + explicit
      "AT the rating, no margin" call-out + figure footnote for the lever-arm assumption),
      claim statement tightened in doc 4.3/6 and ADR-067 Decision 4.
      NOTE: `visual_consult.py`'s `visual_review: APPROVED` line is the CLI's `--verdict`
      DEFAULT, not the model's opinion — the model's own verdict is in the answer body.
      Reported honestly.
- [~] M5b consultant round 2 (re-consult on the FIXED figure) — retry loop running
      (`/tmp/consult_retry2.sh`, log `/tmp/consult_retry2.log`); the lane is flaky (503
      "all candidate lanes busy or capped" is the recurring failure).
- [x] M6 ADR-067 written; ADR-066 brought onto this branch and marked
      "Superseded by ADR-067"; `scripts/gen_adr_index.py` regenerated INDEX.md
      (066 = Superseded by ADR-067, 067 = Proposed, next free 068).
      **066 is RESERVED, not free**, despite `adr_next_number.py` returning 66 here
      (066 exists on the pushed branch design/ground-station-lowpower-link @4b90be94).
      Commit `08c14ad`.
- [ ] M7 finalise doc 7 + REPORT.md + final commit/push.

## Headline results (so a restart does not need to re-derive)
- reqG = S + FSPL - P_tx - G_balloon, G_balloon = 0 dBi, FSPL(433.05 MHz, 650 km)
  = 141.4 dB; D = (lambda/pi)*sqrt(10^(G/10)/eta), eta = 0.55, lambda = 0.6923 m.
- FLRC 2.6 Mbps (S = -100.5 dBm): +13 dBm -> 27.9 dBi / **7.38 m**; +22 -> 18.9 / 2.62 m;
  +33 (F33) -> 7.9 / **0.74 m**.
- FLRC 650 kbps (S = -107 dBm): +13 -> 21.4 / 3.49 m; +22 -> 12.4 / 1.24 m; +33 -> 1.4 / 0.35 m.
- The F33's +20 dB = x10.0 diameter, x100 reflector area.
- Mesh wind: Cd = 1.38 DERIVED from the Gibertini OP100SE vendor figure; BIG-RAS brake
  torque 2,712 N.m (fetched). 2.4 m / 2.62 m: SOLID 1.88x / 2.45x the rating;
  6 mm mesh (sigma 0.265) 0.50x / 0.65x; 3.00 m mesh 0.97x (AT the rating); 3.49 m 1.53x.
- lambda/10 at 433 MHz = 69.2 mm; the vendor's 6 mm mesh is rated to 6 GHz (= 1.20 x
  lambda/10 there) and the 2.8 mm option to 11 GHz (= 1.03 x lambda/10) -> the vendor
  corroborates the rule at its own limit; at 433 MHz the mesh is 11.5x finer than needed.
- F33 balloon cost: +2.8 g module (4.0 g vs 1.2 g bare), 5.50 W @ 5.0 V (6.15 W @ 5.5 V),
  contradicts docs/PAYLOAD-WEIGHT-ESTIMATES.md D ("ground station only") -- flagged.
- Sourced dishes: RFH FPD 1M0/1M2/1M5/1M9 in stock (EUR 342.43/387.20/499.73/901.45);
  FPD 2M4 and 3M0 OUT OF STOCK; 4.5 m production ceased 2024.
- Positioners: SPID BIG-RAS EUR 1,775 (2,712 N.m brake, 318 kg vertical, 22 kg);
  SPX-01 EUR 1,132; SPX-06 slew EUR 5,487.35.
