# Inventory — tollgate stack symbols referenced in app_task.cpp

Scope: `/home/c03rad0r/repos/balloon-fresh/tracker/firmware/main/app_task.cpp`
Search root: `/home/c03rad0r/repos/balloon-fresh/tracker/firmware/`
Kind: READ-ONLY audit. No file under `tracker/firmware/` was created, modified, formatted, staged, or touched.

Repo HEAD at audit time: `64b8923`
`git status --porcelain -- tracker/firmware/main/{app_task.cpp,tollgate_payment_proto.h,tollgate_payment_proto.c}` -> empty (all three tracked and clean in HEAD).

## HEADLINE FINDING

**ZERO tollgate symbols referenced in app_task.cpp are undefined.** All eight
tollgate-stack identifiers resolve to `#define`s, typedefs, or prototypes in
`main/relay_types.h` and `main/tollgate_payment_proto.h` — both of which already
exist in-tree and are tracked in HEAD. There is nothing for a downstream author
to supply: `tollgate_payment_proto.h` is already present and complete for the
symbol set app_task.cpp uses.

Two caveats that are NOT "undefined tollgate symbols" but ARE build-relevant:

1. **`CONFIG_ENABLE_TOLLGATE` is a Kconfig option, not a header symbol.**
   It is *declared* in `main/Kconfig.projbuild:141` and referenced (not defined)
   in app_task.cpp:32/114/145. It is a `config` stanza, so `#define` exists only
   in the generated `sdkconfig.h` when enabled — never in a checked-in header.
   This is the correct mechanism and is not a gap.

2. **The compiled artefact predates the tollgate integration.** As of this
   snapshot `tracker/firmware/sdkconfig:576` reads
   `# CONFIG_ENABLE_TOLLGATE is not set`, so the entire guarded block in
   app_task.cpp (lines 114-145) is compiled out and no `tollgate_*` symbol
   appears in any object. `sdkconfig.defaults.esp32s3:83` sets
   `CONFIG_ENABLE_TOLLGATE=y`, so a fresh esp32s3 build does enable it. The
   `nm` check below therefore proves nothing about definition status — it only
   shows the current artefact was configured with the block off.

## STEP 1 — SOURCE READ (own read, `cat -n`)

Command: `cat -n ~/repos/balloon-fresh/tracker/firmware/main/app_task.cpp`
File is 164 lines. Tollgate-guarded region: lines 114-145, driven by the
`#ifdef CONFIG_ENABLE_TOLLGATE` at line 32 and 114.

Mentions, verbatim from the read:

| app_task.cpp line | token |
|---|---|
| 32  | `#ifdef CONFIG_ENABLE_TOLLGATE` |
| 33  | `#include "tollgate_payment_proto.h"` |
| 114 | `#ifdef CONFIG_ENABLE_TOLLGATE` |
| 115 | `case RELAY_TYPE_TOLLGATE_PAY: {` |
| 117 | `tollgate_msg_hdr_t hdr;` |
| 120 | `tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0` |
| 121 | `hdr.seq` (member of tollgate_msg_hdr_t) |
| 126 | `ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;` |
| 128 | `tollgate_ack_payload_t ack_payload;` |
| 132 | `tollgate_proto_encode(ack_pkt.data + 1,` |
| 133 | `RELAY_PACKET_MAX_SIZE - 1,` |
| 134 | `TG_MSG_ACK, hdr.seq,` |
| 136 | `sizeof(ack_payload)` |
| 145 | `#endif /* CONFIG_ENABLE_TOLLGATE */` |

Non-tollgate includes worth recording because they carry symbols used in the
same function: `relay_types.h` (line 23, unconditional).

## STEP 2 — CANDIDATE SYMBOLS ENUMERATED

Tollgate-stack (guarded, lines 114-145):
`RELAY_TYPE_TOLLGATE_PAY`, `RELAY_TYPE_TOLLGATE_ACK`, `tollgate_msg_hdr_t`,
`tollgate_ack_payload_t`, `tollgate_proto_decode`, `tollgate_proto_encode`,
`TG_MSG_ACK`, `RELAY_PACKET_MAX_SIZE`.

Preprocessor / Kconfig marker: `CONFIG_ENABLE_TOLLGATE`.

Header include: `tollgate_payment_proto.h`.

For completeness, the other symbols referenced but *not* defined in the file
(they belong to the relay/nostr stack, not to the tollgate header a downstream
author would write, but they are "referenced not defined" and are listed so the
inventory is exhaustive): `relay_packet_t`, `RELAY_TYPE_RAW`,
`RELAY_TYPE_NOSTR_EVENT`, `RELAY_TYPE_TELEMETRY`, `QueueHandle_t`, `g_rx_queue`,
`g_tx_queue`, `xQueueReceive`, `xQueueSend`, `pdTRUE`, `portMAX_DELAY`,
`pdMS_TO_TICKS`, `esp_get_free_heap_size`, `ESP_LOGI`, `ESP_LOGE`, `ESP_LOGW`,
`ESP_LOGD`, `nostr_store_t`, `nostr_store_init`, `nostr_store_add`,
`nostr_event_t`, `nostr_event_deserialize`, `secp256k1_context`,
`secp256k1_context_create`, `SECP256K1_CONTEXT_VERIFY`, `app_task_get_store`.

## STEP 3 — TREE-WIDE SEARCH PER SYMBOL (raw output)

### 3.1 `RELAY_TYPE_TOLLGATE_PAY`

```
$ cd ~/repos/balloon-fresh/tracker/firmware/ && grep -rn 'RELAY_TYPE_TOLLGATE_PAY' .
./main/tollgate_payment_proto.h:19: * type tag (RELAY_TYPE_TOLLGATE_PAY or RELAY_TYPE_TOLLGATE_ACK).
./main/test/test_relay_pipeline.c:129:    case RELAY_TYPE_TOLLGATE_PAY: {
./main/test/test_relay_pipeline.c:204:    pkt->data[0] = RELAY_TYPE_TOLLGATE_PAY;
./main/test/test_relay_pipeline.c:623:    assert(RELAY_TYPE_TOLLGATE_PAY == 0x02);
./main/app_task.cpp:115:        case RELAY_TYPE_TOLLGATE_PAY: {
./main/app_main.cpp:581: *   data[0]    = RELAY_TYPE_TOLLGATE_PAY (0x02)
./main/app_main.cpp:622:    pkt.data[0] = RELAY_TYPE_TOLLGATE_PAY;
./main/relay_types.h:12:#define RELAY_TYPE_TOLLGATE_PAY 0x02
./test/integration/test_tollgate_payack.py:15:  - RELAY_TYPE_TOLLGATE_PAY (0x02)
./test/integration/test_tollgate_payack.py:97:RELAY_TYPE_TOLLGATE_PAY = 0x02
```
Classification: **DEFINED elsewhere** — `main/relay_types.h:12` `#define RELAY_TYPE_TOLLGATE_PAY 0x02` (unit-test assertion `test_relay_pipeline.c:623` pins the value).

### 3.2 `RELAY_TYPE_TOLLGATE_ACK`

```
$ grep -rn 'RELAY_TYPE_TOLLGATE_ACK' .
./main/tollgate_payment_proto.h:19: * type tag (RELAY_TYPE_TOLLGATE_PAY or RELAY_TYPE_TOLLGATE_ACK).
./main/test/test_relay_pipeline.c:137:            ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;
./main/test/test_relay_pipeline.c:368:    assert(ack_pkt.data[0] == RELAY_TYPE_TOLLGATE_ACK);
./main/test/test_relay_pipeline.c:400:        assert(a.data[0] == RELAY_TYPE_TOLLGATE_ACK);
./main/test/test_relay_pipeline.c:509:        assert(ack_pkt.data[0] == RELAY_TYPE_TOLLGATE_ACK);
./main/test/test_relay_pipeline.c:624:    assert(RELAY_TYPE_TOLLGATE_ACK == 0x03);
./main/app_task.cpp:126:                ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;
./main/relay_types.h:13:#define RELAY_TYPE_TOLLGATE_ACK 0x03
./test/integration/test_tollgate_payack.py:16:  - RELAY_TYPE_TOLLGATE_ACK (0x03)
./test/integration/test_tollgate_payack.py:98:RELAY_TYPE_TOLLGATE_ACK = 0x03
```
Classification: **DEFINED elsewhere** — `main/relay_types.h:13` `#define RELAY_TYPE_TOLLGATE_ACK 0x03`.

### 3.3 `tollgate_msg_hdr_t`

```
$ grep -rn 'tollgate_msg_hdr_t' .
./main/tollgate_payment_proto.h:55:} __attribute__((packed)) tollgate_msg_hdr_t;
./main/tollgate_payment_proto.h:105: * @return sizeof(tollgate_msg_hdr_t) on success, or -1 on invalid header
./main/tollgate_payment_proto.h:108:                           tollgate_msg_hdr_t *hdr,
./main/test/test_tollgate_payment_proto.c:47:static void check_hdr_fields(const tollgate_msg_hdr_t *hdr,
./main/test/test_tollgate_payment_proto.c:65:    ASSERT_EQ_INT(8, (int)sizeof(tollgate_msg_hdr_t),
./main/test/test_tollgate_payment_proto.c:68:    tollgate_msg_hdr_t hdr;
./main/test/test_tollgate_payment_proto.c:87:    ASSERT_EQ_INT((int)(sizeof(tollgate_msg_hdr_t) + json_len), ret,
./main/test/test_tollgate_payment_proto.c:90:    const tollgate_msg_hdr_t *hdr = (const tollgate_msg_hdr_t *)buf;
./main/test/test_tollgate_payment_proto.c:93:    ASSERT_MEM_EQ(json, buf + sizeof(tollgate_msg_hdr_t), json_len,
./main/test/test_tollgate_payment_proto.c:105:    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), ret,
./main/test/test_tollgate_payment_proto.c:108:    const tollgate_msg_hdr_t *hdr = (const tollgate_msg_hdr_t *)buf;
./main/test/test_tollgate_payment_proto.c:151:    tollgate_msg_hdr_t hdr;
./main/test/test_tollgate_payment_proto.c:155:    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off,
./main/test/test_tollgate_payment_proto.c:160:    ASSERT(payload == data + sizeof(tollgate_msg_hdr_t),
./main/test/test_tollgate_payment_proto.c:166:    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off2,
./main/test/test_tollgate_payment_proto.c:177:    tollgate_msg_hdr_t hdr;
./main/test/test_tollgate_payment_proto.c:198:    tollgate_msg_hdr_t hdr;
./main/test/test_tollgate_payment_proto.c:222:    tollgate_msg_hdr_t *raw = (tollgate_msg_hdr_t *)data;
./main/test/test_tollgate_payment_proto.c:229:    tollgate_msg_hdr_t hdr;
./main/test/test_tollgate_payment_proto.c:238:    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), ret,
./main/test/test_tollgate_payment_proto.c:271:        tollgate_msg_hdr_t hdr;
./main/test/test_tollgate_payment_proto.c:274:        ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), dec, "decode offset");
./main/test/test_tollgate_payment_proto.c:305:    tollgate_msg_hdr_t hdr;
./main/test/test_tollgate_payment_proto.c:308:    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), dec, "decode ACK");
```
Classification: **DEFINED elsewhere** — typedef at `main/tollgate_payment_proto.h:49-55`:
```
49 typedef struct {
50     uint8_t  version;       /* Protocol version (TOLLGATE_PROTO_VERSION) */
51     uint8_t  type;          /* tollgate_msg_type_t */
52     uint16_t seq;           /* Sequence number for dedup */
53     uint16_t payload_len;   /* Length of payload following header */
54     uint16_t reserved;      /* Alignment / future use */
55 } __attribute__((packed)) tollgate_msg_hdr_t;
```
Unit test pins `sizeof() == 8` (`test_tollgate_payment_proto.c:65-66`).

### 3.4 `tollgate_ack_payload_t`

```
$ grep -rn 'tollgate_ack_payload_t' .
./main/tollgate_payment_proto.h:68:} __attribute__((packed)) tollgate_ack_payload_t;
./main/test/test_tollgate_payment_proto.c:289:    ASSERT_EQ_INT(14, (int)sizeof(tollgate_ack_payload_t),
./main/test/test_tollgate_payment_proto.c:290:                  "sizeof(tollgate_ack_payload_t) == 14 (packed)");
./main/test/test_tollgate_payment_proto.c:292:    tollgate_ack_payload_t ack;
./main/test/test_tollgate_payment_proto.c:311:    const tollgate_ack_payload_t *ack2 = (const tollgate_ack_payload_t *)payload;
./main/test/test_relay_pipeline.c:139:            tollgate_ack_payload_t ack;
./main/app_task.cpp:128:                tollgate_ack_payload_t ack_payload;
```
Classification: **DEFINED elsewhere** — typedef at `main/tollgate_payment_proto.h:62-68`:
```
62 /* ACK message payload (Balloon → Client) */
63 typedef struct {
64     uint32_t session_id;
65     uint32_t expires_unix;     /* Session expiry timestamp */
66     uint32_t quota_bytes;      /* Data quota (0 = unlimited time-based) */
67     uint16_t price_sats;       /* Price that was charged */
68 } __attribute__((packed)) tollgate_ack_payload_t;
```
Unit test pins `sizeof() == 14` (`test_tollgate_payment_proto.c:289-290`).

### 3.5 `tollgate_proto_decode`

```
$ grep -rn 'tollgate_proto_decode' .
./main/tollgate_payment_proto.h:107:int tollgate_proto_decode(const uint8_t *data, uint16_t len,
./main/test/test_tollgate_payment_proto.c:154:    int off = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:165:    int off2 = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, NULL);
./main/test/test_tollgate_payment_proto.c:180:    int ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:183:    ret = tollgate_proto_decode(data, 0, &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:186:    ret = tollgate_proto_decode(NULL, 100, &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:201:    int ret = tollgate_proto_decode(data, sizeof(data), &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:207:    ret = tollgate_proto_decode(data0, sizeof(data0), &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:211:    ret = tollgate_proto_decode(data0, sizeof(data0), &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:232:    int ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:237:    ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:242:    ret = tollgate_proto_decode(data, (uint16_t)sizeof(data) - 1, &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:273:        int dec = tollgate_proto_decode(buf, (uint16_t)enc, &hdr, &payload);
./main/test/test_tollgate_payment_proto.c:307:    int dec = tollgate_proto_decode(buf, (uint16_t)ret, &hdr, &payload);
./main/test/test_relay_pipeline.c:133:        if (tollgate_proto_decode(pkt->data + 1, (uint16_t)(pkt->len - 1), &hdr, &payload) > 0) {
./main/test/test_relay_pipeline.c:373:    assert(tollgate_proto_decode(ack_pkt.data + 1, (uint16_t)(ack_pkt.len - 1), &ack_hdr, &ack_payload) > 0);
./main/test/test_relay_pipeline.c:404:        assert(tollgate_proto_decode(a.data + 1, (uint16_t)(a.len - 1), &h, &pl) > 0);
./main/test/test_relay_pipeline.c:512:        assert(tollgate_proto_decode(ack_pkt.data + 1, (uint16_t)(ack_pkt.len - 1), &h, &pl) > 0);
./main/tollgate_payment_proto.c:35:int tollgate_proto_decode(const uint8_t *data, uint16_t len,
./main/app_task.cpp:120:            if (tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0) {
```
Classification: **DECLARED elsewhere** (prototype `main/tollgate_payment_proto.h:107-109`) and **DEFINED elsewhere** (definition `main/tollgate_payment_proto.c:35`):
```
107 int tollgate_proto_decode(const uint8_t *data, uint16_t len,
108                            tollgate_msg_hdr_t *hdr,
109                            const uint8_t **payload);
```
```
$ sed -n '35,36p' main/tollgate_payment_proto.c
35 int tollgate_proto_decode(const uint8_t *data, uint16_t len,
36                            tollgate_msg_hdr_t *hdr, const uint8_t **payload)
```

### 3.6 `tollgate_proto_encode`

```
$ grep -rn 'tollgate_proto_encode' .
./main/tollgate_payment_proto.h:94:int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
./main/test/test_tollgate_payment_proto.c:84:    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_PAY, 42, json, json_len);
./main/test/test_tollgate_payment_proto.c:103:    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_STATUS, 7, NULL, 0);
./main/test/test_tollgate_payment_proto.c:120:    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_PAY, 1, json, json_len);
./main/test/test_tollgate_payment_proto.c:125:    ret = tollgate_proto_encode(exact, sizeof(exact), TG_MSG_PAY, 1, json, json_len);
./main/test/test_tollgate_payment_proto.c:129:    ret = tollgate_proto_encode(exact, sizeof(exact) - 1, TG_MSG_PAY, 1, json, json_len);
./main/test/test_tollgate_payment_proto.c:133:    ret = tollgate_proto_encode(NULL, 256, TG_MSG_PAY, 1, json, json_len);
./main/test/test_tollgate_payment_proto.c:266:        int enc = tollgate_proto_encode(buf, sizeof(buf),
./main/test/test_tollgate_payment_proto.c:301:    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_ACK, 99,
./main/test/test_relay_pipeline.c:143:            int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
./main/test/test_relay_pipeline.c:207:    int enc_len = tollgate_proto_encode(pkt->data + 1,
./main/tollgate_payment_proto.c:14:int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
./main/app_task.cpp:132:                int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
./main/app_main.cpp:582: *   data[1..]  = tollgate_proto_encode(TG_MSG_PAY, seq, payload, len)
./main/app_main.cpp:588: * The PAY message is encoded with the real tollgate_proto_encode() from
./main/app_main.cpp:625:    int enc_len = tollgate_proto_encode(pkt.data + 1,
```
Classification: **DECLARED elsewhere** (prototype `main/tollgate_payment_proto.h:94-96`) and **DEFINED elsewhere** (definition `main/tollgate_payment_proto.c:14`):
```
94 int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
95                            tollgate_msg_type_t type, uint16_t seq,
96                            const char *payload, uint16_t payload_len);
```
```
$ sed -n '14,16p' main/tollgate_payment_proto.c
14 int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
15                            tollgate_msg_type_t type, uint16_t seq,
16                            const char *payload, uint16_t payload_len)
```

Note the app_task.cpp:132-136 call passes `(const char *)&ack_payload` as the
payload — a cast of the packed struct pointer to `const char *`, which matches
the declared `const char *payload` parameter type. The declaration accommodates it.

### 3.7 `TG_MSG_ACK`

```
$ grep -rn 'TG_MSG_ACK' .
./main/tollgate_payment_proto.h:41:    TG_MSG_ACK      = 0x02,  /* Balloon → Client: Payment accepted + session info */
./main/tollgate_payment_proto.h:88: * @param type         Message type (TG_MSG_PAY, TG_MSG_ACK, etc.)
./main/test/test_tollgate_payment_proto.c:257:        { TG_MSG_ACK,  5678, "{\"session_id\":42,\"expires\":999}" },
./main/test/test_tollgate_payment_proto.c:301:    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_ACK, 99,
./main/test/test_relay_pipeline.c:145:                                                 TG_MSG_ACK, hdr.seq,
./main/test/test_relay_pipeline.c:374:    assert(ack_hdr.type == TG_MSG_ACK);
./main/test/test_relay_pipeline.c:405:        assert(h.type == TG_MSG_ACK);
./main/test/test_relay_pipeline.c:513:        assert(h.type == TG_MSG_ACK);
./main/app_task.cpp:134:                                                     TG_MSG_ACK, hdr.seq,
./test/integration/test_tollgate_payack.py:102:TG_MSG_ACK = 0x02
```
Classification: **DEFINED elsewhere** — enum member of `tollgate_msg_type_t` at `main/tollgate_payment_proto.h:39-46`:
```
39 typedef enum {
40     TG_MSG_PAY      = 0x01,  /* Client → Balloon: Cashu token payment */
41     TG_MSG_ACK      = 0x02,  /* Balloon → Client: Payment accepted + session info */
42     TG_MSG_NACK     = 0x03,  /* Balloon → Client: Payment rejected + reason */
43     TG_MSG_STATUS   = 0x04,  /* Client → Balloon: Request status/pricing */
44     TG_MSG_INFO     = 0x05,  /* Balloon → Client: Status response (price, mints) */
45     TG_MSG_REVOKE   = 0x06,  /* Balloon → Client: Session revoked */
46 } tollgate_msg_type_t;
```

### 3.8 `RELAY_PACKET_MAX_SIZE`

```
$ grep -rn 'RELAY_PACKET_MAX_SIZE' .
./main/radio_task.cpp:61:                s_transport->recv(rx_pkt.data, RELAY_PACKET_MAX_SIZE, &n_out, 100);
./main/test/test_relay_send_nostr.c:8: *   - Check serialized event fits in RELAY_PACKET_MAX_SIZE - 1
./main/test/test_relay_send_nostr.c:92:                                           RELAY_PACKET_MAX_SIZE - 1);
./main/test/test_relay_send_nostr.c:221:     * Relay packet max = 511 bytes (RELAY_PACKET_MAX_SIZE - 1 for type tag).
./main/test/test_relay_send_nostr.c:236:    /* Verify the serialized size fits within RELAY_PACKET_MAX_SIZE */
./main/test/test_relay_send_nostr.c:237:    assert(txq.packets[0].len <= RELAY_PACKET_MAX_SIZE);
./main/test/test_relay_pipeline.c:144:                                                 RELAY_PACKET_MAX_SIZE - 1,
./main/test/test_relay_pipeline.c:193:    uint16_t slen = nostr_event_serialize(evt, pkt->data + 1, RELAY_PACKET_MAX_SIZE - 1);
./main/test/test_relay_pipeline.c:208:                                         RELAY_PACKET_MAX_SIZE - 1,
./main/test/test_relay_pipeline.c:619:    assert(sizeof(relay_packet_t) >= RELAY_PACKET_MAX_SIZE + sizeof(size_t) + sizeof(uint32_t) + sizeof(int));
./main/app_task.cpp:133:                                                     RELAY_PACKET_MAX_SIZE - 1,
./main/app_main.cpp:399: * Content is limited to ~374 bytes (RELAY_PACKET_MAX_SIZE - 1 - 137 bytes
./main/app_main.cpp:453:                                           RELAY_PACKET_MAX_SIZE - 1);
./main/app_main.cpp:457:               evt.content_len, RELAY_PACKET_MAX_SIZE - 1, RELAY_PACKET_MAX_SIZE - 1);
./main/app_main.cpp:612:    if (payload_len > RELAY_PACKET_MAX_SIZE - 1 - sizeof(tollgate_msg_hdr_t)) {
./main/app_main.cpp:615:               RELAY_PACKET_MAX_SIZE - 1 - (int)sizeof(tollgate_msg_hdr_t));
./main/app_main.cpp:626:                                         RELAY_PACKET_MAX_SIZE - 1,
./main/relay_types.h:6:#define RELAY_PACKET_MAX_SIZE 512
./main/relay_types.h:19:    uint8_t  data[RELAY_PACKET_MAX_SIZE];
```
Classification: **DEFINED elsewhere** — `main/relay_types.h:6` `#define RELAY_PACKET_MAX_SIZE 512`.

### 3.9 `CONFIG_ENABLE_TOLLGATE`

```
$ grep -rn 'CONFIG_ENABLE_TOLLGATE' .   # build/ and docs/ excluded from view
./main/CMakeLists.txt:29:if(CONFIG_ENABLE_TOLLGATE)
./main/app_task.cpp:32:#ifdef CONFIG_ENABLE_TOLLGATE
./main/app_task.cpp:114:#ifdef CONFIG_ENABLE_TOLLGATE
./main/app_task.cpp:145:#endif /* CONFIG_ENABLE_TOLLGATE */
./main/app_main.cpp:78:#ifdef CONFIG_ENABLE_TOLLGATE
./main/app_main.cpp:575:#ifdef CONFIG_ENABLE_TOLLGATE
./main/app_main.cpp:649:#endif /* CONFIG_ENABLE_TOLLGATE */
./main/app_main.cpp:670:#ifdef CONFIG_ENABLE_TOLLGATE
./sdkconfig.defaults.esp32s3:83:CONFIG_ENABLE_TOLLGATE=y
./sdkconfig:576:# CONFIG_ENABLE_TOLLGATE is not set
```
Classification: **DEFINED elsewhere (Kconfig, not C header)** — declaring stanza `main/Kconfig.projbuild:141-148`:
```
$ cat -n main/Kconfig.projbuild | sed -n '141,148p'
141 config ENABLE_TOLLGATE
142     bool "Enable TollGate payment processing (Cashu e-cash over mesh)"
143     default n
144     depends on ENABLE_RELAY_MODE
145     help
146         Enable TollGate payment message handling in app_task. Decodes PAY
147         messages from ground stations, validates Cashu tokens, and sends ACK
148         responses with session info. Requires relay mode for continuous RX.
```
`config ENABLE_TOLLGATE` (Kconfig line 141) is what ESP-IDF turns into
`CONFIG_ENABLE_TOLLGATE` in the generated `sdkconfig.h`. This is the correct,
customary mechanism for a compile-time feature gate; it is not a symbol a
downstream C author would place in a header.

### 3.10 `tollgate_payment_proto.h` (the include)

```
$ rg -n 'tollgate_payment_proto' .
./test/integration/test_tollgate_payack.py:10:The test uses the tollgate_payment_proto wire format (ADR-100):
./test/integration/test_tollgate_payack.py:100:# TollGate message types (from tollgate_payment_proto.h)
./main/app_main.cpp:79:#include "tollgate_payment_proto.h"
./main/app_main.cpp:589: * tollgate_payment_proto.c (ADR-100 wire format).
./main/app_task.cpp:33:#include "tollgate_payment_proto.h"
./main/CMakeLists.txt:30:    list(APPEND APP_SRCS "tollgate_payment_proto.c")
...
./main/tollgate_payment_proto.c:2: * tollgate_payment_proto.c — encode/decode for TollGate payment protocol
./main/tollgate_payment_proto.c:11:#include "tollgate_payment_proto.h"
./main/tollgate_payment_proto.h:2: * tollgate_payment_proto.h — TollGate payment protocol for balloon tracker
...
./main/test/test_relay_pipeline.c:83:#include "tollgate_payment_proto.h"
./main/test/test_tollgate_payment_proto.c:21:#include "tollgate_payment_proto.h"
```
```
$ find . -name 'tollgate*' -not -path './build/*'
./main/tollgate_payment_proto.h
./main/tollgate_payment_proto.c
```
Classification: **DEFINED/BESIDE elsewhere** — header present at
`main/tollgate_payment_proto.h`, implementation at `main/tollgate_payment_proto.c`,
and both are added to the build by `main/CMakeLists.txt:29-30`:
```
$ sed -n '29,31p' main/CMakeLists.txt
29 if(CONFIG_ENABLE_TOLLGATE)
30     list(APPEND APP_SRCS "tollgate_payment_proto.c")
```

## STEP 3 RETRIES (mandated fallbacks)

Requirement: if the first pass is empty, retry with (a) include-path form,
(b) bare name without prefix, (c) containing header name. In this run the first
pass was **not** empty for any candidate, so these were run as confirmatory
corroboration, not out of necessity. All retries are also non-empty.

### (a) include-path form

```
$ grep -rn 'main/tollgate_payment_proto.h' .
./main/test/test_relay_pipeline.c:78:/* The header now exists at main/tollgate_payment_proto.h with        */
./docs/recon/raw_doc_scan.md:88:### C1 — `main/tollgate_payment_proto.h` (in-scope firmware)
./docs/recon/raw_doc_scan.md:447:- Created `main/tollgate_payment_proto.h` — standalone header with ...
```
(non-empty: the header is a real in-tree file, cited by a test comment)

### (b) bare name without `tollgate_` / `TG_` prefix

```
$ grep -rn 'proto_decode' . | wc -l                      -> 20 hits
$ grep -rn 'proto_encode' . | wc -l                      -> 17 hits
$ grep -rn 'msg_hdr_t' . | wc -l                         -> 42 hits
$ grep -rn 'MSG_ACK' . | wc -l                           -> 10 hits
$ grep -rn 'ack_payload' . | wc -l                       -> 17 hits
$ grep -rn 'msg_type_t' . | wc -l                        ->  6 hits
$ grep -rn 'TOLLGATE_PROTO_VERSION' . | wc -l            ->  8 hits
$ grep -rn 'TOLLGATE_MAX_TOKEN_LEN' . | wc -l            ->  2 hits
```
All non-empty; e.g. `TOLLGATE_MAX_TOKEN_LEN` (the shortest list):
```
$ grep -rn 'TOLLGATE_MAX_TOKEN_LEN' .
./main/tollgate_payment_proto.h:36:#define TOLLGATE_MAX_TOKEN_LEN  2048
./main/tollgate_payment_proto.h:59:    char token[TOLLGATE_MAX_TOKEN_LEN];  /* Cashu token string (cashuA...) */
```

### (c) containing header name

```
$ grep -rn 'tollgate_msg' .
./main/tollgate_payment_proto.h:13: *   offset 1  type         uint8_t   (tollgate_msg_type_t)
./main/tollgate_payment_proto.h:46:} tollgate_msg_type_t;
./main/tollgate_payment_proto.h:51:    uint8_t  type;          /* tollgate_msg_type_t */
./main/tollgate_payment_proto.h:55:} __attribute__((packed)) tollgate_msg_hdr_t;
./main/tollgate_payment_proto.h:95:                           tollgate_msg_type_t type, uint16_t seq,
./main/tollgate_payment_proto.h:105: * @return sizeof(tollgate_msg_hdr_t) on success, or -1 on invalid header
./main/test/test_tollgate_payment_proto.c:47:static void check_hdr_fields(const tollgate_msg_hdr_t *hdr,
...
```
(non-empty)

## FULL HEADER CROSS-REFERENCE

Every symbol app_task.cpp references from the tollgate header, matched against
the header's own declarations (all present):

| symbol | kind | app_task.cpp | header site | value / signature |
|---|---|---|---|---|
| `RELAY_TYPE_TOLLGATE_PAY` | macro | :115 | relay_types.h:12 | 0x02 |
| `RELAY_TYPE_TOLLGATE_ACK` | macro | :126 | relay_types.h:13 | 0x03 |
| `RELAY_PACKET_MAX_SIZE`   | macro | :133 | relay_types.h:6  | 512 |
| `TG_MSG_ACK`              | enum member | :134 | tollgate_payment_proto.h:41 | 0x02 |
| `tollgate_msg_hdr_t`      | typedef struct | :117 | tollgate_payment_proto.h:49-55 | packed, 8 bytes |
| `tollgate_ack_payload_t`  | typedef struct | :128 | tollgate_payment_proto.h:62-68 | packed, 14 bytes |
| `tollgate_proto_decode`   | function | :120 | tollgate_payment_proto.h:107 (+ .c:35) | returns hdr size or -1 |
| `tollgate_proto_encode`   | function | :132 | tollgate_payment_proto.h:94 (+ .c:14) | returns bytes written or -1 |

Header symbols NOT used by app_task.cpp but present (so the header is a superset,
not a minimal stub): `TOLLGATE_PROTO_VERSION` (:33), `TOLLGATE_MAX_TOKEN_LEN`
(:36), `TG_MSG_PAY/NACK/STATUS/INFO/REVOKE` (:40,:42-45), `tollgate_msg_type_t`
(:39-46), `tollgate_pay_payload_t` (:58-60), `tollgate_nack_payload_t` (:71-74),
`TG_ERR_INVALID_TOKEN/SWAP_FAILED/MINT_UNREACHABLE/ALREADY_PAID/RATE_LIMITED`
(:77-81).

## STEP 5 — COMPILED-OBJECT CHECK (`nm`, read-only)

Probed the only reachable main object and the linked ELF:

```
$ find build -name '*app_task*'   -> (empty)
$ find build -name '*tollgate*'   -> (empty)
$ ls build/esp-idf/main/CMakeFiles/__idf_main.dir/ -> app_main.cpp.obj
$ nm -C build/esp-idf/main/CMakeFiles/__idf_main.dir/app_main.cpp.obj | grep -iE 'tollgate|TG_MSG'  -> (no output)
$ nm -C build/balloon-tracker.elf | grep -iE 'tollgate_proto|tollgate_msg|tollgate_ack' -> (no output)
```

Interpretation (this is why the `nm` evidence cannot settle the question):
`tracker/firmware/sdkconfig:576` = `# CONFIG_ENABLE_TOLLGATE is not set`. The
artefact in `build/` was configured with the tollgate block OFF, so
`main/tollgate_payment_proto.c`, `app_task.cpp`, and their symbols are absent
from the build by design. `nm` returning nothing here is a config fact, not a
missing-definition fact. No `nm` row is asserted for any function symbol;
whether `tollgate_proto_encode`/`tollgate_proto_decode` are *linkable* is
established instead by their source definitions at `main/tollgate_payment_proto.c:14`
and `:35` plus `main/CMakeLists.txt:30` adding the TU to `APP_SRCS`.

## NOT FOUND

**None.** Every candidate symbol was found defined or declared inside
`~/repos/balloon-fresh/tracker/firmware/`. This report makes no NOT-FOUND claim,
and therefore the required "visibly empty output" evidence would be vacuous —
there is no such row. The nearest-to-empty outputs observed were the `nm`
greps on a build that had the feature gate disabled, and those are explained
above as a Kconfig state, not absence of definition.

## VERDICT FOR THE DOWNSTREAM AUTHOR

`tollgate_payment_proto.h` does **not** need to be authored to satisfy
app_task.cpp. It already exists at `tracker/firmware/main/tollgate_payment_proto.h`
(115 lines, header-guarded, `extern "C"` wrapped, no ESP-IDF dependencies),
tracked in HEAD `64b8923`, with a matching implementation
`tracker/firmware/main/tollgate_payment_proto.c` wired into the build at
`main/CMakeLists.txt:29-30`. The eight symbols app_task.cpp consumes are all
supplied. What remains outstanding is design-level, not inventory-level: the
ACK path in app_task.cpp sends a raw packed `tollgate_ack_payload_t` cast to
`const char*`, while the PAY path in app_main.cpp/CLI emits JSON — the two
payload representations are not demonstrably mutually decodable. That is a spec
question, not a missing-symbol question, and is out of scope for this inventory.
```