# Analysis — MeshCore LR2021 support and temperature/frequency drift: what the community actually did, what the LR2021 hardware offers, and what FLRC's offset tolerance costs us

> **STATUS: ANALYSIS.** This is an analysis document, **not** an ADR. It records
> findings from an external open-source project and from primary vendor documents,
> and it carries a recommendation in §6. It **orders nothing** and **changes no
> design file**. No decision is taken here; §6 is advice to the decision owner.

- Date: 2026-10-07
- Repo: `balloon-fresh`, branch `analysis/meshcore-lr2021-drift`
- Author: Hermes subagent (delegated research task)
- Scope: (a) the MeshCore/community PRs and issues about **adding LR2021 support**,
  (b) the community **temperature/frequency-drift** discussion and its real
  mechanism, (c) what the **LR2021 silicon** provides for this, (d) the
  **FLRC-vs-LoRa frequency-offset tolerance** numbers, (e) what it means for our
  balloon. Explicitly **out of scope**: the oscillator-heater question, which a
  separate concurrent worker owns. Nothing here is written to their file.
- Epistemic rule applied throughout: every quoted string was fetched from the
  named URL or the named local PDF on this date. Every conversion is arithmetic
  shown in the text. Anything I could not confirm is marked `TODO(unverified)` in
  §7, and every search that returned nothing is reported as **empty** rather than
  filled in.

---

## 1. Repositories searched, and how

| Item | Value |
|---|---|
| Method | GitHub REST via `gh` CLI, authenticated as `felixfelix-bot` (token scopes incl. `repo`), so ~5000 req/h — the 60/h unauthenticated limit was not a constraint. |
| Search APIs used | `gh search issues`, `gh search prs`, `gh search repos`, `gh api search/code`, `gh api repos/.../issues/<n>`, `gh api repos/.../issues/<n>/comments`, `gh api repos/.../pulls/<n>`, `gh api orgs/.../repos`, `gh api repos/.../git/trees/<branch>?recursive=1` |
| Raw source | `curl https://raw.githubusercontent.com/...` for `RadioLib` and `MeshCore` files |
| Local PDFs | `pdftotext -layout` on the datasheets and app notes already vendored in `docs/` of this repo (§4) |

**The MeshCore firmware repository is `meshcore-dev/MeshCore`, not `ripplebiz/MeshCore`.**

`ripplebiz` is the founder's personal handle; the project was transferred to a
`meshcore-dev` organisation. Confirmed by querying the old path and reading the
canonical name back from the API:

```
$ gh api repos/ripplebiz/MeshCore --jq '.full_name'
meshcore-dev/MeshCore
```

`ripplebiz` still appears as a reviewer in the threads (§2, PR #2739), consistent
with the transfer. Repository facts read from the API on 2026-10-07:
description `"A new lightweight, hybrid routing mesh protocol for packet radios"`,
created `2025-01-19`, MIT, 3816 stars, 1426 forks, `pushed_at` `2026-10-07T07:41:54Z`.

**There is a `meshcore-dev` organisation.** All non-fork repos in it
(`gh api orgs/meshcore-dev/repos?per_page=100`):

```
meshcore-dev/MeshCore          (firmware + protocol; fork=false)
meshcore-dev/meshcore-cli      meshcore-dev/meshcore.js
meshcore-dev/flasher.meshcore.io   meshcore-dev/meshcore-ha
meshcore-dev/meshcore_py       meshcore-dev/nRF52-Flash-Format
meshcore-dev/map.meshcore.io   meshcore-dev/blog.meshcore.io
meshcore-dev/config.meshcore.io
meshcore-dev/Adafruit_nRF52_Arduino  (fork=true — a vendored dependency)
```

**Firmware lives only in `meshcore-dev/MeshCore`.** The other org repos are CLI
tooling, JS/Python bindings, a flasher web app, a Home Assistant integration, a
map, a config UI, a blog, and one vendored Arduino fork. There is no second
firmware repository in the org.

Repositories searched, and why:

| Repo | Searched for | Why |
|---|---|---|
| `meshcore-dev/MeshCore` | issues + PRs + code, terms in §2/§3 | the project the operator named; where LR2021 support and the drift thread live |
| `jgromes/RadioLib` | issues + PRs + raw `LR2021` sources | MeshCore depends on RadioLib; the LR2021 driver and the oscillator-config API live here, not in MeshCore |
| `meshtastic/firmware` | issues + PRs, TCXO/XTAL/drift terms | the cross-reference the task asked for (§6) — a *different* project |
| Global `gh search issues` / `gh search prs` | `LR2021`, `LoRa2021`, `LR2021IML` | to catch forks/variants hosting firmware that the in-repo search would miss |

Wide global issue search for `LR2021` returned 50+ hits across
`Xinyuan-LilyGO/*`, `sh123/esp32_loradv`, `lora-rs/lora-rs`, `Lora-net/usp`,
`jgromes/RadioLib`, `meshtastic/firmware`, `olliw42/mLRS`, `TheClams/lr2021*`,
`OffbandMesh/meshcore-firmware`, `liquidraver/ZephCore` (Zephyr port),
`mmmorks/meshcore-linux`, `openhop-dev/openhop_core`, and others. Only the
MeshCore-hosted and RadioLib-hosted threads are load-bearing for this analysis;
the others are noted where they corroborate, and are not treated as MeshCore work.

---

## 2. The LR2021 PRs and issues

### 2.1 The state of LR2021 support in MeshCore — it LANDED

LR2021 support is **merged and shipping** in MeshCore. The vehicle was a set of
merged PRs by other contributors in August–September 2026, not the original
request. Verified via `gh api repos/meshcore-dev/MeshCore/pulls/<n>`:

| # | Title | State | Merged | Created | Merged at | Author |
|---|---|---|---|---|---|---|
| **3115** | Add support for Meshnology W12 and LR2021 Wrapper | closed | **true** | 2026-08-05 | 2026-08-05 | `@oltaco` |
| **3112** | Add support for Seeed SenseCAP MeshTracker X1 (LR2021) | closed | **true** | 2026-08-04 | 2026-08-06 | `@Hacuchino-hash` |
| **3146** | LR2021: add PREAMBLE_DETECTED bit and IRQ timeout logic | closed | **true** | 2026-08-09 | 2026-08-10 | `@oltaco` |
| **3218** | Fix LR2021 occasionally stopping reception after a TX power change | closed | **true** | 2026-08-15 | 2026-08-17 | `@fkallay1` |
| **3379** | fix: LR2021 to use correct macro for IRQ_DETECTED in startReceive() | closed | **true** | 2026-09-08 | 2026-09-08 | `@oltaco` |

This matches the `dev`-branch file listing, which contains the shared helpers
(`gh api repos/meshcore-dev/MeshCore/git/trees/dev?recursive=1`):

```
src/helpers/radiolib/CustomLR2021.h
src/helpers/radiolib/CustomLR2021Wrapper.h
```

So: **"MeshCore has LR2021 support" is a true statement**, delivered by #3115 /
#3112 / #3146 / #3218 / #3379.

### 2.2 The proposals that did NOT land

These are **open** and must not be described as support that exists:

| # | Title | State | Created | Author | Note |
|---|---|---|---|---|---|
| **2740** | [Feature request] NiceRF LoRa2021 (LR2021 Gen 4) variant support | **open** | 2026-06-10 | `@c03rad0r` (our operator's account) | the originating request; the *variant* is still a proposal |
| **2739** | feat: Add NiceRF LoRa2021 (LR2021 Gen 4) variant support | **open** | 2026-06-10 | `@c03rad0r` | the paired PR; rebased and slimmed, still unmerged |
| **2944** | Kit lr2021 | **open** | 2026-07-13 | `@lilmoham` | |
| **3074** | Add Lierda AM36 Pico (L-LRMAM36-FANN4-PK02) variant — ESP32-S3 + Semtech LR2021 | **open** | 2026-07-30 | `@omegaconjecture` | |
| **3512** | LR2021 continuous mode race condition / packet corruption | **open** | 2026-09-27 | `@carlhodder` | a live defect, not support |
| **3261** | Fix LR11x0 and LR2021 packet loss when a stale SPI reply is read as the length | **open** | 2026-08-20 | `@fkallay1` | a live defect |
| **3502** | LR1121: Allow for use of SX128x compatible bandwidths | **open** | 2026-09-25 | `@dkmr27` | LR1121, a *different* chip |
| **2841** | Performance research: RadioLib per-packet overhead caps FLRC throughput at ~80 kbps on ESP32-C3 | **closed** | 2026-06-25 | `@c03rad0r` | research, closed |
| **3349** | Wrong constant for LR2021 startReceive + question? | **closed** | 2026-09-03 | `@carlhodder` | closed; superseded by merged #3379 |
| **861** | Support for LR1121 | **open** | 2025-09-29 | `@enimatek-nl` | LR1121, a *different* chip |
| **2678** | [Feature request] LilyGo T-Watch S3 + T3S3 (LR1121 / SX1280) board support + a 2.4 GHz LoRa frequency plan | **open** | 2026-06-03 | `@GrayHatGuy` | 2.4 GHz frequency plan still open |

### 2.3 Verbatim quotes — the LR2021 threads

**Issue #2740** (open), https://github.com/meshcore-dev/MeshCore/issues/2740 —
opened by our operator's account. Body, on the *silicon's clock source*:

> Crystal oscillator, not TCXO

and on the LC-oscillator NTC:

> Key differences from SX1262:
> - IRQ on DIO9 → `irqDioNum = 9` + `setDioFunction(9)`
> - `setRxBoostedGainMode(uint8_t 0-7)` vs `bool`
> - No DIO2-as-RF-switch (NiceRF module handles RF switching internally)
> - Crystal oscillator, not TCXO

The first substantive reply, `@carlhodder`, 2026-06-14, is the one that raises
temperature drift on this hardware:

> 2) Potential clock issues
> Do we want to block some configurations from repeater builds? e.g. urban areas using the 62.5KHz BW may start to get into trouble with outdoor units at temperature extremes without either a TCXO, or the NTC temp compensation enabled (which the base niceRF module does not populate, I removed the shield to check).

`@fkallay1`, 2026-09-02, on the two NiceRF parts and their clocks:

> Worth mentioning that NiceRF sell two different parts here, and it matters for comparing notes: the plain LoRa2021 that @c03rad0r describes, 19.72 by 15 mm, and the LoRa2021F33-2G4 I have, which carries an external PA and goes to about 30 dBm.

> On the temperature point you raised in June: mine, the PA version, is specified with an industrial TCXO at 0.5 ppm, which is presumably why I have not run into the drift you were worried about for outdoor units. If the plain module is on a plain crystal, that difference is worth knowing for anyone choosing between the two.

`@carlhodder`, 2026-09-03, resolving which part has what:

> The NiceRF F33 (1W) modules use a TCXO so they're good.
>
> The Waveshare Core2021 places the NTC, so I run that with temp compensation enabled. The manufacturer confirmed 100K but not the beta coefficient, so I've assumed the most common for an 0402/100K/1% of 4250K but should test.
>
> The base NiceRF LoRa2021 does not place the NTC, so it's gathering dust on my desk lol.

Our own project's comment on that same issue, `@felixfelix-bot`, 2026-09-04:

> **Use case worth a docs note:** we are preparing high-altitude-balloon (~30 km) mapping flights. Companion role with repeat disabled and `advert_interval = 0` makes a HAB node polite by default — no phantom base station, no ghost direct routes on landing. …

> Also +1 on the temperature point: the base module crystal at stratosphere temps is one more reason our balloon payload stays RX-only (TX drifts, RX tolerates).

**That last line is our own prior claim and §5 shows it is only half right.** It is
correct that TX-vs-RX asymmetry exists (the transmitter's error directly shifts
the carrier the receiver must acquire), but "RX tolerates" is false in the
absolute: the receiver's own reference error consumes the *same* tolerance
budget, because the FLRC figure is a maximum error **between** Tx and Rx. See §5.4.

**PR #2739** (open), https://github.com/meshcore-dev/MeshCore/pull/2739 — the
hardware description states the oscillator explicitly:

> - Crystal oscillator (XTAL), not TCXO — `tcxoVoltage = 0`

`@ripplebiz` (project founder, reviewing), 2026-06-23:

> Looks good. Just a small suggestion: I'd probably move the IDF Hal to /src/helpers/radiolib, as it's related only to RadioLib and could potentially be re-used by other variants

`@dkmr27`, 2026-07-09, on a *different* module with a TCXO — the ask that turned
into the TCXO-config work:

> my module is different, Ebyte E80-900M2212S and it has a TCXO. It would be nice if you can include provision in the wrapper to set a TCXO voltage if it's defined by the variant.
>
> Also tested 2.4Ghz which is working but has the same SX128x compatibility issues (LDRO) as does the LR1121.

`@fkallay1`, 2026-08-20, correcting our PR's claim that the module's front-end DIOs
need no programming, and diagnosing our `-707`:

> **The front-end DIOs do need programming.** The description says "No DIO2-as-RF-switch (NiceRF handles internally)". They are internal in the sense that they are not brought out to the MCU, but they are LR2021 DIOs wired to the front-end on the module PCB, and the chip has to be told to drive them — `setRfSwitchTable()` writes that mode mask into the chip, it does not touch MCU GPIOs.

> **The TCXO is very likely the cause of your -707.** … We configure 3.3 V (matching `LR20XX_SYSTEM_TCXO_CTRL_3_3V` in NiceRF's demo), and `begin()` succeeds with it … And -706/-707 is exactly what a wrong TCXO configuration returns, which is why the LR2021 support already in `dev` retries `begin()` with 0.0 V on those two codes.

The retry `@fkallay1` describes is in `dev` now — verified in
`src/helpers/radiolib/CustomLR2021.h`:

```c
  #ifdef LR2021_TCXO_VOLTAGE
      float tcxo = LR2021_TCXO_VOLTAGE;
  #else
      float tcxo = 1.6f;
...
      int status = begin(LORA_FREQ, LORA_BW, LORA_SF, cr, RADIOLIB_LR2021_LORA_SYNC_WORD_PRIVATE, LORA_TX_POWER, 16, tcxo);
      // if radio init fails with -707/-706, try again with tcxo voltage set to 0.0f
```

Our operator's reply, 2026-09-04, declaiming the rebase and being explicit that
the *variant* is for the crystal-only module:

> On his TCXO note: this variant targets the plain crystal-only module, so tcxoVoltage=0 is correct here; our -707 was the Arduino SPI driver (the ESP-IDF path fixed RX with TCXO settings unchanged)

### 2.4 Searches that returned nothing

Stated plainly, because an empty result is a finding:

- `gh search prs "LR2021IML"` and `gh search issues "LR2021IML"` → **empty** (no
  results at all). Whatever "LR2021IML" names, it does not appear as an
  issue/PR term on GitHub.
- `gh search prs "LoRa2021 OR LR2021IML"` (global) → **empty**. The `LR2021`
  searches in §2.1/§2.2 already cover the `LoRa2021` hits (the NiceRF module
  name), which is why this compound query adds nothing.
- `gh api search/code q="xtrim repo:meshcore-dev/MeshCore"` → `total_count=0`.
  Likewise `setXoscCpTrim`, `SetTempCompCfg`, `tempcomp` → all `total_count=0`
  (see §3.4 — this is the load-bearing negative result).
- `gh search issues "AFC" --repo meshcore-dev/MeshCore` → **empty**. No AFC
  discussion in MeshCore.
- `gh search issues "frequency drift" --repo meshcore-dev/MeshCore` → **empty**.
- `gh search issues "temperature drift" --repo meshcore-dev/MeshCore` → **empty**.
- `gh search issues "temperature compensation" --repo meshtastic/firmware` →
  **no results**.
- `gh search issues "frequency drift" --repo meshtastic/firmware` → one hit,
  `#4723` (`T114 can't send messages longer than 47 chars`), title-only
  coincidence, **not** about oscillator drift.

The drift discussion is therefore **not** found by the words "drift" or
"temperature drift". It is found by `crystal`, `TCXO`, and `frequency error` — the
three terms that all point at **#3365**. That is the next section.

---

## 3. The temperature-drift discussion — found, quoted, and its actual mechanism

### 3.1 The thread

**Issue #3365, "W12 frequency error"** — open, 2026-09-06, `@yo2ldk`,
https://github.com/meshcore-dev/MeshCore/issues/3365 (11 comments at time of
reading). This is the thread the operator half-remembers. It is *about* frequency
error on LR2021 hardware, and it contains the temperature-compensation remark.

Opening post, verbatim:

> Hi,
>
> I received my W12 companion, flashed with MC an,d not work.. after some tests, I put SDR receiver and the W12 frequency is down with 24KHz that 869.618, so i change it on 896.642 and all is ok. they use XO on this excellent device with LR2021 ??? so bad.. :(
>
> my question is fi you can add in FW something to adjust freq ?
> like (LR2021 support that):
>
> `#define W12_XOSC_TRIM_A ...`
> `#define W12_XOSC_TRIM_B ...`

Corroboration from other operators (same thread):

> `@lbibass` 2026-09-08: I had to bump the frequency by about 25kHz for it to operate properly, to 910.55 kHz.

> `@na7q` 2026-09-13: I had to set mine to 910.544 to put it spot on for 910.525. **I'm not seeing any real drift either with usage or minimal temp fluctuations.**

> `@Chris611` 2026-09-26: I have the same issue with a Waveshare Core2021 HF board. It also doesn't have a TCXO. Verified on SDR the frequency is slightly off so had to bump the TX frequency by +20khz.

**Note the ppm values.** 24 kHz at 869.618 MHz is **27.6 ppm**; 25 kHz at
910.525 MHz is **27.5 ppm**. That is a large, *fixed* offset — well outside the
±10 ppm the bare NiceRF module datasheet claims (§4.3) — and `@na7q` reports it
does **not** move with temperature in normal use. That distinction (fixed offset
vs temperature-driven drift) is the whole crux of this section.

### 3.2 The maintainer's position

`@recrof` (MeshCore maintainer), 2026-09-13, verbatim:

> W12 does not use TCXO, this is not software but hardware issue. **we do not plan adding any frequency compenstation at this time**

That is a clear, dated upstream statement: **MeshCore does not implement
frequency compensation.** It is still true on 2026-10-07 — see §3.4.

### 3.3 The ACTUAL mechanism that was proposed and tested

Four distinct mechanisms appear in #3365. Naming them precisely, because the
task asks for the mechanism rather than the vibe:

**(a) A static, build-time XOSC foot-capacitance trim.** `@Chris611` 2026-09-26:

> I implemented osc_trim myself in the CustomLR2021 class. So now when adding `-D LR2021_XOSC_TRIM_A=3 -D LR2021_XOSC_TRIM_B=3` it seems accurate

`@Chris611` 2026-09-28 shows what it calls — RadioLib's public wrapper over the
chip's CP trim:

> so it just uses radiolib setXoscCpTrim for lr2021 (guess you're using the same principle?)
>
> ```
>     // Public wrapper for the protected LR2021::setXoscCpTrim().
>     // Adjusts the crystal oscillator load capacitance (CP trim).
>     // A/B are 6-bit values; increasing them generally pulls the
>     // oscillator frequency downward.
>     int16_t setXoscTrim(uint8_t a, uint8_t b, uint8_t startTime) {
>       return setXoscCpTrim(a, b, startTime);
>     }
> ```

with the call site placed *before* anything else uses the radio:

> ```
>       // Apply the crystal oscillator CP trim BEFORE anything else uses the
>       // radio, so the carrier cannot be transmitted on the untrimmed frequency.
>       // A=0/B=0 is the no-trim baseline; real values come from the
>       // PlatformIO build flags after SDR calibration.
> ```

**(b) A runtime CLI command, `set radio.xtrim <xta>[,<xtb>]`, in a maintainer-built
custom firmware.** `@recrof` 2026-09-27, releasing a fixed build into the thread:

> can you guys test: [meshnology_w12_drift_fix.zip](https://github.com/user-attachments/files/32701757/meshnology_w12_drift_fix.zip)
>
> to flash, go to https://flasher.meshcore.io -> Custom firmware option. **it has trim a/b set to 3.** if it doesn't move the frequency you can adjust it via companion CLI or repeater cli via new commands: `set radio.xtrim <xta>[,<xtb>]`
>
> please report if it works and keeps the frequency where it should be. also report if it works out of the box with default setting.

**(c) The temperature-compensation path — named, and explicitly NOT available.**
`@lbibass` 2026-09-27, in reply to the release above:

> An alternative option might be to enable the temperature compensation on the LR2021. **But radiolib doesn't support that yet. The w12 includes a thermistor to compensate for thermal drift.** I don't know about the Waveshare module though.

`@lbibass` again 2026-09-27, on why the static trim may not be the end of it:

> I should also do testing with putting the board in the fridge or freezer to simulate different temp conditions, to make sure that the board will still operate at the correct frequency. **I have a feeling that without enabling the temp compensation, it will still fluctuate with temps.**

**(d) Empirically, one trim value did not fit all boards.** `@lbibass` and
`@Chris611` converged on *different* values for the *same* module — 8,8 vs 3,3:

> `@lbibass` 2026-09-27: At the defaults of 3,3 it was transmitting too high. I tuned it to 8,8 and that was much better. … Now we wait and see if a value of 8,8 will work for other people, or if it's only good for my board.

> `@Chris611` 2026-09-28: I did some more testing and with 8,8 my receiving node still responds, but it seems slightly too low. 3,3 seems perfect for my boards.

`@recrof` closed the loop by pointing at his fork branch, 2026-09-29:

> here is my code: https://github.com/recrof/MeshCore/tree/lr2021-trim

### 3.4 The mechanism, named, and whether it landed

**Two mechanisms, one shipped-by-a-fork, one absent:**

1. **What actually exists in the community: a static, one-time, SDR-calibrated
   XOSC foot-capacitance trim.** It is a *fixed frequency-offset correction*, not
   a temperature compensation. It is set either as a build flag
   (`LR2021_XOSC_TRIM_A` / `LR2021_XOSC_TRIM_B`) or at runtime
   (`set radio.xtrim`). Underneath it is the silicon command `SetXoscCpTrim`.
   **The correction is not temperature-driven and contains no temperature term.**

2. **What was named but is unimplemented: chip-level NTC temperature
   compensation.** `@lbibass`'s remark is the direct answer to the operator's
   recollection. The mechanism exists *in the LR2021 silicon* (§4.1, commands
   `SetTempCompCfg` 0x0132 and `SetNtcParams` 0x0133) and needs an external NTC
   thermistor near the crystal. It is **not** implemented in RadioLib ("radiolib
   doesn't support that yet") and therefore **not** in MeshCore.

**It did not land upstream, and I can prove it, not merely infer it:**

```
gh api -X GET search/code -f q="xtrim repo:meshcore-dev/MeshCore"           -> total_count=0
gh api -X GET search/code -f q="setXoscCpTrim repo:meshcore-dev/MeshCore"   -> total_count=0
gh api -X GET search/code -f q="SetTempCompCfg repo:meshcore-dev/MeshCore"  -> total_count=0
gh api -X GET search/code -f q="tempcomp repo:meshcore-dev/MeshCore"        -> total_count=0
```

Zero occurrences of any of the four in the whole upstream repository. The trim
code lives only on `recrof/MeshCore@lr2021-trim` (branch confirmed to exist,
`gh api repos/recrof/MeshCore/branches/lr2021-trim` → sha
`790b08020356d168c4dc702e5f6f4f23f5b45962`), released as a custom-firmware zip
plus a CLI command, consistent with the maintainer's own 2026-09-13 "we do not
plan adding any frequency compenstation at this time".

**So the operator's recollection resolves as: yes, there was talk of compensating
for temperature drift — `@lbibass`'s NTC remark — but the mechanism that came out
of the thread is a static capacitor trim, and the temperature compensation
itself was explicitly deferred because RadioLib lacks it.**

---

## 4. What the LR2021 hardware actually offers

All of this is read from the Semtech primary documents already vendored in this
repo and extracted locally with `pdftotext -layout`. Nothing below is invented; the
figures and command names are copied from the files named in each heading.

Source files:
- `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
  (250 pp., `DS.LR20xx`, Rev. 2.2, dated `29/07/26` in the running footer) —
  referenced below as **DS 2.2**.
- `docs/lr2021-research/semtech-official/AN1200.101_LR2021_FLRC_Improvements.pdf`
  (16 pp., Rev. 1.0, June 2026) — **AN1200.101**.
- `docs/lr2021-research/semtech-official/AN1200.102_LR20xx_LoRaImprovements_Rev1.1.pdf`
  (37 pp., Version 1.1, June 2026) — **AN1200.102**.
- `docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf` (NiceRF bare module) —
  **NiceRF base**.
- `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` (NiceRF F33 PA module) —
  **NiceRF F33**.

### 4.1 Temperature compensation — yes, on-chip, with real command numbers

**DS 2.2 §1.9.2, "32 MHz Crystal"** (datasheet p. 33):

> The optional XTAL temperature compensation mechanism measures the XTAL temperature change and compensates on chip for the induced frequency shift. When the temperature compensation mechanism is used, the VTCXO pin can be used to power an external temperature sensor (R and NTC) monitoring the XTAL temperature. The NTC output is then fed into the chip via pin NTC and measured by an increase in ADC. The resulting temperature information is used by the chip to automatically compensate, to some extent, the frequency shift due to XTAL heating. This function is particularity useful when high power PA is desired on a small PCB footprint. Refer to AN1200.102 for further details.

**DS 2.2 §6.12, "Temperature Compensation"** (datasheet p. 132):

> The temperature compensation is useful to limit frequency drift during high power transmissions.

**DS 2.2 §6.12.1 `SetTempCompCfg`** (register description p. 133; command byte
sequence `0x01 0x32`):

> The SetTempCompCfg command configures the heating compensation block in Tx if an XTAL 32 MHz is used.
>
> `ntc` controls the NTC source
> - 1: Enables NTC
> - 0: Disables NTC
>
> `comp_mode` defines the compensation mode:
> - 0x0: Disabled
> - 0x1: Relative
> - 0x2: Absolute
> - 0x3: RFU
>
> If a TCXO was configured this command fails.
>
> If an NTC source is available, it is used to compensate the variation in temperature of the crystal, while the internal temperature measurement can always be used to compensate the frequency deviation due to chip self heating.

**DS 2.2 §6.12.2 `SetNtcParams`** (command `0x01 0x33`):

> The SetNtcParams command enters the NTC parameter to be used during heating compensation.
>
> `ntc_r_ratio`: Defines the ratio between the resistor bias value and the NTC resistor value at 25 °C, on 10 bits with 9 fractional bits (10,9).
> `ntc_beta`: NTC temperature in 2 Kelvin/lsb.
> `delay`: First order time delay coefficient.

The command table (`DS 2.2`, table of commands, p. ~107 region) lists them as:

```
SetXoscCpTrim          0x0131    xta(5:0)
                                 xtb(5:0)          Configures XOSC foot capacitor trim
SetTempCompCfg         0x0132    ntc               Configures the temperature compensation for Tx mode
SetNtcParams           0x0133    ntc_beta(11:0)    Configures the NTC parameters
```

**Three constraints on this feature, all from the datasheet text above:**
1. It requires an **external NTC thermistor and bias resistor populated next to
   the crystal** (DS 2.2 §1.9.2 and the pin table: pin 3 = `NTC`, "Negative
   Temperature Coefficient (NTC) resistor connection"; pin 6 = `VTCXO/VNTC`,
   "External TCXO supply voltage (REG_TCXO) / NTC supply").
2. **It fails if a TCXO is configured** ("If a TCXO was configured this command
   fails"). So it is mutually exclusive with the TCXO path.
3. It is aimed at **self-heating during high-power TX**, not at ambient
   stratospheric cold. The stated purpose is "to limit frequency drift during
   high power transmissions" and "the frequency shift due to XTAL heating".

### 4.2 A settable frequency-synthesis offset — yes: `SetXoscCpTrim`

**DS 2.2 §6.11.4 `SetXoscCpTrim`** (datasheet p. 131; command `0x01 0x31`):

> The SetXoscCpTrim command allows the developer to trim the built-in foot capacitance of the 32 MHz Xtal oscillator. These trims are only used when going to a mode where the XOSC is enabled. If a TCXO is configured, this command has no effect, as the trims are not applied.
>
> - `xta`: Trims the foot capacitor on XTA pin. **0 = 11.3 pF, max = 47 = 33.4 pF, 1 LSB = 0.47 pF.** See Table 6-67.
> - `xtb`: Trims the foot capacitor on XTB pin. 0 = 11.1 pF, max = 47 = 33.2 pF, 1 LSB = 0.47 pF. See Table 6-68.
> - `additional_start_time`: (optional) Adds an additional delay in us for XTAL starting (RC->XSOC mode) to allow better stabilization of XTAL. If not sent, the previous value is kept. Default = 0.

RadioLib exposes this publicly. Verified in
`raw.githubusercontent.com/jgromes/RadioLib/master/src/modules/LR2021/LR2021.h`:

```cpp
    int16_t setTcxoMode(uint8_t tune, uint32_t startTime);
    int16_t setXoscCpTrim(uint8_t xta, uint8_t xtb, uint8_t startTime);
```

and its implementation in `LR2021_cmds_chip_control.cpp`:

```cpp
int16_t LR2021::setXoscCpTrim(uint8_t xta, uint8_t xtb, uint8_t startTime) {
  ...
  return(this->SPIcommand(RADIOLIB_LR2021_CMD_SET_XOSC_CP_TRIM, true, buff, sizeof(buff)));
```

So the chip command **is** wrapped by RadioLib, which is why the community could
use it without patching RadioLib. What RadioLib does **not** wrap is the
temperature-compensation pair — confirmed by an empty `search/code` for
`SetTempCompCfg`, and by grepping the whole `LR2021` module: the only
temperature-related API is a *read*:

```cpp
    float getTemperature(uint8_t source, uint8_t bits = 13);   // LR2021.h
```

### 4.3 A temperature readout — yes, with caveats

**DS 2.2 Table 6-33, `GetTemp` Response** (p. 117):

> `Source` sets the temperature sensor source for temperature measurement.
> - 0x00: Built-in junction temperature Vbe
> - 0x01: Built-in junction temperature close to XOSC
> - **0x02: NTC**
> - 0x03: RFU
>
> `Format`: 0 = raw value; 1 = the chip returns the temperature in °C in 13 bits. Actual temperature = Temp/32
>
> Note: **If a TCXO is currently being used, this command fails if the NTC is used as source.**

Two caveats that matter and that I did **not** invent:
- RadioLib's source carries a warning about the read path. In
  `LR2021_cmds_chip_control.cpp` (line 169 area):
  > `// reading of temperature in degrees seems broken and the datasheet disagrees with reference implementation`
- `RadioLib` tracks a known gap for the sibling part:
  `jgromes/RadioLib#1863` (open, 2026-09-01, `@p-f-w`) —
  *"missing some functional implementations of getFrequencyError(), getTemperature() and getVoltage() for LR1121"*.

### 4.4 A frequency-error *readout* — **not found for LR2021**

I searched DS 2.2 for a command returning the measured carrier frequency error
(an FEI-style readout). The hits in the string "frequency error" are all
*specifications* ("Max freq error tolerated") in the RF performance tables, plus
one unrelated register note:

> automatic frequency limitation is performed during the PA selection: the frequency selection has to be performed according to the …

**No `GetFreqError`-style command is documented in DS 2.2 that I could find.**
`TODO(unverified)` in §7. Note the LR2021 measurement list in DS 2.2 does not
include an LO-offset readout, unlike some Semtech parts.

### 4.5 An AFC facility — **not found**

The string `AFC` has **zero** hits in DS 2.2, AN1200.101, and AN1200.102 as far
as my greps reached, and `gh search issues "AFC" --repo meshcore-dev/MeshCore`
returned **empty**. The LR2021's answer to frequency offset is the *wider
tolerance* plus the *static trim*, not a closed-loop automatic frequency
control. **Marked `TODO(unverified)`** — absence in the documents I could grep is
not proof of absence in the silicon, but I found no AFC in any primary source I
read.

### 4.6 The module-level oscillator specs (what our two parts actually carry)

**NiceRF base module** (`LoRa2021-Module-Datasheet-V1.3.pdf`):

> ```
> Frequency Error      @Crystal     10      ppm
>                      @TCXO        0.5     ppm
> ```
> Pin 13 `VTCXO` — O — "Can provide power for an external TCXO."

**NiceRF F33-2G4 module** (`LoRa2021F33-2G4-datasheet-v1.1.pdf`):

> - Industrial-grade TCXO Crystal Oscillator 0.5PPM
> ```
> Frequency Error                            0.5    ppm
> ```

**Reconcile that with §3.1.** The base module is *specified* at ±10 ppm on its
crystal, yet the MeshCore operators measured **~27 ppm** of fixed offset
(24 kHz @ 869.6 MHz, 25 kHz @ 910.5 MHz). The chip's trim range is
11.3 pF → 33.4 pF, ~0.47 pF/LSB, so a large fraction of that 27 ppm is almost
certainly **board-level foot-capacitance mismatch** — which is exactly what the
`SetXoscCpTrim` command corrects, and exactly why the community's fix worked. The
±10 ppm crystal spec is a *crystal* figure, not a *board* figure. This is an
inference from the numbers, and I flag the causal attribution as
`TODO(unverified)` in §7; the two numbers themselves are quotes.

---

## 5. FLRC vs LoRa frequency-offset tolerance, and what it costs us

### 5.1 The authoritative FLRC figures

**AN1200.101 §5.2, "Frequency Error Tolerance"** (pp. 8–9), verbatim:

> The FLRC modem automatically assigns the receive bandwidth necessary to accommodate the transmitted FLRC signal. However, it is also necessary to consider the frequency offset between the transmitter and receiver caused by reference oscillator frequency errors.
>
> The following table shows the permissible offset as a function of both data rate and payload length for 10% packet error rate. The dependency on payload length arises because during the transmission process the crystal is subject to instantaneous heating. However, this effect can be avoided by keeping the **total frequency error between Tx and Rx** less than the frequency limits below.

**Table 3 — Measured Typical Frequency Error Tolerance [kHz] of the FLRC Modem versus Data Rate for all Frequency Bands** (payload 10 B → 511 B):

| Payload | 2600 kbps | 2080 kbps | 1300 kbps | 1040 kbps | 650 kbps | 520 kbps | 325 kbps | 260 kbps |
|---|---|---|---|---|---|---|---|---|
| 10 B  | ±206 | ±235 | ±142 | ±121 | ±76 | ±59 | ±37 | ±30 |
| 31 B  | ±206 | ±226 | ±137 | ±117 | ±73 | ±57 | ±36 | ±29 |
| 100 B | ±206 | ±212 | ±128 | ±111 | ±69 | ±53 | ±34 | ±27 |
| 200 B | ±206 | ±205 | ±122 | ±107 | ±67 | ±51 | ±32 | ±26 |
| 300 B | ±206 | ±202 | ±118 | ±104 | ±66 | ±50 | ±32 | ±25 |
| 400 B | ±205 | ±201 | ±117 | ±104 | ±65 | ±50 | ±32 | ±25 |
| 511 B | ±206 | ±198 | ±119 | ±102 | ±64 | ±50 | ±31 | ±25 |

The same tolerance expressed in **ppm** is given separately for the two bands
(AN1200.101 Tables 4 and 5), and is the crucial part:

**Table 5 — 2.45 GHz Band PPM Typical Frequency Error Tolerance versus Data Rate:**

| Payload | 2600 | 2080 | 1300 | 1040 | 650 | 520 | 325 | 260 |
|---|---|---|---|---|---|---|---|---|
| 10 B  | ±84 | ±96 | ±58 | ±49 | **±31** | ±24 | ±15 | ±12 |
| 31 B  | ±84 | ±92 | ±56 | ±48 | **±30** | ±23 | ±15 | ±12 |
| 511 B | ±84 | ±81 | ±48 | ±42 | **±26** | ±20 | ±13 | ±10 |

**Table 4 — 868/915 MHz Band PPM Typical Frequency Error Tolerance versus Data Rate:**

| Payload | 2600 | 2080 | 1300 | 1040 | 650 | 520 | 325 | 260 |
|---|---|---|---|---|---|---|---|---|
| 31 B | ±225 | ±257 | ±155 | ±132 | ±83 | ±65 | ±41 | ±32 |
| 511 B | ±224 | ±219 | ±128 | ±113 | ±71 | ±54 | ±34 | ±28 |

**The datasheet's own FLRC frequency-error figures corroborate AN1200.101** — DS 2.2
table 3-13 (`FRF = 2.4 GHz`, `CR = 3/4`, packet size 31 bytes):

```
FLRC_1040_CR05_FERR    Max freq error tolerated   FRF = 2.4 GHz    +/-100   kHz
FLRC_650_CR05_FERR     Max freq error tolerated   FRF = 2.4 GHz    +/-70    kHz
FLRC_520_CR05_FERR     Max freq error tolerated   FRF = 2.4 GHz    +/-50    kHz
FLRC_325_CR05_FERR     Max freq error tolerated   FRF = 2.4 GHz    +/-30    kHz
FLRC_260_CR05_FERR     Max freq error tolerated   FRF = 2.4 GHz    +/-25    kHz
```

Do not confuse `CR05` with 0.5 kbps — the condition line reads "BRF = 650 kbps,
CR = 3/4, BWF = 600 kHz", i.e. `CR05` is the 0.5 (1/2) coding-rate variant of the
table and the operating conditions in the row are 650 kbps / CR 3/4.

### 5.2 The LoRa comparison

**DS 2.2, LoRa sub-GHz performance tables** (p. 62 region):

```
LORA_FERR_L1   LoRa Maximum tolerated frequency offset between transmitter and receiver     All bandwidths   -25   25   %BW
LORA_FERR_L2   ... for at most 3 dB degradation                                            All bandwidths   -33   33   %BW
LORA_FERR_L4   ... for at most 1.5 dB degradation.  SF12                                  -100   100   ppm
LORA_FERR_L5   ... for at most 1.5 dB degradation.  SF11                                  -200   200   ppm
LORA_FDRIFT1   LoRa frequency drift tolerance      LowDataRateOptimize = 0                     -   200   Hz/s
LORA_FDRIFT2   LoRa frequency drift tolerance      BWLORA = 125 kHz, SF12, LDRO = 1            -   100   Hz/s
```

**AN1200.102, Chapter 6**, explaining L1/L2:

> In previous LoRa® generations, frequency offset tolerance was limited to ±BW/4, corresponding to ±31.25 kHz for BW 125 kHz. Beyond this value, PER degrades rapidly … The LR20xx can be configured for a larger tolerance of ±BW/3, corresponding to ±41.7 kHz for BW 125 kHz.

and, on why it matters:

> The LR20xx extended frequency offset tolerance relaxes constraints on the 32 MHz crystal oscillator, enabling the use of lower-cost crystals.

**LoRa's tolerance is proportional to bandwidth; FLRC's tolerance is proportional
to data rate and is (per Table 3) essentially band-independent in absolute Hz.**
That asymmetry drives everything below.

### 5.3 The conversions

Reference frequencies: **433.05 MHz** (the low edge of our licence-exempt band,
`docs/adr/041-rf-frontend-licence-exempt.md`) and **2.4 GHz**.

Endpoint oscillator error (a single radio's own reference):

| Reference | at 433.05 MHz | at 2.4 GHz |
|---|---|---|
| crystal ±10 ppm (NiceRF base module spec) | ±4.33 kHz | ±24.0 kHz |
| crystal ±20 ppm | ±8.66 kHz | ±48.0 kHz |
| crystal ±25 ppm | ±10.83 kHz | ±60.0 kHz |
| crystal ±30 ppm | ±12.99 kHz | ±72.0 kHz |
| observed W12 offset, ~27 ppm | ±11.69 kHz | ±64.8 kHz |
| TCXO 0.5 ppm (NiceRF F33 spec) | ±0.217 kHz | ±1.20 kHz |

Worst-case **combined** Tx+Rx error (the quantity AN1200.101's tables bound):

| Link | combined ppm | at 433.05 MHz | at 2.4 GHz |
|---|---|---|---|
| two ±10 ppm crystals | 20.0 | ±8.66 kHz | ±48.0 kHz |
| two ±20 ppm crystals | 40.0 | ±17.32 kHz | ±96.0 kHz |
| two ±25 ppm crystals | 50.0 | ±21.65 kHz | ±120.0 kHz |
| two ±30 ppm crystals | 60.0 | ±25.98 kHz | ±144.0 kHz |
| ±20 ppm crystal vs 0.5 ppm TCXO | 20.5 | ±8.88 kHz | ±49.2 kHz |
| ±30 ppm crystal vs 0.5 ppm TCXO | 30.5 | ±13.21 kHz | ±73.2 kHz |
| two 0.5 ppm TCXOs | 1.0 | ±0.43 kHz | ±2.40 kHz |

FLRC tolerance converted to ppm at each band (from Table 3's absolute kHz, 650 and
520 kbps rows for the 511 B case):

| FLRC rate | tolerance | at 433.05 MHz | at 2.4 GHz |
|---|---|---|---|
| 2600 kbps | ±206 kHz | ±476 ppm | ±86 ppm |
| 1300 kbps | ±119 kHz | ±275 ppm | ±50 ppm |
| 1040 kbps | ±102 kHz | ±236 ppm | ±42 ppm |
| 650 kbps | ±64 kHz | ±148 ppm | **±27 ppm** |
| 520 kbps | ±50 kHz | ±115 ppm | **±21 ppm** |
| 325 kbps | ±31 kHz | ±72 ppm | ±13 ppm |
| 260 kbps | ±25 kHz | ±58 ppm | ±10 ppm |

LoRa tolerance in ppm at each band (`±25 %BW` standard / `±33 %BW` extended):

| LoRa BW | at 433.05 MHz (std / ext) | at 2.4 GHz (std / ext) |
|---|---|---|
| 125 kHz | ±72 / ±95 ppm | ±13 / ±17 ppm |
| 250 kHz | ±144 / ±191 ppm | ±26 / ±34 ppm |
| 500 kHz | ±289 / ±381 ppm | ±52 / ±69 ppm |
| 812 kHz | ±469 / ±619 ppm | ±85 / ±112 ppm |
| 1625 kHz | ±938 / ±1238 ppm | ±169 / ±223 ppm |

### 5.4 Plain answers to the question the recommendation hinges on

**Q: Is a plain ±20–30 ppm crystal inside or outside FLRC's tolerance?**

| Case | 433.05 MHz | 2.4 GHz |
|---|---|---|
| One ±20 ppm crystal → 2.4 GHz FLRC 650 kbps (±27 ppm) | inside (uses 14 % of ±148 ppm) | **borderline-outside** in a two-crystal link; inside a one-crystal link |
| Two ±20 ppm crystals → FLRC 650 kbps | **inside**, ±17.3 kHz of ±64 kHz (3.7× margin) | **outside**, ±96 kHz of ±64 kHz (0.67×) |
| Two ±30 ppm crystals → FLRC 650 kbps | **inside**, ±26.0 kHz of ±64 kHz (2.5× margin) | **outside**, ±144 kHz of ±64 kHz (0.44×) |
| Two ±30 ppm crystals → FLRC 2600 kbps | **inside**, ±26.0 kHz of ±206 kHz (7.9× margin) | **inside**, ±144 kHz of ±206 kHz (1.4× margin) |
| TCXO 0.5 ppm + crystal 20 ppm → any FLRC rate | comfortable at every rate | inside at ≥650 kbps; marginal at 520 kbps (1.16×); outside at ≤325 kbps |

**Q: Is a TCXO 0.5 ppm inside?** Yes, everywhere: ±1.2 kHz at 2.4 GHz against
FLRC 650 kbps' ±64 kHz is 53× margin, and even against FLRC 260 kbps' ±25 kHz it
is 21× margin.

**The headline, stated plainly:**

- At **433 MHz**, FLRC 650 kbps tolerates **±64–76 kHz = ±148–175 ppm**. Even two
  ±30 ppm crystals (±26 kHz) sit comfortably inside. **Our 433 MHz downlink is not
  drift-limited under FLRC.**
- At **2.4 GHz**, the *same* ±64–76 kHz absolute budget becomes only **±27–32 ppm**.
  Two plain crystals (±40 to ±60 ppm combined) are **outside**. A single crystal
  against a TCXO reference (~20.5 ppm) is inside at 650 kbps by ~1.5× and
  **outside at 325 and 260 kbps**.
- **FLRC's absolute tolerance is band-independent**, so as a *fraction* it is
  **≈5.5× looser at 433 MHz than at 2.4 GHz**. Low band is the drift-friendly
  band, which inverts the usual intuition.
- **"FLRC tolerates more drift than LoRa" is false as a blanket statement.** At
  2.4 GHz FLRC 650 kbps (±27–32 ppm) beats narrow LoRa BW125 (±13 ppm) but loses
  to LoRa BW812 (±85 ppm) and BW1625 (±169 ppm). Only FLRC at ≥1300 kbps beats
  LoRa BW125 at 2.4 GHz in ppm, and only FLRC ≥2080 kbps beats LoRa BW500. **The
  comparison depends entirely on which FLRC rate is set against which LoRa
  bandwidth.**
- **Lowering the FLRC rate makes the drift problem worse, not better.** Tolerance
  scales with rate: 2600 kbps → ±86 ppm at 2.4 GHz, 260 kbps → ±10 ppm. This is the
  opposite of the LoRa instinct, where wider BW (a costlier, faster setting) buys
  tolerance and a *slower* link is what you fall back to. For FLRC, the drift-robust
  setting is the **fast** one.

### 5.5 What would settle the residual uncertainty

No authoritative figure exists for the *board-level* temperature-driven drift of
our *specific* carrier board — only the crystal spec (±10 ppm claim), the
community's fixed offset observation (~27 ppm), and the silicon's tolerance. The
measurement that would settle it:

1. Put the bare LR2021 board in a climate chamber (or the repo's existing
   fridge/freezer + hot-plate method used elsewhere in the bench work) across
   **+20 °C to −56 °C** in steps, at fixed supply.
2. Transmit a CW carrier (or a known FLRC preamble) at a fixed set frequency.
3. Measure the carrier offset on an SDR or spectrum analyser at each step.
4. Fit offset vs temperature. The **slope** (Hz/°C, or ppm/°C) is the drift
   figure; the **intercept** is the fixed offset the CP trim removes.
5. Then run a 2.4 GHz FLRC 650 kbps link with the balloon radio as receiver at
   both temperature extremes and count PER against the ±64–76 kHz budget.

The MeshCore thread had *started* this (`@lbibass`: "I should also do testing with
putting the board in the fridge or freezer to simulate different temp
conditions") but never reported results — the thread went quiet after
2026-09-29. **No measurement of the temperature slope exists in the thread.**

---

## 6. What this means for our balloon, and what I recommend

### 6.1 Verification of the design context (checked against the repo, not taken on faith)

| Context claim | Verified? | Evidence |
|---|---|---|
| Radios: SX1280 + bare LR2021 (2.4 GHz) + LoRa2021F33-2G4 (433 MHz PA) | yes | `docs/DUAL-VARIANT-DESIGN.md:16,72-78` — V2 = NiceRF LoRa2021F33-2G4, +33 dBm @433, +30 dBm @868/2.4G |
| 433 MHz is the downlink, **balloon→ground**, ≤10 mW ERP licence-exempt | yes | `docs/adr/041-rf-frontend-licence-exempt.md:33-34` — "licence-exempt at 433.05–434.79 MHz at ≤10 mW ERP … binds the balloon's transmitter — the 433 MHz downlink" |
| 2.4 GHz is the uplink, **ground→balloon**, and is the binding direction | yes | `docs/adr/041-…:56,92` — "D1 — WHICH direction binds: the 2.4 GHz uplink, not the 433 downlink" |
| The 433 downlink link budget uses **SF12 / BW125** (LoRa, not FLRC) | yes | `docs/adr/041-…:59,65` — tool invocation `--sf 12 --bw 125`, "tool LoRa table, SF12/BW125 = -137 dBm" |
| The F33 has a **built-in 0.5 ppm TCXO**; the bare/v1 variant supports an **external TCXO** | yes | `docs/DUAL-VARIANT-DESIGN.md:78` — "TCXO \| External (VTCXO pin) \| **Built-in 0.5ppm**"; `docs/F33-MODULE-PLAN.md:18,44`; NiceRF base datasheet pin 13 `VTCXO` + `@TCXO 0.5 ppm` row |
| Our FLRC profiles are BR2600 / BR1300 / BR650, CR 3/4 | yes | `docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md:24,38-39,72` — "BR650, BR1300 and **BR2600**", "`cr = CR_3_4`" |
| 100 µW night anchor, 33 J supercap, no battery | per task context; not re-derived here | task brief; out of scope for this analysis |
| Ambient −50 to −56 °C in flight | per task context | task brief |
| A separate worker owns the oscillator-heater question | per task context | I did not touch it; nothing here is written to their file |

One thing the context did **not** say explicitly and that matters: the balloon's
**2.4 GHz receiver is the bare LR2021 on a crystal**, while its **433 MHz
transmitter is the F33 on a 0.5 ppm TCXO**. Per §5.3 those two roles land on
opposite ends of the drift budget.

### 6.2 The recommendation

**R1 — Do not treat "FLRC is drift-tolerant" as settled. The 2.4 GHz direction is
where it hurts, and it is our binding direction.** ADR-041 already names the
2.4 GHz uplink as the binding link. Under FLRC at 650/520 kbps, a bare-crystal
2.4 GHz receiver is outside the tolerance budget whenever the ground side is also
crystal-referenced, and only ~1.5× inside even against a perfect TCXO ground
transmitter. This is a real constraint on the current design, and it is not
visible in a link-budget table — the margin is an *offset* budget, not a dB
budget, and the two do not trade against each other.

**R2 — Prefer a 2.4 GHz receiver referenced to a TCXO.** Concretely, either use
the **F33's built-in 0.5 ppm TCXO** to cover 2.4 GHz RX as well as 433 TX, or fit
the **external TCXO on the bare module's `VTCXO` pin** — the option the variant
already anticipates (`docs/DUAL-VARIANT-DESIGN.md:78`, "External (VTCXO pin)"). At
±1.2 kHz vs a ±25–76 kHz budget this removes the drift question entirely at
2.4 GHz. It is the only option here that is a **guarantee rather than a
calibration**, and it costs no firmware work. *(The choice of TCXO part and its
power budget belong to the concurrent oscillator worker; R2 states the interface,
not their answer.)*

**R3 — If a bare crystal is kept at 2.4 GHz, run the fastest FLRC rate the link
closes on, not the slowest.** Tolerance scales with rate (§5.4). FLRC 2600 kbps
buys ±86 ppm at 2.4 GHz — ~3× the 650 kbps budget — which brings even two ±30 ppm
crystals inside (±144 kHz of ±206 kHz). This is a **zero-BOM, firmware-only**
mitigation. It also composes with our measured FLRC throughput work
(`docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md`: BR2600 is the configured air
rate and 1484.9 kbps was measured sustained). The catch is that the higher rate
needs more link margin, so this trades an offset budget for a dB budget — decide
it with ADR-041's tool, not by intuition.

**R4 — The "degrade rather than lose" ladder must not fall to a lower FLRC rate.**
This is the single most actionable finding in this document. Our governing
principle is "degrade rather than lose the balloon", and the natural reading of
"degrade" is *slow down the link*. For FLRC that is backwards: 650 → 520 → 325 kbps
takes the 2.4 GHz offset budget from ±27 ppm to ±21 to ±13 ppm, i.e. the degraded
rung is *more* likely to fail on drift. The correct degrade path, if the 2.4 GHz
offset budget is the thing at risk, is one of:
  - switch the 2.4 GHz reference to the TCXO (R2), or
  - fall back to the **433 MHz band**, where FLRC's ppm budget is ≈5.5× looser and
    the balloon transmits with the F33's 0.5 ppm TCXO, or
  - accept a shorter 2.4 GHz window (fewer, longer attempts) rather than a slower
    modulation.
  **Write this into whichever degrade-ladder document owns it** — but not here;
  this document orders nothing.

**R5 — Use a one-time SDR-calibrated `SetXoscCpTrim` as a fallback, not as the
plan.** The community's mechanism (§3.3) is real, cheap, and available today
through RadioLib's `setXoscCpTrim`. But note its three limits honestly: (i) it
corrects a **fixed** offset, with **no temperature term**; (ii) the community found
that **one trim value did not fit all boards** (8,8 vs 3,3 on the same module),
so it is a per-board calibration that must be done at integration, not a firmware
constant we can trust blind; (iii) it does nothing for the temperature-driven
component, which is exactly the component a −50 °C balloon cares about. So: worth
having as a calibration step, wrong to rely on as the drift answer.

**R6 — The LR2021's on-chip temperature compensation is attractive but **not**
available to us today, and probably not on our module as shipped.** Three
independent blockers, each sourced:
  1. **RadioLib does not implement it.** `SetTempCompCfg` / `SetNtcParams` are
     absent from RadioLib (code search and source grep, §3.4) and from MeshCore
     entirely. Using it means writing driver code.
  2. **It needs a populated NTC thermistor next to the crystal.** The bare NiceRF
     module "does not place the NTC" (community teardown, `@carlhodder`,
     §2.3). So on our bare LR2021 the hardware for the feature is likely absent.
  3. **It is mutually exclusive with a TCXO** ("If a TCXO was configured this
     command fails", §4.1) — so it is an alternative to R2, not a complement.
  Combined with the fact that its stated purpose is TX **self-heating**, not
  ambient cold, R6's conclusion is: **do not design around it.** If we ever want
  NTC temperature compensation we would need a module that populates the NTC
  (the Waveshare Core2021 does, per `@carlhodder`) plus custom driver work — a
  larger change than R2/R3 for a weaker guarantee.

**R7 — The 433 MHz FLRC path needs no drift mitigation.** At 433 MHz, FLRC 650 kbps
tolerates ±148–175 ppm; the balloon transmits from an F33 with a 0.5 ppm TCXO
(±0.2 kHz), and the ground station's reference can be anything reasonable. This
direction has ~100× margin on the frequency-offset axis. If FLRC is wanted
anywhere on this payload specifically *because* crystal drift is a worry, the
433 MHz downlink is where the physics is friendliest — and it is also where ADR-041
gives us 24.3 dB of link margin at SF12/BW125, so there is room to move the 433
link to FLRC without touching the 10 mW ERP cap.

**R8 — One correction to our own prior claim.** Our comment on MeshCore #2740 says
"the base module crystal at stratosphere temps is one more reason our balloon
payload stays RX-only (TX drifts, RX tolerates)". The **TX/RX asymmetry is real,
but "RX tolerates" is not**. The FLRC figure is a maximum error *between* Tx and
Rx: the receiver's own reference error consumes the same budget as the
transmitter's. A crystal-referenced receiver is not spared the problem — it is
half of it. Correcting this in our records matters because the sentence currently
reads as a reason to stop worrying about the 2.4 GHz RX, when §5.4 says the 2.4 GHz
RX is precisely where the budget is tightest.

### 6.3 Summary table

| Link | Balloon role | Reference | Best-case FLRC band budget | Verdict |
|---|---|---|---|---|
| 433.05–434.79 MHz downlink | **TX** (F33, 0.5 ppm TCXO) | ±1.2 kHz at worst | ±64–76 kHz (650 kbps) | ~50–60× margin. **No mitigation needed.** |
| 2.4 GHz uplink | **RX** (bare LR2021, crystal) | ±48 kHz (20 ppm) to ±72 kHz (30 ppm) | ±64–76 kHz (650 kbps); ±206 kHz (2600 kbps) | **Outside** vs a second crystal; ~1.5× inside vs a TCXO floor; **inside** at 2600 kbps. **Needs R2 or R3.** |

---

## 7. `TODO(unverified)` and empty searches

**`TODO(unverified)` — things I could not confirm and did NOT invent:**

1. **No `GetFreqError`-style carrier-offset readout for the LR2021.** I found no
   such command in DS 2.2. Absence in documents I could grep is not proof of
   absence in silicon. §4.4.
2. **No AFC facility in the LR2021.** Zero `AFC` hits in the three Semtech
   documents I extracted, and an empty MeshCore `AFC` search. Same caveat. §4.5.
3. **The causal attribution of the community's ~27 ppm offset to foot-capacitance
   mismatch** is my inference from the trim range and the ±10 ppm crystal spec. The
   27 ppm measurement and the ±10 ppm spec are quotes; the explanation is not
   proven. §4.6.
4. **Board-level temperature coefficient** (ppm/°C) of our actual 2.4 GHz carrier
   board: **unknown, unmeasured.** The MeshCore thread never reported the
   fridge/freezer result. §5.5 gives the measurement that would settle it.
5. **Whether `SetTempCompCfg` partially compensates ambient cold** (as opposed to
   TX self-heating) is not established by any document I read; the datasheet's own
   framing is self-heating. §4.1.
6. **Whether the SX1280's FLRC tolerance matches the LR2021's.** Every FLRC figure
   in §5 is from LR2021/LR20xx documents. I did **not** find an equivalent
   frequency-error-tolerance table for the SX1280, and I did not assume one.
   **Do not apply §5's numbers to the SX1280 without its own source.** The
   SX1280's tolerance is `TODO(unverified)`.
7. **Whether the F33-2G4's 2.4 GHz RX path can be used simultaneously with the
   433 MHz TX role** in our architecture (one module, two bands, TDM) — an
   architectural question ADR-041/ADR-034 touch but that this analysis did not
   resolve. R2 depends on the answer.
8. **The exact EU SRD regulatory row for the 2.4 GHz EIRP cap** — already flagged
   `TODO(unverified)` in `docs/adr/041-…:140`; not re-investigated here.

**Searches that came up EMPTY (reported as empty, not filled in):**

| Search | Result |
|---|---|
| `gh search issues "LR2021IML"` (global) | empty — no results |
| `gh search prs "LR2021IML"` / `"LoRa2021 OR LR2021IML"` (global) | empty |
| `gh search issues "frequency drift" --repo meshcore-dev/MeshCore` | empty |
| `gh search issues "temperature drift" --repo meshcore-dev/MeshCore` | empty |
| `gh search issues "AFC" --repo meshcore-dev/MeshCore` | empty |
| `gh search prs "xtrim"` / `"XOSC"` / `"crystal trim"` / `"temperature compensation"` --repo meshcore-dev/MeshCore` | empty |
| `gh api search/code q="xtrim\|setXoscCpTrim\|SetTempCompCfg\|tempcomp repo:meshcore-dev/MeshCore"` | `total_count=0` for all four |
| `gh search issues "temperature compensation" --repo meshtastic/firmware` | no results |
| `gh search issues "frequency drift" --repo meshtastic/firmware` | 1 irrelevant hit (#4723, message-length bug) |
| Semtech DS 2.2 / AN1200.101 / AN1200.102 — string `AFC` | zero hits in extracted text |
| Semtech DS 2.2 — FLRC drift-*rate* spec (an FLRC analogue of `LORA_FDRIFT1/2`) | **none found**; only LoRa has Hz/s drift-rate rows |

**On the Meshtastic cross-reference (task item 6), stated as the empty result it
is:** Meshtastic has **no** `temperature compensation` issue or PR. Its relevant
oscillator history is *configuration* handling, not compensation — the closest and
most instructive artefact is `meshtastic/firmware` PR **#11995** (open,
2026-09-27, `@NomDeTom`), *"SX126x: follow RadioLib's silent XTAL fallback and log
the chip's state after init"*, which documents that RadioLib `SX126x::begin()`
silently retries on the crystal when the TCXO fails and **zeroes its own
`tcxoVoltage`**, so a log can report a TCXO the board does not have. Its own body
states: *"LR11x0 and LR2021 are unaffected: RadioLib has no such retry for them,
so `begin()` fails and Meshtastic's own fallback logs the result correctly."* So
Meshtastic offers **no concrete compensation mechanism that MeshCore lacks** — it
has the same "declare your oscillator, log which one you got" posture. The
`-707/-706 → tcxo=0.0f` retry already in MeshCore's `CustomLR2021.h` (§2.3) is
MeshCore's own equivalent. **Different project; no mechanism to adopt.** Also note
`meshtastic/firmware#11995` is *open*, not merged.

**Provenance note.** Every issue/PR number, state, date, author, and URL above was
returned by a live `gh` call on 2026-10-07; every quoted string is copied from the
fetched body/comment or the named PDF. Comment counts and states are as of the
read time and will drift.
