#!/usr/bin/env python3
"""cvm_campaign.py — distributed adaptive sweep controller using CVM (Nostr).

Replaces e80_campaign.py's in-process arm_and_stream() flow with CVM tool
calls to a remote TX board server and a remote RX board server. The SPRT
decision logic (sprt_decide) is imported from e80_campaign — single-sourced.

Architecture:
    Coordinator (this file)
        │
        ├── CVMClient ──► TX board server (cvm_board_server --role tx)
        │                   ├── set_config (dynamic config push: MOD/FREQ/PA/ROLE)
        │                   ├── board_query / board_send / board_stat
        │                   ├── board_start_burst
        │                   └── board_swd_reset
        │
        └── CVMClient ──► RX board server (cvm_board_server --role rx)
                            ├── set_config (dynamic config push: MOD/FREQ/PA/ROLE)
                            ├── board_query / board_send / board_stat
                            ├── board_capture
                            └── board_swd_reset

The coordinator may run on either machine (it only needs Nostr relay
reachability, not direct USB or SSH access to the boards).

CLI:
    python3 cvm_campaign.py --mode probe --band 868 --stop-id S1 --distance 50 \\
        --tx-npub npub1... --rx-npub npub1... \\
        --client-hex <coordinator_secret_hex>

Makefile:
    make range-adaptive TX_NPUB=npub1... RX_NPUB=npub1... CONFIGS=outdoor-10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

# Sibling imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Reuse e80_campaign's SPRT logic — single-sourced
import e80_campaign as camp  # noqa: E402
import e80_sweep_full as sw    # noqa: E402  (for airtime helpers)

DEFAULT_RELAYS = [
    "wss://relay.primal.net",
    "wss://nostr.mom",
    "wss://nos.lol",
    "wss://relay2.contextvm.org",
    "wss://relay.nostr.band",
]

KIND_CVM_RPC = 25910
KIND_GIFT_WRAP = 1059

DEFAULT_TIMEOUT = 30.0      # per CVM call (cold relay latency 5-10s)
ARM_TIMEOUT = 60.0           # ARM TX may need 3s + relay latency
CAPTURE_BUDGET_MULT = 1.5    # extra margin for n_cap × airtime
RETRY_COUNT = 1              # retry once on timeout before failing


# ===========================================================================
# CVMClient — calls a remote CVM board server via Nostr gift wrap
# ===========================================================================

class CVMClient:
    """Remote CVM board server client. Wraps gift-wrapped JSON-RPC round trips.

    For tests, accept `transport=` (any object with `async call(target_npub,
    rpc, timeout)`) and skip the nostr_sdk connection entirely.
    """

    def __init__(self, server_npub_hex: str, client_keys_hex: str,
                 relays: list[str], transport=None, log=print):
        self.server_npub_hex = server_npub_hex
        self.client_keys_hex = client_keys_hex
        self.relays = relays
        self.transport = transport  # None for real Nostr
        self.log = log
        # Real Nostr state (lazily loaded)
        self._client = None
        self._signer = None
        self._server_pk = None
        self._client_pk = None
        # Response correlation
        self._pending: dict[Any, asyncio.Future] = {}
        self._notification_task = None

    async def connect(self):
        """Establish real Nostr connections (only when transport is None)."""
        if self.transport is not None:
            return  # mock mode
        import nostr_sdk
        # Parse keys
        self._signer_keys = nostr_sdk.Keys.parse(self.client_keys_hex)
        self._signer = nostr_sdk.NostrSigner.keys(self._signer_keys)
        self._client_pk = self._signer_keys.public_key()
        # Resolve server npub → PublicKey
        if self.server_npub_hex.startswith("npub1"):
            self._server_pk = nostr_sdk.PublicKey.parse(self.server_npub_hex)
        else:
            self._server_pk = nostr_sdk.PublicKey.from_hex(self.server_npub_hex)
        # Build client
        self._client = nostr_sdk.ClientBuilder().signer(self._signer).build()
        added = 0
        for url in self.relays:
            try:
                await self._client.add_relay(nostr_sdk.RelayUrl.parse(url))
                added += 1
            except Exception as e:
                self.log(f"[cvm-client] relay add fail {url}: {e}")
        if added == 0:
            raise RuntimeError(f"no relays reachable (tried {self.relays})")
        await self._client.connect()
        # Subscribe to our gift wraps (broad — filter p tag client-side)
        sub_filter = nostr_sdk.Filter().kinds([nostr_sdk.Kind(KIND_GIFT_WRAP)])
        await self._client.subscribe(sub_filter, None)
        self.log(f"[cvm-client] connected to {added} relays "
                 f"(client_pk={self._client_pk.bech32()[:24]}...)")

        # Start the notification handler
        handler = _ClientNotificationHandler(self)
        self._notification_task = asyncio.create_task(
            self._client.handle_notifications(handler))

    async def call(self, tool_name: str, arguments: dict,
                  timeout: float = DEFAULT_TIMEOUT) -> dict:
        """Call a tool on the remote board server.

        Returns the tool's result dict (the JSON inside result.content[0].text).
        Raises TimeoutError if no reply within timeout+retries.
        """
        if self.transport is not None:
            return await self._call_via_mock(tool_name, arguments, timeout)
        return await self._call_via_nostr(tool_name, arguments, timeout)

    async def _call_via_mock(self, tool_name: str, arguments: dict,
                              timeout: float) -> dict:
        """Mock-transport path (used by tests)."""
        rpc = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": tool_name, "arguments": arguments},
               "id": _next_id()}
        response = await self.transport.call(self.server_npub_hex, rpc, timeout)
        return self._extract_result(response, tool_name)

    async def _call_via_nostr(self, tool_name: str, arguments: dict,
                              timeout: float) -> dict:
        """Real Nostr path."""
        import nostr_sdk
        rpc_id = _next_id()
        rpc = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": tool_name, "arguments": arguments},
               "id": rpc_id}
        payload = json.dumps(rpc)
        # Build inner event (kind 25910)
        inner = nostr_sdk.UnsignedEvent.from_json(json.dumps({
            "pubkey": self._client_pk.to_hex(),
            "kind": KIND_CVM_RPC,
            "tags": [["p", self._server_pk.to_hex()]],
            "content": payload,
            "created_at": nostr_sdk.Timestamp.now().as_secs(),
        }))
        # Register pending future for matching response
        fut = asyncio.get_event_loop().create_future()
        self._pending[rpc_id] = fut

        # Send
        try:
            gw = await nostr_sdk.gift_wrap(self._signer, self._server_pk, inner)
            await self._client.send_event(gw)
        except Exception as e:
            self._pending.pop(rpc_id, None)
            raise RuntimeError(f"send failed: {e}") from e

        # Wait for reply with retry once
        t0 = time.monotonic()
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(rpc_id, None)
            if RETRY_COUNT == 0:
                raise TimeoutError(f"{tool_name}: no reply after {timeout:.0f}s")
            self.log(f"[cvm-client] timeout on {tool_name} (id={rpc_id}), "
                     f"retrying...")
            # One retry — re-send + wait again
            rpc_id2 = _next_id()
            rpc2 = dict(rpc, id=rpc_id2)
            inner2 = nostr_sdk.UnsignedEvent.from_json(json.dumps({
                "pubkey": self._client_pk.to_hex(),
                "kind": KIND_CVM_RPC,
                "tags": [["p", self._server_pk.to_hex()]],
                "content": json.dumps(rpc2),
                "created_at": nostr_sdk.Timestamp.now().as_secs(),
            }))
            fut2 = asyncio.get_event_loop().create_future()
            self._pending[rpc_id2] = fut2
            try:
                gw2 = await nostr_sdk.gift_wrap(self._signer, self._server_pk, inner2)
                await self._client.send_event(gw2)
                return await asyncio.wait_for(fut2, timeout=timeout)
            except asyncio.TimeoutError:
                self._pending.pop(rpc_id2, None)
                raise TimeoutError(
                    f"{tool_name}: no reply after 2 attempts ({timeout:.0f}s ×2)")
            finally:
                self._pending.pop(rpc_id2, None)

    def _extract_result(self, response: dict, tool_name: str) -> dict:
        """Pull the tool's result dict out of the JSON-RPC response envelope."""
        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"{tool_name}: {err.get('message', err)}")
        result = response.get("result")
        if not result:
            raise RuntimeError(f"{tool_name}: missing result in response")
        content = result.get("content", [])
        if not content:
            raise RuntimeError(f"{tool_name}: empty content in response")
        text = content[0].get("text", "{}")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{tool_name}: bad JSON in content text: {e}") from e
        return parsed

    async def close(self):
        if self._notification_task:
            self._notification_task.cancel()
            try:
                await self._notification_task
            except asyncio.CancelledError:
                pass
        if self._client:
            try:
                await self._client.shutdown()
            except Exception:
                pass


class _ClientNotificationHandler:
    """HandleNotification adapter for the CVMClient."""

    def __init__(self, client: CVMClient):
        self.client = client

    async def handle(self, relay_url, subscription_id, event):
        try:
            # Filter p tag = our pubkey
            p_tag = _extract_p_tag(event)
            if p_tag is None or p_tag != self.client._client_pk.to_hex():
                return
            import nostr_sdk
            unwrapped = await nostr_sdk.UnwrappedGift.from_gift_wrap(
                self.client._signer, event)
            inner = unwrapped.rumor()
            rpc = json.loads(inner.content())
            rpc_id = rpc.get("id")
            # Wake up the pending future
            fut = self.client._pending.pop(rpc_id, None)
            if fut is None or fut.done():
                return  # late or duplicate
            # Extract result dict on the event-loop thread
            content_text = rpc.get("result", {}).get("content", [{}])[0].get("text", "{}")
            try:
                parsed = json.loads(content_text)
                fut.set_result(parsed)
            except Exception as e:
                fut.set_exception(RuntimeError(f"bad result JSON: {e}"))
        except Exception as e:
            self.client.log(f"[cvm-client] handle err: {type(e).__name__}: {e}")

    async def handle_msg(self, relay_url, msg):
        return None


def _extract_p_tag(event):
    try:
        for tag in event.tags().to_vec():
            v = tag.as_vec()
            if v and v[0] == "p" and len(v) >= 2:
                return v[1]
    except Exception:
        pass
    return None


_RPC_ID_COUNTER = 0

def _next_id() -> int:
    global _RPC_ID_COUNTER
    _RPC_ID_COUNTER += 1
    return _RPC_ID_COUNTER


# ===========================================================================
# Distributed SPRT loop — replaces e80_campaign.sprt_run()
# ===========================================================================

async def push_config_to_boards(cfg: dict, tx_client: CVMClient,
                                 rx_client: CVMClient) -> bool:
    """Push a single config entry to both TX and RX boards via set_config MCP tool.

    Wraps the config entry into a preset JSON with one config and sends it
    to each board's set_config tool (inline JSON mode). The board server
    applies MOD/FREQ/PA/ROLE commands to the board.

    Returns True if both boards accepted the config, False otherwise.
    """
    # Build a single-config preset for inline JSON mode
    preset = json.dumps({
        "name": "dynamic",
        "configs": [cfg],
    })
    # Push to both boards
    for client in (tx_client, rx_client):
        result = await client.call("set_config", {"config_json": preset})
        if not result.get("ok"):
            return False
    return True


async def cvm_sprt_run(cfg, tx_client: CVMClient, rx_client: CVMClient,
                        session_id: int, cfg_idx: int, n_cap: int = 20,
                        policy: Optional[dict] = None,
                        stop_fn=None) -> camp.SprtResult:
    """Distributed replacement for e80_campaign.sprt_run().

    Pushes radio config to both TX and RX via the set_config MCP tool
    (dynamic config pushing), then sends SESSION/CONFIG metadata via
    board_send, arms TX via board_query (ARM TX), starts the burst via
    board_start_burst, captures on RX via board_capture, then applies SPRT
    via the shared sprt_decide() helper. Returns SprtResult(verdict, k, n).
    """
    p = policy or camp.SPRT
    n_cap_local = n_cap or p["n_cap"]
    n_min = p["n_min"]

    # --- Push radio config (MOD/FREQ/PA/ROLE) to both boards via set_config ---
    mod = cfg["mod"]
    if not await push_config_to_boards(cfg, tx_client, rx_client):
        return camp.SprtResult("DEAD", n_cap_local, n_cap_local)

    # --- Session metadata (not radio config — still via board_send) ---
    for client in (tx_client, rx_client):
        await client.call("board_send", {"line": f"SESSION {session_id}"})
        await client.call("board_send", {"line": f"CONFIG {cfg_idx} 1"})
    # Band override if outside 868 (firmware gate)
    if not (sw.BAND_MIN_HZ <= cfg["freq"] <= sw.BAND_MAX_HZ):
        for client in (tx_client, rx_client):
            await client.call("board_send",
                              {"line": f"BAND OVERRIDE {sw.BAND_OVERRIDE_PIN}"})

    # --- Arm TX ---
    arm_reply = await tx_client.call("board_query",
                                      {"line": "ARM TX", "timeout": 30.0})
    if not arm_reply.get("ok") or "ARMED" not in arm_reply.get("reply", ""):
        return camp.SprtResult("DEAD", n_cap_local, n_cap_local)

    # --- Start burst on TX ---
    burst = await tx_client.call("board_start_burst",
                                  {"n": n_cap_local, "plen": cfg["plen"],
                                   "gap_us": cfg["gap"]})
    if not burst.get("ok"):
        return camp.SprtResult("DEAD", n_cap_local, n_cap_local)

    # --- Compute capture budget ---
    if mod == "lora":
        toa_max = sw.lora_airtime_s(12, 125, cfg["plen"])
    else:
        toa_max = sw.flrc_airtime_s(260, cfg["plen"])
    capture_budget = max(5.0, n_cap_local * (toa_max + cfg["gap"] / 1e6)
                          + 10.0) * CAPTURE_BUDGET_MULT

    # --- Capture on RX (single RPC; server drains and parses) ---
    cap_result = await rx_client.call(
        "board_capture",
        {"duration_s": capture_budget, "config_idx": cfg_idx,
         "eager_stop": p.get("eager_stop", False)},  # future-standard flag
        timeout=capture_budget + 20.0,  # capture + relay round trip
    )
    if not cap_result.get("ok"):
        # Capture failed — treat as dead
        return camp.SprtResult("DEAD", n_cap_local, n_cap_local)

    pkts = cap_result.get("pkts", [])
    n = cap_result.get("n", 0)
    k = cap_result.get("k", 0)

    # Stop TX (graceful end-of-burst)
    try:
        await tx_client.call("board_send", {"line": "STOP"})
    except Exception:
        pass

    # Apply SPRT decision (single-shot — we already have all packets)
    res = camp.sprt_decide(k, n, p)
    return res


async def cvm_stop_tx(tx_client: CVMClient):
    """Distributed version of stop_tx()."""
    await tx_client.call("board_send", {"line": "STOP"})


# ===========================================================================
# Helpers — parse npub, build client/transport
# ===========================================================================

def parse_npub_to_hex(npub_or_hex: str) -> str:
    """Convert npub1... to hex. If already hex, return as-is."""
    if npub_or_hex.startswith("npub1"):
        import nostr_sdk
        return nostr_sdk.PublicKey.parse(npub_or_hex).to_hex()
    return npub_or_hex


# ===========================================================================
# Main entrypoint — argparse-driven CLI
# ===========================================================================

def _parse_args():
    ap = argparse.ArgumentParser(
        description="E80 distributed adaptive sweep coordinator (Nostr/CVM)")
    ap.add_argument("--mode", default="probe",
                    choices=["probe", "good", "degraded", "cliff", "full-stop"],
                    help="Campaign mode (default: probe)")
    ap.add_argument("--band", default="868",
                    choices=["868", "2g4", "both"],
                    help="Band: 868 MHz, 2.4 GHz, or both")
    ap.add_argument("--reset-policy", default="strict",
                    choices=["strict", "gated"],
                    help="Reset policy between configs")
    ap.add_argument("--stop-id", default="S1",
                    help="Distance stop identifier (S1, S2, ...)")
    ap.add_argument("--distance", type=int, default=0,
                    help="Distance in meters for this stop")
    ap.add_argument("--state", default=None,
                    help="Path to campaign state JSON (carry-forward DB)")
    ap.add_argument("--out", default=None,
                    help="Output directory")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print configs only, no CVM calls")
    # CVM-specific
    ap.add_argument("--tx-npub", required=False,
                    help="TX board server Nostr public key (npub1...)")
    ap.add_argument("--rx-npub", required=False,
                    help="RX board server Nostr public key (npub1...)")
    ap.add_argument("--client-hex", default=os.environ.get("CVM_CLIENT_HEX"),
                    help="Coordinator Nostr private key (64-char hex)")
    ap.add_argument("--relays", default=",".join(DEFAULT_RELAYS),
                    help="Comma-separated relay URLs")
    ap.add_argument("--n-cap", type=int, default=camp.SPRT["n_cap"],
                    help=f"Packets per config (default {camp.SPRT['n_cap']})")
    ap.add_argument("--configs", default=None,
                    help="Config preset name (e.g. outdoor-10) or path to a "
                         "JSON preset file. Overrides --mode/--band when given.")
    ap.add_argument("--configs-json", default=None,
                    help="Inline config preset JSON (the whole preset object "
                         "with a 'configs' list). Lets the coordinator run on "
                         "a machine without the config file — the config JSON "
                         "comes from CONFIGS in the Makefile. "
                         "Overrides --configs when given.")
    return ap.parse_args()


async def amain(args) -> int:
    # Reuse e80_bench_ctl's preset loader (single-sourced). The config comes
    # from one of three sources, in priority order:
    #   1. --configs-json (inline JSON string — lets the coordinator run on a
    #      machine without the config file; e.g. from Makefile CONFIGS)
    #   2. --configs (preset name or file path)
    #   3. --mode/--band (programmatic campaign builder)
    import e80_bench_ctl as ctl
    if args.configs_json:
        try:
            preset = json.loads(args.configs_json)
            cfgs = ctl.load_config_preset(preset)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"ERROR parsing --configs-json: {e}", file=sys.stderr)
            return 2
        print(f"E80 CVM Campaign — configs-json "
              f"stop={args.stop_id} d={args.distance}m", flush=True)
    elif args.configs:
        try:
            cfgs = ctl.load_config_preset(args.configs)
        except (FileNotFoundError, ValueError) as e:
            print(f"ERROR loading configs '{args.configs}': {e}",
                  file=sys.stderr)
            return 2
        print(f"E80 CVM Campaign — configs={args.configs} "
              f"stop={args.stop_id} d={args.distance}m", flush=True)
    else:
        cfgs = camp.build_campaign_configs(args.mode, band=args.band)
        print(f"E80 CVM Campaign — mode={args.mode} band={args.band} "
              f"stop={args.stop_id} d={args.distance}m", flush=True)
    print(f"Configs: {len(cfgs)}", flush=True)

    if args.dry_run:
        for i, c in enumerate(cfgs):
            print(f"  [{i+1}] {c['label']}  mod={c['mod']} "
                  f"freq={c['freq']/1e6:.0f}MHz plen={c['plen']} "
                  f"pa={c['pa']} gap={c['gap']}")
        if not args.tx_npub or not args.rx_npub:
            print(f"\n(dry-run: TX_NPUB/RX_NPUB not required)")
        return 0

    if not args.tx_npub or not args.rx_npub:
        print("ERROR: --tx-npub and --rx-npub are required (or use --dry-run)",
              file=sys.stderr)
        return 2
    if not args.client_hex:
        print("ERROR: --client-hex (or CVM_CLIENT_HEX env) is required",
              file=sys.stderr)
        return 2

    tx_npub_hex = parse_npub_to_hex(args.tx_npub)
    rx_npub_hex = parse_npub_to_hex(args.rx_npub)
    relays = [r.strip() for r in args.relays.split(",") if r.strip()]

    # Build clients
    tx_client = CVMClient(tx_npub_hex, args.client_hex, relays,
                          log=lambda s: print(s, flush=True))
    rx_client = CVMClient(rx_npub_hex, args.client_hex, relays,
                           log=lambda s: print(s, flush=True))
    await tx_client.connect()
    await rx_client.connect()
    print(f"Connected to both TX and RX board servers via Nostr", flush=True)

    # Warmup: verify both servers are alive
    tx_info = await tx_client.call("board_info", {})
    rx_info = await rx_client.call("board_info", {})
    print(f"  TX server: role={tx_info.get('role')} fw={tx_info.get('fw')} "
          f"port={tx_info.get('port')}", flush=True)
    print(f"  RX server: role={rx_info.get('role')} fw={rx_info.get('fw')} "
          f"port={rx_info.get('port')}", flush=True)
    if not tx_info.get("alive"):
        print("WARNING: TX board not alive — calling board_swd_reset",
              flush=True)
        await tx_client.call("board_swd_reset", {})
    if not rx_info.get("alive"):
        print("WARNING: RX board not alive — calling board_swd_reset",
              flush=True)
        await rx_client.call("board_swd_reset", {})

    # CSV/MD output paths
    out_dir = args.out or os.path.dirname(os.path.dirname(_TOOLS_DIR))
    ts_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(out_dir, f"campaign-{args.stop_id}-{ts_str}.csv")
    md_path = os.path.join(out_dir, f"campaign-{args.stop_id}-{ts_str}.md")

    import csv
    state = camp.CampaignState(args.state) if args.state else None
    session_id = int(datetime.now().strftime("%y%m%d%H%M"))

    csv_f = open(csv_path, "w", newline="")
    csv_w = csv.writer(csv_f)
    csv_w.writerow(camp.CAMPAIGN_CSV_FIELDS)

    results = []
    prev_cfg = None
    try:
        for i, cfg in enumerate(cfgs):
            print(f"  [{i+1}/{len(cfgs)}] {cfg['label']} ... ",
                  end="", flush=True)
            # Per-config SWD reset between configs (if policy says so)
            if prev_cfg is not None and camp.maybe_reset(prev_cfg, cfg, args.reset_policy):
                await tx_client.call("board_swd_reset", {})
                await rx_client.call("board_swd_reset", {})
            res = await cvm_sprt_run(cfg, tx_client, rx_client,
                                     session_id=session_id, cfg_idx=i,
                                     n_cap=args.n_cap)
            results.append((cfg, res))
            camp.write_csv_row(csv_w, args.stop_id, args.distance, args.mode,
                                i, cfg, res)
            csv_f.flush()
            print(f"{res.verdict} k={res.k}/{res.n}", flush=True)
            if state:
                state.record_verdict(args.stop_id, args.distance,
                                     cfg["label"], res.verdict, res.k, res.n)
            prev_cfg = cfg
    finally:
        csv_f.close()
        if state:
            state.commit()
        camp.write_md_report(md_path, args.stop_id, args.distance, args.mode,
                              results, state)
        print(f"\nCSV: {csv_path}")
        print(f"Report: {md_path}")
        await tx_client.close()
        await rx_client.close()
    return 0


def main():
    args = _parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
