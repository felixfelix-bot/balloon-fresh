# LR2021 fetch manifest — drivers fragment

- source file specified by the task (read only): `docs/lr2021-research/drivers/provenance.md`
- source file status: **ABSENT — does not exist on any ref of `felixfelix-bot/balloon-fresh`, in any worktree on this host, or in any path outside the repo**
- verified entries (path exists AND sha256 matches): `0`
- entries flagged HASH MISMATCH: `0`
- FAILED entries: `1`
- verification tooling: `sha256sum` (fallback `shasum -a 256`, then `sha256`), plus `test -f`
- network access: none

---

## FAILED

### F1 — `docs/lr2021-research/drivers/provenance.md` — SOURCE FILE NOT PRESENT

- local path: `docs/lr2021-research/drivers/provenance.md` (specified by the task; never created)
- origin URL: `n/a` — no retrieval was ever recorded, because the source file itself was never produced
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: `n/a`
- file size: `n/a`
- sha256: `n/a`
- explicit reason: **source file absent.** The producer card `t_c6dd8d63` ("Vendor RadioLib LR2021 driver sources at a pinned SHA into `docs/lr2021-research/drivers/`", `worker-base`, network fetch via `curl`) is `archived` with **no completed run** — its only two runs are `scheduled` (run 61) and `blocked` (run 123, `fleet-offload:dq05`). It never fetched anything, so `docs/lr2021-research/drivers/` and its `provenance.md` were never created. This card `t_73c3244e` names that absent file as its read-only INPUT, so there are no entries to normalise or re-verify.

---

## Evidence recorded during this pass

All commands below are local and read-only with respect to `docs/`; no network access was used.

1. `git log --all --oneline -- docs/lr2021-research/drivers` → empty. No commit on any branch, tag or remote ref in this clone ever added the path.
2. `git ls-tree -r --name-only origin/main | grep 'lr2021-research/drivers/'` → empty. The path is absent from the current default-branch tree.
3. `git ls-tree -r --name-only origin/main | grep -i 'lr2021-research/.*provenance'` → the provenance files that DO exist are:
   - `docs/lr2021-research/datasheets/.provenance/lr1110.md`
   - `docs/lr2021-research/datasheets/.provenance/lr1121.md`
   - `docs/lr2021-research/datasheets/provenance-lr11x0.md`
   - `docs/lr2021-research/datasheets/provenance.md`
   - `docs/lr2021-research/errata/provenance.md`
   - `docs/lr2021-research/radiolib-master/PROVENANCE.md`
   None is at the specified path.
4. Filesystem sweep of `/home/c03rad0r/{repos,worktrees,.hermes/.worktrees}/**/docs/lr2021-research/drivers/provenance.md` and of `**/lr2021-manifest-parts` → no `drivers/` directory exists anywhere on this host; the only `lr2021-manifest-parts` directory is the sibling fragment task's own scratch (`t_9c3e3b22`), which holds `datasheets.md` only.
5. Card state read read-only from `~/.hermes/kanban/boards/tollgate/kanban.db` (`mode=ro`): `t_c6dd8d63` → `status=archived`, `result=NULL`, `current_run_id=NULL`; `task_runs` for it → `[scheduled/61, blocked/123]`. No run ever produced the deliverable.

---

## Non-normative note for the merge step (sourcing only, no technical conclusions)

A driver-provenance record **does** exist in the corpus at a different path than the one this card names: `docs/lr2021-research/radiolib-master/PROVENANCE.md` (RadioLib `master` snapshot @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, commit date 2026-09-13, version macros 7.7.1-dev, retrieved 2026-09-14 UTC by `git clone --depth 1`), authored by task `t_dbcc7e9a`. It was **not** used to populate this fragment, because the card specifies `docs/lr2021-research/drivers/provenance.md` as its read-only INPUT and re-scoping a named input is a manager decision, not a sourcing decision. Recorded here so the merge step and the manager can see the gap rather than infer it.

---

END OF FRAGMENT
