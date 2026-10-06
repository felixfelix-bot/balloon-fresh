# Task report — balloon v9 radio decisions, 2026-10-07

## What was done

Wrote two new Architecture Decision Records on a dedicated worktree
(`bf-adr-radio`, branch `adr/radioband-tdm`) stacked on the tip of
`pr/029-dual-band-flight-board` (4059860), updated ADR-029's header with a
one-line supersede pointer, committed, and pushed to both `github` and `ngit`.

## New files

- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` — records the operator's 2026-10-07
  band split: TX on 433 MHz via the F33-2G4 module's 2 W sub-GHz port, RX on 2.4 GHz
  via a separate bare `LoRa2021`, and why a single-module half-duplex chip cannot
  provide simultaneous TX/RX. Includes filtering obligations, the recorded SX1280-as-RX
  alternative (D6), the open 5 V rail item, and the 433 MHz DE-legality flag.
- `docs/adr/035-tdm-radio-schedule.md` — records the operator's 2026-10-07 windowed
  ranging decision and the TDM contract: dedicated ranging, TX, RX, and idle windows;
  one transmitter at a time; GNSS continuous; the firmware schedule contract and
  testability requirement; the energy-opportunistic TX hook; the unresolved storage
  element and 433 duty-cycle open items.

## Modified files

- `docs/adr/029-dual-band-flight-board.md` — added one header line:
  `Superseded in part by ADR-034 (433 MHz TX / 2.4 GHz RX on two chips) and ADR-035 (TDM radio schedule).`

## Numbering verification

Next-free-number checks run on the worktree:

```
git ls-tree -r --name-only HEAD docs/adr
git log --all --oneline --name-only --pretty=format: -- 'docs/adr/*' | sort -u
```

Result: 033 is claimed on an unmerged branch
(`docs/adr/033-giftwrap-single-construction-path.md`); 034 and 035 are free on every
branch inspected.

## Branch and commit

- Local branch: `adr/radioband-tdm`
- Local HEAD after commit: `0d3fe4778c7d800998f8f8db80d6a55a2cafb776`
- Remote `github`: `0d3fe4778c7d800998f8f8db80d6a55a2cafb776`
- Remote `ngit`: `0d3fe4778c7d800998f8f8db80d6a55a2cafb776`

All three observed equal after push, confirmed by `git ls-remote github adr/radioband-tdm`
and `git ls-remote ngit adr/radioband-tdm`.

## What was NOT done

No schematic, placement, routing, or firmware source code was changed — the task was
documentation-only, intended to gate downstream hardware work.

## Blockers

None encountered.
