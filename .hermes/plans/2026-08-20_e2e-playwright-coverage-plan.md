# E2E Playwright Test Coverage Plan for Open PRs

**Created:** 2026-08-20
**Status:** AWAIT OPERATOR APPROVAL

## Overview

Review all open PRs across our repos, identify logic that needs E2E Playwright coverage, schedule kanban tasks to implement tests, capture Playwright recordings, and post them as PR comments.

## PR Audit Summary

### PRs WITH Browser UI (Playwright-applicable)

| PR | Repo | Title | Existing E2E | New Tests Needed |
|----|------|-------|---------------|------------------|
| #1240 | PlebeianApp/market | Auction: e2e tests, beta tag, whitelist, ADRs | ✅ 17 tests (4 spec files) | 0 (comprehensive) |
| #1232 | PlebeianApp/market | OG meta tags for product social previews | 1 Playwright + 23 unit | 5 new tests |
| #10 | felixfelix-bot/market | Community takeover: OG meta tags (superset of #1232) | 10+ tests (image upload, lightning mock, OG) | 5 new tests (same as #1232) |
| #11 | tidley/auditable-voting | Light theme + theme toggle | ❌ None | 11 new tests + Playwright infra setup |

### PRs WITHOUT Browser UI (Skip for Playwright)

| PR | Repo | Why Skip |
|----|------|----------|
| #3 | felixfelix-bot/market | Pure CI/infrastructure (coverage gates, mutation testing) |
| #4 | felixfelix-bot/market | Pure CI/infrastructure (preview deploys, nsite reports) |
| #14 | tidley/auditable-voting | CSV parser + OTP service are pure logic, no UI wiring yet |
| #356 | OpenTollGate/tollgate-module-basic-go | Pure Go backend (LUD-25 mint service, JSON API only) |
| #354 | OpenTollGate/tollgate-module-basic-go | Pure Go CLI tool (token recovery + audit docs) |
| #353 | OpenTollGate/tollgate-module-basic-go | Pure Go backend (vendor IE config, 14 lines) |
| #13 | net4sats/configurationwizzard | Repo cleanup (AGENTS.md, .gitignore) |

---

## Phase 1: Auditable Voting — Playwright Infrastructure + Theme Toggle Tests

**Board:** `auditable-voting-tests`
**PRs covered:** #11 (theme toggle), #14 (CSV/OTP — infra only, no UI tests yet)
**Worker:** worker-plebeian or worker-admin (TypeScript/Playwright)

### Task E2E-AV-1: Set up Playwright infrastructure for auditable-voting

**Repo:** `~/repos/auditable-voting/` (clone if not present, fork = felixfelix-bot/auditable-voting)
**Branch:** `feat/e2e-theme-toggle` (from `main`)

**Steps:**
1. Clone repo if needed: `git clone https://github.com/felixfelix-bot/auditable-voting.git ~/repos/auditable-voting`
2. Create `playwright.config.ts`:
   ```typescript
   import { defineConfig } from '@playwright/test';
   export default defineConfig({
     testDir: './e2e',
     timeout: 30000,
     fullyParallel: false,
     workers: 1,
     use: {
       baseURL: 'http://localhost:5173',
       video: 'on',
       screenshot: 'only-on-failure',
     },
     webServer: {
       command: 'npm run dev',
       port: 5173,
       reuseExistingServer: true,
       timeout: 30000,
     },
   });
   ```
3. Add `test:e2e` script to `package.json`: `"test:e2e": "npx playwright test"`
4. Create `e2e/` directory
5. Install Playwright browsers: `npx playwright install chromium`
6. Commit + push to fork: `git push fork feat/e2e-theme-toggle --no-verify`

**Verification:**
- `npx playwright test --list` shows empty test suite (infra ready, no tests yet)
- `npm run dev` starts Vite dev server on port 5173

### Task E2E-AV-2: Implement theme toggle E2E tests

**Branch:** `feat/e2e-theme-toggle`

**File:** `e2e/theme-toggle.spec.ts`

**Tests to implement (11 tests):**

1. `test: theme toggle button is visible on gateway screen`
   - Navigate to `/`
   - Assert `.simple-theme-toggle` button is visible
   - Assert `aria-label` = "Switch to light theme" (default dark)

2. `test: clicking toggle switches from dark to light theme`
   - Navigate to `/`
   - Click `.simple-theme-toggle`
   - Assert `document.documentElement.dataset.theme` = "light"
   - Assert `localStorage["av-theme"]` = "light"
   - Assert button `aria-label` = "Switch to dark theme"

3. `test: clicking toggle switches from light back to dark`
   - Start in light theme (set localStorage before goto, then goto)
   - Click toggle
   - Assert `data-theme` = "dark"
   - Assert `localStorage["av-theme"]` = "dark"

4. `test: theme persists across page reload`
   - Toggle to light
   - Reload page
   - Assert `data-theme` = "light" (preload script reads localStorage)
   - Assert toggle shows Moon icon (light is active)

5. `test: theme persists across navigation between entrypoints`
   - Set light theme on `/`
   - Navigate to `/vote.html`
   - Assert `data-theme` = "light"

6. `test: default theme is dark when no preference stored`
   - Clear `localStorage["av-theme"]`
   - Navigate to `/`
   - Assert `data-theme` = "dark"

7. `test: follows system prefers-color-scheme: light on first visit`
   - Emulate `colorScheme: 'light'` in browser context
   - Clear `localStorage["av-theme"]`
   - Navigate to `/`
   - Assert `data-theme` = "light"

8. `test: follows system prefers-color-scheme: dark on first visit`
   - Emulate `colorScheme: 'dark'`
   - Clear `localStorage["av-theme"]`
   - Navigate to `/`
   - Assert `data-theme` = "dark"

9. `test: preload script prevents FOUC (data-theme set before React)`
   - Navigate to `/`
   - Use `page.addInitScript()` to capture `document.documentElement.dataset.theme` before React hydration
   - Assert it's already set (not undefined)

10. `test: theme toggle is present after login on all roles`
    - Login as voter → toggle visible
    - Login as coordinator → toggle visible
    - Login as auditor → toggle visible

11. `test: light theme renders visible text (contrast check)`
    - Toggle to light
    - Assert `window.getComputedStyle(document.body).backgroundColor` is a light color
    - Toggle to dark
    - Assert background is dark color

**Single-flow video test** (for PR comment):
- `test: full theme toggle happy path` — one test that walks through: dark → toggle to light → verify → reload → verify persistence → toggle back to dark → verify. This produces one coherent video.

**Verification:**
- `npx playwright test e2e/theme-toggle.spec.ts --video=on` — all tests pass
- Video files in `test-results/` directory

### Task E2E-AV-3: Record Playwright video and post to PR #11

**Steps:**
1. Run the single-flow happy path test with video: `npx playwright test e2e/theme-toggle.spec.ts -g "full theme toggle happy path" --video=on --output=test-results/video`
2. Convert webm to mp4: `find test-results/ -name "video.webm" -exec ffmpeg -y -i {} -c:v libx264 -preset fast -crf 28 -vf "scale=1280:720" {}.mp4 \;`
3. Upload video to Blossom server (or attach directly via gh CLI if < 10MB)
4. Post comment on PR #11 (tidley/auditable-voting):
   ```bash
   GH_TOKEN=$(cat ~/reviews/.ghtoken) gh pr comment 11 --repo tidley/auditable-voting --body "## E2E Playwright Test Evidence

   Theme toggle E2E tests: **11/11 passing** ✅

   ### Test Coverage
   - Theme toggle button visibility on gateway screen ✅
   - Dark → Light theme switch ✅
   - Light → Dark theme switch ✅
   - Theme persistence across reload ✅
   - Theme persistence across page navigation ✅
   - Default dark theme (no preference) ✅
   - System prefers-color-scheme: light fallback ✅
   - System prefers-color-scheme: dark fallback ✅
   - FOUC prevention (preload script) ✅
   - Toggle available on all role screens ✅
   - Light theme contrast check ✅

   ### Video Recording
   [Link to video or MEDIA attachment]

   ### Test File
   \`e2e/theme-toggle.spec.ts\` — 11 tests + 1 happy path flow test"
   ```
5. If #14 is still open, post a similar comment noting the CSV/OTP modules have unit test coverage and will get E2E tests when UI is built

**Quality gates:**
- Tests must pass before posting comment
- Video must show the full toggle flow (dark → light → reload → dark)
- Commit tests to `feat/e2e-theme-toggle` branch on fork

---

## Phase 2: Plebeian Market — OG Meta Tags E2E Tests

**Board:** `plebeian-market-e2e-infra`
**PRs covered:** #1232 (upstream), #10 (fork superset)
**Worker:** worker-plebeian (TypeScript/Playwright)

### Task E2E-PM-1: Implement OG meta tags E2E tests

**Repo:** `~/repos/market/` (PlebeianApp/market clone)
**Branch:** `community/459-og-meta-tags` (already has the OG meta feature)

**File:** `e2e/tests/og-meta-tags.spec.ts` (new) — extends existing `e2e/tests/product-page.spec.ts`

**Prerequisites:**
- Dev server running on port 34569 with required env vars:
  ```
  NODE_ENV=test PORT=34569 APP_RELAY_URL=ws://localhost:10547
  APP_PRIVATE_KEY=e2e0000000000000000000000000000000000000000000000000000000000001
  CVM_SERVER_KEY=e2e2222222222222222222222222222222222222222222222222222222222222
  LOCAL_RELAY_ONLY=true NIP46_RELAY_URL=ws://localhost:10547
  ```
- nak relay running on port 10547

**Tests to implement (5 tests):**

1. `test: NSFW product page does NOT leak OG meta tags in initial HTML`
   - Seed an NSFW product (kind-30402 with `content_warning: nsfw` tag) to relay
   - Fetch `/products/{nsfwProductId}` via raw HTTP (`page.request.get`)
   - Assert response is 200
   - Assert `og:title` NOT in response HTML
   - Assert `og:image` NOT in response HTML

2. `test: unknown product ID serves shell without OG tags`
   - Fetch `/products/nonexistent-id-12345` via raw HTTP
   - Assert response is 200 (shell served)
   - Assert `og:title` NOT in HTML (graceful degradation)

3. `test: client-side document.title updates after SPA load`
   - Navigate to product page in browser
   - Wait for SPA hydration (`networkidle` or `domcontentloaded` + timeout)
   - Assert `document.title` contains product title
   - Assert `document.title` contains "Plebeian Market"

4. `test: meta tags persist after SPA hydration`
   - Navigate to product page
   - Wait for load
   - Assert `meta[property="og:title"]` still present (server tags not clobbered)
   - Assert `meta[property="og:image"]` still present

5. `test: product price meta tags present in initial HTML`
   - Fetch `/products/{productId}` via raw HTTP
   - Assert `product:price:amount` meta tag present with correct value
   - Assert `product:price:currency` meta tag present with correct value

**Single-flow video test** (for PR comment):
- `test: full OG meta tags happy path` — fetch raw HTML → verify all OG tags → load in browser → verify SPA hydration → verify tags persist

**Verification:**
- `npx playwright test e2e/tests/og-meta-tags.spec.ts --config=e2e/playwright.config.ts --video=on`
- All tests pass

### Task E2E-PM-2: Record Playwright video and post to PR #1232

**Steps:**
1. Run single-flow happy path test with video
2. Convert webm to mp4
3. Upload to Blossom or attach via gh
4. Post comment on PR #1232 (PlebeianApp/market):
   ```bash
   GH_TOKEN=$(cat ~/reviews/.ghtoken) gh pr comment 1232 --repo PlebeianApp/market --body "## E2E Playwright Test Evidence

   OG meta tags E2E tests: **5/5 passing** ✅

   ### Test Coverage
   - NSFW product does not leak OG meta tags ✅
   - Unknown product ID graceful degradation ✅
   - Client-side document.title updates after SPA load ✅
   - Meta tags persist after SPA hydration ✅
   - Product price/currency meta tags present ✅

   ### Video Recording
   [Link to video or MEDIA attachment]

   ### Test File
   \`e2e/tests/og-meta-tags.spec.ts\`"
   ```
5. Post similar comment on PR #10 (felixfelix-bot/market) if still open

---

## Phase 3: Verification and Wrap-up

### Task E2E-WRAP-1: Verify all test videos posted to PRs

**Steps:**
1. Check that PR #11 (tidley/auditable-voting) has a comment with video evidence
2. Check that PR #1232 (PlebeianApp/market) has a comment with video evidence
3. Check that PR #10 (felixfelix-bot/market) has a comment with video evidence (or cross-reference to #1232)
4. Verify PR #1240 already has comprehensive E2E tests (17 tests in 4 spec files) — no new tests needed, but consider posting a comment acknowledging the existing coverage
5. Update session-notes.md with completion status

---

## Execution Order

```
Phase 1 (parallel):
  E2E-AV-1 → E2E-AV-2 → E2E-AV-3  (auditable-voting: infra → tests → video → PR comment)
  E2E-PM-1 → E2E-PM-2              (plebeian market: tests → video → PR comment)

Phase 2:
  E2E-WRAP-1  (verification)
```

## Boards

- **auditable-voting-tests** — for AV tasks (E2E-AV-1, E2E-AV-2, E2E-AV-3)
- **plebeian-market-e2e-infra** — for PM tasks (E2E-PM-1, E2E-PM-2)

## Worker Assignment

- **worker-plebeian** (TypeScript/Playwright expert) — both AV and PM tasks
  - Model: kimi-k2.7-code (quota-resilient, TS/Playwright specialist)
  - Or: glm-5.2 if kimi unavailable

## Key Constraints

1. **Tests MUST pass before posting PR comments** — no fabricated evidence
2. **Videos MUST show real test execution** — not mock/placeholder
3. **PR comments MUST include test count, pass/fail status, and video link**
4. **All work committed and pushed** to fork branches (never upstream main directly)
5. **Plebeian Market dev server** requires specific env vars (APP_PRIVATE_KEY, CVM_SERVER_KEY, etc.) — missing CVM_SERVER_KEY crashes the server
6. **Auditable Voting** has zero Playwright infra — must create config + e2e/ dir first
7. **Plebeian PRs** target `auctions` branch (#1240) and `master` (#1232) — different base branches
8. **Plebeian gate**: felixfelix-bot PRs need external review FIRST (only maximotodev/Franchovy), then c03rad0r merges