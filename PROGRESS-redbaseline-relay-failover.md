# PROGRESS — RED baseline for relay-failover tests (verdict_transport)

Repo: balloon-e80bench
Task: capture the verbatim RED pytest baseline for the relay-failover
(NIP-59 kind-1059 gift-wrap publish) suite.

- Locate tests -> FAILOVER/RELAY/1059 code lives in firmware/e80-stm32-bench/tools/
  (no tools/tests/ subdir exists). Suite = test_verdict_transport.py. -> DONE
- Suite state at current HEAD 658ac8b1 -> test module present AND verdict_transport.py
  present => 50 passed (GREEN). The implementation already landed. -> DONE
- Authored RED state = parent commit 522c001e (test file present, module absent).
  Reproduced verbatim in isolated worktree (NOT /tmp): ~/worktrees/e80-redbaseline. -> DONE
- Captured RED output (collection error, 1 error, ModuleNotFoundError). -> DONE
- Files touched: REPORT.md, PROGRESS.md (this worktree only; no source modified). -> DONE
- Commit + push deliverable. -> IN PROGRESS
