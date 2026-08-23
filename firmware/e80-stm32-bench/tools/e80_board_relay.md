# E80 Board Relay Protocol — Distributed Bench Testing Design

**Status:** Draft v1 (2026-08-23)
**Scope:** Split TX/RX board control across two computers for range testing.

---

## 1. Architecture Overview

```
┌──────────────────────────────────────┐
│          COORDINATOR                  │
│  (on T470 or DQ05)                   │
│                                      │
│  e80_sweep_full.py / e80_campaign.py │
│        │            │                │
│   BoardClient   BoardClient          │
│   (TX)          (RX)                 │
└─────┬──────────────┬─────────────────┘
      │ TCP 8685     │ TCP 8685
      │              │
┌─────▼──────┐  ┌────▼────────┐
│ BoardServer│  │ BoardServer  │
│ (TX host)  │  │ (RX host)    │
│            │  │              │
│ serial →   │  │ serial →     │
│ TX board   │  │ RX board     │
│ + SWD probe│  │ + SWD probe  │
└────────────┘  └──────────────┘
```

Each computer runs a **BoardServer** daemon that wraps its local serial
port (CH340 @ 2 Mbaud) and SWD probe (CMSIS-DAP via openocd). The
**coordinator** (either machine) opens two **BoardClient** TCP connections
and drives both boards through the same high-level API the existing code
uses (`cmd()`, `drain()`, `readline()`, `swd_reset()`).

### Design goals

1. **Minimal code changes**: `BoardClient` exposes the same method
   signatures that `e80_sweep_full.py` and `e80_campaign.py` call on
   serial objects today. Migration is mostly `s/cmd(ser, line)/s.cmd(line)/`.

2. **Real-time-safe streaming**: RX packet capture at 2 Mbaud cannot
   block on network. The board server uses a dedicated serial-reader
   thread with a queue-bounded TCP writer.

3. **Simple wire format**: Newline-delimited JSON. Debuggable with
   `nc`, no binary framing, no protobuf build step.

---

## 2. Wire Format

### Framing: Newline-delimited JSON

Every message is a single JSON object terminated by `\n`:

```
{"type":"cmd","id":"42","line":"MOD LORA 7 125","timeout":15.0}\n
{"type":"reply","id":"42","ok":true,"reply":"OK MOD LORA 7 125"}\n
```

**Why not length-prefixed binary?** The board emits ASCII CSV lines
(`PKT,session,config,...,pcrc16\n`). There are no binary payloads in
the current or planned firmware. Newline-delimited JSON is easier to
debug (`nc dq05 8685 | python -m json.tool`), works with `str.splitlines()`,
and maps 1:1 to the board's own line-oriented protocol.

**Max message size:** 64 KB (covers the largest drain response: 10 000
packets × ~150 bytes/line = 1.5 MB → sent as individual `board_line`
messages during capture, not as a single `drain` response). The `drain`
response returns a JSON array of lines capped at 4096 entries; larger
captures must use `capture_start`/`capture_stop` streaming.

### Connection lifecycle

- Server listens on **TCP 8685** (configurable).
- **One active client connection at a time.** A second connection
  receives `{"type":"error","id":null,"code":"BUSY","msg":"connection in use"}`
  and is closed.
- On TCP disconnect, server resets to idle: stops capture mode, clears
  pending command, but keeps the serial port open for the next client.
- Graceful close: client sends `{"type":"quit"}` → server replies
  `{"type":"bye","id":"..."}` and closes the connection. Serial port
  stays open.

---

## 3. Message Types

### 3.1 Coordinator → Board Server

| type | required fields | optional fields | description |
|------|-----------------|-----------------|-------------|
| `cmd` | `id`, `line` | `timeout` (def 15), `prefixes` (def `["OK","ERR"]`) | Send line to board, return first reply matching any prefix. `ERR` → error reply. |
| `write` | `id`, `line` | `timeout` (def 3) | Send line to board, return first non-empty line (no prefix matching). For START command. |
| `drain` | `id`, `duration` | `timeout` (def duration+10) | Collect all board output for `duration` seconds, return as JSON array. Cap 4096 lines. |
| `flush` | `id` | | Clear serial input buffer (discard all pending data). |
| `swd_reset` | `id` | `timeout` (def 45) | Run openocd SWD reset on the board's local probe. |
| `capture_start` | `id` | | Enter streaming mode: forward all board output as `board_line` messages. |
| `capture_stop` | `id` | `timeout` (def 5) | Exit streaming mode. Returns capture stats. |
| `health` | `id` | | Board health: port open, probe serial, openocd available, uptime, last activity, capture active. |
| `ping` | `id` | | Echo with timestamps for latency measurement. |
| `quit` | | | Graceful close. |

### 3.2 Board Server → Coordinator

| type | fields | description |
|------|--------|-------------|
| `reply` | `id`, `ok`, `reply` | Success response to `cmd`/`write`. `reply` is the board's response line (or null for `flush`). |
| `error` | `id`, `code`, `msg` | Error response. `id` may be null for connection-level errors. |
| `drain_result` | `id`, `ok`, `lines` (array[string]) | Response to `drain`. |
| `capture_stats` | `id`, `ok`, `lines_forwarded`, `dropped`, `duration_s`, `seq_end` | Response to `capture_stop`. |
| `swd_done` | `id`, `ok`, `duration_s` | SWD reset completed. |
| `board_line` | `line`, `ts_ns`, `seq` | **Async** (no `id`). Forwarded board output during capture mode. `ts_ns` = server monotonic clock in nanoseconds. `seq` = monotonic counter since `capture_start`. |
| `health_ok` | `id`, `port`, `port_open`, `baud`, `probe_serial`, `openocd_available`, `uptime_s`, `last_activity_s`, `capturing`, `dropped_total` | Health status. |
| `pong` | `id`, `ts_orig_ns`, `ts_recv_ns` | Ping response with server receive timestamp. |
| `bye` | `id` | Graceful close acknowledgement. |

### 3.3 Error Codes

| code | meaning |
|------|---------|
| `BOARD_TIMEOUT` | Board didn't respond within timeout. |
| `BOARD_ERR` | Board returned `ERR <reason>` response. `msg` includes the full ERR line. |
| `SERIAL_CLOSED` | Serial port is closed or inaccessible. |
| `SERIAL_ERROR` | Serial I/O error (read/write failure). |
| `SWD_FAILED` | openocd exited non-zero or timed out. |
| `SWD_UNAVAILABLE` | openocd binary not found on this server. |
| `INVALID_STATE` | Operation not valid in current state (e.g. `capture_start` while already capturing). |
| `OVERLOAD` | Server serial-reader queue overflow (lines dropped). |
| `BUSY` | Another client holds the connection. |
| `INTERNAL` | Unexpected server error. |

---

## 4. Board Server Design

### 4.1 Thread architecture

```
                    ┌──────────────────┐
                    │  TCP listener     │
                    │  (accept loop)    │
                    └────────┬──────────┘
                             │ accept (one client)
                    ┌────────▼──────────┐
                    │  Client handler   │
                    │  (JSON protocol)  │
                    │                   │
                    │  - parse requests  │
                    │  - send replies    │
                    │  - manage state    │
                    └────────┬──────────┘
                             │ shared state (thread-safe)
           ┌─────────────────┼──────────────────┐
    ┌──────▼──────┐   ┌──────▼───────┐   ┌──────▼──────┐
    │ Serial      │   │ SWD          │   │ Capture     │
    │ reader      │   │ reset       │   │ forwarder   │
    │ (thread)    │   │ (subprocess)│   │ (thread)    │
    └─────────────┘   └──────────────┘   └─────────────┘
```

**Serial reader thread** (highest priority — never blocks):
- Reads serial data in 256-byte chunks.
- Assembles lines by scanning for `\n`.
- In **command mode** (default): scanned lines are checked against the
  pending command's expected prefixes. Matched line becomes the reply.
  Non-matching lines are discarded (boot noise, debug spew).
- In **capture mode**: every non-empty line is pushed to a bounded queue
  (max 8192 entries). If queue is full, the **oldest** entry is dropped
  and `dropped_count` increments. New data is always preferred.
- In **drain mode**: every non-empty line is appended to a list (cap 4096).

**Capture forwarder thread**:
- Pops from the capture queue and writes `board_line` JSON messages to
  the TCP socket. If the TCP write blocks (slow consumer), the queue
  grows; if it hits the cap, serial reader drops old entries (never
  blocks the serial read).

**Client handler** (main thread for the connection):
- Reads newline-delimited JSON from TCP.
- Dispatches requests to the appropriate handler (synchronous cmd/drain,
  or state switch for capture mode).
- Sends JSON responses (except `board_line`, which is sent by the
  forwarder thread — synchronized via a write lock).

### 4.2 Server pseudocode

```python
#!/usr/bin/env python3
"""e80_board_server.py — TCP relay daemon for one E80 board + SWD probe."""

import json, os, queue, signal, socket, subprocess, sys, threading, time
import serial

BAUD = 2_000_000
DEFAULT_PORT = 8685
CAPTURE_QUEUE_SIZE = 8192
DRAIN_MAX_LINES = 4096
OPENOCD = "/usr/bin/openocd"

class BoardServer:
    def __init__(self, serial_port, probe_serial, listen="0.0.0.0:8685"):
        self.ser = serial.Serial(serial_port, BAUD, timeout=0.1,
                                  parity="N", stopbits=1, bytesize=8)
        self.port_name = serial_port
        self.probe_serial = probe_serial
        self.fw_dir = os.path.expanduser(
            "~/repos/balloon-e80bench/firmware/e80-stm32-bench")

        host, _, port = listen.rpartition(":")
        self.listen_host = host or "0.0.0.0"
        self.listen_port = int(port or DEFAULT_PORT)

        # State
        self._lock = threading.Lock()       # guards TCP writes
        self._cmd_lock = threading.Lock()   # serializes board commands
        self.mode = "command"               # "command" | "capture" | "drain"
        self.dropped_total = 0
        self.last_activity = time.monotonic()
        self.start_time = time.monotonic()

        # Command response plumbing
        self._pending_cmd = None       # dict: line, prefixes, deadline, result
        self._cmd_event = threading.Event()

        # Capture queue + forwarder
        self._cap_q = queue.Queue(maxsize=CAPTURE_QUEUE_SIZE)
        self._cap_seq = 0
        self._cap_lines_forwarded = 0
        self._cap_start = 0.0
        self._cap_stop = False

        # Drain accumulator
        self._drain_buf = []
        self._drain_deadline = 0.0

        # TCP socket
        self.sock = None

    # ---- Serial reader thread (NEVER blocks on anything but serial) ----

    def serial_reader_loop(self):
        buf = bytearray()
        while True:
            try:
                chunk = self.ser.read(256)
            except Exception as e:
                # Serial error — can't recover, log and exit
                self._push_error("SERIAL_CLOSED", f"serial read: {e}")
                break
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                text = raw.rstrip(b"\r").decode(errors="replace").strip()
                if text:
                    self._handle_serial_line(text)

    def _handle_serial_line(self, line):
        self.last_activity = time.monotonic()
        mode = self.mode

        if mode == "capture":
            try:
                self._cap_q.put_nowait(line)
            except queue.Full:
                # Drop oldest, push newest (newer data = more valuable)
                try:
                    self._cap_q.get_nowait()
                    self.dropped_total += 1
                except queue.Empty:
                    pass
                try:
                    self._cap_q.put_nowait(line)
                except queue.Full:
                    pass  # still full after eviction (race); drop this line

        elif mode == "drain":
            if len(self._drain_buf) < DRAIN_MAX_LINES:
                self._drain_buf.append(line)

        else:  # command mode
            if self._pending_cmd is None:
                return  # unsolicited output during idle — discard
            prefixes = self._pending_cmd.get("prefixes", ["OK", "ERR"])
            deadline = self._pending_cmd["deadline"]
            if time.monotonic() > deadline:
                return  # past timeout, let cmd() handle it
            for p in prefixes:
                if line.startswith(p):
                    self._pending_cmd["result"] = line
                    if line.startswith("ERR"):
                        self._pending_cmd["error"] = True
                    self._cmd_event.set()
                    return
            # Non-matching line during pending cmd — discard (boot noise)

    # ---- Capture forwarder thread ----

    def capture_forwarder_loop(self):
        while True:
            line = self._cap_q.get()  # blocks until line or sentinel
            if line is None:  # sentinel: capture_stop
                break
            self._cap_seq += 1
            msg = {
                "type": "board_line",
                "line": line,
                "ts_ns": time.monotonic_ns(),
                "seq": self._cap_seq,
            }
            self._send_json(msg)
            self._cap_lines_forwarded += 1

    # ---- TCP client handler ----

    def handle_client(self, conn, addr):
        if self.sock is not None:
            self._send_to(conn, {"type": "error", "id": None,
                                 "code": "BUSY",
                                 "msg": "connection in use"})
            conn.close()
            return
        self.sock = conn
        self.conn = conn
        buf = ""
        try:
            while True:
                data = conn.recv(8192)
                if not data:
                    break
                buf += data.decode(errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        self._send_to(conn, {"type": "error", "id": None,
                                             "code": "INTERNAL",
                                             "msg": f"invalid JSON: {line[:100]}"})
                        continue
                    self._dispatch(msg)
        except (ConnectionError, OSError):
            pass
        finally:
            # Reset state on disconnect
            self.mode = "command"
            self._pending_cmd = None
            self._cap_stop = True
            self._cap_q.put(None)  # stop forwarder if running
            self.sock = None
            conn.close()
            print(f"[board-server] client {addr} disconnected, idle")

    def _dispatch(self, msg):
        t = msg.get("type")
        mid = msg.get("id")
        try:
            if t == "cmd":
                self._do_cmd(mid, msg.get("line", ""),
                             msg.get("prefixes", ["OK", "ERR"]),
                             msg.get("timeout", 15.0))
            elif t == "write":
                self._do_cmd(mid, msg.get("line", ""),
                             None,  # no prefix matching
                             msg.get("timeout", 3.0))
            elif t == "drain":
                self._do_drain(mid, msg.get("duration", 5.0))
            elif t == "flush":
                self._do_flush(mid)
            elif t == "swd_reset":
                self._do_swd_reset(mid, msg.get("timeout", 45.0))
            elif t == "capture_start":
                self._do_capture_start(mid)
            elif t == "capture_stop":
                self._do_capture_stop(mid)
            elif t == "health":
                self._do_health(mid)
            elif t == "ping":
                self._do_ping(mid, msg)
            elif t == "quit":
                self._send_to(self.sock, {"type": "bye", "id": mid})
                raise ConnectionError("client quit")
            else:
                self._send_to(self.sock, {"type": "error", "id": mid,
                                          "code": "INTERNAL",
                                          "msg": f"unknown type: {t}"})
        except Exception as e:
            self._send_to(self.sock, {"type": "error", "id": mid,
                                      "code": "INTERNAL", "msg": str(e)})

    # ---- Command handlers ----

    def _do_cmd(self, mid, line, prefixes, timeout):
        with self._cmd_lock:
            if self.mode != "command":
                self._reply_error(mid, "INVALID_STATE",
                                  f"cannot cmd while in {self.mode} mode")
                return
            self._pending_cmd = {
                "line": line,
                "prefixes": prefixes,
                "deadline": time.monotonic() + timeout,
                "result": None,
                "error": False,
            }
            self._cmd_event.clear()
            self.ser.write((line + "\r\n").encode())
            if not self._cmd_event.wait(timeout=timeout):
                self._pending_cmd = None
                self._reply_error(mid, "BOARD_TIMEOUT",
                                  f"no reply to '{line}' in {timeout}s")
                return
            cmd = self._pending_cmd
            self._pending_cmd = None
            if cmd.get("error"):
                self._reply_error(mid, "BOARD_ERR", cmd["result"] or "ERR")
            else:
                self._send_to(self.sock, {"type": "reply", "id": mid,
                                          "ok": True, "reply": cmd["result"]})

    def _do_drain(self, mid, duration):
        with self._cmd_lock:
            if self.mode != "command":
                self._reply_error(mid, "INVALID_STATE",
                                  f"cannot drain while in {self.mode} mode")
                return
            self.mode = "drain"
            self._drain_buf = []
            self._drain_deadline = time.monotonic() + duration
        time.sleep(duration + 0.1)  # let reader accumulate
        with self._cmd_lock:
            lines = list(self._drain_buf)
            self._drain_buf = []
            self.mode = "command"
        self._send_to(self.sock, {"type": "drain_result", "id": mid,
                                  "ok": True, "lines": lines})

    def _do_flush(self, mid):
        with self._cmd_lock:
            self.ser.reset_input_buffer()
        self._send_to(self.sock, {"type": "reply", "id": mid,
                                  "ok": True, "reply": None})

    def _do_swd_reset(self, mid, timeout):
        # Can run concurrently with capture — SWD uses a different USB device
        if not os.path.isfile(OPENOCD):
            self._reply_error(mid, "SWD_UNAVAILABLE", f"{OPENOCD} not found")
            return
        try:
            t0 = time.monotonic()
            result = subprocess.run(
                [OPENOCD, "-f", "interface/cmsis-dap.cfg",
                 "-f", "target/stm32f1x.cfg",
                 "-c", f"transport select swd; adapter serial {self.probe_serial}; "
                       f"init; reset halt; resume; exit"],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=timeout, cwd=self.fw_dir)
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace")[:500]
                # Don't reset mode on SWD failure — board may still be OK
                self._reply_error(mid, "SWD_FAILED",
                                  f"openocd exit {result.returncode}: {err}")
                return
            time.sleep(2.0)  # firmware boot settle
            self._send_to(self.sock, {"type": "swd_done", "id": mid,
                                      "ok": True,
                                      "duration_s": round(time.monotonic() - t0, 2)})
        except subprocess.TimeoutExpired:
            self._reply_error(mid, "SWD_FAILED",
                              f"openocd timed out after {timeout}s")

    def _do_capture_start(self, mid):
        with self._cmd_lock:
            if self.mode != "command":
                self._reply_error(mid, "INVALID_STATE",
                                  f"already in {self.mode} mode")
                return
            self.ser.reset_input_buffer()
            self.mode = "capture"
            self._cap_q = queue.Queue(maxsize=CAPTURE_QUEUE_SIZE)
            self._cap_seq = 0
            self._cap_lines_forwarded = 0
            self._cap_start = time.monotonic()
            self._cap_stop = False
        # Start forwarder thread for this capture session
        t = threading.Thread(target=self._run_forwarder, daemon=True)
        t.start()
        self._forwarder_thread = t
        self._send_to(self.sock, {"type": "reply", "id": mid,
                                  "ok": True, "reply": "capturing"})

    def _run_forwarder(self):
        while not self._cap_stop:
            try:
                line = self._cap_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if line is None:
                break
            self._cap_seq += 1
            self._cap_lines_forwarded += 1
            self._send_json({
                "type": "board_line",
                "line": line,
                "ts_ns": time.monotonic_ns(),
                "seq": self._cap_seq,
            })

    def _do_capture_stop(self, mid):
        with self._cmd_lock:
            if self.mode != "capture":
                self._reply_error(mid, "INVALID_STATE", "not capturing")
                return
            self.mode = "command"
            self._cap_stop = True
            self._cap_q.put(None)  # stop forwarder
            stats = {
                "lines_forwarded": self._cap_lines_forwarded,
                "dropped": 0,  # populated from serial reader drops
                "duration_s": round(time.monotonic() - self._cap_start, 3),
                "seq_end": self._cap_seq,
            }
        self._send_to(self.sock, {"type": "capture_stats", "id": mid,
                                  "ok": True, **stats})

    def _do_health(self, mid):
        self._send_to(self.sock, {
            "type": "health_ok", "id": mid,
            "port": self.port_name,
            "port_open": self.ser.is_open,
            "baud": BAUD,
            "probe_serial": self.probe_serial,
            "openocd_available": os.path.isfile(OPENOCD),
            "uptime_s": round(time.monotonic() - self.start_time, 1),
            "last_activity_s": round(time.monotonic() - self.last_activity, 1),
            "capturing": (self.mode == "capture"),
            "dropped_total": self.dropped_total,
        })

    def _do_ping(self, mid, msg):
        self._send_to(self.sock, {
            "type": "pong", "id": mid,
            "ts_orig_ns": msg.get("ts_ns", 0),
            "ts_recv_ns": time.monotonic_ns(),
        })

    # ---- TCP write helpers ----

    def _send_json(self, obj):
        self._send_to(self.sock, obj)

    def _send_to(self, sock, obj):
        data = (json.dumps(obj) + "\n").encode()
        with self._lock:
            try:
                sock.sendall(data)
            except (ConnectionError, OSError):
                pass  # client gone

    def _reply_error(self, mid, code, msg):
        self._send_to(self.sock, {"type": "error", "id": mid,
                                  "code": code, "msg": msg})

    # ---- Main loop ----

    def serve_forever(self):
        # Start serial reader thread
        reader = threading.Thread(target=self.serial_reader_loop, daemon=True)
        reader.start()

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.listen_host, self.listen_port))
        srv.listen(1)
        print(f"[board-server] listening on {self.listen_host}:{self.listen_port} "
              f"port={self.port_name} probe={self.probe_serial}")
        while True:
            conn, addr = srv.accept()
            print(f"[board-server] client {addr} connected")
            self.handle_client(conn, addr)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="E80 board relay server")
    ap.add_argument("--port", required=True, help="serial device, e.g. /dev/ttyUSB3")
    ap.add_argument("--probe", required=True, help="SWD probe CMSIS-DAP serial")
    ap.add_argument("--listen", default="0.0.0.0:8685", help="listen address:port")
    args = ap.parse_args()
    BoardServer(args.port, args.probe, args.listen).serve_forever()
```

---

## 5. Board Client Design (Coordinator Side)

The `BoardClient` class is a drop-in replacement for the serial objects
that `e80_sweep_full.py` and `e80_campaign.py` use. It exposes the same
method names, so the existing code changes minimally.

```python
import json, queue, socket, threading, time

class BoardClient:
    """TCP client for a remote BoardServer. Same API surface as the
    serial helpers in e80_sweep_full.py (cmd, drain_lines, readline, write,
    reset_input_buffer, swd_reset)."""

    def __init__(self, host, port=8685):
        self.host = host
        self.port = port
        self._sock = socket.create_connection((host, port), timeout=10)
        self._sock.settimeout(None)  # blocking, read via reader thread
        self._buf = ""
        self._pending = {}            # id → dict(result, event)
        self._cap_q = queue.Queue()   # board_line messages during capture
        self._seq = 0
        self._lock = threading.Lock()
        self._cap_active = False
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    # ---- Background TCP reader ----

    def _reader_loop(self):
        buf = ""
        while True:
            try:
                data = self._sock.recv(8192)
            except (ConnectionError, OSError):
                self._handle_disconnect()
                break
            if not data:
                self._handle_disconnect()
                break
            buf += data.decode(errors="replace")
            while "\n" in buf:
                raw, buf = buf.split("\n", 1)
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                self._dispatch(msg)

    def _dispatch(self, msg):
        if msg.get("type") == "board_line":
            if self._cap_active:
                self._cap_q.put(msg)
            # else: late board_line after capture_stop — discard
        elif msg.get("id") in self._pending:
            entry = self._pending[msg["id"]]
            entry["result"] = msg
            entry["event"].set()

    def _handle_disconnect(self):
        # Wake up any blocking callers with an error
        for mid, entry in self._pending.items():
            entry["result"] = {"type": "error", "id": mid,
                                "code": "SERIAL_CLOSED",
                                "msg": "connection lost"}
            entry["event"].set()
        # Unblock capture readline
        self._cap_q.put(None)

    # ---- Send + wait for response ----

    def _send(self, msg, timeout=30.0):
        self._seq += 1
        mid = str(self._seq)
        msg["id"] = mid
        event = threading.Event()
        entry = {"result": None, "event": event}
        self._pending[mid] = entry
        data = (json.dumps(msg) + "\n").encode()
        with self._lock:
            self._sock.sendall(data)
        if not event.wait(timeout=timeout):
            self._pending.pop(mid, None)
            raise TimeoutError(f"no response to {msg['type']} in {timeout}s")
        result = self._pending.pop(mid, {}).get("result", {})
        if result.get("type") == "error":
            code = result.get("code", "INTERNAL")
            msg_text = result.get("msg", "unknown error")
            raise BoardServerError(f"[{code}] {msg_text}", code)
        return result

    # ---- Public API (matches existing serial helper signatures) ----

    def cmd(self, line, timeout=15.0):
        """Send a console command, wait for OK/ERR, return reply string.
        Raises BoardServerError on ERR or timeout."""
        resp = self._send({"type": "cmd", "line": line, "timeout": timeout},
                          timeout=timeout + 5)
        return resp.get("reply")

    def write(self, line, reply_timeout=3.0):
        """Send a raw command line, return the first non-empty reply.
        Used for START (reply may be immediate OK, but we just want
        the first line)."""
        resp = self._send({"type": "write", "line": line,
                           "timeout": reply_timeout},
                          timeout=reply_timeout + 5)
        return resp.get("reply")

    def drain_lines(self, seconds):
        """Drain all board output for N seconds, return list of lines."""
        resp = self._send({"type": "drain", "duration": seconds},
                          timeout=seconds + 15)
        return resp.get("lines", [])

    def reset_input_buffer(self):
        """Flush the serial input buffer on the board server."""
        self._send({"type": "flush"}, timeout=10)

    # Alias: the existing code also calls rx.reset_input_buffer()
    flush = reset_input_buffer

    def stat(self):
        """Query STAT? and return the reply string (unparsed)."""
        return self.cmd("STAT?", timeout=10.0)

    def swd_reset(self):
        """SWD-reset the board via openocd on the board server."""
        resp = self._send({"type": "swd_reset"}, timeout=50)
        return True

    # ---- Capture streaming API ----

    def capture_start(self):
        """Enter streaming mode. Board output will arrive as board_line
        messages accessible via readline()."""
        self._cap_q = queue.Queue()
        self._cap_active = True
        self._send({"type": "capture_start"}, timeout=10)

    def readline(self, timeout=3.0):
        """In capture mode: return the next board output line.
        Returns None on timeout (no data within `timeout` seconds)."""
        try:
            msg = self._cap_q.get(timeout=timeout)
            if msg is None:
                return None  # disconnect sentinel
            return msg.get("line")
        except queue.Empty:
            return None

    def capture_stop(self):
        """Exit streaming mode. Returns capture stats dict."""
        self._cap_active = False
        # Drain any remaining board_lines from queue
        while True:
            try:
                self._cap_q.get_nowait()
            except queue.Empty:
                break
        resp = self._send({"type": "capture_stop"}, timeout=10)
        return resp

    def health(self):
        """Get board server health."""
        return self._send({"type": "health"}, timeout=10)

    def ping(self):
        """Measure round-trip latency to the board server."""
        t0 = time.monotonic_ns()
        resp = self._send({"type": "ping", "ts_ns": t0}, timeout=5)
        t1 = time.monotonic_ns()
        rtt_ms = (t1 - t0) / 1e6
        return {"rtt_ms": rtt_ms, "server_ts_ns": resp.get("ts_recv_ns", 0)}

    def close(self):
        try:
            self._send({"type": "quit"}, timeout=5)
        except Exception:
            pass
        self._sock.close()


class BoardServerError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code
```

---

## 6. Distributed arm_and_stream / sprt_run

### 6.1 arm_and_stream (fire-and-forget burst)

The existing pattern: flush RX, write START to TX, drain TX lines for
the burst duration, drain RX lines after.

```python
def arm_and_stream(tx, rx, cfg, npkts, toa=None, wait_extra=8):
    """tx, rx are BoardClient objects. 1:1 mapping with existing code."""
    mod = cfg["mod"]
    if toa is None:
        if mod == "lora":
            toa = lora_airtime_s(cfg["sf"], cfg["bw"], cfg["plen"])
        else:
            toa = flrc_airtime_s(cfg["br"], cfg["plen"])
    wait_s = npkts * (toa + cfg["gap"] / 1e6) + wait_extra

    rx.reset_input_buffer()                      # was: rx.reset_input_buffer()
    start_reply = tx.write(                      # was: tx.write(...) + readline(tx)
        f"START N={npkts} LEN={cfg['plen']} GAP={cfg['gap']}")
    tx_lines = tx.drain_lines(wait_s)             # was: drain_lines(tx, wait_s)
    rx_lines = rx.drain_lines(5)                  # was: drain_lines(rx, 5)

    return {
        "start_reply": start_reply,
        "tx_lines": tx_lines,
        "rx_lines": rx_lines,
        "toa": toa,
        "wait_s": wait_s,
    }
```

**Changes from existing code:** Only the method call syntax (`tx.write()`
instead of `tx.write(bytes)` + `readline(tx)`). The `drain_lines()` method
now sends a `drain` request to the board server instead of reading
the local serial port.

### 6.2 sprt_run (real-time streaming with early-stop)

The existing pattern: configure radio on both boards, arm RX (capture
mode), write START to TX, read RX PKT lines one by one with SPRT
decision after each, optionally STOP early.

```python
def sprt_run(cfg, tx, rx, session_id, cfg_idx, policy=None, stop_fn=None):
    """tx, rx are BoardClient objects. SPRT early-stop burst.
    Key difference: rx.readline() reads from the TCP capture stream."""
    p = policy or SPRT
    n_cap = p["n_cap"]
    n_min = p["n_min"]

    # --- Radio config (identical to existing code) ---
    mod = cfg["mod"]
    m = (f"MOD LORA {cfg['sf']} {cfg['bw']}"
         if mod == "lora"
         else f"MOD FLRC {cfg['br']} {cfg['pa']}")
    for s in (rx, tx):
        s.cmd(m)
    if mod == "lora":
        rx.cmd(f"PA {cfg['pa']}")
        tx.cmd(f"PA {cfg['pa']}")
    rx.cmd(f"FREQ {cfg['freq']}")
    tx.cmd(f"FREQ {cfg['freq']}")
    rx.cmd("ROLE RX")
    tx.cmd("ROLE TX")
    tx.cmd(f"SESSION {session_id}")
    rx.cmd(f"SESSION {session_id}")
    tx.cmd(f"CONFIG {cfg_idx} 1")
    rx.cmd(f"CONFIG {cfg_idx} 1")

    if not (BAND_MIN_HZ <= cfg["freq"] <= BAND_MAX_HZ):
        for s in (rx, tx):
            s.cmd(f"BAND OVERRIDE {BAND_OVERRIDE_PIN}")

    r = tx.cmd("ARM TX")
    if not r or not r.startswith("OK ARMED"):
        return SprtResult("DEAD", n_cap, n_cap)

    # --- Real-time streaming capture ---
    # NEW: use capture_start/readline instead of reset_input_buffer/readline loop
    rx.reset_input_buffer()
    rx.capture_start()                           # server enters streaming mode

    # Send START to TX (non-blocking reply — just confirm board accepted)
    tx.write(f"START N={n_cap} LEN={cfg['plen']} GAP={cfg['gap']}")

    k = 0
    n = 0
    if mod == "lora":
        toa_max = lora_airtime_s(12, 125, cfg["plen"])
    else:
        toa_max = flrc_airtime_s(260, cfg["plen"])
    deadline = time.monotonic() + n_cap * (toa_max + cfg["gap"] / 1e6) + 10

    while n < n_cap and time.monotonic() < deadline:
        # This reads from the TCP board_line stream, not the serial port.
        # Latency: ~1ms per line on LAN, ~5-20ms on Netbird VPN.
        # At FLRC-650 (10ms gap), this keeps up easily.
        line = rx.readline(timeout=3.0)
        if line is None:
            break
        pkt = parse_pkt(line)
        if pkt is None or pkt["config"] != cfg_idx:
            continue
        n += 1
        if pkt["bit_err"] > 0:
            k += 1
        if n >= n_min:
            res = sprt_decide(k, n, p)
            if res.verdict in ("CLEAN", "DEAD"):
                if stop_fn:
                    stop_fn(tx)     # tx.cmd("STOP")
                rx.capture_stop()
                return res

    rx.capture_stop()
    res = sprt_decide(k, n, p)
    return res
```

**Changes from existing code:**
- `rx.reset_input_buffer()` → same method name (delegates to `flush` on server)
- `sw.readline(rx, timeout=3.0)` → `rx.readline(timeout=3.0)` (reads from TCP stream)
- Before streaming: `rx.capture_start()` tells the server to forward board output
- After streaming: `rx.capture_stop()` tells the server to stop forwarding
- Everything else (cmd, arm, SPRT logic) is identical

### 6.3 run_config (full sweep config)

```python
def run_config(idx, cfg, tx, rx, session_id, npkts=NPKTS):
    """tx, rx are BoardClient objects. Full per-config sequence."""
    mod = cfg["mod"]
    if cfg["plen"] > LEN_CAP.get(mod, 255):
        return { ... invalid config, same as existing ... }

    # SWD reset both boards (now via remote board servers)
    tx.swd_reset()                                # was: swd_reset(PROBE_TX)
    rx.swd_reset()                                # was: swd_reset(PROBE_RX)
    t_cfg_start = time.monotonic()

    if not ensure_alive(tx) or not ensure_alive(rx):
        raise RuntimeError("board unresponsive after retries")
    # ensure_alive uses tx.cmd("ID?") and checks for "E80BENCH" — works as-is

    # Session/config tagging
    tx.cmd(f"SESSION {session_id}")
    rx.cmd(f"SESSION {session_id}")
    tx.cmd(f"CONFIG {idx} 1")
    rx.cmd(f"CONFIG {idx} 1")

    # Band override for 2.4 GHz
    if not (BAND_MIN_HZ <= cfg["freq"] <= BAND_MAX_HZ):
        for s in (rx, tx):
            s.cmd(f"BAND OVERRIDE {BAND_OVERRIDE_PIN}")

    # Radio config
    m = (f"MOD LORA {cfg['sf']} {cfg['bw']}"
         if mod == "lora"
         else f"MOD FLRC {cfg['br']} {cfg['pa']}")
    for s in (rx, tx):
        s.cmd(m)
    if mod == "lora":
        rx.cmd(f"PA {cfg['pa']}")
        tx.cmd(f"PA {cfg['pa']}")
    rx.cmd(f"FREQ {cfg['freq']}")
    tx.cmd(f"FREQ {cfg['freq']}")

    rx.cmd("ROLE RX")
    tx.cmd("ROLE TX")
    tx.cmd("ARM TX")

    # Burst (reuse arm_and_stream)
    burst = arm_and_stream(tx, rx, cfg, npkts)
    # ... parse tx_lines, rx_lines, STAT — same as existing ...
```

The `ensure_alive` function also needs adaptation:

```python
def ensure_alive(board_client):
    """If board unresponsive, SWD-reset it (up to 2 retries)."""
    for attempt in range(3):
        try:
            r = board_client.cmd("ID?")
            if r and "E80BENCH" in r:
                return True
        except BoardServerError:
            pass
        print(f"    board unresponsive (attempt {attempt+1}), SWD reset")
        board_client.swd_reset()
        time.sleep(1.0)
    return False
```

---

## 7. Real-time Streaming Performance Analysis

### 7.1 Can TCP keep up with 2 Mbaud serial?

The board serial runs at 2 Mbaud (250 KB/s). Each PKT line is ~100-150
ASCII bytes. At the fastest burst rate (FLRC-2600, 64B payload):

| Parameter | Value |
|-----------|-------|
| Airtime per packet | ~0.5 ms |
| Gap per packet | 10 ms (firmware floor) |
| PKT line size | ~120 bytes |
| Lines per second | ~95 (1 per 10.5ms) |
| Data rate to TCP | ~11 KB/s |
| TCP on LAN (1ms RTT) | easily handles |
| TCP via Netbird | easily handles (if RTT < 10ms) |

At the slowest rate (LoRa SF12, 16B payload):

| Parameter | Value |
|-----------|-------|
| Airtime per packet | ~990 ms |
| Gap per packet | ~15 ms |
| Lines per second | ~1 (1 per ~1s) |

**Conclusion:** TCP bandwidth is never the bottleneck. The concern is
**latency jitter** — if the TCP write blocks for >10ms during a
FLRC-2600 burst, the serial reader thread's queue fills up. The bounded
queue (8192 entries × 120 bytes = ~1MB) provides ~75 seconds of
buffering headroom, which is far more than any realistic network jitter.

### 7.2 Serial reader thread never blocks

The critical design invariant: **the serial reader thread does nothing
except read serial and push to a queue.** It never writes to TCP. It
never runs openocd subprocesses. It never parses JSON. If the capture
queue is full, it drops the oldest entry (preferring newer data) and
increments the dropped counter — but it never blocks.

### 7.3 SWD reset during capture

SWD reset takes 2-5 seconds (openocd subprocess). During this time, the
serial reader must continue running (the board reboots and emits boot
banner lines). Since SWD reset runs in the client handler thread and
serial reader is a separate thread, they don't interfere. The boot
banner lines are handled normally (forwarded as `board_line` messages
during capture, or discarded in command mode if no prefix matches).

---

## 8. Clock Synchronization

### 8.1 NTP is sufficient for current use cases

The coordinator's timing concerns are:
1. **Per-config wall-clock**: `cfg_t_start` / `cfg_t_end` ISO timestamps
   (second granularity). NTP ±10ms is more than adequate.
2. **Burst duration**: measured with `time.monotonic()` on the
   coordinator — no cross-machine timing needed.
3. **T0 schedule** (e80_bench_ctl.py wall-clock schedule): second
   granularity, NTP is fine.

### 8.2 Board-local timestamps (`ts_ms` in PKT lines)

Each PKT line includes `ts_ms` — a board-local millisecond counter
(firmware SysTick). These timestamps are relative to board boot and
are NOT comparable across boards. They are used for intra-burst
timing analysis (packet arrival spacing) only. No cross-machine sync
needed.

### 8.3 Optional handshake timestamp for latency measurement

The `ping` message provides round-trip time and server-side receive
timestamp. The coordinator can call `ping()` on both servers before
a burst to:
- Log the network latency to each board server for this test run
- Verify both servers are reachable and responsive
- Estimate clock offset: if `server_ts_ns - client_ts_ns` differs
  significantly between the two servers, they're out of NTP sync

This is for logging/validation only — not used for timing the burst.

### 8.4 When NTP might not be sufficient

If future work requires correlating TX-side and RX-side packet timing
at sub-ms precision (e.g., RSSI-vs-time-of-arrival analysis), NTP won't
cut it. Options:
- **PTP (IEEE 1588)**: sub-microsecond on LAN, needs ptp4l/hwstamp
- **GPS PPS pulse**: both boards share a GPS-PPS — but the boards
  don't have a PPS input.
- **Firmware modification**: TX board emits a marker packet with its
  `ts_ms`, RX board records its own `ts_ms` when it received it.
  Coordinator computes offset = rx_ts_ms - tx_ts_ms. Simple but
  requires firmware support.

For now: **NTP + `ping()` latency logging. Document this as a
known limitation.**

---

## 9. Error Handling & Recovery

### 9.1 Board server dies mid-test

**Detection:** TCP connection breaks → BoardClient's reader thread
gets EOF → injects error responses into all pending requests →
`readline()` in capture loop returns `None`.

**Recovery (sprt_run):**

```python
while n < n_cap and time.monotonic() < deadline:
    line = rx.readline(timeout=3.0)
    if line is None:
        break  # either timeout (normal) or connection lost (error)
    # ... SPRT logic ...
```

If the RX board server dies, `readline()` returns `None` (timeout) or
raises `BoardServerError(SERIAL_CLOSED)`. The coordinator should:
1. Attempt to send STOP to the TX board server (if alive)
2. Log partial results (k errors in n packets so far)
3. Record the config as "INTERRUPTED" (not a valid SPRT verdict)
4. Attempt to reconnect to the dead board server
5. If reconnection fails within 30s, abort the campaign stop

**Recovery (arm_and_stream):**

```python
tx_lines = tx.drain_lines(wait_s)  # raises if TX server died
rx_lines = rx.drain_lines(5)       # raises if RX server died
```

Wrap in try/except, record partial results, abort config.

### 9.2 Board becomes unresponsive (serial timeout)

A single `cmd()` call times out → `BoardServerError(BOARD_TIMEOUT)`.
The `ensure_alive()` function already handles this: retries 2× with
SWD reset. With BoardClient, this works as-is — just call
`board_client.swd_reset()` and retry.

### 9.3 Serial buffer overflow on board server

If the capture queue overflows (network too slow), the board server
drops old packets and increments `dropped_count`. This is returned in
the `capture_stop` response as `"dropped": N`. The coordinator logs
this and the campaign report notes the data loss for affected configs.

**Detection:** `seq` gaps in `board_line` messages. The coordinator
can check for monotonic `seq` and log gaps. However, since the drop
happens before the message enters TCP, the coordinator won't see a
missing seq — it'll see a discontinuity. The `capture_stats` result
is the authoritative source: if `lines_forwarded < expected`, data
was lost.

### 9.4 Both machines lose network connectivity

TCP connections on both clients break simultaneously. All pending
requests get SERIAL_CLOSED errors. Coordinator logs partial data and
aborts. Campaign state DB (CampaignState JSON) preserves verdicts
already recorded — the next run will carry-forward.

### 9.5 Coordinator crash

The coordinator crashes mid-test. Board servers detect TCP disconnect
→ reset to idle (stop capture, clear pending). Serial ports stay open.
On coordinator restart, it reconnects, runs `health()` on both
servers, sees `capturing: false`, and resumes from the last committed
CampaignState checkpoint.

### 9.6 Board server crash (process death)

If the board server process itself dies (OOM, segfault), the serial
port closes. On restart (systemd auto-restart), the server reopens
the serial port. The coordinator detects disconnect, waits for
reconnection (retry every 2s for 30s), then calls `health()` to verify
board responsiveness before resuming.

---

## 10. Deployment Notes

### 10.1 T470 + DQ05 layout

| Machine | Role | Board | Serial Port | SWD Probe |
|---------|------|-------|-------------|-----------|
| T470 | TX board server + coordinator | TX (Board A) | `/dev/ttyUSB0` | `148757200D2D1425` |
| DQ05 | RX board server | RX (Board B) | `/dev/ttyUSB0` | `203584200D2D0D42` |

**Network:** Direct Ethernet cable (1 Gbps, ~0.2ms RTT) or Netbird
mesh VPN (variable latency, verify < 10ms with `ping()` before burst).

### 10.2 DQ05 openocd

DQ05 currently has no openocd installed. Install before field use:

```bash
sudo apt install openocd
# Verify:
which openocd && openocd --version
```

The board server checks `os.path.isfile("/usr/bin/openocd")` at startup
and reports `openocd_available: false` in `health()` if missing. SWD
reset calls will return `SWD_UNAVAILABLE` errors. All other board
server functionality (serial commands, capture) works without openocd.

If openocd is absent on DQ05 and the RX board needs SWD reset,
options:
1. Install openocd on DQ05 (recommended)
2. Move the RX board's SWD probe to T470 (T470 controls both probes,
   DQ05 only handles serial)
3. Use `ARM TX` + `STOP` cycling instead of SWD reset (firmware-only
   reset, less reliable for clearing radio state — not recommended
   per `maybe_reset` findings)

### 10.3 systemd service

One `.service` file per board server:

```ini
# /etc/systemd/system/e80-board-tx.service
[Unit]
Description=E80 Board Server (TX)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/e80_board_server.py --port /dev/ttyUSB0 --probe 148757200D2D1425 --listen 0.0.0.0:8685
Restart=on-failure
RestartSec=2
User=c03rad0r

[Install]
WantedBy=multi-user.target
```

### 10.4 Firewall

Open TCP 8685 on both machines (or restrict to the other machine's
IP for security):

```bash
# On T470 (allow DQ05):
sudo ufw allow from <dq05_ip> to any port 8685 proto tcp

# On DQ05 (allow T470):
sudo ufw allow from <t470_ip> to any port 8685 proto tcp
```

---

## 11. Migration Path

### Phase 1: BoardClient wrapper (no server needed yet)

Create `e80_board_client.py` with the `BoardClient` class. Add a
`LocalBoardServer` shim that wraps `serial.Serial` directly (no TCP)
and exposes the same interface. This validates the API surface without
networking.

```python
class LocalBoardClient:
    """Drop-in BoardClient that wraps a local serial port directly.
    No TCP needed. Same API as BoardClient for local testing."""
    def __init__(self, port, probe_serial=None):
        self.ser = serial.Serial(port, BAUD, timeout=0.1)
        self.probe_serial = probe_serial
        # ... same methods, operate on self.ser directly ...
```

Modify `e80_sweep_full.py` and `e80_campaign.py` to accept either
`serial.Serial` objects or `BoardClient`/`LocalBoardClient` objects
(duck typing — same method names). Run existing tests unchanged via
`LocalBoardClient`.

### Phase 2: BoardServer daemon

Implement the full `BoardServer` class. Test with two board servers
on the same machine (two ports) + coordinator on localhost.

### Phase 3: Distributed deployment

Deploy board servers on T470 and DQ05. Run coordinator from either
machine. Verify with a probe campaign (`--mode probe`).

### Phase 4: Integration with campaign controller

Update `e80_campaign.py` `main()` to accept `--tx-host` / `--rx-host`
arguments (default: localhost) and create `BoardClient` objects instead
of calling `open_boards()`.

```python
# In e80_campaign.py main():
if args.tx_host:
    tx = BoardClient(args.tx_host, args.tx_port)
    rx = BoardClient(args.rx_host, args.rx_port)
else:
    # Legacy: local serial
    tx_port, rx_port, tx, rx = sw.open_boards()
    tx = LocalBoardClient(tx_port, PROBE_TX)
    rx = LocalBoardClient(rx_port, PROBE_RX)
```

---

## 12. Wire Protocol Examples

### 12.1 Command + reply

```
→ {"type":"cmd","id":"1","line":"ID?","prefixes":["OK","ERR","ID"],"timeout":10}
← {"type":"reply","id":"1","ok":true,"reply":"ID E80BENCH-0561b29 serial=0x12345678"}
```

### 12.2 Error response

```
→ {"type":"cmd","id":"2","line":"FREQ 999000000","timeout":10}
← {"type":"error","id":"2","code":"BOARD_ERR","msg":"ERR freq out of range"}
```

### 12.3 SWD reset

```
→ {"type":"swd_reset","id":"3"}
← {"type":"swd_done","id":"3","ok":true,"duration_s":4.2}
```

### 12.4 Capture stream (real-time PKT capture)

```
→ {"type":"capture_start","id":"4"}
← {"type":"reply","id":"4","ok":true,"reply":"capturing"}
← {"type":"board_line","line":"PKT,1,3,1,0,1280903,-42,7,1,0,0,868000000,...,0x1A2B","ts_ns":1724428800123456789,"seq":1}
← {"type":"board_line","line":"PKT,1,3,1,1,1280913,-43,7,1,0,...,0x2B3C","ts_ns":1724428800133556789,"seq":2}
← {"type":"board_line","line":"PKT,1,3,1,2,1280923,-41,7,1,0,...,0x3C4D","ts_ns":1724428800143656789,"seq":3}
→ {"type":"capture_stop","id":"5"}
← {"type":"capture_stats","id":"5","ok":true,"lines_forwarded":3,"dropped":0,"duration_s":0.031,"seq_end":3}
```

### 12.5 Drain (bulk collect after burst)

```
→ {"type":"drain","id":"6","duration":15.0}
← {"type":"drain_result","id":"6","ok":true,"lines":["OK START N=50 LEN=64 GAP=10000","TX DONE sent=50 sent_ok=50",""]}
```

### 12.6 Health check

```
→ {"type":"health","id":"7"}
← {"type":"health_ok","id":"7","port":"/dev/ttyUSB0","port_open":true,"baud":2000000,"probe_serial":"148757200D2D1425","openocd_available":true,"uptime_s":3600.5,"last_activity_s":0.2,"capturing":false,"dropped_total":0}
```

### 12.7 Full burst sequence (coordinator perspective)

```
# Setup: configure both boards
TX → {"type":"cmd","id":"10","line":"MOD LORA 7 125"}
TX ← {"type":"reply","id":"10","ok":true,"reply":"OK MOD LORA 7 125"}
RX → {"type":"cmd","id":"11","line":"MOD LORA 7 125"}
RX ← {"type":"reply","id":"11","ok":true,"reply":"OK MOD LORA 7 125"}
TX → {"type":"cmd","id":"12","line":"FREQ 868000000"}
TX ← {"type":"reply","id":"12","ok":true,"reply":"OK FREQ 868000000"}
RX → {"type":"cmd","id":"13","line":"FREQ 868000000"}
RX ← {"type":"reply","id":"13","ok":true,"reply":"OK FREQ 868000000"}
TX → {"type":"cmd","id":"14","line":"ROLE TX"}
TX ← {"type":"reply","id":"14","ok":true,"reply":"OK ROLE TX"}
RX → {"type":"cmd","id":"15","line":"ROLE RX"}
RX ← {"type":"reply","id":"15","ok":true,"reply":"OK ROLE RX"}
TX → {"type":"cmd","id":"16","line":"ARM TX"}
TX ← {"type":"reply","id":"16","ok":true,"reply":"OK ARMED"}

# Burst: arm RX capture, start TX
RX → {"type":"flush","id":"17"}
RX ← {"type":"reply","id":"17","ok":true,"reply":null}
RX → {"type":"capture_start","id":"18"}
RX ← {"type":"reply","id":"18","ok":true,"reply":"capturing"}
TX → {"type":"write","id":"19","line":"START N=50 LEN=64 GAP=10000","timeout":3}
TX ← {"type":"reply","id":"19","ok":true,"reply":"OK START N=50 LEN=64 GAP=10000"}

# Stream: RX board outputs PKT lines, forwarded in real-time
RX ← {"type":"board_line","line":"PKT,1,0,1,0,...","ts_ns":...,"seq":1}
RX ← {"type":"board_line","line":"PKT,1,0,1,1,...","ts_ns":...,"seq":2}
...  (coordinator reads these via rx.readline(), runs SPRT)
RX ← {"type":"board_line","line":"PKT,1,0,1,49,...","ts_ns":...,"seq":50}

# Stop capture
RX → {"type":"capture_stop","id":"20"}
RX ← {"type":"capture_stats","id":"20","ok":true,"lines_forwarded":50,"dropped":0,"duration_s":0.52,"seq_end":50}

# TX post-burst drain
TX → {"type":"drain","id":"21","duration":2}
TX ← {"type":"drain_result","id":"21","ok":true,"lines":["TX DONE sent=50 sent_ok=50"]}

# RX stats
RX → {"type":"cmd","id":"22","line":"STAT?","prefixes":["STAT","OK"]}
RX ← {"type":"reply","id":"22","ok":true,"reply":"STAT role=RX rx=50 crc_err=0 per_x1e6=0 per_ci_x1e6=[0,735] ..."}
```

---

## 13. File Layout (proposed)

```
firmware/e80-stm32-bench/tools/
├── e80_board_relay.md      ← this document
├── e80_board_server.py     ← BoardServer daemon (§4)
├── e80_board_client.py     ← BoardClient + LocalBoardClient (§5)
├── e80_bench_ctl.py        ← existing (minimal changes: BoardClient support)
├── e80_sweep_full.py       ← existing (add --tx-host / --rx-host args)
└── e80_campaign.py         ← existing (add --tx-host / --rx-host args)
```

### Changes to existing files

**e80_sweep_full.py:**
- Add `--tx-host`, `--rx-host` (default: None → local serial)
- In `main()` / `open_boards()`: if tx_host set, create `BoardClient(tx_host)`;
  else use existing `serial.Serial` path
- `arm_and_stream()`: change `tx.write(bytes)` → `tx.write(str)`,
  `drain_lines(ser, s)` → `ser.drain_lines(s)`
  (works on both BoardClient and serial.Serial — add a helper or monkey-patch
  serial.Serial with a `drain_lines` method, or just check duck-type)
- `swd_reset()`: becomes a no-op local function that calls
  `board_client.swd_reset()` — or remove and call directly on client objects

**e80_campaign.py:**
- In `main()`: same tx_host/rx_host argument pattern
- `sprt_run()`: change `sw.cmd(s, ...)` → `s.cmd(...)`,
  `sw.readline(rx, ...)` → `rx.readline(...)`,
  add `rx.capture_start()` / `rx.capture_stop()` around the streaming loop

---

## 14. Known Limitations & Future Work

1. **Single connection per server.** No concurrent monitoring while a
   test runs. Future: add a read-only `/health` HTTP endpoint on a
   different port for monitoring scripts.

2. **No authentication.** The TCP port is unencrypted and unauthenticated.
   Fine for a direct Ethernet cable or trusted Netbird network. For
   hostile networks: add TLS + shared-secret token in a header field.

3. **No binary streaming.** All data is JSON-encoded ASCII. For very
   high-speed modes (FLRC-2600 with 511B payloads at 0 gap), the JSON
   overhead (~20 bytes per `board_line` wrapper) adds ~16 KB/s —
   negligible. If firmware ever emits binary packet dumps, switch to
   length-prefixed framing with a binary body mode.

4. **Clock sync at second granularity.** NTP within ±10ms. Sub-ms
   cross-board timing requires PTP or firmware marker support (§8.4).

5. **No board auto-discovery.** The operator manually configures which
   machine is TX and which is RX. The `identify_boards()` radio handshake
   works only when both boards are on the same server. Future: coordinate
   a cross-server radio handshake (TX server sends 2 packets at known
   freq, RX server reports if it received them).

6. **DQ05 needs openocd.** Without openocd, SWD reset on DQ05's board
   isn't possible. The board server handles this gracefully (health reports
   `openocd_available: false`, `swd_reset` returns `SWD_UNAVAILABLE`), but
   the coordinator's reset logic needs a fallback path or the operator
   must install openocd before field deployment.
