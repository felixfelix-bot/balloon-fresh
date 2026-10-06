# tools/alt — retained alternative implementations

**Nothing here is on the live code path.** These are alternative designs kept so
that no branch work is discarded during the 2026-10-06 consolidation. The shipped
tooling is one level up in `tools/`.

## Why this exists

`feat/e80-spi-bypass` (tip `f13af13c`) implemented the *same* planned milestones
(HOST-1 firmware-hash gate, HOST-3 session-id injection — see
`.hermes/plans/2026-08-20_firmware-harmonization-schedule.md`) with a
**class-based API**, while trunk implemented them with a **function-based API**.
Only `main` is shared, so neither is a version of the other and neither
"supersedes" the other. Trunk's design won because the live tree consumes it:

- `firmware/e80-stm32-bench/tools/e80_bench_ctl.py:86`
  `from firmware_hash_gate import parse_fw_hash, validate_fw_hash, format_session_start`
- `mesh-stack/flrc-bench-espidf/monitor_range.py:27`
  `from firmware_hash_gate import parse_fw_hash, validate_fw_hash`
  (`:16` `from session_manager import generate_session_id, format_session_command, inject_session_id_into_pkt`)
- `tools/fw_harm_measurement.py` also imports `parse_fw_hash` at module level

The class-based API has **zero consumers**.

| | live design | retained alternative |
|---|---|---|
| `firmware_hash_gate` | `../firmware_hash_gate.py` — `parse_fw_hash`, `validate_fw_hash`, `query_firmware_hash`, `check` | `./firmware_hash_gate.py` — `FirmwareHashGate`, `compute_firmware_hash`, `read_fw_hash_from_serial`, `parse_fw_boot_line` |
| `session_manager` | `../session_manager.py` — full lifecycle (21 functions) | `./session_manager.py` — `SessionManager` class + `validate_session_id` (strict subset) |

`tools/session_manager.py` is a *functional superset* of the retained copy, so
that copy is archival only. `tools/firmware_hash_gate.py` is a genuine design
divergence, not a superset — that is the file this directory exists for.

## Tests

```bash
PYTHONPATH=. /usr/bin/python3 -m pytest tests/alt -v      # 65 passed
```

Kept as a package (`tests/alt/__init__.py`) because `tests/` itself has no
`__init__.py`, so two same-basename files in different directories would
otherwise raise pytest's "import file mismatch".

### Import rule — do not regress this

The alt tests MUST import package-qualified:

```python
from tools.alt.firmware_hash_gate import FirmwareHashGate      # correct
from firmware_hash_gate import FirmwareHashGate                # WRONG
```

The bare form is a process-wide hazard: it claims `sys.modules['firmware_hash_gate']`
for *every* subsequent importer. That is not hypothetical — it broke the suite.
`tools/fw_harm_measurement.py` does `from firmware_hash_gate import parse_fw_hash`
at module level, and `tests/test_host_baud.py` loads that file via
`importlib.util.spec_from_file_location`, so the alt module shadowed it:

```
ImportError: cannot import name 'parse_fw_hash' from 'firmware_hash_gate'
             (.../tools/alt/firmware_hash_gate.py)
```

Symptom was one extra failure in an unrelated suite (`test_host_baud.py`), which
would have looked like flakiness. Package-qualified imports give `tools.alt.*`
their own `sys.modules` keys, so the bare names stay unclaimed for live tooling.
(`tools/` is a PEP-420 namespace package; `tools/alt/__init__.py` keeps `tools.alt`
deterministic.)

## Provenance

Extracted byte-identical from `feat/e80-spi-bypass` (`f13af13c`). Edits made:
`tools/alt/__init__.py` added; in each test file the module locator gained one
`dirname` level and the import became package-qualified. Module bodies are
untouched. Delete this directory only when the class-based design is formally
abandoned.
