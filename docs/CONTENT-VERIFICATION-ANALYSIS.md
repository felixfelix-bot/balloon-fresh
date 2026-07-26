# Content Verification Analysis — What CRC Proves and What It Doesn't

**Date:** 2025-07-25

---

## THE WALK TEST CONSTRAINT

During the walk test, the TX board is in Felix's rucksack. We CANNOT connect to it via serial. The only evidence of what TX transmitted comes from what RX receives.

This means: if a packet is lost entirely (never received by RX), we cannot know what was in it. We can only verify content of packets that RX successfully captures.

## WHAT CRC-16 CCITT PROVES

**CRC-16 guarantees that the received packet has zero bit errors with very high probability.**

How it works:
- TX fills 249 payload bytes (bytes 4-252) with: GPS lat/lon/sats/fix, phase ID, sequence number, firmware hash, BER fill pattern
- TX computes CRC-16 over ALL 249 bytes
- TX stores CRC at bytes 253-254
- RX recomputes CRC over received bytes 4-252
- If recomputed CRC matches stored CRC → packet content verified

**What this proves:**
- Every received bit in those 249 bytes is correct
- GPS coordinates are correct
- Phase ID is correct
- Sequence number is correct
- BER fill pattern is correct
- Firmware hash is correct

**What this does NOT prove:**
- That TX actually sent a packet we didn't receive (packet loss)
- That the RF link was clean (we might have received garbage that happens to pass CRC — probability ~1/65536 per packet)

## BIT ERROR RATE (BER) ANALYSIS

For packets that RX receives, we can do BYTE-LEVEL comparison:

TX fill pattern (bytes 31-254):
```c
for (int i = 31; i < pktSize; i++) txBuf[i] = (uint8_t)(i & 0xFF);
```

Byte 31 = 0x1F, byte 32 = 0x20, byte 33 = 0x21, ... byte 254 = 0xFE.

RX knows the expected pattern. If ANY byte differs from expected, RX can:
1. Count total bit errors in that byte
2. Report which byte position had the error
3. Compare across packet sizes and modes

**This gives us BER even on packets that pass CRC** (if CRC is ever wrong due to a coincidence).

However: on packets that RX never receives, we have zero data. We can compute PER (packet error rate) as lost/total, but not BER.

## WHAT WE SEE DURING THE WALK

For each packet RX receives:
- Phase ID (which radio mode + size)
- Sequence number (which packet in the phase)
- GPS lat/lon (TX position)
- RSSI (signal strength)
- CRC pass/fail (content integrity)

For each phase RX sees:
- PHASE_RESULT: how many packets received vs lost
- PER (packet error rate)
- Average/minimum RSSI
- CRC error count

**The operator does NOT need to interact with TX during the walk.**
TX boots → waits for GPS fix → starts sweeping → embeds GPS data in every packet → RX captures everything.

## SUMMARY

| Question | Answer |
|----------|--------|
| Can we verify received packet content? | YES — CRC-16 guarantees bit-for-bit correctness |
| Can we verify lost packet content? | NO — packet never arrived, nothing to check |
| Can we do BER analysis? | YES — for received packets, compare fill pattern |
| Can we track position? | YES — GPS lat/lon in every packet |
| Does operator need to interact with TX? | NO — autonomous after GPS lock |
