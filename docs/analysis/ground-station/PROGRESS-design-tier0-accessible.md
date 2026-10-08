# PROGRESS — design/tier0-accessible

**Goal:** find and cost an ULTRA-LOW-COST accessible tier BELOW Tier A, and re-cost Tier A now that
the 2.4 GHz dish is known to be unnecessary. Lead with the EIRP-cap question.

## Log

- **Setup** — fetched `github` + `ngit`; worktree `bf-tier0` on `design/tier0-accessible` from
  `github/main` @ `09e1b69`. 206 remote branches; confirmed **ADR 066/067/068 are claimed on other
  branches, 069 is free** on every `github/*` branch.
- **Read the priors** (via `git show github/<branch>:<path>`): `positioner-lowcost-3dprinted.md`
  (right-sizing, EIRP cancellation, €726 total incl. dish+feed), `ground-station-bom-candidates.md`
  (all CONFIRMED prices), `ground-station-flrc-max-throughput.md` (F33 → 0.74 m dish), `dualband-…`,
  `ground-station-gain-per-dollar.md` (sweet spots + positioner menu P1 €429).
- **Wrote the model** `docs/analysis/tier0_accessible_model.py` (stdlib only; every table below).
- **Wrote the doc** `docs/analysis/tier0-accessible-ground-station.md`.
- **Commit 1** `e37909b` — committed EARLY (loud lesson from sibling tasks that died on HTTP 503).
  Pushed **github first**, then **ngit separately** (both `design/tier0-accessible`).
- **Figure** `docs/analysis/render_tier0_figure.py` → `figures/tier0-eirp-capped-uplink.png`
  (needs a matplotlib interpreter: `/opt/miniconda/bin/python3`; the default `python3` has no
  matplotlib).
- **Consult round 1** — `gpt-6-astra`, 200. **Qualified REFUTE** (panel-A over-claim of universal
  inertness; unlabelled 1.2 m dish; €926/927 mismatch; panel-B "cannot" too absolute; panel-C saving
  approximate).
- **Fixed** figure labels + doc wording; added **Table 1c** for the balloon-LNA dependency of the
  2.4 GHz uplink (a real honesty gap — the no-LNA case fails at 650 km and a ground dish does **not**
  fix it).
- **Consult round 2** — `gpt-6-astra`, 200. **PASS WITH MINOR REVISION** (1.2 m label occluded;
  qualify "uplink-margin-equivalent"; separate system-level claims; state the cap conditions).
- **Fixed** the figure (dish labels above the plot, legend lower-right, scoping footnote, panel
  titles) and the doc (§1.3 conditions, §1.4 qualification, §5 cross-reference, §4 parts-cost scope).
- **Commit 2** `b8d4dd2` → github.
- **Consult round 3** — `gpt-6-astra`, 200. **Minor revision still required** (panel-B "enough";
  panel-C endpoint wording).
- **Consult round 4** — `gpt-6-astra`, 200. **NOT YET ACCEPTABLE.** This round found a **real
  defect**: the dish+feed is **€325.90**, not the €314.90 the first draft said — corrected
  everywhere. Also: qualify "equivalent" (uplink-margin only), qualify Tier-0 as conditional,
  rebuild the figure for label/footnote clearance.
- **Consult round 5** — `gpt-6-astra`, 200. **CONDITIONAL PASS**; the model itself verified the
  corrected arithmetic (€326−€60=€266 … €951−€616=€335). Fixed panel-A title collision + panel-C
  title clipping; adopted the safer headline phrasing.
- **Consult round 6** — `gpt-6-astra`, 200. **PASS**, "no material new over-claim".
- **Cycle:** REFUTE → PASS-WITH-MINOR-REVISION → Minor → NOT-YET-ACCEPTABLE → CONDITIONAL PASS →
  PASS (6 rounds, 12 findings, all fixed; §8 of the doc records every verdict verbatim).
- **Commit 3** `cd4fe35` → github. **Commit 4** = rounds 3–6 + arithmetic fix → github + ngit.
- **Search backends captcha-gated again** (Brave 429, DDG 202, Mojeek captcha, Ecosia 403, eBay 403,
  wimo/Reichelt search JS-gated) → new cheap items stay `TODO(unverified)`, never invented.

## Key numbers banked

- Useful ground 2.4 GHz gain = **20 − 12 = 8 dB**; a 0.6 m dish is **13.4 dB inert**, 1.2 m **19.4 dB**.
- Max compliant uplink margin **+17.4 dB @300 km / +10.7 dB @650 km**.
- 433 LoRa @650 km req gain **−13.7 dBi** (omni closes +13.7 dB). F33 FLRC 2.6 Mbps @650 km req
  **+7.9 dBi** (a 13.1 dBi Yagi ⇒ +5.2 dB). Low-power FLRC 2.6 Mbps @650 km req **+18.9 dBi** (dish).
- Tier 0a **€90–245**; Tier 0b **€144–304**; Tier A re-costed **€616–685** (DIY) / **€546–615**
  (Yaesu G-450CDC €359); Tier A original **€927–951**.
