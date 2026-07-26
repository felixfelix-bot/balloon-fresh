/*
 * sweep_scheduler.h — Bitrate sweep scheduler for FLRC range testing
 *
 * Cycles through multiple FLRC bitrates on a fixed time schedule.
 * Uses GPS time (if locked) or millis() fallback for synchronization.
 *
 * Default schedule: 2600 → 1300 → 650 → 325 kbps, 3 min each = 12 min cycle.
 * After a full cycle, the schedule repeats from the beginning.
 *
 * Usage:
 *   GpsTimeModule gps;
 *   SweepScheduler scheduler;
 *   gps.begin(1, 0, 9);
 *   scheduler.begin(&gps);
 *   // In loop():
 *   gps.update();
 *   if (scheduler.update()) {
 *       rfSwitchBitrate(scheduler.getCurrentBitrate());
 *       // reset stats, re-arm RX, etc.
 *   }
 */

#pragma once
#include <Arduino.h>
#include "gps_time.h"

// Maximum number of schedule entries (static array, no heap)
#define SWEEP_MAX_ENTRIES 8

struct SweepEntry {
    uint16_t bitrateKbps;
    uint32_t durationMs;    // How long to stay at this bitrate
};

class SweepScheduler {
public:
    // Initialize with GPS time module and optional cycle offset.
    // Loads the default 4-entry schedule (2600/1300/650/325, 3 min each).
    // cycleOffsetMs: stagger the cycle start so TX and RX don't switch
    //   simultaneously. With GPS locked, both boards align to UTC
    //   boundaries regardless of boot time.
    void begin(GpsTimeModule* gps, uint32_t cycleOffsetMs = 0);

    // Poll the schedule. Call this frequently in loop().
    // Returns true if the bitrate window changed since the last call.
    //   On true: caller should call rfSwitchBitrate(getCurrentBitrate())
    //   and reset any per-window statistics.
    bool update();

    // ─── State accessors ──────────────────────────────────────────────

    uint16_t getCurrentBitrate();       // kbps of current window
    uint8_t  getCurrentIndex();         // 0 .. scheduleLen-1
    uint8_t  getCurrentCycle();         // repetition count (0, 1, 2, ...)
    uint32_t getTimeInWindowMs();      // elapsed in current window
    uint32_t getTimeUntilSwitchMs();   // remaining in current window
    uint32_t getTotalCycleMs();        // sum of all durations

    // Replace the default schedule with a custom one (max SWEEP_MAX_ENTRIES).
    void setSchedule(const SweepEntry* entries, uint8_t count);

    // Print schedule + current state to Serial.
    void printStatus();

    // Static default schedule (4 entries)
    static const SweepEntry DEFAULT_SCHEDULE[];
    static const uint8_t    DEFAULT_SCHEDULE_LEN;

private:
    GpsTimeModule* gps;
    SweepEntry schedule[SWEEP_MAX_ENTRIES];
    uint8_t  scheduleLen;
    uint8_t  currentIndex;
    uint32_t cycleStartTimeMs;  // aligned reference point for modular math
    uint32_t lastSwitchMs;      // millis/getScheduleTime at last detected switch
    uint32_t cycleCount;        // how many full cycles completed

    // Recompute currentIndex + cycleCount from current time.
    void recalcPosition();
};
