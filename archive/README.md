# Superseded & legacy material

**Purpose:** keep history as reference **without polluting the working context**.
Nothing here is authoritative. Nothing here may be cited as a live decision.

## The rule for this directory

| | |
|---|---|
| **What goes here** | Superseded *generations* — old board revs, old design ideas, retired analyses, v1/v2-era concept docs whose every choice has been replaced. |
| **What does NOT go here** | Anything that is still **cited as authority**. In particular, **ADRs are never moved here** — 143 files cite `docs/adr/` paths, and moving an ADR breaks those citations and destroys the *why* behind decisions that are still live. A superseded ADR is superseded **by a newer ADR** (that is what the supersession chain is for), not by being hidden. |
| **How to move something** | `git mv` the file here, then **leave a pointer stub at the old path** so old links and citations still resolve. |
| **Where records land** | A retired generation that has a source-of-truth owner is indexed in `docs/`; this directory is the storage, not the index. |

## Layout

```
archive/
  boards/        superseded board generations (v8x, v_c3, v2_adc lineage)
  docs/          retired analyses and v1/v2-era concept documents
  README.md      this file
```

## Why pointers instead of deletion

The repo's own rule (AGENTS.md) is that a contradiction that names no winner is a
**defect**. Deletion creates the worst version of that: a citation that resolves to
nothing. **Stubs preserve the address and state the supersession explicitly**, which
is strictly better than both keeping stale prose live and deleting it.

## Convention for a pointer stub

```markdown
> **ARCHIVED → `archive/<path>`** (moved 2026-10-14)
> Superseded by: <ADR-NNN or doc>. This file is kept for history only.
> Do not cite as authority.
```
