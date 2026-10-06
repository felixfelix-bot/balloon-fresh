# NIP-29 Relay Sharing — Hermes Handover Guide

**Version:** 2026-08-19
**Audience:** A friend who already runs their own Hermes instance and wants to exchange context with Felix's Hermes via a shared NIP-29 relay.
**TL;DR:** You'll generate a Nostr keypair, point your Hermes Nostr adapter at a shared relay, and Felix will add your pubkey to a NIP-29 group. After that, both Hermes instances can send and receive kind 9 chat events in real time.

---

## 1. What We're Building

Two independent Hermes instances — yours and Felix's — connected to the same NIP-29 relay. Each instance runs a **Nostr platform adapter** that:

- Subscribes to one or more **NIP-29 groups** on the relay
- Publishes **kind 9 (chat) events** to those groups when the Hermes agent wants to share context
- Receives kind 9 events published by the other instance and feeds them into the local Hermes as incoming messages

This gives both instances a real-time, push-based channel for exchanging coordination messages, status updates, and context snippets — no polling, no shared filesystem required.

**Key properties:**
- Each Hermes has its own Nostr identity (nsec/npub keypair)
- Relay membership is enforced at the relay level (strfry29 rejects events from non-member pubkeys)
- The adapter skips self-echo (you won't see your own messages come back)
- 30-second automatic reconnection if the WebSocket drops

---

## 2. Architecture

```
┌─────────────────┐                    ┌──────────────────────────┐                    ┌─────────────────┐
│   Your Hermes    │                    │      Shared Relay        │                    │  Felix's Hermes  │
│   (friend)       │                    │                          │                    │                  │
│                  │   WebSocket (ws/wss)│                          │ WebSocket (ws/wss) │                  │
│  ┌────────────┐  │◄──────────────────►│      strfry29 / Buzz     │◄─────────────────►│  ┌────────────┐  │
│  │ Nostr      │  │                    │                          │                    │  │ Nostr      │  │
│  │ Adapter    │  │    kind 9 events   │   NIP-29 group routing   │   kind 9 events   │  │ Adapter    │  │
│  │            │──────────────────────►│                          │◄──────────────────│  │            │  │
│  └────────────┘  │                    │                          │                    │  └────────────┘  │
│                  │                    │   Membership enforcement │                    │                  │
│  nsec: friend    │                    │   (kind 9000 put-user)   │                    │  nsec: felix     │
│  npub: shared    │                    │                          │                    │  npub: shared    │
└─────────────────┘                    └──────────────────────────┘                    └─────────────────┘
```

### Relay URL Options

| Option | URL | Network | Auth | Notes |
|--------|-----|---------|------|-------|
| strfry29 on T470 | `ws://100.90.101.9:7780` | Tailscale/Netbird | None | Felix's laptop. Fast, no NIP-42 needed. |
| strfry29 on DQ05 | `ws://100.90.22.201:7780` | Tailscale/Netbird | None | Felix's mini PC. Same config as T470. |
| Buzz on VPS2 | `wss://relay.orangesync.tech` | Clearnet (public) | **NIP-42 AUTH required** | Use this if you're NOT on the Tailscale/Netbird mesh. Requires adapter patch (see Step 3b). |

**Recommendation:** Use the strfry29 relay if you have Tailscale/Netbird access. It's simpler (no NIP-42 AUTH patch needed) and lower latency.

---

## 3. Prerequisites

Before you start, make sure you have:

### 3.1 Your Own Hermes Instance
Your Hermes should already be installed and running (you can see it respond to messages). This guide assumes you have a working `~/.hermes/` directory with a `.env` file.

### 3.2 The Hermes Nostr Adapter
The Nostr platform adapter is **NOT** in the upstream `NousResearch/hermes-agent` repository yet. It lives in Felix's fork:

- **Repository:** `felixfelix-bot/hermes-agent`
- **Branch:** `main` (commit `a480d7fbe`, merged Aug 12 2026)
- **File:** `gateway/platforms/nostr.py`
- **What it does:** Extends `BasePlatformAdapter`, connects to strfry NIP-29 relays via WebSocket, handles kind 9 events, manages subscriptions, and provides a 30s reconnection watcher.

You'll need to clone this fork (or cherry-pick `nostr.py` into your existing Hermes installation). See Step 1.

### 3.3 `nak` CLI (Nostr Tool)
`nak` is a command-line Nostr utility written in Go. You'll use it for key generation and optionally for manual event testing.

```bash
# Install nak (if not already installed)
# Option A: Download a prebuilt binary from https://github.com/0xchat-app/nak/releases
# Option B: Build from source
go install github.com/0xchat-app/nak@latest
```

**Verify:**
```bash
nak --version
```

> **Note on nak version:** nak v0.18.6 has NO `--relay` flag. The relay URL is passed as a **positional argument** (e.g., `nak event ... ws://relay:7780`). Use `--auth` for NIP-42 authentication when talking to the Buzz relay.

### 3.4 Python 3.11+ with Required Packages
The Nostr adapter depends on:
- **`coincurve`** — for BIP-340 Schnorr signatures (Nostr event signing). This replaces the heavier `pynostr` library.
- **`websockets`** — for WebSocket connections to the relay.

```bash
pip install coincurve websockets
```

### 3.5 Network Access
Ensure your machine can reach the chosen relay:
- **strfry29 (Tailscale/Netbird):** You must be on the same Tailscale or Netbird network as Felix's machines. Test with `curl -v http://100.90.101.9:7780/` (expect a WebSocket upgrade response or at least a TCP connection).
- **Buzz relay (clearnet):** Any internet connection works. Test with `curl -v https://relay.orangesync.tech/`.

---

## 4. Step 1: Get the Nostr Adapter

The Nostr adapter file lives at `gateway/platforms/nostr.py` in Felix's fork. You have two options:

### Option A: Clone the Fork (Full Hermes Installation)

```bash
# Clone Felix's fork
git clone https://github.com/felixfelix-bot/hermes-agent.git
cd hermes-agent
git checkout main   # commit a480d7fbe or later

# Install in development mode
pip install -e .

# Verify the adapter exists
ls -la gateway/platforms/nostr.py
```

### Option B: Cherry-Pick into Your Existing Hermes

If you prefer to keep your current Hermes installation and just add the adapter:

```bash
cd /path/to/your/hermes-agent
# Fetch the fork
git remote add felix https://github.com/felixfelix-bot/hermes-agent.git
git fetch felix main

# Cherry-pick the commit that added the Nostr adapter
git cherry-pick a480d7fbe

# Verify
ls -la gateway/platforms/nostr.py
```

If you encounter merge conflicts, you can also just copy the single file:

```bash
# Fetch the raw file
curl -O https://raw.githubusercontent.com/felixfelix-bot/hermes-agent/main/gateway/platforms/nostr.py
mv nostr.py gateway/platforms/nostr.py
```

**Verify the adapter loads:**
```bash
python -c "from gateway.platforms.nostr import NostrAdapter; print('Nostr adapter import OK')"
```

If you see `ImportError`, make sure `coincurve` and `websockets` are installed in the same Python environment that Hermes uses.

---

## 5. Step 2: Generate a Keypair

Your Hermes instance needs its own Nostr identity. **Do NOT reuse Felix's keys.** Each instance gets its own keypair.

### 5.1 Generate the Private Key

```bash
nak key generate
```

This outputs:
```
nsec1<...a long bech32 string...>
```

> ⚠️ **CRITICAL:** `nak key generate` outputs the **private key** (nsec). Keep this secret. Never share it with anyone, including Felix. The nsec is stored on your machine only.

### 5.2 Derive the Public Key

```bash
# From nsec to npub
nak key convert <your-nsec1...>
```

This outputs:
```
npub1<...a shorter bech32 string...>
```

### 5.3 Derive the HEX Public Key (for relay membership)

The relay needs your **public key in HEX format** (64 hex characters) to add you as a group member. You can derive it with Python:

```python
python3 -c "
from coincurve import PrivateKey
import hashlib

# Paste your nsec hex here (convert nsec to hex first, or use the raw hex)
# If you have the raw 32-byte private key hex:
priv_hex = '<your-private-key-hex>'
priv = PrivateKey(bytes.fromhex(priv_hex))
pub = priv.public_key.format(compressed=False)
pub_hex = pub[1:33].hex()  # X coordinate (32 bytes) for BIP-340
print('Public key hex:', pub_hex)
"
```

Alternatively, use `nak`:
```bash
nak key convert <your-nsec1...>
# If nak outputs hex, use that. Otherwise use the Python method above.
```

> **What to share with Felix:** Send him your **npub** and/or **HEX public key**. Keep your **nsec** private.

### 5.4 Save the nsec File

Create a file containing only the nsec string:

```bash
mkdir -p ~/.hermes/keys
echo -n "nsec1<your-nsec-string>" > ~/.hermes/keys/nostr_nsec.txt
chmod 600 ~/.hermes/keys/nostr_nsec.txt
```

The file should contain **only** the bech32 nsec string, nothing else — no newline, no comments, no JSON wrapper.

---

## 6. Step 3: Relay Configuration

Choose one of the two relay options based on your network access.

### Step 3a: Felix's strfry29 Relay (Tailscale/Netbird)

If you're on the same Tailscale or Netbird mesh network as Felix, use one of these:

| Host | URL | Machine |
|------|-----|---------|
| T470 | `ws://100.90.101.9:7780` | Felix's laptop |
| DQ05 | `ws://100.90.22.201:7780` | Felix's mini PC |

**Test connectivity:**
```bash
# Quick TCP reachability check
curl -v --max-time 5 http://100.90.101.9:7780/
# Expect: HTTP 426 Upgrade Required or similar WebSocket response
```

If both relays are reachable, pick either one (they sync via the same backend). If only one is up, ask Felix which to use.

**No NIP-42 AUTH patch needed** — strfry29 relays don't require WebSocket authentication.

### Step 3b: Buzz Relay on VPS2 (Clearnet)

If you're **NOT** on the Tailscale/Netbird mesh, use the public Buzz relay:

| Host | URL | Network |
|------|-----|---------|
| VPS2 | `wss://relay.orangesync.tech` | Clearnet (public internet) |

**Test connectivity:**
```bash
curl -v --max-time 5 https://relay.orangesync.tech/
```

#### ⚠️ CRITICAL: NIP-42 AUTH Patch Required

The Buzz relay requires **NIP-42 authentication** for WebSocket connections. The Hermes Nostr adapter (`gateway/platforms/nostr.py`) does **NOT** implement NIP-42 AUTH out of the box. You **must** patch the adapter before it will work with the Buzz relay.

**What NIP-42 AUTH does:** When the client opens a WebSocket to the relay, the relay sends an `AUTH` challenge event (kind 22242). The client must sign this challenge with its nsec and send the signed event back. Only then can the client subscribe (REQ) and publish events.

**The patch you need to apply to `gateway/platforms/nostr.py`:**

1. After opening the WebSocket connection, listen for an `AUTH` challenge:
   - The relay sends: `["AUTH", "<challenge-string>"]`
2. When you receive the AUTH challenge:
   - Build a kind 22242 event:
     - `kind`: 22242
     - `tags`: `[["relay", "<relay-url>"], ["challenge", "<challenge-string>"]]`
     - `content`: empty string `""`
     - `pubkey`: your public key (derived from nsec)
     - `created_at`: current Unix timestamp
   - Sign the event with your nsec (using `coincurve` for BIP-340 Schnorr signature)
   - Send the signed event to the relay: `["AUTH", <signed-event-json>]`
3. After sending the AUTH event, proceed with your normal `REQ` subscription.

**Pseudocode for the patch:**

```python
# In the WebSocket connect/handshake logic:
async def handle_auth_challenge(self, ws, challenge, relay_url):
    """Handle NIP-42 AUTH challenge from relay."""
    event = {
        "kind": 22242,
        "pubkey": self.pubkey_hex,
        "created_at": int(time.time()),
        "tags": [
            ["relay", relay_url],
            ["challenge", challenge],
        ],
        "content": "",
    }
    # Sign with coincurve (BIP-340 Schnorr)
    event_id = compute_event_id(event)
    event["sig"] = self.sign_schnorr(event_id)
    event["id"] = event_id
    await ws.send(json.dumps(["AUTH", event]))
    # Wait for OK response before proceeding
```

**Reference:** [NIP-42 specification](https://github.com/nostr-protocol/nips/blob/master/42.md)

If you're not comfortable patching the adapter, **use the strfry29 relay instead** (Step 3a) — it doesn't require NIP-42.

---

## 7. Step 4: Felix Adds Your Pubkey as a Group Member

This step is performed by **Felix** (the relay admin). You don't run these commands — but you need to understand what happens so you can troubleshoot.

### What Felix Does:

1. **Creates a NIP-29 group** (kind 9007) with a fresh UUID-v4 as the `h` tag:

```bash
GROUP_ID=$(uuidgen)
nak event --sec <felix-admin-nsec> -k 9007 -t "h=$GROUP_ID" -c "" ws://100.90.101.9:7780
```

2. **Adds your pubkey as a member** (kind 9000):

> ⚠️ **CRITICAL:** The `p` tag must contain your **PUBLIC KEY hex** (64 hex characters), NOT your private key hex and NOT your npub. `nak key generate` outputs a PRIVATE key — Felix must use your **public** key.

```bash
# WRONG — this uses private key hex (will be rejected or silently fail):
nak event --sec <felix-admin-nsec> -k 9000 -t "h=$GROUP_ID" -t "p=<your-PRIVATE-key-hex>" -c "" ws://100.90.101.9:7780

# CORRECT — uses PUBLIC key hex:
nak event --sec <felix-admin-nsec> -k 9000 -t "h=$GROUP_ID" -t "p=<your-PUBLIC-key-hex>" -c "" ws://100.90.101.9:7780
```

> ⚠️ **strfry29 put-user tag format:** The role is the **3rd element of the p tag**, NOT a separate tag. The correct format is: `["p", "<hex_pubkey>", "member"]`. However, `nak` CLI cannot build multi-element tags with `-t "p=<pubkey>,member"` — it treats the entire value as a single string. Felix should use a Python/websockets script or the `buzz` CLI instead if a role is needed.

**What you need to send Felix:**
- Your **HEX public key** (64 hex characters) — so he can add you as a group member
- Or your **npub** — he can convert it to hex himself

After Felix creates the group and adds your pubkey, he'll send you:
- The **group ID** (a UUID-v4 string, e.g., `a1b2c3d4-...`)
- The **relay URL** to connect to

---

## 8. Step 5: Configure Hermes

Edit your `~/.hermes/.env` file and add the following environment variables:

```bash
# Nostr adapter configuration
NOSTR_RELAYS=ws://100.90.101.9:7780
NOSTR_GROUPS=a1b2c3d4-e5f6-7890-abcd-ef1234567890
NOSTR_NSEC_PATH=/home/youruser/.hermes/keys/nostr_nsec.txt
```

### Variable Reference

| Variable | Value | Notes |
|----------|-------|-------|
| `NOSTR_RELAYS` | Comma-separated relay URLs | e.g., `ws://100.90.101.9:7780` or `wss://relay.orangesync.tech`. Multiple relays allowed. |
| `NOSTR_GROUPS` | Comma-separated group UUIDs | The group IDs Felix created and added you to. e.g., `shared-coordination,project-alpha`. |
| `NOSTR_NSEC_PATH` | Absolute path to nsec file | File must contain **only** the bech32 nsec string (e.g., `nsec1...`). No newlines, no JSON. |

### nsec File Requirements

```bash
# The file should contain ONLY the nsec string:
cat ~/.hermes/keys/nostr_nsec.txt
# Output: nsec1<...>

# Permissions MUST be 600 (owner read/write only):
chmod 600 ~/.hermes/keys/nostr_nsec.txt
ls -la ~/.hermes/keys/nostr_nsec.txt
# -rw------- 1 youruser youruser ... nostr_nsec.txt
```

> **Important:** The nsec file must be readable by the **user account that runs the Hermes gateway process**. If Hermes runs as a systemd service under a different user, ensure that user has read access to the file (or place the file in a directory the service user can read).

### Multiple Groups

If Felix created multiple groups for you, list them all:

```bash
NOSTR_GROUPS=shared-coordination,project-alpha,project-beta
```

The adapter will subscribe to all listed groups simultaneously.

### Full .env Example

```bash
# Existing Hermes config...
HERMES_MODEL=glm-5.3
# ... (your existing settings)

# Nostr adapter
NOSTR_RELAYS=ws://100.90.101.9:7780
NOSTR_GROUPS=a1b2c3d4-e5f6-7890-abcd-ef1234567890
NOSTR_NSEC_PATH=/home/youruser/.hermes/keys/nostr_nsec.txt
```

---

## 9. Step 6: Restart and Verify

### 9.1 Restart the Gateway

How you restart depends on how you run Hermes:

**If using systemd:**
```bash
sudo systemctl restart hermes-gateway
# Or whatever your service name is
```

**If running manually:**
```bash
# Stop the current process (Ctrl+C or kill)
# Then restart:
cd /path/to/hermes-agent
python -m gateway.main
```

### 9.2 Check Gateway Logs

Look for these success indicators in the logs:

```bash
# If using systemd:
journalctl -u hermes-gateway -f --since "1 min ago"

# If running manually, check the console output or log file:
tail -f /path/to/hermes/logs/gateway.log
```

**Success indicators:**
```
Nostr adapter connected to relay ws://100.90.101.9:7780
Channel directory built: 3 target(s)
```

**Failure indicators (and what to check):**
| Error message | Likely cause | Fix |
|---------------|--------------|-----|
| `Connection refused` | Relay unreachable or wrong URL | Verify network access, check relay URL |
| `AUTH required` or `NIP-42` errors | Using Buzz relay without AUTH patch | Apply the NIP-42 AUTH patch (Step 3b) or switch to strfry29 |
| `unknown member` | Your pubkey not added to the group | Ask Felix to verify your pubkey hex was added correctly |
| `Permission denied` reading nsec file | File permissions or wrong user | `chmod 600` the nsec file; ensure gateway user can read it |
| `Invalid nsec format` | nsec file has extra characters | Ensure file contains only the nsec string, no trailing newline |
| `ModuleNotFoundError: coincurve` | Missing Python dependency | `pip install coincurve websockets` in the correct venv |

### 9.3 End-to-End Test

1. **Send a test message from your Hermes:**
   Ask your Hermes to send a message to the shared group (e.g., "Send a message to the Nostr group saying 'hello from friend'").

2. **Verify receipt on Felix's side:**
   Felix should see the kind 9 event arrive in his Hermes. He can check his gateway logs or ask his Hermes if it received a message.

3. **Send a test message from Felix's Hermes:**
   Felix sends a message to the shared group.

4. **Verify receipt on your side:**
   Check your logs for an incoming kind 9 event. Note: the adapter skips self-echo, so you won't see your own messages come back — only messages from the other instance.

```
# Expected log on receipt:
Received kind 9 event from <npub> in group <group-id>: "hello from felix"
```

If both directions work, you're done. Welcome to shared Hermes context exchange.

---

## 10. Shared Groups

### Suggested Group Structure

| Group | Purpose | Members |
|-------|---------|---------|
| `shared-coordination` | General coordination, status updates, "are you online?" messages | Both Hermes instances |
| `project-<name>` | Per-project context exchange (optional) | Both Hermes instances (or subset) |

### How Groups Work

- Each group is identified by a UUID-v4 string (the `h` tag in events)
- Felix creates groups using kind 9007 events (as relay admin)
- Felix adds members using kind 9000 events (put-user)
- Both Hermes instances subscribe to the groups listed in `NOSTR_GROUPS`
- Messages (kind 9) published to a group are only delivered to subscribed members

### Existing Groups on Felix's Relay

Felix already has these groups configured on the strfry29 relay (T470/DQ05):

- `balloon-orch`
- `balloon-track-1`
- `plebeian-orch`
- `plebeian-my-prs`
- `plebeian-reviews`
- `plebeian-adrs`
- `plebeian-track-1`

You can ask Felix to add you to any of these existing groups, or request a new shared coordination group.

---

## 11. Pitfalls

These are the top issues we've encountered. Read this section carefully — it will save you hours of debugging.

### 11.1 NIP-42 AUTH Required by Buzz Relay
- **Symptom:** `AUTH` error or `connection closed` immediately after connecting to `wss://relay.orangesync.tech`
- **Cause:** The Buzz relay requires NIP-42 AUTH. The Hermes Nostr adapter does NOT implement this out of the box.
- **Fix:** Patch the adapter to handle AUTH challenges (see Step 3b). Or use the strfry29 relay instead.

### 11.2 Private Key vs Public Key in p Tags
- **Symptom:** Felix adds you to a group, but your events are rejected with "unknown member"
- **Cause:** The `p` tag in the kind 9000 (put-user) event must contain the **PUBLIC KEY hex** (64 chars), not the private key hex. `nak key generate` outputs the private key — it's easy to accidentally use the wrong one.
- **Fix:** Derive the public key first (Step 2.3). Double-check: private key hex starts with a different pattern; public key hex is 64 characters of the X-coordinate of the public key point. When in doubt, use Python `coincurve` to derive and verify.

### 11.3 strfry29 put-user Tag Format
- **Symptom:** Member added but role not set, or member not recognized
- **Cause:** The role must be the **3rd element of the p tag**: `["p", "<hex_pubkey>", "member"]`. It's NOT a separate tag. The `nak` CLI's `-t "p=<pubkey>,member"` creates a 2-element tag `["p", "<pubkey>,member"]` where the comma is part of the value — this is WRONG.
- **Fix:** Use a Python/websockets script to build the event with the correct 3-element tag, or use the `buzz` CLI.

**Correct Python example for adding a member:**
```python
import asyncio
import websockets
import json
import time
from coincurve import PrivateKey

async def add_member(relay_url, admin_nsec_hex, group_id, friend_pubkey_hex, role="member"):
    # Build kind 9000 event
    event = {
        "kind": 9000,
        "pubkey": <admin_pubkey_hex>,
        "created_at": int(time.time()),
        "tags": [
            ["h", group_id],
            ["p", friend_pubkey_hex, role],  # 3-element tag!
        ],
        "content": "",
    }
    # Sign event (using coincurve for BIP-340)
    event_id = compute_event_id(event)
    event["id"] = event_id
    event["sig"] = sign_schnorr(admin_nsec_hex, event_id)

    async with websockets.connect(relay_url) as ws:
        await ws.send(json.dumps(["EVENT", event]))
        response = await ws.recv()
        print(f"Relay response: {response}")

asyncio.run(add_member(
    "ws://100.90.101.9:7780",
    "<admin-nsec-hex>",
    "<group-uuid>",
    "<friend-pubkey-hex>",
    "member"
))
```

### 11.4 Metadata Events Need Both `d` and `h` Tags
- **Symptom:** Group metadata (name, description, picture) not properly stored/deduplicated by strfry29
- **Cause:** Metadata events (kinds 39000–39003) need **both** a `d` tag (for NIP-33 parameterized replaceable event dedup) and an `h` tag (for NIP-29 group routing). Missing either causes dedup failures.
- **Fix:** Always include both tags in metadata events:
  ```json
  ["d", "<group-id>"],
  ["h", "<group-id>"]
  ```

### 11.5 strfry29 Rejects Events from Non-Member Pubkeys
- **Symptom:** Your Hermes publishes a kind 9 event, but the relay responds with `["OK", false, ..., "unknown member"]`
- **Cause:** strfry29 enforces membership at the relay level. If your pubkey hasn't been added to the group (via kind 9000 put-user), your events are rejected.
- **Fix:** Ask Felix to verify your pubkey hex was added to the correct group. Verify the hex matches your nsec-derived public key.

### 11.6 nsec File Must Be Readable by Gateway Process User
- **Symptom:** `Permission denied` error in logs when loading nsec
- **Cause:** The nsec file permissions or ownership don't allow the gateway process to read it
- **Fix:**
  ```bash
  chmod 600 ~/.hermes/keys/nostr_nsec.txt
  # If gateway runs as a different user:
  chown <gateway-user>:<gateway-user> ~/.hermes/keys/nostr_nsec.txt
  ```

### 11.7 Self-Echo Skip — You Won't See Your Own Messages
- **Symptom:** You send a message to the group, but don't see it come back in your own logs
- **Cause:** The Nostr adapter intentionally skips events published by itself (based on pubkey match). This prevents echo loops.
- **Fix:** This is by design. To verify your message was received, check the **other** Hermes instance's logs, not your own.

### 11.8 nak v0.18.6 Has NO `--relay` Flag
- **Symptom:** `nak event --relay ws://...` fails with "unknown flag"
- **Cause:** nak v0.18.6 uses a **positional argument** for the relay URL, not a flag.
- **Fix:**
  ```bash
  # CORRECT — relay URL is positional:
  nak event --sec <nsec> -k 9007 -t "h=<uuid>" -c "" ws://relay:7780

  # For NIP-42 AUTH (Buzz relay), use --auth:
  nak event --sec <nsec> -k 9 -t "h=<uuid>" --auth -c "hello" wss://relay.orangesync.tech
  ```

---

## 12. Security Notes

### 12.1 Key Hygiene
- **Never share your nsec with anyone** — including Felix. The nsec is your Hermes's private identity.
- **Share only your npub** (or HEX public key) with Felix for group membership.
- **Each Hermes instance must have its own nsec.** Do not reuse Felix's keys or share a key between instances. If one key is compromised, only that instance is affected.

### 12.2 Relay Membership Enforcement
- Relay membership is enforced at the **relay level**, not just client-side. strfry29 will reject events from pubkeys that haven't been added as group members.
- This means even if someone knows the relay URL and group ID, they cannot publish or subscribe without being an authorized member.

### 12.3 Admin Key Separation
- The **relay admin key** (held by Felix) is separate from individual member keys. The admin key is used to create groups (kind 9007) and add members (kind 9000). Member keys are used only for publishing (kind 9) and subscribing.
- You (the friend) do not have and do not need the admin key. Only Felix needs it.

### 12.4 WebSocket Security
- **strfry29 (Tailscale/Netbird):** Traffic is encrypted at the transport layer by Tailscale/Netbird's WireGuard tunnel. The `ws://` (unencrypted WebSocket) is fine because the underlying network is already encrypted.
- **Buzz relay (clearnet):** Uses `wss://` (TLS-encrypted WebSocket). Ensure your system's CA certificates are up to date.

### 12.5 nsec File Permissions
- The nsec file (`NOSTR_NSEC_PATH`) should have `600` permissions (owner read/write only).
- Never commit the nsec file to version control.
- Consider using a secrets manager or encrypted storage if your environment supports it.

---

## 13. Quick Reference Checklist

```
[ ] 1. Clone felixfelix-bot/hermes-agent (main branch) or cherry-pick nostr.py
[ ] 2. pip install coincurve websockets
[ ] 3. nak key generate → save nsec to ~/.hermes/keys/nostr_nsec.txt (chmod 600)
[ ] 4. Derive npub and HEX public key from nsec
[ ] 5. Send npub / HEX pubkey to Felix
[ ] 6. Felix creates group, adds your pubkey as member, sends you group ID + relay URL
[ ] 7. Add to ~/.hermes/.env:
      NOSTR_RELAYS=ws://<relay-url>:7780
      NOSTR_GROUPS=<group-uuid>
      NOSTR_NSEC_PATH=/home/<user>/.hermes/keys/nostr_nsec.txt
[ ] 8. If using Buzz relay (wss://relay.orangesync.tech): patch adapter for NIP-42 AUTH
[ ] 9. Restart Hermes gateway
[ ] 10. Check logs for "Nostr adapter connected to relay" and "Channel directory built"
[ ] 11. Send test message, verify receipt on the other side
[ ] 12. No auth errors, no "unknown member" rejections → done
```

---

## 14. What You Need from Felix

After completing this guide, you should only need to ask Felix for two things:

1. **"What's the relay URL?"** — He'll tell you `ws://100.90.101.9:7780` (T470) or `ws://100.90.22.201:7780` (DQ05) for Tailscale/Netbird, or `wss://relay.orangesync.tech` for clearnet (Buzz relay, needs NIP-42 patch).

2. **"What's my group ID?"** — He'll give you the UUID-v4 of the group he created and added your pubkey to. Put this in `NOSTR_GROUPS`.

Everything else in this guide is self-service — you can do it without Felix's involvement.

---

*Document generated 2026-08-19. Based on Hermes Nostr adapter commit a480d7fbe (felixfelix-bot/hermes-agent fork, main branch). NIP-29 spec: https://github.com/nostr-protocol/nips/blob/master/29.md. NIP-42 spec: https://github.com/nostr-protocol/nips/blob/master/42.md.*