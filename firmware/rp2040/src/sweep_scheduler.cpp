/*
 * sweep_scheduler.cpp — Bitrate sweep scheduler implementation
 *
 * See sweep_scheduler.h for usage.
 */

#include "sweep_scheduler.h"

// ─── Default schedule ────────────────────────────────────────────────
// 4 FLRC bitrates, 3 minutes each = 12 minute total cycle.
const SweepEntry SweepScheduler::DEFAULT_SCHEDULE[] = {
    { 2600, 180000 },   // Window 0: fastest, shortest range
    { 1300, 180000 },   // Window 1
    {  650, 180000 },   // Window 2
    {  325, 180000 },   // Window 3: slowest, longest range
};
const uint8_t SweepScheduler::DEFAULT_SCHEDULE_LEN = 4;

// ─── Initialization ──────────────────────────────────────────────────

void SweepScheduler::begin(GpsTimeModule* gpsModule, uint32_t cycleOffsetMs) {
    gps = gpsModule;

    // Load default schedule
    scheduleLen = DEFAULT_SCHEDULE_LEN;
    for (uint8_t i = 0; i < scheduleLen && i < SWEEP_MAX_ENTRIES; i++) {
        schedule[i] = DEFAULT_SCHEDULE[i];
    }

    uint32_t totalCycle = getTotalCycleMs();
    if (totalCycle == 0) totalCycle = 1;  // guard against empty schedule

    // Normalize offset to [0, totalCycle)
    cycleOffsetMs = cycleOffsetMs % totalCycle;

    uint32_t now = (gps ? gps->getScheduleTimeMs() : 0);

    // Align cycle start to totalCycle boundaries + offset.
    //
    // With GPS locked: getScheduleTimeMs() returns UTC-anchored ms.
    //   Both TX and RX compute the same cycleStartTimeMs regardless of
    //   when they booted → they switch bitrates at the same UTC instant.
    //
    // Without GPS (millis fallback): getScheduleTimeMs() returns millis().
    //   Each board aligns to its own boot time → some skew between TX/RX,
    //   but the cycle still advances correctly (~5s skew acceptable).
    cycleStartTimeMs = (now / totalCycle) * totalCycle + cycleOffsetMs;

    // If the offset pushed the start into the future, step back one cycle
    // so that cycleStartTimeMs <= now and modular arithmetic works.
    while (cycleStartTimeMs > now) {
        cycleStartTimeMs -= totalCycle;
    }

    currentIndex  = 0;
    lastSwitchMs  = now;
    cycleCount    = 0;

    // Compute correct position for mid-cycle boot
    recalcPosition();
}

// ─── Core update loop ────────────────────────────────────────────────

bool SweepScheduler::update() {
    if (!gps || scheduleLen == 0) return false;

    uint32_t now        = gps->getScheduleTimeMs();
    uint32_t totalCycle = getTotalCycleMs();
    if (totalCycle == 0) return false;

    uint32_t elapsedInCycle = (now - cycleStartTimeMs) % totalCycle;

    // Walk the schedule to find which window the elapsed time falls in
    uint8_t  newIndex = 0;
    uint32_t accum    = 0;
    for (uint8_t i = 0; i < scheduleLen; i++) {
        accum += schedule[i].durationMs;
        if (elapsedInCycle < accum) {
            newIndex = i;
            break;
        }
        // If elapsed exceeds all windows (shouldn't happen with modulo,
        // but guard against rounding), clamp to last entry
        if (i == scheduleLen - 1) newIndex = i;
    }

    // Derive cycle count from total elapsed time
    uint32_t newCycleCount = (now - cycleStartTimeMs) / totalCycle;

    // Detect a change: either the window index changed, or we wrapped
    // into a new cycle (even if the index is still 0 → 0).
    if (newIndex != currentIndex || newCycleCount != cycleCount) {
        currentIndex = newIndex;
        cycleCount   = newCycleCount;
        lastSwitchMs = now;
        return true;
    }

    return false;
}

// ─── State accessors ─────────────────────────────────────────────────

uint16_t SweepScheduler::getCurrentBitrate() {
    if (scheduleLen == 0) return 0;
    return schedule[currentIndex].bitrateKbps;
}

uint8_t SweepScheduler::getCurrentIndex() {
    return currentIndex;
}

uint8_t SweepScheduler::getCurrentCycle() {
    return (uint8_t)cycleCount;  // truncates to 0-255 (>51 hrs at 12-min cycle)
}

uint32_t SweepScheduler::getTimeInWindowMs() {
    if (!gps || scheduleLen == 0) return 0;

    uint32_t now        = gps->getScheduleTimeMs();
    uint32_t totalCycle = getTotalCycleMs();
    if (totalCycle == 0) return 0;

    uint32_t elapsedInCycle = (now - cycleStartTimeMs) % totalCycle;

    // Sum durations of all windows before the current one
    uint32_t windowStart = 0;
    for (uint8_t i = 0; i < currentIndex; i++) {
        windowStart += schedule[i].durationMs;
    }
    return elapsedInCycle - windowStart;
}

uint32_t SweepScheduler::getTimeUntilSwitchMs() {
    if (!gps || scheduleLen == 0) return 0;

    uint32_t now        = gps->getScheduleTimeMs();
    uint32_t totalCycle = getTotalCycleMs();
    if (totalCycle == 0) return 0;

    uint32_t elapsedInCycle = (now - cycleStartTimeMs) % totalCycle;

    // Sum durations up to and including current window → that's the boundary
    uint32_t windowEnd = 0;
    for (uint8_t i = 0; i <= currentIndex; i++) {
        windowEnd += schedule[i].durationMs;
    }
    uint32_t remaining = windowEnd - elapsedInCycle;
    return remaining;
}

uint32_t SweepScheduler::getTotalCycleMs() {
    uint32_t total = 0;
    for (uint8_t i = 0; i < scheduleLen; i++) {
        total += schedule[i].durationMs;
    }
    return total;
}

// ─── Custom schedule ─────────────────────────────────────────────────

void SweepScheduler::setSchedule(const SweepEntry* entries, uint8_t count) {
    if (count > SWEEP_MAX_ENTRIES) count = SWEEP_MAX_ENTRIES;
    scheduleLen = count;
    for (uint8_t i = 0; i < count; i++) {
        schedule[i] = entries[i];
    }

    // Re-align cycle to new total duration
    uint32_t totalCycle = getTotalCycleMs();
    if (totalCycle == 0) return;

    uint32_t now = (gps ? gps->getScheduleTimeMs() : 0);
    cycleStartTimeMs = (now / totalCycle) * totalCycle;
    while (cycleStartTimeMs > now) {
        cycleStartTimeMs -= totalCycle;
    }

    currentIndex = 0;
    lastSwitchMs = now;
    cycleCount   = 0;
    recalcPosition();
}

// ─── Status output ───────────────────────────────────────────────────

void SweepScheduler::printStatus() {
    if (!gps) {
        Serial.println("SWEEP: no GPS module");
        return;
    }

    const char* srcStr;
    switch (gps->getSource()) {
        case TIME_GPS:    srcStr = "GPS";    break;
        case TIME_MILLIS: srcStr = "MILLIS"; break;
        default:          srcStr = "NONE";   break;
    }

    // Print full schedule
    Serial.print("SWEEP_SCHEDULE cycle=");
    Serial.print(getTotalCycleMs());
    Serial.print("ms modes=");
    for (uint8_t i = 0; i < scheduleLen; i++) {
        Serial.print(schedule[i].bitrateKbps);
        if (i < scheduleLen - 1) Serial.print(",");
    }
    Serial.print(" time_src=");
    Serial.println(srcStr);

    // Print current position
    Serial.print("SWEEP_STATE idx=");
    Serial.print(currentIndex);
    Serial.print(" bitrate=");
    Serial.print(getCurrentBitrate());
    Serial.print(" cycle=");
    Serial.print(cycleCount);
    Serial.print(" inWindow=");
    Serial.print(getTimeInWindowMs());
    Serial.print("ms untilSwitch=");
    Serial.print(getTimeUntilSwitchMs());
    Serial.println("ms");
}

// ─── Internal helpers ────────────────────────────────────────────────

void SweepScheduler::recalcPosition() {
    if (!gps || scheduleLen == 0) return;

    uint32_t now        = gps->getScheduleTimeMs();
    uint32_t totalCycle = getTotalCycleMs();
    if (totalCycle == 0) return;

    uint32_t elapsedInCycle = (now - cycleStartTimeMs) % totalCycle;

    uint32_t accum = 0;
    for (uint8_t i = 0; i < scheduleLen; i++) {
        accum += schedule[i].durationMs;
        if (elapsedInCycle < accum) {
            currentIndex = i;
            break;
        }
        if (i == scheduleLen - 1) currentIndex = i;
    }

    cycleCount = (now - cycleStartTimeMs) / totalCycle;
}
