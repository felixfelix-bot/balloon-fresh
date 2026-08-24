# Balloon Project — Decisions & Blockers Log

**Maintained by:** balloon-hermes (coordinator)
**Purpose:** Track decisions you need to make and blockers that stop progress.
Updated as assessments arrive from track groups.

---

## DECISIONS NEEDED FROM YOU

### D-001: Hardware Allocation — ESP32-S3 Boards
**Status:** OPEN
**Asked by:** balloon-tollgate, balloon-pow
**Question:** 3 ESP32-S3 boards exist (Board A/B/C). Multiple tracks need them for testing. Who gets priority?
**Options:**
  1. Tollgate first (already running on them, verify extraction)
  2. PoW first (needs to measure hashrate, power)
  3. Time-share (each track gets boards for X hours)
**Impact:** Blocks standalone verification for tollgate + pow tracks.

### D-002: microfips Git Remote
**Status:** OPEN
**Asked by:** balloon-fips
**Question:** ~/repos/microfips-upstream/ has no git remote. Create a GitHub repo for it?
**Options:**
  1. New repo (c03rad0r/microfips or balloon-specific org)
  2. Push to existing upstream
**Impact:** FIPS track can't push work without a remote.

### D-003: Blossom Server — New GitHub Repo
**Status:** OPEN
**Asked by:** balloon-blossom
**Question:** balloon-blossom worktree is a new repo with no remote. Create a GitHub repo for it?
**Options:**
  1. c03rad0r/balloon-blossom
  2. Under balloon org
**Impact:** Blossom track can't push work without a remote.

---

## BLOCKERS YOU NEED TO ADDRESS

(Will be populated as track assessments arrive with their blocker reports)

### B-001: [awaiting assessments]
**Status:** Pending
**Track:** TBD
**Blocker:** TBD
**What you need to do:** TBD

---

## RESOLVED DECISIONS

(none yet)

---

## RESOLVED BLOCKERS

(none yet)
