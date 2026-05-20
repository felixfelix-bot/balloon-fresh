# NostrServerTransport Configuration

## Complete Options Interface

```typescript
interface NostrServerTransportOptions {
  // Required
  signer: NostrSigner;
  relayHandler: RelayHandler | string[];

  // Optional - Server metadata
  serverInfo?: ServerInfo;

  // Optional - Discovery
  isPublicServer?: boolean;
  publishRelayList?: boolean;
  relayListUrls?: string[];
  bootstrapRelayUrls?: string[];

  // Optional - Access control
  allowedPublicKeys?: string[];
  excludedCapabilities?: CapabilityExclusion[];

  // Optional - Features
  injectClientPubkey?: boolean;
  encryptionMode?: EncryptionMode;
  logLevel?: LogLevel;
}
```

## ServerInfo

```typescript
interface ServerInfo {
  name?: string; // Human-readable name
  picture?: string; // Icon URL
  website?: string; // Website URL
  about?: string; // Description
}
```

## CapabilityExclusion

```typescript
interface CapabilityExclusion {
  method: string; // e.g., "tools/call", "tools/list"
  name?: string; // Specific tool/resource name
}
```

## EncryptionMode

- `OPTIONAL` (default) - Use encryption if client supports it
- `REQUIRED` - Only accept encrypted connections
- `DISABLED` - Never use encryption

## Discoverability Options

- `isPublicServer` - Publishes public discoverability metadata
- `publishRelayList` - TypeScript SDK option that publishes `kind:10002` relay-list metadata unless explicitly disabled
- `relayListUrls` - Explicit relay URLs to advertise in the relay list
- `bootstrapRelayUrls` - Extra relays where discoverability events are published without advertising them as operational relays

## LogLevel

- `debug` - Detailed tracing
- `info` - Lifecycle events
- `warn` - Unexpected situations
- `error` - Failures
- `silent` - No logging
