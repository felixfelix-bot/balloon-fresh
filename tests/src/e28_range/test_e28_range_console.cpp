// TDD RED test: E28 ranging console core (ESP32-S3 + SX1282, LILYGO T3S3).
//
// The console core is host-testable: all radio hardware access is behind an
// e28_io_t seam (put / radioBegin / radioRange / radioRangingResult), so the
// same object code runs under pytest (with a fake io) and in the ESP32-S3
// firmware (with the SX1282 RadioLib ops). This test pins the command set,
// the indoor +10 dBm power cap, and the ranging state machine.
//
// RED phase: e28_range_console.h/.c do not exist yet -> fails to compile.
// GREEN phase: every CHECK below must (a) compile and (b) pass.
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

extern "C" {
#include "e28_range_console.h"
}

static int failures = 0;

#define CHECK(cond, msg) do { \
  if(!(cond)) { printf("FAIL: %s\n", msg); failures++; } \
} while(0)

// ---- fake io seam -------------------------------------------------------
static std::string out_buf;
static int fake_begin_ret;          // last radioBegin return
static int last_radio_begin;        // count of radioBegin() calls
static int last_radio_range_master; // count of radioRange(true, ...) calls
static int last_radio_range_slave;  // count of radioRange(false, ...) calls
static uint32_t last_range_addr;
static int fake_range_ret;          // last radioRange return
static float fake_ranging_result;   // last radioRangingResult return
static uint32_t fake_begin_calls = 0;

static void fake_put(const char* s) { out_buf += s; }

static int fake_radio_begin(void) {
  last_radio_begin++;
  fake_begin_calls++;
  return fake_begin_ret;
}
static int fake_radio_range(bool master, uint32_t addr) {
  last_range_addr = addr;
  if(master) last_radio_range_master++;
  else       last_radio_range_slave++;
  return fake_range_ret;
}
static float fake_radio_ranging_result(void) {
  return fake_ranging_result;
}

static e28_io_t make_io(void) {
  e28_io_t io;
  io.put = fake_put;
  io.radioBegin = fake_radio_begin;
  io.radioRange = fake_radio_range;
  io.radioRangingResult = fake_radio_ranging_result;
  return io;
}

static void reset_fakes(void) {
  out_buf.clear();
  last_radio_begin = 0;
  last_radio_range_master = 0;
  last_radio_range_slave = 0;
  last_range_addr = 0;
  fake_range_ret = 0;             // RADIOLIB_ERR_NONE
  fake_ranging_result = 4.5f;
  fake_begin_ret = 0;             // RADIOLIB_ERR_NONE
}

// helper: run feed_line against a fresh console bound to a fresh fake io
// (kept for symmetry with the firmware glue; not used by every test)

int main(void) {
  // ================= ID? =================
  reset_fakes();
  e28_io_t io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("ID?");
  CHECK(out_buf.find("E28-RANGE") != std::string::npos, "ID? must report board name");
  CHECK(out_buf.find("0123456") != std::string::npos, "ID? must report fw hash");

  // ================= default state / STAT? =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("role=idle") != std::string::npos, "default role idle");
  CHECK(out_buf.find("pa=10") != std::string::npos, "default pa = indoor cap (10)");
  CHECK(out_buf.find("addr=0xE80E2801") != std::string::npos, "default addr 0xE80E2801");
  CHECK(out_buf.find("bw=812") != std::string::npos, "default bw 812.5 kHz");
  CHECK(out_buf.find("last=none") != std::string::npos, "no ranging result yet");

  // ================= HELP / ? =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("HELP");
  CHECK(out_buf.find("ID?") != std::string::npos, "HELP lists ID?");
  CHECK(out_buf.find("RANGE") != std::string::npos, "HELP lists RANGE");
  CHECK(out_buf.find("RANGE-SLAVE") != std::string::npos, "HELP lists RANGE-SLAVE");
  CHECK(out_buf.find("RANGE?") != std::string::npos, "HELP lists RANGE?");
  CHECK(out_buf.find("FREQ") != std::string::npos, "HELP lists FREQ");
  CHECK(out_buf.find("SF") != std::string::npos, "HELP lists SF");
  CHECK(out_buf.find("BW") != std::string::npos, "HELP lists BW");
  CHECK(out_buf.find("PA") != std::string::npos, "HELP lists PA");
  CHECK(out_buf.find("ADDR") != std::string::npos, "HELP lists ADDR");

  // ================= PA indoor cap =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("PA 22");      // SX1282 can reach +22 but must be capped
  CHECK(out_buf.find("capped") != std::string::npos, "PA 22 must warn 'capped'");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("pa=10") != std::string::npos, "PA 22 is capped to 10");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("PA 8");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("pa=8") != std::string::npos, "PA 8 stays 8 (under cap)");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("PA -3");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("pa=-3") != std::string::npos, "negative PA allowed (SX1282 range -18..+13)");

  // PA below the SX1282 floor must be clamped, not wrapped past the cap
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("PA -200");   // would wrap to +56 if unchecked
  CHECK(out_buf.find("floor") != std::string::npos, "PA -200 rejected below SX1282 floor");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("pa=-18") != std::string::npos, "PA -200 clamped to -18, never wraps past cap");

  // non-numeric PA must be rejected, not coerced to 0
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("PA banana");
  CHECK(out_buf.find("ERR") != std::string::npos, "PA banana rejected (not coerced)");

  // ================= FREQ bounds =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("FREQ 2440000000");  // 2440 MHz
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("freq=2440") != std::string::npos, "FREQ 2440000000 -> 2440 MHz");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("FREQ 9999999999");  // out of band
  CHECK(out_buf.find("ERR") != std::string::npos, "out-of-band FREQ rejected");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("FREQ banana");
  CHECK(out_buf.find("ERR") != std::string::npos, "non-numeric FREQ rejected");

  // ================= SF bounds =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("SF 7");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("sf=7") != std::string::npos, "SF 7 accepted");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("SF 13");  // out of 5..12
  CHECK(out_buf.find("ERR") != std::string::npos, "SF 13 rejected");

  // ================= BW (812.5 kHz only) =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("BW 812.5");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("bw=812") != std::string::npos, "BW 812.5 accepted");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("BW 125");  // not the 812.5-only value
  CHECK(out_buf.find("ERR") != std::string::npos, "BW 125 rejected (812.5 kHz only)");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("BW 406.25");  // ranging-valid but not the 812.5-only value
  CHECK(out_buf.find("ERR") != std::string::npos, "BW 406.25 rejected (812.5 kHz only)");

  // ================= ADDR =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("ADDR 0xDEADBEEF");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("DEADBEEF") != std::string::npos, "ADDR 0xDEADBEEF stored");

  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("ADDR zzz");
  CHECK(out_buf.find("ERR") != std::string::npos, "non-numeric ADDR rejected");

  // ================= RANGE (master) -> DIST =================
  reset_fakes();
  io = make_io();
  fake_range_ret = 0;              // RADIOLIB_ERR_NONE
  fake_ranging_result = 12.75f;
  e28_range_init(&io, "0123456");
  e28_range_feed_line("RANGE");
  CHECK(last_radio_range_master == 1, "RANGE initiates one master ranging exchange");
  CHECK(last_range_addr == 0xE80E2801ul, "RANGE uses configured addr");
  CHECK(out_buf.find("DIST=12.75") != std::string::npos, "RANGE reports DIST in meters");

  // distance persisted -> RANGE?
  reset_fakes();
  io = make_io();
  fake_range_ret = 0;
  fake_ranging_result = 7.5f;
  e28_range_init(&io, "0123456");
  e28_range_feed_line("RANGE");
  e28_range_feed_line("RANGE?");
  CHECK(out_buf.find("DIST=7.50") != std::string::npos || out_buf.find("DIST=7.5") != std::string::npos,
        "RANGE? reports last distance");

  // ================= RANGE master timeout =================
  reset_fakes();
  io = make_io();
  fake_range_ret = -901;  // RADIOLIB_ERR_RANGING_TIMEOUT
  e28_range_init(&io, "0123456");
  e28_range_feed_line("RANGE");
  CHECK(out_buf.find("TIMEOUT") != std::string::npos, "ranging timeout reported as RANGE TIMEOUT");

  // ================= RANGE-SLAVE =================
  reset_fakes();
  io = make_io();
  fake_range_ret = 0;
  e28_range_init(&io, "0123456");
  e28_range_feed_line("RANGE-SLAVE");
  CHECK(last_radio_range_slave == 1, "RANGE-SLAVE runs one slave ranging exchange");
  CHECK(last_range_addr == 0xE80E2801ul, "RANGE-SLAVE uses configured addr");
  CHECK(out_buf.find("SLAVE OK") != std::string::npos, "RANGE-SLAVE reports SLAVE OK");

  // RANGE-SLAVE error path
  reset_fakes();
  io = make_io();
  fake_range_ret = -901;
  e28_range_init(&io, "0123456");
  e28_range_feed_line("RANGE-SLAVE");
  CHECK(out_buf.find("ERR") != std::string::npos, "RANGE-SLAVE error reported");

  // ================= config push after FREQ/SF/BW/PA calls radioBegin =====
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("FREQ 2460000000");
  CHECK(last_radio_begin >= 1, "FREQ pushes config via radioBegin");

  // ================= boot config push =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  CHECK(last_radio_begin >= 1, "init pushes power-on defaults to radio");

  // ================= tab-separated command =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("FREQ\t2440000000");
  e28_range_feed_line("STAT?");
  CHECK(out_buf.find("freq=2440") != std::string::npos, "tab-separated FREQ accepted");

  // ================= '?' alias =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("?");
  CHECK(out_buf.find("RANGE") != std::string::npos, "'?' lists commands (RANGE present)");

  // ================= unknown command =================
  reset_fakes();
  io = make_io();
  e28_range_init(&io, "0123456");
  e28_range_feed_line("BOGUS");
  CHECK(out_buf.find("ERR") != std::string::npos, "unknown command -> ERR");

  // ============ chip version decode (SX128x reg 0x01F0) ===================
  // The 17-byte raw burst capture may or may not carry a status byte before
  // the first data byte and/or interleaved with each data byte. The decoder
  // must find the ASCII "SX1" signature in whichever alignment holds it.
  // This is the exact failure that broke the first hardware run (2026-09-23):
  // the firmware was built for the "SX1282" SKU while the silicon reports
  // "SX1280", so RadioLib's findChip() returned RADIOLIB_ERR_CHIP_NOT_FOUND.
  {
    char ver[17];

    // (a) no status byte at all: version string starts at raw[0]
    uint8_t noStatus[17] = { 'S','X','1','2','8','0', 0, 0,0,0,0,0,0,0,0,0,0 };
    e28_decode_chip_version(noStatus, ver);
    CHECK(strcmp(ver, "SX1280") == 0, "decode: no-status layout -> SX1280");

    // (b) one leading status byte, then straight data
    uint8_t lead[17] = { 0xAA, 'S','X','1','2','8','0', 0,0,0,0,0,0,0,0,0,0 };
    e28_decode_chip_version(lead, ver);
    CHECK(strcmp(ver, "SX1280") == 0, "decode: leading status byte -> SX1280");

    // (c) status byte interleaved before each data byte
    uint8_t interl[17] = { 0xAA, 'S', 0xAA, 'X', 0xAA, '1', 0xAA, '2', 0xAA,
                           '8', 0xAA, '0', 0xAA, 0xAA, 0xAA, 0xAA, 0xAA };
    e28_decode_chip_version(interl, ver);
    CHECK(strcmp(ver, "SX1280") == 0, "decode: interleaved status bytes -> SX1280");

    // (d) dead bus (all 0xFF): must NOT claim an SX1xx chip, must be empty
    uint8_t dead[17];
    memset(dead, 0xFF, sizeof dead);
    e28_decode_chip_version(dead, ver);
    CHECK(strncmp(ver, "SX1", 3) != 0, "decode: dead bus 0xFF does not claim SX1xx");
    CHECK(strlen(ver) == 0, "decode: dead bus 0xFF decodes to empty string");

    // (e) empty bus (all 0x00) — same rule
    uint8_t zero[17];
    memset(zero, 0x00, sizeof zero);
    e28_decode_chip_version(zero, ver);
    CHECK(strncmp(ver, "SX1", 3) != 0, "decode: dead bus 0x00 does not claim SX1xx");
    CHECK(strlen(ver) == 0, "decode: dead bus 0x00 decodes to empty string");

    // (g) NUL padding is trimmed to the bare chip name
    uint8_t pad1282[17] = { 'S','X','1','2','8','2', 0,0,0,0,0,0,0,0,0,0,0 };
    e28_decode_chip_version(pad1282, ver);
    CHECK(strcmp(ver, "SX1282") == 0, "decode: NUL padding trimmed -> SX1282");

    // (f) ranging capability gate (SX1281 has no ranging engine in RadioLib)
    CHECK(e28_chip_supports_ranging("SX1280") == true, "SX1280 supports ranging");
    CHECK(e28_chip_supports_ranging("SX1282") == true, "SX1282 supports ranging (inherits SX1280)");
    CHECK(e28_chip_supports_ranging("SX1281") == false, "SX1281 rejected (no ranging engine)");
    CHECK(e28_chip_supports_ranging("SX1262") == false, "SX1262 rejected (sub-GHz, no ranging)");
    CHECK(e28_chip_supports_ranging(NULL) == false, "NULL version rejected");
  }

  if(failures == 0) {
    printf("E28 range console: ALL CHECKS PASSED\n");
    return(0);
  }
  printf("E28 range console: %d check(s) FAILED\n", failures);
  return(1);
}
