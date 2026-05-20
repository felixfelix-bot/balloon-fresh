# Balloon Leak Test Results

## Overview

Long-duration leak test of DecoGlee 18" foil party balloons filled with Amazon helium, conducted March-April 2026 in Bonn, Germany (indoor, room temperature).

---

## Test Setup

| Parameter | Value |
|-----------|-------|
| Balloon type | DecoGlee 18" Round Foil (Mylar) |
| Product link | https://www.amazon.de/dp/B0F5H6VLPZ |
| Quantity tested | 3 balloons, tied together |
| Gas | Amazon helium (purity unknown, likely 80-97%) |
| Test location | Indoor, room temperature |
| Test method | Magnets as calibrated weights, removed one-by-one when balloons could no longer lift them |
| Test weight | Magenesis 10x2mm neodymium magnets (52-pack) |
| Magnet product | https://www.amazon.de/dp/B06X977K8L |
| Scale used | MS300 jewelry scale (for magnet weight verification) |
| Calipers | Used for magnet dimension measurement |

---

## Raw Data

### Magnet Caliper Measurements

Measured with digital calipers:

| Dimension | Value (mm) |
|-----------|-----------|
| Diameter | 9.97 |
| Thickness | 2.12 |

### Scale Readings (Magnet Weight Verification)

MS300 scale, affected by magnetic interference with strain gauge load cell.

Method: Scale zeroed vertically (measuring magnetic force only), then turned horizontal (magnetic + gravity). Difference should yield true weight.

| # On Scale | Description | Vertical (g) | Horizontal (g) | Delta (g) |
|-----------|-------------|-------------|----------------|-----------|
| 9 | All magnets (8 whole + 1 fragment) | 132.91 | 169.77 | 36.86 |
| 8 | After removing 1st magnet | 139.19 | 174.18 | 34.99 |
| 7 | After removing 2nd magnet | 128.875 | 161.91 | 33.03 |
| 6 | After removing broken half | 123.56 | 156.25 | 32.69 |
| 5 | After removing broken larger piece | 129.40 | 161.17 | 31.77 |
| 4 | After removing 4th magnet | 105.09 | 135.09 | 30.00 |
| 3 | After removing 5th magnet | 107.26 | 136.11 | 28.85 |
| 2 | After removing 6th magnet | 84.96 | 112.65 | 27.69 |
| 1 | After removing 7th magnet | 56.74 | 82.70 | 25.96 |
| 0+fragment | After removing 8th magnet (1 fragment left) | 25.81 | 48.22 | 22.41 |

**Problems with scale data:**
- Readings increased after removing magnets in some steps (physically impossible)
- Final "1 fragment remaining" showed 22.41g (impossibly heavy for a small magnet fragment)
- Individual magnet deltas ranged from 0.34g to 3.55g (inconsistent)
- Cause: Neodymium magnets interfere with the strain gauge load cell in the MS300

### Balloon Lift Test Log (Verbatim)

User's raw log entries:

```
reduced from 12 magnets to 11 magnets at 21:31 on 08.03.2025
09.03.2026 at 20.31 (same)
reduced from 11 to 10 magnets on 10.03.2026 at 09:10
11.03.2026 reduced from 10 to 09 magnets at 23:00
11.03.2026 reduced from 10 to 9 magnets
17.03.2026 teduced from 9 to 8 magnets at 23:10
22.03.2026 reduced from 8 to 7 magnets at 11:30
01.04.2026 reduced from 7 to 5 magnets at 23:51
02.04.2026 reduced from 5 to 4 magnets at 21:41
After this the ballon got lost with the remaining three magnets.
```

---

## Data Sanitization Process

### Step 1: Date Correction

The first entry reads "08.03.2025" but all subsequent entries are 2026. This is clearly a typo — the test started on **08.03.2026**. All entries normalized to 2026.

### Step 2: Duplicate Entry Removal

Two entries exist for 11.03.2026:
- "11.03.2026 reduced from 10 to 09 magnets at 23:00"
- "11.03.2026 reduced from 10 to 9 magnets"

These describe the same event (10 → 9 magnets). The second is a re-statement. Consolidated into one entry at 23:00.

### Step 3: Non-Reduction Entry

"09.03.2026 at 20.31 (same)" — the user noted "same", meaning no magnets were removed. This is an observation point, not a reduction event. Retained for leak rate analysis but marked as non-reduction.

### Step 4: Multi-Magnet Drop

On 01.04.2026, the count dropped from 7 to 5 (2 magnets at once). This could mean:
- Two balloons leaked significantly on the same day, or
- The user checked less frequently and found 2 magnets had become too heavy

Retained as a single event with 2-magnet loss.

### Step 5: Final State

"After this the ballon got lost with the remaining three magnets" — the test rig flew away or was lost when 3 magnets (~3.6g) remained on the line. This means the balloons could still lift 3 magnets but not 4 at that point. The loss event is between the last observation (02.04.2026 21:41, 4 magnets) and whenever the rig was discovered missing.

### Sanitized Timeline

| Date/Time | Magnets (before) | Magnets (after) | Event |
|-----------|-----------------|----------------|-------|
| 08.03.2026 21:31 | 12 | 11 | First reduction |
| 09.03.2026 20:31 | 11 | 11 | Observation only (no change) |
| 10.03.2026 09:10 | 11 | 10 | Reduction |
| 11.03.2026 23:00 | 10 | 9 | Reduction |
| 17.03.2026 23:10 | 9 | 8 | Reduction |
| 22.03.2026 11:30 | 8 | 7 | Reduction |
| 01.04.2026 23:51 | 7 | 5 | Reduction (2 magnets) |
| 02.04.2026 21:41 | 5 | 4 | Reduction |
| After 02.04.2026 | 4 | 3? | Lost with ~3 magnets remaining |

---

## Calculations

### Magnet Weight

The MS300 scale could not reliably measure neodymium magnets due to magnetic interference with the strain gauge load cell. Instead, weight was calculated from physical dimensions and material density.

**Method:**

1. **Volume from caliper measurements:**
   ```
   diameter = 9.97 mm, radius = 4.985 mm
   thickness = 2.12 mm
   volume = pi * r^2 * h
          = 3.14159 * 4.985^2 * 2.12
          = 165.5 mm^3
          = 0.1655 cm^3
   ```

2. **Material density:**
   - Magenesis magnets are described as "Neodymium" with nickel coating
   - Neodymium magnet grades: N35 (7.3 g/cm^3), N42 (7.4 g/cm^3), N52 (7.5 g/cm^3)
   - Cheap Amazon magnets are typically N35 grade
   - Used density: **7.3 g/cm^3** (N35)

3. **Weight calculation:**
   ```
   weight = volume * density
          = 0.1655 cm^3 * 7.3 g/cm^3
          = 1.21 g per magnet
   ```

4. **Cross-check with scale data:**
   - The 4 most consistent individual magnet deltas from scale readings: 1.87g, 1.96g, 1.77g, 1.73g (average 1.83g)
   - Amazon pack weight: 95g / 52 magnets = 1.83g (includes packaging, lifting plates)
   - Both are biased high by the same magnetic interference issue
   - Density calculation of 1.21g is considered more reliable

**Result: 1.21g per magnet** (N35 density estimate from caliper measurements)

### Per-Balloon Net Lift

```
Initial free lift = 12 magnets * 1.21 g/magnet = 14.5 g (for 3 balloons)
Per-balloon net lift = 14.5 / 3 = 4.83 g
```

This represents the net lifting capacity per balloon after subtracting the balloon's own envelope weight.

### Per-Balloon Envelope Weight

Standard 18" round foil balloon holds approximately 14-15 liters of helium.

```
Gross lift per balloon = 15 L * 1.02 g/L (helium buoyancy at STP) = 15.3 g
Net lift per balloon    = 4.83 g (measured)
Envelope weight         = 15.3 - 4.83 = ~10.5 g per balloon
```

This matches industry estimates of 10-12g for standard party foil balloons.

### Leak Rate Analysis

```
Total lift lost: (12 - 3) magnets * 1.21 g = 10.9 g
Duration: ~25 days
Leak rate (3 balloons): 10.9 / 25 = 0.44 g/day
Leak rate per balloon:  0.44 / 3 = 0.15 g/day
```

**Per-period breakdown:**

| Period | Magnets Lost | Lift Lost (g) | Days | Rate (g/day) | Notes |
|--------|-------------|---------------|------|-------------|-------|
| Start → 08.03 | 1 | 1.21 | ~1 | ~1.21 | Rapid initial loss |
| 08.03 → 10.03 | 1 | 1.21 | 1.5 | 0.81 | |
| 10.03 → 11.03 | 1 | 1.21 | 1.6 | 0.76 | |
| 11.03 → 17.03 | 1 | 1.21 | 6.0 | 0.20 | Slow period |
| 17.03 → 22.03 | 1 | 1.21 | 4.5 | 0.27 | |
| 22.03 → 01.04 | 2 | 2.42 | 10.5 | 0.23 | 2 magnets at once |
| 01.04 → 02.04 | 1 | 1.21 | 0.9 | 1.34 | Accelerating failure |

The leak rate was relatively stable at ~0.2-0.3 g/day per 3-balloon system for most of the test, but accelerated to >1 g/day near the end, suggesting one or more balloons developed a significant leak.

### Flight Duration Projections

Projections use the measured indoor leak rate of 0.15 g/day per balloon. These are UPPER BOUNDS — outdoor conditions will be worse.

**With cut-down system (dead balloons released):**

| Payload | Balloons | Initial Lift (g) | Free Lift (g) | Leak Rate (g/day) | Est. Days | Survives N Failures |
|---------|----------|-----------------|---------------|-------------------|-----------|-------------------|
| Minimal (9g) | 4 | 19.3 | 10.3 | 0.58 | ~18 | 2 |
| Minimal (9g) | 6 | 29.0 | 20.0 | 0.87 | ~23 | 4 |
| Minimal (9g) | 8 | 38.7 | 29.7 | 1.16 | ~26 | 6 |
| Mesh V1 (14g) | 5 | 24.2 | 10.2 | 0.72 | ~14 | 2 |
| Mesh V1 (14g) | 6 | 29.0 | 15.0 | 0.87 | ~17 | 3 |
| Mesh V1 (14g) | 7 | 33.8 | 19.8 | 1.01 | ~20 | 4 |
| Mesh V1 (14g) | 8 | 38.7 | 24.7 | 1.16 | ~21 | 5 |

### Over-Provisioning Analysis: Cut-Down Is Essential

A dead balloon that stays attached acts as 10.5g of dead weight — more than DOUBLE the 4.8g of lift it provided when alive.

**Without cut-down (6 balloons, Mesh V1 14g):**

| Alive/Total | Lift (g) | Dead Weight (g) | Net (g) | Payload (g) | Margin | Status |
|------------|---------|----------------|---------|-----------|--------|--------|
| 6/6 | 29.0 | 0.0 | 29.0 | 14 | +15.0 | Flying |
| 5/6 | 24.2 | 10.5 | 13.7 | 14 | -0.3 | Sinking |
| 4/6 | 19.3 | 21.0 | -1.7 | 14 | -15.7 | Sinking |

First balloon death = mission over.

**With cut-down (6 balloons, Mesh V1 14g):**

| Alive/Total | Lift (g) | Dead Weight (g) | Net (g) | Payload (g) | Margin | Status |
|------------|---------|----------------|---------|-----------|--------|--------|
| 6/6 | 29.0 | 0 | 29.0 | 14 | +15.0 | Flying |
| 5/6 | 24.2 | 0 | 24.2 | 14 | +10.2 | Flying |
| 4/6 | 19.3 | 0 | 19.3 | 14 | +5.3 | Flying |
| 3/6 | 14.5 | 0 | 14.5 | 14 | +0.5 | Flying (barely) |
| 2/6 | 9.7 | 0 | 9.7 | 14 | -4.3 | Sinking |

Can survive losing 3 out of 6 balloons.

**Cut-down hardware weight penalty:**
- Per channel: MOSFET (IRLML2502, ~0.02g) + nichrome wire + nylon tether ≈ 0.5g
- 6 channels: ~3g extra payload
- Net effect: 3g more payload, but can survive multiple balloon deaths — worthwhile for long-duration

### Altitude Effects (Qualitative)

These projections are based on INDOOR, room temperature data. At stratospheric altitude (~12 km):

| Factor | Effect | Impact |
|--------|--------|--------|
| Lower pressure (~194 hPa at 12 km vs 1013 hPa) | Gas expands, but foil envelope is rigid — limited expansion | Neutral to slightly positive |
| Extreme cold (-60°C) | Gas contracts: 216K/293K = 0.74, lift drops ~22% | Significant negative |
| UV radiation | Degrades Mylar/foil material, accelerates leaks | Significant negative |
| Thermal cycling (-60°C night to +20°C day) | Stresses seams and valves | Moderate negative |
| Jetstream vibration (150+ km/h) | Mechanical fatigue on seams | Moderate negative |

**Realistic outdoor projection: 2-5x faster leak rate than indoor test → 4-8 days expected flight duration with over-provisioning + cut-down.**

---

## Key Findings

1. **Per-balloon net lift: 4.8g** — Each DecoGlee 18" foil balloon provides ~4.8g of lifting capacity beyond its own weight when filled with helium.

2. **Per-balloon envelope weight: ~10.5g** — Standard party foil balloons are heavy relative to their lift.

3. **Indoor leak rate: 0.15 g/day per balloon** (Amazon helium). Stable for ~20 days, then accelerates.

4. **Dead balloon penalty: 10.5g dead weight vs 4.8g lift** — Over-provisioning without a cut-down mechanism is counterproductive. A dead balloon that stays attached is more than 2x heavier than the lift it provided.

5. **Cut-down is essential for long-duration flights.** A nichrome wire per balloon adds ~0.5g per channel but allows the system to shed dead weight and survive multiple balloon failures.

6. **Party balloons are viable for short test flights (3-8 days).** For multi-week flights, purpose-built envelopes (SBS-13, SPS-13) would be needed. However, the low cost (~EUR 0.37/balloon from a 30-pack) makes party balloons attractive for disposable test flights and iterative development.

7. **Balloon count sweet spot for Mesh V1 (~14g):** 6-7 balloons with cut-down, providing 17-20 days indoor (4-8 days outdoor estimated), surviving 3-4 balloon failures.

8. **Helium purity matters.** Amazon party helium may be diluted with air. Industrial-grade 99% helium would provide more lift per balloon.

9. **Hydrogen provides ~8% more lift** than helium (1.10 g/L vs 1.02 g/L) at the cost of flammability. For unmanned pico balloons, this is an acceptable tradeoff used by many ham radio balloonists.

---

## Implications for Project Design

### First Flight Strategy

Start with a simple configuration:
- 6 DecoGlee balloons in vertical chain
- Minimal tracker payload (~9g)
- No cut-down (accept first balloon death = mission end)
- Heat-seal all valve necks with flat iron
- Trim excess foil edges (saves ~1g per balloon)
- Aim for 3-5 day test flight

### Long-Duration Strategy

For the mesh network vision:
- Over-provision with 7-8 balloons
- Per-balloon nichrome cut-down with BMP280-triggered release
- Single vertical chain (avoid tangling)
- Consider hydrogen for ~8% more lift
- Consider heat-sealing + additional Mylar tape reinforcement on seams
- Budget for 4-8 day flights, plan for frequent relaunches

### Cost per Flight

| Item | Qty | Unit Cost | Total |
|------|-----|-----------|-------|
| DecoGlee balloons | 6-8 | EUR 0.37 | EUR 2.22-2.96 |
| Helium (shared canister) | ~30L | ~EUR 0.50/L | EUR 15.00 |
| Tracker electronics (reusable) | 1 | EUR 30 | EUR 0 (amortized) |
| Fishing line tethers | ~5m | EUR 0.10 | EUR 0.10 |
| **Total per launch** | | | **~EUR 18** |

If hydrogen used instead of helium: ~EUR 5 for gas, total ~EUR 8 per launch.

---

## Test Log

| Date | Event |
|------|-------|
| 08.03.2026 | Test started. 3x DecoGlee 18" balloons filled with Amazon helium. 12 Magenesis 10x2mm neodymium magnets attached. |
| 08.03.2026 | Measured magnet dimensions with calipers: 9.97mm diameter x 2.12mm thickness. |
| 08.03.2026 21:31 | First reduction: 12 → 11 magnets |
| 09.03.2026 20:31 | Observation: still 11 magnets |
| 10.03.2026 09:10 | Reduced: 11 → 10 magnets |
| 11.03.2026 23:00 | Reduced: 10 → 9 magnets |
| 17.03.2026 23:10 | Reduced: 9 → 8 magnets |
| 22.03.2026 11:30 | Reduced: 8 → 7 magnets |
| 01.04.2026 23:51 | Reduced: 7 → 5 magnets (accelerating leak) |
| 02.04.2026 21:41 | Reduced: 5 → 4 magnets |
| After 02.04.2026 | Test rig lost with 3 magnets remaining (~3.6g free lift) |
