// flrc_range_host.cpp — host-driven range bench node (main TU / plan executor).
//
// Full spec: docs/PLAN-host-driven-bench.md (REV-2 binding).
//   §1 Console Protocol v1 — single-line, case-insensitive, \r\n-terminated,
//   accepted on BOTH USB CDC (Serial) and UART (Serial1 -> ESP32 bridge);
//   every reply echoed on both.
//
// FW-6 wiring: parse (FW-2) -> dispatch (bench_apply_cmd, pure TU) -> this
// file executes the returned plan against the FW-5a radio backend:
//   RH_PLAN_REINIT_FULL  -> bench_radio_reinit(cfg)  (band-aware when flagged)
//   RH_PLAN_START_BURST  -> burst engine (FW-7/8, not yet resident)
//   RH_PLAN_STOP         -> burst engine (FW-7/8, not yet resident)
// Replies are formatted by the pure dispatch TU (bench_format_reply) except
// STAT? (FW-9 formatter) which still falls back to ERR UNKNOWN.
//
// REV-2 M2 rules baked in:
//   - Serial1 (GP12 RX / GP13 TX) is THE protocol port (ESP32 bridge side).
//   - CDC output gated on the Serial connected flag; NEVER call Serial.flush().
//
// Later tasks grow the executor here (FW-7 TX engine, FW-8 RX engine, FW-9
// heartbeat/STAT?) — keep this file the loop owner.

#include <Arduino.h>
#include <strings.h>

#include "flrc_range_host_dispatch.h"
#include "flrc_range_host_radio.h"
#include "flrc_range_host_safety.h"
#include "lr2021_bw_codes.h"

#ifndef SERIAL_BAUD
#define SERIAL_BAUD 115200
#endif

/* Build id for the ID? reply. Injected per-build by CI (platformio
 * build_flags -DFW_HASH='"<git>"'); "dev" for local builds. */
#ifndef FW_HASH
#define FW_HASH "dev"
#endif

// Protocol port wiring (Pico GP12/13 <-> bridge GPIO3/2, see plan DOC-1).
static const int8_t kProtoRxPin = 12;  // Pico GP12 <- bridge GPIO3
static const int8_t kProtoTxPin = 13;  // Pico GP13 -> bridge GPIO2

/* Bench protocol state (FW-6 dispatch owns the transitions). */
static bench_state_t g_state;
static bool g_radio_ok = false;  /* cold-init result; reinit only when set */

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

/* Translate bench protocol state -> radio backend config (FW-5a). Pure
 * mapping; range validity is re-checked by bench_radio_cfg_valid(). */
static void state_to_cfg(const bench_state_t &st, bench_radio_cfg_t *cfg) {
  memset(cfg, 0, sizeof(*cfg));
  cfg->mod = st.mod;
  cfg->freq_hz = st.freq_hz;
  cfg->flrc_br_kbps = (uint16_t)(st.br_bps / 1000UL);  // 8 exact rates
  cfg->lora_sf = st.sf;
  cfg->lora_bw_code = (st.mod == BENCH_MOD_LORA)
                          ? lr2021_bw_hz_to_code(st.bw_hz)
                          : LR2021_BW_CODE_INVALID;
  cfg->lora_cr = 1;  // CR4/5 — matches the FW-4 airtime model
  cfg->dbm = st.dbm;
  cfg->pkt_len = (uint16_t)st.len_bytes;
  cfg->tx_timeout_ms = bench_safety_tx_timeout_ms(
      st.mod, st.sf, st.bw_hz, st.br_bps, cfg->pkt_len);
}

/* Execute a dispatch plan against the hardware backend. */
static void executePlan(const rh_plan_t &plan) {
  switch (plan.action) {
    case RH_PLAN_REINIT_FULL: {
      if (!g_radio_ok) return;  // config stored; radio cold-init failed
      bench_radio_cfg_t cfg;
      state_to_cfg(g_state, &cfg);
      if (bench_radio_cfg_valid(&cfg)) bench_radio_reinit(&cfg);
      break;
    }
    case RH_PLAN_START_BURST:
      // FW-7 (TX engine) / FW-8 (RX engine): arm burst from g_state, stamp
      // g_state.stats.t_start_us, drive the per-packet loop from loop().
      break;
    case RH_PLAN_STOP:
      // FW-7/FW-8: abort in-flight burst, stamp stats.t_stop_us. Stats are
      // already retained by the dispatch layer until the next START.
      break;
    case RH_PLAN_NONE:
    default:
      break;
  }
}

static void handleLine(const char *line) {
  if (line[0] == '\0') return;  // empty line: ignore

  rh_cmd_t cmd;
  rh_cmd_parse(line, &cmd);              // FW-2 (sets cmd.err on failure)
  rh_plan_t plan = bench_apply_cmd(&g_state, &cmd);  // FW-6 decision table

  char out[512];
  if (bench_format_reply(&g_state, &cmd, &plan, out, sizeof(out))) {
    replyBoth(out);
  } else {
    // No single-line reply yet (STAT? — FW-9 formatter).
    snprintf(out, sizeof(out), "ERR UNKNOWN %s", line);
    replyBoth(out);
  }

  if (plan.err == RH_CMD_OK) executePlan(plan);
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

  bench_state_init(&g_state, FW_HASH);  // §1 boot defaults, role=NONE

  // Radio cold bring-up (FW-5a). Runs before the banner so the protocol
  // port is alive either way; a missing chip only disables re-init exec.
  bench_radio_hardware_begin();
  bench_radio_cfg_t cfg;
  state_to_cfg(g_state, &cfg);
  g_radio_ok = bench_radio_cfg_valid(&cfg) && bench_radio_full_init(&cfg);

  char banner[96];
  bench_format_id(&g_state, banner, sizeof(banner));
  Serial1.println(banner);  // protocol port: banner immediately
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  // CDC banner on first connect transition (output gating per M2).
  static bool cdcBannered = false;
  static char cdcBanner[96] = {'\0'};
  if (cdcBanner[0] == '\0') bench_format_id(&g_state, cdcBanner, sizeof(cdcBanner));
  if (!cdcBannered && Serial) {
    Serial.println(cdcBanner);
    cdcBannered = true;
  }

  pumpLine(Serial, bufCdc);
  pumpLine(Serial1, bufProto);

  // Slow activity blink until the HB heartbeat line arrives (FW-9, feeds
  // the ESP32-bridge 30 s silence watchdog — plan gotcha #1).
  digitalWrite(LED_BUILTIN, (millis() / 600) & 1);
}
