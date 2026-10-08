# PROGRESS — design/positioner-lowcost

**Task:** Design and cost a LOW-COST AZ/EL positioner for the balloon ground station,
leading with dish RIGHT-SIZING as the dominant cost lever, with a real parts list + URLs,
torque chain, back-driving, stow/survival, backlash-vs-pointing, salvage options, an
analysis doc, an ADR draft, and an independent consultant verdict recorded verbatim with the
served model named.

**Branch:** `design/positioner-lowcost` · **Base:** `09e1b69` (`github/main`) ·
**Worktree:** `/home/c03rad0r/worktrees/bf-positioner`

> **PROGRESS.md and REPORT.md are gitignored in this repo (`.gitignore` lines 67–68).**
> This branch force-adds them per the task brief ("`git add -f` on your branch only").
> They are working notes, not deliverables.

## Cluster log

**C1 — Setup + upstream read (done).** Worktree cut from `github/main` @ `09e1b69`. Read the
committed budget/model sources the task named: `docs/analysis/ground-station-lowpower-link-and-shared-dish.md`
(branch `design/ground-station-lowpower-link`), `docs/LINK-BUDGET-LICENCE-EXEMPT.md`
(branch `design/ground-station-rf`), `docs/analysis/ground-station-bom-candidates.md`
(branch `design/ground-station-bom`), `docs/analysis/dualband-single-dish.md`,
`ground_station_dish_model.py`, `ground_station_rf_model.py`. **Key input harvested:** the
2.4 GHz uplink budget closes with **negative** required ground gain — the right-sizing
conclusion follows directly from the repo's own committed numbers.

**C2 — Printables 945761 specs (done).** `printables.com` returns **HTTP 403** to scripted
requests; recovered the page from the **Internet Archive** snapshot `2026-04-02`
(`web/20260402154451id_/...`) and confirmed the model record via the printables GraphQL API.
Real specs: **28BYJ-48** steppers (author: *"Considering how weak those motors are, they are
not the best option"*), **4 × 608zz** bearings, **14:50** elevation gear ratio (V3), AZ+EL,
tripod adapter, no electronics bay, updated 2024-08-11, by **Stratos**.

**C3 — Web sourcing (partial, honest gaps).** Sourced and verified: StepperOnline stepper
holding torques + prices (NEMA17 0.59 N·m $8.75; NEMA23 3.0 N·m $23.02; NEMA34 8.2 N·m
$36.36); StepperOnline **NMRV** worm reducers (NMRV30 15:1 18 N·m; NMRV40 20:1 40 N·m;
NMRV50 30:1 85 N·m; NMRV50 50:1 74 N·m) with the vendor's own **self-locking** claim;
Tek2000 **QARL-24 SuperJack 36 V actuator** $339 / 675 kg load; Argent Data **anemometer**
$68/$15; Wikipedia slewing-bearing definition. **BLOCKED:** every general search backend
(Brave, DuckDuckGo, Bing, Ecosia, Mojeek) served a **captcha** to this fleet's egress IP
after the first two queries — so printed-gear tooth strength, wiper/power-steering/wheelchair
motor torques, slewing-bearing price, and used-Yaesu price are `TODO(unverified)` rather
than guessed. Wikipedia + direct vendor fetches stayed reachable.

**C4 — Model + doc + figure (done, committed `391efae`).**
`docs/analysis/positioner_lowcost_model.py` (stdlib only, exit 0, no `%%` leaks) prints every
table quoted in the doc. `docs/analysis/positioner-lowcost-3dprinted.md` written and
committed **early** (task instruction: two prior workers died on HTTP 503), then refined.
Figure `docs/analysis/figures/positioner-rightsizing.png` rendered from the stdlib SVG
generator `render_positioner_figure.py` via ImageMagick `convert` (matplotlib absent).

**C5 — ADR + consultant (done, committed `3352359`).** `scripts/adr_next_number.py` → **66**,
but **066 is already claimed** on a remote branch
(`066-ground-station-lowpower-shared-positioner.md`); **067 verified free on every
`github/*` branch** and used. ADR draft `docs/adr/067-positioner-architecture.md` (Proposed)
+ INDEX entry. Consultant engaged on the **2nd** attempt (1st = **HTTP 503 "all candidate
lanes busy or capped"**, exactly as warned) → **`visual_review: APPROVED`,
`visual_reviewer_model: gpt-6-astra`**; verdict recorded **verbatim** in the doc §15 with a
reconciliation of the one numeric ambiguity it raised.

**C6 — Push + verify (done).** `git push github` then `git push ngit` **separately** (never
`--atomic`, never `main`). ngit printed the cosmetic *"failed to publish 1 state event"*
and still landed the ref.

## SHAs (final)

| Ref | SHA |
|---|---|
| local HEAD | `33523591b4edd6c733ddbc765dc6064c41682da9` |
| `github/design/positioner-lowcost` | `33523591b4edd6c733ddbc765dc6064c41682da9` |
| `ngit/design/positioner-lowcost` | `33523591b4edd6c733ddbc765dc6064c41682da9` |

Earlier milestone commit: `391efaeb9be5668d6409e5374a435209c205d725` (pushed to both remotes
before the ADR — the "commit early" mitigation).

## Hard rules observed

- Never pushed `main`/`master`; never force-pushed.
- `AGENTS.md` untouched. Nothing ordered; no fab freeze.
- Every figure cited with a URL or marked `TODO(unverified)` (39 markers in the doc).
