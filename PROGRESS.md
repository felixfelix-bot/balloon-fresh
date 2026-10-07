# PROGRESS — analysis/pico-balloon-solar

**STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**

- Branch: `analysis/pico-balloon-solar`
- Worktree: `/home/c03rad0r/worktrees/bf-pico`
- Base commit: `af9a672` (verified with `git cat-file -t` before worktree creation)
- Date: 2026-10-07

## Deliverables

| File | State |
|---|---|
| `docs/analysis/pico-balloon-solar-survey.md` | **DONE** — 8 sections, 26 sources read + quoted, §8 lists UNVERIFIED |
| `REPORT.md` | **DONE** — top-3 findings + recommendation |
| `PROGRESS.md` | this file |

## Task checklist

- [x] §1 Define the class (sub-100 g all-up / 10–30 g payload) with source justification; 26 sources
      by name, typed as first-hand / vendor / second-hand
- [x] §2 What they use, per source: bare rigid crystalline / flexible thin film / potted / none; how
      attached; substrate; protection; part numbers; mass
- [x] §3 W/g and mg/cm² per approach; central question answered (different *component*, not different
      *structure*) with deciding numbers; TODO(unverified) marked where unsupported
- [x] §4 Void/pressure question answered from balloon sources; real pressure/temperature/duration;
      CubeSat analogue rejected on numbers; "no balloon evidence either way" stated plainly
- [x] §5 Flexible thin film vs bare silicon with quoted efficiency, W/g, mg/cm², robustness, assembly
- [x] §6 Failure reports (9 sourced failures; the two negatives stated as negatives)
- [x] §7 Recommendation with deciding number + what is NOT settled and needs a bench test
- [x] §8 UNVERIFIED list (7 entries)
- [x] Honesty statement

## Method notes / issues hit

- `browser_exec` failed again this session: `daemon default didn't come up`. Chrome **was** started
  locally (`google-chrome --headless=new --remote-debugging-port=9222`) and the DevTools endpoint
  answered, but the browser-harness refused to attach (`chrome-not-running`), so the browser tool was
  unusable. Worked around it with the `r.jina.ai` text-render proxy + `curl` + `pandoc` + DuckDuckGo's
  HTML endpoint (via the proxy) for search. Scripts left in `_research/` (untracked scratch).
- Brave/DuckDuckGo/Bing/Mojeek/Startpage all block direct automated curl (429 / captcha); DuckDuckGo
  HTML **through the jina proxy** worked and was the search path used.
- GitHub HTML pages block the proxy (403 abuse); GitHub **raw** and the `gh` API worked — KS4VA and
  K1FM READMEs fetched from `raw.githubusercontent.com`.
- NIBBB (WordPress) returned only a title through the proxy; fetched directly with `curl` + `pandoc`.
- groups.io is login-walled; lora-aprs.org is bot-walled; both listed UNVERIFIED, not read.

## Verification done

Pushed to `github` then `ngit` **separately**; all three SHAs verified equal with `git ls-remote`:

| Remote | Ref | SHA |
|---|---|---|
| local `HEAD` | `analysis/pico-balloon-solar` | `55a1d76b78e99cedaffde013628d08dcccaf67b0` |
| `github` (`felixfelix-bot/balloon-fresh`) | `refs/heads/analysis/pico-balloon-solar` | `55a1d76b78e99cedaffde013628d08dcccaf67b0` |
| `ngit` (`relay.ngit.dev/balloon-fresh`) | `refs/heads/analysis/pico-balloon-solar` | `55a1d76b78e99cedaffde013628d08dcccaf67b0` |

No force-push; no push to `main`/`master`. Pre-push secret scan reported
`✓ No secrets detected in full repo history.`

Note: `REPORT.md` and `PROGRESS.md` are matched by the repo-wide `.gitignore`
(lines 66–67), so they were added with `git add -f` to make the branch
self-contained; the survey doc was added normally.
