# PROGRESS — design/amplifier-substitution (ground-station amplifiers vs antenna gain)

Task: test whether ground 2.4 GHz PA (uplink) + 433 LNA (downlink) is a cheaper way to buy
link budget than antenna gain, and whether it collapses the antenna-tracker requirement.
Cost + gain-per-euro only (regulatory explicitly out of scope per operator).

## Milestones

- [x] M0 — repo reconned; worktree `bf-amps` on branch `design/amplifier-substitution` off
      `github/main` tip `09e1b69`. Bands confirmed against ADR-034 (433 TX down / 2.4 GHz RX up).
- [x] M1 — `docs/analysis/ground-station-amplifier-vs-antenna.md` (full analysis, all sourced),
      `docs/analysis/ground_station_amp_vs_ant_model.py` (repro command), this file.
      → pushed github + ngit.
- [x] M2 — figure (SVG→PNG, `docs/analysis/ground_station_amp_vs_ant_figure.py`) +
      visual-consultant verdict verbatim in `docs/analysis/assets/consult-verdict-amp-vs-ant.txt`.
      Consultant served model **`gpt-6-astra`**, `visual_review: APPROVED`; substance CONFIRMED
      with qualifications; layout iterated 4 rounds → final CONFIRM.
- [x] M3 — ADR draft `docs/adr/068-ground-station-amplifier-vs-antenna.md`
      (068 verified free on **all** github/ngit branches; 066/067 already claimed elsewhere;
      `scripts/adr_next_number.py` not present in this repo → manual check recorded in the ADR).
- [x] M4 — REPORT.md + final push + ls-remote SHA evidence.

## Sourced price/spec base (all fetched, URLs in the doc)

- 2.4 GHz PA: DXpatrol QO100-PA-1W €69 (2300–2500 MHz, +30 dBm, 12 dB gain, 5V/450mA);
  QO100-AMP12 €185 (LDMOS ~24 dB gain, 12 W@28V); RT-2400-2 €355 (discontinued, NF 3.2 dB).
- 433 LNA: SSB Electronic LNA ISM 433 €257 (20 dB gain, NF 0.7 dB, selective BPF).
- 2.4 GHz LNA: SHF mast preamp 6m–13cm €219. 70cm preamps €151.90–€345.
- Coax relay CX-520D €156.50. Sequencer DCW-2004 B €342.
- Antennas: 433 Yagi €69–215 (5–14 dBi/€); Ku dish 0.75–1.0 m €94.90–143.90 + feed €185;
  13cm Yagi €239. Coax Ecoflex 15 €13.60/m.
- Trackers: DIY €40; G-450CDC €359–399; G-5500DC €949; SPID RAS €1,260.82; BIG-RAS €1,775.
- Datasheet: LR2021 abs-max RF input +10 dBm (Table 3-1); blocking −20…−32 dBm.

## Key results

- €/dB: 433 Yagi 13.1→14.8 dBi = €3.24/dB; 433 LNA *effective* = €40.4/dB (not €12.85 — cascade
  caps LNA benefit at ~6.4 dB); 2.4 GHz PA = €5.75–8.30/dB; 2.4 GHz dish+feed = €15.6–19.9/dB.
- Tracker: 7.3° beam (27 dBi) → 0.73° budget → commercial az/el (€1,260+). 29–82° beams →
  open-loop stepper (€40). Tracker collapse = ≈€1,220 saving, driven by the ANTENNA not the amp.
- Breakdown points: receive ceiling ~6.4 dB; T_ant penalty 4.63 dB@2.4G / 3.17 dB@433;
  balloon RX overload — 12 W + 27 dBi = 772 m keep-out (abs-max +10 dBm); self-desense — 12 W
  blocks co-located 433 LNA at <10 m; DC — 12 W PA ≈27 W DC (car battery).
- 3 stations: A antenna-led €2,045/35 dB/€58.4 per dB; B amplifier-led €1,041/42.2 dB/€24.7;
  C balanced €1,032/41.8 dB/€24.7 → **C recommended**.

## Notes / gotchas

- `docs/analysis/` exists on main but NOT in the stale checked-out `repos/balloon-fresh`
  tree (that tree is on branch `feat/tracker-tx-tempcomp`); read from the `bf-amps` worktree.
- curl needs a browser UA: digikey/mouser/minicircuits 403 on bare curl; wimo/rfhamdesign OK.
- No matplotlib in system python; figures built as SVG then rasterised with `cairosvg`.

## Push evidence (final)

Branch `design/amplifier-substitution`:
- LOCAL  : 02fb4a154d557969dfbde417817e5f44e84f8407
- GITHUB : 02fb4a154d557969dfbde417817e5f44e84f8407
- NGIT   : 02fb4a154d557969dfbde417817e5f44e84f8407
(pushed github first, then ngit separately; verified with `git ls-remote` on BOTH.)
