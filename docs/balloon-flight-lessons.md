# Balloon Flight Lessons

Lessons learned from 80+ documented pico-balloon flights by 6+ independent practitioners, plus community resources. Data collected May 2026.

---

## Data Sources

| Practitioner | Flights | Period | URL |
|-------------|---------|--------|-----|
| John Ruthroff (KC9IKB) | 37 | May 2023 - Mar 2025 | https://www.theastroimager.com/picoballoning/pico-ballooning/ |
| Bryan Klofas (KF6ZEO) / SF-HAB | 5+ launches documented | Sep-Dec 2021 | https://www.klofas.com/blog/tag/picoballoon.html |
| KI4MCW | 31 | Nov 2024 - Jan 2026 | https://sites.google.com/site/ki4mcw/Home/pico-balloonery |
| K9YO | Beginner guide + flights | 2022-2023 | https://sites.google.com/view/picoballoonsbyk9yo/beginners-guide |
| David Schneider (IEEE Spectrum) | 3 | Dec 2025 | https://spectrum.ieee.org/explore-stratosphere-diy-pico-balloon |
| Doug & Mark (Picoballoons.net / Traquito) | Multiple | 2021+ | https://www.picoballoons.net/ |
| Pico Balloon mailing list | Community wisdom | 2019-present | https://groups.io/g/picoballoon |
| SF-HAB group | Multiple | 2021+ | https://www.sfhab.org/ (referenced in Klofas blog and Pacificon 2021 presentation) |

---

## Success Factor #1: Gas Purity (Critical)

**This is the single most important factor for long-duration flights.**

### Evidence

**Ruthroff's gas comparison (37 flights, all with Yokohama balloons):**
- Source: https://www.theastroimager.com/picoballoning/pico-ballooning/
- Party-store helium (80% He / 20% air): **9 flights, 0 circumnavigations, 0% success rate**
  - JR16: 7 days (first party He flight)
  - JR18: 6 hours
  - JR19: 11 hours
  - JR20: 4 days
  - JR21: 5 days
  - JR22: 7 hours
  - JR23: 9 days
  - JR24: 13 hours
  - JR25: 8 hours
- Ultra-pure helium (99.999%, industrial): **3 flights, 2 circumnavigations, 67% success rate**
  - JR28: 175 days, 11 laps
  - JR29: **528 days, 32 laps** (longest duration)
  - JR30: 2 days 22h (TPU clamp failure, not gas)
- Hydrogen: **~9 flights, 5 circumnavigations, 55% success rate**
  - JR09: 60 days, 5 laps
  - JR10: 232 days, 11 laps
  - JR14: 507 days, 27 laps
  - JR32: 216 days (heat sealed and clamped)
  - JR35: 124 days, 8 laps

**Ruthroff's helium purity test:**
- Source: https://www.theastroimager.com/picoballoning/pico-ballooning/ (section "What's up with party store helium?")
- Method: Inflate identical balloons to same diameter, hang weights until hover
- Spoozer brand (party): 4.15g hover
- Party City brand (party): 7.25g hover
- 99.999% industrial helium: 8.42g hover
- Party-store provides only 49-86% of the lift of pure helium

**US regulatory requirement:**
- Source: Ruthroff's site, "NEW INFORMATION October 2024"
- In the US, balloon helium must contain ≥20% oxygen (to prevent inhalation asphyxiation)
- This means US party-store helium is legally capped at ~80% purity maximum

**KI4MCW's experience with "Party Factory helium from Germany":**
- Source: https://sites.google.com/site/ki4mcw/Home/pico-balloonery
- Used in Flights #14-31
- Flight #14: 15 days (best result with this gas)
- Flight #22: "tank was questionable - seemed to fill the balloon more than normal, as though there was air in the balloon along with the helium" → only reached 20K ft, burst after 2 days
- Mixed results overall, no full circumnavigations

**K9YO's guidance:**
- Source: https://sites.google.com/view/picoballoonsbyk9yo/beginners-guide
- "The best gas to use is hydrogen. It is somewhat lighter and does not diffuse through the balloon as quickly."
- "Helium from party balloons has been used in the past, but it is typically only 80% helium."

### Lesson

**Never use party-store helium for long-duration flights.** Use hydrogen (preferred, cheaper, more lift) or industrial-grade 99.999% helium from a gas supplier.

---

## Success Factor #2: Balloon Quality

### Evidence

**Yokohama vs all others:**
- Source: Ruthroff (https://www.theastroimager.com/picoballoning/pico-ballooning/)
- Yokohama + H2: multiple 100+ day flights
- Source: Klofas (https://www.klofas.com/blog/tag/picoballoon.html)
- Chinese clear party balloons (36") + H2: ~12 days max
- Source: KI4MCW (https://sites.google.com/site/ki4mcw/Home/pico-balloonery)
- PartyWoo 50" + He: 15 days max, most flights 4-8 days
- Cymylar 60" + He: 7 days max, most flights 2-4 days

**KI4MCW's frustration with PartyWoo:**
- Source: Flight #24 notes
- "I'm frustrated by the continued failures with the PartyWoo balloons."
- Switched to Cymylar 60", similar problems

**SBS-13 from SF-HAB:**
- Source: Klofas blog, Pacificon 2021 presentation reference
- "David launched two SBS-13 picoballoons from the Central Valley in winter 2021, one of which went 2.5 times around the world."

### Lesson

Yokohama balloons are 10-50x more durable than party alternatives. The $15/balloon cost is easily justified by the dramatically longer flight duration.

---

## Success Factor #3: Balloon Preparation

### Stretching

**Ruthroff's stretching procedure:**
- Source: https://www.theastroimager.com/picoballooning/pico-ballooning/ (Section 4A)
- Inflate with air to 100-116" circumference using 12V air pump (~2 hours)
- Hold at stretch for hours to days (Ruthroff likes 105")
- Deflate completely (switch pump to IN port, ~2 hours)
- Refill with lifting gas (~0.07 m³ for launch — looks underinflated, this is normal)
- Why: "The larger the volume of the balloon, the higher it will float. This helps reduce the risk of the balloon running into foul weather."

**Ruthroff's critical mistake (JR01-JR06):**
- Source: Flight JR03 notes
- Confused 0.31 millibars with 0.31 PSI when stretching → overpressured balloons → weakened them → multiple early failures
- 0.31 mbar = 0.0045 PSI (way too low)
- 0.31 PSI = 21.4 mbar (correct)
- "LESSON LEARNED: I don't worry about internal balloon pressure anymore. Inflate it to 100" circumference, stretch it as much as you please/dare (I like 105") and hold it at that diameter for a few hours or a few days."

**Dry vs wet stretching:**
- Source: Ruthroff JR09 notes
- "LESSON LEARNED: Manometer or high-humidity stretching not required."
- Dry stretching to 101.5-105" works fine

**KI4MCW's pre-stretching:**
- Source: Flight #14 notes
- "Pre-stretched PartyWoo 50-inch balloon" → 15 days
- Source: Flight #25 notes
- Filled Cymylar days ahead, topped off twice, sealed top and bottom → 7 days 18h

### Lesson

Stretch balloons to 100-116" circumference with air before flight. Hold for hours. Dry stretching is sufficient.

---

## Success Factor #4: Sealing Method

### Evidence

**Ruthroff's sealing experiments:**
- Source: https://www.theastroimager.com/picoballoning/pico-ballooning/ (Section on sealing)
- Heat seal + Kapton/Kynar tape: **Proven reliable** — used on all successful flights
- Epoxy: "didn't work for me"
- Superglue: "didn't work for me"
- Epoxy with UV light: "didn't work for me"
- E6000 adhesive: "didn't work for me"
- Plastic model glue: failed
- Heat sealer setting: "6" on standard food-bag sealer, ~5 seconds per seal
- Apply 2-3 heat seals on nozzle + Kapton tape over the seal

**Ruthroff's TPU clamp experiment (JR30, JR31):**
- Source: Flight JR30 notes
- 3D-printed TPU clamp with bolts, no heat seal, no tape, no glue
- JR30: Failed after 2 days 22h
- JR31: Failed after 5 days 15h (also mixed party + pure helium)
- "The TPU clamp concept has been abandoned due to lack of practicality/need."

**KI4MCW's sealing experiments:**
- Source: Flight #13 notes
- "Hopefully Santa will bring me a heat sealer for Christmas" (after balloon leak failures)
- Source: Flight #14 notes
- "Heat-sealed neck" → 15 days (best result)
- Source: Flight #31 notes
- Tried gluing neck closed (added ~2g of glue) → 4 days 14h (worse than heat seal alone)
- Source: Flight #25 notes
- Sealed both top and bottom of Cymylar with Kapton tape → 7 days 18h

**Self-sealing valves:**
- Source: Ruthroff, balloon preparation section
- Yokohama self-sealing valves are unreliable at altitude
- "The self-sealing nozzle may not self-seal" after deflation/refill cycle
- Yokohama now sells "no nozzle" versions specifically for pico-balloonists

### Lesson

**Use heat seal + Kapton/Kynar tape. Nothing else works reliably.** Do NOT rely on self-sealing valves or adhesives.

---

## Success Factor #5: Free Lift Amount

### Evidence

**Ruthroff's free lift data:**
- Source: Individual flight notes
- 5g free lift: JR09 (60 days), JR14 (507 days), JR27 (2 days)
- 6g free lift: JR10 (232 days), JR12 (failed), JR13 (5 days)
- 7g free lift: JR29 (528 days), JR35 (124 days)
- 8g free lift: JR25 (8 hours, party He)
- Optimal range: **5-7g free lift**

**KI4MCW's free lift experiments:**
- Source: Flight #14 notes
- 5.7g free lift (miscalculated): "barely got off the ground" → 15 days (best flight)
- Source: Flight #18 notes
- 4.5g free lift: "barely got off the ground", hit a tree 150 yards downrange
- Source: Flight #19 notes
- 4.5g free lift: antenna wrapped around light pole, flight time ~10 seconds
- Source: Flight #20 notes
- 4.5g free lift: clean vertical climb in zero wind → 8 days 18h
- Source: Flight #22 notes
- 4.5g free lift: "barely got off the ground", topped at 20K ft → 2 days

**KI4MCW's observation about low free lift:**
- Source: Flight #18-19 notes
- "Using low amounts of free lift are causing take-off trajectories to be so low that I worry my launch site may no longer be suitable."

**Klofas/SF-HAB:**
- Source: https://www.klofas.com/blog/tag/picoballoon.html (Launch 12-16)
- "around 6 grams of free lift" for 36" Chinese party balloons

### Neck Lift Measurement Method

**Ruthroff's method:**
- Source: Section "How much lifting gas to add"
- "I take a plastic bag, put weights in it, and weigh it until it weighs [payload + free lift] grams"
- "I then use a piece of tape to tape the bag/weight assembly to the balloon and add lifting gas until the balloon hovers"
- "It pays to be finicky about this process. Too little lift and your balloon ends up in a place where there be monsters. Too much lifting gas and you risk bursting the balloon."

### Lesson

**5-7g free lift is optimal.** Below 5g risks obstacles on departure. Above 8g risks balloon burst. Measure with calibrated weights.

---

## Success Factor #6: Payload Weight

### Evidence

**Ruthroff's payloads:**
- Source: Individual flight notes
- 14g: JR01-JR06, JR09 (60 days)
- 16.4g: JR28 (175 days)
- 16.7g: JR14 (507 days)
- 17g: JR05
- 17.8-18.4g: JR27, JR29 (528 days)
- 20.35g: JR16 (7 days, party He)
- 21-22g: JR32 (216 days)
- 28.7g: JR35 (124 days)

**KI4MCW's payloads:**
- Source: Flight notes
- 15.1g: Flight #23 (lightest, 8 days 6h)
- 19.2-22.9g: Most flights (4-15 days)
- 28.9g: Flight #14 (heaviest, 15 days)

**Ruthroff's weight budget breakdown:**
- Source: Section 3B
- "The total package, balloon, payload, power supply...normally can't weight more than 3 ounces [85g]"
- "Since nearly half that weight is taken up by the balloon itself, we're down to lifting a useful payload/power supply combination of 8/10th's of an ounce [23g]"

**IEEE Spectrum (David Schneider):**
- Source: https://spectrum.ieee.org/explore-stratosphere-diy-pico-balloon
- "The payload of a pico balloon is so light (between 12 to 30 grams) that you can use a large Mylar party balloon filled with helium to lift it."

### Our Payload Weights

| Variant | Weight | Fits Yokohama? |
|---------|--------|---------------|
| Minimal tracker | 9g | Yes (well within 20-25g limit) |
| Mesh V1 | 14g | Yes (proven by Ruthroff's 14g flights) |
| Mesh V2 | 22g | Yes (proven by KI4MCW's 22g flights) |

### Lesson

Our payload weights are well within the proven range. No weight reduction needed for Yokohama balloons.

---

## Success Factor #7: Solar Cell Handling

### Evidence

**KI4MCW's experience:**
- Source: Flight #11 notes
- "Holy cow are these solar cells fragile!"
- "I certainly ended up needing a hundred cells, because I broke them frequently"
- Traquito Solar System "leaves the cells vulnerable to breakage"

**KI4MCW's solutions:**
- Source: Flight #11A notes
- Styrofoam plate chassis: "provides a protective bumper around the fragile solar cells"
- "The cells are mounted loosely (by the wire leads), which helps cushion any contact"
- Source: Flight #13 notes
- "Flexible polymer solar cells do not shatter when you drop them, which is a HUGE improvement"
- "But it does take four of them at this size in parallel to produce the current needed"
- "At $10 USD per cell, that makes for a fairly expensive tracker"

**Ruthroff's approach:**
- Source: Section 2D
- 7-10 polycrystalline cells, 0.5V each, wired in series
- Cells "float" on airframe — only ends attached with epoxy, middle free to contract
- "I don't do this because of the possibility that the temperature change between the assembly area and the cold at 40,000 feet may crack a cell"

**Ruthroff on solder joint reliability:**
- Source: JR09 notes
- "After soldering the solar cell assembly, I applied epoxy over the solder joints in the hope that this would prevent a joint breaking at the cold temperatures found at altitude."

### Lesson

Solar cells are extremely fragile. Use protective chassis, epoxy over solder joints, and allow cells to thermally expand/contract. Consider flexible polymer cells if budget allows.

---

## Success Factor #8: Antenna Strain Relief

### Evidence

**Ruthroff's Kevlar strain relief:**
- Source: Section "Attaching transmitter to the balloon"
- Uses 30 gauge magnet wire for antenna (~0.33mm diameter)
- Kevlar kite line runs parallel to upper antenna element, slightly shorter
- "The Kevlar line is slightly shorter than the upper antenna element, so it will take the strain of lifting the payload instead of the antenna wire, which may break if stressed given its thinness"
- Wire wrapped + epoxied to Kevlar every ~45 inches
- "LESSON LEARNED: I don't attach the antenna to the kite line except at the ends as there is no real need to do so."

**KI4MCW's antenna wire issues:**
- Source: Flight #12 notes
- "38-gauge magnet wire for the lower side of the HF antenna broke in two places during launch"
- "I'm re-thinking the use of this incredibly fragile wire"
- Source: Flight #13 notes
- Switched to 30-gauge wire-wrap wire for lower antenna: "much stronger than the ultra-skinny 38-gauge magnet wire"
- Source: Flight #23 notes
- Used 38-gauge for both upper and lower with fishing line support → 8 days 6h

### Lesson

Antenna wire will break under load without strain relief. Use Kevlar kite line or braided fishing line as the structural element.

---

## Success Factor #9: Launch Conditions

### Evidence

**Ruthroff on weather:**
- Source: Section 3A
- "PB's and their payloads are very fragile. They don't react well to moisture"
- "At that altitude [40,000 feet] the air is very dry so moisture condensing or freezing on the balloon or payload isn't much of a concern"
- "Summer thunderstorms can reach up to 60,000 feet"

**Klofas on clouds/fog:**
- Source: https://www.klofas.com/blog/tag/picoballoon.html (Launch 9 notes)
- "Our major lesson learned from the previous launch failure was there should be no fog or clouds at the launch site. Fog or clouds can condense on the balloon surface or tracker electronics, weighing down the picoballoon so it falls out of the sky."

**KI4MCW on wind:**
- Source: Flight #11 notes
- "On launch day there was entirely too much wind. I tried to time the release between small gusts, but the balloons blew horizontally anyway. The craft nose-dived into the sidewalk, breaking four solar cells and ending the flight."
- Source: Flight #17 notes
- "Launch day was windier than expected. I had to hold the payload by the 3D-printed frame for a minute or so, waiting for a lull in the wind before launching."
- Source: Flight #19 notes
- "This flight ended before it began when the antenna wrapped itself around a light pole in the parking lot upon launch."

**Ruthroff on night launches:**
- Source: Section 4A
- "Another advantage of a night release has to do with the state that the world is in. Quite innocent and harmless activities these days are often misinterpreted by the ignorant, paranoid and fearful"
- Practical concern: won't know if balloon survived until next morning

**KI4MCW on dew:**
- Source: Flight #28 notes
- "Slow takeoff, no wind, but lots of dew"

### Lesson

**Launch only in: zero wind, no clouds/fog, no precipitation, no dew.** Wait for calm conditions. Avoid winter solstice (low sun = weak solar power).

---

## Failure Mode Analysis

### Most Common Failure: Night Loss

**Ruthroff:**
- Source: Flight table
- "Went down at night" entries: JR01, JR12
- "Losses at night are the most disappointing since determining the cause of the loss is nothing more than an guess"
- JR14: possibly brought down by thunderstorm (507 days)
- JR32: "Another unexplainable night loss"

### Balloon Failure vs Electronics Failure

**Ruthroff's diagnosed failures:**
- Balloon failure: JR01, JR02, JR03, JR06, JR08, JR09, JR12, JR21, JR22, JR24, JR25, JR30, JR31, JR34, JR37
- Electronics failure (suspected): JR04, JR26, JR27, JR36
- Unknown: JR05, JR07, JR13, JR16, JR20, JR23, JR32, JR35
- Thunderstorm: JR14, JR33

**KI4MCW's diagnosed failures:**
- Source: Flight notes
- Balloon leak: Most flights (#11A, #13, #15, #16, #17 implied, #22, #24, #27, #29, #30)
- Burst: #17 (Siberia), #23 (weather encounter), #25 (thunderstorm)
- Launch failure (wind/obstacles): #11, #19
- Never transmitted: #12, #26
- GPS spoofing: #20 (over Belarus)
- Nearly circumnavigated: #14 (fell short ~2000 miles), #20 (fell short at Aleutians)

**Klofas/SF-HAB:**
- Source: https://www.klofas.com/blog/tag/picoballoon.html (Launches 12-16)
- 5 launches in 2 weeks, only 1 survived first night
- Launch 10: "Halfway Around the World!" then went down in Uzbekistan

### Lesson

Balloon failure (leak or burst) is the #1 cause of flight loss, not electronics. Invest in quality balloons and proper sealing.

---

## Altitude Targets

### Evidence

**Ruthroff's altitudes:**
- Source: Flight table
- 38,000-45,000 ft (11.6-13.7 km) for most successful flights
- JR14 reached 51,000 ft (15.5 km)
- Ideal: above weather but in jetstream

**Klofas on altitude:**
- Source: https://www.klofas.com/blog/tag/picoballoon.html (Launch 10 notes)
- "Our ideal altitude is above 11,100 meters [36,400 ft], which is higher than most bad weather but still in the jetstream"
- "HYSPLIT predictions... at 9,000 meters, showed the balloon spinning in circles around the western United States. If we could reach 10,000 meters, the balloon had a good chance of reaching the Atlantic Ocean"

**KI4MCW's altitude issues:**
- Source: Flight #22 notes
- Topped at ~20K ft due to contaminated helium → burst after 2 days
- Source: Flight #14 notes
- Consistent 30,000+ ft → 15 days, nearly circumnavigated

### Lesson

Target **36,000-45,000 ft (11-13.7 km)** for optimal jetstream riding while staying above most weather. Below 30,000 ft = increased weather risk and slower winds.

---

## Additional Lessons

### Batteries Don't Work at Altitude

**Ruthroff:**
- Source: Section 2D
- "Batteries don't like the cold and will have very low output for a very short time so for practical purposes this isn't a viable option"

### FCC/Regulatory

**Ruthroff:**
- Source: FAQ section
- FAA has no problem with pico balloons (too light and small)
- FCC requires amateur radio license for transmissions
- No clear international agreement on airspace altitude limits

**K9YO:**
- Source: https://sites.google.com/view/picoballoonsbyk9yo/beginners-guide
- "The government has laws that govern the flying of balloons. They stipulate weight and size limits. Pico balloons are far below these limits."
- "Jet engines are designed and tested to ingest birds which are much larger and denser"

### Descent Rate After Balloon Failure

**Ruthroff:**
- Source: FAQ section
- "Roughly four to eight hours" to reach the ground
- "When the balloon pops, it acts like a small parachute"
- "~1 mile per hour" descent rate given light payload weight

### Cost per Flight

**Ruthroff:**
- Source: FAQ section
- "About $25 to $75 in materials"

**K9YO:**
- Source: https://sites.google.com/view/picoballoonsbyk9yo/beginners-guide
- "About $140 (Jan 2023) without gas" for first flight including tracker
- "For your second balloon you will only need to buy a tracker, balloon and gas, so the cost is significantly less"

**IEEE Spectrum:**
- Source: https://spectrum.ieee.org/explore-stratosphere-diy-pico-balloon
- Jetpack boards: $39 (5x from JLCPCB including shipping/tariffs)
- Pi Pico: $4
- Balloon: $10 (2-pack)
- Helium: $10 (supermarket)
- Solar modules: $14 (2x $7)
- Total: ~$77 for first flight, ~$28 for subsequent flights

### Si5351 Harmonic Emissions

**IEEE Spectrum (David Schneider):**
- Source: https://spectrum.ieee.org/explore-stratosphere-diy-pico-balloon
- Si5351A outputs square wave, not sinusoid → spurious emissions at odd harmonics
- 3rd harmonic at 42 MHz was only -25 dB below 14 MHz fundamental
- FCC requires -43 dBc for spurious emissions
- Solution: antenna traps (4 loops of #32 magnet wire + 220pF capacitor)
- Added only 0.3g weight
- Note: Our LR2021 design uses proper filtered RF output, so this is not an issue for us

### GPS Spoofing

**KI4MCW:**
- Source: Flight #20 notes
- "Experiencing a GPS spoof over Belarus"
- Known issue in certain geopolitical regions

### Platform Rotation

**Ruthroff:**
- Source: JR37 notes
- Attempted to measure platform rotation using angled JetPack
- Results inconclusive due to low time resolution (1 measurement per 10 minutes)
- "Eventually someone will figure out how to do this with an IMU or compass module"

### OpenTJP Firmware

**KI4MCW:**
- Source: Flight #24 notes
- Switched from stock Traquito firmware to OpenTJP (open source)
- "The OpenTJP firmware seems to be up to the task of running the Traquito, and since it is open source, is more amenable to tinkering"
- Community is migrating to this firmware

---

## Community Resources

| Resource | URL | Description |
|----------|-----|-------------|
| Pico Balloon mailing list | https://groups.io/g/picoballoon | 1,152 members, active discussion since 2019 |
| Traquito | https://traquito.github.io/ (implied from picoballoons.net) | Tracker hardware, firmware, community maps |
| Picoballoons.net | https://www.picoballoons.net/ | Migrating to Traquito, $14 WSPR tracker |
| WSPRnet | https://wsprnet.org/ | Global WSPR spot database, balloon tracking |
| WSPR.rocks | https://wspr.rocks/ | Real-time WSPR tracking with maps |
| HYSPLIT | https://ready.arl.noaa.gov/HYSPLIT.php | NOAA flight trajectory prediction tool |
| SF-HAB | https://www.sfhab.org/ | Bay Area high-altitude ballooning, how-tos |
| LU7AA WSPR tracking | http://lu7aa.org/ | WSPR balloon tracking with altitude data |

### Tracker Vendors

| Tracker | Vendor URL | Cost |
|---------|-----------|------|
| Traquito JetPack | https://traquito.github.io/ (implied) | ~$14 (PCB) + $4 (Pi Pico) |
| U4B (QRP Labs) | https://www.qrp-labs.com/ | ~$30 |
| ZachTek WSPR TX Pico | https://www.zachtek.com/ | ~$65 |

### Where to Buy Balloons

| Balloon | Source | URL |
|---------|--------|-----|
| Yokohama | US resellers / direct | Contact via https://www.yokohamaballoon.com/ |
| SBS-13 | Scientific Balloon Solutions | https://www.scientificballoonsolutions.com/products/ |
| Chinese clear 36" | AliExpress | Search "36 inch clear foil balloon" |
| PartyWoo 50" | Amazon | Search "PartyWoo 50 inch balloon" |
| Cymylar 60" | Amazon/AliExpress | Search "cymylar 60 inch balloon" |

### Where to Get Gas

**K9YO's guidance:**
- Source: https://sites.google.com/view/picoballoonsbyk9yo/beginners-guide
- "The best gas to use is hydrogen. It is commonly used in industrial welding and a tank of it can be more easily obtained."
- "Potentially, you could contact a commercial welding company to fill your balloon."
- "The supply of helium is limited, and it is difficult to get from gas supply stores."

**Ruthroff's gas sources:**
- Source: Flight JR26 notes
- Industrial gas supplier for ultra-pure helium (99.999%)
- Argon regulator fits helium tanks (same thread)
- Hydrogen from industrial supplier

---

## Summary: What We Must Do for Long-Duration Flights

1. **Use hydrogen** from industrial gas supplier (or 99.999% helium if H2 unavailable)
2. **Use Yokohama balloons** ($15 each, 10-pack)
3. **Stretch to 100-116" circumference** with air, hold hours to days
4. **Heat seal + Kapton tape** the nozzle (nothing else works)
5. **5-7g free lift** (measure with calibrated weights)
6. **Payload ≤ 22g** (our Mesh V1 at 14g is fine)
7. **Kevlar strain relief** on antenna wire
8. **Launch in zero wind, no clouds, no precipitation**
9. **Protect solar cells** during handling (most fragile component)
10. **Target 36,000-45,000 ft** altitude
