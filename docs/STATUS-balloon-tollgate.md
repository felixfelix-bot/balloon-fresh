# Balloon TollGate — Status

## Discovery Sync Log

### Batch 10 (2026-08-08): diagonal 45° routing capability
- **Source:** balloon-circuit-design commit `cbdd656`
- **Finding:** `route_diagonal.py` adds 8 diagonal routing patterns for PCB v7 (13/16 signal nets routed, up from 9/16)
- **Tags:** HARDWARE, PROTOCOL
- **TollGate impact:** ZERO. PCB routing tool — not in tollgate scope (firmware: Cashu portal, Nostr relay, wifistr). No `route_diagonal.py` in tollgate worktree.
- **Action:** None. Informational only.

### Batch 9 (2026-08-08): 6 PCB findings, zero tollgate impact
- PCB placement gates, FreeROUTING hung, DRC iterations — all hardware track work.
- **TollGate impact:** ZERO.

### Batch 8 (2026-08-08): 2 PCB placement gate findings, zero tollgate impact
- **TollGate impact:** ZERO.

### Batch 7 (2026-08-08): 2 C3 PCB findings, zero tollgate impact
- **TollGate impact:** ZERO.

### Batches 1-6 (2026-08-05 to 2026-08-07): Various PCB findings, zero tollgate impact
- **TollGate impact:** ZERO.