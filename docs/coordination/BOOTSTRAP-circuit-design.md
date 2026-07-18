# Bootstrap — Balloon Circuit Design Track

**This message is for YOUR track group only (balloon-circuit-design). Do not forward it to other balloon groups. The orchestrator (balloon-hermes) sends messages individually to each track. Your only job is to work in YOUR worktree and report back to balloon-hermes.**

---

You are the balloon-circuit-design track group. This is a NEW track — you have not been bootstrapped yet.

## Your Role

You are a SUB-MANAGER in the balloon project hierarchy. You report to balloon-hermes (the orchestrator). You manage ONE track only: PCB circuit design for manufacturing. You do NOT coordinate other tracks.

## Your Worktree

~/worktrees/balloon-circuit-design/

Your AGENTS.md is already configured with anti-collapse guardrails. Read it.

## Your Mission

Design a manufacturable, tested PCB for the balloon tracker hardware. Target manufacturer: JLCPCB.

CRITICAL RULE: circuits MUST be tested on dev boards (ESP32-C3_Mini_V1) BEFORE ordering from JLCPCB. No ordering unvalidated designs.

Focus areas:
- Schematic capture using SKiDL (Python) + KiCad (for layout)
- PCB layout (2-layer preferred for cost)
- JLCPCB DRC compliance (6mil minimum trace, LCSC component availability)
- Power budget verification (solar → supercaps → LDO → ESP32-C3 + LR2021)
- Gerber file generation for manufacturing
- Design for weight: target <9g flight board (Minimal variant) or <14g (Mesh V1)

## Reference Documents (in your worktree)

- tracker/hardware/hub_board/ — central electronics board (SKiDL + KiCad schematic generator)
- tracker/hardware/hub_board_diy/ — DIY v0.1 dev hub board (toner transfer)
- tracker/hardware/wing_board/ — 4x antenna+solar wing boards
- tracker/hardware/footprints/ — custom component footprint data (JSON)
- docs/component-guide.md — all parts with explanations and alternatives
- docs/power-budget.md — tracker + mesh relay power analysis
- docs/plan-variants.md — DIY / Minimal / Mittel / Komfort / Mesh V1 / Mesh V2 variants

## Radio Pin Assignments (from balloon-hermes, VALIDATED)

### ESP32-C3_Mini_V1 Dev Board (NiceRF LR2021)
```
NiceRF Pin   ESP32 GPIO  Silkscreen
Pin 1        3.3V        3V3
Pin 2,8,11,12,18  GND    GND
Pin 3 (MISO) GPIO2      D2
Pin 4 (MOSI) GPIO7      D7
Pin 5 (SCK)  GPIO6      D6
Pin 6 (NSS)  GPIO10     D10
Pin 7 (BUSY) GPIO4      D4
Pin 9        ANT (Sub-GHz, 50 Ohm)
Pin 10       2.4G (2.4 GHz, 50 Ohm)
Pin 14 (RST) GPIO3      D3
Pin 15 (DIO9/IRQ) GPIO5 D5
Pin 16 (DIO8) GPIO1     D1
Pin 17 (DIO7) GPIO0     D0
```

### ESP32-C3 Bare Flight Board
```
GPIO7  = SPI_MOSI (LR2021)
GPIO2  = SPI_MISO (LR2021)
GPIO6  = SPI_SCLK (LR2021)
GPIO10 = SPI_CS   (LR2021 NSS)
GPIO3  = LR2021 RESET
GPIO4  = LR2021 BUSY
GPIO5  = LR2021 DIO9 (IRQ)
GPIO0  = ADC Supercap Voltage
GPIO20 = I2C_SDA (BMP280)  -- NOT GPIO8 (strapping pin)
GPIO21 = I2C_SCL (BMP280)  -- NOT GPIO9 (strapping pin)
GPIO1  = FEM TX_EN (SKY66112) -- optional
```

IMPORTANT: GPIO8 and GPIO9 are strapping pins on ESP32-C3. Do NOT use them for I2C or anything with pull-ups. The flight board uses GPIO20/GPIO21 for I2C.

## Your First Task

1. Read the existing hub_board SKiDL schematic and the DIY v0.1 board docs
2. Read the component guide and power budget analysis
3. Review the plan-variants to understand weight/feature tradeoffs for each PCB variant
4. Design a first-pass schematic for the Minimal variant (~8-9g, wire dipole, no FEM)
5. Verify the pin assignments above are consistent with the existing hub_board design
6. Identify any conflicts between the validated pin map and existing schematic

Save your work to tracker/hardware/balloon-minimal-board/ in your worktree.

## Then Write Your Assessment

Write docs/INTEGRATION-ASSESSMENT.md using the standard 10-section format:

https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/ASSESSMENT-PROMPT.md

Adapt sections for hardware track:
- "What Works Right Now" — which parts of existing hub_board design are proven
- "Blockers for ESP32-C3 Port" becomes "Blockers for PCB Manufacturing"
- "Dependencies on Other Tracks" — you need validated pin assignments from balloon-hermes (provided above) and weight constraints from balloon-pre-stretching
- "Estimated Effort" — time to schematic capture, layout, DRC, Gerber generation

## When Done

git add tracker/hardware/balloon-minimal-board/ docs/
git commit -m "feat: balloon minimal board schematic + integration assessment"
git push

Then send a 5-line summary to balloon-hermes.