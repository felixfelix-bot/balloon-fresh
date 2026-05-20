import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  NostrServerTransport,
  PrivateKeySigner,
  ApplesauceRelayPool,
} from "@contextvm/sdk";
import { z } from "zod";
import { SerialPort } from "serialport";

// Static NSEC (hex private key)
// nsec: nsec1avgzrt4wcc8jhmcnckytuguntdwaa9rum4gjp87rtzw7dv2r8casqe5cjq
// hex:  eb1021aeaec60f2bef13c588be23935b5dde947cdd51209fc3589de6b1433e3b
const privateKey = "eb1021aeaec60f2bef13c588be23935b5dde947cdd51209fc3589de6b1433e3b";

const signer = new PrivateKeySigner(privateKey);

// Use MCP-friendly relays only (avoid general public social relays like damus)
const relayPool = new ApplesauceRelayPool([
  "wss://relay.contextvm.org",
  "wss://cvm.otherstuff.ai",
]);

// Default to ttyUSB1 since that is what we validated manually
const SERIAL_PATH = process.env.ANTENNA_SERIAL ?? "/dev/ttyUSB0";
const BAUD = 115200;

// --- Serial Setup ---
const port = new SerialPort({
  path: SERIAL_PATH,
  baudRate: BAUD,
});

port.on("open", () => {
  console.log("Serial connected:", SERIAL_PATH);
});

port.on("error", (err) => {
  console.error("Serial port error:", err.message);
  console.error(
    `Make sure the device exists and is not in use. Current path: ${SERIAL_PATH}`
  );
});

// Buffer incoming serial data by line
let serialBuffer = "";
type PendingResolver = {
  prefix: string;
  resolve: (line: string) => void;
};

const pendingResolvers: PendingResolver[] = [];

port.on("data", (data: Buffer) => {
  const text = data.toString("utf8");

  // Print raw serial output immediately (picocom-style)
  process.stdout.write(text);

  serialBuffer += text;

  const lines = serialBuffer.split("\n");
  serialBuffer = lines.pop() || "";

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    // Resolve any pending waiters
    for (let i = 0; i < pendingResolvers.length; i++) {
      const pending = pendingResolvers[i];
      if (line.includes(pending.prefix)) {
        pending.resolve(line);
        pendingResolvers.splice(i, 1);
        i--;
      }
    }
  }
});

const server = new McpServer({
  name: "antenna-tracker-server",
  version: "0.1.0",
});

// ---- Move Antenna Tool ----
server.registerTool(
  "move_antenna",
  {
    description: "Move antenna azimuth and elevation",
    inputSchema: z.object({
      azimuth_steps: z.number().optional(),
      elevation_steps: z.number().optional(),
    }),
  },
  async ({ azimuth_steps, elevation_steps }) => {
    console.log("[MCP] move_antenna called with:", {
      azimuth_steps,
      elevation_steps,
    });

    const responses: string[] = [];

    const waitForResponse = (expectedPrefix: string) =>
      new Promise<string>((resolve) => {
        pendingResolvers.push({
          prefix: expectedPrefix,
          resolve,
        });
      });

    if (azimuth_steps !== undefined) {
      console.log(`[SERIAL] -> AZ ${azimuth_steps}`);
      port.write(`AZ ${azimuth_steps}\n`);
      const resp = await waitForResponse("AZ done");
      responses.push(resp);
    }

    if (elevation_steps !== undefined) {
      console.log(`[SERIAL] -> EL ${elevation_steps}`);
      port.write(`EL ${elevation_steps}\n`);
      const resp = await waitForResponse("EL done");
      responses.push(resp);
    }

    return {
      content: [
        {
          type: "text",
          text: `Move completed: ${responses.join(", ")}`,
        },
      ],
    };
  }
);

// ---- Echo Tool (debug) ----
server.registerTool(
  "echo",
  {
    description: "Echo back the provided message",
    inputSchema: z.object({
      message: z.string(),
    }),
  },
  async ({ message }) => {
    console.log("[MCP] echo called with:", { message });
    return {
      content: [{ type: "text", text: `Echo: ${message}` }],
    };
  }
);

const transport = new NostrServerTransport({
  signer,
  relayHandler: relayPool,
  isPublicServer: false,
  serverInfo: {
    name: "Antenna Tracker MCP Server",
    about: "Controls ESP32 antenna tracker over serial",
  },
});

await server.connect(transport);

console.log("Antenna MCP server connected over Nostr");
