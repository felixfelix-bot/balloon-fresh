# TX Payload Buffer — Implementation Spec (T0)

Branch: `feat/tx-buffer` (base: `feat/persist-tx-seq` @ 04e9470)
Reviewer: kimi-consultant cold review 2026-08-21 (all findings adopted)

## Decisions (FINAL — do not relitigate in tasks)

| Point | Decision |
|---|---|
| Framing | Length-delimited, NO escaping. `BUF LOAD <n> <crc16_hex>\r\n` ack `OK BINARY <n>`, then exactly n raw bytes, then reply `OK BUF <n> <crc_ok>` or `ERR CRC` |
| CRC16 | CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect, no xorout). Bitwise in C (~40B). Golden vectors shared C↔Python in tests |
| Seq headers | (a) VERBATIM — host embeds 4-byte BE seq + PRBS-15 body in staged payloads. RX pipeline untouched, bit_err stays meaningful |
| Wrap | ALWAYS wrap buffer end (long-soak capable). Chunk = contiguous slice; wrap at buffer boundary |
| LEN | chunk size = START LEN= (existing validation 6–255 LoRa / 6–511 FLRC). LEN may exceed staged bytes (wrap) |
| PRBS fallback | len==0 → existing PRBS path unchanged. `OK START` reply gains `src=BUF` or `src=PRBS` |
| Persistence | Buffer survives STOP/ROLE change; cleared ONLY by BUF CLEAR / new LOAD / power cycle |
| Capacity | 4096 bytes static + u16 len + u16 crc. Reject `n=0` and `n>4096` BEFORE binary mode (`ERR RANGE`) |

## Reject matrix (BUF LOAD)

Reject with ERR (no binary phase) when: role==RX, state==BSTATE_TX_BURST, tx_armed (NOTE: STOP does NOT clear armed; unlock = ROLE change), n==0, n>4096.
Reject clears any partial state, returns to line mode.

## Binary receive rules

1. Consume the command line's trailing CR/LF BEFORE counting payload bytes (off-by-2 hazard).
2. Feed IWDG inside receive-wait loop (IWDG is STICKY after first ARM TX — "unarmed" ≠ safe).
3. Idle timeout 1.0s → abort, discard, `ERR TIMEOUT`, return to line mode.
4. Firmware SILENT between ack and final OK/ERR (no interleaved output).
5. CRC fail → set len=0 (stale-partial buffer forbidden), reply `ERR CRC`.
6. Ring overflow (128B console ring) is detected by end-CRC; optionally count drops, surface in BUF STATUS.

## Commands

- `BUF CLEAR` → `OK BUF 0`
- `BUF LOAD <n> <crc16_hex>` → see framing above
- `BUF STATUS` → `BUF len=<n> crc=<hex4> drops=<n>`
- `STAT?` and `ID?` gain ` buf=<n>` suffix
- `START` → `OK START ... src=BUF|PRBS`

## RX-side addition (T5a — proceed NOW, SWD works despite dead UART)

Append 24th PKT field `pcrc16` (payload CRC16, same variant). APPEND ONLY — never reorder existing 23 fields. Host tool `e80_sweep.py` (balloon-fresh, feat/c3-harmonization) updated lockstep: parse_pkt accepts 23 OR 24 fields; add binary loader (NO retry/reset_input_buffer during binary phase — dedicated non-retrying path).

## Test numbers (consultant-corrected)

- Wrap boundary: N=64 (4096/64, exact, no wrap), N=65 and N=100 (wrap at chunk 65)
- NOT N=50 (3200B < 4096, no wrap — old plan math wrong)
- Golden CRC vectors: "" =0x0000? NO — CCITT-FALSE("123456789")=0x29B1 (canonical). Also 64B zero vector + 4096B incrementing vector shared C/Python.

## E2E gate (T5b, needs RX UART hardware fix)

Pass (a): host stages 50×64B seq+PRBS payloads → PRBS ON → all PKT bit_err==0.
Pass (b): host stages random data → PRBS OFF → pcrc16 matches host-computed → byte-exact via pcrc16.
Publish: data/e80-harmonization/ measurement file + commit + push. THAT COMMIT IS THE FINAL QUALITY GATE.

## Flash budget gate

24988 + ~1200 ≈ 26.2K < 35K hard budget. BUILD FAILS GATE IF >35K.
