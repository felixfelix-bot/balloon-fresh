# PROGRESS — tollgate proto call-site inventory (READ-ONLY recon)

- worktree: /home/c03rad0r/worktrees/tg-proto-scan  branch autonomous/mesh-baseline @ fb36809
- finding: app_task.cpp:33 includes tollgate_payment_proto.h under CONFIG_ENABLE_TOLLGATE; decode @120, encode @132 (TG_MSG_ACK) — STATUS: read
- finding: tollgate_payment_proto.h/.c exist in tree (header 8B packed, encode/decode defined) — STATUS: read
- finding: main/tollgate_payment_proto.c DEVICE (real) impl uses hdr->seq (uint16_t), no price_sats write; app_task passes `(const char *)&ack_payload` where ack_payload.price_sats=0 — STATUS: cross-checked
- next: read main/test/test_relay_pipeline.c in full (BINDING mock)
- next: grep tree for tollgate_ TG_MSG_ TG_PROTO_ price_sats msg_type seq
- finding: BOTH host suites compile+pass: test_tollgate_payment_proto 83/83 PASS; test_relay_pipeline 12/12 PASS — STATUS: verified, evidence observed
- finding: empirical probed sizes — hdr=8, ack=14, pay=2048, nack=130; offsets ver/type/seq/plen/res=0/1/2/4/6 — STATUS: verified via /tmp/probe
- finding: app_main.cpp:627 is a THIRD encoder consumer (CLI tollgate_send_pay) not in the task brief — STATUS: enumerated
- finding: existing authoritative contract docs already in tree: TOLLGATE_PROTO_CONTRACT.md (repo root, local lineage) + docs/recon/*.md — STATUS: cross-referenced
- next: symbol definition sweep (any referenced-but-undefined), write REPORT.md, commit+push
- finding: REPORT.md written (21KB, full symbol table + 9 disagreements + dead-symbol list) — STATUS: on disk
- done: commit + push
