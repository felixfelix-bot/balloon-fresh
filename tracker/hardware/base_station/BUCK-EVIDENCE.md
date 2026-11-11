# Buck candidate — proposed D14 deviation, not measured startup

Supersedes only the unresolved buck paragraph of BOOT-CORE-EVIDENCE.md for this **candidate**. Original board/netlist and freeze are unchanged. Existing boot-core/RP2040 work retained. No push, merge, tag or physical boot claim.

## Selection and source conflict

Propose **TPS54202DDCR**, TI DDC six-lead SOT-23, `Package_TO_SOT_SMD:SOT-23-6`. This is NOT a footprint-compatible TPS62162 substitution and NOT transcription-green: D14 row 14 freezes TPS62162, whose 17 V recommended limit cannot cover 18 V normal input. Approval of this replacement and relocating protection upstream remain required. Keep 9–18 V input and >=0.5 A continuous/1 A peak targets; TPS54202 has 4.5–28 V recommended input and 2 A silicon capability (not a measured board rating). Simple synchronous six-pin part, no external catch diode or compensation IC.

TI exact-orderable part page was fetched successfully: https://www.ti.com/product/TPS54202/part-details/TPS54202DDCR . Live distributor/JLC stock and price **not confirmed**.

Pin oracle from TI Table 4-1: 1 GND, 2 SW, 3 VIN, 4 FB, 5 EN, 6 BOOT. EN5 deliberately open: section 6.3.5 explicitly permits floating EN because of its internal pullup current source. Never tie EN to 18 V (5.5 V recommended/7 V absolute limit), nor to its own output. Internal soft-start is 5ms typical. Bootstrap 100nF X7R 16V connects BOOT6 to SW2, NOT ground. No PG exists: remove obsolete REG_PG and leave RP2040 pad7 unused; firmware must not assume a working power-good input.

Installed KiCad SOT-23-6 loaded with pcbnew: left 1/2/3 at y=-0.95/0/+0.95mm, right 6/5/4, matching TI top view. Six physical pads; no exposed pad. No PCB placement has been done.

## Passive design and numerical bounds

- L1 **Bourns SRP6060FA-150M**, 15uH +/-20%, 43mOhm max DCR; datasheet Isat 5.8A **typical** at 30% inductance drop, Irms 4.5A **typical** at 20C rise. `Inductor_SMD:L_Bourns_SRP6060FA` loaded successfully: two pads at x=+/-2.025mm, 1.55x5.6mm. TI Table 7-2 starts at 15uH for 5V. Actual heat/DC-bias must be qualified; typical saturation is not a guaranteed minimum.
- At 18V, 5V out, Lmin=12uH, fmin=390kHz times 0.94 jitter: delta-I=0.821A, peak at 1A load=1.411A, RMS=1.028A. This is below the 2.5A minimum high-side limit. At 0.5A, RMS=0.553A. Fault-limit maximums 3.9A high side/4.3A low side informed the inductor selection, but do not prove short-circuit survivability.
- Feedback 100k/13.5k, both 0.1%: nominal 5.0108V. Using TI Vref 0.581–0.611V and opposing resistor tolerances gives **4.8761–5.1460V**, inside VGA 4.75–5.25V before ripple/transients. Slight change from TI example 13.3k improves high-end headroom. 75pF C0G 50V feed-forward across upper resistor follows Table 7-2 starting point; loop testing required.
- Input 22uF X7R 50V 1210, acceptance **effective >=10uF** at 18V, including tolerance/DC bias/temp/aging, plus 100nF X7R 50V. Required input ripple-current capability >=0.5A for 1A output worst duty. Input bulk/cable damping external as needed; ceramic voltage rating alone does not establish capacitance or hot-plug safety.
- Output two 22uF X7R 25V 1206, each **effective >=15uF** at 5V (total >=30uF), same derating conditions. Exact ceramic MPN/curves are still procurement gates, not claimed selected/verified. TI Eq14 estimates crossover <=26.3kHz at 30uF without feed-forward. Ideal capacitive ripple at worst delta-I about 9.3mVpp. Eq11 two-cycle estimate for 0.5A load step is 91mV at minimum jittered frequency, before ESR; it does NOT prove staying inside VGA bounds. Specify ESR/ripple heating and measure complete transient envelope.
- Thermal: typical MOSFET conduction at 1A is about 0.10–0.13W depending duty, excluding switching/gate/control losses. Datasheet JEDEC thetaJA=118.6C/W vs EVM=57.2C/W demonstrates layout dependence. No ambient/current qualification or guarantee from that estimate. Preserve >=0.5A continuous/1A peak design target, validate at worst input/load/ambient.

## Input protection contract (deliberately external)

J_PWR is the **already protected** 9–18V boundary. Remove the old unselected series D_REV and shunt D_TVS placeholders rather than claiming them functional; notably the old shunt diode pin convention was not verified. Candidate connects J_PWR directly to VIN bypass and U_REG VIN3.

Upstream source must provide correct polarity, fuse/current limiting, reverse-polarity blocking, and surge/hot-plug suppression so IC VIN never exceeds **28V including ringing**, with no negative excursion. 30V is absolute maximum, not a clamp target. Require regulated 9–18V under normal load; long cable or raw battery/mast source without validated protection is NOT approved. No onboard lightning/surge/reverse protection has been designed. Select/validate upstream clamp against waveform, cable energy and tolerances; a TVS standoff label alone is insufficient. This boundary is a proposal, not silently claiming the freeze's protection is implemented.

## Primary datasheets downloaded

Ignored local copies under `output/readiness/buck/sources/`:
- TI **SLVSD26C**, revised February 2026, Table 4-1; §§5.1/5.3/5.5, 6.3.5/6.3.9/6.3.10, 7.2/Table 7-2: https://www.ti.com/lit/ds/symlink/tps54202.pdf
  SHA256 `297fae8754121e09dd3290b748865282a7f594800d742e86f92dfcfc54b4deea`.
- Bourns **SRP6060FA Series**, electrical table and recommended land pattern: https://www.bourns.com/docs/product-datasheets/srp6060fa.pdf
  SHA256 `28ee89c71c693436d0f33e33d36df97c3704511c09249bd0cc4373f23e026740`.

## Executed verification and reproduction

`test_pin_startup` first failed on the old TPS62162/package, passed after capture fix. `test_filter_ratings` then failed on old 2.2uH and passed after passive correction. Four copied-map mutations reject input-from-output, EN-from-output, bootstrap-to-ground and feedback-bottom-to-output. These test connectivity/requirements, not analog startup.

From `tracker/hardware/base_station`:
```sh
python3 -m unittest test_buck test_boot_core test_rp2040_pinout test_verifier_portability -v
python3 test_spec_transcription.py
mkdir -p output/readiness/buck/candidate
cp gen_base_station_netlist.py spec.json test_netlist_implements_spec.py output/readiness/buck/candidate/
python3 output/readiness/buck/candidate/gen_base_station_netlist.py
python3 output/readiness/buck/candidate/test_netlist_implements_spec.py
sha256sum output/readiness/buck/candidate/base_station_v1.net
```

**13 unittest tests PASS**, including all previous 10; legacy structural invariants **25/25**; retained freeze checks **34/34 with explicit PROPOSED DEVIATION warning**, NOT replacement approval. Deterministic candidate generated twice: **62 components, 43 nets**; SHA256 **`fa497e433f12cc17d51712b7b38e5fde45eb8fbba95249703810d2918d4d280a`**. `git diff --check` clean. Original base_station_v1.net/PCB were not generated over.

## Still blocked

No measured startup, brownout, load steps, loop gain, reverse/backfeed, short-circuit, thermal, conducted/radiated RF noise, or physical MCU boot. Need exact capacitor purchasing/derating, upstream protection approval, schematic ERC, placement, layout hot-loop/quiet-feedback review and DRC. RF ADL5240/AD8318 captures and LNA limiter remain placeholders, two BPF/tee/masthead measurement gates remain, and separated net names do not establish fault isolation. USB still lacks connector/ESD/BOOTSEL interface and VBUS/power policy; 27-ohm series resistors alone are not a complete USB implementation. Boot2/flash, crystal startup and SWD remain untested on hardware.
