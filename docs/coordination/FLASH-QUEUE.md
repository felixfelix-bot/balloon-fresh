# Flash Queue — Board Access Coordination

> **NO flashing without orchestrator (balloon-hermes) approval.**
> Sub-managers escalate flash requests to the orchestrator.

## Active Queue

| track | board | purpose | requested_time | approved_by | duration | status |
|-------|-------|---------|----------------|-------------|----------|--------|
| _(empty — no pending flash requests)_ | | | | | | |

## Rules

1. **NO flashing without orchestrator (balloon-hermes) approval**
2. **Sub-managers escalate flash requests to orchestrator** — do NOT flash autonomously
3. **Lock must be acquired BEFORE flashing** — `BALLOON_TRACK=<track> python3 balloon-board-lock.py acquire <resource>`
4. **Use pio-flash.sh wrapper** (NOT raw `pio run -t upload`)
5. **Hard device lock is active** — `chmod 000` on `/dev/ttyACMx` blocks ALL raw tool access
6. **picotool/openocd PATH shims active** — raw tool invocations are intercepted

## Walk Test Protocol (2026-07-24 Lesson)

During the 2026-07-24 walk test, 5 board-lock thefts occurred because:
- flock is advisory-only (doesn't block `cat`, `pio upload`, `picotool`)
- Sub-managers bypassed pio-flash.sh and ran raw `pio run -t upload`
- Multiple binaries deployed during the test — firmware mismatch made data unreliable

**This is now prevented by:**
- **Hard device lock**: `chmod 000 /dev/ttyACMx` on lock acquire (Phase 2a)
- **PATH shims**: picotool/openocd refuse to run without a lock (Phase 2b)
- **Flash queue**: this document — all flash requests must be approved (Phase 2c)
- **pio-flash.sh fix**: uses `balloon-board-lock.py check` for reliable verification (Phase 2d)

## How to Request a Flash

1. **Sub-manager**: Add a row to the queue table above with your request
2. **Orchestrator**: Review and approve (set `approved_by` and `status=APPROVED`)
3. **Sub-manager**: Acquire lock and flash:
   ```bash
   export BALLOON_TRACK=<your-track>
   python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both --purpose "approved flash: <reason>"
   ./tools/pio-flash.sh <env> --upload-port /dev/ttyACMx
   python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release both
   ```
4. **Update queue**: Set `status=DONE` when complete
