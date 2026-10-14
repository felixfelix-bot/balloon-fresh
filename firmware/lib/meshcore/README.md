# meshcore — MeshCore-style mesh transport core (host-testable)

The mesh half of the flight computer's radio stack. A balloon usually has no
line of sight to the ground station, so a packet has to be relayed by whatever
nodes are in range: that is what this module implements, and it is MeshCore's
job (Meshtastic is the sibling transport; both sit behind the same HAL).

This module is **pure logic on top of the frozen radio contract**. It performs
no I/O of its own, so the entire protocol — framing, flooding, duplicate
suppression, ACK reliability, fragmentation — is exercised on the host with
plain `g++`. No PlatformIO, no radio.

## The HAL boundary

`firmware/lib/radio_core/radio_hal.h` is the frozen contract. This module
includes it as `../radio_core/radio_hal.h` and **does not link
`radio_core.cpp`**: tests supply their own device model (`RadioHalFake`, in
`mesh.cpp`). `make_radio_hal()` is never defined here — a test that accidentally
pulled in `radio_core` would fail at link time instead of quietly constructing a
real device.

## Layout

| file | role |
| --- | --- |
| `meshcodec.h` / `meshcodec.cpp` | L1 header codec. Strict: a truncated, over-long, mis-versioned or field-inconsistent frame is rejected **whole**. |
| `mesh.h` / `mesh.cpp` | Transport core (`Node`, `DupCache`, `Reassembly`) plus `RadioHalFake`. |
| `meshsim.h` / `meshsim.cpp` | Deterministic simulated mesh: virtual clock, adjacency matrix, exact-delivery-set assertions, stable digests, DOT output. |
| `test_meshcore.cpp` | The only translation unit with `main()`. Both the test runner and the `--check` / `--dot` CLI. |
| `template_values.sh` | Single source of truth for every sizing constant. |
| `meshcore.h` | **generated** from `template_values.sh`; do not edit by hand. |
| `scripts/gen_meshcore_header.py` | Renders `meshcore.h`; `--check` fails if it is stale. |

## Running

```sh
make -C firmware/lib test            # from the repo root of the module's parent
./build/meshcore.test                # the test runner
./build/meshcore.test --check        # every scenario + digest, for a host check
./build/meshcore.test --dot          # the mesh as Graphviz DOT (stable)
```

`firmware/lib/Makefile` auto-discovers any directory containing `test_*.cpp`, so
adding this module never edits the Makefile.

## Why one `main()`

`firmware/lib/Makefile` compiles **every** `*.cpp` in a module into a **single**
executable, and `harness.h` keeps its check counters in `static` (per-translation
unit) variables. Two `main()` translation units would each link but each keep
its own silent counters, so all tests live in one file and the library files
define no `main()`. `meshsim.cpp` is deliberately organised that way; splitting
tests out again would silently stop counting failures.

## Semantics

* **Flood.** A `Data`/`Hello` frame addressed to `MESH_BROADCAST` is delivered
  locally and re-broadcast, consuming one hop. A unicast frame is forwarded only
  towards a **direct neighbour**: multi-hop unicast needs a route table, which
  this core does not have, so multi-hop reach is by flooding. A unicast frame
  whose destination is neither us nor a neighbour is dropped (`drops_no_route`),
  not blindly flooded.
* **Hop limit.** Decremented on every forward. `hop_limit == 0` means final:
  deliver (if addressed to us or broadcast) but never re-broadcast.
* **Own packets.** A frame whose `src` is our own id is our own flood coming
  back; it is dropped, never delivered to our own application.
* **Duplicate suppression.** Keyed on `(src, pkt_id, frag_index)`. The cache is a
  bounded ring — it evicts, so memory is O(capacity). `dedup_enabled = false`
  exists so tests can watch the mesh storm and prove the check is load-bearing.
* **ACK.** A single-fragment unicast `Data` datagram arms a retransmit timer; a
  matching `Ack` cancels it. Otherwise the datagram is retransmitted at most
  `max_attempts - 1` times with exponential backoff, then reported as a failure.
  There is no unbounded retry loop. `Ack` frames are never forwarded, never
  ACKed, and are only acted on by their destination. An ACK for a multi-hop
  unicast datagram can only travel if a route exists, which the model supplies.
* **Fragmentation.** Datagrams larger than `app_mtu` are split into
  `ceil(len / app_mtu)` frames sharing one `pkt_id`; all fragments are flooded.
  Reassembly is **presence-based**: every fragment index must be present.
  Completing on an arrival *count* instead would let a duplicate stand in for a
  missing fragment and yield a corrupt message, so `Reassembly` counts
  `corrupt_completions()` and the tests assert it stays zero.

## Determinism

The simulation uses a virtual clock and an explicit adjacency matrix. Virtual
time is advanced only by `Sim::advance_to()`, which is what fires ACK timers; a
relayed frame is handed to a neighbour with **zero per-hop latency**, so one
flood completes within a single virtual instant. Charging per-hop airtime would
drift every node's clock independently and make "one virtual instant" impossible
to reason about. Each simulated node's neighbour table is bounded by
`MESH_MAX_NEIGHBORS`, and `meshsim.h` `static_assert`s
`MESH_NODES <= MESH_MAX_NEIGHBORS` so a denser model cannot silently truncate
adjacency.

Every scenario emits a stable digest (deliveries in node order, then counters),
and `test_meshcore.cpp` asserts a digest is reproducible run to run, so a
behavioural drift shows up as a changed digest rather than a silent pass.

## Honesty

**The simulated mesh is a model, not field evidence.** There is no radio here:
frames are relayed by an adjacency matrix on a host clock. These tests prove the
protocol *semantics* — whole-flood duplicate suppression, hop-budget reach, the
exact delivery set of a given topology, bounded retries, and fragment integrity.
They say nothing about RF range, airtime, packet loss, interference, or the
SX1280/LR2021 driver. Real-hardware validation is a separate exercise.
