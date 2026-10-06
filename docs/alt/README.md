# `docs/alt/` — retained alternative documents

Same policy as `tools/alt/`: when two independently-authored artifacts address the
same subject and *neither supersedes the other by blob ancestry*, the live one stays
on its normal path and the alternative is **retained here**, byte-identical, with its
provenance recorded. Nothing is discarded, and the "which one wins" decision never
destroys the loser.

Import/consumption rule (learned the hard way in `tools/alt`): anything here is a
**non-live** artifact. Nothing on the normal build/test path may import, eval, or
`safe_load` these files by bare name. Reference them by full path.

---

## `TOLLGATE_PROTO_CONTRACT.mesh-baseline.md`

**Subject:** the wire/API contract for `tracker/firmware/main/tollgate_payment_proto.{h,c}`.

**Why there are two:** both documents were authored on **2026-09-27** for the same
header, independently. Neither blob appears in the other's history at that path
(`git log <rev> -- TOLLGATE_PROTO_CONTRACT.md`), so this is a genuine parallel
authorship, not an old-vs-new pair.

| | live doc (trunk) | this retained copy |
|---|---|---|
| path | `TOLLGATE_PROTO_CONTRACT.md` | `docs/alt/TOLLGATE_PROTO_CONTRACT.mesh-baseline.md` |
| blob | `453d8265` | `b1cd96d9` |
| size | 41,983 B / 611 lines | 44,879 B / 756 lines |
| title | "Authoritative **API Contract** for `tollgate_payment_proto.h`" | "Authoritative **wire contract** for `tollgate_payment_proto.h`" |
| revision | **Rev 3** — §0.5 records cold-review corrections **F1–F6**; §7.1 filed defects D1/D2 | no revision lineage; §0 notes all four named recon inputs were missing |
| history | `68c27cd` (rev 2, "reconcile with shipped code + pinned tests") → `fef79ba` (rev 3) | blob `b1cd96d9`, carried identically by `autonomous/mesh-baseline`, `worker-balloon/pcb-phase1-t877`, `wt/t_bba26596-4layer` |

**Which one is live, and why:** the trunk document, because it is the one with a
**revision lineage to the shipped code and the pinned tests** (rev 2 reconciled
against both; rev 3 applied the F1–F6 cold-review corrections) and it is the one
cross-referenced by the repo's own commits and ADR-002. The retained copy is
**branch-scoped** by its own header ("Status: AUTHORITATIVE for branch
`autonomous/mesh-baseline`") and has no review lineage. The live doc also states an
explicit precedence rule: where the doc and the tests disagree on a pinned number,
the tests win — that rule is absent from the copy.

**This copy is not dead weight.** It is ~145 lines longer and carries material the
live doc does not, notably:

- `§4.3` — the two tag namespaces overlap, and *that overlap is coincidental*; it is
  called out as the number-one confusion hazard.
- `§9` — a numbered `DEVIATION` list of every place the shipped implementation
  departs from the contract.

Those two sections are the candidate merge material if the live doc is next revised.

**Retrieved with:**
```
git show autonomous/mesh-baseline:TOLLGATE_PROTO_CONTRACT.md
```
Byte-identical (`git hash-object` = `b1cd96d91…`). The source branches remain
reachable under the `archive/consolidate-2026-10-05/` tags; this copy exists so the
document survives independent of those refs.
