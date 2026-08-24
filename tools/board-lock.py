"""
Simplified board lock helper for TollGate hardware testing.
Integrates with balloon-board-lock.py but provides a simpler interface for pytest and Make targets.
"""

import os
import sys
import subprocess
import json
import argparse
from pathlib import Path


def run_lock_command(args):
    """Run balloon-board-lock.py command and return result."""
    # Set BALLOON_TRACK environment variable
    env = os.environ.copy()
    env["BALLOON_TRACK"] = "tollgate"
    
    # Build command
    script_path = Path(__file__).parent.parent / "tools" / "balloon-board-lock.py"
    cmd = [sys.executable, str(script_path)] + args
    
    # Run command
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Hardware board lock helper for TollGate testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  BALLOON_TRACK=tollgate %(prog)s acquire tx --purpose "flash firmware" --timeout 60
  BALLOON_TRACK=tollgate %(prog)s acquire esp32-tx --purpose "ESP32 programming" --timeout 120
  BALLOON_TRACK=tollgate %(prog)s release tx
  %(prog)s check tx  # exit 0 if we hold tx lock
  %(prog)s status
        """
    )
    
    parser.add_argument("action", choices=["acquire", "release", "status", "check"],
                        help="Action to perform")
    parser.add_argument("resource", nargs="?",
                        choices=["tx", "rx", "both", "esp32-tx", "esp32-rx", "esp32-both"],
                        help="Which board(s) to lock/unlock/check")
    parser.add_argument("--purpose", default="hardware testing",
                        help="Why you need the board (shown to other sessions)")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Max seconds to wait for lock (default: 60)")
    parser.add_argument("--force", action="store_true",
                        help="Force release even if not ours")
    parser.add_argument("--steal", action="store_true",
                        help="Take a lock from another track (logged)")
    
    args = parser.parse_args()

    if args.action == "status":
        result = run_lock_command(["status"])
        print(result.stdout)
        sys.exit(result.returncode)

    if not args.resource:
        print("Error: resource required for acquire/release/check", file=sys.stderr)
        sys.exit(2)

    # Map tollgate-specific resource names to balloon-board-lock names
    resource_map = {
        "tx": "tx",
        "rx": "rx", 
        "both": "both",
        "esp32-tx": "board-a",
        "esp32-rx": "board-b", 
        "esp32-both": "all-s3"
    }
    
    balloon_resource = resource_map.get(args.resource)
    if not balloon_resource:
        print(f"Error: unknown resource {args.resource}", file=sys.stderr)
        sys.exit(2)

    if args.action == "acquire":
        cmd_args = ["acquire", balloon_resource, "--purpose", args.purpose, "--timeout", str(args.timeout)]
        result = run_lock_command(cmd_args)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    elif args.action == "release":
        cmd_args = ["release", balloon_resource]
        if args.force:
            cmd_args.append("--force")
        if args.steal:
            cmd_args.append("--steal")
        result = run_lock_command(cmd_args)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    elif args.action == "check":
        cmd_args = ["check", balloon_resource]
        result = run_lock_command(cmd_args)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()