# PCB completion roadmap — release lane and bounded investigations

Updated: 2026-11-02. Status: planning only; **not a fabrication release**.

## Authority and scope

This is a hub-specific completion/investigation checklist subordinate to the
[program board completion plan](../plans/PROGRAM-BOARD-COMPLETION-PLAN.md),
not a competing program roadmap or a new board specification. The program plan
owns program-wide priorities; this checklist supplies bounded hub task details.
Its historical machine snapshot must not be read as live readiness evidence. The native KiCad schematic/netlist, board, matching project/rules,
parameter registry (`docs/ssot/parameters.json`) and applicable accepted ADRs
remain authoritative. Existing production gates and routing-method restrictions
are unchanged; a feasibility result does not authorize a replacement router.

`tracker/hardware/PCB-EXECUTION-PLAN.md` is the historical August three-variant
plan; `tracker/hardware/ROADMAP-v5-pcb.md` is the historical v5 plan. Neither
supplies current board dimensions, routing rules or release thresholds. In
particular, do not reuse the v5 blanket through-via prohibition, Python version
advice or nonzero-unconnected acceptance as current instructions. Use native
KiCad connectivity/DRC and current project gates, not those historical claims.

## Lane A — current order critical path (blocking release)

The PCB implementation owner owns repairs; an independent reviewer owns review;
the release/package owner owns exports and hashes; the human purchaser alone
owns purchase approval. The PCB manager assigns named people before dispatch.
No Lane B investigation is a prerequisite for this lane or the current order.

1. **Freeze and measure the actual inputs.** Record revision, KiCad version,
   board/schematic/netlist/project/rules/library hashes and fresh native results
   on a copy. Do not borrow sibling rules or treat an absent rules file as a pass.
2. **Combined stitch and remaining electrical repairs.** Evaluate the combined
   candidate, not a sum of isolated successes. Refill and run native KiCad DRC,
   endpoint connectivity, schematic parity/ERC and applicable project checkers.
   Preserve proven critical paths. Require no unresolved required electrical
   connections or unapproved waivers; investigate any checker disagreement.
3. **Mechanical, footprint and silkscreen checks.** Resolve library/footprint
   parity, edge/drill/thermal issues, slots and internal cutouts, assembly access
   and legibility. Preserve placement approval; any necessary placement change
   must re-enter the existing placement gate before routing. These checks remain
   pre-routing prerequisites wherever the existing process requires them.
4. **Independent review.** Review the exact hashed candidate and evidence, with
   cross-family and spatial review where required. Unresolved findings block
   release; renders alone do not prove electrical or fabrication correctness.
5. **Exact release package and human approval.** Regenerate and inspect Gerbers,
   drills, BOM and CPL from that candidate; hash every deliverable with the source
   manifest and review evidence. Any source/export change invalidates sign-off.
   Obtain explicit human purchase approval for that exact package before order.

Historical scope, **not fresh measurements or demonstrated improvements**:
[endpoint audit](../analysis/hub-endpoint-audit-20261030/readiness-audit.md)
recorded 86 missing connections/minimum joins across 22 nets. The prior work
handoff also reported 35 islands, 29 provisionally isolated, and 22 individual
stitch candidates with 7 still unapproved. Those handoff figures have not been
reproduced by this documentation task and are not acceptance evidence. Neither
individual candidates nor provisional isolation prove combined-board safety.
The fresh baseline belongs to the separately assigned baseline owner; this
roadmap does not overwrite that owner's results or claim the board improved.

## Lane B — optional, nonblocking process improvement

All items below are **not run by this roadmap update**. Timeboxes include setup,
reading, experiments and reporting; stop at the limit rather than extending the
critical path. Run only in isolated scratch copies, never the order source or a
shared dirty worktree. No paid service, account purchase or board upload is
approved here. Missing access, credentials, compatibility or evidence means
**defer**, not a fabricated successful result.

### B1 — pinned local Freerouting DSN/SES feasibility: 60 minutes

- **Owner:** routing-tool investigator; **acceptance reviewer:** PCB checker owner.
- **Source:** <https://github.com/freerouting/freerouting>.
- **Work:** pin an upstream release/commit and executable hash; record local
  runtime/version and documented invocation. Test KiCad 9 DSN export → local
  routing → SES import on a disposable board copy. Establish whether existing
  copper and constrained critical routes can be preserved before any routing
  trial. No service-backed fallback or production-router substitution.
- **Output:** a reproducible command log, pinned tool/source manifest, input/DSN/
  SES/imported-board hashes, import/export limitations and native before/after
  checks; report incomplete stages as not run.
- **Accept for a later proposal only:** reproducible round trip with unchanged
  schematic-derived netlist, stackup, critical placement and proven paths;
  frozen **0.20 mm clearance** and all other rules intact; slots/internal cutouts
  and keepouts preserved; no new native DRC/project-gate failures. Quantify any
  connectivity gain on the combined board, not the router's own score.
- **Reject/defer:** dropped geometry, rule relaxation, moved critical parts,
  changed connectivity, unpreserved copper, unsupported DSN/SES semantics,
  failed native checks or inability to finish within 60 minutes. Keep negative
  evidence. Even success needs a separately reviewed proposal/ADR before use
  under the existing routing-method policy.

### B2 — AI-PCB-Generator source review: 30 minutes

- **Owner:** tooling/source reviewer; **acceptance reviewer:** manufacturing owner.
- **Source:** <https://github.com/22507260/AI-PCB-Generator>.
- **Work:** pin a commit; inspect router, DFM and manufacturing-export paths and
  tests. Distinguish implemented behavior from README claims. This is source
  review, not adoption, generated-board trust or an end-to-end feasibility claim.
- **Output:** path/line citations at the pinned commit, dependencies/license,
  KiCad-version assumptions, native input/output formats, validation authority
  and concrete reusable ideas (or an explicit no-useful-fit conclusion).
- **Accept for follow-up:** a small, attributable mechanism with tests and a
  credible native-KiCad integration seam that preserves frozen constraints.
  **Reject/defer:** opaque/self-grading DFM, unverified manufacturing outputs,
  geometry loss, unsupported KiCad 9 assumptions, incompatible license or no
  inspectable implementation within 30 minutes. Never replace native checkers.

### B3 — official Quilter interface/constraints verification: 20 minutes

- **Owner:** vendor-interface researcher; **acceptance reviewer:** PCB manager.
- **Source:** official vendor documentation reached from <https://www.quilter.ai/>;
  record exact URLs and access dates, not third-party command examples.
- **Work:** verify the actually supported interface, KiCad 9 import/export,
  preservation of placement/netlist/stackup, frozen rules, keepouts, existing
  copper, slots/internal cutouts, and available output validation. Separate
  documented support, explicit exclusions and unknowns in a matrix.
- **Output:** cited interface/constraint matrix and access/cost/data-handling
  requirements. An unverified Quilter CLI is **not usable**; invent no commands.
- **Accept for follow-up:** official evidence of the needed interface and every
  required constraint, with a separate approval path for uploads or spending.
  **Reject/defer:** undocumented API/CLI, missing preservation guarantees,
  inaccessible evidence or timebox expiry. No board upload or paid trial here.

### B4 — PcbRouter/OpenROAD: deferred, no current execution slot

- **Owner:** routing-tool investigator; **reopening reviewer:** PCB checker owner.
- **Source:** <https://github.com/The-OpenROAD-Project-Attic/PcbRouter>.
- The README's KiCad **5.1.2** basis is not proof of KiCad 9 compatibility.
  Reopen only with pinned source and demonstrated KiCad 9 import/export and
  constraint-preserving round-trip evidence, including slots/internal cutouts.
  Reject unsupported conversion assumptions. No porting project or OpenROAD
  integration belongs on the current order path.

## Reporting and stop rule

Each investigator returns owner, elapsed time, pinned sources, exact artifacts,
commands/checks actually run, acceptance/rejection verdict and unresolved limits.
The PCB manager records accept-for-follow-up / reject / defer; none means
production approved. Stop immediately on production-file mutation, required
constraint loss, unsafe commands or an approval guard. Do not bypass hooks,
checks or human purchase approval. Unfinished investigations stay deferred while
Lane A continues.

## DECISIONS

- Keep research separate from release: the historical endpoint audit establishes
  remaining electrical scope, not a need to replace tools. Reject research as
  an order prerequisite; revisit only if the implementation owner documents a
  concrete blocker and the relevant change passes existing approval gates.
- Put this task roadmap under `docs/fab/`, with pointers from the two historical
  plans. They describe older variants and conflicting rules; extending either
  as a current board specification would silently revive obsolete assumptions.
- Preserve native KiCad/checker authority and the frozen constraints. Tool claims
  and isolated candidates are not release evidence; only reproducible checks
  on the exact combined candidate can change the release verdict.
