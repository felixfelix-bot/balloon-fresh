# PROGRESS — test_relay_pipeline.c mock/stand-in contract analysis

Task: analyze mock implementation in tracker/firmware/main/test/test_relay_pipeline.c
Branch (read): autonomous/mesh-baseline @ fb36809
Worktree: ~/worktrees/t_relaymocks (branch worker-heavy/relay-mock-contract)
Mode: READ-ONLY analysis of source; artifacts written are the deliverables.

## Log
- Located file: tracker/firmware/main/test/test_relay_pipeline.c (637 lines, md5 e3185ac3d3c8db2d49f27dd9e2c16547) -> READ in full -> 3 headers read (relay_types.h, nostr_store.h, tollgate_payment_proto.h) -> consumer app_task.cpp read.
- Confirmed the mock/stand-in = mock_queue_t ring buffer + app_task_process_packet() re-impl (in the TEST). tollgate_payment_proto is NOT mocked (real .c linked).
- Verified target file byte-identical between ~/repos/balloon-fresh and branch worktree tg-proto-contract.
- KEY FINDING: header comment (lines 116-121) claims app_task.cpp uses `== 0`; ACTUAL app_task.cpp line 100 uses `> 0`. Comment is factually WRONG.
- KEY FINDING: test decodes PAY with `> 0`, app_task.cpp line 120 accepts with `>= 0` — permissive-vs-strict disagreement.
- KEY FINDING: test uses real struct ack (sizeof=14); app_task.cpp line 132-136 passes `sizeof(ack_payload)` (size_t) into uint16_t payload_len param.
- Symbol table written -> status: DRAFTING report.
