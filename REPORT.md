# REPORT — CONFIG_ENABLE_* symbol enumeration (tracker/firmware)

## Refs (recorded verbatim)

- `git rev-parse --abbrev-ref HEAD` at `~/repos/balloon-fresh/tracker/firmware/` → **pcbprog/base-d14-freeze**
- `git rev-parse --short HEAD` → **3c23483**
- `autonomous/mesh-baseline` resolves to **fb368093d9efb44dd521b52eb71ed47c839c6a78** (short **fb36809**)

**BRANCH MISMATCH — did NOT check out `autonomous/mesh-baseline`.** The checked-out HEAD
was `pcbprog/base-d14-freeze`, not `autonomous/mesh-baseline`. Per instruction I did not
switch branches. Instead I grepped the branch ref directly with
`git grep -hE 'CONFIG_ENABLE_[A-Z0-9_]+' autonomous/mesh-baseline -- .` from the repo root
`/home/c03rad0r/repos/balloon-fresh`.

Working tree note: `git status` in balloon-fresh showed unrelated pre-existing modifications
(e.g. deleted `../../data/*.log`). Nothing was modified, staged, or created in the firmware
source tree — this task is read-only on source. The only files written are PROGRESS.md and
REPORT.md inside the isolated worktree `~/worktrees/task-enable-symbols`.

## Scope A — tracker/firmware (the assigned path)

Tracked files on `autonomous/mesh-baseline` under `tracker/firmware/` containing matches (8):
components/meshcore/esp_idf/EspIdfInterfaces.h, main/CMakeLists.txt, main/app_main.cpp,
main/app_task.cpp, sdkconfig, sdkconfig.bak.mesh, sdkconfig.defaults, sdkconfig.defaults.esp32s3

### COMMAND 1 (tracker/firmware scope)

Command run (literal):

    grep -rhoE 'CONFIG_ENABLE_[A-Z0-9_]+' . | sort -u

Result: returned 12 lines (non-empty). Equivalent `git grep` encoding of the same line base
(`git grep -hE 'CONFIG_ENABLE_[A-Z0-9_]+' autonomous/mesh-baseline -- .`) yielded 90 raw lines.
Deduped symbol list:

    CONFIG_ENABLE_ANTENNA_SWITCH
    CONFIG_ENABLE_BMP280
    CONFIG_ENABLE_FEM
    CONFIG_ENABLE_GPS
    CONFIG_ENABLE_MESH
    CONFIG_ENABLE_MESHCORE
    CONFIG_ENABLE_NOSTR_STORE
    CONFIG_ENABLE_POWER_MANAGER
    CONFIG_ENABLE_RELAY_MODE
    CONFIG_ENABLE_STATIC_TASK_CLEAN_UP_HOOK
    CONFIG_ENABLE_TDMA
    CONFIG_ENABLE_TOLLGATE

### COMMAND 2 (tracker/firmware scope)

Command run (literal):

    grep -rhoE 'CONFIG_ENABLE_[A-Z0-9_]+' . | sort | uniq -c | sort -rn

Result: returned 12 lines (non-empty). Machine-produced counts:

          14 CONFIG_ENABLE_NOSTR_STORE
          12 CONFIG_ENABLE_GPS
          12 CONFIG_ENABLE_BMP280
          10 CONFIG_ENABLE_TOLLGATE
           9 CONFIG_ENABLE_RELAY_MODE
           9 CONFIG_ENABLE_MESH
           9 CONFIG_ENABLE_FEM
           6 CONFIG_ENABLE_MESHCORE
           6 CONFIG_ENABLE_ANTENNA_SWITCH
           3 CONFIG_ENABLE_TDMA
           2 CONFIG_ENABLE_STATIC_TASK_CLEAN_UP_HOOK
           1 CONFIG_ENABLE_POWER_MANAGER

Sum of counts = 90, matching the 90 raw matched lines.

### Deduped symbol list with counts (tracker/firmware scope)

    CONFIG_ENABLE_ANTENNA_SWITCH                  6
    CONFIG_ENABLE_BMP280                         12
    CONFIG_ENABLE_FEM                             9
    CONFIG_ENABLE_GPS                            12
    CONFIG_ENABLE_MESH                            9
    CONFIG_ENABLE_MESHCORE                        6
    CONFIG_ENABLE_NOSTR_STORE                    14
    CONFIG_ENABLE_POWER_MANAGER                   1
    CONFIG_ENABLE_RELAY_MODE                      9
    CONFIG_ENABLE_STATIC_TASK_CLEAN_UP_HOOK       2
    CONFIG_ENABLE_TDMA                            3
    CONFIG_ENABLE_TOLLGATE                       10

## Scope B — whole balloon-fresh repo root (literal reading of the commands)

The commands as written are "from the repo root" (`REPO: ~/repos/balloon-fresh/`), which is
wider than the assigned path. I ran the same enumeration across the whole repo root on the
branch ref and report it separately so both readings are covered. Same 12 symbols; wider count.

Raw matched lines across the whole tree: 236; tracked files containing matches: 46.

    CONFIG_ENABLE_ANTENNA_SWITCH                  6
    CONFIG_ENABLE_BMP280                         20
    CONFIG_ENABLE_FEM                            15
    CONFIG_ENABLE_GPS                            17
    CONFIG_ENABLE_MESH                           45
    CONFIG_ENABLE_MESHCORE                        8
    CONFIG_ENABLE_NOSTR_STORE                    28
    CONFIG_ENABLE_POWER_MANAGER                   1
    CONFIG_ENABLE_RELAY_MODE                     25
    CONFIG_ENABLE_STATIC_TASK_CLEAN_UP_HOOK      12
    CONFIG_ENABLE_TDMA                            5
    CONFIG_ENABLE_TOLLGATE                       73

Sum of counts = 255. NOTE: 255 (unique-symbol occurrences) vs 236 (raw matched lines) differ
because some raw lines contain more than one distinct CONFIG_ENABLE_* token; both figures come
from real tool output, no hand counting.

## Command-by-command return status

1. `git rev-parse --abbrev-ref HEAD` (firmware dir) → returned: `pcbprog/base-d14-freeze`
2. `git rev-parse --short HEAD` (firmware dir) → returned: `3c23483`
3. `git grep -hE 'CONFIG_ENABLE_[A-Z0-9_]+' autonomous/mesh-baseline -- .` (tracker/firmware) → returned: 90 lines
4. `git grep -lE 'CONFIG_ENABLE_[A-Z0-9_]+' autonomous/mesh-baseline -- .` (tracker/firmware) → returned: 8 file paths
5. Command 1 literal, tracker/firmware scope → returned: 12 deduped lines (non-empty)
6. Command 2 literal, tracker/firmware scope → returned: 12 count lines (non-empty)
7. `git grep -hE 'CONFIG_ENABLE_[A-Z0-9_]+' autonomous/mesh-baseline -- .` (repo root) → returned: 236 lines
8. `git grep -lE 'CONFIG_ENABLE_[A-Z0-9_]+' autonomous/mesh-baseline -- .` (repo root) → returned: 46 file paths
9. Command 1 literal, repo-root scope → returned: 12 deduped lines (non-empty)
10. Command 2 literal, repo-root scope → returned: 12 count lines (non-empty)

No command in this task **returned nothing** — every enumeration command produced output.
The `git -C … rev-parse --verify autonomous/mesh-baseline` probe returned the full SHA (non-empty).

## Acceptance

- Every symbol line above is quoted verbatim from tool output actually read. No invented symbols.
- All counts are machine-produced by `sort | uniq -c | sort -rn`; nothing counted by hand.
- Out of scope by instruction (owned by sibling tasks): sdkconfig/Kconfig/CMake declaration scan,
  and TOLLGATE classification. Not attempted here.
