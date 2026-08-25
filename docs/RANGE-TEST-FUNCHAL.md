# E80 Range Test Plan — Funchal, Madeira

**Base station:** Cowork Funchal, Rua das Mercês 41, 3rd floor (~30m elev)
**Coordinates:** 32.6513120, -16.9116550
**Date:** August 2026

## Cowork Window Orientation

The cowork has windows on all four sides. The RX board must be moved
between window sets depending on the TX direction:

| Window | Direction | Faces | Best for |
|--------|-----------|-------|----------|
| South | S/SW | Sea, rooftops | Cabo Girão, Ponta da Cruz, Pico do Funcho |
| North | N/NNE | Hills, Monte | Monte, Quinta Imperador, Pico do Arieiro, Pico Ruivo |
| East | E/ENE | Coast, Garajau | São Gonçalo, Garajau, Caniço, Camacha |
| West | W/WNW | Hills, Câmara de Lobos | Pico dos Barcelos, Jardim Achada, Cabo Girão (alt) |

**Constraint:** Each window change requires traveling to the cowork.
Group TX locations by window side to minimize trips.

## Trip Plan (sorted by window side)

### TRIP 1 — SOUTH WINDOW (sea-facing)
**RX at Cowork, south window. TX walks west along seafront.**

| Stop | Distance | TX Location | Bearing | Notes |
|------|----------|-------------|---------|-------|
| 50m | 50m | Avenida do Mar (outside building) | S | Walk out front door |
| 100m | 100m | Avenida do Mar, past marina | S | Continue along seafront |
| 218m | 218m | Avenida do Mar / Rua do Gomes | SSW | Near port area |
| 436m | 436m | Parque da Avenida do Mar | S | Park by the sea |
| 872m | 872m | Jardim Miradouro da Achada | NW | **⚠️ NW facing — see Trip 2** |

**Total walking: ~500m along seafront. 4 stops, ~20 min.**

Note: stop-872m (Jardim Achada) is NW-facing, so move it to Trip 2
(North/West window). Stops 50m–436m are all within 500m of Cowork
and can be done from any window — the signal is strong enough at
these distances that window orientation barely matters.

### TRIP 2 — WEST WINDOW (hills/ Câmara de Lobos)
**RX at Cowork, west window. TX travels W/WNW by taxi.**

| Stop | Distance | TX Location | Bearing | Elev | Coordinates | Notes |
|------|----------|-------------|---------|------|-------------|-------|
| 872m | ~1km | Jardim Miradouro da Achada | NW 312° | 100m | 32.6573, -16.9196 | Walkable, hilltop park |
| 1744m | ~2.7km | Pico dos Barcelos | WNW 288° | 200m | 32.6587, -16.9394 | Hilltop viewpoint, taxi |
| 5000m | ~5.7km | (skip — Garajau is E-facing) | — | — | — | Do in Trip 3 |
| 11000m | ~8.7km | Cabo Girão | W 274° | 580m | 32.6565, -17.0045 | 580m sea cliff, spectacular LOS |

**Total: 3 stops. Taxi to Pico dos Barcelos (~10 min), then taxi to Cabo Girão (~15 min).**
**Window change: 1 (south → west before starting).**

Cabo Girão is one of the highest sea cliffs in Europe — 580m vertical
drop with unobstructed LOS over the sea to Funchal. Ideal for the
stop-11000m test. The cliff face looks ESE toward Funchal.

### TRIP 3 — EAST WINDOW (coastal, Garajau side)
**RX at Cowork, east window. TX travels E/ENE by taxi.**

| Stop | Distance | TX Location | Bearing | Elev | Coordinates | Notes |
|------|----------|-------------|---------|------|-------------|-------|
| 1744m | ~2.7km | São Gonçalo | E 94° | 50m | 32.6497, -16.8831 | Coastal headland, sea-level |
| 5000m | ~5.7km | Garajau | E 99° | 50m | 32.6433, -16.8514 | Coastal headland, clear LOS over sea |
| 5000m (alt) | ~7km | Camacha | ENE 63° | 600m | 32.6794, -16.8449 | High plateau, may have hill blocking |
| 11000m | ~15.8km | Machico | ENE 60° | 10m | 32.7229, -16.7659 | Coastal town, sea-level LOS |

**Total: 2-3 stops. Taxi to Garajau (~15 min), then to Machico (~30 min).**
**Window change: 1 (west → east before starting).**

Garajau is a coastal headland with clear LOS over water to Funchal.
The path goes over the sea — no terrain obstruction. Camacha is higher
(600m) but inland — verify visual LOS first, hills may block.

### TRIP 4 — NORTH WINDOW (Monte / peaks)
**RX at Cowork, north window. TX travels N/NNE by taxi.**

| Stop | Distance | TX Location | Bearing | Elev | Coordinates | Notes |
|------|----------|-------------|---------|------|-------------|-------|
| 1744m | ~2.7km | Quinta Jardins do Imperador | N 9° | 550m | 32.6750, -16.9074 | Monte area, looks DOWN into bowl |
| 1744m (alt) | ~2.9km | Monte (village) | NNE 15° | 550m | 32.6763, -16.9038 | Same hillside, classic viewpoint |
| 11000m | ~9.2km | Curral das Freiras | NNW 327° | 650m | 32.7208, -16.9657 | Central valley, surrounded by peaks |
| 11000m (alt) | ~9.5km | Pico do Arieiro | N 350° | 1818m | 32.7357, -16.9287 | 1818m peak, sees entire island |
| 11000m+ | ~12.5km | Pico Ruivo | NNW 346° | 1862m | 32.7603, -16.9435 | Highest peak on Madeira |

**Total: 2-3 stops. Taxi to Monte (~10 min), then drive to Pico do Arieiro (~45 min up mountain road).**
**Window change: 1 (east → north before starting).**

Monte (550m) looks directly down into the Funchal bowl — excellent LOS
to Cowork's north window. Pico do Arieiro (1818m) has panoramic views
of the entire island. Both are near-guaranteed LOS.

Curral das Freiras is in a deep valley — LOS to Funchal may be blocked
by intervening ridges. Verify visually before testing.

### TRIP 5 — MAX RANGE (Northwest, far side of island)
**RX at Cowork, north or west window. TX drives to far side of island.**

| Stop | Distance | TX Location | Bearing | Elev | Coordinates | Notes |
|------|----------|-------------|---------|------|-------------|-------|
| 70000m | ~34km | Porto Moniz | NW 315° | 50m | 32.8670, -17.1666 | Far NW coast, volcanic pools |
| 70000m (alt) | ~15.5km | Encumeada | NW 317° | 1000m | 32.7538, -17.0240 | Mountain pass, high elevation |

**Total: 1 stop. Drive to Porto Moniz (~1 hour via ER101).**
**Window change: north or west window.**

Porto Moniz is the farthest point on Madeira from Funchal (~34km).
True 70km is not possible on a single island — would need Porto Santo
(~40km away, separate island, ferry/plane required).

Encumeada (15.5km, 1000m pass) is closer and has high elevation —
may work for a "max range on Madeira" test. LOS likely blocked by
central peaks (Pico Ruivo massif).

## Summary: Optimal Trip Sequence

Minimizes window changes at Cowork:

| Order | Window | TX Stops | Travel | Duration |
|-------|--------|----------|--------|----------|
| 1 | South | 50m, 100m, 218m, 436m | Walk seafront | 30 min |
| 2 | West | 872m (Achada), 1744m (Barcelos), 11000m (Cabo Girão) | Taxi ×2 | 2 hours |
| 3 | East | 1744m (São Gonçalo), 5000m (Garajau), 11000m (Machico) | Taxi ×2 | 2 hours |
| 4 | North | 1744m (Monte), 11000m (Pico Arieiro) | Taxi + drive | 3 hours |
| 5 | NW | 70000m (Porto Moniz or Encumeada) | Drive | Half day |

**Total: 4 window changes, 5 trips, ~1.5 days of testing.**

## Antenna Considerations

- **868 MHz band** (configs 1-7): Use 868 MHz antenna on both boards.
  - Configs: FLRC-2600, FLRC-1300, FLRC-650, FLRC-260, LoRa-SF5 BW500, LoRa-SF7 BW500, LoRa-SF5 BW125
  - Frequency: 869.525 MHz
  - PA: +22 dBm (outdoor mode)

- **2.4 GHz band** (configs 8-10): Swap to 2.4 GHz antenna on Pin 10.
  - Configs: 2G4-FLRC-2600, 2G4-FLRC-650, 2G4-LoRa-SF5 BW500
  - Frequency: 2400 MHz
  - PA: +12 dBm
  - **⚠️ Antenna swap required at both TX and RX between config 7 and 8**
  - At Cowork: swap RX antenna during the ~30s band transition window
  - At TX location: swap TX antenna during same window
  - The script prints "⚠️ BAND TRANSITION" warning

## Technical Setup

### RX (at Cowork, 3rd floor)
```
# Board on /dev/ttyUSB1, probe 203584200D2D0D42
cd /tmp/balloon-fresh/firmware/e80-stm32-bench
make rx DIST=<dist> BOUNDARY_S=60
```

### TX (at viewpoint)
```
# Board on /dev/ttyUSB0, probe 148757200D2D1425
# Bring: E80 board + Pico probe + laptop + antenna(s) + battery
cd /tmp/balloon-fresh/firmware/e80-stm32-bench
make tx DIST=<dist> BOUNDARY_S=60
```

Both compute same T0 (next 60-second boundary). Start both within
50 seconds of each other. BOUNDARY_S=60 means max 60s wait.

### Distributed Mode (separate terminals)
For two-operator mode, each terminal runs independently:

Terminal 1 (RX at Cowork):
```
cd /tmp/balloon-fresh/firmware/e80-stm32-bench
make rx DIST=50m BOUNDARY_S=60
```

Terminal 2 (TX at viewpoint):
```
cd /tmp/balloon-fresh/firmware/e80-stm32-bench
make tx DIST=50m BOUNDARY_S=60
```

T0 and SESSION_ID are auto-computed identically on both machines
(deterministic epoch rounding). No communication needed between
operators — just start both within the same 60-second window.

### Single-Operator mode (both boards on one laptop)
Use the gist script:
```
curl -sL https://gist.githubusercontent.com/felixfelix-bot/f68630ae67a143aa4e7d8be68360f670/raw/e80-desk-sweep.sh | bash -s -- --skip-flash
```

Note: single-machine mode has SWD reset timing issues when both
boards share one openocd. For outdoor tests, use two laptops
(distributed mode).

## Viewpoint Details

### Monte (Quinta Jardins do Imperador)
- **Distance:** 2.66 km N
- **Elevation:** 550m (looks down into Funchal bowl)
- **LOS:** Excellent — Monte is directly above Funchal, unobstructed view
- **Access:** Taxi (~10 min from Cowork), or cable car from Funchal
- **Parking:** Available at Quinta Imperador
- **Best for:** stop-1744m

### Pico dos Barcelos
- **Distance:** 2.72 km WNW
- **Elevation:** 200m hilltop
- **LOS:** Good — hilltop above rooftops, facing Cowork
- **Access:** Taxi (~10 min), short walk uphill
- **Best for:** stop-1744m (west side)

### Cabo Girão
- **Distance:** 8.71 km W
- **Elevation:** 580m sea cliff
- **LOS:** Excellent — 580m vertical cliff, unobstructed over sea
- **Access:** Taxi (~20 min), paved road to cliff top
- **Parking:** Visitor parking at miradouro
- **Best for:** stop-11000m

### Garajau
- **Distance:** 5.71 km E
- **Elevation:** 50m coastal headland
- **LOS:** Good — over water, no terrain obstruction
- **Access:** Taxi (~15 min), coastal road
- **Best for:** stop-5000m

### Pico do Arieiro
- **Distance:** 9.52 km N
- **Elevation:** 1818m
- **LOS:** Panoramic — sees entire island, guaranteed LOS
- **Access:** Drive (~45 min from Funchal), paved road to summit
- **Parking:** Parking at summit
- **Best for:** stop-11000m (north side)
- **Note:** Often in cloud — check weather before driving up

### São Gonçalo
- **Distance:** 2.68 km E
- **Elevation:** 50m coastal headland
- **LOS:** Good — across the bay, over water
- **Access:** Taxi (~10 min), or bus
- **Best for:** stop-1744m (east side)

### Jardim Miradouro da Achada
- **Distance:** 1.0 km NW
- **Elevation:** 100m
- **LOS:** Good — nearby hilltop, above rooftops
- **Access:** Walk (~15 min from Cowork)
- **Best for:** stop-872m

## Quick Reference — Trip Sequence

5 trips, sorted by Cowork window side to minimize changes. Only 4 window
changes total. Each trip group hits all TX locations visible from that
window without going back to move the radio.

| Order | Window | TX Stops | Travel | Duration |
|-------|--------|----------|--------|----------|
| 1 | South | 50m, 100m, 218m, 436m | Walk seafront | 30 min |
| 2 | West | 872m (Achada), 1744m (Barcelos), 11000m (Cabo Girão) | Taxi ×2 | 2 hours |
| 3 | East | 1744m (São Gonçalo), 5000m (Garajau), 11000m (Machico) | Taxi ×2 | 2 hours |
| 4 | North | 1744m (Monte), 11000m (Pico Arieiro) | Taxi + drive | 3 hours |
| 5 | NW | 70000m (Porto Moniz or Encumeada) | Drive | Half day |

**Total: 4 window changes, 5 trips, ~1.5 days of testing.**

Note: 70km true distance not possible on Madeira alone (~34km max to
Porto Moniz). Would need Porto Santo island for 70km+.

## Weather Notes
- Madeira peaks (Pico Arieiro, Pico Ruivo) frequently in cloud
- Check cloud cover before driving to high elevations
- Coastal points (Cabo Girão, Garajau) are usually clear
- Best testing weather: clear morning, before afternoon clouds build
- Sea breeze can affect 868 MHz propagation on coastal paths