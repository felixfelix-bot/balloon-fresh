# MeshCore PR #2739 — Rebase + Head-Update Procedure (2026-09-04)

Status: rebase complete on our side; pushing to the c03rad0r fork needs
c03rad0r credentials (bot PAT is felixfelix-bot only). One-liner prepared,
tested, and published.

## State (verified 2026-09-04)

| Item | Value |
|---|---|
| PR | https://github.com/meshcore-dev/MeshCore/pull/2739 |
| Before | head `c23a323` — 774-line diff, CONFLICTING, review CHANGES_REQUESTED (answered Jul-5, no re-review since) |
| After | head `1ed56aac` (`1ed56aaca6345e5a0a67d2d19e9403154349fe02`) — rebased onto upstream `dev`, slimmed to NiceRF-only deltas, **7/7 PlatformIO envs build-green** |
| Mirror | `felixfelix-bot/MeshCore` branch `pr-2739-rebased` @ `1ed56aac` |
| Upstream context | generic LR2021 support already landed via #3115 / #3112 / #3146 / #3218; our PR now carries only: NiceRF variant files, ESP-IDF SPI HAL workaround (non-default pins), DIO9 IRQ config |
| Rebase shape | 434 new commits (upstream dev pulled in), 8 old commits dropped (history rewrite → force-with-lease required) |

## The one-liner (run on a machine with c03rad0r GitHub credentials)

```bash
curl -fsSL https://gist.githubusercontent.com/felixfelix-bot/3079c7c0cceb533d1defdf6984bfc58e/raw/push-pr2739.sh | bash
```

Gist source (read first if you like): https://gist.github.com/felixfelix-bot/3079c7c0cceb533d1defdf6984bfc58e

## What the script does (and refuses to do)

1. Bare-clones ONLY branch `pr-2739-rebased` from the felixfelix-bot mirror
   into a temp dir; no existing checkout is touched; temp dir removed after.
2. **Abort guard A:** mirror head must be exactly `1ed56aac…` — if the mirror
   moved, it stops and says so.
3. **Abort guard B:** remote `feature/nicerf-lr2021-variant` must still be at
   `c23a323…` — if anyone pushed since 2026-09-04, it stops rather than clobber.
4. Pushes exactly that one commit to exactly that one branch with
   `--force-with-lease` pinned to the old SHA (force needed: rebases rewrite
   history; the lease makes it safe). HTTPS first, SSH fallback.
5. Prints the PR URL. Maintainers then see the slimmed diff on re-review.

Verified before publishing: syntax check + full local simulation (real mirror
fetch, fake destination repo at the old SHA) — push landed at `1ed56aac`,
guards fired correctly.

## Manual equivalent (if you prefer no curl|bash)

```bash
git clone --bare --single-branch --branch pr-2739-rebased \
  https://github.com/felixfelix-bot/MeshCore.git /tmp/mc.git
git --git-dir /tmp/mc.git push \
  --force-with-lease=refs/heads/feature/nicerf-lr2021-variant:c23a323ae7d99f908ed66e0840847f3f17800fff \
  https://github.com/c03rad0r/MeshCore.git \
  1ed56aaca6345e5a0a67d2d19e9403154349fe02:refs/heads/feature/nicerf-lr2021-variant
```

## Notes

- After the push, PR #2739 should request re-review (maintainers: oltaco
  left the last review round; our issue-side comment
  https://github.com/meshcore-dev/MeshCore/issues/2740#issuecomment-5539112861
  already tells the thread the rebase is coming).
- Downstream work does NOT depend on this push: the passive-mapper firmware
  task bases directly on the felixfelix-bot mirror @ `1ed56aac`.
- If guard B fires (branch moved legitimately, e.g. we pushed a newer rebase),
  update `OLD_SHA` in the gist or ask the manager for a fresh one-liner.
