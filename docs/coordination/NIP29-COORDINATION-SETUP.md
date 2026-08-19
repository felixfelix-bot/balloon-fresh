# Balloon NIP-29 Relay Coordination Setup

## Status: ACTIVE (2026-08-20)

All 10 balloon tracks now have NIP-29 identities and group membership on the strfry29 relay.

## Relay

- **Primary:** ws://100.90.101.9:7780 (strfry29 on T470, Tailscale)
- **Fallback:** ws://100.90.22.201:7780 (strfry29 on DQ05, Tailscale)
- **Admin key:** ~/.hermes/state/nip29-relay-nsec.key (pubkey: b37b05dd...)
- **Manager key:** BUZZ_PRIVATE_KEY in ~/.hermes/profiles/manager/.env (pubkey: 4ae5fe8e...)

## Groups (11 balloon groups)

| Group | Purpose | Members |
|-------|---------|---------|
| balloon-orch | Cross-track coordination — ALL tracks | 12 (10 tracks + manager + admin) |
| balloon-track-1 | Range/speed test coordination | 2 (manager + admin) |
| balloon-nostr | Nostr relay track | 2 |
| balloon-tollgate | Tollgate/Cashu track | 2 |
| balloon-pow | PoW/Mining track | 2 |
| balloon-fips | FIPS Mesh track | 2 |
| balloon-blossom | Blossom Server track | 2 |
| balloon-range-tests | Range Tests track | 2 |
| balloon-speed-tests | Speed Tests track | 2 |
| balloon-pre-stretching | Pre-stretching track | 2 |
| balloon-circuit-design | Circuit Design track | 2 |

## Track Identities

Each track has its own nsec key stored at `~/.hermes/keys/balloon-nip29/<track>.nsec`.

Config file: `~/.hermes/state/balloon-nip29-config.yaml`
Helper script: `~/.hermes/state/balloon-nip29-post.sh`

## Usage

### Post from a track identity

```bash
# Post to track's own group
~/.hermes/state/balloon-nip29-post.sh balloon-range-tests balloon-range-tests "Range test complete: 200/200 0CRC"

# Post to orchestrator group (cross-track visibility)
~/.hermes/state/balloon-nip29-post.sh balloon-range-tests balloon-orch "Range test results posted to track group"

# Post as manager
~/.hermes/state/balloon-nip29-post.sh manager balloon-orch "Orchestrator directive: all tracks report status"
```

### Read messages from a group

```bash
# Read recent messages from balloon-orch
nak req -k 9 -t h=balloon-orch ws://100.90.101.9:7780

# Read from a specific track group
nak req -k 9 -t h=balloon-range-tests ws://100.90.101.9:7780
```

## Message Protocol

- `[INTENT]` — Before starting work: "I plan to work on X"
- `[STATUS]` — After completing work: "Done X. Results: Y. Next: Z"
- `[BLOCKER]` — When blocked: "Blocked on X. Need Y from track Z"
- `[CHECK-IN]` — Periodic presence: "Track X active, current state: Y"

## What Worked

1. strfry29 relay infrastructure (deployed Jul 2026) works reliably
2. nak CLI handles all NIP-29 operations (group creation, membership, messaging)
3. Each track gets its own Nostr identity — separate from Signal identity
4. Cross-track coordination via balloon-orch group — all tracks can see all posts

## What Didn't Work

1. Other balloon track managers are NOT separate Hermes profiles — they're Signal group sessions on the same machine. They can't independently connect to the relay.
2. The manager (this profile) posts on behalf of all tracks using each track's nsec key.
3. NIP-29 adapter in hermes-agent is not yet wired into the gateway for auto-posting — all posting is manual via nak CLI.

## Next Steps

1. Wire NIP-29 posting into kanban task completion flow — auto-post [STATUS] when tasks complete
2. Set up a cron job to poll relay for cross-track messages and surface them in Signal
3. When other friends set up their own Hermes instances, share the handover guide (docs/nip29-relay-sharing-handover.md) and add their pubkeys to relevant groups
4. Consider auto-posting status summaries every 6h to balloon-orch