# REPORT — docs/licence-exempt-design-point

**Status: COMPLETE.** All deliverables written, committed and pushed to all three remotes,
every ref verified by `git ls-remote`.

## Deliverables
| File | Status |
|---|---|
| `docs/licence-exempt-design-point.md` | written, committed, pushed |
| `docs/adr/039-licence-exempt-433-design-point.md` | written, committed, pushed |

## Commit
`14274f3bd2b5ab513483f8857d23a879c09131c6` — `docs: licence-exempt 433 MHz design point + ADR-039`
(branch `docs/licence-exempt-design-point`, base `144c819`).

## Push verification (observed SHAs)
| Remote | URL | `git ls-remote <remote> refs/heads/docs/licence-exempt-design-point` |
|---|---|---|
| github | https://github.com/felixfelix-bot/balloon-fresh.git | `14274f3bd2b5ab513483f8857d23a879c09131c6` |
| ngit | nostr://npub1nng5…/relay.ngit.dev/balloon-fresh | `14274f3bd2b5ab513483f8857d23a879c09131c6` |
| origin | https://github.com/felixfelix-bot/balloon-fresh.git | `14274f3bd2b5ab513483f8857d23a879c09131c6` |

All three match HEAD. Push order: github → ngit → origin sequentially. No force-push.

## ADR number
`ls docs/adr/` run once. 039 **was free** (present: 031/032/034/035/036/037; absent:
033/036/038). Used the briefed number 039 — no substitution.

## Content decisions recorded
- **Authority recorded, not re-litigated:** operate licence-exempt at 433.05–434.79 MHz at
  ≤10 mW ERP with integral antenna instead of the DE amateur licence.
- **Corrected premise recorded:** "below 1 W is compliance-free" is WRONG; DE 433 cap is
  ~10 mW ERP + integral antenna; DE ended licence-free 433 remote control in 2008; "1 W" is
  the US 915 MHz Part 15 rule.
- **Citations:** ERC/REC 70-03 Annex 1 named as primary, with the exact Annex-1 table row
  marked **`TODO(unverified)`** (row text not read this session).
  `docs/SOLAR-PIN-REGULATORY.md` @ `bc50dacd` cited as in-repo secondary source.
- **Per-band table** produced: 433 ≈10 mW ERP / integral antenna; 2.4 GHz 100 mW EIRP;
  868 MHz explicitly **not used**.
- **Link budget** per ADR-041 (`adr/rf-frontend-licence-exempt` @ `a419e7d`): binding
  direction is the **2.4 GHz uplink**; 433 downlink closes at **+24.3 dB** with a 12 dBi
  ground Yagi; 2.4 GHz uplink **+16.4 dB with F33 internal LNA (DIO5 HIGH) / +4.4 dB
  without / +0.4 dB with 6 dBi antenna**. The earlier "+6.4 dB with LNA / −5.6 dB without =
  the no-LNA link FAILS" framing is recorded as **mis-applying the 433 10 mW cap to the
  2.4 GHz uplink and SUPERSEDED** (correct drop 17 dB; no-LNA is thin, not failed).
  Cross-refs ADR-037, ADR-005.
- **Ground-gain recovery:** ground receive gain/LNAs unregulated, no balloon mass; ground
  Yagi recovers the downlink loss. 2.4 GHz uplink is ground-transmitted at 100 mW EIRP so
  it does not take the same hit.
- **Hard requirement:** firmware TX clamp ≤10 mW ERP + production test proving it
  (conducted power = 10 mW minus antenna gain); **2 W F33 PA and the bare 22 dBm module are
  over-limit**.
- **Removed:** callsign frame, plain-telemetry/no-encryption duties (amateur obligations).
  `docs/regulatory-amateur` becomes the rejected-alternative record — **not deleted**.
  **Remains:** non-interference, no protection from interference, duty cycle, antenna/ERP
  cap. Actual beacon duty cycle ~1.7 % (1 s per 60 s) stated against the allowance.
- **Open items flagged, not assumed:** (a) licence-exempt SRD airborne use is a grey area
  (framework written for short-range ground use) — national-regulation check before flight;
  (b) whether a balloon-side LNA is still needed once ground carries the gain; (c) sub-GHz
  FLRC availability on the F33.
- **ADR-039** records: the decision; the corrected premise; consequences (ADR-037 "FEM
  omitted" reopened and settled by ADR-041 → external FEM stays off balloon; F33 PA
  over-limit; clamp + production test required); relation to ADR-034/035/036/037; status
  **Proposed**.

## Issues / notes
- `github` and `origin` are the **same URL** (github.com/felixfelix-bot/balloon-fresh);
  origin's push reported "Everything up-to-date" and its `ls-remote` still returned the
  correct SHA. Pushed sequentially as instructed regardless.
- No conflict encountered on `docs/adr/006-*.md` or `docs/adr/037-*.md` (not edited).
- ngit push reported `Published 1 state event to 1/2 relays (failed: nos.lol)` — the
  ngit.dev relay accepted it; `git ls-remote ngit` confirms the ref.
- No reconnaissance / PDF fetches / link-budget re-derivation performed.
