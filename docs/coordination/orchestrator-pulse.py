#!/usr/bin/env python3
"""
Balloon Orchestrator Pulse — reads all track statuses from worktrees,
builds dependency graph, detects blocked chains, outputs master timeline.

Usage:
    python3 orchestrator-pulse.py           # full report
    python3 orchestrator-pulse.py --json     # machine-readable output
    python3 orchestrator-pulse.py --silent    # exit 0 if nothing actionable, 1 if blocked

Reads:
    - TRACKS-REGISTRY.yaml for track definitions + dependencies
    - Each track's worktree for git log (last commit)
    - Each track's docs/INTEGRATION-ASSESSMENT.md for readiness data
    - Each track's docs/STATUS-<track>.md for latest status pull
    - Hermes kanban boards (if configured in registry)
    - DECISIONS-AND-BLOCKERS.md for open decisions
"""
import yaml
import os
import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime

REPO = Path.home() / "repos" / "balloon-fresh"
COORD_DIR = REPO / "docs" / "coordination"
REGISTRY_PATH = COORD_DIR / "TRACKS-REGISTRY.yaml"
DECISIONS_PATH = COORD_DIR / "DECISIONS-AND-BLOCKERS.md"


def load_registry():
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)


def git_last_commit(worktree):
    """Get last commit hash + message from a worktree."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, cwd=worktree, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "no commits / not a git repo"


def read_assessment(worktree):
    """Read integration assessment if it exists."""
    path = Path(worktree) / "docs" / "INTEGRATION-ASSESSMENT.md"
    if not path.exists():
        return None
    content = path.read_text()
    # Extract key fields
    has_depends = "## Dependencies on Other Tracks" in content
    has_blockers = "## Blockers for ESP32-C3 Port" in content
    has_checklist = "## Integration Checklist" in content
    has_questions = "## Questions for the Coordinator" in content
    return {
        "exists": True,
        "has_dependencies": has_depends,
        "has_blockers": has_blockers,
        "has_checklist": has_checklist,
        "has_questions": has_questions,
        "lines": len(content.splitlines()),
    }


def read_status_file(worktree, track_name):
    """Read latest status pull if it exists."""
    path = Path(worktree) / "docs" / f"STATUS-{track_name}.md"
    if not path.exists():
        return None
    content = path.read_text()
    return {"exists": True, "lines": len(content.splitlines()), "content": content[:500]}


def check_kanban(board_slug):
    """Check kanban board if configured."""
    if not board_slug:
        return None
    try:
        result = subprocess.run(
            ["hermes", "kanban", "--board", board_slug, "ls", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            tasks = json.loads(result.stdout)
            done = sum(1 for t in tasks if t.get("status") == "done")
            total = len(tasks)
            blocked = sum(1 for t in tasks if t.get("status") == "blocked")
            running = sum(1 for t in tasks if t.get("status") == "running")
            ready = sum(1 for t in tasks if t.get("status") == "ready")
            return {
                "done": done, "total": total, "blocked": blocked,
                "running": running, "ready": ready
            }
    except Exception:
        pass
    return None


def build_dependency_graph(registry):
    """Build a directed graph from depends_on relationships."""
    tracks = registry.get("tracks", [])
    graph = {}
    for track in tracks:
        name = track["name"]
        deps = track.get("depends_on", [])
        blocks = track.get("blocks", [])
        graph[name] = {"depends_on": deps, "blocks": blocks}

    # Detect cycles
    def has_cycle(node, visited, stack):
        if node in stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for dep in graph.get(node, {}).get("depends_on", []):
            if has_cycle(dep, visited, stack):
                return True
        stack.discard(node)
        return False

    visited = set()
    cycles = []
    for node in graph:
        if node not in visited:
            if has_cycle(node, visited, set()):
                cycles.append(node)

    return graph, cycles


def find_critical_path(graph, tracks_info):
    """Find the longest dependency chain (critical path)."""
    def chain_length(node, memo={}):
        if node in memo:
            return memo[node]
        deps = graph.get(node, {}).get("depends_on", [])
        if not deps:
            memo[node] = 1
            return 1
        length = 1 + max(chain_length(dep, memo) for dep in deps)
        memo[node] = length
        return length

    longest = 0
    critical = []
    for node in graph:
        length = chain_length(node)
        if length > longest:
            longest = length
            critical = [node]

    # Reconstruct the chain
    if critical:
        chain = [critical[0]]
        current = critical[0]
        while True:
            deps = graph.get(current, {}).get("depends_on", [])
            if not deps:
                break
            # Pick the dep with the longest chain
            best_dep = max(deps, key=lambda d: chain_length(d))
            chain.append(best_dep)
            current = best_dep
        chain.reverse()
        return chain
    return []


def generate_report(registry, graph, cycles, critical_path, track_data):
    """Generate the full orchestrator report."""
    lines = []
    lines.append("# Balloon Orchestrator Pulse Report")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")

    # Summary
    tracks = registry.get("tracks", [])
    total = len(tracks)
    assessed = sum(1 for t in track_data if t.get("assessment"))
    blocked = sum(1 for t in track_data if t.get("blockers"))
    lines.append(f"## Summary")
    lines.append(f"- Total tracks: {total}")
    lines.append(f"- Assessments complete: {assessed}/{total}")
    lines.append(f"- Tracks with blockers: {blocked}")
    lines.append(f"- Critical path length: {len(critical_path)} tracks")
    lines.append("")

    # Dependency graph
    lines.append("## Dependency Graph")
    lines.append("```")
    for name, info in graph.items():
        deps = info.get("depends_on", [])
        blocks = info.get("blocks", [])
        if deps:
            lines.append(f"  {' -> '.join(deps)} -> [{name}]")
        else:
            lines.append(f"  [{name}] (no deps)")
        if blocks:
            lines.append(f"    blocks: {', '.join(blocks)}")
    lines.append("```")
    lines.append("")

    # Critical path
    if critical_path:
        lines.append("## Critical Path (longest dependency chain)")
        lines.append("```")
        for i, track in enumerate(critical_path):
            prefix = "  START -> " if i == 0 else "           -> "
            lines.append(f"{prefix}{track}")
        lines.append("```")
        lines.append("")

    # Cycle detection
    if cycles:
        lines.append("## ⚠ CYCLE DETECTED")
        lines.append(f"Circular dependencies found involving: {', '.join(cycles)}")
        lines.append("")

    # Per-track status
    lines.append("## Per-Track Status")
    lines.append("")
    lines.append("| Track | Phase | Last Commit | Assessment | Kanban | Blockers |")
    lines.append("|-------|-------|-------------|------------|--------|----------|")
    for i, track in enumerate(tracks):
        td = track_data[i]
        name = track["name"]
        phase = track.get("phase", "?")
        commit = td.get("last_commit", "?")[:50]
        assess = "✓" if td.get("assessment") else "✗"
        kanban = ""
        if td.get("kanban"):
            k = td["kanban"]
            kanban = f"{k['done']}/{k['total']} ({k['blocked']}b)"
        blockers = "Yes" if td.get("has_blockers") else "None"
        lines.append(f"| {name} | {phase} | {commit} | {assess} | {kanban} | {blockers} |")
    lines.append("")

    # Blocked chains
    lines.append("## Blocked Dependency Chains")
    for name, info in graph.items():
        deps = info.get("depends_on", [])
        if deps:
            unready_deps = []
            for dep in deps:
                dep_track = next((t for t in tracks if t["name"] == dep), None)
                if dep_track and dep_track.get("phase") != "execution":
                    unready_deps.append(dep)
            if unready_deps:
                lines.append(f"- **{name}** blocked by: {', '.join(unready_deps)}")
                lines.append(f"  Resolution: {', '.join(unready_deps)} must reach execution phase")
    lines.append("")

    # Open decisions
    decisions = registry.get("open_decisions", [])
    if decisions:
        lines.append("## Open Decisions")
        for d in decisions:
            status_icon = "🔴" if d["status"] == "open" else "🟢"
            lines.append(f"- {status_icon} {d['id']}: {d['topic']} [{d['status']}]")
        lines.append("")

    # Shared resources
    resources = registry.get("shared_resources", [])
    if resources:
        lines.append("## Shared Resource Conflicts")
        for r in resources:
            if r["status"] == "open" or r["status"] == "limited":
                needed = ", ".join(r.get("needed_by", []))
                lines.append(f"- **{r['name']}** — needed by: {needed} [{r['status']}]")
        lines.append("")

    return "\n".join(lines)


def main():
    output_json = "--json" in sys.argv
    silent = "--silent" in sys.argv

    registry = load_registry()
    tracks = registry.get("tracks", [])

    track_data = []
    for track in tracks:
        worktree = os.path.expanduser(track["worktree"])
        td = {
            "name": track["name"],
            "last_commit": git_last_commit(worktree),
            "assessment": read_assessment(worktree),
            "status_file": read_status_file(worktree, track["name"]),
            "kanban": check_kanban(track.get("kanban_board")),
        }
        track_data.append(td)

    graph, cycles = build_dependency_graph(registry)
    critical_path = find_critical_path(graph, {})

    if silent:
        has_blockers = any(td.get("has_blockers") for td in track_data)
        has_cycles = len(cycles) > 0
        if has_blockers or has_cycles:
            sys.exit(1)
        sys.exit(0)

    report = generate_report(registry, graph, cycles, critical_path, track_data)

    if output_json:
        print(json.dumps({
            "generated": datetime.now().isoformat(),
            "tracks": track_data,
            "graph": graph,
            "cycles": cycles,
            "critical_path": critical_path,
        }, indent=2))
    else:
        print(report)


if __name__ == "__main__":
    main()