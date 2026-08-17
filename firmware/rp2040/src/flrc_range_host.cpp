// flrc_range_host.cpp — host-driven range bench node (FW-1 scaffold stub).
//
// Full spec: docs/PLAN-host-driven-bench.md (REV-2 binding).
//   §1 Console Protocol v1 — single-line, case-insensitive, \r\n-terminated,
//   accepted on BOTH USB CDC (Serial) and UART (Serial1 -> ESP32 bridge);
//   every reply echoed on both.
//
// FW-1 scope (stub only):
//   - dual-serial banner:  "ID range-host v1 role=NONE tx_inhibited=1"
//   - ID? reply:           same banner line (fw=<hash> + role wiring land in FW-6)
//   - anything else:       "ERR UNKNOWN <echoed line>"
//
// REV-2 M2 rules baked in:
//   - Serial1 (GP12 RX / GP13 TX) is THE protocol port (ESP32 bridge side).
//   - CDC output gated on the Serial connected flag; NEVER call Serial.flush().
//
// Later tasks replace the guts (FW-2 parser, FW-5a/b radio, FW-6 dispatch,
// FW-7/8 engines, FW-9 heartbeat/STAT?) — keep this file the loop owner.

#include <Arduino.h>
#include <strings.h>

#ifndef SERIAL_BAUD
#define SERIAL_BAUD 115200
#endif

static const char kBANNER[] = "ID range-host v1 role=NONE tx_inhibited=1";

// Protocol port wiring (Pico GP12/13 <-> bridge GPIO3/2, see plan DOC-1).
static const int8_t kProtoRxPin = 12;  // Pico GP12 <- bridge GPIO3
static const int8_t kProtoTxPin = 13;  // Pico GP13 -> bridge GPIO2

struct LineBuf {
  char b[128];
  size_t n;
  bool overflow;
};

static LineBuf bufCdc;
static LineBuf bufProto;

static void replyBoth(const char *line) {
  Serial1.println(line);              // protocol port: always
  if (Serial) Serial.println(line);   // CDC: gated on connected flag (M2)
}

static void handleLine(const char *line) {
  if (line[0] == '\0') return;  // empty line: ignore
  // Case-insensitive first-token match (§1). Full tokenizer lands in FW-2.
  if (strncasecmp(line, "ID?", 3) == 0 && (line[3] == '\0' || line[3] == ' ')) {
    replyBoth(kBANNER);
    return;
  }
  char out[160];
  snprintf(out, sizeof(out), "ERR UNKNOWN %s", line);
  replyBoth(out);
}

// Non-blocking line pump: accepts '\n' or '\r' as terminator, strips the
// trailing CR of CRLF pairs, caps echo at the buffer size.
static void pumpLine(Stream &s, LineBuf &lb) {
  while (s.available() > 0) {
    char c = (char)s.read();
    if (c == '\n' || c == '\r') {
      if (c == '\n' && lb.n > 0 && lb.b[lb.n - 1] == '\r') lb.n--;  // CRLF
      if (c == '\r' && s.peek() == '\n') continue;                  // CR of CRLF
      lb.b[lb.n] = '\0';
      handleLine(lb.b);
      lb.n = 0;
      lb.overflow = false;
    } else if (lb.n < sizeof(lb.b) - 1) {
      lb.b[lb.n++] = c;
    } else {
      lb.overflow = true;  // drop extra chars; truncated line still echoes
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);  // USB CDC (banner deferred to connect, M2)
  Serial1.setRX(kProtoRxPin);  // earlephilhower core: pin mapping via
  Serial1.setTX(kProtoTxPin);  // setRX/setTX, then begin(baud, config)
  Serial1.begin(SERIAL_BAUD, SERIAL_8N1);
  Serial1.println(kBANNER);  // protocol port: banner immediately
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  // CDC banner on first connect transition (output gating per M2).
  static bool cdcBannered = false;
  if (!cdcBannered && Serial) {
    Serial.println(kBANNER);
    cdcBannered = true;
  }

  pumpLine(Serial, bufCdc);
  pumpLine(Serial1, bufProto);

  // Slow activity blink until the HB heartbeat line arrives (FW-9, feeds
  // the ESP32-bridge 30 s silence watchdog — plan gotcha #1).
  digitalWrite(LED_BUILTIN, (millis() / 600) & 1);
}
