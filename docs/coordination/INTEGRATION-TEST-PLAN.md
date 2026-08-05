# Integration Test Plan — Phases 2-4

## Prerequisites (all phases)

### Hardware
- 2x ESP32-S3 boards (board-a, board-b)
- 2x NiceRF LoRa2021 modules (wired to S3 via jumper wires)
- USB serial connection to both boards
- Breadboard or perfboard for LR2021 wiring

### Wiring Checklist (both boards identical)
| LR2021 Pin | S3 GPIO | Function |
|-----------|---------|----------|
| SCK | 6 | SPI clock |
| MISO | 2 | SPI MISO |
| MOSI | 7 | SPI MOSI |
| NSS | 10 | SPI chip select |
| BUSY | 4 | Busy signal |
| RST | 3 | Reset |
| DIO9 | 5 | IRQ (RX done) |
| LED | 18 | Status LED |
| FEM_TX | 19 | FEM control |

### Firmware
- Branch: autonomous/mesh-baseline
- Build: `idf.py set-target esp32s3 && idf.py build`

---

## Phase 2: Two-Board Raw Byte Ping

**Goal:** Send raw bytes from board A to board B over LoRa. Zero new code.

### Config
- CONFIG_ENABLE_RELAY_MODE=n (use existing CLI commands)
- CONFIG_ENABLE_MESH=n (isolate radio)

### Steps
1. Flash board A: `idf.py -p /dev/ttyACM0 flash monitor`
2. On board A serial console:
   ```
   radio_test 1 "hello"
   ```
   Expected: "TX: 6 bytes sent" or similar

3. Flash board B: `idf.py -p /dev/ttyACM1 flash monitor`
4. On board B serial console:
   ```
   radio_recv 30
   ```
   Expected: "RX: received 6 bytes: hello" within 30s

5. Swap roles (board B TX, board A RX) to verify bidirectional

### Pass criteria
- Board B receives what board A sends
- Latency < 2s
- No corruption in received bytes

### Troubleshooting
| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| No RX | NSS pin wrong | Check wiring, NSS=GPIO10 |
| Garbage RX | SPI speed mismatch | Check SCK frequency |
| Timeout | DIO9 not wired | DIO9=GPIO5 needed for RX IRQ |
| Build fails | Wrong target | `idf.py set-target esp32s3` |

### Estimated time: 30 minutes

---

## Phase 3: Nostr Event Round-Trip

**Goal:** Board A sends Nostr event via relay mode, board B stores it.

### Config (both boards)
```
CONFIG_ENABLE_RELAY_MODE=y
CONFIG_ENABLE_NOSTR_STORE=y
CONFIG_ENABLE_MESH=n
CONFIG_ENABLE_TOLLGATE=n
```
Reconfigure: `idf.py reconfigure && idf.py build`

### Steps
1. Flash both boards with relay-mode firmware
2. Board A serial:
   ```
   relay_send_nostr <pubkey_hex> <kind> "hello from board A"
   ```
   (If CLI command doesn't exist, use: `radio_send <hex_encoded_event>`)

3. Board B serial:
   - radio_task receives packet → pushes to rx_queue
   - app_task dequeues → nostr_event_deserialize → nostr_store_add
   - Expected log: "Stored Nostr event: id=... kind=1"

4. Verify on board B:
   ```
   nostr_dump
   ```
   (If CLI command doesn't exist, check serial log for store confirmation)

### Pass criteria
- Board B logs "Stored Nostr event" with correct pubkey/kind/content
- nostr_store count incremented
- Event ID matches on both boards

### Troubleshooting
| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| "deserialize failed" | Deserialize bug | Fixed in commit f11ddd6 — verify build |
| Event not stored | Store full | Check capacity, restart board B |
| No RX | DIO9 not wired | Check GPIO5 connection |
| TX never sends | tx_queue empty | Check relay_send CLI command |

### Estimated time: 1 hour

---

## Phase 4: TollGate PAY Round-Trip

**Goal:** Board A sends PAY, board B decodes and sends ACK back.

### Config (both boards)
```
CONFIG_ENABLE_RELAY_MODE=y
CONFIG_ENABLE_NOSTR_STORE=y
CONFIG_ENABLE_TOLLGATE=y
CONFIG_ENABLE_MESH=n
```
Reconfigure: `idf.py reconfigure && idf.py build`

### Steps
1. Flash both boards with tollgate-enabled firmware
2. Board A serial:
   ```
   tollgate_send_pay 1000 "test-payment-001"
   ```
   (If CLI doesn't exist, encode PAY via test code and send via radio_send)

3. Board B receives → app_task:
   - tollgate_proto_decode → TG_MSG_PAY
   - Encode ACK with matching seq
   - Push ACK to tx_queue → radio_task sends

4. Board A receives ACK:
   - Expected log: "TollGate ACK received: seq=1000"
   - Verify ACK payload matches

### Pass criteria
- Board B decodes PAY and sends ACK
- Board A receives ACK within 5s
- Sequence numbers match
- Payment amount preserved in ACK

### Troubleshooting
| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| PAY not decoded | Wrong API names | Fixed in cb49869 — verify build |
| No ACK sent | tx_queue full | Check RELAY_TX_QUEUE_LEN |
| ACK corrupted | Serialization bug | Run host-side relay test (12/12 pass) |

### Estimated time: 1 hour

---

## Pre-Flight Checklist (before starting any phase)

- [ ] Both boards flash successfully with `idf.py -p /dev/ttyACMx flash`
- [ ] Serial monitor shows boot messages on both boards
- [ ] GPIO pins verified with multimeter (NSS=10, BUSY=4, DIO9=5)
- [ ] LR2021 modules powered (3.3V, check current draw)
- [ ] Boards at least 30cm apart (avoid overload)
- [ ] No other track holding board locks (check balloon-board-lock.py)

## Missing CLI Commands

The following CLI commands may not exist yet and need implementation:

| Command | Purpose | Estimated work |
|---------|---------|----------------|
| relay_send_nostr | Serialize + send Nostr event | 2h (needs Nostr serialize) |
| nostr_dump | Dump stored events | 1h (simple iteration) |
| tollgate_send_pay | Encode + send PAY | 1h (tollgate_proto_encode exists) |

If these commands don't exist, Phase 2 (raw ping) is the only testable phase
without writing new CLI code. Phase 3-4 can be tested via serial input or
by hardcoding test packets in app_main.cpp.

## Total estimated time: 2.5 hours (with CLI commands) or 30 min (raw ping only)