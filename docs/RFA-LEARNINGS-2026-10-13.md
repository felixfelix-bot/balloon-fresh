# RFA Research Learnings — LR2021 bent-pipe alternatives & ELRS driver audit (2026-10-13)

**Provenance:** triggered by an operator-pasted Google-AI-Mode thread (pico balloon as
bent-pipe internet gateway; LR2021 vs SX1280/CC1200/Wi-Fi HaLow/ExpressLRS). Every
load-bearing claim below was verified against primary sources (datasheets, driver source,
kernel source, GitHub API) — not against the paste. Two companion reports:
`docs/RFA1-ELRS-LR2021-DIFF-2026-10-12.md` (this PR) and
hermes-manager-skills `research/ai-claim-vetting/references/rfa2-halow-coverage-class-verdict-2026-10-12.md`.

---

## 1. Our firmware is missing the vendor patch layer (HIGHEST VALUE)

ExpressLRS unconditionally loads a **560-word PRAM patch** in `Begin()`
(`src/lib/LR2021Driver/LR2021.cpp:112` → `LoadPatchRAM`; writes 32-bit words to
`0x801000` in 12-word chunks so command+payload fits the 64-byte SPI buffer; enables via
`LR2021_PATCH_ENABLE_PRAM_OC` = `0x012D`). Our raw-SPI firmware **never uploads a patch**
(`grep pram|patch` over `firmware/rp2040/src/` and `lr2021_transport/src/` → 0 hits).

A patch RAM is the vendor's post-silicon PHY-fix channel. An unpatched chip is a strong
root-cause candidate for our **open** anomaly: 64 B / 128 B payloads at FLRC 260/650 kbps
→ 200/200 CRC errors while 255 B is clean (payload-length- AND bitrate-dependent =
classic PHY-side signature). Note the 255 B case is **closed** (wrong FIFO-clear opcode
`{0x01,0x1E}` vs correct `{0x01,0x20}`, see `docs/255-BYTE-PACKET-INVESTIGATION.md`) —
the short-payload case is the remaining mystery.

**Settling experiment** (bench, needs board + flash approval): upload the ELRS PRAM table
through our opcode path, re-run 64 B/128 B @ 260/650 kbps + 255 B control. A flip to clean
confirms the hypothesis.

## 2. Cheap init deltas vs ELRS (candidate fixes, each one line)

| Delta | Ours | ExpressLRS | Where |
|---|---|---|---|
| `SYSTEM_CALIBRATE` arg | `0x5F` | `0x7F` | our `init_sequence` vs `LR2021.cpp:147` |
| calibrate settle | 5 ms | **10 ms** | ours vs `LR2021.cpp:148` |
| front-end calib settle | 5 ms | **30 ms** | ours vs `LR2021.cpp:152` |
| standby after reset | `STDBY_XOSC` | `STDBY_RC` | ordering differs; patch loads FIRST |
| PA ramp | `0x04` = 32 µs | not extracted | datasheet Table 7-21 (2 µs … 128 µs) |

Unsettled calibration is a classic cause of flaky, band-dependent sensitivity. Raising
our two delays to 10/30 ms costs nothing. Our own source already carries the comment
"`0x5F` (NOT `0x6F`)" — this byte has bitten us before; prefer the vendor-adjacent `0x7F`
unless the datasheet says otherwise.

## 3. AI-Mode paste: verdict summary (why we verify)

| Claim | Verdict |
|---|---|
| ELRS "has LR2021 support planned" | **Stale-by-weeks**: PR #3697 MERGED 2026-08-19 onto master (60 files, `src/lib/LR2021Driver/`). Release 4.1.0 (2026-07-17) predates it — build from master, not the tag. |
| CC1200 "+14 dBm, 1 Mbps" | Datasheet Rev. D: **+16 dBm, 1.25 Mbps**. CC1101: +12 dBm, 600 kbps. The "5–15 km / 25+ km / 2 W PA" range figures are TI marketing; a 2 W PA is illegal in EU SRD anyway. |
| "Formosa Drone … spinning LR2021 modules" | **FABRICATED vendor** (GitHub knows only a Brazilian drone-services shop). |
| "OpenFLRC" library ecosystem | Marginal (1 repo, 0 stars). The real SX1280 FLRC ecosystem is RadioLib — which we already use. |
| `iw dev wlan0 set distance 50` extends HaLow | **Wrong syntax** (PHY command) **and FABRICATED mechanism** — see §4. |
| CC1200/CC1101 "no hardware ACK timeout" | TRUE (dumb packet engine: sync word + length + CRC; timeout is host software). |

## 4. HaLow long-range: the knob does not exist (NOT-REACHABLE, both vendors)

Traced end-to-end (iw → nl80211 → cfg80211/mac80211 → driver), independently re-verified
by live greps of both trees:

- **Morse Micro**: `morse_wiphy_set_wiphy_params` (`wiphy.c:1305`) handles only
  RTS/FRAG thresholds and **ignores** the `WIPHY_PARAM_COVERAGE_CLASS` bit → returns
  success while doing nothing (**silent no-op**, fullmac). The softmac path
  (`mors_ops`, `mac.c:5920`) has no `.set_coverage_class` → `-EOPNOTSUPP`. The only
  `coverage` in the whole tree is the S1G **Country-element** field
  (`dot11ah/reg.c:132`, hard-coded 0) — a management-frame byte, not a PHY knob.
- **Newracom**: `nrc_mac80211_ops` has no `.set_coverage_class` → `-EOPNOTSUPP`. No
  distance/slot/ACK-timeout parameter anywhere (CLI exposes `set gi`, `set ack_mode`,
  `set txpwr`, `set rc`, `set maxagg`; module params are fw/bd/ack/bi flags).
- **Root of the paste's error**: coverage class is a **legacy OFDM-PHY dynack mechanism**
  (IEEE 802.11-2007 §17.3.8.6, consumed by ath9k/ath10k at 2.4/5 GHz), NOT an 802.11ah
  S1G mechanism. The AI extrapolated from regular WiFi.

**What actually extends HaLow range**: 1 MHz channels + MCS0/MCS10 (BPSK ½ ×2 repetition,
0.17 Mbps @ −107 dBm per MM6108 Table 15) + long GI + ACK mode. The ~1 km figure is a
link-budget design point, not a protocol ceiling (WiLongH, IEEE OJ-COMS 2025, measured
voice >1 km at 1 MHz). Cost of max-range config vs max-throughput: ~**194×** PHY-rate
(0.17 vs 33 Mbps).

**Strategic takeaway for the bent-pipe project**: LR2021 stays the right chip — HaLow
modules don't fit the 15–30 g budget, don't offer a distance knob, and their range trick
(MCS10 repetition) buys sensitivity at 100× rate cost, which a data link can't afford.

## 5. Method learnings (transferable)

- **Diff against a second independent implementation.** We ran our raw-SPI init for
  months without cross-checking against RadioLib/ELRS. One afternoon of diffing surfaced
  the missing patch layer + two cheap deltas. Rule: before debugging a PHY anomaly on
  bespoke register code, diff against every public driver for the same silicon.
- **Datasheet beats marketing rows.** Every rate/power/range number in the paste needed
  the datasheet PDF (`pdftotext` + targeted `sed -n` on the section) to correct.
- **"Coming soon" release notes age in weeks.** The paste said "planned"; the merge had
  already landed a month earlier. Always resolve to the actual PR merge date.
- **Trace a userspace knob to its kernel consumer.** `iw` accepting a command proves
  nothing; the decisive question is whether any driver in your hardware's tree
  implements the callback. (`grep -rn set_coverage_class <driver tree>` → 0 hits is a
  complete answer.)
- **Beware thinking-mode lanes for delegation.** Both analysis subagents died to
  `HTTP 400: reasoning_content must be passed back` (DeepSeek thinking mode) — their
  on-disk artifacts (clones, extracted datasheets, transcripts) were still recoverable;
  salvage-first beats re-dispatch.

## 6. Open items

1. PRAM experiment (bench, gated on board slots + flash approval via FLASH-QUEUE.md).
2. Firmware deltas card: calib `0x7F` + settle delays 10/30 ms (+ consider faster PA ramp).
3. Not extracted (bounded follow-up if ever needed): ELRS's FLRC modulation-param field
   encode for Q2, their band-split threshold, their PA ramp choice, and what the 560-word
   patch actually fixes (opaque words; no public changelog found).
