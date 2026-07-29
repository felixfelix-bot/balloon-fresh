# Balloon Tollgate — Payment Layer for Internet Transport

Captive portal + Cashu payment processing for balloon-based internet access.

## Architecture (per ADR-024)

Extract ONLY balloon-relevant components from tollgate-esp32 source repo:
- Captive portal (payment collection)
- Cashu payment processing

Leave in source repo: display, stratum v2, PoW, bidax UI.

## Worktree

Sub-manager works in: ~/worktrees/balloon-tollgate-fresh/ (branch: balloon-tollgate-extract)
This directory is the integration target within balloon-fresh master.

