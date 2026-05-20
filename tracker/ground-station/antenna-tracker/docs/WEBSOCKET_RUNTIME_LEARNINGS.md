# WebSocket Runtime Learnings

## 1. Root Cause

`cvmi` assumes a Node 20+ environment where `WebSocket` is globally available.

Running via `bunx` or certain execution contexts may not expose `WebSocket` globally, resulting in:

```
WebSocket is not defined
```

This is a runtime environment mismatch — not a networking issue.

## 2. What Was NOT The Problem

- Network connectivity (confirmed via `nak` to Nostr relays)
- TLS or DNS
- Rust MCP server binary
- Relay availability

The failure occurred before any network call.

## 3. Working Solution

Use Node 20 and preload a WebSocket shim when necessary:

```
NODE_OPTIONS="--require ./cvmi-wrapped.js" npx cvmi serve <binary>
```

This guarantees `WebSocket` exists in the Node runtime before `cvmi` executes.

## 4. Script Fixes

- `run-cvmi.sh` uses `NODE_OPTIONS` preload
- `scripts/dev_serve_and_call.sh` updated to use the same wrapped approach
- Startup detection now waits for `Public key:` instead of obsolete `Gateway started`

## 5. Current Server Status

### Rust MCP Server (`mcp-antenna`)

- The Rust binary builds and runs correctly.
- It connects to the Nostr relays successfully.
- The gateway starts and publishes a public key.
- **However, tools are not currently visible/exposed through the gateway.**

This indicates that while transport is functioning, tool registration or exposure in the Rust implementation is incomplete or not wired correctly to the gateway layer.

### TypeScript MCP Server (`ts/src/server.ts`)

- Runs correctly in the browser environment.
- Successfully exposes tools.
- Tools are visible and callable via the gateway.

This confirms that the transport + gateway + protocol flow is working end-to-end. The difference is in how tools are registered/exposed between the Rust and TypeScript implementations.

## 6. Architectural Insight

- Transport layer (Nostr relays + gateway) is functioning.
- Runtime mismatch (Bun vs Node) was the original WebSocket issue.
- Tool visibility issue is specific to the Rust MCP server implementation.

The TypeScript server serves as a known-good reference implementation for tool exposure.
## 5. Best Practice Going Forward

- Use Node for `cvmi`
- Avoid mixing Bun/Deno for tools expecting Node Web APIs
- Do not rely on global Web APIs being present unless explicitly guaranteed by the runtime

## 7. General Lesson

When encountering `X is not defined` in JS CLIs:

1. Verify runtime (`node -v`, `bun --version`)
2. Test global availability (`node -e "console.log(typeof WebSocket)"`)
3. Confirm whether failure occurs before network activity

Most CLI runtime bugs are environment mismatches — not connectivity failures.
