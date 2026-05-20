// CJS shim so it can be loaded via NODE_OPTIONS=--require
const WS = require("ws");

global.WebSocket = WS;
globalThis.WebSocket = WS;
