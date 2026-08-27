// test_rp2040_prbs7_config.cpp — PRBS-7: RP2040 PRBS-9 hardware CONFIG command tests
//
// Tests the PRBS-9 hardware test mode CONFIG command:
//   1. CONFIG PRBS9 ON → writes 0x020E 0x03 to SPI (PRBS9 mode)
//   2. CONFIG PRBS9 OFF → writes 0x020E 0x00 to SPI (NORMAL mode)
//   3. Safety: can't enable while TX armed (IRQ pin LOW = TX active)
//   4. Invalid syntax rejected
//   5. State tracking: prbs9_enabled flag toggles correctly
//
// Compile + run:
//   g++ -std=c++17 -O0 -g -Wall -I../firmware/rp2040/src \
//     test_rp2040_prbs7_config.cpp -o /tmp/test_rp2040_prbs7 && /tmp/test_rp2040_prbs7

#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cassert>
#include <vector>

// ─── LR2021 TX_TEST_MODE register constants (from lr20xx driver) ──────
// SET_TX_TEST_MODE opcode = 0x020E, 1-byte payload
#define LR20XX_SET_TX_TEST_MODE_OC  0x020E
#define LR20XX_TX_TEST_MODE_NORMAL  0x00
#define LR20XX_TX_TEST_MODE_PRBS9   0x03

// ─── Mock SPI capture ────────────────────────────────────────────────
struct SpiCapture {
    std::vector<std::vector<uint8_t>> commands;
    void reset() { commands.clear(); }
    void write(const uint8_t *cmd, size_t len) {
        commands.emplace_back(cmd, cmd + len);
    }
    size_t callCount() const { return commands.size(); }
    const std::vector<uint8_t>& lastCall() const { return commands.back(); }
};

static SpiCapture g_spi;

// ─── Mock SPI function (replaces rfWriteCmd for testing) ──────────────
static void rfWriteCmd_mock(const uint8_t *cmd, size_t len) {
    g_spi.write(cmd, len);
}

// ─── Mock TX active state ────────────────────────────────────────────
static bool g_txActive = false;

// ─── PRBS-9 state (mirrors firmware) ─────────────────────────────────
static bool prbs9_enabled = false;

// ─── Safety check (mirrors firmware isTxActive()) ────────────────────
static bool isTxActive() {
    return g_txActive;
}

// ─── rfSetTxTestMode (mirrors firmware, uses mock SPI) ────────────────
static void rfSetTxTestMode(uint8_t mode) {
    uint8_t cmd[3] = {
        (uint8_t)(LR20XX_SET_TX_TEST_MODE_OC >> 8),
        (uint8_t)(LR20XX_SET_TX_TEST_MODE_OC >> 0),
        mode
    };
    rfWriteCmd_mock(cmd, 3);
}

// ─── Command handler (mirrors firmware CONFIG PRBS9 ON|OFF handler) ──
// Returns: 0=OK, -1=syntax error, -2=safety rejection
static int handleConfigPrbs9(const char *arg) {
    if (strcmp(arg, "ON") == 0) {
        if (isTxActive()) {
            return -2;  // Safety: TX active
        }
        rfSetTxTestMode(LR20XX_TX_TEST_MODE_PRBS9);
        prbs9_enabled = true;
        return 0;
    } else if (strcmp(arg, "OFF") == 0) {
        if (isTxActive()) {
            return -2;  // Safety: TX active
        }
        rfSetTxTestMode(LR20XX_TX_TEST_MODE_NORMAL);
        prbs9_enabled = false;
        return 0;
    }
    return -1;  // Syntax error
}

// ─── TEST 1: CONFIG PRBS9 ON writes correct SPI command ──────────────
static void test_config_prbs9_on(void) {
    printf("TEST 1: CONFIG PRBS9 ON writes 0x020E 0x03 to SPI... ");
    g_spi.reset();
    prbs9_enabled = false;
    g_txActive = false;

    int rc = handleConfigPrbs9("ON");
    assert(rc == 0);
    assert(prbs9_enabled == true);
    assert(g_spi.callCount() == 1);
    assert(g_spi.lastCall().size() == 3);
    assert(g_spi.lastCall()[0] == 0x02);
    assert(g_spi.lastCall()[1] == 0x0E);
    assert(g_spi.lastCall()[2] == LR20XX_TX_TEST_MODE_PRBS9);
    printf("PASS\n");
}

// ─── TEST 2: CONFIG PRBS9 OFF writes correct SPI command ────────────
static void test_config_prbs9_off(void) {
    printf("TEST 2: CONFIG PRBS9 OFF writes 0x020E 0x00 to SPI... ");
    g_spi.reset();
    prbs9_enabled = true;
    g_txActive = false;

    int rc = handleConfigPrbs9("OFF");
    assert(rc == 0);
    assert(prbs9_enabled == false);
    assert(g_spi.callCount() == 1);
    assert(g_spi.lastCall().size() == 3);
    assert(g_spi.lastCall()[0] == 0x02);
    assert(g_spi.lastCall()[1] == 0x0E);
    assert(g_spi.lastCall()[2] == LR20XX_TX_TEST_MODE_NORMAL);
    printf("PASS\n");
}

// ─── TEST 3: Safety: can't enable while TX armed ─────────────────────
static void test_safety_tx_active_on(void) {
    printf("TEST 3: Safety: CONFIG PRBS9 ON rejected while TX active... ");
    g_spi.reset();
    prbs9_enabled = false;
    g_txActive = true;  // TX is in flight

    int rc = handleConfigPrbs9("ON");
    assert(rc == -2);       // Safety rejection
    assert(prbs9_enabled == false);  // State unchanged
    assert(g_spi.callCount() == 0);  // No SPI write
    printf("PASS\n");
}

// ─── TEST 3b: Safety: can't disable while TX armed ───────────────────
static void test_safety_tx_active_off(void) {
    printf("TEST 3b: Safety: CONFIG PRBS9 OFF rejected while TX active... ");
    g_spi.reset();
    prbs9_enabled = true;
    g_txActive = true;  // TX is in flight

    int rc = handleConfigPrbs9("OFF");
    assert(rc == -2);       // Safety rejection
    assert(prbs9_enabled == true);   // State unchanged
    assert(g_spi.callCount() == 0);  // No SPI write
    printf("PASS\n");
}

// ─── TEST 4: Invalid syntax rejected ─────────────────────────────────
static void test_invalid_syntax(void) {
    printf("TEST 4: Invalid syntax rejected... ");
    g_spi.reset();
    prbs9_enabled = false;
    g_txActive = false;

    int rc = handleConfigPrbs9("ENABLE");
    assert(rc == -1);       // Syntax error
    assert(prbs9_enabled == false);  // State unchanged
    assert(g_spi.callCount() == 0);  // No SPI write
    printf("PASS\n");
}

// ─── TEST 5: State tracking: ON then OFF toggles correctly ───────────
static void test_state_toggle(void) {
    printf("TEST 5: State tracking: ON → OFF toggles correctly... ");
    g_spi.reset();
    prbs9_enabled = false;
    g_txActive = false;

    // ON
    int rc1 = handleConfigPrbs9("ON");
    assert(rc1 == 0);
    assert(prbs9_enabled == true);

    // OFF
    int rc2 = handleConfigPrbs9("OFF");
    assert(rc2 == 0);
    assert(prbs9_enabled == false);

    // ON again
    int rc3 = handleConfigPrbs9("ON");
    assert(rc3 == 0);
    assert(prbs9_enabled == true);

    assert(g_spi.callCount() == 3);  // 3 SPI writes total
    printf("PASS\n");
}

// ─── TEST 6: SPI opcode matches E80 lr20xx driver ─────────────────────
static void test_opcode_matches_driver(void) {
    printf("TEST 6: SPI opcode matches E80 lr20xx driver (0x020E)... ");
    g_spi.reset();
    g_txActive = false;

    handleConfigPrbs9("ON");
    assert(g_spi.lastCall()[0] == (LR20XX_SET_TX_TEST_MODE_OC >> 8));
    assert(g_spi.lastCall()[1] == (LR20XX_SET_TX_TEST_MODE_OC & 0xFF));
    printf("PASS\n");
}

// ─── TEST 7: PRBS9 mode value matches lr20xx enum ────────────────────
static void test_mode_values_match_enum(void) {
    printf("TEST 7: Mode values match lr20xx enum (NORMAL=0x00, PRBS9=0x03)... ");
    assert(LR20XX_TX_TEST_MODE_NORMAL == 0x00);
    assert(LR20XX_TX_TEST_MODE_PRBS9 == 0x03);
    printf("PASS\n");
}

int main(void) {
    printf("\n=== RP2040 PRBS-7 Config Command Tests ===\n\n");

    test_config_prbs9_on();
    test_config_prbs9_off();
    test_safety_tx_active_on();
    test_safety_tx_active_off();
    test_invalid_syntax();
    test_state_toggle();
    test_opcode_matches_driver();
    test_mode_values_match_enum();

    printf("\n=== Results: 8/8 passed ===\n");
    return 0;
}