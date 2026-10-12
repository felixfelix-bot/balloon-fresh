# PROGRESS — tollgate proto call-site inventory (READ-ONLY recon)

- worktree: /home/c03rad0r/worktrees/tg-proto-scan  branch autonomous/mesh-baseline @ fb36809
- finding: app_task.cpp:33 includes tollgate_payment_proto.h under CONFIG_ENABLE_TOLLGATE; decode @120, encode @132 (TG_MSG_ACK) — STATUS: read
- finding: tollgate_payment_proto.h/.c exist in tree (header 8B packed, encode/decode defined) — STATUS: read
- finding: main/tollgate_payment_proto.c DEVICE (real) impl uses hdr->seq (uint16_t), no price_sats write; app_task passes `(const char *)&ack_payload` where ack_payload.price_sats=0 — STATUS: cross-checked
- next: read main/test/test_relay_pipeline.c in full (BINDING mock)
- next: grep tree for tollgate_ TG_MSG_ TG_PROTO_ price_sats msg_type seq
