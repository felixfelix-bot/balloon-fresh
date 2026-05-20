import { spawn } from "bun"
import { WebSocket } from "ws"

// Ensure WebSocket is available globally for cvmi
globalThis.WebSocket = WebSocket
// Some libraries reference global instead of globalThis
// @ts-ignore
global.WebSocket = WebSocket

spawn({
  // Use bunx to resolve cvmi from npm
  cmd: ["bunx", "cvmi", "serve", "./mcp-antenna/target/release/mcp-antenna"],
  stdout: "inherit",
  stderr: "inherit",
  stdin: "inherit",
})
