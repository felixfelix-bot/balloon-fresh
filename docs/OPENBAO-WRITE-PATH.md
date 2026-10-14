# OpenBao write path — capability probe result (2026-10-14)

**Question:** can the node AppRole write a provider key into OpenBao (so a new
DeepInfra key can replace the doxed one, surviving `provideers.env`
re-materialization)?

**Answer: NO — and this is by design, not a misconfiguration.**

## What was probed (non-mutating; no key was written)

| Check | Result |
|---|---|
| AppRole login | ✅ token acquired, TTL 3599 s, renewable |
| Token policies | `default`, `fleet-node-cobrador` |
| `sys/capabilities` (self-introspection) | ❌ 403 Forbidden |
| `sys/policies/acl/<role>` (read policy) | ❌ 403 Forbidden |
| `GET secret/data/fleet/providers` (read) | ✅ **allowed** — 18 fields |
| `POST secret/data/fleet/_policy_probe_zz` (write) | ❌ **403 permission denied** |

## The policy, verbatim (roles/02-secrets-openbao/tasks/main.yml:174)

```hcl
path "secret/data/fleet/*"            { capabilities = ["read"] }
path "secret/data/nodes/<node>/*"     { capabilities = ["read"] }
```

**`read` only. No `create`, `update`, or `delete` anywhere.** The node AppRole
is architecturally read-only: a node can *consume* fleet secrets and can never
*author* them. A compromised node therefore cannot rewrite the fleet's keys —
which is precisely the property you would want.

## Consequence for the DeepInfra key

The key **cannot** be delivered through the node AppRole. And there is a second,
independent problem: **`OPENROUTER_API_KEY` and `DEEPINFRA_API_KEY` are read from
different places.**

- `DEEPINFRA_API_KEY` — present in OpenBao (`secret/data/fleet/providers`) ✅
- `OPENROUTER_API_KEY` — **absent** from OpenBao; the router falls back to the
  plaintext `.env` ❌

So even a successful write would not have fixed OpenRouter: that key has no
OpenBao home to write to.

## The sanctioned write path (operator, with a write-capable token)

Writes require `bao kv put`, which needs a token with `update` capability — the
**root token** or a dedicated write/admin AppRole. Neither is held by a node.

The established pattern already exists in the repo
(`roles/71-wifi-uplink-guard/tasks/main.yml:166`):

```bash
# on the OpenBao node, with a write-capable token
bao kv put secret/fleet/providers \
    DEEPINFRA_API_KEY=@- ... <<< "$NEW_KEY"
```

⚠️ **KV v2 caveat:** a `kv put` replaces the whole secret version. Writing only
`DEEPINFRA_API_KEY` deletes the other 17 fields unless they are all re-supplied.
The safe form reads the current data, merges the one changed field, and writes
the full set back.

Then re-materialize so the router picks it up:

```bash
systemctl --user restart openbao-env.service
# openbao-providers-reload.path fires on the file change -> try-restart zai-proxy
```

## Undoxed-key caveat (must not be lost)

Even with the key installed, `deepinfra` sits in the operator-excluded set
(`flat_router.py:2023`, "the opsec-flagged lanes PLUS deepinfra"). Installing an
undoxed key makes the lane *eligible* but not *active* — the exclusion must also
be lifted.
