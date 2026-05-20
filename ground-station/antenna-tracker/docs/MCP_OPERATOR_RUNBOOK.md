# MCP Operator Runbook

Date: 2026-03-12
Environment: Linux (bash)

This document summarizes the correct, modern way to:

- Expose the `mcp-antenna` server over Nostr
- Interact with it using CVMI
- Avoid common runtime and PATH issues

---

# 1. Architecture Overview

```
mcp-antenna (Rust MCP server)
        ↓ (stdio)
cvmi serve (Gateway layer)
        ↓ (Nostr relays)
cvmi call (Client)
```

Key points:

- CVMI replaces legacy `gateway-cli`
- CVMI must be run under Deno (not Node)
- The Rust server must correctly implement MCP initialize lifecycle

---

# 2. Correct Way to Start the MCP Gateway

## ✅ DO THIS

```bash
export PATH="$HOME/.deno/bin:$PATH"
deno run -A npm:cvmi serve ./mcp-antenna/target/release/mcp-antenna
```

Expected output:

```
Generated new private key
Public key: <hex>
Connected to Nostr relays
Gateway started
```

The printed hex value is your server's public key.

---

## ❌ Do NOT Do This

```bash
npx cvmi serve ...
```

This fails under Node with:

```
WebSocket is not defined
```

Reason: Node does not provide a global WebSocket implementation.

---

# 3. Correct Way to Start the MCP Client

In another terminal:

```bash
export PATH="$HOME/.deno/bin:$PATH"
deno run -A npm:cvmi call <server_pubkey>
```

Example:

```bash
deno run -A npm:cvmi call 6c090672a1c3b87a3b6d0f664a8e24d937bc456da1e30e4a3e8db927f23124a0
```

To call a specific tool:

```bash
deno run -A npm:cvmi call <pubkey> <tool> param=value
```

---

# 4. PATH Fixes (Common Issue)

If `deno` is not found:

```bash
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

If `cvmi` was installed globally via npm and not found:

```bash
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

# 5. Common Errors and Their Meaning

## WebSocket is not defined

Cause:
- Running CVMI under Node instead of Deno

Fix:
- Use `deno run -A npm:cvmi`

---

## expect initialized request

Cause:
- MCP server not completing initialize lifecycle
- Server exiting after first request

Fix:
- Ensure Rust server implements full MCP protocol handshake
- Server must remain alive after initialize

---

## connection closed / EPIPE

Cause:
- Rust MCP server exited
- Stdio pipe closed

Fix:
- Fix MCP server lifecycle implementation

---

# 6. Testing MCP Server Without Nostr

To test initialize handshake directly:

```bash
echo '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{}}' \
  | ./mcp-antenna/target/release/mcp-antenna
```

If the server exits immediately, lifecycle implementation is incorrect.

---

# 7. Final Recommended Workflow

Terminal 1:

```bash
deno run -A npm:cvmi serve ./mcp-antenna/target/release/mcp-antenna
```

Terminal 2:

```bash
deno run -A npm:cvmi call <pubkey>
```

---

# 8. Summary of Learnings

- ✅ CVMI replaces legacy gateway-cli
- ✅ Must use Deno runtime
- ✅ Node causes WebSocket errors
- ✅ PATH configuration is critical
- ✅ MCP server must correctly implement initialize lifecycle
- ✅ Nostr transport was functioning correctly

---

End of runbook.
