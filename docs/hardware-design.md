> **ARCHIVED → `archive/docs/hardware-design.md`** (moved 2026-10-14)
>
> **Superseded generation.** This is a v1/v2-era concept document whose every
> design choice has been replaced. It is kept for history only.
> **Do not cite as authority.**
>
> **Why it was archived:** it is the **only source of the 22 × 22 mm hub figure**
> in the repo, and its component court (ESP32-**C3** + LR2021 module + BMP280 +
> **SKY66112 FEM** + **SP4T switch** + TPS7A02 + 2 supercaps, 2-layer) is replaced
> item by item:
>
> | This document | Replaced by |
> |---|---|
> | ESP32-C3 | **ESP32-S3-WROOM-1U-N8R8** — ADR-029 D1, confirmed by **ADR-069** |
> | SKY66112 FEM | **omitted from v9** — ADR-037 |
> | Wi-Fi/BT for config | **never enabled** — ADR-038 |
> | 22 × 22 mm, 2-layer hub | **60 × 60 mm, 4-layer** — **ADR-068** (supersedes ADR-055 D5 / ADR-051 §2.3) |
> | 65 × 28 mm wing | **current wing geometry** — ADR-049, ADR-053, ADR-065 |
> | 4 hub slots for wing boards | the four wing interfaces — ADR-046, ADR-048, ADR-051 |
>
> **Analyses that still cite this file** (8): `docs/analysis/hub-outline-authority.md`,
> `wing-electrical.md`, `wing_omnidirectional.py`, `wing_mass_model.py`,
> `hub_thickness_deflection_model.py`, `wing-omnidirectional.md`,
> `hub-thickness-deflection.md`, `wing-mass-shape.md` — they cite it as *historical
> provenance* for a superseded figure, which remains a valid use. This stub exists
> so those citations still resolve.
>
> **The current outline authority is ADR-068.** The current MCU authority is
> ADR-029 D1 as confirmed by ADR-069.
