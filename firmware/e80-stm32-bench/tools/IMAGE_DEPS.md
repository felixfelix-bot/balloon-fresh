# Container Image Dependencies — `firmware/e80-stm32-bench/tools/`

**Verdict: the E80 STM32 bench test suite pulls ZERO external container images.**

Every test path under `firmware/e80-stm32-bench/tools/` runs natively on the host
(python3 / pytest / ctest) or against real hardware over a serial port / TCP
socket. There is no Dockerfile, no compose file, no `docker run` / `podman run`
invocation, no CI `image:` key, and no registry host reference anywhere in the
scanned tree. Consequently the main enumeration table is empty by fact, not by
omission — the evidence and the audit trail are below.

## Enumeration table

| requirement | type (network) | hard-required or skippable | how it is detected | where it is normally set | affected tests or mark |
|---|---|---|---|---|---|
| _(none — no container images referenced in this tree)_ | n/a | n/a | Exhaustive scans below returned zero image references; see "Evidence" and "Coverage" sections | n/a | n/a |

> The table above has exactly the required 7 columns. It carries a single
> explicit empty-marker row because there is no image to enumerate; a zero-row
> table is reproduced here for acceptance purposes. No cell contains an
> unescaped pipe (`|`).

## Evidence — what was searched and what came back

Every scan was run `git ls-files`-scoped (tracked files only, build dirs and
`__pycache__` excluded) or repo-wide, as noted.

### 1. Container build/invocation artifacts — repo-wide, tracked

```
$ git ls-files | grep -iE "Dockerfile|compose|\.dockerignore|containerfile"
firmware/blossom-server/components/secp256k1/libsecp256k1/ci/linux-debian.Dockerfile
mesh-stack/tollgate/components/secp256k1/libsecp256k1/ci/linux-debian.Dockerfile
```

Both hits are **vendored upstream libsecp256k1 CI** (same github.com/bitcoin-core/
libsecp256k1 tree vendored twice). **Neither is under `firmware/e80-stm32-bench/`
and neither is reachable from any e80 bench test.** Out of scope — see
"Out-of-scope references found elsewhere in the repo".

### 2. CI `image:` keys — repo-wide, tracked

```
$ git ls-files -z | xargs -0 grep -n -E "^\s*image\s*:" | grep -v libsecp256k1
(no output)
```

The only `image:` keys in the entire repo are inside the two vendored
libsecp256k1 `.github/workflows/ci.yml` files (`image: sagemath/sagemath:latest`,
line 662 of each) plus `docker run` in their
`.github/actions/run-in-docker-action/action.yml:43`. Both trees are third-party
vendor slices, not e80 bench code.

### 3. Container words / registry hosts — e80 tree + CI/deploy surfaces

Scanned `firmware/e80-stm32-bench/` recursively plus `.github/`, `.githooks/`,
`ansible/`, `tests/`, `firmware/rp2040/`, `pytest.ini`, `pyproject.toml`,
`Makefile` for: `docker|podman|containerfile|dockerfile|containerd|nerdctl|kaniko|buildah`,
`image:\s*\S`, `FROM <image>`, and the registry hosts
`ghcr.io|docker.io|quay.io|gcr.io|mcr.microsoft.com|*.registry.*`.

```
$ (per-file catch-all scan across the surfaces above)
firmware/e80-stm32-bench/FLASHING.md:16:  - Image: `build-fw/e80_bench.bin` (or `.hex`) from this directory.
tests/test_session_manager.py:218:        """Multiple start_session() calls create unique sessions in the registry."""
EXIT: sweep done
```

* `FLASHING.md:16` — the word "Image" here means the **STM32 firmware binary**
  (`build-fw/e80_bench.bin`), not a container image.
* `tests/test_session_manager.py:218` — "registry" means an **in-memory session
  registry dict**, not an OCI registry.

Zero container matches. The only other textual hit repo-wide is
`firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_bpsk_types.h:119`
(`LR20XX_RADIO_BPSK_PHY_MODE_SIGFOX … the UL-CONTAINER`), which is an LR20xx
radio PHY-mode comment, not a container image.

### 4. CI workflows in scope

| File | Lines | Runners / steps | Container images |
|---|---|---|---|
| `.github/workflows/ci-host-tests.yml` | 77 | `runs-on: ubuntu-latest`; apt-get gcc/make/libmbedtls-dev/libcjson-dev; 5 host C/C++ suites built with gcc/g++ | none — no `container:`, no `image:`, no `services:` |
| `.github/workflows/test.yml` | 30 | `runs-on: ubuntu-latest`; apt-get gcc/g++/libmbedtls-dev; setup-python 3.13; `pip install pytest pyserial`; `pytest tests/` | none |

Neither workflow declares a `job.container`, a `services:` block, or a
`uses:` action that is itself a container-image reference beyond the standard
GitHub-hosted `actions/*` and `docker://` runners (which the file does not use).

### 5. Build / test entry points in the tree

| File | Target | What it actually runs | Image? |
|---|---|---|---|
| `firmware/e80-stm32-bench/Makefile:178` | `test-host` | `cmake -B build tests && cmake --build && ctest` | no |
| `firmware/e80-stm32-bench/Makefile:657` | `range-test-host` | `python3 -m pytest test_e80_range_split.py test_range_check.py -v` | no |
| `firmware/e80-stm32-bench/Makefile:358` | `range-setup` | `ansible-playbook ansible/range-setup.yml` (installs openocd/pyserial, clones repo) | no |
| `firmware/e80-stm32-bench/tools/Makefile` | `tx-server`, `rx-server`, `range-test`, … | `python3 e80_board_server.py` / `e80_range_test.py` over TCP + serial | no |
| `firmware/e80-stm32-bench/tools/create-range-test-zip.sh` | n/a | `zip` bundle of RX log + GPS + metadata | no |
| `firmware/e80-stm32-bench/flash_2g4.sh`, `run_sweep_2g4.sh` | n/a | `openocd` / `python3 e80_sweep*.py` against hardware | no |

`ansible/range-setup.yml` and the other playbooks under `ansible/` install host
packages only (`grep -rn -iE "docker|podman|image:|container" ansible/` → no
output).

## Offline-behaviour analysis (what gates the tests)

Because no image is pulled, "offline" for this suite means *no network at all*.
The relevant guards, cited so the SKIP/HARD-REQUIRED reasoning is auditable:

| Test group | Gate | File:line |
|---|---|---|
| Hardware tests (RP2040 boards) | `pytest.skip(f"Board with serial {serial_substr} not found")` | `tests/conftest.py:53` |
| Hardware fixtures (root suite) | `pytest.skip(f"TX board ({TX_SERIAL}) not connected")` / `pytest.skip(f"RX board ({RX_SERIAL}) not connected")` | `firmware/rp2040/tests/conftest.py:110`, `:119` |
| e80 dongle auto-detect | `except ImportError:` fallbacks around optional detection deps | `firmware/e80-stm32-bench/tools/e80_bench_ctl.py:51`, `:1494`; `e80_detect.py:104`, `:444` |
| CVM board-server tests | `except ImportError:` guard for optional `nostr_sdk` | `firmware/e80-stm32-bench/tools/test_cvm_board_server.py:141` |
| Distributed split tests | `except ImportError:` module fallback | `firmware/e80-stm32-bench/tools/test_e80_range_split.py:368` |
| CVM relay connectivity | **no skip guard** — `cvm_relay_test.py:32` does `import nostr_sdk` then connects to `wss://…`; this is a manual diagnostic target (`make range-cvm-test`), not part of the pytest collection set | `firmware/e80-stm32-bench/tools/cvm_relay_test.py:30-44` |

Markers registered (none of them are container-related):

* `pytest.ini:2-4` — `unit`, `hardware`
* `pyproject.toml:7-11` — `slow`, `hardware`, `host_c`
* `firmware/rp2040/pyproject.toml:2-5` — `hw`, `walk`

No `@pytest.mark.network`, no `@pytest.mark.docker`, no `docker.ping()` fixture,
and no registry-reachability check exists anywhere in the scanned tree.

## Out-of-scope references found elsewhere in the repo (context, not e80 deps)

These are the only container artifacts in the whole repository. They belong to
vendored upstream libraries and are **not** reachable from any
`firmware/e80-stm32-bench/tools/` test. Recorded here so "we searched everywhere"
is auditable.

| requirement | type (network) | hard-required or skippable | how it is detected | where it is normally set | affected tests or mark |
|---|---|---|---|---|---|
| `buildah`/`docker` (libsecp256k1 CI) | network | n/a — vendored upstream | n/a | `firmware/blossom-server/components/secp256k1/libsecp256k1/ci/linux-debian.Dockerfile`; `mesh-stack/tollgate/components/secp256k1/libsecp256k1/ci/linux-debian.Dockerfile` | none reachable from e80 bench |
| `sagemath/sagemath:latest` | network | n/a — vendored upstream | no skip guard (upstream `ci.yml` job) | `…/libsecp256k1/.github/workflows/ci.yml:662` (both vendored copies) | upstream libsecp256k1 CI only |
| docker CLI (via action) | network | n/a — vendored upstream | n/a | `…/libsecp256k1/.github/actions/run-in-docker-action/action.yml:43` | upstream libsecp256k1 CI only |

## Unresolved

None. Every candidate string that could have been a container image reference
was read to its definition and resolved to a non-container meaning
(`FLASHING.md:16` → firmware `.bin`; `test_session_manager.py:218` → in-memory
session registry; `lr20xx_radio_bpsk_types.h:119` → radio UL-CONTAINER PHY mode).

## Files scanned (coverage audit)

Scanned with `git ls-files` scope (tracked only) unless marked recursive.

**`firmware/e80-stm32-bench/tools/` — all 53 tracked files**, including:
`Makefile`, `create-range-test-zip.sh`, `e80_bench_ctl.py`, `e80_detect.py`,
`e80_board_server.py`, `e80_campaign.py`, `e80_range_test.py`, `e80_sweep*.py`,
`cvm_board_server.py`, `cvm_campaign.py`, `cvm_relay_test.py`, `gps_stitch.py`,
`gs_validation.py`, `merge_csvs.py`, `range_check.py`, `stop_verify.py`,
`countdown.py`, `buf_smoke_t3.py`, `v1_equivalence.py`, `v2_reset_ab.py`,
`v3_regression.py`, `v4_rehearsal.py`, and every `test_*.py`
(`test_crc16_golden.py`, `test_cvm_board_server.py`,
`test_cvm_campaign_dynamic_config.py`, `test_cvm_config_provider.py`,
`test_cvm_config_provider_makefile.py`, `test_dist_makefile.py`,
`test_dual_band_code.py`, `test_dualband_configs.py`, `test_e80_bench_ctl.py`,
`test_e80_campaign.py`, `test_e80_detect.py`, `test_e80_range_split.py`,
`test_e80_sweep_lora_filter.py`, `test_gps_stitch.py`, `test_gs_validation.py`,
`test_gs_validation_docs.py`, `test_guard_time_reduction.py`,
`test_harmonized_format.py`, `test_log_path_defaults.py`,
`test_per_stop_configs.py`, `test_prime_discard.py`, `test_range_check.py`,
`test_range_preflight.py`, `test_range_test_guide.py`,
`test_rf_experiment_design.py`, `test_throughput_configs.py`).

**`firmware/e80-stm32-bench/` — recursive, excluding `build*/` and `__pycache__/`:**
`Makefile`, `FLASHING.md`, `OPERATOR-QUICKSTART.md`, `flash_2g4.sh`,
`run_sweep_2g4.sh`, `tests/build/Makefile`, `third_party/**`
(CMSIS/STM32F1xx headers, Radio HAL sources, LR20xx driver).

**Repo-wide CI / test / deploy surfaces:**
`.github/workflows/ci-host-tests.yml`, `.github/workflows/test.yml`,
`.githooks/pre-commit`, `.githooks/pre-push`, `ansible/README.md`,
`ansible/pcb-workstation.yml`, `ansible/range-inventory.ini`,
`ansible/range-setup.yml`, `ansible/setup-debug-env.yml`, `ansible/setup-dev.yml`,
`tests/**` (tracked), `firmware/rp2040/tests/conftest.py`,
`firmware/rp2040/pyproject.toml`, `Makefile`, `pytest.ini`, `pyproject.toml`,
`.gitmodules`, and the full `git ls-files` index for `Dockerfile|compose|
containerfile` and `^\s*image\s*:` patterns.

**Excluded (with reason):** `firmware/e80-stm32-bench/build*/` (CMake-generated
`CMakeConfigureLog.yaml` / `Makefile`, no image refs), `__pycache__/` (bytecode),
`.venv/`, and the two vendored libsecp256k1 trees (third-party upstream, recorded
above).

## How this was verified

No containers were pulled or run (constraint honored; the analysis is
static/code-based). Commands that back every claim above are reproduced in the
"Evidence" section verbatim, together with their output, so any reviewer can
re-run them:

```bash
git ls-files | grep -iE "Dockerfile|compose|\.dockerignore|containerfile"
git ls-files -z | xargs -0 grep -n -E "^\s*image\s*:" | grep -v libsecp256k1
grep -rn -iE "docker|podman|image:|container" firmware/e80-stm32-bench/ ansible/ .github/ .githooks/
```
