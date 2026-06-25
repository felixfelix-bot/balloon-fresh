#!/usr/bin/env python3
"""
gh_ngit_watchdog.py — Dual-platform GitHub + Nostr (ngit) decision monitor

Monitors GitHub issues/PRs across multiple repos, detects items needing
decisions, and cross-posts summaries to Nostr via nak/ngit.

Usage:
  python3 gh_ngit_watchdog.py                    # one-shot scan + report
  python3 gh_ngit_watchdog.py --daemon           # continuous polling
  python3 gh_ngit_watchdog.py --post-reply 2739  # post suggested reply to GH issue
  python3 gh_ngit_watchdog.py --nostr-mirror     # mirror current state to Nostr

Config: gh_ngit_watchdog_config.json (auto-created on first run)

Requires: gh CLI (authenticated), nak CLI, requests
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# ─── Constants ──────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "gh_ngit_watchdog_config.json"
STATE_FILE = SCRIPT_DIR / "gh_ngit_watchdog_state.json"
LOG_FILE = SCRIPT_DIR / "gh_ngit_watchdog.log"

NOSTR_FOOTER = (
    "\n\n---\n📎 *This update is also mirrored on Nostr via [ngit](https://gitworkshop.dev). "
    "If you use ngit/nostr, feel free to respond there — "
    "[relay.ngit.dev](https://relay.ngit.dev)*"
)

# Repos to monitor (owner/repo format)
DEFAULT_REPOS = [
    "meshcore-dev/MeshCore",
    "PlebeianApp/market",
    "OpenTollGate/tollgate-module-basic-go",
    "OpenTollGate/physical-router-test-automation",
    "DanConwayDev/ngit-relay",
    "jgromes/RadioLib",
    "net4sats/configurationwizzard",
]

# GitHub username to track
WATCH_USER = "c03rad0r"

# Decision patterns in issue/PR bodies and comments
DECISION_KEYWORDS = [
    "changes requested",
    "request changes",
    "merge conflict",
    "blocked",
    "blocking",
    "cannot merge",
    "action required",
    "decision needed",
    "needs input",
    "waiting on",
    "review needed",
    "please address",
    "security concern",
    "vulnerability",
    "approve always",
    "ready for review",
    "rfr",
]

# ─── Logging ────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{ts}] [{level}] {msg}"
    print(line, file=sys.stderr)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ─── Config / State ─────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    config = {
        "repos": DEFAULT_REPOS,
        "watch_user": WATCH_USER,
        "nostr_relays": [
            "wss://relay.orangesync.tech",
            "wss://relay.ngit.dev",
        ],
        "poll_interval_seconds": 300,
        "ngit_repos": {
            "esp32-balloon-integration": "nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/esp32-balloon-integration",
        },
        "auto_reply": False,  # Don't auto-post without human approval
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    log(f"Created config at {CONFIG_FILE}")
    return config

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_scan": {}, "seen_comments": {}, "posted": {}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ─── GitHub API via gh CLI ──────────────────────────────────────────────

def gh_api(endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    """Call GitHub API using gh CLI for auth."""
    cmd = ["gh", "api", endpoint]
    if params:
        for k, v in params.items():
            cmd.extend(["-F", f"{k}={v}"])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception as e:
        log(f"gh api failed for {endpoint}: {e}", "ERROR")
    return None

def gh_api_raw(url: str) -> Optional[dict]:
    """Call GitHub API directly with gh auth token."""
    try:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"GitHub API request failed: {url}: {e}", "ERROR")
        return None

def get_open_prs(repo: str) -> List[dict]:
    """Get open PRs in a repo."""
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&sort=updated&direction=desc&per_page=20"
    data = gh_api_raw(url)
    return data or []

def get_open_issues(repo: str) -> List[dict]:
    """Get open issues in a repo."""
    url = f"https://api.github.com/repos/{repo}/issues?state=open&sort=updated&direction=desc&per_page=20"
    data = gh_api_raw(url)
    # Filter out PRs (they appear in issues endpoint)
    return [i for i in (data or []) if "pull_request" not in i]

def get_recent_comments(repo: str, number: int, since: Optional[str] = None) -> List[dict]:
    """Get recent comments on an issue/PR."""
    url = f"https://api.github.com/repos/{repo}/issues/{number}/comments?sort=created&direction=desc&per_page=5"
    data = gh_api_raw(url)
    if not data:
        return []
    if since:
        data = [c for c in data if c.get("created_at", "") > since]
    return data

def get_pr_reviews(repo: str, pr_number: int) -> List[dict]:
    """Get review state for a PR."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews?sort=created&direction=desc&per_page=5"
    data = gh_api_raw(url)
    return data or []

# ─── Decision detection ─────────────────────────────────────────────────

def check_needs_decision(repo: str, item: dict, state: dict, config: dict) -> Optional[dict]:
    """
    Check if an issue/PR needs a decision from the user.
    Returns a decision dict if action needed, None otherwise.
    """
    number = item.get("number", 0)
    title = item.get("title", "")
    body = (item.get("body") or "").lower()
    updated = item.get("updated_at", "")
    item_type = "PR" if "pull_request" in item else "Issue"
    author = item.get("user", {}).get("login", "")
    key = f"{repo}#{number}"

    # Skip if we've already reported this item and it hasn't changed
    last_seen = state.get("last_scan", {}).get(key, "")
    if last_seen == updated:
        return None

    # Check for decision keywords in title/body
    keyword_hits = [kw for kw in DECISION_KEYWORDS if kw in body or kw in title.lower()]
    
    # Check review state for PRs
    review_state = None
    if item_type == "PR":
        reviews = get_pr_reviews(repo, number)
        if reviews:
            review_state = reviews[0].get("state", "")
    
    # Check recent comments for reviewer requests
    recent_comments = get_recent_comments(repo, number, since=last_seen)
    needs_response = False
    comment_summary = ""
    
    for comment in recent_comments:
        cbody = (comment.get("body") or "").lower()
        comment_author = comment.get("user", {}).get("login", "")
        # Only flag if comment is from someone else (not our own)
        if comment_author != config["watch_user"]:
            if any(kw in cbody for kw in DECISION_KEYWORDS):
                needs_response = True
                comment_summary = f"@{comment_author}: {comment.get('body', '')[:200]}"
                break
            # Any comment from maintainer on our PR = potential response needed
            if author == config["watch_user"] and comment_author != config["watch_user"]:
                needs_response = True
                comment_summary = f"@{comment_author}: {comment.get('body', '')[:200]}"
                break
    
    # Determine if decision is needed
    is_author = author == config["watch_user"]
    decision_needed = False
    reason = ""
    priority = "low"
    
    if review_state == "CHANGES_REQUESTED" and is_author:
        decision_needed = True
        reason = f"Changes requested by reviewer on your PR"
        priority = "high"
    elif needs_response and is_author:
        decision_needed = True
        reason = f"New comment from maintainer/reviewer"
        priority = "medium"
    elif keyword_hits and is_author:
        decision_needed = True
        reason = f"Keywords: {', '.join(keyword_hits[:3])}"
        priority = "medium"
    elif "security" in body and is_author:
        decision_needed = True
        reason = "Security-related issue"
        priority = "high"
    
    if not decision_needed:
        return None
    
    # Update state
    state["last_scan"][key] = updated
    
    return {
        "repo": repo,
        "number": number,
        "title": title,
        "type": item_type,
        "author": author,
        "reason": reason,
        "priority": priority,
        "comment_summary": comment_summary,
        "review_state": review_state,
        "url": f"https://github.com/{repo}/pull/{number}" if item_type == "PR" 
               else f"https://github.com/{repo}/issues/{number}",
        "updated_at": updated,
        "keyword_hits": keyword_hits,
    }

# ─── Nostr cross-posting ────────────────────────────────────────────────

def post_to_nostr(content: str, config: dict, kind: int = 1) -> bool:
    """Post a text note to Nostr via nak."""
    relays = config.get("nostr_relays", ["wss://relay.ngit.dev"])
    relay_args = []
    for r in relays:
        relay_args.extend(["--relay", r])
    
    try:
        cmd = ["nak", "event"] + relay_args + ["-k", str(kind)] + ["-c", content]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            # Parse the event ID from output
            try:
                event = json.loads(r.stdout)
                event_id = event.get("id", "unknown")
                log(f"Posted to Nostr: {event_id[:16]}...")
                return True
            except:
                log(f"Posted to Nostr (no event ID parsed)")
                return True
        else:
            log(f"nak event failed: {r.stderr[:200]}", "ERROR")
            return False
    except Exception as e:
        log(f"Nostr post failed: {e}", "ERROR")
        return False

def check_ngit_sync(repo_name: str, config: dict) -> dict:
    """Check if an ngit remote is up to date."""
    ngit_url = config.get("ngit_repos", {}).get(repo_name)
    if not ngit_url:
        return {"synced": False, "reason": "No ngit remote configured"}
    
    # Check if we can fetch from the ngit remote
    repo_path = Path.home() / repo_name
    if not repo_path.exists():
        return {"synced": False, "reason": f"Repo not found at {repo_path}"}
    
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        origin_url = r.stdout.strip()
        is_ngit = "nostr://" in origin_url
        
        # Check last commit
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        last_commit = r.stdout.strip()
        
        return {
            "synced": is_ngit,
            "origin": origin_url,
            "last_commit": last_commit,
            "repo_path": str(repo_path),
        }
    except Exception as e:
        return {"synced": False, "reason": str(e)}

# ─── Report generation ──────────────────────────────────────────────────

def generate_report(decisions: List[dict], config: dict) -> str:
    """Generate a human-readable report of decisions needed."""
    if not decisions:
        return "✅ No decisions needed — all clear."
    
    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    decisions.sort(key=lambda d: priority_order.get(d["priority"], 3))
    
    lines = [f"# 🔔 GitHub Decision Report — {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC"]
    lines.append(f"_{len(decisions)} item(s) need attention_\n")
    
    high = [d for d in decisions if d["priority"] == "high"]
    medium = [d for d in decisions if d["priority"] == "medium"]
    low = [d for d in decisions if d["priority"] == "low"]
    
    if high:
        lines.append("## 🔴 High Priority\n")
        for d in high:
            lines.append(f"### [{d['type']}] {d['repo']}#{d['number']}: {d['title']}")
            lines.append(f"- **Reason**: {d['reason']}")
            if d["review_state"]:
                lines.append(f"- **Review state**: {d['review_state']}")
            if d["comment_summary"]:
                lines.append(f"- **Latest comment**: {d['comment_summary']}")
            lines.append(f"- **URL**: {d['url']}")
            lines.append("")
    
    if medium:
        lines.append("## 🟡 Medium Priority\n")
        for d in medium:
            lines.append(f"### [{d['type']}] {d['repo']}#{d['number']}: {d['title']}")
            lines.append(f"- **Reason**: {d['reason']}")
            if d["comment_summary"]:
                lines.append(f"- **Latest comment**: {d['comment_summary'][:150]}")
            lines.append(f"- **URL**: {d['url']}")
            lines.append("")
    
    if low:
        lines.append("## 🟢 Low Priority\n")
        for d in low:
            lines.append(f"- [{d['type']}] {d['repo']}#{d['number']}: {d['title']} — {d['reason']}")
            lines.append(f"  {d['url']}")
    
    # Nostr sync status
    lines.append("\n## 📡 Nostr/ngit Status")
    for repo_name in config.get("ngit_repos", {}):
        sync = check_ngit_sync(repo_name, config)
        status = "✅" if sync["synced"] else "⚠️"
        lines.append(f"- {status} **{repo_name}**: {sync.get('origin', sync.get('reason', 'unknown'))}")
    
    return "\n".join(lines)

# ─── Main scan ──────────────────────────────────────────────────────────

def scan(config: dict, state: dict) -> List[dict]:
    """Scan all monitored repos for decisions needed."""
    all_decisions = []
    
    for repo in config["repos"]:
        log(f"Scanning {repo}...")
        
        # Get PRs
        prs = get_open_prs(repo)
        for pr in prs:
            d = check_needs_decision(repo, pr, state, config)
            if d:
                all_decisions.append(d)
        
        # Get issues
        issues = get_open_issues(repo)
        for issue in issues:
            d = check_needs_decision(repo, issue, state, config)
            if d:
                all_decisions.append(d)
    
    save_state(state)
    return all_decisions

def run_one_shot(config: dict):
    """Run a single scan and print report."""
    state = load_state()
    decisions = scan(config, state)
    report = generate_report(decisions, config)
    print(report)
    return decisions

def run_daemon(config: dict):
    """Run continuous monitoring."""
    interval = config.get("poll_interval_seconds", 300)
    log(f"Starting daemon mode (polling every {interval}s)")
    
    while True:
        try:
            state = load_state()
            decisions = scan(config, state)
            
            if decisions:
                report = generate_report(decisions, config)
                log(f"Found {len(decisions)} decisions needing attention")
                # Print to stdout for cron capture
                print(report)
                
                # Mirror to Nostr
                if config.get("nostr_relays"):
                    nostr_msg = f"🔔 {len(decisions)} GitHub items need attention. "
                    nostr_msg += "; ".join(f"{d['repo']}#{d['number']}" for d in decisions[:5])
                    post_to_nostr(nostr_msg, config)
            else:
                log("No decisions needed")
                
        except Exception as e:
            log(f"Scan error: {e}", "ERROR")
        
        time.sleep(interval)

# ─── Post reply ─────────────────────────────────────────────────────────

def post_github_reply(repo: str, number: int, body: str, config: dict) -> bool:
    """Post a comment on a GitHub issue/PR with ngit footer."""
    full_body = body + NOSTR_FOOTER
    url = f"https://api.github.com/repos/{repo}/issues/{number}/comments"
    
    try:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
        headers = {"Authorization": f"token {token}"}
        r = requests.post(url, json={"body": full_body}, headers=headers, timeout=15)
        r.raise_for_status()
        log(f"Posted reply to {repo}#{number}")
        
        # Also post to Nostr
        nostr_content = f"[gh:{repo}#{number}] {body[:200]}"
        post_to_nostr(nostr_content, config)
        
        return True
    except Exception as e:
        log(f"Failed to post reply: {e}", "ERROR")
        return False

# ─── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GitHub + Nostr decision watchdog")
    parser.add_argument("--daemon", action="store_true", help="Run as continuous daemon")
    parser.add_argument("--post-reply", type=int, metavar="NUMBER", help="Post a reply to a GH item")
    parser.add_argument("--repo", type=str, help="Repo (for --post-reply)")
    parser.add_argument("--message", type=str, help="Reply message (for --post-reply)")
    parser.add_argument("--nostr-mirror", action="store_true", help="Mirror current state to Nostr")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    config = load_config()
    
    if args.post_reply:
        if not args.repo or not args.message:
            print("Error: --repo and --message required with --post-reply")
            sys.exit(1)
        success = post_github_reply(args.repo, args.post_reply, args.message, config)
        sys.exit(0 if success else 1)
    
    if args.nostr_mirror:
        state = load_state()
        decisions = scan(config, state)
        report = generate_report(decisions, config)
        post_to_nostr(report[:5000], config)  # Nostr text note limit
        print("Mirrored to Nostr")
        return
    
    if args.daemon:
        run_daemon(config)
    else:
        decisions = run_one_shot(config)
        if args.json:
            print(json.dumps(decisions, indent=2))

if __name__ == "__main__":
    main()
