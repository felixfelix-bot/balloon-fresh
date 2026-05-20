// Ensure WebSocket is available globally in Node
try {
  const WebSocket = require("ws");
  if (typeof globalThis.WebSocket === "undefined") {
    globalThis.WebSocket = WebSocket;
  }
} catch (err) {
  console.error("Failed to load 'ws' package:", err.message);
  process.exit(1);
}

// This file is intended to be used with NODE_OPTIONS=--require
// Do not launch anything from here.
