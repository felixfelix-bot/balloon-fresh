# FIPS CDC ACM Serial Fix Plan

## Problem
tokio_serial's epoll-based async reader cannot read from ESP32-C3 USB serial JTAG
(CDC ACM device). Python blocking I/O works. Root cause: Linux CDC ACM driver
doesn't properly deliver data to epoll for this device class.

## Solution
Replace tokio's async serial reader with a poll()-based blocking thread.
Keep tokio's async writer for outgoing data.

## Checklist
- [ ] Write FIPS-CDC-ACM-FIX-PLAN.md
- [ ] Modify FIPS serial transport: poll()-based reader thread
- [ ] Build FIPS
- [ ] Verify boards running bridge firmware
- [ ] Start FIPS B + FIPS A
- [ ] Verify handshake completes
- [ ] Test ping6
- [ ] Commit and push
