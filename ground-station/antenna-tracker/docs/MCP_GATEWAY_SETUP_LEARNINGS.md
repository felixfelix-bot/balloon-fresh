# MCP Gateway Setup – Lessons Learned

Date: 2026-03-12
Environment: Linux (x86_64)

---

## 1. Gateway Command Name

The installed binary is:

```
gateway-cli
```

Not:

```
gateway
```

It was installed at:

```
/usr/local/bin/gateway-cli
```

To run the MCP server via ContextVM:

```bash
gateway-cli
```

---

## 2. Do NOT Use sudo

Running the setup script with `sudo` caused:

- Permission denied errors
- A panic in `sudo-rs`

Correct approach:

```bash
bash scripts/setup_gateway_and_build.sh
```

ContextVM installs user-level binaries. `sudo` is unnecessary and harmful.

---

## 3. Cargo Command Mistakes

Incorrect:

```bash
cargo -build --release
```

Correct:

```bash
cargo build --release
```

Incorrect:

```bash
cargo build --release -p .
```

Reason: `-p` expects a package name, not `.`.

Correct inside crate directory:

```bash
cargo build --release
```

---

## 4. Successful Build Results

From `mcp-antenna/`:

```bash
cargo build --release
cargo test
```

Results:

- ✅ Release build succeeded
- ✅ Tests compiled and executed
- ℹ️ No tests defined (0 tests run)

Binary location:

```
mcp-antenna/target/release/mcp-antenna
```

---

## 5. Successful Gateway Startup

Running:

```bash
gateway-cli
```

Observed:

- MCP server launched: `./mcp-antenna/target/release/mcp-antenna`
- Connected to multiple Nostr relays
- Initialization and announcements sent
- Occasional relay publish warnings (non-fatal)

This confirms:

- ✅ MCP binary executes correctly
- ✅ ContextVM transport connects
- ✅ Tool announcements broadcast successfully

---

## 7. Updated Gateway Recommendation (Use CVMI Instead of gateway-cli)

The original `gateway-cli` tool is functional but outdated in some environments.
The recommended modern approach is to use **CVMI** to expose the MCP server.

### Correct Way to Expose the Server

Do NOT use:

```bash
npx cvmi serve ./mcp-antenna/target/release/mcp-antenna
```

Under Node this fails with:

```
WebSocket is not defined
```

This is due to Node not providing a global WebSocket implementation expected by CVMI.

### ✅ Correct Method (Use Deno Runtime)

Use Deno to execute the npm package:

```bash
deno run -A npm:cvmi serve ./mcp-antenna/target/release/mcp-antenna
```

This avoids the WebSocket runtime issue.

When run successfully, you will see:

```
Generated new private key
Public key: <hex>
```

That hex value is your server’s public key.

---

### Bun Is NOT Required

Attempts to install Bun via snap (`snap install bun-js`) failed because:

- The snap package does not exist
- Bun is not required for CVMI

The correct and supported runtime for CVMI is:

- ✅ Deno
- ❌ Node (without polyfills)
- ❌ Bun (not required)

---

## Current Recommended Workflow

Expose server:

```bash
deno run -A npm:cvmi serve ./mcp-antenna/target/release/mcp-antenna
```

In another terminal, interact:

```bash
deno run -A npm:cvmi call <pubkey>
```

This is the most reliable setup going forward.

---
## 6. Current State

Working:

- MCP server builds
- Gateway CLI installed
- Nostr transport connects
- Tools are announced

Not yet implemented:

- Integration tests for antenna behavior
- Automated MCP tool invocation tests

---

## Recommended Next Steps

1. Add at least one integration test for mocked antenna interaction
2. Document available MCP tools exposed by `mcp-antenna`
3. Perform remote tool invocation test from a second client
4. Add a smoke-test script for repeatable verification
