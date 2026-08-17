// Host-side coverage test for range_test.h (no ESP-IDF needed — the header
// is pragma-once plain structs/inline functions).
//
// ASSERTION: every TX window in range_windows[] must have >=1 exact match in
// the RX scan table range_scan_modes[] on the demodulator-critical fields
// (mode, freq, bitrate, sf, bw, cr). A window without a matching scan mode is
// silently never measured: the scanner never configures the demodulator to
// that waveform, so not even the sync packets are seen (decode-gaps plan,
// gap G1 — windows L9W-868 / L9CR7-868 / F1300C34-868 were missing).
//
// Build & run:  make test   (host g++)

#include <cstdio>
#include "../range_test.h"

static bool scan_covers(const RangeWindow &w) {
    for (size_t j = 0; j < RANGE_SCAN_MODE_COUNT; j++) {
        const RangeScanMode &m = range_scan_modes[j];
        if (m.mode == w.mode && m.freq == w.freq && m.bitrate == w.bitrate &&
            m.sf == w.sf && m.bw == w.bw && m.cr == w.cr) {
            return true;
        }
    }
    return false;
}

int main() {
    const size_t n_windows = sizeof(range_windows) / sizeof(range_windows[0]);
    if (n_windows != (size_t)RANGE_WINDOW_COUNT) {
        std::printf("FAIL: RANGE_WINDOW_COUNT=%d but table has %zu entries\n",
                    RANGE_WINDOW_COUNT, n_windows);
        return 1;
    }

    int uncovered = 0;
    for (size_t i = 0; i < n_windows; i++) {
        const RangeWindow &w = range_windows[i];
        if (!scan_covers(w)) {
            uncovered++;
            std::printf("UNCOVERED window[%zu] %-14s mode=%d freq=%.1f br=%u sf=%u bw=%.1f cr=0x%02X\n",
                        i, w.name, (int)w.mode, w.freq, (unsigned)w.bitrate,
                        (unsigned)w.sf, w.bw, (unsigned)w.cr);
        }
    }

    std::printf("range_windows=%zu scan_modes=%zu uncovered=%d\n",
                n_windows, (size_t)RANGE_SCAN_MODE_COUNT, uncovered);
    if (uncovered == 0) {
        std::printf("PASS: every range window has >=1 exact scan-mode match on (mode,freq,bitrate,sf,bw,cr)\n");
        return 0;
    }
    std::printf("FAIL: %d window(s) have no matching scan mode -> never measured\n", uncovered);
    return 1;
}
